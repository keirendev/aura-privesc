"""AuraClient: async HTTP client implementing the Aura protocol envelope."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import urljoin

import httpx

from .config import DESCRIPTORS
from .exceptions import (
    AuraRequestError,
    ClientOutOfSyncError,
    InvalidSessionError,
)

logger = logging.getLogger(__name__)


class AuraClient:
    """Async HTTP client for Salesforce Aura API calls."""

    def __init__(
        self,
        base_url: str,
        endpoint: str,
        *,
        token: str | None = None,
        fwuid: str | None = None,
        app_name: str | None = None,
        context: dict[str, Any] | None = None,
        concurrency: int = 5,
        delay_ms: int = 0,
        timeout: int = 30,
        proxy: str | None = None,
        insecure: bool = False,
        verbose: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.token = token
        self.fwuid = fwuid
        self.app_name = app_name or "siteforce:communityApp"
        self.context = context or {}
        self.delay_ms = delay_ms
        self.verbose = verbose
        self.proxy = proxy
        self.insecure = insecure
        self._semaphore = asyncio.Semaphore(concurrency)

        transport_kwargs: dict[str, Any] = {}
        if proxy:
            transport_kwargs["proxy"] = proxy
        if insecure:
            transport_kwargs["verify"] = False

        self._http = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            **transport_kwargs,
        )

    @property
    def aura_url(self) -> str:
        return self.base_url + self.endpoint

    @property
    def aura_token(self) -> str:
        return self.token or "undefined"

    def _build_context(self) -> str:
        ctx = dict(self.context)
        if self.fwuid:
            ctx["fwuid"] = self.fwuid
        if "mode" not in ctx:
            ctx["mode"] = "PROD"
        if "app" not in ctx:
            ctx["app"] = self.app_name
        return json.dumps(ctx)

    def _build_message(self, actions: list[dict[str, Any]]) -> str:
        return json.dumps({"actions": actions})

    def _build_action(
        self,
        descriptor: str,
        params: dict[str, Any] | None = None,
        action_id: str = "0",
    ) -> dict[str, Any]:
        return {
            "id": action_id,
            "descriptor": descriptor,
            "callingDescriptor": "UNKNOWN",
            "params": params or {},
        }

    async def request(
        self,
        descriptor: str,
        params: dict[str, Any] | None = None,
        *,
        retry_sync: bool = True,
    ) -> dict[str, Any]:
        """Send an Aura action request, handling clientOutOfSync automatically."""
        async with self._semaphore:
            if self.delay_ms > 0:
                await asyncio.sleep(self.delay_ms / 1000.0)

            action = self._build_action(descriptor, params)
            data = {
                "message": self._build_message([action]),
                "aura.context": self._build_context(),
                "aura.token": self.aura_token,
            }

            if self.verbose:
                logger.info("POST %s | descriptor=%s params=%s", self.aura_url, descriptor, params)

            try:
                resp = await self._http.post(self.aura_url, data=data)
            except httpx.HTTPError as e:
                raise AuraRequestError(f"HTTP error: {e}") from e

            raw_text = resp.text

            if self.verbose:
                logger.info("Response %d: %s", resp.status_code, raw_text[:500])

            if resp.status_code == 401:
                raise InvalidSessionError("HTTP 401 — token is expired or invalid")

            # Aura can return 200 with an error payload
            if not raw_text.strip():
                raise AuraRequestError(
                    "Empty response", status_code=resp.status_code, raw=raw_text
                )

            # Handle non-JSON responses (HTML error pages, etc.)
            try:
                body = resp.json()
            except (json.JSONDecodeError, ValueError):
                # Check for clientOutOfSync in raw text
                if "clientOutOfSync" in raw_text and retry_sync:
                    new_fwuid = self._extract_fwuid_from_error(raw_text)
                    if new_fwuid:
                        self.fwuid = new_fwuid
                        return await self.request(descriptor, params, retry_sync=False)
                raise AuraRequestError(
                    "Non-JSON response", status_code=resp.status_code, raw=raw_text[:500]
                )

            # Check for Aura-level errors
            if isinstance(body, dict):
                # aura:clientOutOfSync
                if body.get("exceptionEvent"):
                    desc = body.get("event", {}).get("descriptor", "")
                    if "clientOutOfSync" in desc and retry_sync:
                        new_fwuid = body.get("event", {}).get("attributes", {}).get(
                            "values", {}
                        ).get("fwuid")
                        if new_fwuid:
                            self.fwuid = new_fwuid
                            return await self.request(descriptor, params, retry_sync=False)
                        raise ClientOutOfSyncError()

                    if "invalidSession" in desc:
                        raise InvalidSessionError("Aura session is invalid or expired")

            return body

    def _extract_fwuid_from_error(self, raw: str) -> str | None:
        """Try to pull a new fwuid from an error response body."""
        import re

        match = re.search(r'"fwuid"\s*:\s*"([^"]+)"', raw)
        return match.group(1) if match else None

    async def call_action(
        self,
        action_name: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a named action from DESCRIPTORS."""
        descriptor = DESCRIPTORS[action_name]
        return await self.request(descriptor, params)

    async def call_apex(
        self,
        controller: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a custom Apex controller method."""
        descriptor = f"apex://{controller}/ACTION${method}"
        return await self.request(descriptor, params)

    async def probe(self, url: str) -> httpx.Response | None:
        """Send a lightweight probe POST to check if endpoint is valid."""
        try:
            action = self._build_action(DESCRIPTORS["getConfigData"])
            data = {
                "message": self._build_message([action]),
                "aura.context": self._build_context(),
                "aura.token": self.aura_token,
            }
            resp = await self._http.post(url, data=data)
            return resp
        except httpx.HTTPError:
            return None

    async def get_page(self, url: str) -> str | None:
        """Fetch an HTML page (for fwuid / JS discovery)."""
        try:
            resp = await self._http.get(url)
            return resp.text if resp.status_code == 200 else None
        except httpx.HTTPError:
            return None

    async def close(self):
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
