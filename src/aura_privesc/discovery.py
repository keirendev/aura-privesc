"""Auto-discover Aura endpoint path, fwuid, app name, and aura.context."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import unquote

from .client import AuraClient
from .config import ENDPOINT_PATHS
from .exceptions import DiscoveryError
from .models import DiscoveryInfo

logger = logging.getLogger(__name__)


async def discover_endpoint(client: AuraClient, base_url: str) -> str:
    """Try each candidate endpoint path and return the first valid one."""
    base = base_url.rstrip("/")
    for path in ENDPOINT_PATHS:
        url = base + path
        logger.debug("Probing endpoint: %s", url)
        resp = await client.probe(url)
        if resp is None:
            continue
        # Valid Aura responses are JSON or contain aura-specific markers
        text = resp.text
        if resp.status_code in (200, 401) and (
            _looks_like_aura(text) or resp.status_code == 200
        ):
            # Confirm it's actually Aura (not a generic 200 HTML page)
            if _looks_like_aura(text):
                logger.info("Found Aura endpoint: %s", path)
                return path
    raise DiscoveryError(
        "Could not discover Aura endpoint. Try specifying --endpoint manually."
    )


def _looks_like_aura(text: str) -> bool:
    """Check if response text looks like a valid Aura API response."""
    if not text or not text.strip():
        return False
    text = text.strip()
    # JSON response with actions array
    if text.startswith("{") or text.startswith("/*"):
        for marker in ("actions", "aura:clientOutOfSync", "aura:", "exceptionEvent", "returnValue"):
            if marker in text:
                return True
    return False


async def discover_context(client: AuraClient, base_url: str) -> dict[str, Any]:
    """Fetch the community page HTML and extract aura.context / fwuid / app."""
    html = await client.get_page(base_url)
    if not html:
        # Try common community sub-paths
        for path in ["/s", "/s/login", ""]:
            html = await client.get_page(base_url.rstrip("/") + path)
            if html:
                break

    context: dict[str, Any] = {}
    fwuid = None
    app_name = None

    if html:
        fwuid = _extract_fwuid(html)
        app_name = _extract_app_name(html)
        context = _extract_context(html)

    return {
        "fwuid": fwuid,
        "app_name": app_name,
        "context": context,
    }


def _extract_fwuid(html: str) -> str | None:
    """Extract fwuid from page HTML or inline JSON."""
    patterns = [
        r'"fwuid"\s*:\s*"([^"]+)"',
        r"fwuid=([A-Za-z0-9_-]+)",
        r'auraConfig\["fw"\]\s*=\s*"([^"]+)"',
    ]
    # Try raw HTML first, then URL-decoded (fwuid is often in encoded JSON)
    for text in (html, unquote(html)):
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    return None


def _extract_app_name(html: str) -> str | None:
    """Extract the Aura app name from page HTML."""
    patterns = [
        r'"app"\s*:\s*"([^"]+)"',
        r'"componentDef"\s*:\s*"([^"]+App)"',
    ]
    for text in (html, unquote(html)):
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    return None


def _extract_context(html: str) -> dict[str, Any]:
    """Extract aura.context JSON from the page."""
    # Look for inline aura context
    patterns = [
        r"aura\.context\s*=\s*({[^;]+});",
        r'"auraContext"\s*:\s*({.+?})\s*[,}]',
    ]
    for text in (html, unquote(html)):
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
    return {}


async def extract_js_urls(client: AuraClient, base_url: str) -> list[str]:
    """Find JS file URLs in community page HTML (for Apex discovery)."""
    html = await client.get_page(base_url)
    if not html:
        return []

    js_urls = []
    for match in re.finditer(r'src="([^"]+\.js[^"]*)"', html):
        url = match.group(1)
        if url.startswith("/"):
            url = base_url.rstrip("/") + url
        elif not url.startswith("http"):
            url = base_url.rstrip("/") + "/" + url
        js_urls.append(url)
    return js_urls


async def run_discovery(
    client: AuraClient,
    base_url: str,
    *,
    manual_endpoint: str | None = None,
    manual_context: str | None = None,
) -> DiscoveryInfo:
    """Full discovery: endpoint, fwuid, context. Returns DiscoveryInfo and updates client."""
    # Discover or use manual endpoint
    if manual_endpoint:
        endpoint = manual_endpoint
    else:
        endpoint = await discover_endpoint(client, base_url)

    client.endpoint = endpoint

    # Discover context from page HTML
    ctx_info = await discover_context(client, base_url)

    if manual_context:
        try:
            parsed = json.loads(manual_context)
            client.context = parsed
        except json.JSONDecodeError:
            logger.warning("Could not parse manual --context JSON, using discovered context")
    elif ctx_info["context"]:
        client.context = ctx_info["context"]

    if ctx_info["fwuid"]:
        client.fwuid = ctx_info["fwuid"]

    if ctx_info["app_name"]:
        client.app_name = ctx_info["app_name"]

    # Try a getConfigData call to validate and potentially recover fwuid
    try:
        await client.call_action("getConfigData")
    except Exception as e:
        logger.debug("Initial getConfigData failed (may be normal): %s", e)

    mode = "authenticated" if client.token else "guest"

    return DiscoveryInfo(
        endpoint=endpoint,
        fwuid=client.fwuid,
        app_name=client.app_name,
        mode=mode,
    )
