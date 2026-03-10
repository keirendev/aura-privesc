"""Self-contained HTML report with embedded CSS and client-side JS."""

from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from ..models import ApexMethodStatus, GraphQLResult, ObjectResult, RestApiResult, RiskLevel, ScanResult

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
tr.obj-row{cursor:pointer}
tr.obj-row:hover td:first-child{text-decoration:underline}
tr.expand-row{display:none;background:var(--bg)}
tr.expand-row.open{display:table-row}
tr.expand-row>td{padding:1rem 1.5rem}
.records-table{width:100%;border-collapse:collapse;margin:.5rem 0;font-size:.85rem}
.records-table th{background:#0d2137;font-size:.8rem;padding:.4rem .6rem}
.records-table td{padding:.3rem .6rem;border-bottom:1px solid var(--border);max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.btn{display:inline-block;padding:4px 12px;border:none;border-radius:4px;font-size:.8rem;font-weight:600;cursor:pointer;margin:2px;color:#fff;text-decoration:none}
.btn-info{background:var(--cyan)}
.btn-read{background:#1565c0}
.btn-create{background:var(--green);color:#000}
.btn-update{background:var(--yellow);color:#000}
.btn-delete{background:var(--red)}
.btn-fire{background:var(--purple)}
.btn:hover{opacity:.85}
.action-bar{margin-top:.5rem}
.toast{visibility:hidden;min-width:200px;background:#333;color:#fff;text-align:center;border-radius:6px;padding:10px 24px;position:fixed;bottom:30px;left:50%;transform:translateX(-50%);font-size:.9rem;z-index:9999}
.toast.show{visibility:visible;animation:fadein .3s,fadeout .3s 1.7s}
@keyframes fadein{from{opacity:0}to{opacity:1}}
@keyframes fadeout{from{opacity:1}to{opacity:0}}
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
        if(row.classList.contains('expand-row')){
          if(!q)row.classList.remove('open');
          return;
        }
        var text=row.textContent.toLowerCase();
        var show=text.indexOf(q)!==-1;
        row.style.display=show?'':'none';
        var next=row.nextElementSibling;
        if(next&&next.classList.contains('expand-row')&&!show){
          next.classList.remove('open');
        }
      });
    });
  });

  /* --- Sortable columns --- */
  document.querySelectorAll('th[data-sort]').forEach(function(th){
    th.addEventListener('click',function(){
      var table=th.closest('table');
      var tbody=table.querySelector('tbody');
      var idx=Array.from(th.parentNode.children).indexOf(th);
      var type=th.getAttribute('data-sort');
      var asc=!th.classList.contains('sorted-asc');
      th.parentNode.querySelectorAll('th').forEach(function(h){h.classList.remove('sorted-asc','sorted-desc');});
      th.classList.add(asc?'sorted-asc':'sorted-desc');
      /* collect row pairs (obj-row + expand-row) */
      var pairs=[];
      var rows=Array.from(tbody.children);
      for(var i=0;i<rows.length;i++){
        if(!rows[i].classList.contains('expand-row')){
          var pair=[rows[i]];
          if(i+1<rows.length&&rows[i+1].classList.contains('expand-row'))pair.push(rows[i+1]);
          pairs.push(pair);
        }
      }
      pairs.sort(function(a,b){
        var va=a[0].children[idx].getAttribute('data-val')||a[0].children[idx].textContent.trim();
        var vb=b[0].children[idx].getAttribute('data-val')||b[0].children[idx].textContent.trim();
        if(type==='num'){va=parseFloat(va)||0;vb=parseFloat(vb)||0;}
        else{va=va.toLowerCase();vb=vb.toLowerCase();}
        if(va<vb)return asc?-1:1;
        if(va>vb)return asc?1:-1;
        return 0;
      });
      pairs.forEach(function(pair){pair.forEach(function(r){tbody.appendChild(r);});});
    });
  });

  /* --- Expand/collapse object rows --- */
  document.querySelectorAll('tr.obj-row').forEach(function(row){
    row.addEventListener('click',function(e){
      if(e.target.closest('.btn'))return;
      var next=row.nextElementSibling;
      if(next&&next.classList.contains('expand-row'))next.classList.toggle('open');
    });
  });
});

