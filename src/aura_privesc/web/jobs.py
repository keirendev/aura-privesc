"""Job manager — runs scan jobs as asyncio tasks."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update

from ..engine import ScanConfig, ScanEngine
from ..exceptions import DiscoveryError
from .db import Scan, get_session

logger = logging.getLogger(__name__)


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
    }


class JobManager:
    """Runs scan jobs as asyncio tasks within the FastAPI event loop."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    @property
    def running_scan_id(self) -> str | None:
        for scan_id, task in self._tasks.items():
            if not task.done():
                return scan_id
        return None

    async def start_scan(self, scan_id: str, config: ScanConfig) -> None:
        task = asyncio.create_task(self._run_scan(scan_id, config))
        self._tasks[scan_id] = task

    async def _run_scan(self, scan_id: str, config: ScanConfig) -> None:
        now = datetime.now(timezone.utc).isoformat()

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
                "discovery": 5,
                "user_context": 10,
                "enumeration": 50,
                "crud_test": 65,
                "apex": 80,
                "graphql": 95,
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
                        finished_at=finished,
                    )
                )
                await session.commit()

        except DiscoveryError as e:
            await self._fail_scan(scan_id, f"Discovery failed: {e}")
        except Exception as e:
            logger.error("Scan %s failed: %s", scan_id, e, exc_info=True)
            await self._fail_scan(scan_id, f"{type(e).__name__}: {e}")

    async def _fail_scan(self, scan_id: str, error: str) -> None:
        finished = datetime.now(timezone.utc).isoformat()
        try:
            async with await get_session() as session:
                await session.execute(
                    update(Scan)
                    .where(Scan.id == scan_id)
                    .values(
                        status="failed",
                        error=error,
                        finished_at=finished,
                    )
                )
                await session.commit()
        except Exception:
            logger.error("Failed to update scan %s as failed", scan_id, exc_info=True)

    def cancel(self, scan_id: str) -> bool:
        task = self._tasks.get(scan_id)
        if task and not task.done():
            task.cancel()
            return True
        return False
