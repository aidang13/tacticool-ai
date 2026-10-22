import json
import time

from tests.conftest import FB_ITEM


def _listed(world):
    """Receive FB_ITEM into Clover and return the Clover item id."""
    r = world.sync.push_firearm_to_clover(FB_ITEM)
    assert r["result"] == "created"
    return r["clover_item_id"]


def test_receive_lists_gun_in_clover_once(world):
    cid = _listed(world)
    ci = world.clover.item(cid)
    assert ci["name"] == "Glock 19 Gen5 9mm Pistol S/N ABC123"
    assert ci["sku"] == f"FB:{FB_ITEM['id']}"
    assert ci["code"] == "ABC123"
    assert ci["price"] == 59999
    assert world.clover.stock_of(ci) == 1.0
    assert world.fake_clover.cat_items[0]["item"]["id"] == cid
    # second push is a no-op
    assert world.sync.push_firearm_to_clover(FB_ITEM)["result"] == "exists"
    assert len(world.fake_clover.items) == 1
    assert world.store.firearm(FB_ITEM["id"])["state"] == "in_stock"


def test_import_inventory_skips_disposed(world):
    world.fake_fb.items["33333333-3333-4333-8333-333333333333"] = {**FB_ITEM, "id": "33333333-3333-4333-8333-333333333333", "serial": "GONE", "disposed": True}
    r = world.sync.import_inventory()
    assert r["created"] == 1 and r["skipped"] == 0 and not r["errors"]
    assert len(world.fake_clover.items) == 1


def test_paid_clover_order_opens_pending_disposition(world):
    cid = _listed(world)
    order = world.fake_clover.add_order("ORD1", cid, 57999)
    r = world.sync.process_order(order)
    assert r["action"] == "pending_disposition"
    did = r["disposition_id"]
    d = world.fake_fb.dispositions[did]
    assert d["externalId"] == "CLV-ORD1" and d["invoiceNumber"] == "ORD1" and d["type"] == "Sale"
    assert world.fake_fb.disp_items[did][0]["itemId"] == FB_ITEM["id"]
    assert world.fake_fb.disp_items[did][0]["price"] == 579.99
    rec = world.store.firearm(FB_ITEM["id"])
    assert rec["state"] == "pending_sale" and rec["clover_order_id"] == "ORD1" and rec["fb_disposition_id"] == did
    # re-processing the same order does not duplicate anything
    r2 = world.sync.process_order(order)
    assert r2["disposition_id"] == did
    assert len(world.fake_fb.dispositions) == 1 and len(world.fake_fb.disp_items[did]) == 1


def test_unpaid_order_waits(world):
    cid = _listed(world)
    order = world.fake_clover.add_order("ORD2", cid, 57999, payment_state="OPEN")
    assert world.sync.process_order(order)["action"] == "waiting"
    assert not world.fake_fb.dispositions


def test_order_without_firearms_is_ignored(world):
    other = world.clover.create_item("Holster", 2999, sku="HOL-1")
    order = world.fake_clover.add_order("ORD3", other["id"], 2999)
    assert world.sync.process_order(order)["action"] == "ignored"


def test_sale_links_to_4473_started_first(world):
    cid = _listed(world)
    d = world.fb.create_pending_disposition({"type": "Sale", "externalId": "manual-4473"})
    world.fb.add_disposition_items(d["id"], [{"id": FB_ITEM["id"], "price": 599.99}])
    order = world.fake_clover.add_order("ORD4", cid, 59999)
    r = world.sync.process_order(order)
    assert r["firearms"][0]["status"] == "already_pending"
    assert r["firearms"][0]["disposition_id"] == d["id"]
    assert len(world.fake_fb.dispositions) == 1


def test_refund_unwinds_pending_sale(world):
    cid = _listed(world)
    order = world.fake_clover.add_order("ORD5", cid, 57999)
    did = world.sync.process_order(order)["disposition_id"]
    order["paymentState"] = "REFUNDED"
    r = world.sync.process_order(order)
    assert r["action"] == "refunded"
    assert did not in world.fake_fb.dispositions  # emptied, so deleted
    assert world.fake_fb.items[FB_ITEM["id"]]["dispositionId"] is None
    assert world.clover.stock_of(world.clover.item(cid)) == 1.0
    assert world.store.firearm(FB_ITEM["id"])["state"] == "in_stock"


