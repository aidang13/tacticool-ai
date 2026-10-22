# Clover + FastBound: one counter, two systems

Bravo + e4473 felt like one system because Bravo owned the register, the bound book and
the 4473. With Clover + FastBound there are two vendors, so this repo carries the glue that
makes them behave like one. FastBound stays the **book of record** (A&D + e4473); Clover is
**the register**; the code in `ffl/` keeps them in step, and Claude gets a set of tools to
run the counter on top of both.

## How the day works once it is set up

| Step | Where you do it | What happens automatically |
|---|---|---|
| **Receive** a gun | FastBound (Acquire) **or** ask Claude: *"receive these from Davidson's, PO 1234"* | Each serial appears in Clover as its own item: qty 1, price from FastBound, barcode = serial, in the **Firearms** category. |
| **Sell** a gun | Clover: scan the serial tag, take payment | A **pending disposition** opens in FastBound with the Clover order number as the invoice. Nothing is written to the A&D yet. |
| **4473 + NICS** | FastBound e4473 on the tablet, started from that pending disposition (or started first, the sale links to it either way) | The completed 4473 is recorded against the gun. A denial raises an attention flag. |
| **Hand it over** | FastBound: commit the disposition (or ask Claude to `deliver` once the gun is leaving) | Clover item goes to qty 0 and is hidden so it can't be sold twice. An ATF 3310.4 multiple-sale report is flagged if FastBound generates one. |
| **Refund before pickup** | Clover: refund the order | The gun comes off the pending disposition and is back at qty 1 in Clover. A refund *after* transfer is flagged for you to handle in FastBound. |
| **Check yourself** | Ask Claude *"reconcile"* or run `python -m ffl reconcile` | Lists every mismatch: on the book but not in Clover, sold in Clover with no disposition, pending for 30+ days, and so on. |

The one rule the code never breaks: **a disposition is committed only when a person says
the gun is physically leaving.** A paid Clover order never commits anything.

## Setup (about an hour)

### 1. FastBound

1. Your **account number** is in the URL after you log in: `https://cloud.fastbound.com/<ACCOUNT>/...`
2. **Settings → Generate API Key.** Copy it once; it is full read/write.
3. Pick the FastBound user the API should act as (your own login is fine). Its email is `FASTBOUND_AUDIT_USER`.
4. Make sure the e4473 is turned on for the account (FastBound Settings → 4473).

Set in Railway (or `.env` locally):

```
FASTBOUND_ACCOUNT=12345
FASTBOUND_API_KEY=...
FASTBOUND_AUDIT_USER=aidan@tacticoolgun.com
```

FastBound now prefers OAuth for new integrations, and an API key still works. If you later want OAuth,
email support@fastbound.com for credentials and put the token in `FASTBOUND_ACCESS_TOKEN`.

### 2. Clover

1. **Merchant ID**: Clover web dashboard → Account & Setup → Business Information (also in the dashboard URL).
2. **Token**, one of two ways:
   - **API Tokens** in the dashboard (Account & Setup → API Tokens → Create new token, tick Inventory, Orders, Merchant, Customers, Payments read + write). Clover documents dashboard tokens as sandbox-only, but many production US dashboards still offer them. If yours does, paste it into `CLOVER_ACCESS_TOKEN` and you are done.
   - **OAuth app** (always works): create an app at https://www.clover.com/developers, set the redirect URL to `https://<your app>/ffl/clover/oauth/callback`, request the same permissions, install it on your merchant. Put `CLOVER_APP_ID` and `CLOVER_APP_SECRET` in Railway, deploy, run `python -m ffl clover-auth-url`, open the link, approve. Tokens are stored in the sync database and refresh themselves.
3. Turn on **Track stock** in Clover Inventory settings so a sale drops the gun's quantity to 0.

```
CLOVER_MERCHANT_ID=ABC123XYZ
CLOVER_ACCESS_TOKEN=...            # or CLOVER_APP_ID + CLOVER_APP_SECRET
```

### 3. The glue (this app on Railway)

```
FFL_PUBLIC_URL=https://<your railway app domain>
FFL_MCP_SECRET=<long random string>
FFL_DB_PATH=/data/ffl.sqlite3       # add a Railway volume mounted at /data
FFL_POLL_SECONDS=60
```

