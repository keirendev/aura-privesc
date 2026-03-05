# Aura Protocol Reference

This document describes how Salesforce's Aura/Lightning framework structures HTTP requests, and how aura-privesc implements them. Any code that constructs Aura requests **must** follow this spec.

## Request Format

All Aura API calls are `POST` requests with `Content-Type: application/x-www-form-urlencoded`.

The body has four fields:

```
message=<raw JSON>&aura.context=<percent-encoded JSON>&aura.pageURI=/s/&aura.token=<percent-encoded token>
```

### Encoding Rules

| Field | Encoding |
|-------|----------|
| `message` | **Raw compact JSON** (NOT percent-encoded) |
| `aura.context` | Percent-encoded JSON |
| `aura.pageURI` | Raw `/s/` |
| `aura.token` | Percent-encoded |

**Critical:** The `message` field must NOT be URL-encoded. Salesforce rejects fully percent-encoded messages. The `aura.context` and `aura.token` fields MUST be percent-encoded.

### Message Envelope

The `message` field contains a JSON object with an `actions` array:

```json
{"actions":[{"id":"123;a","descriptor":"<action_descriptor>","callingDescriptor":"UNKNOWN","params":{...}}]}
```

**Requirements:**
- **Compact JSON** — use `separators=(",", ":")`, no spaces
- **Action ID** — must be `"123;a"` (not `"0"`)
- **callingDescriptor** — always `"UNKNOWN"`

### Action Descriptors

Defined in `config.py:DESCRIPTORS`. Two URI schemes:

- `aura://` — built-in Aura controllers (e.g., `aura://RecordUiController/ACTION$getObjectInfo`)
- `serviceComponent://` — service components (e.g., `serviceComponent://ui.force.components.controllers.lists...`)
- `apex://` — custom Apex controllers (e.g., `apex://MyController/ACTION$myMethod`)

### Context Object

The `aura.context` JSON includes:

```json
{"fwuid": "<framework_uid>", "mode": "PROD", "app": "siteforce:communityApp"}
```

**The `fwuid` is critical.** Without it, the server returns `clientOutOfSync` errors. It's discovered during Phase 1 from the community page HTML.

## getItems Parameters

The `getItems` action retrieves records from a Salesforce object. This is the **canonical parameter set** — use it everywhere:

```python
{
    "entityNameOrId": "<ObjectApiName>",
    "layoutType": "FULL",
    "pageSize": 100,
    "currentPage": 0,
    "useTimeout": False,
    "getCount": False,
    "enableRowActions": False,
}
```

**Do NOT use the old format** (`listViewApiName`, `getCount: True`, `pageSize: 10`). It causes internal server errors on many targets.

### Where getItems params are defined

These params are duplicated in multiple locations. **All must stay in sync:**

| Location | File | Notes |
|----------|------|-------|
| Record retrieval | `enumerator.py:get_records()` | Main enumeration |
| Validation | `validator.py:validate_object_result()` | Re-checks accessible objects |
| CRUD read | `crud.py:_try_get_items()` | Adds optional `listViewApiName` |
| CRUD fallback | `crud.py:read_records()` | Error path proof |
| SOQL check | `permissions.py:check_soql_capability()` | Uses `pageSize: 0` variant |
| Proof curl | `proof.py:proof_for_records()` | Static proof generation |
| HTML report JS | `output/html_output.py:_build_action_buttons()` | Interactive button params |

### Variations

- `crud.py:_try_get_items()` adds `"listViewApiName": list_view` alongside the standard params (for list view discovery)
- `permissions.py:check_soql_capability()` uses `pageSize: 0` (just checking capability, not fetching records)

## clientOutOfSync Recovery

When the client sends a request without a valid `fwuid`, the server may return a `clientOutOfSync` response. There are **two response formats**:

### Format 1: exceptionEvent (top-level)

```json
{
  "exceptionEvent": true,
  "event": {
    "descriptor": "aura:clientOutOfSync",
    "attributes": {"values": {"fwuid": "<new_fwuid>"}}
  }
}
```

### Format 2: coos (in actions array)

```json
{
  "actions": [
    {"id": "123;a", "state": "ERROR", "error": [{"message": "..."}]},
    {"coos": "This page has changes...", "id": "COOSE", "state": "warning"}
  ],
  "context": {"fwuid": "<new_fwuid>", "mode": "PROD", ...}
}
```

Both are handled in `client.py:request()`. The client extracts the new `fwuid` and retries once.

## Curl Proof Commands

Proof curls are generated in **two separate code paths** that must stay consistent:

1. **`proof.py:generate_curl()`** — Python-side proof generation (stored in scan results)
2. **`output/html_output.py:fireAura()`** — JavaScript-side generation (interactive report buttons)

Both must use:
- Action ID `"123;a"`
- Raw JSON message (not percent-encoded)
- Percent-encoded context and token
- Current getItems params format
