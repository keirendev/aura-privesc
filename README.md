# aura-privesc

Salesforce Aura/Lightning privilege escalation scanner. Discovers exposed Aura endpoints, enumerates which objects are readable via `getItems`, tests Apex controllers, performs GraphQL record enumeration, and provides an interactive web dashboard and HTML reports with ready-to-use curl commands.

## Install

Requires Python 3.11+. Node.js 18+ for the web UI frontend (optional).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

To build the web UI frontend:
```bash
cd frontend && npm install && npm run build
```

## Usage

### Web UI (default)

Running `aura-privesc` with no arguments starts the web dashboard:

```bash
aura-privesc
# Opens http://127.0.0.1:8888 in your browser
```

Options:
```bash
aura-privesc serve --port 9999          # Custom port
aura-privesc serve --no-browser         # Don't auto-open browser
aura-privesc serve --host 0.0.0.0      # Non-localhost (warning: no auth)
```

The web UI lets you:
- Configure scans with presets (Quick / Full / Stealth) or advanced options
- Monitor scan progress in real-time
- Browse results with sortable/filterable tables
- Copy curl proof commands with one click
- Discover objects via GraphQL `__schema` introspection
- Introspect type fields via `__type` queries
- Test GraphQL write access (create + auto-delete) per object
- View full scan history
- Toggle dark/light theme

### CLI scan

```bash
aura-privesc scan -u https://target.my.site.com --proxy http://127.0.0.1:8080 --insecure
```

### Authenticated scan

Use `--authenticated` to be prompted for the session ID and Aura token interactively (keeps credentials out of shell history):

```bash
aura-privesc scan -u https://target.my.site.com \
  --endpoint '/s/sfsites/aura' \
  --authenticated \
  --proxy http://127.0.0.1:8080 --insecure
```

### Privileged recon with Salesforce CLI

Use the `recon` subcommand with a privileged org user to enumerate all objects and Apex controllers, then feed the results into a scan against the community endpoint to find privilege escalation gaps.

```bash
# 1. Authenticate
sf org login web --instance-url https://your-instance.sandbox.my.salesforce.com -a myalias

# 2. Recon
aura-privesc recon -u https://your-instance.sandbox.my.salesforce.com --alias myalias -v

# 3. Scan with recon output
aura-privesc scan -u https://target.my.site.com \
  --endpoint '/s/sfsites/aura' \
  --authenticated \
  --objects-file recon/recon-objects-<slug>.txt \
  --apex-file recon/recon-apex-<slug>.txt \
  --proxy http://127.0.0.1:8080 --insecure
```

## What the scan does

1. **Discovery** -- probes endpoint paths, extracts fwuid and aura.context from community HTML
2. **User context** -- identifies current user, checks SOQL capability, discovers config objects
3. **Object enumeration** -- calls `getObjectInfo` for CRUD permissions, `getItems` for records, validates findings
4. **CRUD write testing** -- automatically tests create/update/delete on writable objects to prove access
5. **Apex testing** -- discovers `@AuraEnabled` controllers from JS, tests each method
6. **GraphQL enumeration** -- uses `executeGraphQL` for accurate record counts, field introspection, record fetching with cursor pagination, filtered queries, and relationship traversal
7. **Interactive GraphQL tools** (web UI only) -- `__schema`/`__type` introspection to discover objects and fields directly through GraphQL, and mutation-based write testing (create + delete) to prove write access via a different attack surface than Aura CRUD

## HTML report

The CLI scan generates a self-contained HTML report with:
- Sortable/filterable object findings table with expandable rows
- Action buttons (getObjectInfo, getItems, Create, Update, Delete) that copy curl commands
- Apex methods table with Fire buttons
- GraphQL enumeration table with field details and Count buttons
- Search and sort on all tables

Use `--no-report` to suppress, or `--report-dir ./reports` to change output directory.

## Scan options

```
-u, --url TEXT          Target Salesforce base/community URL (required)
--authenticated         Authenticated scan mode (prompts for sid and token)
--context TEXT          Manual aura.context JSON
--endpoint TEXT         Manual aura endpoint path
--objects-file PATH     File with additional object API names
--apex-file PATH        File with Apex controller.method pairs
--json                  Output as JSON
--skip-crud             Skip per-object CRUD permission checks
--skip-records          Skip record retrieval
--skip-crud-test        Skip automated CRUD write testing
--skip-graphql          Skip GraphQL enumeration
--skip-apex             Skip Apex controller testing
--skip-validation       Skip finding validation
--report / --no-report  Generate HTML report (default: on)
--report-dir DIRECTORY  Directory for HTML report output
--timeout INTEGER       HTTP timeout in seconds (default: 30)
--delay INTEGER         Delay between requests in ms (default: 0)
--concurrency INTEGER   Max concurrent requests (default: 5)
--proxy TEXT            HTTP proxy URL
--insecure              Disable TLS verification
-v, --verbose           Show raw request/response data
```

## Disclaimer

This tool is intended for authorized security testing only. Only use it against systems you have explicit permission to test.
