"""JSON serialization output."""

from __future__ import annotations

import json
import sys

from ..models import ApexMethodStatus, ScanResult


def render(result: ScanResult, validated_only: bool = False) -> None:
    """Serialize ScanResult to JSON on stdout, optionally filtering to validated findings."""
    if validated_only:
        data = result.model_dump()
        data["objects"] = [
            o for o in data["objects"]
            if not o.get("accessible") or o.get("validated") is True
        ]
        data["apex_results"] = [
            a for a in data["apex_results"]
            if a.get("status") != ApexMethodStatus.CALLABLE.value or a.get("validated") is True
        ]
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    else:
        sys.stdout.write(result.model_dump_json(indent=2) + "\n")
