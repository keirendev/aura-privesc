# Architecture

## Source Files

### Core modules (`src/aura_privesc/`)

| File | Purpose |
|------|---------|
| `engine.py` | `ScanEngine` — decoupled scan orchestration with progress callbacks |
| `cli.py` | Click CLI: `scan`, `recon`, and `serve` commands |
| `client.py` | `AuraClient` — async HTTP client implementing the Aura protocol envelope |
| `config.py` | Constants: `DESCRIPTORS`, `ENDPOINT_PATHS`, `STANDARD_OBJECTS` |
| `models.py` | Pydantic models: `ScanResult`, `ObjectResult`, `ApexResult`, `GraphQLRecordPage`, etc. |
| `discovery.py` | Phase 1: endpoint probing, fwuid/context/app extraction from HTML |
| `permissions.py` | Phase 2: user identification, SOQL capability check, config object discovery |
| `enumerator.py` | Phase 3: `getObjectInfo` for CRUD metadata, `getItems` for records |
| `validator.py` | Phase 3 (cont.): re-validates findings to filter false positives |
| `apex.py` | Phase 4: discovers controllers from JS, tests via `call_apex` |
| `crud.py` | Record-level CRUD operations + automated write testing (`auto_crud_test_objects`) |
| `graphql.py` | Phase 5: GraphQL enumeration — record counts, field introspection, record fetching with pagination, filtered queries, relationship traversal |
| `proof.py` | Generates reproducible curl commands for findings (including GraphQL record/filtered proofs) |
| `recon.py` | SF CLI recon subcommand: enumerate objects and `@AuraEnabled` Apex methods via Tooling API |
| `exceptions.py` | `AuraRequestError`, `ClientOutOfSyncError`, `InvalidSessionError`, `DiscoveryError` |

### Output modules (`src/aura_privesc/output/`)

| File | Purpose |
|------|---------|
| `html_output.py` | Self-contained HTML report with embedded CSS, JS, and interactive Aura action buttons |
| `json_output.py` | Machine-readable JSON output |
| `rich_output.py` | Terminal Rich-formatted tables |

### Web UI (`src/aura_privesc/web/`)

| File | Purpose |
|------|---------|
| `app.py` | FastAPI app factory, static file serving, SPA catch-all |
| `api.py` | REST API endpoints (scans CRUD, presets, live GraphQL) |
| `db.py` | SQLAlchemy models + async SQLite session |
| `jobs.py` | `JobManager` — runs scans as asyncio tasks, updates DB with progress |
| `schemas.py` | Pydantic request/response schemas for the REST API |
| `static/` | Built React app (populated by `cd frontend && npm run build`) |

### Frontend (`frontend/`)

React + Vite + TypeScript + Tailwind CSS dashboard.

| Directory | Purpose |
|-----------|---------|
| `src/api/` | API client (`client.ts`) and TypeScript types (`types.ts`) |
| `src/hooks/` | React Query hooks: `useJob`, `useScanResult`, `useScans`, `useTheme` |
| `src/components/layout/` | `AppShell`, `Sidebar`, `ThemeToggle` |
| `src/components/scan-form/` | `ScanForm`, `PresetSelector`, `AdvancedOptions` |
| `src/components/progress/` | `ScanProgress`, `PhaseIndicator` |
| `src/components/results/` | `ExecutiveSummary`, `ObjectsTable`, `ApexTable`, `GraphQLTable` |
| `src/components/history/` | `ScanHistory` |
| `src/components/shared/` | `Badge`, `CrudIndicator`, `CopyButton`, `SearchInput` |
| `src/pages/` | `DashboardPage`, `NewScanPage`, `ScanPage`, `ScanHistoryPage` |
| `src/lib/` | `curl.ts` (port of `fireAura()` from html_output.py) |

## Scan Phases

