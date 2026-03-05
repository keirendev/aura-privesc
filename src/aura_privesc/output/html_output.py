"""Self-contained HTML report with embedded CSS."""

from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from ..models import ApexMethodStatus, RiskLevel, ScanResult

_CSS = """\
:root{--bg:#1a1a2e;--card:#16213e;--border:#0f3460;--text:#e0e0e0;--muted:#888;
--green:#00d26a;--red:#f44336;--yellow:#ffc107;--cyan:#00bcd4;--purple:#9c27b0}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;line-height:1.6;padding:2rem}
.container{max-width:1100px;margin:0 auto}
h1{color:var(--cyan);margin-bottom:.5rem}
h2{color:var(--cyan);margin:2rem 0 1rem;border-bottom:1px solid var(--border);padding-bottom:.5rem}
.subtitle{color:var(--muted);margin-bottom:2rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1.5rem;margin-bottom:1.5rem}
table{width:100%;border-collapse:collapse;margin-bottom:1rem}
th{text-align:left;padding:.6rem .8rem;background:var(--border);color:var(--cyan);font-weight:600}
td{padding:.5rem .8rem;border-bottom:1px solid #1a1a3e}
tr:hover{background:#1a1a3e}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.8rem;font-weight:600;text-transform:uppercase}
.badge-critical{background:#b71c1c;color:#fff}
.badge-high{background:#e65100;color:#fff}
.badge-medium{background:#f57f17;color:#000}
.badge-low{background:#1b5e20;color:#fff}
.badge-info{background:#37474f;color:#ccc}
.check{color:var(--green)}
.fail{color:var(--red)}
.skip{color:var(--muted)}
.status-callable{color:var(--green)}
.status-denied{color:var(--red)}
.status-not_found{color:var(--muted)}
.status-error{color:var(--yellow)}
details{margin-bottom:.5rem}
summary{cursor:pointer;padding:.5rem;background:var(--border);border-radius:4px;font-weight:600}
summary:hover{background:#1a3a6e}
pre{background:#0d1117;padding:1rem;border-radius:4px;overflow-x:auto;font-size:.85rem;margin:.5rem 0;white-space:pre-wrap;word-break:break-all}
code{color:var(--green)}
.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1.5rem}
.stat{text-align:center;padding:1rem;background:var(--card);border:1px solid var(--border);border-radius:8px}
.stat-number{font-size:2rem;font-weight:700;color:var(--cyan)}
.stat-label{color:var(--muted);font-size:.9rem}
footer{text-align:center;color:var(--muted);margin-top:3rem;padding-top:1rem;border-top:1px solid var(--border);font-size:.85rem}
"""

_CHECK = "\u2713"
_CROSS = "\u2717"
_DASH = "\u2014"


def _esc(text: str | None) -> str:
    return html.escape(str(text)) if text else ""


def _badge(risk: RiskLevel) -> str:
    return f'<span class="badge badge-{risk.value}">{risk.value.upper()}</span>'


def _check_or_cross(val: bool) -> str:
    if val:
        return f'<span class="check">{_CHECK}</span>'
    return f'<span class="fail">{_CROSS}</span>'


def _op_cell(cv, op: str) -> str:
    result = getattr(cv, op, None)
    if result is None:
        return f'<span class="skip">{_DASH}</span>'
    return _check_or_cross(result.success)


def _build_header(result: ScanResult, timestamp: str) -> str:
    target = _esc(result.target_url)
    mode = _esc(result.discovery.mode) if result.discovery else "unknown"
    return f"""
<h1>aura-privesc Report</h1>
<p class="subtitle">Target: <strong>{target}</strong> &mdash; Mode: {mode} &mdash; {_esc(timestamp)}</p>
"""


