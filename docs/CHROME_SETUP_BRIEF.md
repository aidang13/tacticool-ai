# Brief for a Claude session that can drive Chrome

Paste this whole file as the first message of a Claude session that has the
Claude in Chrome extension connected (Claude Desktop or Cowork on the Mac/PC
where Chrome is logged into Clover and FastBound). It is self-contained.

---

## Who you are working for

Aidan runs Tacti-Cool Gun (tacticoolgun.com), a firearms retailer. He is moving from
Bravo POS + e4473 to **Clover POS + FastBound** and wants the new pair to feel like one
system. The integration code is already written and pushed to the GitHub repo
`aidang13/tacticool-ai`, branch `claude/clover-pos-claude-connection-wmy861`. Your job is
the **setup**: collect credentials from the two web dashboards, put them in Railway,
deploy, and run the verification commands. Read `docs/CLOVER_FASTBOUND_SETUP.md` in that
repo if you need more background than this brief gives.

## Ground rules

- **Never type a credential into the chat.** Copy from the dashboard, paste straight into
  Railway's variable editor. If you need to tell Aidan a value exists, say "copied" not the value.
- **Read-only in FastBound.** Do not create, edit, commit or delete any acquisition,
  disposition, 4473 or item. Generating the API key is the only write you make there.
- **Read-only in Clover inventory and orders.** Do not ring up, refund or delete anything.
  Creating an API token and turning on stock tracking are the only changes you make.
- Chrome tabs for Clover and FastBound are already logged in. Use `tabs_context_mcp` first,
  then open your own new tab for each site rather than taking over Aidan's tabs.
- If a page blocks you (2FA prompt, permission dialog, menu that does not exist), stop and ask
  Aidan. Do not guess around it.

## Step 1 — FastBound (https://cloud.fastbound.com)

Collect three values:

1. **Account number.** After login the URL looks like `https://cloud.fastbound.com/12345/...`.
   The number after the host is `FASTBOUND_ACCOUNT`.
2. **API key.** Settings → look for *Generate API Key* (or *API Key* under account settings).
   Generate it and copy it once. It is shown once. This is `FASTBOUND_API_KEY`.
3. **Audit user.** The email Aidan is logged in with is `FASTBOUND_AUDIT_USER`.

Also check, and report back without changing anything:
- Settings → is the electronic 4473 (e4473) enabled on the account?
- Is there a page listing valid *Disposition types*? If you can see them, note whether
  one is literally called `Sale`. (The sync uses `Sale` by default via `FASTBOUND_SALE_TYPE`.)

## Step 2 — Clover (https://www.clover.com/dashboard)

Collect:

1. **Merchant ID.** Account & Setup → Business Information (it is also in the dashboard URL).
   This is `CLOVER_MERCHANT_ID`.
2. **API token.** Account & Setup → *API Tokens* (under Business Operations on some dashboards).
   Click *Create New Token*. Name it `tacticool-sync`. Tick **read and write** for:
   Inventory, Orders, Merchant, Customers, Payments. Create it and copy it once.
   This is `CLOVER_ACCESS_TOKEN`.
   - If the *API Tokens* menu does not exist, stop and tell Aidan. The fallback is a Clover
     developer app with OAuth (`CLOVER_APP_ID` / `CLOVER_APP_SECRET`, redirect URL
     `https://<railway app domain>/ffl/clover/oauth/callback`), and he should decide before you
     create anything on https://www.clover.com/developers.
3. **Stock tracking.** Inventory → Settings (or *Item Availability* / *Stock*). Make sure
   *Track stock* / *Manage stock* is turned ON. Without it a sale will not drop a gun to qty 0.

## Step 3 — Railway (https://railway.app)

Open the `tacticool-ai` project → the service → **Variables**. Add:

| Variable | Value |
|---|---|
| `FASTBOUND_ACCOUNT` | from step 1 |
| `FASTBOUND_API_KEY` | from step 1 |
| `FASTBOUND_AUDIT_USER` | from step 1 |
| `FASTBOUND_SALE_TYPE` | `Sale` (change later if `check` says otherwise) |
| `CLOVER_MERCHANT_ID` | from step 2 |
| `CLOVER_ACCESS_TOKEN` | from step 2 |
| `CLOVER_FIREARMS_CATEGORY` | `Firearms` |
| `FFL_PUBLIC_URL` | the service's public domain, e.g. `https://tacticool-ai.up.railway.app` (Settings → Networking) |
| `FFL_MCP_SECRET` | a long random string (40+ chars). Generate one; do not reuse any other secret |
| `FFL_DB_PATH` | `/data/ffl.sqlite3` |
| `FFL_POLL_SECONDS` | `60` |

Then **Settings → Volumes → add a volume** mounted at `/data` (so the sync database survives
deploys). Finally make sure the service deploys from branch
`claude/clover-pos-claude-connection-wmy861` (Settings → Source), or ask Aidan to merge that
branch to main first. Trigger a deploy and wait for it to be healthy
(`GET https://<domain>/health` should return JSON with `"fastbound_configured": true` and
`"clover_configured": true`).

## Step 4 — Verify from a shell with the same variables

Use the Railway service shell (or a terminal on Aidan's machine with the same variables
exported and the repo checked out). Run in order:

```
python -m ffl check
```
Expect: "connected to account …" for FastBound, "connected to merchant …" for Clover, and a
printed list of `AcquireType` / `DisposeType` / `ItemType` values. If `Sale` is not in
`DisposeType`, set `FASTBOUND_SALE_TYPE` in Railway to the closest value and redeploy.

```
python -m ffl register-webhook
```
Expect: it prints a **signing secret once**. Put it in Railway as
`FASTBOUND_WEBHOOK_SECRET` and redeploy. (If it says "updated webhook", the hook already
existed and the secret was issued earlier.)

```
python -m ffl import-inventory
```
Expect: a JSON summary with `created` = number of guns on the FastBound book and no `errors`.
Then look in the Clover dashboard → Inventory: a **Firearms** category with one item per
serial, qty 1, barcode = serial. Report the count to Aidan.

## Step 5 — Connect Claude to the counter

In claude.ai → Settings → Connectors → *Add custom connector*, name `Tacti-Cool FFL`, URL
`https://<railway domain>/mcp/<FFL_MCP_SECRET>`. Then test in a chat: "what firearms are in
stock?" and "anything pending for 4473?". Both should answer from live FastBound data.

## Report back to Aidan

A short list: which values were set, the inventory count imported, anything that did not
exist or did not match this brief (menu names differ between dashboards; that is expected),
and the one thing he must still do himself: ring up one real gun in Clover and confirm the
pending disposition appears in FastBound, start the 4473 from it, and commit at handoff.

## Do not

- Commit, lock, delete or edit anything in FastBound's A&D records or 4473s.
- Sell, refund or delete anything in Clover.
- Paste any key, token or secret into chat, a document, or a commit.
- Create a Clover developer app or change Clover permissions without Aidan's say-so.
