"""SQLite state for the Clover + FastBound glue.

Holds the serial → (FastBound item, Clover item) map, the Clover order cursor,
processed-order / processed-event records for idempotency, and persisted OAuth
tokens. Small and single-file so it runs anywhere (Railway volume, laptop).
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS firearms (
    fb_item_id TEXT PRIMARY KEY,
    serial TEXT,
    label TEXT,
    clover_item_id TEXT,
    clover_sku TEXT,
    price REAL,
    state TEXT,                -- in_stock | pending_sale | 4473_complete | disposed | needs_attention
    fb_disposition_id TEXT,
    clover_order_id TEXT,
    form4473_id TEXT,
    form4473_url TEXT,
    note TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS firearms_serial ON firearms(serial);
CREATE INDEX IF NOT EXISTS firearms_clover ON firearms(clover_item_id);
CREATE TABLE IF NOT EXISTS orders (
    clover_order_id TEXT PRIMARY KEY,
    payment_state TEXT,
    fb_disposition_id TEXT,
    status TEXT,
    note TEXT,
    processed_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    event_key TEXT UNIQUE,
    event_name TEXT,
    payload TEXT,
    result TEXT,
    received_at TEXT
);
CREATE TABLE IF NOT EXISTS attention (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT,
    ref TEXT,
    message TEXT,
    url TEXT,
    created_at TEXT,
    cleared_at TEXT
);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str = "ffl.sqlite3"):
        self.path = path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)

    # ── kv ────────────────────────────────────────────────────────────────
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self.conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, json.dumps(value)))
            self.conn.commit()

    # ── firearms ──────────────────────────────────────────────────────────
    def upsert_firearm(self, fb_item_id: str, **fields) -> dict:
        fields["updated_at"] = _now()
        with self._lock:
            existing = self.conn.execute("SELECT * FROM firearms WHERE fb_item_id=?", (fb_item_id,)).fetchone()
            if existing:
                sets = ", ".join(f"{k}=?" for k in fields)
                self.conn.execute(f"UPDATE firearms SET {sets} WHERE fb_item_id=?", (*fields.values(), fb_item_id))
            else:
                cols = ["fb_item_id", *fields]
                self.conn.execute(
                    f"INSERT INTO firearms({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                    (fb_item_id, *fields.values()),
                )
            self.conn.commit()
        return self.firearm(fb_item_id)

    def firearm(self, fb_item_id: str) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM firearms WHERE fb_item_id=?", (fb_item_id,)).fetchone()
        return dict(row) if row else None

    def firearm_by_clover_item(self, clover_item_id: str) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM firearms WHERE clover_item_id=?", (clover_item_id,)).fetchone()
        return dict(row) if row else None

    def firearm_by_serial(self, serial: str) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM firearms WHERE upper(serial)=upper(?)", (serial,)).fetchall()
        return [dict(r) for r in rows]

    def firearms(self, state: str | None = None) -> list[dict]:
        with self._lock:
            if state:
                rows = self.conn.execute("SELECT * FROM firearms WHERE state=? ORDER BY updated_at DESC", (state,)).fetchall()
            else:
                rows = self.conn.execute("SELECT * FROM firearms ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    # ── orders ────────────────────────────────────────────────────────────
    def order(self, clover_order_id: str) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM orders WHERE clover_order_id=?", (clover_order_id,)).fetchone()
        return dict(row) if row else None

    def record_order(self, clover_order_id: str, payment_state: str | None, status: str, note: str = "", fb_disposition_id: str | None = None) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO orders(clover_order_id,payment_state,fb_disposition_id,status,note,processed_at) VALUES(?,?,?,?,?,?)",
                (clover_order_id, payment_state, fb_disposition_id, status, note, _now()),
            )
            self.conn.commit()

    def orders(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM orders ORDER BY processed_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ── events (idempotency + audit) ──────────────────────────────────────
    def seen_event(self, event_key: str) -> bool:
        with self._lock:
            return self.conn.execute("SELECT 1 FROM events WHERE event_key=?", (event_key,)).fetchone() is not None

    def record_event(self, source: str, event_key: str, event_name: str, payload: Any, result: str = "") -> bool:
        """Returns False if the event was already recorded (duplicate delivery)."""
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT INTO events(source,event_key,event_name,payload,result,received_at) VALUES(?,?,?,?,?,?)",
                    (source, event_key, event_name, json.dumps(payload)[:200000], result, _now()),
                )
                self.conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def update_event_result(self, event_key: str, result: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE events SET result=? WHERE event_key=?", (result[:2000], event_key))
            self.conn.commit()

    def events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT id,source,event_key,event_name,result,received_at FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ── attention queue (things a human must look at) ─────────────────────
    def flag(self, kind: str, ref: str, message: str, url: str | None = None) -> None:
        with self._lock:
            dup = self.conn.execute(
                "SELECT 1 FROM attention WHERE kind=? AND ref=? AND cleared_at IS NULL", (kind, ref)
            ).fetchone()
            if not dup:
                self.conn.execute(
                    "INSERT INTO attention(kind,ref,message,url,created_at) VALUES(?,?,?,?,?)",
                    (kind, ref, message, url, _now()),
                )
                self.conn.commit()

    def clear_flags(self, kind: str, ref: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE attention SET cleared_at=? WHERE kind=? AND ref=? AND cleared_at IS NULL", (_now(), kind, ref))
            self.conn.commit()

    def open_flags(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM attention WHERE cleared_at IS NULL ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
