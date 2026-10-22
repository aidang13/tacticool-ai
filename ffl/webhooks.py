"""HTTP endpoints: FastBound webhooks, Clover webhooks, Clover OAuth callback, status."""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi import APIRouter, HTTPException, Query, Request

from .runtime import get_runtime
from .sync import event_key

router = APIRouter()
SIGNATURE_TOLERANCE = 300


def verify_fastbound_signature(secret: str, raw: bytes, header: str, now: float | None = None) -> bool:
    """X-FastBound-Signature: t=<unix>,v1=<hex hmac-sha256 over "<t>.<raw body>">"""
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        t, v1 = parts["t"], parts["v1"]
    except Exception:
        return False
    if abs((now or time.time()) - int(t)) > SIGNATURE_TOLERANCE:
        return False
    expected = hmac.new(secret.encode(), t.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


@router.post("/webhooks/fastbound")
async def fastbound_webhook(request: Request):
    rt = get_runtime()
    raw = await request.body()
    secret = rt.settings.fastbound_webhook_secret
    if secret:
        if not verify_fastbound_signature(secret, raw, request.headers.get("X-FastBound-Signature", "")):
            raise HTTPException(401, "bad signature")
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "invalid json")
    name, payload = rt.sync.detect_event(dict(request.headers), body)
    key = event_key("fastbound", name, raw, payload)
    if not rt.store.record_event("fastbound", key, name, body):
        return {"status": "duplicate", "event": name}
    try:
        result = rt.sync.dispatch(name, payload)
        rt.store.update_event_result(key, json.dumps(result))
    except Exception as e:  # always 200 — FastBound retries 23 times on non-2xx and then disables the hook
        rt.store.update_event_result(key, f"error: {e}")
        rt.store.flag("webhook_error", key, f"FastBound event {name} failed: {e}")
        return {"status": "error", "event": name, "error": str(e)}
    return {"status": "ok", "event": name, "result": result}


@router.post("/webhooks/clover")
async def clover_webhook(request: Request):
    rt = get_runtime()
    raw = await request.body()
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "invalid json")
    if "verificationCode" in body:
        rt.store.set("clover_verification_code", body["verificationCode"])
        print(f"[clover] webhook verification code: {body['verificationCode']}")
        return {"status": "verification_received"}
    expected = rt.settings.clover_webhook_auth
    if expected and not hmac.compare_digest(expected, request.headers.get("X-Clover-Auth", "")):
        raise HTTPException(401, "bad X-Clover-Auth")
    results = []
    merchants = body.get("merchants") or {}
    for merchant_id, events in merchants.items():
        if merchant_id != rt.settings.clover_merchant_id:
            continue
        for ev in events or []:
            object_id = ev.get("objectId") or ""
            if not object_id.startswith("O:"):
                continue
            order_id = object_id[2:]
            key = f"clover:webhook:{order_id}:{ev.get('ts')}:{ev.get('type')}"
            if not rt.store.record_event("clover", key, "order", ev):
                continue
            try:
                order = rt.clover.order(order_id)
                r = rt.sync.process_order(order)
            except Exception as e:
                r = {"order_id": order_id, "action": "error", "error": str(e)}
                rt.store.flag("order_sync_error", order_id, f"Clover order {order_id} failed to sync: {e}")
            rt.store.update_event_result(key, json.dumps(r)[:2000])
            results.append(r)
    return {"status": "ok", "results": results}


def _require_key(rt, key: str | None):
    if not rt.settings.mcp_secret or key != rt.settings.mcp_secret:
        raise HTTPException(401, "missing or wrong key (FFL_MCP_SECRET)")


@router.get("/ffl/status")
async def ffl_status(key: str | None = Query(default=None)):
    rt = get_runtime()
    _require_key(rt, key)
    return {**rt.status(), "flags": rt.store.open_flags(), "recent_orders": rt.store.orders(20),
            "clover_verification_code": rt.store.get("clover_verification_code")}


@router.post("/ffl/poll")
async def ffl_poll(key: str | None = Query(default=None)):
    rt = get_runtime()
    _require_key(rt, key)
    return rt.sync.poll_orders()


@router.get("/ffl/clover/oauth/callback")
async def clover_oauth_callback(code: str | None = None, merchant_id: str | None = None, key: str | None = None):
    """Redirect target for the Clover OAuth v2 flow. Exchanges the code and stores the tokens."""
    rt = get_runtime()
    if not code:
        raise HTTPException(400, "missing code")
    if merchant_id and rt.settings.clover_merchant_id and merchant_id != rt.settings.clover_merchant_id:
        raise HTTPException(400, f"authorized merchant {merchant_id} does not match CLOVER_MERCHANT_ID")
    if rt.clover is None:
        from .clover import Clover
        rt.clover = Clover(rt.settings.clover_merchant_id or merchant_id or "", access_token="pending",
                           base=rt.settings.clover_base, app_id=rt.settings.clover_app_id,
                           app_secret=rt.settings.clover_app_secret,
                           on_tokens=lambda t: rt.store.set("clover_tokens", t))
        rt.sync.clover = rt.clover
    tokens = rt.clover.exchange_code(code)
    rt.store.set("clover_tokens", tokens)
    return {"status": "connected", "merchant_id": merchant_id or rt.settings.clover_merchant_id,
            "access_token_expiration": tokens.get("access_token_expiration"),
            "note": "Tokens saved to the sync database. Restart not required."}
