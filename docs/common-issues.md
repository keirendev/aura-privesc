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

### Message encoding
- [ ] `client.py:_encode_form()` — raw message, percent-encoded context/token
- [ ] `client.py:_build_message()` — compact JSON separators
- [ ] `proof.py:generate_curl()` — raw message in curl body
- [ ] `output/html_output.py:fireAura()` — JavaScript: `msg` not `encodeURIComponent(msg)`