def _build_summary(result: ScanResult, validated_only: bool) -> str:
    accessible = result.validated_objects if validated_only else result.accessible_objects
    critical = [o for o in accessible if o.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)]
    callable_apex = [
        r for r in result.apex_results
        if r.status == ApexMethodStatus.CALLABLE and (not validated_only or r.validated is True)
    ]
    crud_validated = result.crud_validated_objects if result.interactive_mode else []

    return f"""
<h2>Executive Summary</h2>
<div class="summary-grid">
  <div class="stat"><div class="stat-number">{len(result.objects)}</div><div class="stat-label">Objects Scanned</div></div>
  <div class="stat"><div class="stat-number">{len(accessible)}</div><div class="stat-label">Accessible</div></div>
  <div class="stat"><div class="stat-number" style="color:var(--red)">{len(critical)}</div><div class="stat-label">Critical / High</div></div>
  <div class="stat"><div class="stat-number">{len(callable_apex)}</div><div class="stat-label">Callable Apex</div></div>
  {"<div class='stat'><div class='stat-number'>" + str(len(crud_validated)) + "</div><div class='stat-label'>CRUD Validated</div></div>" if result.interactive_mode else ""}
</div>
"""


def _build_objects_table(result: ScanResult, validated_only: bool) -> str:
    accessible = result.validated_objects if validated_only else result.accessible_objects
    if not accessible:
        return "<h2>Object Findings</h2><p>No accessible objects found.</p>"

    risk_order = {RiskLevel.CRITICAL: 0, RiskLevel.HIGH: 1, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 3, RiskLevel.INFO: 4}
    accessible.sort(key=lambda o: (risk_order.get(o.risk, 99), o.name))

    rows = ""
    for obj in accessible:
        c = obj.crud
        count = str(obj.record_count) if obj.record_count is not None else "-"
        rows += f"""<tr>
  <td>{_esc(obj.name)}</td>
  <td>{_check_or_cross(c.readable)}</td>
  <td>{_check_or_cross(c.createable)}</td>
  <td>{_check_or_cross(c.updateable)}</td>
  <td>{_check_or_cross(c.deletable)}</td>
  <td>{_check_or_cross(c.queryable)}</td>
  <td>{count}</td>
  <td>{_badge(obj.risk)}</td>
</tr>"""

    return f"""
<h2>Object Findings ({len(accessible)})</h2>
<div class="card">
<table>
<tr><th>Object</th><th>R</th><th>C</th><th>U</th><th>D</th><th>Q</th><th>Records</th><th>Risk</th></tr>
{rows}
</table>
</div>
"""


def _build_crud_validation(result: ScanResult) -> str:
    if not result.interactive_mode:
        return ""

    validated = result.crud_validated_objects
    if not validated:
        return "<h2>CRUD Validation Results</h2><p>No CRUD validations performed.</p>"

    rows = ""
    for obj in validated:
        cv = obj.crud_validation
        assert cv is not None
        proven = ", ".join(cv.proven_operations) if cv.proven_operations else "<span class='skip'>none</span>"
        rows += f"""<tr>
  <td>{_esc(obj.name)}</td>
  <td>{_op_cell(cv, 'read')}</td>
  <td>{_op_cell(cv, 'create')}</td>
  <td>{_op_cell(cv, 'update')}</td>
  <td>{_op_cell(cv, 'delete')}</td>
  <td>{proven}</td>
</tr>"""

    return f"""
<h2>CRUD Validation Results ({len(validated)})</h2>
<div class="card">
<table>
<tr><th>Object</th><th>Read</th><th>Create</th><th>Update</th><th>Delete</th><th>Proven Ops</th></tr>
{rows}
</table>
</div>
"""


def _build_apex_table(result: ScanResult, validated_only: bool) -> str:
    if not result.apex_results:
        return ""

    if validated_only:
        display = [
            r for r in result.apex_results
            if r.status != ApexMethodStatus.CALLABLE or r.validated is True
        ]
    else:
        display = list(result.apex_results)

    if not display:
        return ""

    order = {ApexMethodStatus.CALLABLE: 0, ApexMethodStatus.DENIED: 1, ApexMethodStatus.ERROR: 2, ApexMethodStatus.NOT_FOUND: 3}
    display.sort(key=lambda r: (order.get(r.status, 99), r.controller_method))

    rows = ""
    for r in display:
        status_cls = f"status-{r.status.value}"
        rows += f"""<tr>
  <td>{_esc(r.controller_method)}</td>
  <td><span class="{status_cls}">{_esc(r.status.value.upper())}</span></td>
  <td>{_esc(r.message or '')}</td>
</tr>"""

    callable_count = sum(1 for r in display if r.status == ApexMethodStatus.CALLABLE)
    return f"""
<h2>Apex Controllers ({callable_count} callable / {len(display)} tested)</h2>
<div class="card">
<table>
<tr><th>Controller.Method</th><th>Status</th><th>Message</th></tr>
{rows}
</table>
</div>
"""


