"""Thin FastBound REST client.

Covers the parts of the API this shop uses: items, acquisitions, dispositions,
contacts, smart lists, 4473 downloads and webhook subscriptions.

Auth: HTTP Basic with the per-account API key (self-serve from FastBound
Settings → Generate API Key), or an OAuth bearer token if one was issued.
Every write under Basic auth needs the X-AuditUser header; the client adds it.

Reference: https://github.com/FastBound/skills (official API skill + swagger).
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable

import requests


class FastBoundError(RuntimeError):
    def __init__(self, status: int, errors: list[dict], url: str):
        self.status = status
        self.errors = errors
        self.url = url
        detail = "; ".join(f"{e.get('field') or '-'}: {e.get('message')}" for e in errors) or f"HTTP {status}"
        super().__init__(f"FastBound {status} on {url}: {detail}")


class FastBound:
    def __init__(
        self,
        account: str,
        api_key: str = "",
        access_token: str = "",
        audit_user: str = "",
        base: str = "https://cloud.fastbound.com",
        session: Any | None = None,
        timeout: int = 30,
    ):
        if not account:
            raise ValueError("FastBound account number is required")
        if not (api_key or access_token):
            raise ValueError("FastBound needs an API key or an OAuth access token")
        self.account = account
        self.api_key = api_key
        self.access_token = access_token
        self.audit_user = audit_user
        self.base = base.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    # ── plumbing ──────────────────────────────────────────────────────────
    def _url(self, path: str) -> str:
        return f"{self.base}/{self.account}/api/{path.lstrip('/')}"

    def _headers(self, write: bool) -> dict:
        h = {"Accept": "application/json", "x-api-version": "1.0"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        if write and self.audit_user:
            h["X-AuditUser"] = self.audit_user
        return h

    def request(self, method: str, path: str, *, params: dict | None = None, json: Any = None, raw: bool = False):
        write = method.upper() in ("POST", "PUT", "DELETE", "PATCH")
        if write and not self.access_token and not self.audit_user:
            raise FastBoundError(0, [{"field": "X-AuditUser", "message": "FASTBOUND_AUDIT_USER is required for writes under API-key auth"}], path)
        kwargs: dict = {"headers": self._headers(write), "timeout": self.timeout}
        if params:
            kwargs["params"] = {k: v for k, v in params.items() if v is not None}
        if json is not None:
            kwargs["json"] = json
        if not self.access_token:
            kwargs["auth"] = (self.api_key, self.api_key)
        resp = self.session.request(method.upper(), self._url(path), **kwargs)
        if resp.status_code >= 400:
            try:
                errors = resp.json().get("errors", [])
            except Exception:
                errors = [{"field": None, "message": (resp.text or "")[:300]}]
            raise FastBoundError(resp.status_code, errors, path)
        return resp

    def get(self, path: str, **params) -> Any:
        return self.request("GET", path, params=params).json()

    @staticmethod
    def _json_or_empty(resp) -> Any:
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}

    # ── account / smart lists ─────────────────────────────────────────────
    def account_info(self) -> dict:
        return self.get("Account")

    def smart_list(self, name: str) -> list:
        """name: AcquireType | DisposeType | ItemType | Caliber | Manufacturer | Condition | Location ..."""
        data = self.get(f"SmartLists/{name}")
        if isinstance(data, dict):
            for key in ("items", "values", "results"):
                if key in data:
                    return data[key]
        return data

    # ── items ─────────────────────────────────────────────────────────────
    def items(self, take: int = 100, skip: int = 0, **filters) -> dict:
        return self.get("Items", take=take, skip=skip, **filters)

    def iter_items(self, page: int = 100, **filters) -> Iterable[dict]:
        skip = 0
        while True:
            data = self.items(take=page, skip=skip, **filters)
            batch = data.get("items") or []
            yield from batch
            skip += len(batch)
            if not batch or skip >= int(data.get("records") or 0):
                break

    def inventory(self, **filters) -> list[dict]:
        """Firearms currently on the book (acquired, not disposed, not deleted)."""
        return [i for i in self.iter_items(**filters) if not i.get("disposed") and not i.get("deleted")]

    def item(self, item_id: str) -> dict:
        return self.get(f"Items/{item_id}")

    def find_by_serial(self, serial: str) -> list[dict]:
        serial = serial.strip()
        hits = self.items(take=50, serial=serial).get("items") or []
        exact = [i for i in hits if (i.get("serial") or "").strip().upper() == serial.upper()]
        return exact or hits

    def set_external_id(self, item_id: str, external_id: str) -> None:
        self.request("PUT", f"Items/{item_id}/SetExternalId", json={"externalId": external_id})

    # ── contacts ──────────────────────────────────────────────────────────
    def contacts(self, **filters) -> list[dict]:
        data = self.get("Contacts", **filters)
        return data.get("contacts") or data.get("items") or (data if isinstance(data, list) else [])

    def contact(self, contact_id: str) -> dict:
        return self.get(f"Contacts/{contact_id}")

    def create_contact(self, payload: dict) -> tuple[str, dict]:
        """Returns (contact_id, body). Honors FastBound's duplicate-detection header."""
        resp = self.request("POST", "Contacts", json=payload)
        existing = resp.headers.get("X-FastBound-ExistingContactId")
        body = self._json_or_empty(resp)
        if existing:
            return existing, body
        return body.get("id"), body

    # ── acquisitions (receiving) ──────────────────────────────────────────
    def acquisitions(self, **filters) -> list[dict]:
        return self.get("Acquisitions", **filters).get("acquisitions") or []

    def acquisition(self, acquisition_id: str) -> dict:
        return self.get(f"Acquisitions/{acquisition_id}")

    def create_and_commit_acquisition(self, payload: dict) -> dict:
        """One round trip: create, attach contact, add items, commit. Atomic."""
        payload.setdefault("date", dt.date.today().isoformat())
        return self.request("POST", "Acquisitions/CreateAndCommit", json=payload).json()

    # ── dispositions (selling / transferring out) ─────────────────────────
    def dispositions(self, **filters) -> list[dict]:
        return self.get("Dispositions", **filters).get("dispositions") or []

    def disposition(self, disposition_id: str) -> dict:
        return self.get(f"Dispositions/{disposition_id}")

    def disposition_by_external_id(self, external_id: str) -> dict | None:
        try:
            return self.get(f"Dispositions/GetByExternalId/{external_id}")
        except FastBoundError as e:
            if e.status == 404:
                return None
            raise

    def pending_4473s(self, include_awaiting: bool = True) -> list[dict]:
        data = self.get("Dispositions/Only4473s", take=200, includeAwaiting4473Completion=include_awaiting)
        return data.get("dispositions") or []

    def create_pending_disposition(self, payload: dict) -> dict:
        payload.setdefault("date", dt.date.today().isoformat())
        return self.request("POST", "Dispositions", json=payload).json()

    def add_disposition_items(self, disposition_id: str, items: list[dict]) -> Any:
        """items: [{"id": <fastbound item id>, "price": 599.99}, ...]"""
        return self._json_or_empty(self.request("POST", f"Dispositions/{disposition_id}/Items", json={"items": items}))

    def disposition_items(self, disposition_id: str) -> list[dict]:
        return self.get(f"Dispositions/{disposition_id}/Items").get("items") or []

    def remove_disposition_item(self, disposition_id: str, item_id: str) -> None:
        self.request("DELETE", f"Dispositions/{disposition_id}/Items/Remove/{item_id}")

    def delete_pending_disposition(self, disposition_id: str) -> None:
        self.request("DELETE", f"Dispositions/{disposition_id}")

    def lock_disposition(self, disposition_id: str) -> None:
        self.request("PUT", f"Dispositions/Lock/{disposition_id}")

    def commit_disposition(self, disposition_id: str) -> dict:
        """Commit = the firearm has physically left. Never call this on payment alone.

        Returns the commit body plus `multiple_sale` / `multiple_sale_url` and the
        inter-FFL auto-acquisition headers so callers can surface them.
        """
        resp = self.request("POST", f"Dispositions/{disposition_id}/Commit", params={"listDisposedItems": "true"}, json={})
        body = self._json_or_empty(resp)
        h = resp.headers
        body["multiple_sale"] = (h.get("X-FastBound-MultipleSale") or "").lower() == "true"
        body["multiple_sale_url"] = h.get("X-FastBound-MultipleSaleUrl")
        body["receiver_acquisition"] = {
            "account": h.get("X-FastBound-AcquisitionAccount"),
            "id": h.get("X-FastBound-AcquisitionId"),
            "url": h.get("X-FastBound-AcquisitionUrl"),
        } if h.get("X-FastBound-AcquisitionId") else None
        return body

    # ── 4473 ──────────────────────────────────────────────────────────────
    def download_4473(self, form_id: str) -> bytes:
        return self.request("GET", f"Form4473s/Download/{form_id}", raw=True).content

    # ── webhooks ──────────────────────────────────────────────────────────
    def webhook_events(self) -> list:
        return self.get("Webhooks/Events")

    def get_webhook(self, name: str) -> dict | None:
        try:
            return self.get(f"Webhooks/{name}")
        except FastBoundError as e:
            if e.status == 404:
                return None
            raise

    def create_webhook(self, name: str, url: str, events: list[str], description: str = "") -> dict:
        """The response carries `signingSecret` ONCE. Store it immediately."""
        return self.request("POST", "Webhooks", json={"name": name, "url": url, "description": description[:100], "events": events}).json()

    def update_webhook(self, name: str, url: str, events: list[str], description: str = "") -> dict:
        return self._json_or_empty(self.request("PUT", f"Webhooks/{name}", json={"name": name, "url": url, "description": description[:100], "events": events}))

    def delete_webhook(self, name: str) -> None:
        self.request("DELETE", f"Webhooks/{name}")


def describe_item(item: dict) -> str:
    """Human-readable one-liner for a FastBound item."""
    bits = [item.get("manufacturer"), item.get("model"), item.get("caliber"), item.get("type")]
    label = " ".join(b for b in bits if b)
    return f"{label} S/N {item.get('serial', '?')}"
