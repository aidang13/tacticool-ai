"""Lazy singletons: settings, store, API clients and the Sync object."""
from __future__ import annotations

import threading

from .clover import Clover
from .config import Settings, load_settings
from .fastbound import FastBound
from .store import Store
from .sync import Sync

_lock = threading.Lock()
_runtime: "Runtime | None" = None


class Runtime:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.store = Store(self.settings.db_path)
        self.fb = self._build_fastbound()
        self.clover = self._build_clover()
        self.sync = Sync(self.settings, self.fb, self.clover, self.store)

    def _build_fastbound(self) -> FastBound | None:
        s = self.settings
        if not s.fastbound_configured:
            return None
        return FastBound(s.fastbound_account, api_key=s.fastbound_api_key, access_token=s.fastbound_access_token,
                         audit_user=s.fastbound_audit_user, base=s.fastbound_base)

    def _build_clover(self) -> Clover | None:
        s = self.settings
        saved = self.store.get("clover_tokens") or {}
        access = s.clover_access_token or saved.get("access_token", "")
        refresh = s.clover_refresh_token or saved.get("refresh_token", "")
        if not (s.clover_merchant_id and (access or refresh)):
            return None
        return Clover(
            s.clover_merchant_id, access_token=access, base=s.clover_base, app_id=s.clover_app_id,
            app_secret=s.clover_app_secret, refresh_token=refresh,
            on_tokens=lambda tokens: self.store.set("clover_tokens", {
                "access_token": tokens.get("access_token"), "refresh_token": tokens.get("refresh_token"),
                "access_token_expiration": tokens.get("access_token_expiration"),
                "refresh_token_expiration": tokens.get("refresh_token_expiration"),
            }),
        )

    def status(self) -> dict:
        s = self.settings
        return {
            "fastbound_configured": s.fastbound_configured,
            "clover_configured": self.clover is not None,
            "poll_seconds": s.poll_seconds,
            "db_path": s.db_path,
            "last_poll_at": self.store.get("last_poll_at"),
            "last_reconcile": self.store.get("last_reconcile"),
            "open_flags": len(self.store.open_flags()),
            "firearms_tracked": len(self.store.firearms()),
        }


def get_runtime() -> Runtime:
    global _runtime
    with _lock:
        if _runtime is None:
            _runtime = Runtime()
        return _runtime


def reset_runtime(runtime: Runtime | None = None) -> None:
    global _runtime
    with _lock:
        _runtime = runtime