/* --- Build curl command and copy to clipboard --- */
function fireAura(descriptor,params){
  if(typeof AURA==='undefined')return;
  var msg=JSON.stringify({actions:[{id:'123;a',descriptor:descriptor,callingDescriptor:'UNKNOWN',params:params}]});
  var body='message='+msg+'&aura.context='+encodeURIComponent(AURA.context)+'&aura.pageURI=/s/&aura.token='+encodeURIComponent(AURA.token);
  var cmd="curl -k --proxy http://127.0.0.1:8080 -X POST '"+AURA.url+"' -H 'Content-Type: application/x-www-form-urlencoded'";
  if(AURA.sid)cmd+=" -H 'Cookie: sid="+AURA.sid+"'";
  cmd+=" -d '"+body.replace(/'/g,"'\\''")+"' | python3 -m json.tool";
  navigator.clipboard.writeText(cmd).then(function(){
    showToast('Copied curl to clipboard');
  },function(){
    /* fallback: prompt */
    prompt('Copy this curl command:',cmd);
  });
}
function showToast(msg){
  var el=document.getElementById('toast');
  if(!el){el=document.createElement('div');el.id='toast';document.body.appendChild(el);}
  el.textContent=msg;el.className='toast show';
  setTimeout(function(){el.className='toast';},2000);
}
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


def _crud_cell(obj: ObjectResult, op: str) -> str:
    """Three-state HTML cell for C/U/D: proven / failed / not attempted."""
    cv = obj.crud_validation
    if cv is not None:
        result = getattr(cv, op, None)
        if result is not None:
            return _check_or_cross(result.success)
    return '<span class="skip">&mdash;</span>'


def _build_header(result: ScanResult, timestamp: str) -> str:
    target = _esc(result.target_url)
    mode = _esc(result.discovery.mode) if result.discovery else "unknown"
    return f"""
<h1>aura-privesc Report</h1>
<p class="subtitle">Target: <strong>{target}</strong> &mdash; Mode: {mode} &mdash; {_esc(timestamp)}</p>
"""


def _build_summary(
    result: ScanResult,
    accessible_objects: list,
    callable_apex: list,
    graphql_results: list[GraphQLResult] | None = None,
) -> str:
    writable = [o for o in accessible_objects if o.crud.has_write]
    proven = [o for o in accessible_objects if o.crud_validation is not None and o.crud_validation.proven_operations]

    gql_card = ""
    if result.graphql_available and graphql_results:
        gql_with_counts = [r for r in graphql_results if r.total_count is not None]
        gql_card = f'<div class="stat"><div class="stat-number">{len(gql_with_counts)}</div><div class="stat-label">GraphQL Counted</div></div>'

    return f"""
<h2>Executive Summary</h2>
<div class="summary-grid">
  <div class="stat"><div class="stat-number">{len(result.objects)}</div><div class="stat-label">Objects Scanned</div></div>
  <div class="stat"><div class="stat-number">{len(accessible_objects)}</div><div class="stat-label">Accessible</div></div>
  <div class="stat"><div class="stat-number">{len(writable)}</div><div class="stat-label">Writable</div></div>
  <div class="stat"><div class="stat-number" style="color:var(--red)">{len(proven)}</div><div class="stat-label">Proven Writes</div></div>
  <div class="stat"><div class="stat-number">{len(callable_apex)}</div><div class="stat-label">Callable Apex</div></div>
  {gql_card}
</div>
"""


def _build_records_subtable(records: list[dict]) -> str:
    """Build a nested table showing sample records."""
    if not records:
        return '<p style="color:var(--muted);font-size:.85rem">No sample records.</p>'
    # Collect all field names across records
    fields: list[str] = []
    seen: set[str] = set()
    for rec in records:
        for k in rec:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    header = "".join(f"<th>{_esc(f)}</th>" for f in fields)
    body = ""
    for rec in records:
        cells = "".join(
            f"<td title=\"{_esc(str(rec.get(f, '')))}\">{_esc(str(rec.get(f, '')))}</td>"
            for f in fields
        )
        body += f"<tr>{cells}</tr>"
    return f'<table class="records-table"><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>'


def _build_action_buttons(obj) -> str:
    """Build Aura action buttons for an object row."""
    name = obj.name
    esc_name = _esc(name)
    js_name = html.escape(json.dumps(name), quote=True)

    # getObjectInfo
    btns = (
        f'<button class="btn btn-info" '
        f"""onclick="fireAura('aura://RecordUiController/ACTION$getObjectInfo',"""
        f"""{{'objectApiName':{js_name}}})">getObjectInfo</button>"""
    )

    # getItems
    get_items_desc = html.escape(
        "serviceComponent://ui.force.components.controllers.lists."
        "selectableListDataProvider.SelectableListDataProviderController"
        "/ACTION$getItems",
        quote=True,
    )
    btns += (
        f'<button class="btn btn-read" '
        f"""onclick="fireAura('{get_items_desc}',"""
        f"""{{'entityNameOrId':{js_name},'layoutType':'FULL','pageSize':100,'currentPage':0,'useTimeout':false,'getCount':false,'enableRowActions':false}})">getItems</button>"""
    )

    # Create
    create_desc = html.escape(
        "serviceComponent://ui.force.components.controllers.recordGlobalValueProvider."
        "RecordGvpController/ACTION$createRecord",
        quote=True,
    )
    btns += (
        f'<button class="btn btn-create" '
        f"""onclick="fireAura('{create_desc}',"""
        f"""{{'record':{{'apiName':{js_name},'fields':{{'Name':'aura-privesc-test'}}}}}})">Create</button>"""
    )

    # Update / Delete — use first sample record ID if available
    first_id = ""
    if obj.sample_records:
        first_rec = obj.sample_records[0]
        first_id = str(first_rec.get("Id") or first_rec.get("id") or "")
    js_id = html.escape(json.dumps(first_id or "RECORD_ID_HERE"), quote=True)

    update_desc = html.escape(
        "serviceComponent://ui.force.components.controllers.recordGlobalValueProvider."
        "RecordGvpController/ACTION$updateRecord",
        quote=True,
    )
    btns += (
        f'<button class="btn btn-update" '
        f"""onclick="fireAura('{update_desc}',"""
        f"""{{'record':{{'apiName':{js_name},'id':{js_id},'fields':{{'Name':'aura-privesc-updated'}}}}}})">Update</button>"""
    )

    delete_desc = html.escape(
        "serviceComponent://ui.force.components.controllers.recordGlobalValueProvider."
        "RecordGvpController/ACTION$deleteRecord",
        quote=True,
    )
    btns += (
        f'<button class="btn btn-delete" '
        f"""onclick="fireAura('{delete_desc}',"""
        f"""{{'recordId':{js_id}}})">Delete</button>"""
    )

    return f'<div class="action-bar">{btns}</div>'


def _build_objects_table(accessible_objects: list) -> str:
    if not accessible_objects:
        return "<h2>Object Findings</h2><p>No accessible objects found.</p>"

    accessible_objects.sort(key=lambda o: o.name)

    rows = ""
    ncols = 6
    for obj in accessible_objects:
        count = str(obj.record_count) if obj.record_count is not None else "-"
        rows += f"""<tr class="obj-row">
  <td>{_esc(obj.name)}</td>
  <td>{_check_or_cross(obj.crud.readable)}</td>
  <td>{_crud_cell(obj, 'create')}</td>
  <td>{_crud_cell(obj, 'update')}</td>
  <td>{_crud_cell(obj, 'delete')}</td>
  <td data-val="{count}">{count}</td>
</tr>
<tr class="expand-row"><td colspan="{ncols}">
{_build_records_subtable(obj.sample_records)}
{_build_action_buttons(obj)}
</td></tr>"""

    return f"""
<h2>Object Findings ({len(accessible_objects)})</h2>
<input class="search-box" data-table="objects-table" type="text" placeholder="Filter objects\u2026">
<div class="card">
<table id="objects-table">
<thead>
<tr>
  <th data-sort="str">Object<span class="sort-arrow"></span></th>
  <th>R</th><th>C</th><th>U</th><th>D</th>
  <th data-sort="num">Records<span class="sort-arrow"></span></th>
</tr>
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
        parts = r.controller_method.split(".", 1)
        controller = parts[0] if parts else ""
        method = parts[1] if len(parts) > 1 else ""
        js_ctrl = html.escape(json.dumps(controller), quote=True)
        js_meth = html.escape(json.dumps(method), quote=True)
        fire_btn = (
            f'<button class="btn btn-fire" '
            f"""onclick="fireAura('aura://ApexActionController/ACTION$execute',"""
            f"""{{'namespace':'','classname':{js_ctrl},'method':{js_meth},"""
            f"""'params':{{}},'cacheable':false,'isContinuation':false}})">Fire</button>"""
        )
        rows += f"""<tr>
  <td>{_esc(r.controller_method)}</td>
  <td><span class="status-callable">CALLABLE</span></td>
  <td>{_esc(r.message or '')}</td>
  <td>{fire_btn}</td>
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
  <th>Action</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
"""


