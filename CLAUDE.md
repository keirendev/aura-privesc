# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

aura-privesc is a Salesforce Aura/Lightning privilege escalation scanner. It discovers exposed Aura endpoints, enumerates object permissions, tests Apex controllers, and optionally validates findings with record-level CRUD operations. It includes a React + FastAPI web dashboard and a CLI. It's a security research/pentesting tool.

## Documentation

Detailed docs live in `docs/`:
- **`docs/aura-protocol.md`** — Aura protocol spec (encoding rules, message format, getItems params, clientOutOfSync recovery). **Read this before changing any request format.**
- **`docs/architecture.md`** — source file map, scan phases, key patterns
- **`docs/common-issues.md`** — troubleshooting guide with protocol changes checklist

## Development Commands

```bash
# Install in editable mode (use the project venv)
pip install -e .

# Run the web UI (default)
aura-privesc
# Or: aura-privesc serve --no-browser --port 8888

# Run a CLI scan
aura-privesc scan -u https://target.force.com [options]

# Build the React frontend
cd frontend && npm install && npm run build

# Frontend dev mode (proxies /api to localhost:8888)
cd frontend && npm run dev

# Syntax-check all source files
python3 -m py_compile src/aura_privesc/<file>.py

# Import smoke test
.venv/bin/python -c "from aura_privesc.engine import ScanEngine, ScanConfig"
.venv/bin/python -c "from aura_privesc.web.app import create_app"
```

There are no tests, linter, or CI configured yet. Validation is manual against live Salesforce targets.

## Architecture

### Scan Engine (`engine.py`)

`ScanEngine` orchestrates all scan phases, decoupled from output. Takes a `ScanConfig` dataclass and a `ProgressCallback`. Used by both the CLI and the web UI's `JobManager`.

### Scan Phases

1. **Discovery** (`discovery.py`) — probes candidate endpoint paths, extracts fwuid/context/app from community HTML
2. **User context** (`permissions.py`) — identifies current user, checks SOQL capability, discovers config objects. Also runs REST API checks (`rest_api.py`) to detect the "API Enabled" profile permission via `/services/data/` endpoints on the CRM domain
3. **Object enumeration** (`enumerator.py`) — calls `getObjectInfo` for CRUD metadata, `getItems` for records, then validates findings (`validator.py`) to filter false positives
3b. **CRUD write testing** (`crud.py:auto_crud_test_objects`) — automatically tests create/update/delete on writable objects to prove access
4. **Apex testing** (`apex.py`) — discovers controllers from JS files, tests each with `call_apex`, classifies as CALLABLE/DENIED/NOT_FOUND
5. **GraphQL enumeration** (`graphql.py`) — probes `executeGraphQL`, batches totalCount queries, introspects field names/types, fetches records with cursor pagination, supports filtered queries and relationship traversal
6. **Output** — Rich terminal tables (`output/rich_output.py`), JSON (`output/json_output.py`), HTML report (`output/html_output.py`), or web UI

### Web UI (`web/`)

- **`app.py`** — FastAPI app factory, CORS (localhost only), SPA catch-all
- **`api.py`** — REST endpoints: scans CRUD, recons CRUD, presets, live GraphQL queries, cancel endpoints
- **`db.py`** — SQLAlchemy async SQLite at `~/.aura-privesc/scans.db` (0600 permissions). Models: `Scan`, `Recon`
- **`jobs.py`** — `JobManager` runs scan and recon jobs as asyncio tasks, updates DB with progress, supports cancellation
- **`schemas.py`** — Pydantic request/response schemas for scans and recons
- **`static/`** — built React app (from `cd frontend && npm run build`)

### Frontend (`frontend/`)

React 18 + Vite + TypeScript + Tailwind CSS 3 + React Router v7 + TanStack React Query v5.

- **Routing:** `/` (dashboard), `/scan/new`, `/scan/:id`, `/history`, `/recon`
- **Polling:** React Query `refetchInterval` polls scan and recon status every 2s
- **Theming:** Dark mode default (navy/cyan palette), light mode toggle
- **Curl generation:** `lib/curl.ts` ports `fireAura()` from html_output.py

### Key patterns

- **AuraClient** (`client.py`) is the async HTTP client wrapping the Aura protocol envelope. All API calls go through `client.request()`, which handles `clientOutOfSync` fwuid recovery (both `exceptionEvent` and `coos` formats) and concurrency via semaphore.
- **Action descriptors** live in `config.py:DESCRIPTORS` — named mappings to Aura service component URIs.
- **Models** (`models.py`) are all Pydantic `BaseModel`. `ScanResult` is the top-level container passed to all output renderers.
- **Proof generation** has three code paths that **must stay in sync**:
  - `proof.py` — Python-side curl generation (stored in scan results)
  - `output/html_output.py:fireAura()` — JavaScript-side curl generation (interactive report buttons)
  - `frontend/src/lib/curl.ts:buildFireAuraCurl()` — TypeScript curl generation (React web UI)
- **Input validation** — GraphQL object/field names validated with `_SAFE_API_NAME` regex in `graphql.py` and `proof.py`
- **Ephemeral records** — `sample_records` and `record_data` stripped before SQLite persistence to reduce PII exposure

### Aura protocol essentials

See `docs/aura-protocol.md` for the full spec. Key rules:

- **Message encoding:** `message` field is raw compact JSON (not percent-encoded). `aura.context` and `aura.token` are percent-encoded.
- **Action ID:** `"123;a"` (not `"0"`)
- **Compact JSON:** `_build_message()` uses `separators=(",", ":")` — no spaces
- **getItems params:** `layoutType:"FULL"`, `pageSize:100`, `currentPage:0`, `useTimeout:false`, `getCount:false`, `enableRowActions:false` (no `listViewApiName` except in crud.py list view discovery)
- **executeGraphQL params:** `queryInput` with `operationName`, `query`, `variables:{}`. Query helpers are duplicated in `graphql.py` and `proof.py`
- **Protocol details are duplicated** in 8+ locations — see `docs/common-issues.md` for the full checklist of files to update

### Dependencies

**Python:** click, httpx, h2, rich, pydantic, fastapi, uvicorn, sqlalchemy, aiosqlite. Python >=3.11.
**Frontend:** React 18, Vite, TypeScript, Tailwind CSS 3, React Router v7, TanStack React Query v5, Lucide React, Sonner. Node.js 18+.

No Jinja2 — the HTML report uses string formatting with `html.escape`. The `h2` package enables HTTP/2 in httpx, which is required for proxies like Burp Suite that negotiate HTTP/2 with backend servers.

## Important: No target data in repo

Never commit target-specific data (session IDs, tokens, hostnames, recon output). The `recon/` directory and `aura-report-*.html` files are gitignored.
