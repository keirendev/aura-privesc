# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

aura-privesc is a Salesforce Aura/Lightning privilege escalation scanner. It discovers exposed Aura endpoints, enumerates object permissions, tests Apex controllers, and optionally validates findings with record-level CRUD operations. It's a security research/pentesting tool.

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
3. **Object enumeration** (`enumerator.py`) — calls `getObjectInfo` for CRUD metadata, `getItems` for record counts, then validates findings (`validator.py`) to filter false positives
4. **Apex testing** (`apex.py`) — discovers controllers from JS files, tests each with `call_apex`, classifies as CALLABLE/DENIED/NOT_FOUND
5. **Interactive CRUD validation** (`interactive.py`, opt-in `--interactive`) — walks user through per-object read/create/update/delete with Rich prompts
6. **Output** — Rich terminal tables (`output/rich_output.py`), JSON (`output/json_output.py`), or HTML report (`output/html_output.py`)

### Key patterns

- **AuraClient** (`client.py`) is the async HTTP client wrapping the Aura protocol envelope (message + aura.context + aura.token). All API calls go through `client.request()`, which handles `clientOutOfSync` fwuid recovery and concurrency via semaphore.
- **Action descriptors** live in `config.py:DESCRIPTORS` — named mappings to Aura service component URIs.
- **Models** (`models.py`) are all Pydantic `BaseModel`. `ScanResult` is the top-level container passed to all output renderers.
- **Proof generation** (`proof.py`) builds reproducible curl commands for every finding.
- Risk classification (`enumerator.py:classify_risk`) combines object sensitivity (CRITICAL_OBJECTS/HIGH_SENSITIVITY_OBJECTS sets in config) with CRUD permission flags.

### Dependencies

click, httpx, rich, pydantic. Python >=3.11. No Jinja2 — the HTML report uses string formatting with `html.escape`.
