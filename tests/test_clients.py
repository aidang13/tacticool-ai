import pytest

from ffl.clover import CloverError
from ffl.fastbound import FastBoundError
from tests.conftest import FB_ITEM, FakeResponse


def test_fastbound_basic_auth_and_audit_user(world):
    world.fb.account_info()
    call = world.session.calls[-1]
    assert call["auth"] == ("key", "key")
    assert "X-AuditUser" not in call["headers"]  # reads don't need it
    world.fb.create_pending_disposition({"type": "Sale", "externalId": "CLV-1"})
    call = world.session.calls[-1]
    assert call["headers"]["X-AuditUser"] == "aidan@tacticoolgun.com"
    assert call["json"]["date"]  # defaulted to today


def test_fastbound_errors_are_parsed(world):
    with pytest.raises(FastBoundError) as ei:
        world.fb.item("00000000-0000-4000-8000-000000000000")
    assert ei.value.status == 404
    assert "not found" in str(ei.value)


def test_fastbound_write_without_audit_user_is_refused():
    from ffl.fastbound import FastBound
    fb = FastBound("1", api_key="k", session=None)
    with pytest.raises(FastBoundError):
        fb.create_pending_disposition({"type": "Sale"})


def test_fastbound_commit_surfaces_multiple_sale(world):
    d = world.fb.create_pending_disposition({"type": "Sale", "externalId": "x"})
    second = {**FB_ITEM, "id": "22222222-2222-4222-8222-222222222222", "serial": "DEF456"}
    world.fake_fb.items[second["id"]] = second
    world.fb.add_disposition_items(d["id"], [{"id": FB_ITEM["id"], "price": 1}, {"id": second["id"], "price": 1}])
    res = world.fb.commit_disposition(d["id"])
    assert res["multiple_sale"] is True
    assert res["multiple_sale_url"].startswith("https://")
    assert len(res["items"]) == 2


def test_fastbound_find_by_serial_prefers_exact(world):
    assert world.fb.find_by_serial("abc123")[0]["id"] == FB_ITEM["id"]
    assert world.fb.find_by_serial("nope") == []


def test_fastbound_inventory_paginates_and_filters_disposed(world):
    for n in range(150):
        iid = f"{n:08x}-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        world.fake_fb.items[iid] = {**FB_ITEM, "id": iid, "serial": f"S{n}", "disposed": n % 2 == 0}
    inv = world.fb.inventory()
    assert len(inv) == 1 + 75
    assert all(not i["disposed"] for i in inv)


def test_clover_bearer_and_refresh_on_401(world):
    world.clover.merchant()
    assert world.session.calls[-1]["headers"]["Authorization"] == "Bearer tok"
    seen = {"n": 0}

    def flaky(m, p, j):
        seen["n"] += 1
        return (401, {"message": "expired"}) if seen["n"] == 1 else (200, {"id": "MID", "name": "ok"})

    world.session.routes.insert(0, ("GET", __import__("re").compile(r"/v3/merchants/MID/?$"), flaky))
    tokens = {}
    world.clover.on_tokens = tokens.update
    assert world.clover.merchant()["name"] == "ok"
    assert world.clover.access_token == "fresh"
    assert tokens["refresh_token"] == "r2"


def test_clover_error(world):
    with pytest.raises(CloverError) as ei:
        world.clover.item("missing")
    assert ei.value.status == 404


def test_clover_item_and_stock_roundtrip(world):
    it = world.clover.create_item("Glock 19", 59999, sku="FB:abc", code="ABC123")
    assert it["price"] == 59999 and it["sku"] == "FB:abc" and it["code"] == "ABC123"
    world.clover.set_stock(it["id"], 1)
    assert world.clover.stock_of(world.clover.item(it["id"])) == 1.0
    assert world.clover.find_item_by_sku("FB:abc")["id"] == it["id"]
    assert world.clover.find_item_by_sku("FB:zzz") is None
    cat = world.clover.ensure_category("Firearms")
    assert world.clover.ensure_category("firearms")["id"] == cat["id"]


def test_fake_response_json():
    assert FakeResponse(200, {"a": 1}).json() == {"a": 1}
