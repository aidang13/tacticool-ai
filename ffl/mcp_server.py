"""MCP server so Claude can run the counter: inventory, receiving, pending 4473s,
sales sync, delivery and reconciliation across Clover + FastBound.

Run locally for Claude Desktop / Claude Code:   python -m ffl mcp
Or over HTTPS from the Railway app:             https://<app>/mcp/<FFL_MCP_SECRET>
"""
from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from .runtime import get_runtime

INSTRUCTIONS = """You operate the firearms counter for Tacti-Cool Gun.
FastBound is the bound book (A&D) and electronic 4473 of record. Clover is the register.
Guns are received in FastBound (then listed in Clover automatically), rung up in Clover
(which opens a pending disposition in FastBound for the 4473), and transferred in FastBound.
Never commit a disposition unless a human confirms the firearm is physically leaving right now.
Always surface anything in `attention` to the user — those are compliance items."""

mcp = MCPServer("tacticool-ffl", instructions=INSTRUCTIONS)


def _rt():
    return get_runtime()


def _fb_item_view(item: dict, rec: dict | None = None) -> dict:
    status = (item.get("status") or {}).get("name") if isinstance(item.get("status"), dict) else item.get("statusText")
    return {
        "fastbound_item_id": item.get("id"),
        "serial": item.get("serial"),
        "manufacturer": item.get("manufacturer"),
        "model": item.get("model"),
        "caliber": item.get("caliber"),
        "type": item.get("type"),
        "condition": item.get("condition"),
        "price": item.get("price"),
        "cost": item.get("cost"),
        "status": status,
        "disposed": item.get("disposed"),
        "pending_disposition_id": item.get("dispositionId"),
        "acquired": (item.get("acquire_Date") or "")[:10],
        "clover_item_id": (rec or {}).get("clover_item_id"),
        "sync_state": (rec or {}).get("state"),
    }


@mcp.tool()
def status() -> dict:
    """Health of the Clover + FastBound link: what is configured, last poll, open attention items."""
    rt = _rt()
    return {**rt.status(), "attention": rt.store.open_flags()}


@mcp.tool()
def inventory(search: str | None = None, limit: int = 100) -> dict:
    """Firearms currently on the FastBound book (not yet transferred), with their Clover link.
    `search` matches serial, manufacturer, model or caliber."""
    rt = _rt()
    items = rt.sync._need_fb().inventory(**({"search": search} if search else {}))
    out = [_fb_item_view(i, rt.store.firearm(i["id"])) for i in items[:limit]]
    return {"count": len(items), "showing": len(out), "items": out}


@mcp.tool()
def find_firearm(serial: str) -> dict:
    """Look a gun up by serial number across FastBound (book) and Clover (register)."""
    rt = _rt()
    fb_hits = rt.sync._need_fb().find_by_serial(serial)
    results = []
    for item in fb_hits:
        rec = rt.store.firearm(item["id"])
        view = _fb_item_view(item, rec)
        if rt.clover and rec and rec.get("clover_item_id"):
            try:
                ci = rt.clover.item(rec["clover_item_id"])
                view["clover"] = {"name": ci.get("name"), "price_cents": ci.get("price"), "qty": rt.clover.stock_of(ci), "hidden": ci.get("hidden")}
            except Exception as e:
                view["clover"] = {"error": str(e)}
        view["history"] = rec
        results.append(view)
    return {"serial": serial, "matches": results}


@mcp.tool()
def pending_sales() -> dict:
    """Guns sold or started on a 4473 but not yet transferred: FastBound pending dispositions / 4473s
    plus the Clover orders that opened them."""
    rt = _rt()
    fb = rt.sync._need_fb()
    pending = fb.pending_4473s()
    seen = {d["id"] for d in pending}
    for d in fb.dispositions(take=200):
        status = ((d.get("status") or {}).get("name") or "").lower()
        if "pending" in status and d["id"] not in seen:
            pending.append(d)
            seen.add(d["id"])
    rows = []
    for d in pending:
        buyer = " ".join(x for x in [d.get("contactFirstName"), d.get("contactLastName")] if x) or d.get("contactLicenseName") or d.get("contactOrganizationName")
        rows.append({
            "disposition_id": d["id"], "date": (d.get("date") or "")[:10], "type": d.get("type"), "is4473": d.get("is4473"),
            "status": (d.get("status") or {}).get("name"), "buyer": buyer, "items": d.get("itemCount"),
            "clover_order_id": d.get("invoiceNumber"), "external_id": d.get("externalId"),
        })
    return {"count": len(rows), "pending": rows, "tracked_locally": rt.store.firearms("pending_sale") + rt.store.firearms("4473_complete")}


@mcp.tool()
def recent_sales(limit: int = 25) -> dict:
    """Clover orders with firearms that the sync has processed, newest first."""
    rt = _rt()
    return {"orders": rt.store.orders(limit)}


@mcp.tool()
def sync_now() -> dict:
    """Pull new/changed Clover orders right now and open pending dispositions for any firearm sales."""
    rt = _rt()
    return rt.sync.poll_orders()


@mcp.tool()
def push_inventory_to_clover() -> dict:
    """List every firearm on the FastBound book in Clover (one item per serial, qty 1). Safe to re-run."""
    rt = _rt()
    return rt.sync.import_inventory()