def _build_rest_api_section(rest_api: RestApiResult | None) -> str:
    if not rest_api:
        return ""

    status_label = (
        '<span class="check">ENABLED</span>' if rest_api.api_enabled
        else '<span class="fail">DISABLED</span>'
    )

    rows = ""
    for i, check in enumerate(rest_api.checks):
        icon = _check_or_cross(check.success)
        detail = _esc(check.detail or check.error or "")
        endpoint_short = _esc(check.endpoint)
        proof_btn = ""
        if check.proof:
            data_id = f"rest-proof-{i}"
            proof_btn = (
                f'<textarea id="{data_id}" style="display:none">{_esc(check.proof)}</textarea>'
                f'<button class="btn btn-info" '
                f"""onclick="var t=document.getElementById('{data_id}');navigator.clipboard.writeText(t.value)"""
                f""".then(function(){{showToast('Copied curl')}})">Copy curl</button>"""
            )
        rows += f"""<tr>
  <td>{_esc(check.name)}</td>
  <td>{icon}</td>
  <td style="font-size:.85rem;color:var(--muted)">{endpoint_short}</td>
  <td>{detail}</td>
  <td>{proof_btn}</td>
</tr>"""

    soql_block = ""
    if rest_api.soql_example_curl:
        escaped = _esc(rest_api.soql_example_curl)
        soql_block = f"""
<h3 style="color:var(--cyan);margin:1rem 0 .5rem">SOQL Query (REST API)</h3>
<pre style="background:var(--bg);color:var(--green);padding:1rem;border-radius:6px;overflow-x:auto;font-size:.85rem;white-space:pre-wrap;word-break:break-all">{escaped}</pre>
"""

    return f"""
<h2>REST API (API Enabled) &mdash; {status_label}</h2>
<div class="card">
<table>
<thead>
<tr>
  <th>Check</th>
  <th>Status</th>
  <th>Endpoint</th>
  <th>Detail</th>
  <th></th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
{soql_block}
</div>
"""