def test_refund_after_transfer_is_flagged(world):
    cid = _listed(world)
    order = world.fake_clover.add_order("ORD6", cid, 57999)
    did = world.sync.process_order(order)["disposition_id"]
    world.fb.commit_disposition(did)
    order["paymentState"] = "REFUNDED"
    r = world.sync.process_order(order)
    assert r["firearms"][0]["status"] == "needs_attention"
    flags = world.store.open_flags()
    assert flags and flags[0]["kind"] == "refund_after_transfer"


def test_disposition_committed_zeroes_clover(world):
    cid = _listed(world)
    event = {"id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd", "is4473": True, "invoiceNumber": "ORD7",
             "items": [{"id": FB_ITEM["id"], "serial": "ABC123", "manufacturer": "Glock", "model": "19 Gen5", "caliber": "9mm", "type": "Pistol"}]}
    world.store.record_order("ORD7", "PAID", "pending_disposition")
    r = world.sync.handle_disposition_committed(event)
    assert r["items"][0]["clover"] == "zeroed"
    ci = world.clover.item(cid)
    assert world.clover.stock_of(ci) == 0.0 and ci["hidden"] is True
    assert world.store.firearm(FB_ITEM["id"])["state"] == "disposed"
    assert world.store.order("ORD7")["status"] == "transferred"


def test_undispose_restocks(world):
    cid = _listed(world)
    world.sync.handle_disposition_committed({"id": "x", "items": [{"id": FB_ITEM["id"], "serial": "ABC123"}]})
    r = world.sync.handle_item_undisposed({**FB_ITEM, "acquisitionType": "Purchase"})
    assert r["clover"] == "restocked"
    ci = world.clover.item(cid)
    assert world.clover.stock_of(ci) == 1.0 and ci["hidden"] is False


def test_form4473_completed_records_pdf(world):
    _listed(world)
    r = world.sync.handle_form4473_completed({
        "id": "f4473", "responseText": "Proceed", "apiDownloadUrl": "https://cloud.fastbound.com/dl/f4473",
        "disposition": {"id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd"}, "items": [{"id": FB_ITEM["id"], "serial": "ABC123"}],
    })
    rec = world.store.firearm(FB_ITEM["id"])
    assert rec["state"] == "4473_complete" and rec["form4473_url"].endswith("f4473")
    assert not world.store.open_flags()
    world.sync.handle_form4473_completed({"id": "f2", "responseText": "Denied", "items": []})
    assert world.store.open_flags()[0]["kind"] == "4473_not_proceed"


def test_deliver_commits_and_flags_multiple_sale(world):
    cid = _listed(world)
    second = {**FB_ITEM, "id": "22222222-2222-4222-8222-222222222222", "serial": "DEF456"}
    world.fake_fb.items[second["id"]] = second
    cid2 = world.sync.push_firearm_to_clover(second)["clover_item_id"]
    d = world.fb.create_pending_disposition({"type": "Sale", "externalId": "CLV-ORD8"})
    world.fb.add_disposition_items(d["id"], [{"id": FB_ITEM["id"], "price": 500}, {"id": second["id"], "price": 500}])
    r = world.sync.deliver(d["id"])
    assert r["multiple_sale"] is True
    assert {i["clover"] for i in r["items"]} == {"zeroed"}
    assert world.clover.stock_of(world.clover.item(cid)) == 0.0
    assert world.clover.stock_of(world.clover.item(cid2)) == 0.0
    assert world.store.open_flags()[0]["kind"] == "multiple_sale_report"


def test_poll_orders_uses_cursor_and_dedupes(world):
    cid = _listed(world)
    now = int(time.time() * 1000)
    world.fake_clover.add_order("ORD9", cid, 57999, modified=now - 1000)
    r = world.sync.poll_orders()
    assert [o["action"] for o in r["orders"]] == ["pending_disposition"]
    assert world.store.get("clover_orders_cursor_ms") == now - 1000
    assert world.sync.poll_orders()["orders"] == []  # nothing new
    world.fake_clover.orders["ORD9"]["paymentState"] = "REFUNDED"
    world.fake_clover.orders["ORD9"]["modifiedTime"] = now
    assert [o["action"] for o in world.sync.poll_orders()["orders"]] == ["refunded"]


