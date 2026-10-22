import json
import re
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ffl.clover import Clover  # noqa: E402
from ffl.config import Settings  # noqa: E402
from ffl.fastbound import FastBound  # noqa: E402
from ffl.store import Store  # noqa: E402
from ffl.sync import Sync  # noqa: E402


class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self.headers = {k: v for k, v in (headers or {}).items()}
        self.content = b"" if body is None else json.dumps(body).encode()
        self.text = self.content.decode()
        self.ok = status < 400

    def json(self):
        return json.loads(self.content)


class FakeSession:
    """Routes requests to handlers: (METHOD, regex) -> fn(match, params, json) -> (status, body[, headers])."""

    def __init__(self):
        self.routes = []
        self.calls = []

    def on(self, method, pattern, handler):
        self.routes.append((method.upper(), re.compile(pattern), handler))
        return self

    def request(self, method, url, params=None, json=None, headers=None, auth=None, timeout=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json, "headers": headers or {}, "auth": auth})
        for m, rx, fn in self.routes:
            match = rx.search(url)
            if m == method.upper() and match:
                out = fn(match, params or {}, json)
                if isinstance(out, tuple):
                    return FakeResponse(*out)
                return FakeResponse(200, out)
        raise AssertionError(f"no fake route for {method} {url}")


FB_ITEM = {
    "id": "11111111-1111-4111-8111-111111111111", "serial": "ABC123", "manufacturer": "Glock", "model": "19 Gen5",
    "caliber": "9mm", "type": "Pistol", "price": 599.99, "cost": 450.0, "disposed": False, "deleted": False,
    "dispositionId": None, "status": {"id": 1, "name": "In Inventory"}, "acquire_Date": "2026-10-01T00:00:00",
}


