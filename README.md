# aura-privesc

Salesforce Aura/Lightning privilege escalation scanner. Discovers exposed Aura endpoints, enumerates which objects are readable via `getItems`, tests Apex controllers, and generates an interactive HTML report with ready-to-use curl commands for manual CRUD validation.

## Install

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

### Basic scan (guest mode)

```bash
aura-privesc -u https://target.my.site.com --proxy http://127.0.0.1:8080 --insecure
```

### Authenticated scan

Use `--authenticated` to be prompted for the session ID and Aura token interactively (keeps credentials out of shell history):

```bash
aura-privesc -u https://target.my.site.com \
  --endpoint '/s/sfsites/aura' \
  --authenticated \
  --proxy http://127.0.0.1:8080 --insecure
```

You will be prompted for:
- **Session ID (sid)** — the `sid` cookie value from your browser/proxy session
- **Aura token** — the `aura.token` value from the page

### Privileged recon with Salesforce CLI

Use the `recon` subcommand with a privileged org user to enumerate all objects and Apex controllers, then feed the results into a scan against the community endpoint to find privilege escalation gaps.

**1. Authenticate with the Salesforce CLI:**

```bash
sf org login web --instance-url https://your-instance.sandbox.my.salesforce.com -a myalias
```

This opens a browser for OAuth login. Alternatively, use `sf org login access-token` if you have a session token.

**2. Run recon:**

```bash
aura-privesc recon -u https://your-instance.sandbox.my.salesforce.com --alias myalias -v
```

This outputs `recon-objects-<slug>.txt` and `recon-apex-<slug>.txt` (in a `recon/` directory) with the full list of objects and `@AuraEnabled` methods visible to the privileged user.

**3. Scan the community endpoint using the recon output:**

```bash
aura-privesc -u https://target.my.site.com \
  --endpoint '/s/sfsites/aura' \
  --authenticated \
  --objects-file recon/recon-objects-<slug>.txt \
  --apex-file recon/recon-apex-<slug>.txt \
  --proxy http://127.0.0.1:8080 --insecure
```

## What the scan does

The scanner automates the discovery and enumeration phase of Aura privilege escalation testing:

1. **Discovery** — probes endpoint paths, extracts fwuid and aura.context from community HTML
2. **User context** — identifies current user, checks SOQL capability, discovers config objects
3. **Object enumeration** — calls `getObjectInfo` for each object to check CRUD permission flags, then `getItems` to confirm whether records are actually readable. Validates findings to filter false positives
4. **Apex testing** — discovers `@AuraEnabled` controllers from community JS files, tests each method, classifies as CALLABLE / DENIED / NOT_FOUND

## HTML report

The primary output is a self-contained HTML report (dark theme, no external dependencies) generated automatically in the current directory. The report includes:

- **Object findings table** — sortable/filterable, showing which objects are accessible and readable, with record counts
- **Expandable rows** — click any object to see sample record data
- **Action buttons** — each object row has ready-to-use buttons (getObjectInfo, getItems, Create, Update, Delete) that copy a curl command to your clipboard. These are the starting point for manual CRUD validation — modify the field values and record IDs as needed for your test case
- **Apex methods table** — callable methods with Fire buttons to generate curl commands
- **Search/sort** — filter and sort all tables client-side

Use `--no-report` to suppress report generation, or `--report-dir ./reports` to change the output directory.

### Manual CRUD validation workflow

The scan tells you which objects are exposed and readable. To prove write access, use the report's action buttons as a starting point:

1. Open the HTML report
2. Expand an object row to see its sample records and action buttons
3. Click **Create** / **Update** / **Delete** to copy a base curl command
4. Modify the curl as needed (field names, values, record IDs) and run it through your proxy
5. Verify the operation succeeded in the Aura response

## Other output formats

- **JSON** (`--json`) — machine-readable scan results on stdout
- **Terminal** — summary of findings printed to the terminal

## Options

```
-u, --url TEXT          Target Salesforce base/community URL (required)
--authenticated         Authenticated scan mode (prompts for sid and token)
--context TEXT          Manual aura.context JSON
--endpoint TEXT         Manual aura endpoint path
--objects-file PATH     File with additional object API names
--apex-file PATH        File with Apex controller.method pairs
--json                  Output as JSON
--skip-crud             Skip per-object CRUD permission checks (getObjectInfo)
--skip-records          Skip record retrieval (getItems)
--skip-crud-test        Skip automated CRUD write testing
--skip-apex             Skip Apex controller testing
--skip-validation       Skip finding validation (faster, may include false positives)
--report / --no-report  Generate HTML report (default: on)
--report-dir DIRECTORY  Directory for HTML report output
--timeout INTEGER       HTTP timeout in seconds (default: 30)
--delay INTEGER         Delay between requests in ms (default: 0)
--concurrency INTEGER   Max concurrent requests (default: 5)
--proxy TEXT            HTTP proxy URL (e.g. http://127.0.0.1:8080 for Burp)
--insecure              Disable TLS verification
-v, --verbose           Show raw request/response data
```

## Disclaimer

This tool is intended for authorized security testing only. Only use it against systems you have explicit permission to test.
