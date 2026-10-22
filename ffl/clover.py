"""Thin Clover REST (v3) client.

Covers inventory items, stock, categories, orders and OAuth v2 token refresh.

Auth: `Authorization: Bearer <token>`. The token is either a merchant API token
or an OAuth v2 access token. When an OAuth refresh token + app credentials are
configured the client refreshes automatically on 401 and hands the new pair to
`on_tokens` so the caller can persist it (Clover refresh tokens are single-use).
"""
from __future__ import annotations

import time
from typing import Any, Callable, Iterable

import requests


class CloverError(RuntimeError):
    def __init__(self, status: int, message: str, url: str):
        self.status = status
        self.url = url
        super().__init__(f"Clover {status} on {url}: {message}")


class Clover:
    def __init__(
        self,
        merchant_id: str,
        access_token: str = "",
        base: str = "https://api.clover.com",
        app_id: str = "",
        app_secret: str = "",
        refresh_token: str = "",
        on_tokens: Callable[[dict], None] | None = None,
        session: Any | None = None,
        timeout: int = 30,
    ):
        if not merchant_id:
            raise ValueError("Clover merchant id is required")
        if not (access_token or refresh_token):
            raise ValueError("Clover needs an access token or a refresh token")
        self.merchant_id = merchant_id
        self.access_token = access_token
        self.base = base.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret
        self.refresh_token = refresh_token
        self.on_tokens = on_tokens
        self.session = session or requests.Session()
        self.timeout = timeout

    # ── plumbing ──────────────────────────────────────────────────────────
    def _url(self, path: str) -> str:
        if path.startswith("/"):
            return f"{self.base}{path}"
        return f"{self.base}/v3/merchants/{self.merchant_id}/{path}"

    def request(self, method: str, path: str, *, params: dict | None = None, json: Any = None, _retry: bool = True):
        if not self.access_token and self.refresh_token:
            self.refresh()
        headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
        resp = self.session.request(method.upper(), self._url(path), headers=headers, params=params or None, json=json, timeout=self.timeout)
        if resp.status_code == 401 and _retry and self.refresh_token and self.app_id:
            self.refresh()
            return self.request(method, path, params=params, json=json, _retry=False)
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("message") or resp.text
            except Exception:
                msg = resp.text
            raise CloverError(resp.status_code, (msg or "")[:300], path)
        if not resp.content:
            return {}
        return resp.json()

    def get(self, path: str, **params) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, json: Any = None, **params) -> Any:
        return self.request("POST", path, params=params, json=json)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    # ── OAuth v2 ──────────────────────────────────────────────────────────
    @staticmethod
    def authorize_url(app_id: str, redirect_uri: str, base_web: str = "https://www.clover.com") -> str:
        return f"{base_web}/oauth/v2/authorize?client_id={app_id}&redirect_uri={redirect_uri}"

    def exchange_code(self, code: str) -> dict:
        resp = self.session.request(
            "POST", f"{self.base}/oauth/v2/token",
            json={"client_id": self.app_id, "client_secret": self.app_secret, "code": code},
            headers={"Accept": "application/json"}, timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise CloverError(resp.status_code, resp.text[:300], "/oauth/v2/token")
        tokens = resp.json()
        self._absorb(tokens)
        return tokens

    def refresh(self) -> dict:
        if not (self.app_id and self.refresh_token):
            raise CloverError(401, "No refresh token / app id configured; re-authorize", "/oauth/v2/refresh")
        resp = self.session.request(
            "POST", f"{self.base}/oauth/v2/refresh",
            json={"client_id": self.app_id, "refresh_token": self.refresh_token},
            headers={"Accept": "application/json"}, timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise CloverError(resp.status_code, resp.text[:300], "/oauth/v2/refresh")
        tokens = resp.json()
        self._absorb(tokens)
        return tokens

    def _absorb(self, tokens: dict) -> None:
        self.access_token = tokens.get("access_token") or self.access_token
        self.refresh_token = tokens.get("refresh_token") or self.refresh_token
        if self.on_tokens:
            self.on_tokens(tokens)

    # ── merchant ──────────────────────────────────────────────────────────
    def merchant(self) -> dict:
        return self.get("")

    # ── inventory ─────────────────────────────────────────────────────────
    def iter_items(self, filter: str | None = None, expand: str = "itemStock,categories", page: int = 100) -> Iterable[dict]:
        offset = 0
        while True:
            params = {"expand": expand, "limit": page, "offset": offset}
            if filter:
                params["filter"] = filter
            batch = self.get("items", **params).get("elements") or []
            yield from batch
            if len(batch) < page:
                break
            offset += page

    def item(self, item_id: str, expand: str = "itemStock,categories") -> dict:
        return self.get(f"items/{item_id}", expand=expand)

    def find_item_by_sku(self, sku: str) -> dict | None:
        hits = list(self.iter_items(filter=f"sku={sku}"))
        for h in hits:
            if h.get("sku") == sku:
                return h
        return None

    def create_item(self, name: str, price_cents: int, sku: str = "", code: str = "", **extra) -> dict:
        body = {
            "name": name[:127],
            "price": int(price_cents),
            "priceType": "FIXED",
            "isRevenue": True,
            "hidden": False,
            "available": True,
        }
        if sku:
            body["sku"] = sku
        if code:
            body["code"] = code
        body.update(extra)
        return self.post("items", json=body)

    def update_item(self, item_id: str, **fields) -> dict:
        return self.post(f"items/{item_id}", json=fields)

    def delete_item(self, item_id: str) -> None:
        self.delete(f"items/{item_id}")

    def set_stock(self, item_id: str, quantity: float) -> dict:
        return self.post(f"item_stocks/{item_id}", json={"quantity": quantity})

    def stock_of(self, item: dict) -> float | None:
        stock = item.get("itemStock") or {}
        q = stock.get("quantity", stock.get("stockCount"))
        return None if q is None else float(q)

    # ── categories ────────────────────────────────────────────────────────
    def categories(self) -> list[dict]:
        return self.get("categories", limit=500).get("elements") or []

    def ensure_category(self, name: str) -> dict:
        for c in self.categories():
            if (c.get("name") or "").strip().lower() == name.strip().lower():
                return c
        return self.post("categories", json={"name": name})

    def add_item_to_category(self, item_id: str, category_id: str) -> None:
        self.post("category_items", json={"elements": [{"item": {"id": item_id}, "category": {"id": category_id}}]})

    # ── orders ────────────────────────────────────────────────────────────
    ORDER_EXPAND = "lineItems,payments,refunds,customers"

    def order(self, order_id: str) -> dict:
        return self.get(f"orders/{order_id}", expand=self.ORDER_EXPAND)

    def orders_modified_since(self, since_ms: int, page: int = 100) -> Iterable[dict]:
        offset = 0
        while True:
            batch = self.get(
                "orders",
                filter=f"modifiedTime>={int(since_ms)}",
                expand=self.ORDER_EXPAND,
                orderBy="modifiedTime ASC",
                limit=page,
                offset=offset,
            ).get("elements") or []
            yield from batch
            if len(batch) < page:
                break
            offset += page

    def line_items(self, order: dict) -> list[dict]:
        li = order.get("lineItems")
        if isinstance(li, dict):
            return li.get("elements") or []
        return li or []

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)
