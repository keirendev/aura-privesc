"""Job manager — runs scan jobs as asyncio tasks."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update

from ..engine import ScanConfig, ScanEngine
from ..exceptions import DiscoveryError, ReconError
from .db import Recon, Scan, get_session

logger = logging.getLogger(__name__)


class _ScanLogCapture(logging.Handler):
    """Captures log records from aura_privesc.* into a StringIO buffer."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.buffer = io.StringIO()
        self.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.buffer.write(msg + "\n")
        except Exception:
            pass

    def get_text(self) -> str:
        return self.buffer.getvalue()


def _strip_records(result_dict: dict) -> dict:
    """Strip sample_records and record_data from result before persisting."""
    for obj in result_dict.get("objects", []):
        obj.pop("sample_records", None)
        cv = obj.get("crud_validation")
        if cv:
            for op in ("read", "create", "update", "delete"):
                op_result = cv.get(op)
                if op_result:
                    op_result.pop("record_data", None)
    return result_dict


def _build_summary(result_dict: dict) -> dict:
    """Build denormalized summary stats from scan result."""
    objects = result_dict.get("objects", [])
    accessible = [o for o in objects if o.get("accessible")]
    writable = [o for o in accessible if any(
        o.get("crud", {}).get(k) for k in ("createable", "updateable", "deletable")
    )]
    proven = [
        o for o in accessible
        if o.get("crud_validation") and not o["crud_validation"].get("skipped")
        and any(
            o["crud_validation"].get(op, {}).get("success")
            for op in ("create", "update", "delete")
            if o["crud_validation"].get(op)
        )
    ]

    apex = result_dict.get("apex_results", [])
    callable_apex = [a for a in apex if a.get("status") == "callable"]

    gql = result_dict.get("graphql_results", [])
    gql_counted = [r for r in gql if r.get("total_count") is not None]

    return {
        "objects_scanned": len(objects),
        "accessible": len(accessible),
        "writable": len(writable),
        "proven_writes": len(proven),
        "callable_apex": len(callable_apex),
        "graphql_counted": len(gql_counted),
        "graphql_available": result_dict.get("graphql_available", False),
        "rest_api_enabled": bool(result_dict.get("rest_api", {}).get("api_enabled")) if result_dict.get("rest_api") else False,
    }


