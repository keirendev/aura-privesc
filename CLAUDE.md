# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

aura-privesc is a Salesforce Aura/Lightning privilege escalation scanner. It discovers exposed Aura endpoints, enumerates object permissions, tests Apex controllers, and optionally validates findings with record-level CRUD operations. It's a security research/pentesting tool.

## Documentation

Detailed docs live in `docs/`:
- **`docs/aura-protocol.md`** — Aura protocol spec (encoding rules, message format, getItems params, clientOutOfSync recovery). **Read this before changing any request format.**
- **`docs/architecture.md`** — source file map, scan phases, key patterns
- **`docs/common-issues.md`** — troubleshooting guide with protocol changes checklist

## Development Commands

```bash
# Install in editable mode (use the project venv)
pip install -e .

# Run the tool
aura-privesc -u https://target.force.com [options]
# Or via module
python -m aura_privesc -u https://target.force.com [options]

# Syntax-check all source files
python3 -m py_compile src/aura_privesc/<file>.py

# Import smoke test
.venv/bin/python -c "from aura_privesc.cli import main"
```

There are no tests, linter, or CI configured yet. Validation is manual against live Salesforce targets.

## Architecture

The scan runs in phases orchestrated by `cli.py:_run()`:

1. **Discovery** (`discovery.py`) — probes candidate endpoint paths, extracts fwuid/context/app from community HTML
2. **User context** (`permissions.py`) — identifies current user, checks SOQL capability, discovers config objects
3. **Object enumeration** (`enumerator.py`) — calls `getObjectInfo` for CRUD metadata, `getItems` for records, then validates findings (`validator.py`) to filter false positives
3b. **CRUD write testing** (`crud.py:auto_crud_test_objects`) — automatically tests create/update/delete on writable objects to prove access
4. **Apex testing** (`apex.py`) — discovers controllers from JS files, tests each with `call_apex`, classifies as CALLABLE/DENIED/NOT_FOUND
5. **Output** — Rich terminal tables (`output/rich_output.py`), JSON (`output/json_output.py`), or HTML report (`output/html_output.py`)

### Key patterns

- **AuraClient** (`client.py`) is the async HTTP client wrapping the Aura protocol envelope. All API calls go through `client.request()`, which handles `clientOutOfSync` fwuid recovery (both `exceptionEvent` and `coos` formats) and concurrency via semaphore.
- **Action descriptors** live in `config.py:DESCRIPTORS` — named mappings to Aura service component URIs.
- **Models** (`models.py`) are all Pydantic `BaseModel`. `ScanResult` is the top-level container passed to all output renderers.
- **Proof generation** has two code paths that **must stay in sync**:
  - `proof.py` — Python-side curl generation (stored in scan results)
  - `output/html_output.py:fireAura()` — JavaScript-side curl generation (interactive report buttons)
- **Automated CRUD testing** (`crud.py:auto_crud_test`) attempts create/update/delete on writable objects. Results are shown inline in the objects table (proven/failed/not attempted).

### Aura protocol essentials

See `docs/aura-protocol.md` for the full spec. Key rules:

- **Message encoding:** `message` field is raw compact JSON (not percent-encoded). `aura.context` and `aura.token` are percent-encoded.
- **Action ID:** `"123;a"` (not `"0"`)
- **Compact JSON:** `_build_message()` uses `separators=(",", ":")` — no spaces
- **getItems params:** `layoutType:"FULL"`, `pageSize:100`, `currentPage:0`, `useTimeout:false`, `getCount:false`, `enableRowActions:false` (no `listViewApiName` except in crud.py list view discovery)
- **Protocol details are duplicated** in 7+ locations — see `docs/common-issues.md` for the full checklist of files to update

### Dependencies

click, httpx, h2, rich, pydantic. Python >=3.11. No Jinja2 — the HTML report uses string formatting with `html.escape`. The `h2` package enables HTTP/2 in httpx, which is required for proxies like Burp Suite that negotiate HTTP/2 with backend servers.

## Important: No target data in repo

Never commit target-specific data (session IDs, tokens, hostnames, recon output). The `recon/` directory and `aura-report-*.html` files are gitignored.
