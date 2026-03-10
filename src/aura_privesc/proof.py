"""Generate curl proof-of-concept commands for scan findings."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from .client import AuraClient

from .config import DESCRIPTORS

_SAFE_API_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(__[a-zA-Z]+)?$')


def _validate_api_name(name: str) -> None:
    """Raise ValueError if name is not a safe Salesforce API name."""
    if not _SAFE_API_NAME.match(name):
        raise ValueError(f"Invalid API name: {name!r}")


def generate_curl(
    aura_url: str,
    descriptor: str,
    params: dict,
    token: str,
    context: str,
    *,
    sid: str | None = None,
    proxy: str | None = None,
    insecure: bool = False,
) -> str:
    """Build a ready-to-paste curl command that reproduces an Aura request."""
    message = json.dumps(
        {
            "actions": [
                {
                    "id": "123;a",
                    "descriptor": descriptor,
                    "callingDescriptor": "UNKNOWN",
                    "params": params,
                }
            ]
        },
        separators=(",", ":"),
    )

    ctx_encoded = quote(context, safe='')
    token_encoded = quote(token, safe='')
    body = f"message={message}&aura.context={ctx_encoded}&aura.pageURI=/s/&aura.token={token_encoded}"

    flags = ""
    if insecure:
        flags += " -k"
    if proxy:
        flags += f" --proxy {proxy}"
    if sid:
        flags += f" -H 'Cookie: sid={sid}'"

    return f"curl -X POST '{aura_url}' -H 'Content-Type: application/x-www-form-urlencoded'{flags} -d '{body}' | python3 -m json.tool"


def proof_for_object(client: AuraClient, object_name: str) -> str:
    """Generate a getObjectInfo curl command for an object finding."""
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=DESCRIPTORS["getObjectInfo"],
        params={"objectApiName": object_name},
        token=client.aura_token,
        context=client._build_context(),
        sid=client.sid,
        proxy=client.proxy,
        insecure=client.insecure,
    )


def proof_for_records(client: AuraClient, object_name: str) -> str:
    """Generate a getItems curl command that retrieves actual records."""
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=DESCRIPTORS["getItems"],
        params={
            "entityNameOrId": object_name,
            "layoutType": "FULL",
            "pageSize": 100,
            "currentPage": 0,
            "useTimeout": False,
            "getCount": False,
            "enableRowActions": False,
        },
        token=client.aura_token,
        context=client._build_context(),
        sid=client.sid,
        proxy=client.proxy,
        insecure=client.insecure,
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
        sid=client.sid,
        proxy=client.proxy,
        insecure=client.insecure,
    )


def _build_count_query(object_names: list[str]) -> str:
    parts = "".join(f"{name}{{totalCount}}" for name in object_names)
    return f"query getCount{{uiapi{{query{{{parts}}}}}}}"


def _build_fields_query(object_names: list[str]) -> str:
    aliases = " ".join(
        f'{name}:objectInfos(apiNames:["{name}"]){{fields{{dataType}}}}'
        for name in object_names
    )
    return f"query getFields{{uiapi{{{aliases}}}}}"


def _graphql_params(query: str) -> dict:
    op_name = ""
    if query.strip().startswith("query "):
        rest = query.strip()[6:]
        op_name = rest.split("{", 1)[0].split("(", 1)[0].strip()
    return {
        "queryInput": {
            "operationName": op_name,
            "query": query,
            "variables": {},
        }
    }


def proof_for_graphql_count(client: AuraClient, object_names: list[str]) -> str:
    """Generate a curl command for GraphQL totalCount query."""
    query = _build_count_query(object_names)
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=DESCRIPTORS["executeGraphQL"],
        params=_graphql_params(query),
        token=client.aura_token,
        context=client._build_context(),
        sid=client.sid,
        proxy=client.proxy,
        insecure=client.insecure,
    )


def proof_for_graphql_fields(client: AuraClient, object_names: list[str]) -> str:
    """Generate a curl command for GraphQL field introspection query."""
    query = _build_fields_query(object_names)
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=DESCRIPTORS["executeGraphQL"],
        params=_graphql_params(query),
        token=client.aura_token,
        context=client._build_context(),
        sid=client.sid,
        proxy=client.proxy,
        insecure=client.insecure,
    )


def _build_record_query(object_name: str, fields: list[str]) -> str:
    """Build a GraphQL record fetch query for proof generation."""
    _validate_api_name(object_name)
    for f in fields:
        _validate_api_name(f)
    field_nodes = " ".join(f if f == "Id" else f"{f}{{value}}" for f in fields)
    return (
        f"query getRecords{{uiapi{{query{{{object_name}(first:10)"
        f"{{edges{{node{{{field_nodes}}}cursor}}pageInfo{{hasNextPage endCursor}}totalCount}}}}}}}}"
    )


def _build_filtered_record_query(
    object_name: str, fields: list[str], where: dict[str, dict[str, str]]
) -> str:
    """Build a filtered GraphQL query for proof generation."""
    _validate_api_name(object_name)
    for f in fields:
        _validate_api_name(f)
    field_nodes = " ".join(f if f == "Id" else f"{f}{{value}}" for f in fields)

    where_parts = []
    for field_name, conditions in where.items():
        _validate_api_name(field_name)
        cond_parts = []
        for op, val in conditions.items():
            escaped_val = str(val).replace("\\", "\\\\").replace('"', '\\"')
            cond_parts.append(f'{op}:"{escaped_val}"')
        where_parts.append(f"{field_name}:{{{','.join(cond_parts)}}}")
    where_str = ",".join(where_parts)

    return (
        f"query getFiltered{{uiapi{{query{{{object_name}(first:10,where:{{{where_str}}})"
        f"{{edges{{node{{{field_nodes}}}cursor}}pageInfo{{hasNextPage endCursor}}totalCount}}}}}}}}"
    )


def proof_for_graphql_records(
    client: AuraClient, object_name: str, fields: list[str]
) -> str:
    """Generate a curl command for GraphQL record fetch query."""
    query = _build_record_query(object_name, fields)
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=DESCRIPTORS["executeGraphQL"],
        params=_graphql_params(query),
        token=client.aura_token,
        context=client._build_context(),
        sid=client.sid,
        proxy=client.proxy,
        insecure=client.insecure,
    )


def proof_for_graphql_filtered(
    client: AuraClient,
    object_name: str,
    fields: list[str],
    where: dict[str, dict[str, str]],
) -> str:
    """Generate a curl command for a filtered GraphQL query."""
    query = _build_filtered_record_query(object_name, fields, where)
    return generate_curl(
        aura_url=client.aura_url,
        descriptor=DESCRIPTORS["executeGraphQL"],
        params=_graphql_params(query),
        token=client.aura_token,
        context=client._build_context(),
        sid=client.sid,
        proxy=client.proxy,
        insecure=client.insecure,
    )