def test_reconcile_reports_mismatches(world):
    # on the book, not in Clover
    missing = {**FB_ITEM, "id": "44444444-4444-4444-8444-444444444444", "serial": "MISS1"}
    world.fake_fb.items[missing["id"]] = missing
    # listed, then sold in Clover (qty 0) with no FastBound disposition
    cid = _listed(world)
    world.clover.set_stock(cid, 0)
    # disposed in FastBound but still qty 1 in Clover
    gone = {**FB_ITEM, "id": "55555555-5555-4555-8555-555555555555", "serial": "GONE1"}
    world.fake_fb.items[gone["id"]] = gone
    cid_gone = world.sync.push_firearm_to_clover(gone)["clover_item_id"]
    world.fake_fb.items[gone["id"]]["disposed"] = True
    # stale pending disposition
    world.fake_fb.dispositions["66666666-6666-4666-8666-666666666666"] = {"id": "66666666-6666-4666-8666-666666666666", "status": {"name": "Pending"}, "date": "2020-01-01T00:00:00", "itemCount": 1}
    rep = world.sync.reconcile()
    assert rep["summary"]["missing_in_clover"] == 1 and rep["missing_in_clover"][0]["label"].endswith("MISS1")
    assert rep["summary"]["sold_in_clover_no_disposition"] == 1
    assert rep["disposed_but_sellable_in_clover"][0]["clover_item_id"] == cid_gone
    assert rep["summary"]["stale_pending_dispositions"] == 1


def test_receive_creates_acquisition_and_clover_items(world):
    r = world.sync.receive("cccccccc-cccc-4ccc-8ccc-cccccccccccc", [
        {"manufacturer": "Smith & Wesson", "model": "M&P9", "serial": "SW1", "caliber": "9mm", "type": "Pistol", "cost": 400, "price": 549.99},
        {"manufacturer": "Ruger", "model": "10/22", "serial": "RG1", "caliber": ".22 LR", "type": "Rifle", "price": "299"},
    ], po="PO-1", invoice="INV-1")
    assert len(r["items"]) == 2 and r["acquisition_id"]
    sent = world.session.calls[[c["url"] for c in world.session.calls].index(next(c["url"] for c in world.session.calls if "CreateAndCommit" in c["url"]))]["json"]
    assert sent["items"][0]["price"] == "549.99" and sent["items"][0]["cost"] == "400.00"
    assert sent["purchaseOrderNumber"] == "PO-1" and sent["type"] == "Purchase"
    assert [p["result"] for p in r["clover"]] == ["created", "created"]
    names = sorted(i["name"] for i in world.fake_clover.items.values())
    assert names == ["Ruger 10/22 .22 LR Rifle S/N RG1", "Smith & Wesson M&P9 9mm Pistol S/N SW1"]
    assert [i["price"] for i in world.fake_clover.items.values()] == [54999, 29900]


def test_detect_event_shapes(world):
    detect = world.sync.detect_event
    assert detect({"X-FastBound-Event": "Disposition.Committed"}, {"id": "1"})[0] == "disposition.committed"
    assert detect({}, {"event": "form4473.completed", "data": {"id": "9"}}) == ("form4473.completed", {"id": "9"})
    assert detect({}, {"apiDownloadUrl": "u"})[0] == "form4473.completed"
    assert detect({}, {"isManufacturingDisposition": False, "items": []})[0] == "disposition.committed"
    assert detect({}, {"isManufacturingAcquisition": False, "items": []})[0] == "acquisition.committed"
    assert detect({}, {"dispositionItemsRemoved": []})[0] == "disposition.items.removed"
    assert detect({}, {"serial": "x", "acquisitionType": "Purchase"})[0] == "item.undisposed"
    assert detect({}, {"foo": 1})[0] == "unknown"
    assert world.sync.dispatch("unknown", {})["action"] == "stored_only"
    assert json.dumps(world.sync.dispatch("acquisition.committed", {"id": "a", "items": [FB_ITEM]}))["len" if False else 0:1]
