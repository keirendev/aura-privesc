"""Apex controller discovery and testing."""

from __future__ import annotations

import asyncio
import logging
import re

from .client import AuraClient
from .config import COMMON_APEX_CONTROLLERS
from .discovery import extract_js_urls
from .models import ApexMethodStatus, ApexResult
from .proof import proof_for_apex
from .validator import validate_apex_result

logger = logging.getLogger(__name__)


async def discover_apex_from_js(client: AuraClient, base_url: str) -> list[str]:
    """Scan community JS files for apex:// references."""
    js_urls = await extract_js_urls(client, base_url)
    found: set[str] = set()

    for url in js_urls:
        try:
            content = await client.get_page(url)
            if not content:
                continue
            # Match apex://ControllerName/ACTION$methodName
            for match in re.finditer(r"apex://(\w+)/ACTION\$(\w+)", content):
                controller = match.group(1)
                method = match.group(2)
                found.add(f"{controller}.{method}")
            # Match classname/method from ApexActionController execute calls
            for match in re.finditer(
                r'"classname"\s*:\s*"(\w+)"[^}]*"method"\s*:\s*"(\w+)"', content
            ):
                controller = match.group(1)
                method = match.group(2)
                found.add(f"{controller}.{method}")
        except Exception as e:
            logger.debug("Error scanning JS file %s: %s", url, e)

    return sorted(found)


def build_apex_list(
    discovered: list[str] | None = None,
    user_file: list[str] | None = None,
) -> list[str]:
    """Merge common + discovered + user-supplied Apex controller.method pairs."""
    seen: set[str] = set()
    result: list[str] = []

    for entry in COMMON_APEX_CONTROLLERS:
        lower = entry.strip().lower()
        if lower and lower not in seen:
            seen.add(lower)
            result.append(entry.strip())

    for name_list in (discovered or [], user_file or []):
        for entry in name_list:
            lower = entry.strip().lower()
            if lower and lower not in seen:
                seen.add(lower)
                result.append(entry.strip())

    return result


async def test_apex_method(
    client: AuraClient,
    controller_method: str,
    *,
    skip_validation: bool = False,
) -> ApexResult:
    """Test a single Apex controller.method and classify the result."""
    parts = controller_method.rsplit(".", 1)
    if len(parts) != 2:
        return ApexResult(
            controller_method=controller_method,
            status=ApexMethodStatus.ERROR,
            message="Invalid format — expected Controller.method",
        )

    controller, method = parts

    try:
        resp = await client.call_apex_execute(controller, method)
        result = _classify_apex_response(controller_method, resp)
    except Exception as e:
        msg = str(e)
        if "Access Check Failed" in msg or "denied" in msg.lower():
            result = ApexResult(
                controller_method=controller_method,
                status=ApexMethodStatus.DENIED,
                message=msg[:200],
            )
        else:
            result = ApexResult(
                controller_method=controller_method,
                status=ApexMethodStatus.ERROR,
                message=msg[:200],
            )

    if result.status in (ApexMethodStatus.CALLABLE, ApexMethodStatus.DENIED):
        result.proof = proof_for_apex(client, controller, method)

    if result.status == ApexMethodStatus.CALLABLE and not skip_validation:
        result = await validate_apex_result(client, result)

    return result


def _classify_apex_response(
    controller_method: str,
    resp: dict,
) -> ApexResult:
    """Classify an Apex response as callable, denied, or not found."""
    actions = resp.get("actions", [])
    if not actions:
        return ApexResult(
            controller_method=controller_method,
            status=ApexMethodStatus.ERROR,
            message="No actions in response",
        )

    action = actions[0]
    state = action.get("state", "")

    if state == "SUCCESS":
        return ApexResult(
            controller_method=controller_method,
            status=ApexMethodStatus.CALLABLE,
        )

    if state == "ERROR":
        errors = action.get("error", [])
        msg = errors[0].get("message", "") if errors else ""

        if "Access Check Failed" in msg or "not accessible" in msg.lower() or "do not have access" in msg.lower():
            return ApexResult(
                controller_method=controller_method,
                status=ApexMethodStatus.DENIED,
                message=msg[:200],
            )
        if "does not exist" in msg.lower() or "not found" in msg.lower():
            return ApexResult(
                controller_method=controller_method,
                status=ApexMethodStatus.NOT_FOUND,
                message=msg[:200],
            )
        # Other errors — method exists but call failed (still callable)
        return ApexResult(
            controller_method=controller_method,
            status=ApexMethodStatus.CALLABLE,
            message=msg[:200],
        )

    return ApexResult(
        controller_method=controller_method,
        status=ApexMethodStatus.ERROR,
        message=f"Unexpected state: {state}",
    )


async def test_apex_methods(
    client: AuraClient,
    methods: list[str],
    *,
    skip_validation: bool = False,
) -> list[ApexResult]:
    """Test all Apex methods concurrently (bounded by client semaphore)."""
    tasks = [test_apex_method(client, m, skip_validation=skip_validation) for m in methods]
    return list(await asyncio.gather(*tasks))
