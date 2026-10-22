# tacticool-ai

Backend for Tacti-Cool Gun (tacticoolgun.com).

- **Bam Bam** — the website chat assistant (`/api/chat`, `/widget.js`). Searches WooCommerce live and answers with OpenAI.
- **Clover + FastBound glue** (`ffl/`) — keeps the Clover register and the FastBound bound book / e4473 in step, and exposes an MCP server so Claude can run the firearms counter. Setup and daily workflow: [docs/CLOVER_FASTBOUND_SETUP.md](docs/CLOVER_FASTBOUND_SETUP.md).

## Run locally

```
pip install -r requirements-dev.txt
cp .env.example .env        # fill in keys
uvicorn main:app --reload
python -m pytest
```

## Deploy

Railway (`railway.toml` / `Procfile`): `uvicorn main:app --host 0.0.0.0 --port $PORT`.
Environment variables are listed in `.env.example`. Mount a volume and point `FFL_DB_PATH` at it so the sync state survives deploys.

## Useful commands

```
python -m ffl check               # verify FastBound + Clover connections
python -m ffl register-webhook    # subscribe FastBound events to this app
python -m ffl import-inventory    # list every gun on the book in Clover
python -m ffl reconcile           # compare both systems
python -m ffl mcp                 # Claude MCP server over stdio
```
