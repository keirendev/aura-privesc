# Architecture

## Source Files

### Core modules (`src/aura_privesc/`)

| File | Purpose |
|------|---------|
| `cli.py` | Click CLI, orchestrates all scan phases via `_run()` |
| `client.py` | `AuraClient` — async HTTP client implementing the Aura protocol envelope |
| `config.py` | Constants: `DESCRIPTORS`, `ENDPOINT_PATHS`, `STANDARD_OBJECTS` |
| `models.py` | Pydantic models: `ScanResult`, `ObjectResult`, `ApexResult`, `CrudPermissions` |
| `discovery.py` | Phase 1: endpoint probing, fwuid/context/app extraction from HTML |
| `permissions.py` | Phase 2: user identification, SOQL capability check, config object discovery |
| `enumerator.py` | Phase 3: `getObjectInfo` for CRUD metadata, `getItems` for records |
| `validator.py` | Phase 3 (cont.): re-validates findings to filter false positives |
| `apex.py` | Phase 4: discovers controllers from JS, tests via `call_apex` |
| `crud.py` | Record-level CRUD operations + automated write testing (`auto_crud_test_objects`) |
| `proof.py` | Generates reproducible curl commands for findings |
| `recon.py` | SF CLI recon subcommand: enumerate objects and `@AuraEnabled` Apex methods via Tooling API |
| `exceptions.py` | `AuraRequestError`, `ClientOutOfSyncError`, `InvalidSessionError`, `DiscoveryError` |

### Output modules (`src/aura_privesc/output/`)

| File | Purpose |
|------|---------|
| `html_output.py` | Self-contained HTML report with embedded CSS, JS, and interactive Aura action buttons |
| `json_output.py` | Machine-readable JSON output |
| `rich_output.py` | Terminal Rich-formatted tables |

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

Phase 5: Reporting (output/)
    ├─ Rich terminal tables
    ├─ JSON (--json)
    └─ HTML report with interactive buttons
```

## Key Patterns

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

Two code paths generate curl commands — **both must stay consistent**:

1. **`proof.py`** — Python-side, produces curl strings stored in `ObjectResult.proof` / `ObjectResult.proof_records`
2. **`output/html_output.py`** — JavaScript `fireAura()` function, generates curls when user clicks report buttons

### Validation (validator.py)

Re-calls `getObjectInfo` to confirm the finding is real. If the object is readable (getItems returned records), also calls `getItems` to confirm record-level access. Strips `proof_records` on getItems failure but keeps the object as accessible if `getObjectInfo` succeeds.

### Data flow

```
AuraClient → enumerator/apex → ObjectResult/ApexResult → ScanResult → output renderers
                                      ↑
                                 proof.py (curl strings)
```

`ScanResult` is the top-level Pydantic model passed to all output renderers (Rich, JSON, HTML).