Deploy, then from a shell with the same env (Railway shell or locally with `.env`):

```
python -m ffl check               # verifies both logins, prints the valid Acquire/Dispose/Item types
python -m ffl register-webhook    # subscribes FastBound events → prints the signing secret ONCE
```

Put the printed secret in `FASTBOUND_WEBHOOK_SECRET` and redeploy. Then:

```
python -m ffl import-inventory    # every gun on the book becomes a Clover item (safe to re-run)
```

Clover orders are picked up by polling every `FFL_POLL_SECONDS`. If you built a Clover OAuth app you
can also add a webhook in the developer dashboard pointing at `https://<app>/webhooks/clover`; the
verification code Clover sends is shown at `/ffl/status?key=<FFL_MCP_SECRET>`.

### 4. Connect Claude

**claude.ai / Claude Desktop (custom connector):** add `https://<your app>/mcp/<FFL_MCP_SECRET>` as a
remote MCP server. Then: *"what's pending for 4473?"*, *"find serial ABC123"*, *"receive 5 Glocks from
RSR on PO 1234"*, *"reconcile"*.

**Claude Code / Claude Desktop (local):**

```json
{
  "mcpServers": {
    "tacticool-ffl": {
      "command": "python",
      "args": ["-m", "ffl", "mcp"],
      "cwd": "/path/to/tacticool-ai",
      "env": { "FASTBOUND_ACCOUNT": "...", "FASTBOUND_API_KEY": "...", "FASTBOUND_AUDIT_USER": "...", "CLOVER_MERCHANT_ID": "...", "CLOVER_ACCESS_TOKEN": "...", "FFL_DB_PATH": "/path/to/ffl.sqlite3" }
    }
  }
}
```

Tools exposed: `status`, `inventory`, `find_firearm`, `pending_sales`, `recent_sales`, `sync_now`,
`push_inventory_to_clover`, `reconcile`, `find_contact`, `create_ffl_contact`, `receive_firearms`,
`smart_list`, `clover_order`, `deliver_firearm`, `attention`.

Optional but worth it: install FastBound's own Claude skill so Claude knows the API inside out:
`/plugin marketplace add FastBound/skills` then `/plugin install fastbound@fastbound-skills`.

## First live sale: what to verify

1. Ring up a gun in Clover and pay. Within a minute `pending_sales` (or FastBound → Dispositions → Pending) shows a disposition whose invoice is the Clover order id.
2. Open it in FastBound and start the 4473 from it. If FastBound's UI does not let you start a 4473 from an API-created pending disposition, start the 4473 the normal way; the sync links the Clover order to whichever pending disposition already holds that serial.
3. Commit in FastBound at handoff. Within seconds the Clover item is qty 0 and hidden.
4. `python -m ffl check` prints the exact `DisposeType` strings your account accepts. If "Sale" is not one of them, set `FASTBOUND_SALE_TYPE` to the right one.

## How the two systems are tied together

- Clover item **SKU** = `FB:<FastBound item id>` (the permanent link), **barcode/code** = serial (so the tag scans), name = `Manufacturer Model Caliber Type S/N serial`.
- FastBound disposition **externalId** = `CLV-<Clover order id>`, **invoiceNumber** = Clover order id.
- Local SQLite (`FFL_DB_PATH`) remembers the mapping, processed orders/events (so retries never double-post), saved Clover tokens and the attention list.

## Things the glue deliberately does not do

- Commit dispositions on payment, on a timer, or on a 4473 completion (waiting periods, denials, and ATF inspections all punish that).
- Create 4473s or buyer contacts from Clover customer data: the 4473 is the source of truth for the buyer, and FastBound owns it.
- Receive guns from Clover. Receiving starts in FastBound (or through Claude's `receive_firearms`, which writes FastBound first).
- Touch non-serialized inventory (ammo, accessories). Only items whose SKU starts with `FB:` are treated as firearms.

## Day-to-day commands

```
python -m ffl check            # health of both links + attention items
python -m ffl poll             # process new Clover orders now
python -m ffl reconcile        # full comparison report (JSON)
python -m ffl import-inventory # (re)list the book in Clover
```

`GET /health` shows configuration and the number of open attention items.
`GET /ffl/status?key=<FFL_MCP_SECRET>` shows flags, recent orders and the Clover webhook verification code.