class FakeFastBound:
    """In-memory FastBound behind a FakeSession."""

    def __init__(self, session: FakeSession, items=None):
        self.items = {i["id"]: dict(i) for i in (items or [FB_ITEM])}
        self.dispositions = {}
        self.disp_items = {}
        self.next_id = 100
        s = session
        s.on("GET", r"/api/Account$", lambda m, p, j: {"name": "Tacti-Cool Gun"})
        s.on("GET", r"/api/SmartLists/(\w+)$", lambda m, p, j: ["Purchase", "Sale"] if "Type" in m.group(1) else [])
        s.on("GET", r"/api/Items$", self.list_items)
        s.on("GET", r"/api/Items/([0-9a-f-]{36})$", lambda m, p, j: (200, self.items[m.group(1)]) if m.group(1) in self.items else (404, {"errors": [{"field": "id", "message": "not found"}]}))
        s.on("GET", r"/api/Dispositions/GetByExternalId/([^/?]+)$", self.get_by_ext)
        s.on("GET", r"/api/Dispositions/Only4473s$", lambda m, p, j: {"dispositions": [d for d in self.dispositions.values() if d.get("is4473")], "records": 0})
        s.on("GET", r"/api/Dispositions$", lambda m, p, j: {"dispositions": list(self.dispositions.values()), "records": len(self.dispositions)})
        s.on("GET", r"/api/Dispositions/([0-9a-f-]{36})/Items$", lambda m, p, j: {"items": self.disp_items.get(m.group(1), [])})
        s.on("POST", r"/api/Dispositions$", self.create_disp)
        s.on("POST", r"/api/Dispositions/([0-9a-f-]{36})/Items$", self.add_items)
        s.on("DELETE", r"/api/Dispositions/([0-9a-f-]{36})/Items/Remove/([0-9a-f-]{36})$", self.remove_item)
        s.on("DELETE", r"/api/Dispositions/([0-9a-f-]{36})$", self.delete_disp)
        s.on("POST", r"/api/Dispositions/([0-9a-f-]{36})/Commit$", self.commit)
        s.on("POST", r"/api/Acquisitions/CreateAndCommit$", self.create_acq)
        s.on("POST", r"/api/Contacts$", lambda m, p, j: (201, {"id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc", **j}))
        s.on("GET", r"/api/Webhooks/Events$", lambda m, p, j: ["acquisition.committed", "disposition.committed"])
        s.on("GET", r"/api/Webhooks/(\S+)$", lambda m, p, j: (404, {"errors": []}))
        s.on("POST", r"/api/Webhooks$", lambda m, p, j: (201, {"signingSecret": "deadbeef" * 8, **j}))

    def _gid(self):
        self.next_id += 1
        return f"{self.next_id:08x}-0000-4000-8000-000000000000"

    def list_items(self, m, p, j):
        rows = list(self.items.values())
        if p.get("serial"):
            rows = [r for r in rows if r["serial"].upper() == p["serial"].upper()]
        skip, take = int(p.get("skip", 0)), int(p.get("take", 100))
        return {"items": rows[skip:skip + take], "records": len(rows)}

    def get_by_ext(self, m, p, j):
        for d in self.dispositions.values():
            if d.get("externalId") == m.group(1):
                return d
        return 404, {"errors": [{"field": "externalId", "message": "not found"}]}

    def create_disp(self, m, p, j):
        if any(d.get("externalId") == j.get("externalId") for d in self.dispositions.values()):
            return 409, {"errors": [{"field": "externalId", "message": "duplicate"}]}
        did = self._gid()
        self.dispositions[did] = {"id": did, "status": {"id": 1, "name": "Pending"}, "date": j.get("date"), "itemCount": 0, **j}
        return 201, self.dispositions[did]

    def add_items(self, m, p, j):
        did = m.group(1)
        for it in j["items"]:
            self.disp_items.setdefault(did, []).append({"id": self._gid(), "itemId": it["id"], "price": it.get("price")})
            self.items[it["id"]]["dispositionId"] = did
        self.dispositions[did]["itemCount"] = len(self.disp_items[did])
        return 200, {}

    def remove_item(self, m, p, j):
        did, iid = m.group(1), m.group(2)
        self.disp_items[did] = [x for x in self.disp_items.get(did, []) if x["itemId"] != iid]
        self.items[iid]["dispositionId"] = None
        return 200, None

    def delete_disp(self, m, p, j):
        self.dispositions.pop(m.group(1), None)
        return 200, None

    def commit(self, m, p, j):
        did = m.group(1)
        items = []
        for di in self.disp_items.get(did, []):
            self.items[di["itemId"]]["disposed"] = True
            items.append({"itemId": di["itemId"], **{k: self.items[di["itemId"]][k] for k in ("serial", "manufacturer", "model", "caliber", "type")}})
        self.dispositions[did]["status"] = {"id": 2, "name": "Committed"}
        headers = {"X-FastBound-MultipleSale": "true", "X-FastBound-MultipleSaleUrl": "https://cloud.fastbound.com/msr/1"} if len(items) > 1 else {}
        return 200, {"dispositionId": did, "items": items}, headers

    def create_acq(self, m, p, j):
        out = []
        for it in j["items"]:
            iid = self._gid()
            self.items[iid] = {**it, "id": iid, "disposed": False, "deleted": False, "dispositionId": None, "price": float(it.get("price") or 0)}
            out.append({"id": iid, **{k: it.get(k) for k in ("serial", "manufacturer", "model", "caliber", "type", "sku")}})
        return 201, {"id": self._gid(), "items": out, **{k: v for k, v in j.items() if k != "items"}}


