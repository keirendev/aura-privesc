"""Self-validation of findings to filter false positives."""

from __future__ import annotations

import logging
import re

from .client import AuraClient
from .config import DESCRIPTORS
from .models import ApexMethodStatus, ApexResult, ObjectResult

logger = logging.getLogger(__name__)

# Patterns indicating access was denied (case-insensitive)
_ACCESS_DENIED_PATTERNS = re.compile(
    r"access check failed|not accessible|do not have access|insufficient privileges",
    re.IGNORECASE,
)


async def validate_object_result(
    client: AuraClient,
    result: ObjectResult,
) -> ObjectResult:
    """Re-check an accessible object to confirm it's not a false positive."""
    if not result.accessible:
        return result

    try:
        resp = await client.request(
            DESCRIPTORS["getObjectInfo"],
            {"objectApiName": result.name},
        )
    except Exception as e:
        logger.debug("Validation request failed for %s: %s", result.name, e)
        result.validated = False
        result.validation_detail = f"Validation request failed: {e}"
        return result

    actions = resp.get("actions", [])
    if not actions:
        result.validated = False
        result.validation_detail = "No actions in validation response"
        return result

    action = actions[0]
    state = action.get("state", "")

    if state != "SUCCESS":
        result.validated = False
        result.validation_detail = f"Validation returned state={state}"
        return result

    # Confirm real metadata is present (apiName or fields)
    rv = action.get("returnValue", {})
    if "objectInfos" in rv:
        rv = next(iter(rv["objectInfos"].values()), rv)

    has_api_name = bool(rv.get("apiName"))
    has_fields = bool(rv.get("fields"))

    if not (has_api_name or has_fields):
        result.validated = False
        result.validation_detail = "SUCCESS but no real metadata (apiName/fields missing)"
        return result

    result.validated = True
    result.validation_detail = "Object metadata confirmed"

    # If readable, attempt getItems to confirm record-level access
    if result.crud.readable:
        try:
            items_resp = await client.request(
                DESCRIPTORS["getItems"],
                {
                    "entityNameOrId": result.name,
                    "layoutType": "FULL",
                    "pageSize": 100,
                    "currentPage": 0,
                    "useTimeout": False,
                    "getCount": False,
                    "enableRowActions": False,
                },
            )
            items_actions = items_resp.get("actions", [])
            if items_actions and items_actions[0].get("state") == "SUCCESS":
                result.validation_detail = "Record-level access confirmed"
            else:
                # getItems failed — strip the non-working records proof
                result.proof_records = None
        except Exception as e:
            logger.debug("getItems validation failed for %s: %s", result.name, e)
            # Object is still validated — just couldn't confirm record access
            result.proof_records = None

    return result


async def validate_apex_result(
    client: AuraClient,
    result: ApexResult,
) -> ApexResult:
    """Re-check a CALLABLE apex method to confirm it's not a false positive."""
    if result.status != ApexMethodStatus.CALLABLE:
        return result

    parts = result.controller_method.rsplit(".", 1)
    if len(parts) != 2:
        result.validated = False
        result.validation_detail = "Invalid controller.method format"
        return result

    controller, method = parts

    try:
        resp = await client.call_apex(controller, method)
    except Exception as e:
        msg = str(e)
        if _ACCESS_DENIED_PATTERNS.search(msg):
            result.status = ApexMethodStatus.DENIED
            result.validated = True
            result.validation_detail = f"Reclassified to DENIED: {msg[:200]}"
        else:
            result.validated = False
            result.validation_detail = f"Validation request failed: {msg[:200]}"
        return result

    actions = resp.get("actions", [])
    if not actions:
        result.validated = False
        result.validation_detail = "No actions in validation response"
        return result

    action = actions[0]
    state = action.get("state", "")

    if state == "SUCCESS":
        result.validated = True
        result.validation_detail = "Apex method callable confirmed"
        return result

    if state == "ERROR":
        errors = action.get("error", [])
        msg = errors[0].get("message", "") if errors else ""

        if _ACCESS_DENIED_PATTERNS.search(msg):
            result.status = ApexMethodStatus.DENIED
            result.validated = True
            result.validation_detail = f"Reclassified to DENIED: {msg[:200]}"
        else:
            # Other errors (missing params, wrong types) mean we got past
            # the access check — method is genuinely callable
            result.validated = True
            result.validation_detail = f"Got past access check (error: {msg[:200]})"
        return result

    result.validated = False
    result.validation_detail = f"Unexpected state: {state}"
    return result
