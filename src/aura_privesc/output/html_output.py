"""Self-contained HTML report with embedded CSS and client-side JS."""

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
th{text-align:left;padding:.6rem .8rem;background:var(--border);color:var(--cyan);font-weight:600;cursor:pointer;user-select:none;white-space:nowrap}
th:hover{background:#1a3a6e}
th .sort-arrow{margin-left:4px;font-size:.7rem;color:var(--muted)}
th.sorted-asc .sort-arrow::after{content:"\\25B2";color:var(--cyan)}
th.sorted-desc .sort-arrow::after{content:"\\25BC";color:var(--cyan)}
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
.search-box{width:100%;padding:.6rem 1rem;margin-bottom:1rem;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;font-size:.95rem}
.search-box:focus{outline:none;border-color:var(--cyan)}
.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1.5rem}
.stat{text-align:center;padding:1rem;background:var(--card);border:1px solid var(--border);border-radius:8px}
.stat-number{font-size:2rem;font-weight:700;color:var(--cyan)}
.stat-label{color:var(--muted);font-size:.9rem}
footer{text-align:center;color:var(--muted);margin-top:3rem;padding-top:1rem;border-top:1px solid var(--border);font-size:.85rem}
"""

_JS = """\
document.addEventListener('DOMContentLoaded',function(){
  /* --- Search filtering --- */
  document.querySelectorAll('.search-box').forEach(function(input){
    var tableId=input.getAttribute('data-table');
    var table=document.getElementById(tableId);
    if(!table)return;
    input.addEventListener('input',function(){
      var q=this.value.toLowerCase();
      var rows=table.querySelectorAll('tbody tr');
      rows.forEach(function(row){
        var text=row.textContent.toLowerCase();
        row.style.display=text.indexOf(q)!==-1?'':'none';
      });
    });
  });

  /* --- Sortable columns --- */
  document.querySelectorAll('th[data-sort]').forEach(function(th){
    th.addEventListener('click',function(){
      var table=th.closest('table');
      var tbody=table.querySelector('tbody');
      var rows=Array.from(tbody.querySelectorAll('tr'));
      var idx=Array.from(th.parentNode.children).indexOf(th);
      var type=th.getAttribute('data-sort');
      var asc=!th.classList.contains('sorted-asc');

      /* reset all headers in this table */
      th.parentNode.querySelectorAll('th').forEach(function(h){h.classList.remove('sorted-asc','sorted-desc');});
      th.classList.add(asc?'sorted-asc':'sorted-desc');

      rows.sort(function(a,b){
        var va=a.children[idx].getAttribute('data-val')||a.children[idx].textContent.trim();
        var vb=b.children[idx].getAttribute('data-val')||b.children[idx].textContent.trim();
        if(type==='num'){va=parseFloat(va)||0;vb=parseFloat(vb)||0;}
        else{va=va.toLowerCase();vb=vb.toLowerCase();}
        if(va<vb)return asc?-1:1;
        if(va>vb)return asc?1:-1;
        return 0;
      });

      rows.forEach(function(row){tbody.appendChild(row);});
    });
  });
});
"""

_CHECK = "\u2713"
_CROSS = "\u2717"


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
        return f'<span class="skip">&mdash;</span>'
    return _check_or_cross(result.success)


def _build_header(result: ScanResult, timestamp: str) -> str:
    target = _esc(result.target_url)
    mode = _esc(result.discovery.mode) if result.discovery else "unknown"
    return f"""
<h1>aura-privesc Report</h1>
<p class="subtitle">Target: <strong>{target}</strong> &mdash; Mode: {mode} &mdash; {_esc(timestamp)}</p>
"""


def _build_summary(result: ScanResult, accessible_objects: list, callable_apex: list) -> str:
    critical = [o for o in accessible_objects if o.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)]
    crud_validated = result.crud_validated_objects if result.interactive_mode else []

    return f"""
<h2>Executive Summary</h2>
<div class="summary-grid">
  <div class="stat"><div class="stat-number">{len(result.objects)}</div><div class="stat-label">Objects Scanned</div></div>
  <div class="stat"><div class="stat-number">{len(accessible_objects)}</div><div class="stat-label">Accessible</div></div>
  <div class="stat"><div class="stat-number" style="color:var(--red)">{len(critical)}</div><div class="stat-label">Critical / High</div></div>
  <div class="stat"><div class="stat-number">{len(callable_apex)}</div><div class="stat-label">Callable Apex</div></div>
  {"<div class='stat'><div class='stat-number'>" + str(len(crud_validated)) + "</div><div class='stat-label'>CRUD Validated</div></div>" if result.interactive_mode else ""}
