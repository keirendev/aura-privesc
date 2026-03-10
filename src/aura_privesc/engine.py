"""Scan engine — decoupled from CLI output."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .apex import build_apex_list, discover_apex_from_js, test_apex_methods
from .client import AuraClient
from .crud import auto_crud_test_objects
from .discovery import run_discovery
from .enumerator import build_object_list, enumerate_objects
from .exceptions import DiscoveryError
from .graphql import enumerate_graphql, probe_graphql
from .models import ScanResult
from .permissions import check_soql_capability, get_config_objects, get_user_info

logger = logging.getLogger(__name__)

# Callback signature: (phase_name, current, total, detail_message) -> None
ProgressCallback = Callable[[str, int, int, str], Awaitable[None]]


async def _noop_progress(phase: str, current: int, total: int, detail: str) -> None:
    pass


@dataclass
class ScanConfig:
    """All scan parameters — replaces the many kwargs to _run()."""

    url: str
    token: str | None = None
    sid: str | None = None
    manual_context: str | None = None
    manual_endpoint: str | None = None
    objects_file: str | None = None
    apex_file: str | None = None
    objects_list: list[str] | None = None
    apex_list: list[str] | None = None
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
    crm_domain: str | None = None


class _EngineProgress:
    """Adapter that bridges Rich Progress bars to ProgressCallback."""

    def __init__(self, callback: ProgressCallback, phase: str):
        self._callback = callback
        self._phase = phase
        self._current = 0
        self._total = 0

    async def set_total(self, total: int) -> None:
        self._total = total
        self._current = 0
        await self._callback(self._phase, 0, total, "")

    async def advance(self, n: int = 1) -> None:
        self._current += n
        await self._callback(self._phase, self._current, self._total, "")


class _ProgressAdapter:
    """Mimics rich.progress.Progress interface for enumerate_objects/test_apex_methods."""

    def __init__(self, engine_progress: _EngineProgress):
        self._ep = engine_progress
        self._tasks: dict[int, int] = {}
        self._next_id = 0

    def add_task(self, description: str, total: int = 0) -> int:
        tid = self._next_id
        self._next_id += 1
        self._tasks[tid] = 0
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(self._ep.set_total(total))
        return tid

    def update(self, task_id: int, advance: int = 0, **kwargs: Any) -> None:
        if advance:
            import asyncio
            loop = asyncio.get_event_loop()
            loop.create_task(self._ep.advance(advance))


class ScanEngine:
    """Runs all scan phases, reporting progress via callback."""

    def __init__(
        self,
        config: ScanConfig,
        on_progress: ProgressCallback | None = None,
    ):
        self.config = config
        self.on_progress = on_progress or _noop_progress

    async def run(self) -> ScanResult:
        cfg = self.config
        base_url = cfg.url.rstrip("/")
        result = ScanResult(target_url=base_url)

        async with AuraClient(
            base_url=base_url,
            endpoint="/s/sfsites/aura",
            token=cfg.token,
            concurrency=cfg.concurrency,
            delay_ms=cfg.delay,
            timeout=cfg.timeout,
            proxy=cfg.proxy,
            insecure=cfg.insecure,
            verbose=cfg.verbose,
            sid=cfg.sid,
        ) as client:
            # Phase 1: Discovery
            await self.on_progress("discovery", 0, 0, "Discovering Aura endpoint...")
            discovery = await run_discovery(
                client,
                base_url,
                manual_endpoint=cfg.manual_endpoint,
                manual_context=cfg.manual_context,
            )
            result.discovery = discovery
            result.aura_url = client.aura_url
            result.aura_token = client.aura_token
            result.aura_context = client._build_context()
            result.sid = client.sid
            await self.on_progress("discovery", 1, 1, "Discovery complete")

            # Phase 2: User context + SOQL check
            await self.on_progress("user_context", 0, 0, "Checking connectivity & user context...")
            result.user_info = await get_user_info(client)
            result.soql_capable = await check_soql_capability(client)
            config_objects = await get_config_objects(client)

            # REST API checks (guest and authenticated)
            from .rest_api import check_rest_api_access
            result.rest_api = await check_rest_api_access(client, crm_domain=cfg.crm_domain)

            await self.on_progress("user_context", 1, 1, "User context complete")

            # Phase 3: Object enumeration
            user_objects = _load_lines(cfg.objects_file) if cfg.objects_file else cfg.objects_list
            all_objects = build_object_list(config_objects, user_objects)

            ep3 = _EngineProgress(self.on_progress, "enumeration")
            progress3 = _ProgressAdapter(ep3)
            tid3 = progress3.add_task("Enumerating objects", total=len(all_objects))
            result.objects = await enumerate_objects(
                client,
                all_objects,
                skip_crud=cfg.skip_crud,
                skip_records=cfg.skip_records,
                skip_validation=cfg.skip_validation,
                progress=progress3,
                task_id=tid3,
            )

            # Phase 3b: Automated CRUD write testing
            if not cfg.skip_crud_test:
                writable = [
                    o for o in result.objects
                    if o.accessible and o.crud.readable and o.crud.has_write
                ]
                if writable:
                    ep3b = _EngineProgress(self.on_progress, "crud_test")
                    progress3b = _ProgressAdapter(ep3b)
                    tid3b = progress3b.add_task("Testing CRUD writes", total=len(writable))
                    await auto_crud_test_objects(
                        client, writable, progress=progress3b, task_id=tid3b,
                    )

            # Phase 4: Apex testing
            if not cfg.skip_apex:
                await self.on_progress("apex", 0, 0, "Discovering Apex controllers...")
                discovered_apex = await discover_apex_from_js(client, base_url)
                user_apex = _load_lines(cfg.apex_file) if cfg.apex_file else cfg.apex_list
                apex_list = build_apex_list(discovered_apex, user_apex)

                if apex_list:
                    ep4 = _EngineProgress(self.on_progress, "apex")
                    progress4 = _ProgressAdapter(ep4)
                    tid4 = progress4.add_task("Testing Apex methods", total=len(apex_list))
                    result.apex_results = await test_apex_methods(
                        client, apex_list, skip_validation=cfg.skip_validation,
                        progress=progress4, task_id=tid4,
                    )

            # Phase 5: GraphQL enumeration
            if not cfg.skip_graphql:
                await self.on_progress("graphql", 0, 0, "Probing GraphQL...")
                gql_available = await probe_graphql(client)
                result.graphql_available = gql_available

                if gql_available:
                    gql_objects = [o.name for o in result.objects if o.accessible]
                    if gql_objects:
                        ep5 = _EngineProgress(self.on_progress, "graphql")
                        progress5 = _ProgressAdapter(ep5)
                        tid5 = progress5.add_task("GraphQL enumeration", total=len(gql_objects))
                        result.graphql_results = await enumerate_graphql(
                            client, gql_objects, progress=progress5, task_id=tid5,
                        )

        await self.on_progress("complete", 1, 1, "Scan complete")
        return result


def _load_lines(path: str) -> list[str]:
    """Load non-empty, non-comment lines from a file."""
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines
