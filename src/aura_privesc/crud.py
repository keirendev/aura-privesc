"""Record-level CRUD operations via Aura — read, create, update, delete."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .client import AuraClient
from .config import DESCRIPTORS
from .models import CrudOperationResult
from .proof import generate_curl

logger = logging.getLogger(__name__)

# Safe test values per Salesforce field data type
_TYPE_DEFAULTS: dict[str, Any] = {
    "String": "AuraPrivescTest",
    "Email": "aura-privesc-test@example.invalid",
    "Phone": "+15550000000",
    "Url": "https://example.invalid",
    "Boolean": False,
    "Currency": 0.01,
    "Double": 0.0,
    "Integer": 0,
    "Int": 0,
    "Percent": 0,
    "TextArea": "AuraPrivescTest",
    "Picklist": None,  # handled separately — needs picklistValues
}


def extract_required_fields(obj_info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Parse getObjectInfo fields dict to find required + createable fields.

    Returns {fieldName: {"type": dataType, "required": bool, "createable": bool, ...}}.
    """
    fields_raw = obj_info.get("fields", {})
    result: dict[str, dict[str, Any]] = {}

    for name, meta in fields_raw.items():
        if not isinstance(meta, dict):
            continue
        createable = meta.get("createable", False)
        required = meta.get("required", False)
        data_type = meta.get("dataType", "String")

        if required and createable:
            result[name] = {
                "type": data_type,
                "required": required,
                "createable": createable,
                "picklistValues": meta.get("picklistValues"),
                "length": meta.get("length"),
                "label": meta.get("label", name),
            }

    return result


