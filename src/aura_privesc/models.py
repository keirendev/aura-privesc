"""Pydantic models for all scan results."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CrudPermissions(BaseModel):
    createable: bool = False
    readable: bool = False
    updateable: bool = False
    deletable: bool = False
    queryable: bool = False

    @property
    def has_write(self) -> bool:
        return self.createable or self.updateable or self.deletable


class CrudOperationResult(BaseModel):
    operation: str  # "read", "create", "update", "delete"
    success: bool = False
    record_id: str | None = None
    record_data: dict | None = None
    error: str | None = None
    proof: str | None = None
    timestamp: str | None = None


class CrudValidationResult(BaseModel):
    object_name: str
    read: CrudOperationResult | None = None
    create: CrudOperationResult | None = None
    update: CrudOperationResult | None = None
    delete: CrudOperationResult | None = None
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def proven_operations(self) -> list[str]:
        return [
            op.operation
            for op in [self.read, self.create, self.update, self.delete]
            if op is not None and op.success
        ]


class ObjectResult(BaseModel):
    name: str
    accessible: bool = False
    crud: CrudPermissions = CrudPermissions()
    record_count: int | None = None
    sample_records: list[dict] = []
    risk: RiskLevel = RiskLevel.INFO
    error: str | None = None
    proof: str | None = None
    proof_records: str | None = None
    validated: bool | None = None
    validation_detail: str | None = None
    crud_validation: CrudValidationResult | None = None


class ApexMethodStatus(str, Enum):
    CALLABLE = "callable"
    DENIED = "denied"
    NOT_FOUND = "not_found"
    ERROR = "error"


class ApexResult(BaseModel):
    controller_method: str
    status: ApexMethodStatus
    message: str | None = None
    proof: str | None = None
    validated: bool | None = None
    validation_detail: str | None = None


class GraphQLFieldInfo(BaseModel):
    name: str
    data_type: str


class GraphQLResult(BaseModel):
    object_name: str
    total_count: int | None = None
    fields: list[GraphQLFieldInfo] = []
    error: str | None = None
    proof_count: str | None = None
    proof_fields: str | None = None


class GraphQLRecordPage(BaseModel):
    """Page of records returned by GraphQL record fetch."""

    object_name: str
    records: list[dict] = []
    next_cursor: str | None = None
    has_next: bool = False
    total_count: int | None = None


class GraphQLMutationResult(BaseModel):
    """Result of a single GraphQL mutation (create or delete)."""

    operation: str
    success: bool = False
    record_id: str | None = None
    error: str | None = None
    proof: str | None = None


class GraphQLWriteTestResult(BaseModel):
    """Result of a create-then-delete write test via GraphQL."""

    object_name: str
    create: GraphQLMutationResult | None = None
    delete: GraphQLMutationResult | None = None


class UserInfo(BaseModel):
    user_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    email: str | None = None
    is_guest: bool = True


class DiscoveryInfo(BaseModel):
    endpoint: str
    fwuid: str | None = None
    app_name: str | None = None
    mode: str = "guest"


class RestApiCheck(BaseModel):
    name: str
    endpoint: str
    success: bool = False
    status_code: int | None = None
    detail: str | None = None
    proof: str | None = None
    error: str | None = None


class RestApiResult(BaseModel):
    api_enabled: bool = False
    api_version: str | None = None
    api_base_url: str | None = None
    checks: list[RestApiCheck] = []
    soql_example_curl: str | None = None


class ScanResult(BaseModel):
    target_url: str
    discovery: DiscoveryInfo | None = None
    user_info: UserInfo | None = None
    soql_capable: bool = False
    objects: list[ObjectResult] = []
    apex_results: list[ApexResult] = []
    graphql_available: bool = False
    graphql_results: list[GraphQLResult] = []
    rest_api: RestApiResult | None = None

    aura_url: str | None = None
    aura_token: str | None = None
    aura_context: str | None = None
    sid: str | None = None

    @property
    def accessible_objects(self) -> list[ObjectResult]:
        return [o for o in self.objects if o.accessible]

    @property
    def validated_objects(self) -> list[ObjectResult]:
        return [o for o in self.objects if o.accessible and o.validated is True]

    @property
    def critical_findings(self) -> list[ObjectResult]:
        return [o for o in self.objects if o.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)]

    @property
    def crud_validated_objects(self) -> list[ObjectResult]:
        return [o for o in self.objects if o.crud_validation is not None and not o.crud_validation.skipped]