class FakeClover:
    def __init__(self, session: FakeSession):
        self.items = {}
        self.stock = {}
        self.categories = {}
        self.cat_items = []
        self.orders = {}
        self.n = 0
        s = session
        s.on("GET", r"/v3/merchants/MID/?$", lambda m, p, j: {"id": "MID", "name": "Tacti-Cool Gun"})
        s.on("GET", r"/v3/merchants/MID/items$", self.list_items)
        s.on("GET", r"/v3/merchants/MID/items/(\w+)$", lambda m, p, j: (200, self._item(m.group(1))) if m.group(1) in self.items else (404, {"message": "no"}))
        s.on("POST", r"/v3/merchants/MID/items$", self.create_item)
        s.on("POST", r"/v3/merchants/MID/items/(\w+)$", self.update_item)
        s.on("POST", r"/v3/merchants/MID/item_stocks/(\w+)$", self.set_stock)
        s.on("GET", r"/v3/merchants/MID/categories$", lambda m, p, j: {"elements": list(self.categories.values())})
        s.on("POST", r"/v3/merchants/MID/categories$", self.create_cat)
        s.on("POST", r"/v3/merchants/MID/category_items$", lambda m, p, j: self.cat_items.extend(j["elements"]) or {})
        s.on("GET", r"/v3/merchants/MID/orders/(\w+)$", lambda m, p, j: self.orders[m.group(1)])
        s.on("GET", r"/v3/merchants/MID/orders$", self.list_orders)
        s.on("POST", r"/oauth/v2/refresh$", lambda m, p, j: {"access_token": "fresh", "refresh_token": "r2", "access_token_expiration": 9999999999})

    def _id(self):
        self.n += 1
        return f"CLV{self.n:04d}"

    def _item(self, iid):
        it = dict(self.items[iid])
        if iid in self.stock:
            it["itemStock"] = {"quantity": self.stock[iid]}
        return it

    def list_items(self, m, p, j):
        rows = [self._item(i) for i in self.items]
        f = p.get("filter", "")
        if f.startswith("sku="):
            rows = [r for r in rows if r.get("sku") == f[4:]]
        off, lim = int(p.get("offset", 0)), int(p.get("limit", 100))
        return {"elements": rows[off:off + lim]}

    def create_item(self, m, p, j):
        iid = self._id()
        self.items[iid] = {"id": iid, **j}
        return self.items[iid]

    def update_item(self, m, p, j):
        self.items[m.group(1)].update(j)
        return self._item(m.group(1))

    def set_stock(self, m, p, j):
        self.stock[m.group(1)] = j["quantity"]
        return {"item": {"id": m.group(1)}, "quantity": j["quantity"]}

    def create_cat(self, m, p, j):
        cid = self._id()
        self.categories[cid] = {"id": cid, "name": j["name"]}
        return self.categories[cid]

    def list_orders(self, m, p, j):
        f = p.get("filter", "")
        since = int(f.split(">=")[1]) if ">=" in f else 0
        rows = sorted((o for o in self.orders.values() if int(o.get("modifiedTime", 0)) >= since), key=lambda o: o["modifiedTime"])
        off, lim = int(p.get("offset", 0)), int(p.get("limit", 100))
        return {"elements": rows[off:off + lim]}

    def add_order(self, order_id, item_id, price_cents, payment_state="PAID", modified=1_700_000_000_000, refunded=False):
        self.orders[order_id] = {
            "id": order_id, "state": "locked", "paymentState": payment_state, "total": price_cents,
            "modifiedTime": modified, "createdTime": modified,
            "lineItems": {"elements": [{"id": f"L{order_id}", "name": "gun", "price": price_cents, "item": {"id": item_id}, "refunded": refunded}]},
        }
        return self.orders[order_id]


@pytest.fixture
def world(tmp_path):
    session = FakeSession()
    fake_fb = FakeFastBound(session)
    fake_clover = FakeClover(session)
    settings = Settings(
        fastbound_account="12345", fastbound_api_key="key", fastbound_audit_user="aidan@tacticoolgun.com",
        clover_merchant_id="MID", clover_access_token="tok", db_path=str(tmp_path / "t.sqlite3"),
        fastbound_webhook_secret="s3cret", mcp_secret="mcpsecret", poll_seconds=0,
    )
    fb = FastBound("12345", api_key="key", audit_user="aidan@tacticoolgun.com", session=session)
    clover = Clover("MID", access_token="tok", app_id="app", refresh_token="r1", session=session)
    store = Store(settings.db_path)
    sync = Sync(settings, fb, clover, store)

    class W:
        pass

    w = W()
    w.session, w.fake_fb, w.fake_clover, w.settings, w.fb, w.clover, w.store, w.sync = session, fake_fb, fake_clover, settings, fb, clover, store, sync
    return w
