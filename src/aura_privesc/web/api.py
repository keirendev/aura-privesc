"""REST API endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select, update

from ..engine import ScanConfig
from .db import Scan, get_session
from .jobs import JobManager
from .schemas import (
    GraphQLExploreRequest,
    GraphQLFilteredRequest,
    GraphQLMutationRequest,
    GraphQLRecordsRequest,
    GraphQLWriteTestRequest,
    PresetConfig,
    ScanCreate,
    ScanDetail,
    ScanStatus,
    ScanSummary,
)

router = APIRouter(prefix="/api")
job_manager = JobManager()

# --- Presets ---

PRESETS = [
    PresetConfig(
        id="quick",
        label="Quick Scan",
        description="Fast overview: object metadata and Apex controllers only. Skips records, CRUD testing, GraphQL, and validation.",
        config={
            "skip_records": True,
            "skip_crud_test": True,
            "skip_apex": False,
            "skip_graphql": True,
            "skip_validation": True,
        },
    ),
    PresetConfig(
        id="full",
        label="Full Scan",
        description="Complete scan: all phases including CRUD write testing, record enumeration, and GraphQL introspection.",
        config={},
    ),
    PresetConfig(
        id="stealth",
        label="Stealth Scan",
        description="Low and slow: single-threaded with delays. Skips CRUD write testing to minimize traces.",
        config={
            "concurrency": 1,
            "delay": 500,
            "skip_crud_test": True,
        },
    ),
]


@router.get("/presets")
async def list_presets() -> list[PresetConfig]:
    return PRESETS


# --- Scans ---


@router.post("/scans")
async def create_scan(body: ScanCreate) -> ScanDetail:
    # Check for already running scan
    if job_manager.running_scan_id:
        raise HTTPException(409, "A scan is already running")

    scan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    config = ScanConfig(
        url=body.url,
        token=body.token,
        sid=body.sid,
        manual_context=body.manual_context,
        manual_endpoint=body.manual_endpoint,
        objects_list=body.objects_list,
        apex_list=body.apex_list,
        skip_crud=body.skip_crud,
        skip_records=body.skip_records,
        skip_apex=body.skip_apex,
        skip_validation=body.skip_validation,
        skip_crud_test=body.skip_crud_test,
        skip_graphql=body.skip_graphql,
        timeout=body.timeout,
        delay=body.delay,
        concurrency=body.concurrency,
        proxy=body.proxy,
        insecure=body.insecure,
        verbose=body.verbose,
        crm_domain=body.crm_domain,
    )

    config_dict = {
        "url": config.url,
        "skip_crud": config.skip_crud,
        "skip_records": config.skip_records,
        "skip_apex": config.skip_apex,
        "skip_validation": config.skip_validation,
        "skip_crud_test": config.skip_crud_test,
        "skip_graphql": config.skip_graphql,
        "timeout": config.timeout,
        "delay": config.delay,
        "concurrency": config.concurrency,
        "insecure": config.insecure,
        "verbose": config.verbose,
    }
    # Don't store credentials in config_json
    if config.crm_domain:
        config_dict["crm_domain"] = config.crm_domain
    if config.proxy:
        config_dict["proxy"] = config.proxy
    if config.objects_list:
        config_dict["objects_list"] = config.objects_list
    if config.apex_list:
        config_dict["apex_list"] = config.apex_list

    scan = Scan(
        id=scan_id,
        url=body.url,
        config_json=json.dumps(config_dict),
        status="queued",
        phase="",
        progress=0,
        phase_detail="",
        created_at=now,
    )

    async with await get_session() as session:
        session.add(scan)
        await session.commit()

    await job_manager.start_scan(scan_id, config)

    return ScanDetail(
        id=scan_id,
        url=body.url,
        config=config_dict,
        status="queued",
        phase="",
        progress=0,
        phase_detail="",
        created_at=now,
    )


@router.get("/scans")
async def list_scans() -> list[ScanSummary]:
    async with await get_session() as session:
        result = await session.execute(
            select(Scan).order_by(Scan.created_at.desc())
        )
        scans = result.scalars().all()

    return [
        ScanSummary(
            id=s.id,
            url=s.url,
            status=s.status,
            phase=s.phase or "",
            progress=s.progress or 0,
            summary=json.loads(s.summary_json) if s.summary_json else None,
            created_at=s.created_at,
            finished_at=s.finished_at,
        )
        for s in scans
    ]


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str) -> ScanDetail:
    async with await get_session() as session:
        result = await session.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(404, "Scan not found")

    return ScanDetail(
        id=scan.id,
        url=scan.url,
        config=json.loads(scan.config_json) if scan.config_json else {},
        status=scan.status,
        phase=scan.phase or "",
        progress=scan.progress or 0,
        phase_detail=scan.phase_detail or "",
        result=json.loads(scan.result_json) if scan.result_json else None,
        error=scan.error,
        logs=scan.log_text,
        summary=json.loads(scan.summary_json) if scan.summary_json else None,
        started_at=scan.started_at,
        finished_at=scan.finished_at,
        created_at=scan.created_at,
    )


@router.get("/scans/{scan_id}/status")
async def get_scan_status(scan_id: str) -> ScanStatus:
    async with await get_session() as session:
        result = await session.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(404, "Scan not found")

    return ScanStatus(
        id=scan.id,
        status=scan.status,
        phase=scan.phase or "",
        progress=scan.progress or 0,
        phase_detail=scan.phase_detail or "",
    )


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str) -> dict:
    # Cancel if running
    job_manager.cancel(scan_id)

    async with await get_session() as session:
        result = await session.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if not scan:
            raise HTTPException(404, "Scan not found")
        await session.execute(delete(Scan).where(Scan.id == scan_id))
        await session.commit()

    return {"deleted": scan_id}


# --- Live GraphQL endpoints ---


async def _get_scan_client(scan_id: str):
    """Recreate an AuraClient from a completed scan's stored credentials."""
    from ..client import AuraClient

    async with await get_session() as session:
        result = await session.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(404, "Scan not found")
    if scan.status != "completed":
        raise HTTPException(400, "Scan must be completed to use live GraphQL")
    if not scan.result_json:
        raise HTTPException(400, "No scan results available")

    result_data = json.loads(scan.result_json)
    aura_url = result_data.get("aura_url")
    aura_token = result_data.get("aura_token")
    aura_context = result_data.get("aura_context")
    sid = result_data.get("sid")

    if not aura_url:
        raise HTTPException(400, "No Aura URL in scan results")

    config = json.loads(scan.config_json) if scan.config_json else {}

    # Parse base_url and endpoint from aura_url
    from urllib.parse import urlparse
    parsed = urlparse(aura_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    endpoint = parsed.path

    client = AuraClient(
        base_url=base_url,
        endpoint=endpoint,
        token=aura_token,
        concurrency=1,
        timeout=config.get("timeout", 30),
        proxy=config.get("proxy"),
        insecure=config.get("insecure", False),
        sid=sid,
    )

    # Restore context from scan results
    if aura_context:
        import json as _json
        try:
            client.context = _json.loads(aura_context)
        except (ValueError, TypeError):
            pass

    return client


@router.get("/scans/{scan_id}/fields/{object_name}")
async def get_object_fields(scan_id: str, object_name: str) -> dict:
    """Live getObjectInfo call to fetch field names/types for an object."""
    import re
    if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', object_name):
        raise HTTPException(400, "Invalid object name")

    from ..graphql import get_graphql_fields

    client = await _get_scan_client(scan_id)
    try:
        fields_map = await get_graphql_fields(client, [object_name])
        fields = fields_map.get(object_name, [])
        return {
            "object_name": object_name,
            "fields": [{"name": f.name, "data_type": f.data_type} for f in fields],
        }
    finally:
        await client.close()


@router.get("/scans/{scan_id}/records/{object_name}")
async def get_object_records(scan_id: str, object_name: str) -> dict:
    """Live getItems call to fetch records for an object."""
    import re
    if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', object_name):
        raise HTTPException(400, "Invalid object name")

    from ..enumerator import get_records

    client = await _get_scan_client(scan_id)
    try:
        count, records = await get_records(client, object_name)
        return {
            "object_name": object_name,
            "record_count": count,
            "records": records,
        }
    finally:
        await client.close()


@router.post("/graphql/records")
async def graphql_records(body: GraphQLRecordsRequest) -> dict:
    from ..graphql import get_graphql_records

    client = await _get_scan_client(body.scan_id)
    try:
        page = await get_graphql_records(
            client,
            body.object_name,
            body.fields,
            first=body.first,
            after=body.after,
        )
        return page.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        await client.close()


@router.post("/graphql/query")
async def graphql_query(body: GraphQLFilteredRequest) -> dict:
    from ..graphql import get_graphql_filtered_records

    client = await _get_scan_client(body.scan_id)
    try:
        page = await get_graphql_filtered_records(
            client,
            body.object_name,
            body.fields,
            body.where,
            first=body.first,
        )
        return page.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        await client.close()


@router.post("/graphql/explore")
async def graphql_explore(body: GraphQLExploreRequest) -> dict:
    from ..graphql import get_graphql_relationships

    client = await _get_scan_client(body.scan_id)
    try:
        page = await get_graphql_relationships(
            client,
            body.object_name,
            body.relationship,
            body.fields,
            first=body.first,
        )
        return page.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        await client.close()


# --- GraphQL introspection endpoints ---


@router.get("/scans/{scan_id}/graphql/introspect")
async def graphql_introspect_schema(scan_id: str) -> dict:
    """Discover queryable objects via __schema introspection."""
    from ..graphql import introspect_schema
    from ..proof import proof_for_graphql_introspection

    client = await _get_scan_client(scan_id)
    try:
        objects = await introspect_schema(client)
        proof = proof_for_graphql_introspection(client)
        return {"objects": objects, "proof": proof}
    finally:
        await client.close()


@router.get("/scans/{scan_id}/graphql/introspect/{type_name}")
async def graphql_introspect_type(scan_id: str, type_name: str) -> dict:
    """Discover fields of a type via __type introspection."""
    import re
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*(__[a-zA-Z]+)?$', type_name):
        raise HTTPException(400, "Invalid type name")

    from ..graphql import introspect_type_fields
    from ..proof import proof_for_graphql_type_introspection

    client = await _get_scan_client(scan_id)
    try:
        fields = await introspect_type_fields(client, type_name)
        proof = proof_for_graphql_type_introspection(client, type_name)
        return {
            "type_name": type_name,
            "fields": [{"name": f.name, "data_type": f.data_type} for f in fields],
            "proof": proof,
        }
    finally:
        await client.close()


# --- GraphQL mutation endpoints ---


@router.post("/graphql/mutate")
async def graphql_mutate(body: GraphQLMutationRequest) -> dict:
    """Execute a single GraphQL mutation (create or delete)."""
    from ..graphql import graphql_create_record, graphql_delete_record

    if body.operation not in ("create", "delete"):
        raise HTTPException(400, "operation must be 'create' or 'delete'")

    client = await _get_scan_client(body.scan_id)
    try:
        if body.operation == "create":
            if not body.fields:
                raise HTTPException(400, "fields required for create operation")
            result = await graphql_create_record(client, body.object_name, body.fields)
        else:
            if not body.record_id:
                raise HTTPException(400, "record_id required for delete operation")
            result = await graphql_delete_record(client, body.object_name, body.record_id)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        await client.close()


@router.post("/graphql/write-test")
async def graphql_write_test_endpoint(body: GraphQLWriteTestRequest) -> dict:
    """Create then delete a record to prove write access via GraphQL."""
    from ..graphql import graphql_write_test

    client = await _get_scan_client(body.scan_id)
    try:
        result = await graphql_write_test(
            client, body.object_name, body.test_field, body.test_value
        )
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        await client.close()