def _build_graphql_table(graphql_results: list[GraphQLResult], graphql_available: bool) -> str:
    if not graphql_available or not graphql_results:
        return ""

    graphql_results_sorted = sorted(graphql_results, key=lambda r: r.object_name)

    rows = ""
    for r in graphql_results_sorted:
        count = str(r.total_count) if r.total_count is not None else "-"
        n_fields = str(len(r.fields)) if r.fields else "-"

        # Build field details for expandable row
        field_details = ""
        if r.fields:
            field_rows = "".join(
                f"<tr><td>{_esc(f.name)}</td><td>{_esc(f.data_type)}</td></tr>"
                for f in sorted(r.fields, key=lambda f: f.name)
            )
            field_details = (
                f'<table class="records-table"><thead><tr><th>Field</th><th>Type</th></tr></thead>'
                f"<tbody>{field_rows}</tbody></table>"
            )
        else:
            field_details = '<p style="color:var(--muted);font-size:.85rem">No field data.</p>'

        # Count fire button
        js_name = html.escape(json.dumps(r.object_name), quote=True)
        count_query = f"query getCount{{{{uiapi{{{{query{{{{{_esc(r.object_name)}{{{{totalCount}}}}}}}}}}}}}}}}"
        fire_btn = (
            f'<button class="btn btn-fire" '
            f"""onclick="fireAura('aura://RecordUiController/ACTION$executeGraphQL',"""
            f"""{{'queryInput':{{'operationName':'getCount','query':'query getCount{{uiapi{{query{{{_esc(r.object_name)}{{totalCount}}}}}}}}','variables':{{}}}}}})">Count</button>"""
        )

        rows += f"""<tr class="obj-row">
  <td>{_esc(r.object_name)}</td>
  <td data-val="{count}">{count}</td>
  <td>{n_fields}</td>
  <td>{fire_btn}</td>
</tr>
<tr class="expand-row"><td colspan="4">
{field_details}
</td></tr>"""

    return f"""
<h2>GraphQL Enumeration ({len(graphql_results)} objects)</h2>
<input class="search-box" data-table="graphql-table" type="text" placeholder="Filter objects\u2026">
<div class="card">
<table id="graphql-table">
<thead>
<tr>
  <th data-sort="str">Object<span class="sort-arrow"></span></th>
  <th data-sort="num">Record Count<span class="sort-arrow"></span></th>
  <th data-sort="num">Fields<span class="sort-arrow"></span></th>
  <th>Action</th>
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
        _build_summary(result, accessible_objects, callable_apex, result.graphql_results),
        _build_rest_api_section(result.rest_api),
        _build_objects_table(accessible_objects),
        _build_apex_table(callable_apex),
        _build_graphql_table(result.graphql_results, result.graphql_available),
        _build_footer(timestamp),
    ])

    # Build AURA connection config for interactive buttons
    aura_config = ""
    if result.aura_url:
        aura_obj = {
            "url": result.aura_url,
            "token": result.aura_token or "undefined",
            "context": result.aura_context or "{}",
        }
        if result.sid:
            aura_obj["sid"] = result.sid
        aura_config = f"var AURA={json.dumps(aura_obj)};\n"

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
<script>
{aura_config}{_JS}</script>
</body>
</html>
"""

    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(doc)

    return filepath