</div>
"""


def _build_objects_table(accessible_objects: list) -> str:
    if not accessible_objects:
        return "<h2>Object Findings</h2><p>No accessible objects found.</p>"

    risk_order = {RiskLevel.CRITICAL: 0, RiskLevel.HIGH: 1, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 3, RiskLevel.INFO: 4}
    accessible_objects.sort(key=lambda o: (risk_order.get(o.risk, 99), o.name))

    rows = ""
    for obj in accessible_objects:
        c = obj.crud
        count = str(obj.record_count) if obj.record_count is not None else "-"
        risk_val = risk_order.get(obj.risk, 99)
        rows += f"""<tr>
  <td>{_esc(obj.name)}</td>
  <td>{_check_or_cross(c.readable)}</td>
  <td>{_check_or_cross(c.createable)}</td>
  <td>{_check_or_cross(c.updateable)}</td>
  <td>{_check_or_cross(c.deletable)}</td>
  <td>{_check_or_cross(c.queryable)}</td>
  <td data-val="{count}">{count}</td>
  <td data-val="{risk_val}">{_badge(obj.risk)}</td>
</tr>"""

    return f"""
<h2>Object Findings ({len(accessible_objects)})</h2>
<input class="search-box" data-table="objects-table" type="text" placeholder="Filter objects\u2026">
<div class="card">
<table id="objects-table">
<thead>
<tr>
  <th data-sort="str">Object<span class="sort-arrow"></span></th>
  <th>R</th><th>C</th><th>U</th><th>D</th><th>Q</th>
  <th data-sort="num">Records<span class="sort-arrow"></span></th>
  <th data-sort="num">Risk<span class="sort-arrow"></span></th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
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
        proven = ", ".join(cv.proven_operations) if cv.proven_operations else '<span class="skip">none</span>'
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
<thead>
<tr><th>Object</th><th>Read</th><th>Create</th><th>Update</th><th>Delete</th><th>Proven Ops</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
"""


def _build_apex_table(callable_apex: list) -> str:
    if not callable_apex:
        return ""

    callable_apex.sort(key=lambda r: r.controller_method)

    rows = ""
    for r in callable_apex:
        rows += f"""<tr>
  <td>{_esc(r.controller_method)}</td>
  <td><span class="status-callable">CALLABLE</span></td>
  <td>{_esc(r.message or '')}</td>
</tr>"""

    return f"""
<h2>Callable Apex Methods ({len(callable_apex)})</h2>
<input class="search-box" data-table="apex-table" type="text" placeholder="Filter methods\u2026">
<div class="card">
<table id="apex-table">
<thead>
<tr>
  <th data-sort="str">Controller.Method<span class="sort-arrow"></span></th>
  <th>Status</th>
  <th data-sort="str">Message<span class="sort-arrow"></span></th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
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
    output_dir: str = ".",
    validated_only: bool = True,
) -> str:
    """Generate a self-contained HTML report and write it to disk.

    Filters to actionable findings only:
    - Objects that are accessible (validated if validation is enabled)
    - Apex methods with CALLABLE status

    Returns the path to the written file.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    file_ts = now.strftime("%Y%m%d_%H%M%S")

    host = urlparse(result.target_url).hostname or "unknown"
    filename = f"aura-report-{host}-{file_ts}.html"
    filepath = os.path.join(output_dir, filename)

    # Filter to actionable findings
    accessible_objects = result.validated_objects if validated_only else result.accessible_objects
    callable_apex = [
        r for r in result.apex_results
        if r.status == ApexMethodStatus.CALLABLE
        and (not validated_only or r.validated is True)
    ]

    body = "".join([
        _build_header(result, timestamp),
        _build_summary(result, accessible_objects, callable_apex),
        _build_objects_table(accessible_objects),
        _build_crud_validation(result),
        _build_apex_table(callable_apex),
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
<script>{_JS}</script>
</body>
</html>
"""

    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(doc)

    return filepath
