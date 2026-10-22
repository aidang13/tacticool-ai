import hashlib
import hmac
import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from ffl import runtime as rt_module
from ffl.webhooks import verify_fastbound_signature
from tests.conftest import FB_ITEM


@pytest.fixture
def app_client(world, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("FFL_MCP_SECRET", "mcpsecret")
    monkeypatch.setenv("FFL_POLL_SECONDS", "0")
    monkeypatch.setenv("FFL_DB_PATH", world.settings.db_path)
    # Make the app's runtime use the fake-backed clients.
    r = rt_module.Runtime.__new__(rt_module.Runtime)
    r.settings, r.store, r.fb, r.clover, r.sync = world.settings, world.store, world.fb, world.clover, world.sync
    rt_module.reset_runtime(r)
    import importlib
    import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c
    rt_module.reset_runtime(None)


def _sign(secret: str, raw: bytes, t: int | None = None) -> str:
    t = t or int(time.time())
    v1 = hmac.new(secret.encode(), f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"


def test_signature_verification():
    raw = b'{"a":1}'
    assert verify_fastbound_signature("s", raw, _sign("s", raw))
    assert not verify_fastbound_signature("s", raw, _sign("wrong", raw))
    assert not verify_fastbound_signature("s", raw, _sign("s", raw, t=int(time.time()) - 3600))
    assert not verify_fastbound_signature("s", raw, "garbage")


def test_fastbound_webhook_rejects_bad_signature(app_client):
    r = app_client.post("/webhooks/fastbound", content=b"{}", headers={"X-FastBound-Signature": "t=1,v1=00"})
    assert r.status_code == 401


def test_fastbound_webhook_dispatches_and_dedupes(app_client, world):
    world.sync.push_firearm_to_clover(FB_ITEM)
    body = json.dumps({"id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd", "is4473": True, "isManufacturingDisposition": False,
                       "items": [{"id": FB_ITEM["id"], "serial": "ABC123", "manufacturer": "Glock", "model": "19 Gen5", "caliber": "9mm", "type": "Pistol"}]}).encode()
    headers = {"X-FastBound-Signature": _sign("s3cret", body), "Content-Type": "application/json"}
    r = app_client.post("/webhooks/fastbound", content=body, headers=headers)
    assert r.status_code == 200 and r.json()["event"] == "disposition.committed"
    assert r.json()["result"]["items"][0]["clover"] == "zeroed"
    r2 = app_client.post("/webhooks/fastbound", content=body, headers=headers)
    assert r2.json()["status"] == "duplicate"


def test_clover_webhook_verification_and_orders(app_client, world):
    r = app_client.post("/webhooks/clover", json={"verificationCode": "VC-1"})
    assert r.json()["status"] == "verification_received"
    assert world.store.get("clover_verification_code") == "VC-1"
    cid = world.sync.push_firearm_to_clover(FB_ITEM)["clover_item_id"]
    world.fake_clover.add_order("ORDW", cid, 57999)
    payload = {"appId": "A", "merchants": {"MID": [{"objectId": "O:ORDW", "type": "UPDATE", "ts": 1}], "OTHER": [{"objectId": "O:ZZ", "type": "UPDATE", "ts": 1}]}}
    r = app_client.post("/webhooks/clover", json=payload)
    assert r.json()["results"][0]["action"] == "pending_disposition"
    # with CLOVER_WEBHOOK_AUTH set, the header is enforced
    world.settings.clover_webhook_auth = "authcode"
    assert app_client.post("/webhooks/clover", json=payload).status_code == 401
    assert app_client.post("/webhooks/clover", json=payload, headers={"X-Clover-Auth": "authcode"}).status_code == 200


def test_status_requires_key(app_client):
    assert app_client.get("/ffl/status").status_code == 401
    r = app_client.get("/ffl/status?key=mcpsecret")
    assert r.status_code == 200 and r.json()["fastbound_configured"] is True
    assert app_client.get("/health").json()["clover_configured"] is True


def test_mcp_is_mounted_and_lists_tools(app_client):
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    r = app_client.post("/mcp/mcpsecret/", json=init, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["serverInfo"]["name"] == "tacticool-ffl"
    r = app_client.post("/mcp/mcpsecret/", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert {"inventory", "find_firearm", "pending_sales", "sync_now", "reconcile", "receive_firearms", "deliver_firearm", "attention"} <= names
    assert app_client.post("/mcp/wrong/", json=init, headers=headers).status_code == 404


def test_mcp_tool_calls_run_against_the_fakes(app_client, world):
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

    def call(name, args=None):
        r = app_client.post("/mcp/mcpsecret/", headers=headers, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})
        assert r.status_code == 200, r.text
        res = r.json()["result"]
        assert not res.get("isError"), res
        return res.get("structuredContent") or json.loads(res["content"][0]["text"])

    assert call("inventory")["count"] == 1
    assert call("find_firearm", {"serial": "ABC123"})["matches"][0]["serial"] == "ABC123"
    assert call("deliver_firearm", {"disposition_id": "x"})["error"].startswith("Refused")
    pushed = call("push_inventory_to_clover")
    assert pushed["created"] == 1
    assert call("pending_sales")["count"] == 0
