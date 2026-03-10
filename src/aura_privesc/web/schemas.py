"""Pydantic request/response schemas for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, field_validator
from urllib.parse import urlparse


class ScanCreate(BaseModel):
    """Request body for POST /api/scans."""

    url: str
    token: str | None = None
    sid: str | None = None
    manual_context: str | None = None
    manual_endpoint: str | None = None
    skip_crud: bool = False
    skip_records: bool = False
    skip_apex: bool = False
    skip_validation: bool = False
    skip_crud_test: bool = False
    skip_graphql: bool = False
    timeout: int = 30
    delay: int = 0
    concurrency: int = 5
    proxy: str | None = None
    insecure: bool = False
    verbose: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        if not parsed.hostname:
            raise ValueError("URL must have a hostname")
        return v

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, v: str | None) -> str | None:
        if v is not None:
            parsed = urlparse(v)
            if parsed.scheme not in ("http", "https", "socks5"):
                raise ValueError("Proxy URL must use http, https, or socks5 scheme")
        return v


class ScanStatus(BaseModel):
    """Lightweight response for GET /api/scans/{id}/status."""

    id: str
    status: str
    phase: str
    progress: int
    phase_detail: str


class ScanSummary(BaseModel):
    """Response item for GET /api/scans (list)."""

    id: str
    url: str
    status: str
    phase: str
    progress: int
    summary: dict | None = None
    created_at: str
    finished_at: str | None = None


class ScanDetail(BaseModel):
    """Full response for GET /api/scans/{id}."""

    id: str
    url: str
    config: dict
    status: str
    phase: str
    progress: int
    phase_detail: str
    result: dict | None = None
    error: str | None = None
    summary: dict | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str


class PresetConfig(BaseModel):
    """A scan preset configuration."""

    id: str
    label: str
    description: str
    config: dict


class GraphQLRecordsRequest(BaseModel):
    """Request body for POST /api/graphql/records."""

    scan_id: str
    object_name: str
    fields: list[str]
    first: int = 10
    after: str | None = None


class GraphQLFilteredRequest(BaseModel):
    """Request body for POST /api/graphql/query."""

    scan_id: str
    object_name: str
    fields: list[str]
    where: dict[str, dict[str, str]]
    first: int = 10


class GraphQLExploreRequest(BaseModel):
    """Request body for POST /api/graphql/explore."""

    scan_id: str
    object_name: str
    relationship: str
    fields: list[str]
    first: int = 10
