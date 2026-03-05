"""Unit tests for object/apex classification and report filtering."""

from __future__ import annotations

import os
import tempfile

import pytest

from aura_privesc.enumerator import _parse_object_info, get_record_count, get_records
from aura_privesc.apex import _classify_apex_response
from aura_privesc.models import (
    ApexMethodStatus,
    ApexResult,
    CrudPermissions,
    ObjectResult,
    RiskLevel,
    ScanResult,
    DiscoveryInfo,
)
from aura_privesc.output.html_output import write_report


# ---------------------------------------------------------------------------
# Helpers to build mock Aura responses
# ---------------------------------------------------------------------------

def _object_info_success(
    createable: bool = False,
    updateable: bool = False,
    deletable: bool = False,
    queryable: bool = False,
) -> dict:
    return {
        "actions": [{
            "state": "SUCCESS",
            "returnValue": {
                "createable": createable,
                "updateable": updateable,
                "deletable": deletable,
                "queryable": queryable,
            },
        }],
    }


def _object_info_error(message: str = "No access") -> dict:
    return {
        "actions": [{
            "state": "ERROR",
            "error": [{"message": message}],
        }],
    }


def _get_items_success(count: int, records: list | None = None) -> dict:
    rv = {"count": count}
    if records is not None:
        rv["records"] = records
    return {
        "actions": [{
            "state": "SUCCESS",
            "returnValue": rv,
        }],
    }


def _get_items_error() -> dict:
    return {
        "actions": [{
            "state": "ERROR",
            "error": [{"message": "No list view"}],
        }],
    }


# ---------------------------------------------------------------------------
# 1. Object classification tests
# ---------------------------------------------------------------------------

class TestParseObjectInfo:
    def test_success_sets_accessible_and_crud(self):
        resp = _object_info_success(createable=True, queryable=True)
        result = _parse_object_info("Account", resp)
        assert result.accessible is True
        assert result.crud.createable is True
        assert result.crud.readable is True
        assert result.crud.queryable is True
        assert result.crud.updateable is False
        assert result.crud.deletable is False

    def test_error_sets_not_accessible(self):
        resp = _object_info_error("No access to entity")
        result = _parse_object_info("Secret__c", resp)
        assert result.accessible is False
        assert result.error == "No access to entity"

    def test_success_assigns_risk(self):
        resp = _object_info_success(createable=True)
        result = _parse_object_info("Account", resp)
        assert result.accessible is True
        assert result.risk != RiskLevel.INFO

    def test_empty_actions(self):
        result = _parse_object_info("Foo", {"actions": []})
        assert result.accessible is False

    def test_nested_object_infos(self):
        resp = {
            "actions": [{
                "state": "SUCCESS",
                "returnValue": {
                    "objectInfos": {
                        "Account": {
                            "createable": True,
                            "updateable": True,
                            "deletable": False,
                            "queryable": True,
                        }
                    }
                },
            }],
        }
        result = _parse_object_info("Account", resp)
        assert result.accessible is True
        assert result.crud.createable is True
        assert result.crud.updateable is True


# ---------------------------------------------------------------------------
# 2. Record count tests (Bug 3 — zero count must not become None)
# ---------------------------------------------------------------------------

class TestGetRecordCount:
    @pytest.mark.asyncio
    async def test_count_zero_is_not_none(self):
        """count=0 must return 0, not None (the bug we fixed)."""
        class FakeClient:
            async def request(self, descriptor, params):
                return _get_items_success(0)

        count = await get_record_count(FakeClient(), "Account")
        assert count == 0
        assert count is not None

    @pytest.mark.asyncio
    async def test_count_positive(self):
        class FakeClient:
            async def request(self, descriptor, params):
                return _get_items_success(42)

        count = await get_record_count(FakeClient(), "Account")
        assert count == 42

    @pytest.mark.asyncio
    async def test_error_returns_none(self):
        class FakeClient:
            async def request(self, descriptor, params):
                return _get_items_error()

        count = await get_record_count(FakeClient(), "Account")
        assert count is None

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        class FakeClient:
            async def request(self, descriptor, params):
                raise RuntimeError("network error")

        count = await get_record_count(FakeClient(), "Account")
        assert count is None

    @pytest.mark.asyncio
    async def test_totalcount_fallback(self):
        """When 'count' key is absent, fall back to 'totalCount'."""
        class FakeClient:
            async def request(self, descriptor, params):
                return {
                    "actions": [{
                        "state": "SUCCESS",
                        "returnValue": {"totalCount": 7},
                    }],
                }

        count = await get_record_count(FakeClient(), "Account")
        assert count == 7


# ---------------------------------------------------------------------------
# 3. Apex classification tests
# ---------------------------------------------------------------------------