def _build_proofs(result: ScanResult, validated_only: bool) -> str:
    if validated_only:
        proof_objects = result.validated_objects
        proof_apex = [
            a for a in result.apex_results
            if a.proof and a.status in (ApexMethodStatus.CALLABLE, ApexMethodStatus.DENIED) and a.validated is True
        ]
    else:
        proof_objects = result.accessible_objects
        proof_apex = [
            a for a in result.apex_results
            if a.proof and a.status in (ApexMethodStatus.CALLABLE, ApexMethodStatus.DENIED)
        ]

    # Also collect CRUD validation proofs
    crud_proofs: list[tuple[str, str, str]] = []
    for obj in result.objects:
        cv = obj.crud_validation
        if cv is None or cv.skipped:
            continue
        for op_name in ("read", "create", "update", "delete"):
            op = getattr(cv, op_name, None)
            if op and op.proof:
                label = f"{obj.name} — {op_name.upper()}"
                status = "SUCCESS" if op.success else f"FAILED: {op.error or 'unknown'}"
                crud_proofs.append((label, status, op.proof))

    has_any = any(o.proof for o in proof_objects) or bool(proof_apex) or bool(crud_proofs)
    if not has_any:
        return ""

    sections = ""

    for obj in proof_objects:
        if not obj.proof:
            continue
        sections += f"""<details>
<summary>{_esc(obj.name)} ({obj.risk.value.upper()}) — Metadata</summary>
<pre><code>{_esc(obj.proof)}</code></pre>
</details>"""
        if obj.proof_records:
            sections += f"""<details>
<summary>{_esc(obj.name)} ({obj.risk.value.upper()}) — Records</summary>
<pre><code>{_esc(obj.proof_records)}</code></pre>
</details>"""

    for apex in proof_apex:
        label = f"{apex.controller_method} ({apex.status.value.upper()})"
        sections += f"""<details>
<summary>{_esc(label)}</summary>
<pre><code>{_esc(apex.proof)}</code></pre>
</details>"""

    if crud_proofs:
        for label, status, proof in crud_proofs:
            sections += f"""<details>
<summary>{_esc(label)} — {_esc(status)}</summary>
<pre><code>{_esc(proof)}</code></pre>
</details>"""

    return f"""
<h2>Proof Commands</h2>
<div class="card">
{sections}
</div>
"""


def _build_footer(timestamp: str) -> str:
    return f"""
<footer>
  Generated by <strong>aura-privesc</strong> at {_esc(timestamp)}
</footer>
"""


def write_report(
    result: ScanResult,
    *,
    validated_only: bool = False,
    output_dir: str = ".",
) -> str:
    """Generate a self-contained HTML report and write it to disk.

    Returns the path to the written file.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    file_ts = now.strftime("%Y%m%d_%H%M%S")

    host = urlparse(result.target_url).hostname or "unknown"
    filename = f"aura-report-{host}-{file_ts}.html"
    filepath = os.path.join(output_dir, filename)

    body = "".join([
        _build_header(result, timestamp),
        _build_summary(result, validated_only),
        _build_objects_table(result, validated_only),
        _build_crud_validation(result),
        _build_apex_table(result, validated_only),
        _build_proofs(result, validated_only),
        _build_footer(timestamp),
    ])

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>aura-privesc Report — {_esc(host)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="container">
{body}
</div>
</body>
</html>
"""

    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(doc)

    return filepath
