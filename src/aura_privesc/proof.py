"""Generate curl proof-of-concept commands for scan findings."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import AuraClient

from .config import DESCRIPTORS


def generate_curl(
    aura_url: str,
    descriptor: str,
    params: dict,
    token: str,
    context: str,
    *,
    proxy: str | None = None,
    insecure: bool = False,
    sid: str | None = None,
) -> str:
    """Build a ready-to-paste curl command that reproduces an Aura request."""
    message = json.dumps(
        {
            "actions": [
                {
                    "id": "0",
                    "descriptor": descriptor,
                    "callingDescriptor": "UNKNOWN",
                    "params": params,
                }
            ]
        },
        separators=(",", ":"),
    )

    body = f"message={message}&aura.context={context}&aura.pageURI=/s/&aura.token={token}"

    flags = ""
    if proxy:
        flags += f" --proxy {proxy} -k"
    elif insecure:
        flags += " -k"

    if sid:
        flags += f" -H 'Cookie: sid={sid}'"

    return f"curl -s -X POST '{aura_url}' -H 'Content-Type: application/x-www-form-urlencoded'{flags} -d '{body}'"


def proof_for_object(client: AuraClient, object_name: str) -> str:
    """Generate a getObjectInfo curl command for an object finding."""
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=DESCRIPTORS["getObjectInfo"],
        params={"objectApiName": object_name},
        token=client.aura_token,
        context=client._build_context(),
        proxy=client.proxy,
        insecure=client.insecure,
        sid=client.sid,
    )


def proof_for_records(client: AuraClient, object_name: str) -> str:
    """Generate a getItems curl command that retrieves actual records."""
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=DESCRIPTORS["getItems"],
        params={
            "entityNameOrId": object_name,
            "listViewApiName": None,
            "getCount": True,
            "pageSize": 1,
        },
        token=client.aura_token,
        context=client._build_context(),
        proxy=client.proxy,
        insecure=client.insecure,
        sid=client.sid,
    )


def proof_for_apex(client: AuraClient, controller: str, method: str) -> str:
    """Generate an ApexActionController/execute curl command for an Apex finding."""
    descriptor = "aura://ApexActionController/ACTION$execute"
    params = {
        "namespace": "",
        "classname": controller,
        "method": method,
        "params": {},
        "cacheable": False,
        "isContinuation": False,
    }
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=descriptor,
        params=params,
        token=client.aura_token,
        context=client._build_context(),
        proxy=client.proxy,
        insecure=client.insecure,
        sid=client.sid,
    )
