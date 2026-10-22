"""Command line for setup and day-to-day checks.

    python -m ffl check                 verify both connections, print valid FastBound type values
    python -m ffl import-inventory      list every FastBound firearm in Clover
    python -m ffl poll                  process new Clover orders once
    python -m ffl reconcile             compare both systems
    python -m ffl register-webhook      subscribe FastBound events to FFL_PUBLIC_URL/webhooks/fastbound
    python -m ffl clover-auth-url       print the Clover OAuth authorize link (needs CLOVER_APP_ID + FFL_PUBLIC_URL)
    python -m ffl mcp                   run the Claude MCP server over stdio
"""
from __future__ import annotations

import json
import sys

from .runtime import get_runtime


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_check() -> int:
    rt = get_runtime()
    s = rt.settings
    ok = True
    print("== FastBound")
    if not rt.fb:
        print("  not configured: set FASTBOUND_ACCOUNT and FASTBOUND_API_KEY (and FASTBOUND_AUDIT_USER)")
        ok = False
    else:
        try:
            acct = rt.fb.account_info()
            print(f"  connected to account {s.fastbound_account}: {acct.get('name') or acct.get('licenseName') or ''}".rstrip())
            if not s.fastbound_audit_user and not s.fastbound_access_token:
                print("  WARNING: FASTBOUND_AUDIT_USER is empty — writes (dispositions, acquisitions) will fail")
            for name in ("AcquireType", "DisposeType", "ItemType"):
                try:
                    vals = rt.fb.smart_list(name)
                    print(f"  {name}: {vals}")
                except Exception as e:
                    print(f"  {name}: could not load ({e})")
            print(f"  sale disposition type in use: {s.fastbound_sale_type}  (FASTBOUND_SALE_TYPE)")
            hook = rt.fb.get_webhook("tacticool-sync")
            print(f"  webhook 'tacticool-sync': {'registered → ' + hook.get('url', '') if hook else 'not registered (run register-webhook)'}")
        except Exception as e:
            print(f"  FAILED: {e}")
            ok = False
    print("== Clover")
    if not rt.clover:
        print("  not configured: set CLOVER_MERCHANT_ID and CLOVER_ACCESS_TOKEN (or complete the OAuth flow)")
        ok = False
    else:
        try:
            m = rt.clover.merchant()
            print(f"  connected to merchant {m.get('id')}: {m.get('name')}")
            cat = rt.clover.ensure_category(s.clover_firearms_category)
            print(f"  firearms category: {cat.get('name')} ({cat.get('id')})")
            n = sum(1 for i in rt.clover.iter_items() if (i.get('sku') or '').startswith(s.sku_prefix))
            print(f"  serialized firearm items in Clover: {n}")
        except Exception as e:
            print(f"  FAILED: {e}")
            ok = False
    print("== Glue")
    print(f"  database: {s.db_path}")
    print(f"  order polling: every {s.poll_seconds}s" if s.poll_seconds else "  order polling: disabled (FFL_POLL_SECONDS=0)")
    print(f"  public url: {s.public_url or '(FFL_PUBLIC_URL not set — webhooks and OAuth callback need it)'}")
    print(f"  MCP over HTTPS: {'/mcp/<FFL_MCP_SECRET>' if s.mcp_secret else 'disabled (set FFL_MCP_SECRET)'}")
    flags = rt.store.open_flags()
    if flags:
        print(f"  ATTENTION ({len(flags)}):")
        for f in flags:
            print(f"   - [{f['kind']}] {f['message']}")
    return 0 if ok else 1


def cmd_register_webhook() -> int:
    rt = get_runtime()
    s = rt.settings
    if not s.public_url:
        print("FFL_PUBLIC_URL is required (e.g. https://tacticool-ai.up.railway.app)")
        return 1
    url = f"{s.public_url}/webhooks/fastbound"
    events = rt.sync.SUBSCRIBE_EVENTS
    existing = rt.fb.get_webhook("tacticool-sync")
    if existing:
        rt.fb.update_webhook("tacticool-sync", url, events, "Clover sync for Tacti-Cool Gun")
        print(f"updated webhook tacticool-sync → {url}")
        print("signing secret unchanged (FastBound only returns it on creation; delete + re-register to rotate)")
        return 0
    created = rt.fb.create_webhook("tacticool-sync", url, events, "Clover sync for Tacti-Cool Gun")
    print(f"created webhook tacticool-sync → {url}")
    print("\nSAVE THIS NOW as FASTBOUND_WEBHOOK_SECRET (FastBound never shows it again):\n")
    print(f"  {created.get('signingSecret')}\n")
    return 0


def cmd_clover_auth_url() -> int:
    rt = get_runtime()
    s = rt.settings
    if not (s.clover_app_id and s.public_url):
        print("needs CLOVER_APP_ID and FFL_PUBLIC_URL")
        return 1
    from .clover import Clover
    web = "https://sandbox.dev.clover.com" if "sandbox" in s.clover_base else "https://www.clover.com"
    print(Clover.authorize_url(s.clover_app_id, f"{s.public_url}/ffl/clover/oauth/callback", base_web=web))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "help"
    rt = None
    if cmd == "check":
        return cmd_check()
    if cmd == "import-inventory":
        _print(get_runtime().sync.import_inventory()); return 0
    if cmd == "poll":
        _print(get_runtime().sync.poll_orders()); return 0
    if cmd == "reconcile":
        _print(get_runtime().sync.reconcile()); return 0
    if cmd == "register-webhook":
        return cmd_register_webhook()
    if cmd == "clover-auth-url":
        return cmd_clover_auth_url()
    if cmd == "mcp":
        from .mcp_server import run_stdio
        run_stdio(); return 0
    print(__doc__)
    return 0 if cmd in ("help", "-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main())
