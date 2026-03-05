"""Object enumeration, CRUD permission checks, and record counts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .client import AuraClient
from .config import DESCRIPTORS, STANDARD_OBJECTS
from .models import CrudPermissions, ObjectResult
from .proof import proof_for_object, proof_for_records
from .validator import validate_object_result

logger = logging.getLogger(__name__)


async def get_object_info(client: AuraClient, object_name: str) -> ObjectResult:
    """Call getObjectInfo for a single object, return structured result."""
    try:
        resp = await client.request(
            DESCRIPTORS["getObjectInfo"],
            {"objectApiName": object_name},
        )
        return _parse_object_info(object_name, resp)
    except Exception as e:
        logger.debug("getObjectInfo failed for %s: %s", object_name, e)
        return ObjectResult(name=object_name, error=str(e))


def _parse_object_info(name: str, resp: dict[str, Any]) -> ObjectResult:
    """Parse getObjectInfo response into ObjectResult."""
    actions = resp.get("actions", [])
    if not actions:
        return ObjectResult(name=name, error="No actions in response")

    action = actions[0]
    state = action.get("state", "")
    if state == "ERROR":
        errors = action.get("error", [])
        msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
        return ObjectResult(name=name, error=msg)

    if state != "SUCCESS":
        return ObjectResult(name=name, error=f"State: {state}")

    rv = action.get("returnValue", {})
    if not rv:
        return ObjectResult(name=name, error="Empty returnValue")

    # The objectInfo is either at top level or nested under objectInfos
    obj_info = rv
    if "objectInfos" in rv:
        infos = rv["objectInfos"]
        obj_info = next(iter(infos.values()), rv)

    crud = CrudPermissions(
        createable=obj_info.get("createable", False),
        readable=False,  # Set to True only when getItems returns records
        updateable=obj_info.get("updateable", False),
        deletable=obj_info.get("deletable", False),
        queryable=obj_info.get("queryable", False),
    )

    return ObjectResult(name=name, accessible=True, crud=crud)


async def get_record_count(client: AuraClient, object_name: str) -> int | None:
    """Call getItems with getCount=true to retrieve record count (legacy wrapper)."""
    count, _ = await get_records(client, object_name)
    return count


async def get_records(
    client: AuraClient, object_name: str,
) -> tuple[int | None, list[dict]]:
    """Call getItems to retrieve record count and up to 10 sample records."""
    try:
        resp = await client.request(
            DESCRIPTORS["getItems"],
            {
                "entityNameOrId": object_name,
                "layoutType": "FULL",
                "pageSize": 100,
                "currentPage": 0,
                "useTimeout": False,
                "getCount": False,
                "enableRowActions": False,
            },
        )
        actions = resp.get("actions", [])
        if actions and actions[0].get("state") == "SUCCESS":
            rv = actions[0].get("returnValue", {})
            # Records can be under "records" or "result" (wrapped in {record: ...})
            records = rv.get("records") or rv.get("result") or []
            # Unwrap {record: {...}} wrappers if present
            unwrapped = []
            for r in records:
                if isinstance(r, dict) and "record" in r and len(r) == 1:
                    unwrapped.append(r["record"])
                else:
                    unwrapped.append(r)
            return len(unwrapped), unwrapped
    except Exception as e:
        logger.debug("getItems failed for %s: %s", object_name, e)
    return None, []


async def enumerate_object(
    client: AuraClient,
    object_name: str,
    *,
    skip_crud: bool = False,
    skip_records: bool = False,
    skip_validation: bool = False,
) -> ObjectResult:
    """Full enumeration of a single object: info + record count + validation."""
    if skip_crud:
        result = ObjectResult(name=object_name)
    else:
        result = await get_object_info(client, object_name)

    if result.accessible and not skip_records:
        count, records = await get_records(client, object_name)
        if records:
            result.crud.readable = True
            result.record_count = count
        else:
            result.crud.readable = False
            result.record_count = 0
        result.sample_records = records

    if result.accessible:
        result.proof = proof_for_object(client, object_name)
        if result.crud.readable:
            result.proof_records = proof_for_records(client, object_name)

    if result.accessible and not skip_validation:
        result = await validate_object_result(client, result)

    return result


async def enumerate_objects(
    client: AuraClient,
    object_names: list[str],
    *,
    skip_crud: bool = False,
    skip_records: bool = False,
    skip_validation: bool = False,
    progress=None,
    task_id=None,
) -> list[ObjectResult]:
    """Enumerate all objects concurrently (bounded by client semaphore)."""
    coros = [
        enumerate_object(
            client, name, skip_crud=skip_crud, skip_records=skip_records,
            skip_validation=skip_validation,
        )
        for name in object_names
    ]
    results = []
    for coro in asyncio.as_completed(coros):
        result = await coro
        results.append(result)
        if progress and task_id is not None:
            progress.update(task_id, advance=1)
    return results


def build_object_list(
    config_objects: list[str] | None = None,
    user_objects: list[str] | None = None,
) -> list[str]:
    """Merge standard + discovered + user-supplied objects, deduplicated."""
    seen: set[str] = set()
    result: list[str] = []

    for name in STANDARD_OBJECTS:
        lower = name.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(name)

    for name_list in (config_objects or [], user_objects or []):
        for name in name_list:
            lower = name.strip().lower()
            if lower and lower not in seen:
                seen.add(lower)
                result.append(name.strip())

    return result