class TestClassifyApexResponse:
    def test_success_is_callable(self):
        resp = {"actions": [{"state": "SUCCESS"}]}
        result = _classify_apex_response("Ctrl.method", resp)
        assert result.status == ApexMethodStatus.CALLABLE

    def test_access_check_failed_is_denied(self):
        resp = {
            "actions": [{
                "state": "ERROR",
                "error": [{"message": "Access Check Failed for Controller"}],
            }]
        }
        result = _classify_apex_response("Ctrl.method", resp)
        assert result.status == ApexMethodStatus.DENIED

    def test_does_not_exist_is_not_found(self):
        resp = {
            "actions": [{
                "state": "ERROR",
                "error": [{"message": "Controller does not exist"}],
            }]
        }
        result = _classify_apex_response("Ctrl.method", resp)
        assert result.status == ApexMethodStatus.NOT_FOUND

    def test_other_error_is_callable(self):
        """Other errors mean the method exists but the call failed — still callable."""
        resp = {
            "actions": [{
                "state": "ERROR",
                "error": [{"message": "System.NullPointerException"}],
            }]
        }
        result = _classify_apex_response("Ctrl.method", resp)
        assert result.status == ApexMethodStatus.CALLABLE

    def test_no_actions_is_error(self):
        result = _classify_apex_response("Ctrl.method", {"actions": []})
        assert result.status == ApexMethodStatus.ERROR

    def test_unexpected_state(self):
        resp = {"actions": [{"state": "INCOMPLETE"}]}
        result = _classify_apex_response("Ctrl.method", resp)
        assert result.status == ApexMethodStatus.ERROR


# ---------------------------------------------------------------------------
# 4. Report filtering tests (Bug 1 — accessible objects without record_count
#    must still appear in the report)
# ---------------------------------------------------------------------------

def _make_scan_result() -> ScanResult:
    """Build a ScanResult with mixed objects and apex for testing."""
    return ScanResult(
        target_url="https://example.force.com",
        discovery=DiscoveryInfo(endpoint="/s/sfsites/aura", mode="guest"),
        objects=[
            # Accessible with record count
            ObjectResult(
                name="Account",
                accessible=True,
                validated=True,
                crud=CrudPermissions(readable=True, createable=True, queryable=True),
                record_count=5,
                risk=RiskLevel.HIGH,
            ),
            # Accessible WITHOUT record count (getItems failed) — must still appear
            ObjectResult(
                name="Contact",
                accessible=True,
                validated=True,
                crud=CrudPermissions(readable=True, queryable=True),
                record_count=None,
                risk=RiskLevel.LOW,
            ),
            # Accessible with zero records — must still appear
            ObjectResult(
                name="Case",
                accessible=True,
                validated=True,
                crud=CrudPermissions(readable=True, queryable=True),
                record_count=0,
                risk=RiskLevel.LOW,
            ),
            # NOT accessible — must be excluded
            ObjectResult(
                name="Secret__c",
                accessible=False,
                error="No access",
            ),
        ],
        apex_results=[
            ApexResult(
                controller_method="MyCtrl.doThing",
                status=ApexMethodStatus.CALLABLE,
                validated=True,
            ),
            ApexResult(
                controller_method="LockedCtrl.secret",
                status=ApexMethodStatus.DENIED,
                message="Access Check Failed",
            ),
            ApexResult(
                controller_method="GhostCtrl.gone",
                status=ApexMethodStatus.NOT_FOUND,
                message="does not exist",
            ),
        ],
    )


class TestReportFiltering:
    def test_accessible_objects_without_record_count_appear(self):
        result = _make_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            html = open(path).read()

        # All 3 accessible objects must appear
        assert "Account" in html
        assert "Contact" in html
        assert "Case" in html
        # Non-accessible must NOT appear
        assert "Secret__c" not in html

    def test_non_accessible_excluded(self):
        result = _make_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            html = open(path).read()
        assert "Secret__c" not in html

    def test_callable_apex_appears_denied_excluded(self):
        result = _make_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            html = open(path).read()

        assert "MyCtrl.doThing" in html
        assert "LockedCtrl.secret" not in html
        assert "GhostCtrl.gone" not in html

    def test_summary_stats_match(self):
        result = _make_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            html = open(path).read()

        # 3 accessible objects, 1 callable apex
        assert "Object Findings (3)" in html
        assert "Callable Apex Methods (1)" in html

    def test_validated_only_false_includes_unvalidated(self):
        result = _make_scan_result()
        # Add an accessible but unvalidated object
        result.objects.append(ObjectResult(
            name="Lead",
            accessible=True,
            validated=None,
            crud=CrudPermissions(readable=True),
            risk=RiskLevel.LOW,
        ))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=False)
            html = open(path).read()

        # Lead is accessible, so it should appear when not filtering by validation
        assert "Lead" in html
        assert "Object Findings (4)" in html


# ---------------------------------------------------------------------------
# 5. CLI summary stat tests
# ---------------------------------------------------------------------------