```
Phase 1: Discovery (discovery.py)
    └─ Probe endpoints, extract fwuid/context/app from community HTML

Phase 2: User Context (permissions.py)
    └─ Identify user, check SOQL, discover config objects

Phase 3: Object Enumeration (enumerator.py + validator.py)
    ├─ getObjectInfo → CRUD permissions
    ├─ getItems → records (readable = records returned)
    └─ validate_object_result() → filter false positives

Phase 3b: CRUD Write Testing (crud.py)
    └─ auto_crud_test_objects() → create/update/delete on writable objects

Phase 4: Apex Testing (apex.py)
    ├─ Extract controllers from community JS files
    └─ Test each method → CALLABLE / DENIED / NOT_FOUND

Phase 5: GraphQL Enumeration (graphql.py)
    ├─ Probe executeGraphQL availability
    ├─ Batch totalCount queries (10 objects/batch)
    ├─ Field introspection via objectInfos (100 objects/batch)
    ├─ Record fetching with cursor pagination (get_graphql_records)
    ├─ Filtered queries with where clauses (get_graphql_filtered_records)
    └─ Relationship traversal (get_graphql_relationships)

Phase 6: Reporting (output/)
    ├─ Rich terminal tables
    ├─ JSON (--json)
    └─ HTML report with interactive buttons
```

## Key Patterns

### ScanEngine (engine.py)

Decouples scan orchestration from output. `ScanConfig` holds all scan parameters. `ScanEngine.run()` executes all phases, calling a `ProgressCallback` instead of printing to the terminal. Both the CLI (`cli.py:_run_cli_scan`) and the web UI (`jobs.py:JobManager`) use `ScanEngine`.

### AuraClient (client.py)

Central async HTTP client. All Aura API calls go through `client.request(descriptor, params)`.

- **Concurrency** — bounded by asyncio semaphore (default 5)
- **HTTP/2** — enabled automatically when `h2` is installed, required for proxies like Burp Suite
- **fwuid recovery** — handles both `exceptionEvent` and `coos`-style `clientOutOfSync`
- **Session management** — optional `sid` cookie for authenticated scans
- **Proxy/TLS** — configurable via `--proxy` and `--insecure` flags

### Protocol encoding (client.py:_encode_form)

See [Aura Protocol Reference](aura-protocol.md) for the encoding spec. The `message` field is raw compact JSON; everything else is percent-encoded.

### Proof generation

Three code paths generate curl commands — **all must stay consistent**:

1. **`proof.py`** — Python-side, produces curl strings stored in scan results
2. **`output/html_output.py`** — JavaScript `fireAura()` function, generates curls when user clicks report buttons
3. **`frontend/src/lib/curl.ts`** — TypeScript port of `fireAura()` for the React web UI

### Input validation (GraphQL)

Object names are validated against `_SAFE_API_NAME` regex before interpolation into GraphQL query strings (in both `graphql.py` and `proof.py`).

### Web UI architecture

- **FastAPI** backend serves REST API at `/api/*` and the built React SPA
- **SQLite** stores scan history at `~/.aura-privesc/scans.db` (0600 permissions)
- **Single scan at a time** enforced at API layer (409 Conflict)
- **Ephemeral record data** — `sample_records` and `record_data` stripped before SQLite persistence
- **Polling** — React frontend polls `/api/scans/{id}/status` every 2s during active scans
- **Live GraphQL** — completed scan credentials can be used for interactive GraphQL queries via `/api/graphql/*`

### Data flow

```
CLI:     ScanConfig → ScanEngine → ScanResult → output renderers
Web UI:  POST /api/scans → JobManager → ScanEngine → DB → GET /api/scans/{id}

AuraClient → enumerator/apex → ObjectResult/ApexResult → ScanResult
                                      ↑
                                 proof.py (curl strings)
```

`ScanResult` is the top-level Pydantic model passed to all output renderers (Rich, JSON, HTML) and serialized to the database (with records stripped).