class JobManager:
    """Runs scan and recon jobs as asyncio tasks within the FastAPI event loop."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._recon_tasks: dict[str, asyncio.Task] = {}

    @property
    def running_scan_id(self) -> str | None:
        for scan_id, task in self._tasks.items():
            if not task.done():
                return scan_id
        return None

    @property
    def running_recon_id(self) -> str | None:
        for recon_id, task in self._recon_tasks.items():
            if not task.done():
                return recon_id
        return None

    async def start_scan(self, scan_id: str, config: ScanConfig) -> None:
        task = asyncio.create_task(self._run_scan(scan_id, config))
        self._tasks[scan_id] = task

    async def _run_scan(self, scan_id: str, config: ScanConfig) -> None:
        now = datetime.now(timezone.utc).isoformat()

        # Capture logs for this scan
        log_capture = _ScanLogCapture()
        aura_logger = logging.getLogger("aura_privesc")
        aura_logger.addHandler(log_capture)

        # Update status to running
        async with await get_session() as session:
            await session.execute(
                update(Scan)
                .where(Scan.id == scan_id)
                .values(status="running", started_at=now, phase="discovery", progress=0)
            )
            await session.commit()

        async def on_progress(phase: str, current: int, total: int, detail: str) -> None:
            pct = int((current / total * 100) if total > 0 else 0)
            phase_map = {
                "discovery": 2,
                "user_context": 5,
                "enumeration": 10,
                "crud_test": 50,
                "apex": 65,
                "graphql": 80,
                "complete": 100,
            }
            # Use weighted progress: phase base + within-phase progress
            base = phase_map.get(phase, 0)
            if phase == "complete":
                overall = 100
            elif total > 0:
                next_phases = list(phase_map.keys())
                idx = next_phases.index(phase) if phase in next_phases else 0
                next_base = phase_map.get(next_phases[min(idx + 1, len(next_phases) - 1)], 100)
                range_size = next_base - base
                overall = base + int(range_size * current / total)
            else:
                overall = base

            try:
                async with await get_session() as session:
                    await session.execute(
                        update(Scan)
                        .where(Scan.id == scan_id)
                        .values(
                            phase=phase,
                            progress=min(overall, 100),
                            phase_detail=detail or "",
                        )
                    )
                    await session.commit()
            except Exception:
                logger.debug("Failed to update progress", exc_info=True)

        try:
            engine = ScanEngine(config, on_progress=on_progress)
            result = await engine.run()

            result_dict = result.model_dump()
            summary = _build_summary(result_dict)
            stripped = _strip_records(result_dict)

            finished = datetime.now(timezone.utc).isoformat()
            async with await get_session() as session:
                await session.execute(
                    update(Scan)
                    .where(Scan.id == scan_id)
                    .values(
                        status="completed",
                        progress=100,
                        phase="complete",
                        phase_detail="Scan complete",
                        result_json=json.dumps(stripped),
                        summary_json=json.dumps(summary),
                        log_text=log_capture.get_text(),
                        finished_at=finished,
                    )
                )
                await session.commit()

        except DiscoveryError as e:
            logger.error("Scan %s discovery failed: %s", scan_id, e)
            await self._fail_scan(scan_id, f"Discovery failed: {e}", log_capture.get_text())
        except Exception as e:
            logger.error("Scan %s failed: %s", scan_id, e, exc_info=True)
            await self._fail_scan(scan_id, f"{type(e).__name__}: {e}", log_capture.get_text())
        finally:
            aura_logger.removeHandler(log_capture)

    async def _fail_scan(self, scan_id: str, error: str, log_text: str = "") -> None:
        finished = datetime.now(timezone.utc).isoformat()
        try:
            async with await get_session() as session:
                await session.execute(
                    update(Scan)
                    .where(Scan.id == scan_id)
                    .values(
                        status="failed",
                        error=error,
                        log_text=log_text or None,
                        finished_at=finished,
                    )
                )
                await session.commit()
        except Exception:
            logger.error("Failed to update scan %s as failed", scan_id, exc_info=True)

    async def cancel(self, scan_id: str) -> bool:
        task = self._tasks.get(scan_id)
        if task and not task.done():
            task.cancel()
            finished = datetime.now(timezone.utc).isoformat()
            try:
                async with await get_session() as session:
                    await session.execute(
                        update(Scan)
                        .where(Scan.id == scan_id)
                        .values(
                            status="failed",
                            error="Cancelled by user",
                            finished_at=finished,
                        )
                    )
                    await session.commit()
            except Exception:
                logger.error("Failed to update cancelled scan %s", scan_id, exc_info=True)
            return True
        return False

    # --- Recon jobs ---

    async def start_recon(
        self,
        recon_id: str,
        instance_url: str,
        alias: str,
        access_token: str,
        skip_objects: bool,
        skip_apex: bool,
    ) -> None:
        task = asyncio.create_task(
            self._run_recon(recon_id, instance_url, alias, access_token, skip_objects, skip_apex)
        )
        self._recon_tasks[recon_id] = task

    async def _run_recon(
        self,
        recon_id: str,
        instance_url: str,
        alias: str,
        access_token: str,
        skip_objects: bool,
        skip_apex: bool,
    ) -> None:
        from ..recon import check_sf_cli, sf_login_access_token, enumerate_objects, enumerate_aura_methods

        loop = asyncio.get_event_loop()
        now = datetime.now(timezone.utc).isoformat()

        async with await get_session() as session:
            await session.execute(
                update(Recon)
                .where(Recon.id == recon_id)
                .values(status="running", phase="sf_check", phase_detail="Checking sf CLI...")
            )
            await session.commit()

        try:
            # Phase 1: sf CLI check
            await loop.run_in_executor(None, check_sf_cli)

            # Phase 2: login via access token
            await self._update_recon_phase(recon_id, "login", "Authenticating with access token...")
            username = await loop.run_in_executor(
                None, sf_login_access_token, instance_url, access_token, alias,
            )

            await self._update_recon_phase(recon_id, "login", f"Logged in as {username}", username=username)

            target_org = alias

            # Phase 3: objects
            objects: list[str] = []
            if not skip_objects:
                await self._update_recon_phase(recon_id, "objects", "Enumerating sObjects...")
                objects = await loop.run_in_executor(None, enumerate_objects, target_org)
                await self._update_recon_phase(recon_id, "objects", f"Found {len(objects)} objects")

            # Phase 4: apex
            apex: list[str] = []
            if not skip_apex:
                await self._update_recon_phase(recon_id, "apex", "Enumerating @AuraEnabled methods...")
                apex = await loop.run_in_executor(None, enumerate_aura_methods, target_org)
                await self._update_recon_phase(recon_id, "apex", f"Found {len(apex)} methods")

            # Phase 5: complete
            finished = datetime.now(timezone.utc).isoformat()
            async with await get_session() as session:
                await session.execute(
                    update(Recon)
                    .where(Recon.id == recon_id)
                    .values(
                        status="completed",
                        phase="complete",
                        phase_detail="Recon complete",
                        objects_json=json.dumps(objects) if objects else None,
                        apex_json=json.dumps(apex) if apex else None,
                        finished_at=finished,
                    )
                )
                await session.commit()

        except (ReconError, Exception) as e:
            logger.error("Recon %s failed: %s", recon_id, e, exc_info=True)
            finished = datetime.now(timezone.utc).isoformat()
            try:
                async with await get_session() as session:
                    await session.execute(
                        update(Recon)
                        .where(Recon.id == recon_id)
                        .values(
                            status="failed",
                            error=f"{type(e).__name__}: {e}",
                            finished_at=finished,
                        )
                    )
                    await session.commit()
            except Exception:
                logger.error("Failed to update recon %s as failed", recon_id, exc_info=True)

    async def _update_recon_phase(
        self, recon_id: str, phase: str, detail: str, username: str | None = None,
    ) -> None:
        try:
            values: dict[str, Any] = {"phase": phase, "phase_detail": detail}
            if username is not None:
                values["username"] = username
            async with await get_session() as session:
                await session.execute(
                    update(Recon).where(Recon.id == recon_id).values(**values)
                )
                await session.commit()
        except Exception:
            logger.debug("Failed to update recon phase", exc_info=True)

    async def cancel_recon(self, recon_id: str) -> bool:
        task = self._recon_tasks.get(recon_id)
        if task and not task.done():
            task.cancel()
            # Mark as failed in DB so it doesn't stay "running" forever
            finished = datetime.now(timezone.utc).isoformat()
            try:
                async with await get_session() as session:
                    await session.execute(
                        update(Recon)
                        .where(Recon.id == recon_id)
                        .values(
                            status="failed",
                            error="Cancelled by user",
                            finished_at=finished,
                        )
                    )
                    await session.commit()
            except Exception:
                logger.error("Failed to update cancelled recon %s", recon_id, exc_info=True)
            return True
        return False
