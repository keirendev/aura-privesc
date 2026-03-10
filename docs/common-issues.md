# Common Issues & Troubleshooting

## Curl proofs from report don't work

**Symptoms:** Clicking a button in the HTML report copies a curl command, but running it returns an error or no data.

**Common causes:**

### 1. Expired session

The `sid` cookie and `aura.token` in the proof are captured at scan time. If the session has expired, the curl will fail with HTTP 401 or an Aura `invalidSession` error.

**Fix:** Re-run the scan with a fresh session.

### 2. Missing fwuid

If the `aura.context` in the proof doesn't include `fwuid`, the server returns `clientOutOfSync`:

```json
{"actions":[{"state":"ERROR","error":[{"message":"An internal server error has occurred"}]}],
 ...,"coos":"This page has changes since the last refresh..."}
```

**Fix:** The client now extracts fwuid from response context and keeps it updated. If proofs still lack fwuid, check that Phase 1 discovery is finding it from the HTML page.

### 3. Outdated protocol format

If the curl uses old getItems params (`listViewApiName`, `getCount:true`, `pageSize:10`) or old action ID (`"id":"0"`), it will fail on many targets.

**Correct format** — see [Aura Protocol Reference](aura-protocol.md):
- Action ID: `"123;a"`
- getItems params: `layoutType`, `pageSize:100`, `currentPage:0`, `useTimeout:false`, `getCount:false`, `enableRowActions:false`

### 4. Protocol details are duplicated

Curl commands are generated in **two separate code paths**:
- `proof.py:generate_curl()` — produces proof strings stored in scan results
- `output/html_output.py:fireAura()` — JavaScript in the HTML report builds curls client-side

**If you update protocol details (action ID, params, encoding), you MUST update both.** Also check `_build_action_buttons()` in html_output.py for hardcoded params in button onclick handlers.

## HTTP/2 proxy errors (Burp Suite)

**Symptoms:** Scan returns zero results when using `--proxy` with Burp Suite. Verbose output (`-v`) shows:

```
RemoteProtocolError("illegal status line: bytearray(b'HTTP/2 200 OK')")
```

**Cause:** Burp Suite negotiates HTTP/2 with the backend server but fails to properly convert the response to HTTP/1.1 for the client.

**Fix:** The client enables HTTP/2 natively via the `h2` package so it can speak HTTP/2 directly through Burp. Ensure `h2` is installed:

```bash
pip install h2
```

This is included as a dependency in `pyproject.toml` and installed automatically with `pip install -e .`.

## Scan returns zero results

**Symptoms:** All phases complete but no accessible objects or callable Apex methods found.

**Possible causes:**

1. **Session expired** — authenticated scans need a valid `sid` and `aura.token`. Re-authenticate.
2. **fwuid not discovered** — check verbose output (`-v`) for discovery phase details.
3. **clientOutOfSync not handled** — the client handles both `exceptionEvent` and `coos` response formats. If a new format appears, check `client.py:request()`.
4. **Target has no exposed objects** — the target may genuinely have no accessible Aura endpoints for the current user context.

## Protocol changes checklist

When updating Aura protocol details (action ID, params, encoding), update ALL of these locations:

### Action ID (`"123;a"`)
- [ ] `client.py:_build_action()` — default parameter
- [ ] `proof.py:generate_curl()` — hardcoded in message JSON
- [ ] `output/html_output.py:fireAura()` — JavaScript function

### getItems params
- [ ] `enumerator.py:get_records()`
- [ ] `validator.py:validate_object_result()`
- [ ] `crud.py:_try_get_items()` (keeps optional `listViewApiName`)
- [ ] `crud.py:read_records()` fallback
- [ ] `permissions.py:check_soql_capability()` (uses `pageSize:0` variant)
- [ ] `proof.py:proof_for_records()`
- [ ] `output/html_output.py:_build_action_buttons()` — getItems button onclick

### executeGraphQL params
- [ ] `graphql.py:_graphql_params()` — builds `queryInput` with `operationName`, `query`, `variables`
- [ ] `graphql.py:_build_count_query()` — totalCount query format
- [ ] `graphql.py:_build_fields_query()` — objectInfos introspection query format
- [ ] `graphql.py:_build_record_query()` — record fetch with cursor pagination
- [ ] `graphql.py:_build_filtered_query()` — filtered record queries with where clauses
- [ ] `graphql.py:_build_relationship_query()` — relationship traversal queries
- [ ] `proof.py:_graphql_params()` / `_build_count_query()` / `_build_fields_query()` — duplicated for proof generation
- [ ] `proof.py:_build_record_query()` / `_build_filtered_record_query()` — duplicated for proof generation
- [ ] `graphql.py:_build_schema_query()` / `_build_type_query()` — __schema/__type introspection queries
- [ ] `graphql.py:_build_create_mutation()` / `_build_delete_mutation()` — UIAPI mutation queries
- [ ] `proof.py:_build_schema_query()` / `_build_type_query()` — duplicated for proof generation
- [ ] `proof.py:_build_create_mutation()` / `_build_delete_mutation()` — duplicated for proof generation
- [ ] `output/html_output.py:_build_graphql_table()` — Count button onclick handler
- [ ] `frontend/src/lib/curl.ts:buildFireAuraCurl()` — TypeScript curl generation in React UI

## GraphQL not available

**Symptoms:** Phase 5 reports "executeGraphQL not available on this target".

**Cause:** The `aura://RecordUiController/ACTION$executeGraphQL` descriptor is not exposed on all Salesforce instances. Some orgs disable it or the guest user profile may not have access.

**Fix:** This is expected on some targets. Use `--skip-graphql` to skip the phase and avoid the probe request.

## GraphQL OPERATION_TOO_LARGE

**Symptoms:** GraphQL count queries fail with `OPERATION_TOO_LARGE` error.

**Cause:** Too many objects in a single batched query. The scanner uses 10 objects per batch, but some targets have lower limits.

**Fix:** The scanner automatically retries failed batches individually. If this happens frequently, the counts will still be retrieved but more slowly.

### Message encoding
- [ ] `client.py:_encode_form()` — raw message, percent-encoded context/token
- [ ] `client.py:_build_message()` — compact JSON separators
- [ ] `proof.py:generate_curl()` — raw message in curl body
- [ ] `output/html_output.py:fireAura()` — JavaScript: `msg` not `encodeURIComponent(msg)`
- [ ] `frontend/src/lib/curl.ts:buildFireAuraCurl()` — TypeScript port uses same encoding

### Input validation (GraphQL)
- [ ] `graphql.py:_validate_api_name()` — `_SAFE_API_NAME` regex for object/field names
- [ ] `proof.py:_validate_api_name()` — same regex, duplicated

## Web UI troubleshooting

### Web UI doesn't load

**Symptoms:** `aura-privesc serve` starts but browser shows a placeholder page.

**Fix:** Build the React frontend:
```bash
cd frontend && npm install && npm run build
```

### Port already in use

**Fix:** Use a different port: `aura-privesc serve --port 9999`

### Non-localhost access

By default, the web UI binds to `127.0.0.1` only. To allow network access:
```bash
aura-privesc serve --host 0.0.0.0
```

**Warning:** The API has no authentication. Only bind to non-localhost on trusted networks.
