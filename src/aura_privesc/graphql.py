"""GraphQL enumeration via executeGraphQL — record counts, field introspection, and record fetching."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from .config import DESCRIPTORS
from .models import GraphQLFieldInfo, GraphQLRecordPage, GraphQLResult
from .proof import proof_for_graphql_count, proof_for_graphql_fields

if TYPE_CHECKING:
    from rich.progress import Progress

    from .client import AuraClient

logger = logging.getLogger(__name__)

# Validation: only allow safe Salesforce API names in GraphQL query interpolation
_SAFE_API_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(__[a-zA-Z]+)?$')


def _validate_api_name(name: str) -> None:
    """Raise ValueError if name is not a safe Salesforce API name."""
    if not _SAFE_API_NAME.match(name):
        raise ValueError(f"Invalid API name: {name!r}")


def _graphql_params(query: str) -> dict[str, Any]:
    """Build executeGraphQL params for a given GraphQL query string."""
    # Extract operation name from the query (first word after 'query ')
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


def _build_count_query(object_names: list[str]) -> str:
    """Build a batched totalCount GraphQL query for multiple objects."""
    parts = []
    for name in object_names:
        parts.append(f"{name}{{totalCount}}")
    inner = "".join(parts)
    return f"query getCount{{uiapi{{query{{{inner}}}}}}}"


def _build_fields_query(object_names: list[str]) -> str:
    """Build an objectInfos introspection query for field names/types.

    NOTE: The UIAPI GraphQL ``objectInfos`` endpoint does not expose field API
    names — only ``label`` and ``dataType``.  ``get_graphql_fields`` therefore
    uses the Aura ``getObjectInfo`` action instead, which returns a dict of
    fields keyed by API name.  This helper is kept only for proof-curl
    generation.
    """
    aliases = " ".join(
        f'{name}:objectInfos(apiNames:["{name}"]){{fields{{label dataType}}}}'
        for name in object_names
    )
    return f"query getFields{{uiapi{{{aliases}}}}}"


async def probe_graphql(client: AuraClient) -> bool:
    """Test whether executeGraphQL is available by querying User totalCount."""
    descriptor = DESCRIPTORS["executeGraphQL"]
    query = "query getUsersCount{uiapi{query{User{totalCount}}}}"
    params = _graphql_params(query)
    try:
        resp = await client.request(descriptor, params)
    except Exception:
        logger.debug("executeGraphQL probe failed", exc_info=True)
        return False

    # Check for SUCCESS state and no errors in returnValue
    actions = resp.get("actions", [])
    if not actions:
        return False
    action = actions[0]
    if action.get("state") != "SUCCESS":
        return False
    rv = action.get("returnValue")
    if isinstance(rv, dict) and rv.get("errors"):
        return False
    return True


async def get_graphql_counts(
    client: AuraClient,
    object_names: list[str],
    batch_size: int = 10,
) -> dict[str, int | None]:
    """Batch totalCount queries. Returns {object_name: count_or_None}."""
    descriptor = DESCRIPTORS["executeGraphQL"]
    results: dict[str, int | None] = {}

    # Process in batches
    for i in range(0, len(object_names), batch_size):
        batch = object_names[i : i + batch_size]
        query = _build_count_query(batch)
        params = _graphql_params(query)

        try:
            resp = await client.request(descriptor, params)
        except Exception:
            logger.debug("GraphQL count batch failed", exc_info=True)
            # Fall back to individual queries
            for name in batch:
                results[name] = await _get_single_count(client, name)
            continue

        actions = resp.get("actions", [])
        if not actions or actions[0].get("state") != "SUCCESS":
            for name in batch:
                results[name] = await _get_single_count(client, name)
            continue

        rv = actions[0].get("returnValue", {})
        errors = rv.get("errors") or []

        # Check for OPERATION_TOO_LARGE or ValidationError
        has_op_error = any(
            "OPERATION_TOO_LARGE" in str(e.get("errorType", ""))
            for e in errors
            if isinstance(e, dict)
        )
        has_validation_error = any(
            "ValidationError" in str(e.get("errorType", ""))
            for e in errors
            if isinstance(e, dict)
        )

        if has_op_error or has_validation_error:
            # Retry individually
            for name in batch:
                results[name] = await _get_single_count(client, name)
            continue

        # Parse successful response
        data = rv.get("data", {}).get("uiapi", {}).get("query", {})
        for name in batch:
            obj_data = data.get(name)
            if isinstance(obj_data, dict) and "totalCount" in obj_data:
                results[name] = obj_data["totalCount"]
            else:
                results[name] = None

    return results


async def _get_single_count(client: AuraClient, object_name: str) -> int | None:
    """Get totalCount for a single object (fallback for batch failures)."""
    descriptor = DESCRIPTORS["executeGraphQL"]
    query = _build_count_query([object_name])
    params = _graphql_params(query)
    try:
        resp = await client.request(descriptor, params)
    except Exception:
        return None

    actions = resp.get("actions", [])
    if not actions or actions[0].get("state") != "SUCCESS":
        return None

    rv = actions[0].get("returnValue", {})
    if rv.get("errors"):
        return None

    data = rv.get("data", {}).get("uiapi", {}).get("query", {})
    obj_data = data.get(object_name)
    if isinstance(obj_data, dict) and "totalCount" in obj_data:
        return obj_data["totalCount"]
    return None


async def get_graphql_fields(
    client: AuraClient,
    object_names: list[str],
    batch_size: int = 10,
) -> dict[str, list[GraphQLFieldInfo]]:
    """Introspect field names/types via Aura getObjectInfo.

    The UIAPI GraphQL ``objectInfos`` endpoint does not expose field API names
    (only ``label``), so we use the Aura ``getObjectInfo`` action instead.
    Each call returns a dict of fields keyed by API name.
    """
    import asyncio as _asyncio

    descriptor = DESCRIPTORS["getObjectInfo"]
    results: dict[str, list[GraphQLFieldInfo]] = {}

    for i in range(0, len(object_names), batch_size):
        batch = object_names[i : i + batch_size]
        tasks = [
            client.request(descriptor, {"objectApiName": name})
            for name in batch
        ]
        responses = await _asyncio.gather(*tasks, return_exceptions=True)

        for name, resp in zip(batch, responses):
            if isinstance(resp, Exception):
                logger.debug("getObjectInfo failed for %s: %s", name, resp)
                results[name] = []
                continue

            actions = resp.get("actions", [])
            if not actions or actions[0].get("state") != "SUCCESS":
                results[name] = []
                continue

            rv = actions[0].get("returnValue", {})
            if "objectInfos" in rv:
                rv = next(iter(rv["objectInfos"].values()), rv)

            fields_data = rv.get("fields", {})
            field_list: list[GraphQLFieldInfo] = []
            if isinstance(fields_data, dict):
                for fname, finfo in fields_data.items():
                    dtype = finfo.get("dataType", "") if isinstance(finfo, dict) else ""
                    field_list.append(GraphQLFieldInfo(name=fname, data_type=dtype))
            results[name] = field_list

    return results


async def enumerate_graphql(
    client: AuraClient,
    object_names: list[str],
    *,
    progress: Progress | None = None,
    task_id: int | None = None,
) -> list[GraphQLResult]:
    """Orchestrate GraphQL enumeration: counts + fields, merge into results."""
    total = len(object_names)

    # Get counts
    counts = await get_graphql_counts(client, object_names)
    if progress is not None and task_id is not None:
        progress.update(task_id, advance=total // 2 or 1)

    # Get fields
    fields = await get_graphql_fields(client, object_names)
    if progress is not None and task_id is not None:
        progress.update(task_id, advance=total - (total // 2 or 1))

    # Merge into GraphQLResult list with proofs
    results: list[GraphQLResult] = []
    for name in object_names:
        count = counts.get(name)
        field_list = fields.get(name, [])

        # Generate proof curls
        proof_count = proof_for_graphql_count(client, [name])
        proof_fields_str = proof_for_graphql_fields(client, [name])

        results.append(
            GraphQLResult(
                object_name=name,
                total_count=count,
                fields=field_list,
                proof_count=proof_count,
                proof_fields=proof_fields_str,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Enhanced GraphQL: record fetching, filtered queries, relationship traversal
# ---------------------------------------------------------------------------


def _build_record_query(
    object_name: str,
    fields: list[str],
    *,
    first: int = 10,
    after: str | None = None,
) -> str:
    """Build a GraphQL query to fetch records with cursor pagination."""
    _validate_api_name(object_name)
    for f in fields:
        _validate_api_name(f)

    # Id is a scalar leaf in UIAPI GraphQL; all other fields are value objects
    field_nodes = " ".join(f if f == "Id" else f"{f}{{value}}" for f in fields)
    args = f"first:{first}"
    if after:
        escaped = after.replace("\\", "\\\\").replace('"', '\\"')
        args += f',after:"{escaped}"'

    return (
        f"query getRecords{{uiapi{{query{{{object_name}({args})"
        f"{{edges{{node{{{field_nodes}}}cursor}}pageInfo{{hasNextPage endCursor}}totalCount}}}}}}}}"
    )


def _build_filtered_query(
    object_name: str,
    fields: list[str],
    where: dict[str, dict[str, str]],
    *,
    first: int = 10,
) -> str:
    """Build a GraphQL query with a where clause."""
    _validate_api_name(object_name)
    for f in fields:
        _validate_api_name(f)

    field_nodes = " ".join(f if f == "Id" else f"{f}{{value}}" for f in fields)

    where_parts = []
    for field_name, conditions in where.items():
        _validate_api_name(field_name)
        cond_parts = []
        for op, val in conditions.items():
            if op not in ("eq", "ne", "lt", "lte", "gt", "gte", "like", "in", "nin"):
                raise ValueError(f"Invalid where operator: {op!r}")
            escaped_val = str(val).replace("\\", "\\\\").replace('"', '\\"')
            cond_parts.append(f'{op}:"{escaped_val}"')
        where_parts.append(f"{field_name}:{{{','.join(cond_parts)}}}")
    where_str = ",".join(where_parts)

    return (
        f"query getFiltered{{uiapi{{query{{{object_name}(first:{first},where:{{{where_str}}})"
        f"{{edges{{node{{{field_nodes}}}cursor}}pageInfo{{hasNextPage endCursor}}totalCount}}}}}}}}"
    )


def _build_relationship_query(
    object_name: str,
    relationship: str,
    fields: list[str],
    *,
    first: int = 10,
) -> str:
    """Build a GraphQL query to traverse a relationship."""
    _validate_api_name(object_name)
    _validate_api_name(relationship)
    for f in fields:
        _validate_api_name(f)

    field_nodes = " ".join(f if f == "Id" else f"{f}{{value}}" for f in fields)

    return (
        f"query getRelated{{uiapi{{query{{{object_name}(first:1)"
        f"{{edges{{node{{{relationship}(first:{first})"
        f"{{edges{{node{{{field_nodes}}}cursor}}totalCount}}}}}}}}}}}}}}"
    )


def _parse_record_page(resp: dict, object_name: str) -> GraphQLRecordPage:
    """Parse a GraphQL response into a GraphQLRecordPage."""
    actions = resp.get("actions", [])
    if not actions or actions[0].get("state") != "SUCCESS":
        return GraphQLRecordPage(object_name=object_name)

    rv = actions[0].get("returnValue", {})
    if rv.get("errors"):
        return GraphQLRecordPage(object_name=object_name)

    data = rv.get("data", {}).get("uiapi", {}).get("query", {})
    obj_data = data.get(object_name, {})

    records = []
    edges = obj_data.get("edges", [])
    for edge in edges:
        node = edge.get("node", {})
        record = {}
        for key, val in node.items():
            if isinstance(val, dict) and "value" in val:
                record[key] = val["value"]
            elif not isinstance(val, dict):
                # Scalar leaf (e.g. Id)
                record[key] = val
            elif "edges" in val:
                sub_records = []
                for sub_edge in val.get("edges", []):
                    sub_node = sub_edge.get("node", {})
                    sub_rec = {}
                    for sk, sv in sub_node.items():
                        if isinstance(sv, dict) and "value" in sv:
                            sub_rec[sk] = sv["value"]
                    if sub_rec:
                        sub_records.append(sub_rec)
                record[key] = sub_records
        if record:
            records.append(record)

    page_info = obj_data.get("pageInfo", {})
    total_count = obj_data.get("totalCount")

    return GraphQLRecordPage(
        object_name=object_name,
        records=records,
        next_cursor=page_info.get("endCursor"),
        has_next=page_info.get("hasNextPage", False),
        total_count=total_count,
    )


def _extract_bad_fields(resp: dict) -> set[str]:
    """Extract field names from FieldUndefined / SubselectionNotAllowed errors.

    Error paths look like ``uiapi/query/Object/edges/node/FieldName`` or
    ``uiapi/query/Object/edges/node/FieldName/value``.  We extract the field
    name that sits directly under ``node/``.
    """
    import re
    bad: set[str] = set()
    rv = resp.get("actions", [{}])[0].get("returnValue", {})
    for err in rv.get("errors", []):
        # Use the path to find the field under node/
        path = ""
        for loc_key in ("paths", "path"):
            paths = err.get(loc_key, [])
            if paths:
                path = paths[0] if isinstance(paths[0], str) else "/".join(paths)
                break
        if not path:
            # Fall back to the @[...] in the message
            m = re.search(r"@\[([^\]]+)\]", err.get("message", ""))
            if m:
                path = m.group(1)
        # Extract field name right after .../node/
        m = re.search(r"/node/(\w+)", path)
        if m:
            bad.add(m.group(1))
    return bad


async def get_graphql_records(
    client: AuraClient,
    object_name: str,
    fields: list[str],
    *,
    first: int = 10,
    after: str | None = None,
    max_retries: int = 3,
) -> GraphQLRecordPage:
    """Fetch records for an object with cursor pagination.

    If the query fails with FieldUndefined errors, the invalid fields are
    removed and the query is retried automatically.
    """
    _validate_api_name(object_name)
    descriptor = DESCRIPTORS["executeGraphQL"]
    remaining = list(fields)

    for attempt in range(max_retries + 1):
        if not remaining:
            return GraphQLRecordPage(object_name=object_name)

        query = _build_record_query(object_name, remaining, first=first, after=after)
        params = _graphql_params(query)

        try:
            resp = await client.request(descriptor, params)
        except Exception:
            logger.debug("GraphQL record fetch failed for %s", object_name, exc_info=True)
            return GraphQLRecordPage(object_name=object_name)

        bad_fields = _extract_bad_fields(resp)
        if bad_fields and attempt < max_retries:
            logger.debug("Retrying %s without fields: %s", object_name, bad_fields)
            remaining = [f for f in remaining if f not in bad_fields]
            continue

        return _parse_record_page(resp, object_name)

    return GraphQLRecordPage(object_name=object_name)


async def get_graphql_filtered_records(
    client: AuraClient,
    object_name: str,
    fields: list[str],
    where: dict[str, dict[str, str]],
    *,
    first: int = 10,
) -> GraphQLRecordPage:
    """Fetch records with a where filter."""
    _validate_api_name(object_name)
    descriptor = DESCRIPTORS["executeGraphQL"]
    query = _build_filtered_query(object_name, fields, where, first=first)
    params = _graphql_params(query)

    try:
        resp = await client.request(descriptor, params)
    except Exception:
        logger.debug("GraphQL filtered query failed for %s", object_name, exc_info=True)
        return GraphQLRecordPage(object_name=object_name)

    return _parse_record_page(resp, object_name)


async def get_graphql_relationships(
    client: AuraClient,
    object_name: str,
    relationship: str,
    fields: list[str],
    *,
    first: int = 10,
) -> GraphQLRecordPage:
    """Fetch records through a relationship traversal."""
    _validate_api_name(object_name)
    _validate_api_name(relationship)
    descriptor = DESCRIPTORS["executeGraphQL"]
    query = _build_relationship_query(object_name, relationship, fields, first=first)
    params = _graphql_params(query)

    try:
        resp = await client.request(descriptor, params)
    except Exception:
        logger.debug("GraphQL relationship query failed for %s.%s", object_name, relationship, exc_info=True)
        return GraphQLRecordPage(object_name=object_name)

    actions = resp.get("actions", [])
    if not actions or actions[0].get("state") != "SUCCESS":
        return GraphQLRecordPage(object_name=object_name)

    rv = actions[0].get("returnValue", {})
    if rv.get("errors"):
        return GraphQLRecordPage(object_name=object_name)

    data = rv.get("data", {}).get("uiapi", {}).get("query", {})
    obj_data = data.get(object_name, {})
    edges = obj_data.get("edges", [])

    records = []
    total_count = None
    if edges:
        node = edges[0].get("node", {})
        rel_data = node.get(relationship, {})
        total_count = rel_data.get("totalCount")
        for edge in rel_data.get("edges", []):
            sub_node = edge.get("node", {})
            record = {}
            for key, val in sub_node.items():
                if isinstance(val, dict) and "value" in val:
                    record[key] = val["value"]
            if record:
                records.append(record)

    return GraphQLRecordPage(
        object_name=object_name,
        records=records,
        total_count=total_count,
    )
