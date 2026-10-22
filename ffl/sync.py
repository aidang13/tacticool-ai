"""The workflows that make Clover + FastBound behave like one system.

Receive  : FastBound acquisition committed  →  Clover item created (qty 1, SKU FB:<id>, barcode = serial)
Sell     : Clover order paid with a firearm  →  FastBound pending disposition (ready for the e4473)
4473     : FastBound form4473.completed      →  recorded against the firearm
Transfer : FastBound disposition committed   →  Clover item zeroed / hidden
Refund   : Clover order refunded             →  pending disposition unwound, Clover qty restored
Reconcile: both sides compared, differences listed for a human

Rule that is never broken here: a disposition is only COMMITTED when a person
confirms the firearm physically left (FastBound UI, or the `deliver` tool).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

from .clover import Clover, CloverError
from .config import Settings
from .fastbound import FastBound, FastBoundError, describe_item
from .store import Store

PAID_STATES = {"PAID"}
REFUNDED_STATES = {"REFUNDED", "CREDITED"}


def _cents(value: Any) -> int:
    try:
        return int(round(float(value or 0) * 100))
    except (TypeError, ValueError):
        return 0


def _today() -> str:
    return dt.date.today().isoformat()


class Sync:
    def __init__(self, settings: Settings, fb: FastBound | None, clover: Clover | None, store: Store):
        self.settings = settings
        self.fb = fb
        self.clover = clover
        self.store = store

    # ── helpers ───────────────────────────────────────────────────────────
    def _need_fb(self) -> FastBound:
        if not self.fb:
            raise RuntimeError("FastBound is not configured (FASTBOUND_ACCOUNT / FASTBOUND_API_KEY)")
        return self.fb

    def _need_clover(self) -> Clover:
        if not self.clover:
            raise RuntimeError("Clover is not configured (CLOVER_MERCHANT_ID / CLOVER_ACCESS_TOKEN)")
        return self.clover

    def sku_for(self, fb_item_id: str) -> str:
        return f"{self.settings.sku_prefix}{fb_item_id}"

    def fb_id_from_sku(self, sku: str | None) -> str | None:
        if sku and sku.startswith(self.settings.sku_prefix):
            return sku[len(self.settings.sku_prefix):]
        return None

    def item_label(self, item: dict) -> str:
        return describe_item(item)

    # ══════════════════════════════════════════════════════════════════════
    # RECEIVE: FastBound → Clover
    # ══════════════════════════════════════════════════════════════════════
    def push_firearm_to_clover(self, item: dict) -> dict:
        """Create (or confirm) the Clover sellable item for one FastBound firearm."""
        clover = self._need_clover()
        fb_id = item["id"]
        sku = self.sku_for(fb_id)
        label = self.item_label(item)
        price_cents = _cents(item.get("price"))

        if item.get("disposed") or item.get("deleted"):
            return {"fb_item_id": fb_id, "result": "skipped", "reason": "not in inventory", "label": label}

        known = self.store.firearm(fb_id)
        existing = None
        if known and known.get("clover_item_id"):
            try:
                existing = clover.item(known["clover_item_id"])
            except CloverError as e:
                if e.status != 404:
                    raise
        if existing is None:
            existing = clover.find_item_by_sku(sku)

        if existing:
            self.store.upsert_firearm(
                fb_id, serial=item.get("serial"), label=label, clover_item_id=existing["id"], clover_sku=sku,
                price=price_cents / 100, state=known["state"] if known and known.get("state") else "in_stock",
            )
            return {"fb_item_id": fb_id, "result": "exists", "clover_item_id": existing["id"], "label": label}

        created = clover.create_item(name=label, price_cents=price_cents, sku=sku, code=(item.get("serial") or "")[:64])
        clover.set_stock(created["id"], 1)
        if self.settings.clover_firearms_category:
            cat = clover.ensure_category(self.settings.clover_firearms_category)
            clover.add_item_to_category(created["id"], cat["id"])
        self.store.upsert_firearm(
            fb_id, serial=item.get("serial"), label=label, clover_item_id=created["id"], clover_sku=sku,
            price=price_cents / 100, state="in_stock",
        )
        return {"fb_item_id": fb_id, "result": "created", "clover_item_id": created["id"], "label": label}

    def import_inventory(self) -> dict:
        """Push every firearm currently on the FastBound book into Clover (idempotent)."""
        fb = self._need_fb()
        results = {"created": 0, "exists": 0, "skipped": 0, "errors": [], "items": []}
        for item in fb.inventory():
            try:
                r = self.push_firearm_to_clover(item)
                results[r["result"]] += 1
                results["items"].append(r)
            except Exception as e:  # keep going; report at the end
                results["errors"].append({"fb_item_id": item.get("id"), "serial": item.get("serial"), "error": str(e)})
        return results

    def handle_acquisition_committed(self, event: dict) -> dict:
        out = []
        for item in event.get("items") or []:
            full = dict(item)
            full.setdefault("disposed", False)
            full.setdefault("deleted", False)
            out.append(self.push_firearm_to_clover(full))
        return {"acquisition_id": event.get("id"), "items": out}

    # ══════════════════════════════════════════════════════════════════════
    # SELL: Clover → FastBound pending disposition
    # ══════════════════════════════════════════════════════════════════════
    def _firearm_for_line(self, line: dict) -> dict | None:
        """Resolve a Clover line item to {fb_item_id, clover_item_id, price_cents} or None."""
        item_ref = line.get("item") or {}
        clover_item_id = item_ref.get("id")
        if not clover_item_id:
            return None
        rec = self.store.firearm_by_clover_item(clover_item_id)
        fb_id = rec["fb_item_id"] if rec else None
        if not fb_id:
            try:
                clover_item = self._need_clover().item(clover_item_id, expand="")
            except CloverError:
                return None
            fb_id = self.fb_id_from_sku(clover_item.get("sku"))
            if not fb_id:
                return None
        return {"fb_item_id": fb_id, "clover_item_id": clover_item_id, "price_cents": int(line.get("price") or 0),
                "line_id": line.get("id"), "refunded": bool(line.get("refunded"))}

    def firearm_lines(self, order: dict) -> list[dict]:
        lines = []
        for line in self._need_clover().line_items(order):
            f = self._firearm_for_line(line)
            if f:
                lines.append(f)
        return lines

    def process_order(self, order: dict) -> dict:
        """Idempotent. Call on every Clover order change (poll or webhook)."""
        order_id = order["id"]
        payment_state = order.get("paymentState")
        lines = self.firearm_lines(order)
        if not lines:
            return {"order_id": order_id, "action": "ignored", "reason": "no serialized firearms on order"}

        all_refunded = lines and all(l["refunded"] for l in lines)
        if payment_state in REFUNDED_STATES or all_refunded:
            return self._unwind_sale(order, lines)
        if payment_state not in PAID_STATES:
            self.store.record_order(order_id, payment_state, "waiting", "order not fully paid yet")
            return {"order_id": order_id, "action": "waiting", "payment_state": payment_state}
        return self._ensure_pending_disposition(order, [l for l in lines if not l["refunded"]])

    def _ensure_pending_disposition(self, order: dict, lines: list[dict]) -> dict:
        fb = self._need_fb()
        order_id = order["id"]
        external_id = f"CLV-{order_id}"
        linked: list[dict] = []
        to_add: list[dict] = []

        for l in lines:
            try:
                item = fb.item(l["fb_item_id"])
            except FastBoundError as e:
                self.store.flag("missing_fb_item", l["fb_item_id"], f"Clover order {order_id} sold a firearm whose FastBound record is gone ({e})")
                continue
            label = self.item_label(item)
            if item.get("disposed"):
                # Transferred in FastBound before (or without) being rung up — nothing to create.
                self.store.upsert_firearm(item["id"], serial=item.get("serial"), label=label, clover_item_id=l["clover_item_id"],
                                          state="disposed", clover_order_id=order_id, fb_disposition_id=item.get("dispositionId"))
                linked.append({"fb_item_id": item["id"], "label": label, "status": "already_disposed", "disposition_id": item.get("dispositionId")})
            elif item.get("dispositionId"):
                # A 4473 / pending disposition already holds this gun (started in FastBound first). Link, don't duplicate.
                self.store.upsert_firearm(item["id"], serial=item.get("serial"), label=label, clover_item_id=l["clover_item_id"],
                                          state="pending_sale", clover_order_id=order_id, fb_disposition_id=item["dispositionId"])
                linked.append({"fb_item_id": item["id"], "label": label, "status": "already_pending", "disposition_id": item["dispositionId"]})
            else:
                to_add.append({"item": item, "label": label, "line": l})

        disposition_id = None
        if to_add:
            existing = fb.disposition_by_external_id(external_id)
            if existing:
                disposition_id = existing["id"]
                already = {i.get("itemId") or i.get("id") for i in fb.disposition_items(disposition_id)}
                to_add = [t for t in to_add if t["item"]["id"] not in already]
            else:
                try:
                    created = fb.create_pending_disposition({
                        "externalId": external_id,
                        "type": self.settings.fastbound_sale_type,
                        "invoiceNumber": order_id,
                        "note": f"Clover order {order_id} paid {_today()} — created by tacticool-ai sync. Start the 4473 from this pending disposition; commit only at handoff.",
                    })
                except FastBoundError as e:
                    if e.status == 409:  # raced with ourselves; reuse
                        created = fb.disposition_by_external_id(external_id) or {}
                    else:
                        raise
                disposition_id = created["id"]
            if to_add:
                fb.add_disposition_items(disposition_id, [{"id": t["item"]["id"], "price": t["line"]["price_cents"] / 100} for t in to_add])
            for t in to_add:
                self.store.upsert_firearm(t["item"]["id"], serial=t["item"].get("serial"), label=t["label"], clover_item_id=t["line"]["clover_item_id"],
                                          price=t["line"]["price_cents"] / 100, state="pending_sale", clover_order_id=order_id, fb_disposition_id=disposition_id)
                linked.append({"fb_item_id": t["item"]["id"], "label": t["label"], "status": "added_to_pending_disposition", "disposition_id": disposition_id})

        if not disposition_id:
            disposition_id = next((x["disposition_id"] for x in linked if x.get("disposition_id")), None)
        self.store.record_order(order_id, order.get("paymentState"), "pending_disposition", json.dumps([x["status"] for x in linked]), disposition_id)
        return {"order_id": order_id, "action": "pending_disposition", "disposition_id": disposition_id, "firearms": linked}

    def _unwind_sale(self, order: dict, lines: list[dict]) -> dict:
        fb = self._need_fb()
        clover = self._need_clover()
        order_id = order["id"]
        out = []
        for l in lines:
            rec = self.store.firearm(l["fb_item_id"]) or {}
            try:
                item = fb.item(l["fb_item_id"])
            except FastBoundError:
                continue
            label = self.item_label(item)
            if item.get("disposed"):
                self.store.flag("refund_after_transfer", item["id"],
                                f"Clover order {order_id} was refunded but {label} is already transferred in FastBound. "
                                f"If the gun came back, acquire it from the customer in FastBound (or undispose if the transfer never happened).")
                out.append({"fb_item_id": item["id"], "label": label, "status": "needs_attention"})
                continue
            disp_id = item.get("dispositionId") or rec.get("fb_disposition_id")
            if disp_id:
                try:
                    fb.remove_disposition_item(disp_id, item["id"])
                    remaining = fb.disposition_items(disp_id)
                    if not remaining:
                        fb.delete_pending_disposition(disp_id)
                except FastBoundError as e:
                    self.store.flag("refund_unwind_failed", item["id"], f"Could not remove {label} from pending disposition {disp_id}: {e}")
            try:
                clover.set_stock(l["clover_item_id"], 1)
                clover.update_item(l["clover_item_id"], hidden=False, available=True)
            except CloverError as e:
                self.store.flag("clover_restock_failed", l["clover_item_id"], f"Could not restore Clover stock for {label}: {e}")
            self.store.upsert_firearm(item["id"], serial=item.get("serial"), label=label, state="in_stock", clover_order_id=None, fb_disposition_id=None)
            out.append({"fb_item_id": item["id"], "label": label, "status": "back_in_stock"})
        self.store.record_order(order_id, order.get("paymentState"), "refunded", json.dumps([x["status"] for x in out]))
        return {"order_id": order_id, "action": "refunded", "firearms": out}

    def poll_orders(self, lookback_ms: int = 90_000) -> dict:
        """Pull Clover orders modified since the last cursor and process each one."""
        clover = self._need_clover()
        now = clover.now_ms()
        cursor = self.store.get("clover_orders_cursor_ms")
        if cursor is None:
            cursor = now - 24 * 3600 * 1000
        since = max(0, int(cursor) - lookback_ms)
        results = []
        newest = cursor
        for order in clover.orders_modified_since(since):
            modified = int(order.get("modifiedTime") or 0)
            newest = max(newest, modified)
            key = f"clover:order:{order['id']}:{order.get('paymentState')}:{modified}"
            if self.store.seen_event(key):
                continue
            self.store.record_event("clover", key, "order", {"id": order["id"], "paymentState": order.get("paymentState")})
            try:
                r = self.process_order(order)
            except Exception as e:
                r = {"order_id": order["id"], "action": "error", "error": str(e)}
                self.store.flag("order_sync_error", order["id"], f"Clover order {order['id']} failed to sync: {e}")
            self.store.update_event_result(key, json.dumps(r)[:2000])
            if r.get("action") != "ignored":
                results.append(r)
        self.store.set("clover_orders_cursor_ms", newest)
        self.store.set("last_poll_at", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        return {"polled_since_ms": since, "orders": results}

    # ══════════════════════════════════════════════════════════════════════
    # TRANSFER / 4473 / UNDO: FastBound → Clover
    # ══════════════════════════════════════════════════════════════════════
    def _zero_in_clover(self, fb_item_id: str, label: str) -> str:
        clover = self._need_clover()
        rec = self.store.firearm(fb_item_id)
        clover_item_id = rec.get("clover_item_id") if rec else None
        if not clover_item_id:
            found = clover.find_item_by_sku(self.sku_for(fb_item_id))
            clover_item_id = found["id"] if found else None
        if not clover_item_id:
            return "no_clover_item"
        clover.set_stock(clover_item_id, 0)
        if self.settings.hide_sold_items:
            clover.update_item(clover_item_id, hidden=True, available=False)
        return "zeroed"

    def handle_disposition_committed(self, event: dict) -> dict:
        out = []
        for item in event.get("items") or []:
            label = self.item_label(item)
            status = self._zero_in_clover(item["id"], label) if self.clover else "clover_not_configured"
            self.store.upsert_firearm(item["id"], serial=item.get("serial"), label=label, state="disposed", fb_disposition_id=event.get("id"))
            self.store.clear_flags("stale_pending", item["id"])
            out.append({"fb_item_id": item["id"], "label": label, "clover": status})
        inv = event.get("invoiceNumber")
        if inv and self.store.order(inv):
            self.store.record_order(inv, None, "transferred", "disposition committed", event.get("id"))
        return {"disposition_id": event.get("id"), "is4473": event.get("is4473"), "items": out}

    def handle_form4473_completed(self, event: dict) -> dict:
        disp = event.get("disposition") or {}
        out = []
        for item in event.get("items") or []:
            label = self.item_label(item)
            self.store.upsert_firearm(item["id"], serial=item.get("serial"), label=label, state="4473_complete",
                                      fb_disposition_id=disp.get("id"), form4473_id=event.get("id"), form4473_url=event.get("apiDownloadUrl"))
            out.append({"fb_item_id": item["id"], "label": label})
        response = (event.get("responseText") or "").lower()
        if "denied" in response or "cancel" in response:
            self.store.flag("4473_not_proceed", event.get("id") or "", f"4473 {event.get('id')} ended with '{event.get('responseText')}'. Unwind the Clover sale / refund if needed.")
        return {"form4473_id": event.get("id"), "response": event.get("responseText"), "disposition_id": disp.get("id"), "items": out}

    def handle_item_undisposed(self, event: dict) -> dict:
        label = self.item_label(event)
        clover = self.clover
        status = "clover_not_configured"
        if clover:
            rec = self.store.firearm(event["id"])
            clover_item_id = rec.get("clover_item_id") if rec else None
            if not clover_item_id:
                found = clover.find_item_by_sku(self.sku_for(event["id"]))
                clover_item_id = found["id"] if found else None
            if clover_item_id:
                clover.set_stock(clover_item_id, 1)
                clover.update_item(clover_item_id, hidden=False, available=True)
                status = "restocked"
            else:
                status = "no_clover_item"
                self.push_firearm_to_clover({**event, "disposed": False, "deleted": False})
                status = "created"
        self.store.upsert_firearm(event["id"], serial=event.get("serial"), label=label, state="in_stock", fb_disposition_id=None, clover_order_id=None)
        return {"fb_item_id": event["id"], "label": label, "clover": status}

    def handle_disposition_items_removed(self, event: dict) -> dict:
        """Staff pulled a gun off a pending disposition in FastBound. Put it back on the shelf in Clover
        only if it was never sold there; otherwise flag it."""
        out = []
        for di in event.get("dispositionItemsRemoved") or event.get("dispositionItemsAdded") or []:
            item = di.get("item") or di
            rec = self.store.firearm(item.get("id", ""))
            if rec and rec.get("clover_order_id"):
                self.store.flag("removed_from_pending", item["id"],
                                f"{self.item_label(item)} was removed from pending disposition {event.get('id')} in FastBound but Clover order {rec['clover_order_id']} is still paid. Refund or re-add it.")
                out.append({"fb_item_id": item["id"], "status": "flagged"})
            else:
                out.append({"fb_item_id": item.get("id"), "status": "noop"})
        return {"disposition_id": event.get("id"), "items": out}

    def deliver(self, disposition_id: str) -> dict:
        """Commit a pending disposition because the firearm is physically leaving NOW.

        Surfaces the Multiple Sale (ATF 3310.4) signal — that is a legal filing the
        owner must review, not a log line.
        """
        fb = self._need_fb()
        result = fb.commit_disposition(disposition_id)
        committed_items = result.get("items") or []
        for it in committed_items:
            label = self.item_label(it)
            status = self._zero_in_clover(it.get("itemId") or it.get("id"), label) if self.clover else "clover_not_configured"
            self.store.upsert_firearm(it.get("itemId") or it.get("id"), serial=it.get("serial"), label=label, state="disposed", fb_disposition_id=disposition_id)
            it["clover"] = status
        if result.get("multiple_sale"):
            self.store.flag("multiple_sale_report", disposition_id,
                            "ATF Form 3310.4 Multiple Sale Report generated — review and transmit or dismiss it in FastBound.",
                            result.get("multiple_sale_url"))
        return result

    # ══════════════════════════════════════════════════════════════════════
    # Event dispatch (FastBound webhooks)
    # ══════════════════════════════════════════════════════════════════════
    @staticmethod
    def detect_event(headers: dict, body: Any) -> tuple[str, dict]:
        """FastBound deliveries carry the resource snapshot. Work out which event it is."""
        h = {k.lower(): v for k, v in (headers or {}).items()}
        name = h.get("x-fastbound-event") or h.get("x-fastbound-event-name") or ""
        payload = body if isinstance(body, dict) else {}
        for key in ("event", "eventName", "eventType", "type"):
            v = payload.get(key)
            if not name and isinstance(v, str) and "." in v:
                name = v
        for key in ("data", "payload", "resource"):
            if isinstance(payload.get(key), dict):
                payload = payload[key]
                break
        if not name:
            if "apiDownloadUrl" in payload or "buyerLanguage" in payload:
                name = "form4473.completed"
            elif "dispositionItemsAdded" in payload:
                name = "disposition.items.added"
            elif "dispositionItemsRemoved" in payload:
                name = "disposition.items.removed"
            elif "isManufacturingDisposition" in payload and "items" in payload:
                name = "disposition.committed"
            elif "isManufacturingAcquisition" in payload and "items" in payload:
                name = "acquisition.committed"
            elif "serial" in payload and "acquisitionType" in payload:
                name = "item.undisposed" if not payload.get("dispositionType") else "item.edited"
            else:
                name = "unknown"
        return name.lower(), payload

    def dispatch(self, name: str, payload: dict) -> dict:
        handlers = {
            "acquisition.committed": self.handle_acquisition_committed,
            "disposition.committed": self.handle_disposition_committed,
            "form4473.completed": self.handle_form4473_completed,
            "item.undisposed": self.handle_item_undisposed,
            "disposition.items.removed": self.handle_disposition_items_removed,
        }
        fn = handlers.get(name)
        if not fn:
            return {"event": name, "action": "stored_only"}
        return {"event": name, **fn(payload)}

    SUBSCRIBE_EVENTS = [
        "acquisition.committed",
        "disposition.committed",
        "disposition.items.removed",
        "form4473.completed",
        "item.undisposed",
        "multiplesalereport.transmitted",
    ]

    # ══════════════════════════════════════════════════════════════════════
    # Reconcile
    # ══════════════════════════════════════════════════════════════════════
    def reconcile(self, stale_days: int = 30) -> dict:
        fb = self._need_fb()
        clover = self._need_clover()
        report: dict[str, list] = {
            "missing_in_clover": [],            # on the book, nothing to ring up
            "sold_in_clover_no_disposition": [],  # Clover qty 0 but FastBound still shows it free
            "available_in_clover_but_pending": [],  # Clover could sell it again
            "disposed_but_sellable_in_clover": [],
            "orphan_clover_items": [],
            "stale_pending_dispositions": [],
            "attention": self.store.open_flags(),
        }
        clover_by_fb: dict[str, dict] = {}
        for ci in clover.iter_items():
            fb_id = self.fb_id_from_sku(ci.get("sku"))
            if fb_id:
                clover_by_fb[fb_id] = ci

        inventory = {i["id"]: i for i in fb.inventory()}
        for fb_id, item in inventory.items():
            label = self.item_label(item)
            ci = clover_by_fb.get(fb_id)
            if not ci:
                report["missing_in_clover"].append({"fb_item_id": fb_id, "label": label})
                continue
            qty = clover.stock_of(ci)
            pending = bool(item.get("dispositionId"))
            if pending and qty and qty > 0:
                report["available_in_clover_but_pending"].append({"fb_item_id": fb_id, "label": label, "clover_item_id": ci["id"], "qty": qty})
            if not pending and qty is not None and qty <= 0 and not ci.get("hidden"):
                report["sold_in_clover_no_disposition"].append({"fb_item_id": fb_id, "label": label, "clover_item_id": ci["id"]})

        for fb_id, ci in clover_by_fb.items():
            if fb_id in inventory:
                continue
            qty = clover.stock_of(ci)
            try:
                item = fb.item(fb_id)
            except FastBoundError:
                report["orphan_clover_items"].append({"clover_item_id": ci["id"], "name": ci.get("name"), "reason": "no FastBound item"})
                continue
            if item.get("disposed") and (qty or 0) > 0:
                report["disposed_but_sellable_in_clover"].append({"fb_item_id": fb_id, "label": self.item_label(item), "clover_item_id": ci["id"], "qty": qty})

        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=stale_days)
        for d in fb.dispositions(take=200):
            status = ((d.get("status") or {}).get("name") or "").lower()
            if "pending" not in status:
                continue
            when = d.get("date") or ""
            try:
                dts = dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
                if dts.tzinfo is None:
                    dts = dts.replace(tzinfo=dt.timezone.utc)
            except ValueError:
                continue
            if dts < cutoff:
                report["stale_pending_dispositions"].append({"disposition_id": d["id"], "date": when, "invoice": d.get("invoiceNumber"), "items": d.get("itemCount")})

        report["summary"] = {k: len(v) for k, v in report.items() if isinstance(v, list)}
        report["checked_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        self.store.set("last_reconcile", report["summary"])
        return report

    # ══════════════════════════════════════════════════════════════════════
    # Receiving helper used by the MCP tool / CLI
    # ══════════════════════════════════════════════════════════════════════
    def receive(self, contact_id: str, items: list[dict], acquisition_type: str = "Purchase", po: str = "", invoice: str = "", tracking: str = "", note: str = "") -> dict:
        """Record an acquisition in FastBound (CreateAndCommit) and list the guns in Clover."""
        fb = self._need_fb()
        payload = {
            "contactId": contact_id,
            "type": acquisition_type,
            "date": _today(),
            "purchaseOrderNumber": po or None,
            "invoiceNumber": invoice or None,
            "shipmentTrackingNumber": tracking or None,
            "note": note or None,
            "items": [],
        }
        for it in items:
            entry = {k: v for k, v in it.items() if v not in (None, "")}
            for money in ("cost", "price"):
                if money in entry:
                    entry[money] = f"{float(entry[money]):.2f}"
            payload["items"].append(entry)
        payload = {k: v for k, v in payload.items() if v is not None}
        acq = fb.create_and_commit_acquisition(payload)
        pushed = []
        if self.clover:
            for item in acq.get("items") or []:
                full = {**next((i for i in items if (i.get("serial") or "").upper() == (item.get("serial") or "").upper()), {}), **item}
                full.setdefault("disposed", False)
                full.setdefault("deleted", False)
                try:
                    pushed.append(self.push_firearm_to_clover(full))
                except Exception as e:
                    pushed.append({"fb_item_id": item.get("id"), "result": "error", "error": str(e)})
        return {"acquisition_id": acq.get("id"), "items": acq.get("items"), "clover": pushed}


def event_key(source: str, name: str, raw: bytes, payload: dict) -> str:
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return f"{source}:{name}:{payload.get('id', '')}:{digest}"
