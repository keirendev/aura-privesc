"""Permission aggregation, SOQL check, user info retrieval."""

from __future__ import annotations

import logging
from typing import Any

from .client import AuraClient
from .config import DESCRIPTORS
from .models import UserInfo

logger = logging.getLogger(__name__)


async def get_user_info(client: AuraClient) -> UserInfo:
    """Get current user info via getProfileMenuResponse."""
    try:
        resp = await client.call_action("getProfileMenuResponse")
        return _parse_user_info(resp, is_guest=client.token is None)
    except Exception as e:
        logger.debug("getProfileMenuResponse failed: %s", e)
        return UserInfo(is_guest=client.token is None)


def _parse_user_info(resp: dict[str, Any], is_guest: bool) -> UserInfo:
    """Parse profile menu response into UserInfo."""
    actions = resp.get("actions", [])
    if not actions or actions[0].get("state") != "SUCCESS":
        return UserInfo(is_guest=is_guest)

    rv = actions[0].get("returnValue", {})
    if not rv:
        return UserInfo(is_guest=is_guest)

    return UserInfo(
        user_id=rv.get("userId") or rv.get("Id"),
        username=rv.get("userName") or rv.get("Username"),
        display_name=rv.get("Name") or rv.get("displayName"),
        email=rv.get("Email") or rv.get("email"),
        is_guest=is_guest,
    )


async def check_soql_capability(client: AuraClient) -> bool:
    """Test if SOQL queries work by trying getItems on Account."""
    try:
        resp = await client.request(
            DESCRIPTORS["getItems"],
            {
                "entityNameOrId": "Account",
                "listViewApiName": None,
                "getCount": True,
                "pageSize": 0,
            },
        )
        actions = resp.get("actions", [])
        if actions and actions[0].get("state") == "SUCCESS":
            return True
    except Exception as e:
        logger.debug("SOQL capability check failed: %s", e)
    return False


async def get_config_objects(client: AuraClient) -> list[str]:
    """Extract object names from getConfigData response."""
    try:
        resp = await client.call_action("getConfigData")
        return _parse_config_objects(resp)
    except Exception as e:
        logger.debug("getConfigData for objects failed: %s", e)
        return []


def _parse_config_objects(resp: dict[str, Any]) -> list[str]:
    """Extract object API names from config data."""
    objects: list[str] = []
    actions = resp.get("actions", [])
    if not actions or actions[0].get("state") != "SUCCESS":
        return objects

    rv = actions[0].get("returnValue", {})

    # Look through the response for object references
    def _walk(data: Any, depth: int = 0) -> None:
        if depth > 5:
            return
        if isinstance(data, dict):
            # Check for apiName or objectApiName keys
            for key in ("apiName", "objectApiName", "entityName"):
                val = data.get(key)
                if isinstance(val, str) and val and not val.startswith("aura://"):
                    objects.append(val)
            for v in data.values():
                _walk(v, depth + 1)
        elif isinstance(data, list):
            for item in data:
                _walk(item, depth + 1)

    _walk(rv)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for obj in objects:
        if obj not in seen:
            seen.add(obj)
            unique.append(obj)

    return unique
