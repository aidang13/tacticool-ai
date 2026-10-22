"""Environment-driven settings for the Clover + FastBound integration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    # FastBound — https://cloud.fastbound.com/<account>/api
    fastbound_account: str = field(default_factory=lambda: _env("FASTBOUND_ACCOUNT"))
    fastbound_api_key: str = field(default_factory=lambda: _env("FASTBOUND_API_KEY"))
    fastbound_access_token: str = field(default_factory=lambda: _env("FASTBOUND_ACCESS_TOKEN"))
    fastbound_audit_user: str = field(default_factory=lambda: _env("FASTBOUND_AUDIT_USER"))
    fastbound_base: str = field(default_factory=lambda: _env("FASTBOUND_BASE", "https://cloud.fastbound.com"))
    fastbound_webhook_secret: str = field(default_factory=lambda: _env("FASTBOUND_WEBHOOK_SECRET"))
    # Disposition type used when a Clover sale creates a pending disposition.
    # Valid strings come from GET /SmartLists/DisposeType (run `python -m ffl check`).
    fastbound_sale_type: str = field(default_factory=lambda: _env("FASTBOUND_SALE_TYPE", "Sale"))

    # Clover — https://api.clover.com/v3/merchants/<mId>
    clover_merchant_id: str = field(default_factory=lambda: _env("CLOVER_MERCHANT_ID"))
    clover_access_token: str = field(default_factory=lambda: _env("CLOVER_ACCESS_TOKEN"))
    clover_base: str = field(default_factory=lambda: _env("CLOVER_BASE", "https://api.clover.com"))
    clover_app_id: str = field(default_factory=lambda: _env("CLOVER_APP_ID"))
    clover_app_secret: str = field(default_factory=lambda: _env("CLOVER_APP_SECRET"))
    clover_refresh_token: str = field(default_factory=lambda: _env("CLOVER_REFRESH_TOKEN"))
    clover_webhook_auth: str = field(default_factory=lambda: _env("CLOVER_WEBHOOK_AUTH"))
    clover_firearms_category: str = field(default_factory=lambda: _env("CLOVER_FIREARMS_CATEGORY", "Firearms"))

    # Glue behaviour
    db_path: str = field(default_factory=lambda: _env("FFL_DB_PATH", "ffl.sqlite3"))
    poll_seconds: int = field(default_factory=lambda: int(_env("FFL_POLL_SECONDS", "60") or 0))
    mcp_secret: str = field(default_factory=lambda: _env("FFL_MCP_SECRET"))
    public_url: str = field(default_factory=lambda: _env("FFL_PUBLIC_URL").rstrip("/"))
    hide_sold_items: bool = field(default_factory=lambda: _env("FFL_HIDE_SOLD_ITEMS", "true").lower() != "false")

    @property
    def fastbound_configured(self) -> bool:
        return bool(self.fastbound_account and (self.fastbound_api_key or self.fastbound_access_token))

    @property
    def clover_configured(self) -> bool:
        return bool(self.clover_merchant_id and (self.clover_access_token or self.clover_refresh_token))

    @property
    def sku_prefix(self) -> str:
        """Clover SKU prefix that marks an item as a serialized FastBound firearm."""
        return "FB:"


def load_settings() -> Settings:
    return Settings()