def build_test_values(required_fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Generate safe dummy values for each required field based on data type."""
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    values: dict[str, Any] = {}

    for name, meta in required_fields.items():
        dtype = meta["type"]

        if dtype == "Picklist":
            pv = meta.get("picklistValues")
            if pv and isinstance(pv, list):
                # Pick first non-empty value
                for entry in pv:
                    val = entry.get("value") if isinstance(entry, dict) else entry
                    if val:
                        values[name] = val
                        break
            continue

        default = _TYPE_DEFAULTS.get(dtype)
        if default is None:
            continue

        if dtype == "String":
            length = meta.get("length", 255)
            val = f"AuraPrivescTest_{ts}"
            values[name] = val[:length] if length else val
        elif dtype == "Email":
            values[name] = f"aura-test-{ts}@example.invalid"
        else:
            values[name] = default

    return values


def _proof_curl(client: AuraClient, descriptor: str, params: dict) -> str:
    """Build a proof curl for a CRUD operation."""
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=descriptor,
        params=params,
        token=client.aura_token,
        context=client._build_context(),
        proxy=client.proxy,
        insecure=client.insecure,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_object_field_metadata(
    client: AuraClient, object_name: str,
) -> dict[str, Any] | None:
    """Fetch getObjectInfo and return the parsed objectInfo dict (or None)."""
    try:
        resp = await client.request(
            DESCRIPTORS["getObjectInfo"],
            {"objectApiName": object_name},
        )
        actions = resp.get("actions", [])
        if not actions or actions[0].get("state") != "SUCCESS":
            return None
        rv = actions[0].get("returnValue", {})
        if "objectInfos" in rv:
            rv = next(iter(rv["objectInfos"].values()), rv)
        return rv
    except Exception as e:
        logger.debug("getObjectInfo for field metadata failed on %s: %s", object_name, e)
        return None


async def _get_list_view_name(
    client: AuraClient, object_name: str,
) -> str | None:
    """Try to discover a valid list view name for the object."""
    try:
        resp = await client.request(
            DESCRIPTORS["getListsByObjectName"],
            {"objectApiName": object_name},
        )
        actions = resp.get("actions", [])
        if not actions or actions[0].get("state") != "SUCCESS":
            return None
        rv = actions[0].get("returnValue", {})
        lists = rv.get("lists") or rv.get("records") or []
        if isinstance(rv, list):
            lists = rv
        for lv in lists:
            if isinstance(lv, dict):
                api_name = lv.get("apiName") or lv.get("developerName")
                if api_name:
                    return api_name
    except Exception:
        pass
    return None


async def _try_get_items(
    client: AuraClient,
    object_name: str,
    list_view: str | None,
) -> tuple[dict | None, str]:
    """Attempt getItems with a specific listViewApiName. Returns (response_action, proof)."""
    descriptor = DESCRIPTORS["getItems"]
    params = {
        "entityNameOrId": object_name,
        "listViewApiName": list_view,
        "getCount": True,
        "pageSize": 1,
    }
    proof = _proof_curl(client, descriptor, params)
    try:
        resp = await client.request(descriptor, params)
        actions = resp.get("actions", [])
        if actions and actions[0].get("state") == "SUCCESS":
            return actions[0], proof
    except Exception:
        pass
    return None, proof


def _parse_read_action(action: dict, proof: str) -> CrudOperationResult:
    """Parse a successful getItems action into a CrudOperationResult."""
    rv = action.get("returnValue", {})
    records = rv.get("records") or rv.get("result", [])
    count = rv.get("count") or rv.get("totalCount")
    first_record = records[0] if records else None
    record_id = None
    record_data = None
    if first_record and isinstance(first_record, dict):
        record_id = (
            first_record.get("id")
            or first_record.get("Id")
            or first_record.get("record", {}).get("id")
        )
        record_data = first_record

    return CrudOperationResult(
        operation="read",
        success=True,
        record_id=record_id,
        record_data={"count": count, "sample": record_data},
        proof=proof,
        timestamp=_now_iso(),
    )


async def read_records(
    client: AuraClient, object_name: str,
) -> CrudOperationResult:
    """Attempt to read actual records via getItems.

    Tries multiple strategies:
    1. Discover a valid list view via getListsByObjectName
    2. Fall back to common list view names
    3. Fall back to listViewApiName=None
    """
    # Strategy 1: discover a real list view
    list_view = await _get_list_view_name(client, object_name)
    if list_view:
        action, proof = await _try_get_items(client, object_name, list_view)
        if action:
            return _parse_read_action(action, proof)

    # Strategy 2: try common list view names
    last_proof = ""
    last_error = ""
    for lv_name in ("AllItems", "RecentlyViewed", None):
        action, proof = await _try_get_items(client, object_name, lv_name)
        last_proof = proof
        if action:
            return _parse_read_action(action, proof)

    # All strategies failed — build a descriptive error
    descriptor = DESCRIPTORS["getItems"]
    params = {
        "entityNameOrId": object_name,
        "listViewApiName": None,
        "getCount": True,
        "pageSize": 1,
    }
    fallback_proof = _proof_curl(client, descriptor, params)

    # Do one final explicit call to capture the actual error message
    try:
        resp = await client.request(descriptor, params)
        actions = resp.get("actions", [])
        if actions:
            action = actions[0]
            if action.get("state") != "SUCCESS":
                errors = action.get("error", [])
                last_error = errors[0].get("message", "Unknown") if errors else action.get("state", "Unknown")
            else:
                return _parse_read_action(action, fallback_proof)
        else:
            last_error = "No actions in response"
    except Exception as e:
        last_error = str(e)

    return CrudOperationResult(
        operation="read", error=last_error,
        proof=last_proof or fallback_proof, timestamp=_now_iso(),
    )


async def create_record(
    client: AuraClient,
    object_name: str,
    fields: dict[str, Any],
) -> CrudOperationResult:
    """Create a test record via createRecord action."""
    descriptor = DESCRIPTORS["createRecord"]
    params = {"record": {"apiName": object_name, "fields": fields}}
    proof = _proof_curl(client, descriptor, params)

    try:
        resp = await client.request(descriptor, params)
        actions = resp.get("actions", [])
        if not actions:
            return CrudOperationResult(
                operation="create", error="No actions in response",
                proof=proof, timestamp=_now_iso(),
            )

        action = actions[0]
        if action.get("state") != "SUCCESS":
            errors = action.get("error", [])
            msg = errors[0].get("message", "Unknown") if errors else action.get("state", "Unknown")
            return CrudOperationResult(
                operation="create", error=str(msg),
                proof=proof, timestamp=_now_iso(),
            )

        rv = action.get("returnValue", {})
        record_id = rv.get("id") or rv.get("Id")
        return CrudOperationResult(
            operation="create",
            success=True,
            record_id=record_id,
            record_data=rv,
            proof=proof,
            timestamp=_now_iso(),
        )

    except Exception as e:
        return CrudOperationResult(
            operation="create", error=str(e),
            proof=proof, timestamp=_now_iso(),
        )


async def update_record(
    client: AuraClient,
    object_name: str,
    record_id: str,
    fields: dict[str, Any],
) -> CrudOperationResult:
    """Update an existing record via updateRecord action."""
    descriptor = DESCRIPTORS["updateRecord"]
    params = {"record": {"apiName": object_name, "id": record_id, "fields": fields}}
    proof = _proof_curl(client, descriptor, params)

    try:
        resp = await client.request(descriptor, params)
        actions = resp.get("actions", [])
        if not actions:
            return CrudOperationResult(
                operation="update", error="No actions in response",
                record_id=record_id, proof=proof, timestamp=_now_iso(),
            )

        action = actions[0]
        if action.get("state") != "SUCCESS":
            errors = action.get("error", [])
            msg = errors[0].get("message", "Unknown") if errors else action.get("state", "Unknown")
            return CrudOperationResult(
                operation="update", error=str(msg),
                record_id=record_id, proof=proof, timestamp=_now_iso(),
            )

        return CrudOperationResult(
            operation="update",
            success=True,
            record_id=record_id,
            record_data=action.get("returnValue"),
            proof=proof,
            timestamp=_now_iso(),
        )

    except Exception as e:
        return CrudOperationResult(
            operation="update", error=str(e),
            record_id=record_id, proof=proof, timestamp=_now_iso(),
        )


async def delete_record(
    client: AuraClient,
    record_id: str,
) -> CrudOperationResult:
    """Delete a record via deleteRecord action."""
    descriptor = DESCRIPTORS["deleteRecord"]
    params = {"recordId": record_id}
    proof = _proof_curl(client, descriptor, params)

    try:
        resp = await client.request(descriptor, params)
        actions = resp.get("actions", [])
        if not actions:
            return CrudOperationResult(
                operation="delete", error="No actions in response",
                record_id=record_id, proof=proof, timestamp=_now_iso(),
            )

        action = actions[0]
        if action.get("state") != "SUCCESS":
            errors = action.get("error", [])
            msg = errors[0].get("message", "Unknown") if errors else action.get("state", "Unknown")
            return CrudOperationResult(
                operation="delete", error=str(msg),
                record_id=record_id, proof=proof, timestamp=_now_iso(),
            )

        return CrudOperationResult(
            operation="delete",
            success=True,
            record_id=record_id,
            proof=proof,
            timestamp=_now_iso(),
        )

    except Exception as e:
        return CrudOperationResult(
            operation="delete", error=str(e),
            record_id=record_id, proof=proof, timestamp=_now_iso(),
        )
