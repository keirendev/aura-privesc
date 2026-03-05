"""Salesforce CLI recon: enumerate objects and @AuraEnabled Apex methods."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .exceptions import ReconError

logger = logging.getLogger(__name__)

SF_CLI_INSTALL_URL = "https://developer.salesforce.com/tools/salesforcecli"


@dataclass
class ReconResult:
    instance_url: str
    username: str | None = None
    objects: list[str] = field(default_factory=list)
    apex_methods: list[str] = field(default_factory=list)
    objects_file: Path | None = None
    apex_file: Path | None = None


def check_sf_cli() -> str:
    """Verify the Salesforce CLI is installed and return its path."""
    path = shutil.which("sf")
    if not path:
        raise ReconError(
            f"Salesforce CLI (sf) not found on PATH. "
            f"Install it from: {SF_CLI_INSTALL_URL}"
        )
    return path


def sf_login(instance_url: str, alias: str | None = None) -> str:
    """Open browser auth flow and return the authenticated username."""
    cmd = [
        "sf", "org", "login", "web",
        "--instance-url", instance_url,
        "--json",
    ]
    if alias:
        cmd.extend(["--alias", alias])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as e:
        raise ReconError("Browser login timed out after 120s") from e

    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise ReconError(f"sf org login web failed: {stderr}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ReconError(f"Failed to parse sf login output: {e}") from e

    username = data.get("result", {}).get("username")
    if not username:
        raise ReconError(f"No username in login response: {proc.stdout[:500]}")

    return username


def enumerate_objects(target_org: str) -> list[str]:
    """List all sObject API names in the org via sf CLI."""
    cmd = [
        "sf", "sobject", "list",
        "--sobject-type", "all",
        "--target-org", target_org,
        "--json",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as e:
        raise ReconError("sf sobject list timed out") from e

    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise ReconError(f"sf sobject list failed: {stderr}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ReconError(f"Failed to parse sobject list output: {e}") from e

    objects = data.get("result", [])
    if not isinstance(objects, list):
        raise ReconError(f"Unexpected sobject list format: {type(objects)}")

    return sorted(objects)


def parse_aura_enabled_methods(apex_body: str) -> list[str]:
    """Extract method names following @AuraEnabled annotations."""
    pattern = r"@AuraEnabled(?:\s*\([^)]*\))?\s+[^(]+\b(\w+)\s*\("
    return re.findall(pattern, apex_body)


def enumerate_aura_methods(target_org: str) -> list[str]:
    """Query all @AuraEnabled methods via the Tooling API."""
    soql = (
        "SELECT Name, Body FROM ApexClass "
        "WHERE Body LIKE '%@AuraEnabled%' AND NamespacePrefix = null"
    )
    cmd = [
        "sf", "data", "query",
        "--query", soql,
        "--use-tooling-api",
        "--target-org", target_org,
        "--json",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as e:
        raise ReconError("Tooling API query timed out") from e

    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise ReconError(f"Tooling API query failed: {stderr}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ReconError(f"Failed to parse query output: {e}") from e

    records = data.get("result", {}).get("records", [])
    methods: list[str] = []

    for record in records:
        class_name = record.get("Name", "")
        body = record.get("Body", "")
        if not class_name or not body:
            continue
        for method_name in parse_aura_enabled_methods(body):
            methods.append(f"{class_name}.{method_name}")

    return sorted(methods)


def _host_slug(url: str) -> str:
    """Convert a URL hostname to a filename-safe slug."""
    hostname = urlparse(url).hostname or "unknown"
    return hostname.replace(".", "-")


def save_results(recon: ReconResult, output_dir: str = ".") -> tuple[Path | None, Path | None]:
    """Write recon results to files compatible with _load_lines()."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = _host_slug(recon.instance_url)

    objects_path: Path | None = None
    apex_path: Path | None = None

    if recon.objects:
        objects_path = out / f"recon-objects-{slug}.txt"
        with open(objects_path, "w") as f:
            f.write(f"# Salesforce objects for {recon.instance_url}\n")
            f.write(f"# Enumerated via sf CLI as {recon.username}\n")
            f.write(f"# {len(recon.objects)} objects\n")
            for obj in recon.objects:
                f.write(f"{obj}\n")
        recon.objects_file = objects_path

    if recon.apex_methods:
        apex_path = out / f"recon-apex-{slug}.txt"
        with open(apex_path, "w") as f:
            f.write(f"# @AuraEnabled Apex methods for {recon.instance_url}\n")
            f.write(f"# Enumerated via sf CLI as {recon.username}\n")
            f.write(f"# {len(recon.apex_methods)} methods\n")
            for method in recon.apex_methods:
                f.write(f"{method}\n")
        recon.apex_file = apex_path

    return objects_path, apex_path