class TestCLISummaryStats:
    def test_accessible_count_uses_model_properties(self):
        result = _make_scan_result()
        # Simulate what cli.py now does
        validated_only = True
        accessible = result.validated_objects if validated_only else result.accessible_objects
        callable_apex = [
            r for r in result.apex_results
            if r.status == ApexMethodStatus.CALLABLE and (not validated_only or r.validated is True)
        ]
        assert len(accessible) == 3
        assert len(callable_apex) == 1

    def test_without_validation(self):
        result = _make_scan_result()
        validated_only = False
        accessible = result.validated_objects if validated_only else result.accessible_objects
        callable_apex = [
            r for r in result.apex_results
            if r.status == ApexMethodStatus.CALLABLE and (not validated_only or r.validated is True)
        ]
        assert len(accessible) == 3
        assert len(callable_apex) == 1

    def test_enum_comparison_not_string(self):
        """Verify enum comparison works (the bug was comparing .value == 'CALLABLE')."""
        apex = ApexResult(
            controller_method="Ctrl.m",
            status=ApexMethodStatus.CALLABLE,
        )
        # The old buggy code
        assert apex.status.value != "CALLABLE"
        assert apex.status.value == "callable"
        # The correct comparison
        assert apex.status == ApexMethodStatus.CALLABLE


# ---------------------------------------------------------------------------
# 6. get_records tests
# ---------------------------------------------------------------------------

class TestGetRecords:
    @pytest.mark.asyncio
    async def test_returns_count_and_records(self):
        sample = [{"Id": "001xx", "Name": "Acme"}]

        class FakeClient:
            async def request(self, descriptor, params):
                return _get_items_success(1, records=sample)

        count, records = await get_records(FakeClient(), "Account")
        assert count == 1
        assert records == sample

    @pytest.mark.asyncio
    async def test_zero_count_empty_records(self):
        class FakeClient:
            async def request(self, descriptor, params):
                return _get_items_success(0, records=[])

        count, records = await get_records(FakeClient(), "Account")
        assert count == 0
        assert records == []

    @pytest.mark.asyncio
    async def test_error_returns_none_empty(self):
        class FakeClient:
            async def request(self, descriptor, params):
                raise RuntimeError("boom")

        count, records = await get_records(FakeClient(), "Account")
        assert count is None
        assert records == []

    @pytest.mark.asyncio
    async def test_no_records_key_returns_empty_list(self):
        class FakeClient:
            async def request(self, descriptor, params):
                return _get_items_success(5)

        count, records = await get_records(FakeClient(), "Account")
        assert count == 5
        assert records == []


# ---------------------------------------------------------------------------
# 7. HTML report interactive features
# ---------------------------------------------------------------------------

def _make_interactive_scan_result() -> ScanResult:
    """Build a ScanResult with aura connection details and sample records."""
    return ScanResult(
        target_url="https://example.force.com",
        discovery=DiscoveryInfo(endpoint="/s/sfsites/aura", mode="guest"),
        aura_url="https://example.force.com/s/sfsites/aura",
        aura_token="mytoken",
        aura_context='{"mode":"PROD","app":"siteforce:communityApp"}',
        sid=None,
        objects=[
            ObjectResult(
                name="Account",
                accessible=True,
                validated=True,
                crud=CrudPermissions(readable=True, createable=True, queryable=True),
                record_count=2,
                sample_records=[
                    {"Id": "001xx000001", "Name": "Acme Corp"},
                    {"Id": "001xx000002", "Name": "Globex"},
                ],
                risk=RiskLevel.HIGH,
            ),
            ObjectResult(
                name="Contact",
                accessible=True,
                validated=True,
                crud=CrudPermissions(readable=True),
                record_count=0,
                sample_records=[],
                risk=RiskLevel.LOW,
            ),
        ],
        apex_results=[
            ApexResult(
                controller_method="MyCtrl.doThing",
                status=ApexMethodStatus.CALLABLE,
                validated=True,
            ),
        ],
    )


class TestHTMLInteractiveFeatures:
    def test_aura_config_present(self):
        result = _make_interactive_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            content = open(path).read()
        assert "var AURA=" in content
        assert '"url": "https://example.force.com/s/sfsites/aura"' in content
        assert '"token": "mytoken"' in content

    def test_fire_buttons_for_objects(self):
        result = _make_interactive_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            content = open(path).read()
        assert "getObjectInfo" in content
        assert "getItems" in content
        assert ">Create<" in content
        assert ">Update<" in content
        assert ">Delete<" in content

    def test_fire_button_for_apex(self):
        result = _make_interactive_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            content = open(path).read()
        assert ">Fire<" in content
        assert "ApexActionController" in content

    def test_expand_rows_present(self):
        result = _make_interactive_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            content = open(path).read()
        assert 'class="expand-row"' in content
        assert 'class="obj-row"' in content

    def test_sample_records_in_expand(self):
        result = _make_interactive_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            content = open(path).read()
        assert "Acme Corp" in content
        assert "Globex" in content
        assert 'class="records-table"' in content

    def test_no_aura_config_when_missing(self):
        result = _make_scan_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report(result, output_dir=tmpdir, validated_only=True)
            content = open(path).read()
        assert "var AURA=" not in content