@mcp.tool()
def reconcile(stale_days: int = 30) -> dict:
    """Compare FastBound and Clover and list every mismatch a human should look at."""
    rt = _rt()
    return rt.sync.reconcile(stale_days=stale_days)


@mcp.tool()
def find_contact(query: str) -> dict:
    """Find an existing FastBound contact (distributor, FFL, customer) by name, trade name or FFL number."""
    rt = _rt()
    fb = rt.sync._need_fb()
    q = query.strip()
    hits: list[dict] = []
    digits = q.replace("-", "")
    if digits.isdigit() and len(digits) >= 10:
        hits = fb.contacts(fflNumber=q)
    if not hits:
        hits = fb.contacts(tradeName=q) or fb.contacts(licenseName=q) or fb.contacts(organizationName=q)
    if not hits and " " in q:
        first, last = q.split(" ", 1)
        hits = fb.contacts(firstName=first, lastName=last)
    return {"query": q, "contacts": [{k: c.get(k) for k in ("id", "fflNumber", "licenseName", "tradeName", "organizationName", "firstName", "lastName", "premiseCity", "premiseState")} for c in hits[:20]]}


@mcp.tool()
def create_ffl_contact(ffl_number: str, ffl_expires: str, premise_address1: str, premise_city: str,
                       premise_state: str, premise_zip: str, license_name: str = "", trade_name: str = "",
                       email: str = "", phone: str = "") -> dict:
    """Create a licensee contact (distributor / other FFL) in FastBound. FastBound looks the FFL up
    in FFLeZ and fills in the licence details. Returns the existing contact if it already exists."""
    rt = _rt()
    fb = rt.sync._need_fb()
    payload = {
        "fflNumber": ffl_number, "fflExpires": ffl_expires, "lookupFFL": True,
        "licenseName": license_name or None, "tradeName": trade_name or None,
        "premiseAddress1": premise_address1, "premiseCity": premise_city, "premiseState": premise_state,
        "premiseZipCode": premise_zip, "premiseCountry": "US", "emailAddress": email or None, "phoneNumber": phone or None,
    }
    contact_id, body = fb.create_contact({k: v for k, v in payload.items() if v is not None})
    return {"contact_id": contact_id, "contact": body}


@mcp.tool()
def receive_firearms(contact_id: str, items: list[dict[str, Any]], acquisition_type: str = "Purchase",
                     po_number: str = "", invoice_number: str = "", tracking_number: str = "", note: str = "") -> dict:
    """Receive guns into the bound book and put them on the Clover register in one step.

    `items` entries need manufacturer, model, serial, caliber, type (Pistol / Revolver / Rifle / Shotgun /
    Frame/Receiver / Other Firearm ...) and may include importer, countryOfManufacture, condition, cost,
    price, mpn, upc, sku, barrelLength, totalLength. Match what is physically marked on the firearm.
    `acquisition_type` must be one of FastBound's AcquireType smart-list values (see `smart_list`)."""
    rt = _rt()
    return rt.sync.receive(contact_id, items, acquisition_type=acquisition_type, po=po_number, invoice=invoice_number, tracking=tracking_number, note=note)


@mcp.tool()
def smart_list(name: str) -> Any:
    """FastBound's valid values. name: AcquireType, DisposeType, ItemType, Caliber, Manufacturer, Condition, Location, Importer, CountryOfManufacture."""
    rt = _rt()
    return rt.sync._need_fb().smart_list(name)


@mcp.tool()
def clover_order(order_id: str) -> dict:
    """Fetch a Clover order and show which lines are serialized firearms."""
    rt = _rt()
    clover = rt.sync._need_clover()
    order = clover.order(order_id)
    return {
        "id": order.get("id"), "state": order.get("state"), "payment_state": order.get("paymentState"),
        "total_cents": order.get("total"), "created": order.get("createdTime"), "modified": order.get("modifiedTime"),
        "lines": [{"name": l.get("name"), "price_cents": l.get("price"), "item_id": (l.get("item") or {}).get("id"), "refunded": l.get("refunded")} for l in clover.line_items(order)],
        "firearms": rt.sync.firearm_lines(order),
        "sync_record": rt.store.order(order_id),
    }


@mcp.tool()
def deliver_firearm(disposition_id: str, confirm_physically_leaving: bool = False) -> dict:
    """COMMIT a pending disposition in FastBound because the customer is walking out with the gun now
    (4473 complete, NICS proceed, any waiting period over). This writes the bound book — only call it
    with confirm_physically_leaving=True after the person at the counter says so. Reports an ATF 3310.4
    multiple-sale flag if FastBound raises one."""
    if not confirm_physically_leaving:
        return {"error": "Refused: set confirm_physically_leaving=True only when the firearm is physically leaving now."}
    rt = _rt()
    return rt.sync.deliver(disposition_id)


@mcp.tool()
def attention(clear_kind: str | None = None, clear_ref: str | None = None) -> dict:
    """Open compliance / sync items a human must look at. Pass clear_kind + clear_ref to mark one handled."""
    rt = _rt()
    if clear_kind and clear_ref:
        rt.store.clear_flags(clear_kind, clear_ref)
    return {"attention": rt.store.open_flags()}


def run_stdio() -> None:
    mcp.run("stdio")
