"""REST API access checks — detects the 'API Enabled' profile permission.

Makes actual HTTP calls to /services/data/ endpoints using a clean httpx client
(no Aura headers). The 'API Enabled' permission controls access to REST, SOAP,
Tooling, Bulk, and Streaming APIs — capabilities far beyond Aura.

Experience Cloud domains (*.my.site.com, *.force.com) don't serve /services/data/.
The REST API lives on the CRM domain (*.my.salesforce.com). This module derives the
CRM domain from the target URL automatically, falling back to the target domain.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from .client import AuraClient
from .models import RestApiCheck, RestApiResult

logger = logging.getLogger(__name__)


def _derive_crm_base(base_url: str) -> str | None:
    """Derive the CRM (My Domain) base URL from an Experience Cloud URL.

    Salesforce domain patterns:
      *.my.site.com           → *.my.salesforce.com          (Experience Cloud)
      *.sandbox.my.site.com   → *.sandbox.my.salesforce.com  (Sandbox Experience)
      *.lightning.force.com   → *.my.salesforce.com          (Lightning)
      *.force.com             → *.my.salesforce.com          (Legacy community)
      *.my.salesforce.com     → already CRM, returns None

    Returns a full base URL (scheme://host) or None if already on CRM domain
    or the pattern isn't recognised.
    """
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    scheme = parsed.scheme or "https"

    # Already on CRM domain
    if host.endswith(".my.salesforce.com") or host.endswith(".sandbox.my.salesforce.com"):
        return None

    # Sandbox Experience Cloud: {mydomain}--{sandbox}.sandbox.my.site.com
    if host.endswith(".sandbox.my.site.com"):
        org = host.removesuffix(".sandbox.my.site.com")
        return f"{scheme}://{org}.sandbox.my.salesforce.com"

    # Experience Cloud enhanced domain: {mydomain}.my.site.com
    if host.endswith(".my.site.com"):
        org = host.removesuffix(".my.site.com")
        return f"{scheme}://{org}.my.salesforce.com"

    # Lightning: {mydomain}.lightning.force.com
    if host.endswith(".lightning.force.com"):
        org = host.removesuffix(".lightning.force.com")
        return f"{scheme}://{org}.my.salesforce.com"

    # Legacy community: {mydomain}.force.com (take first subdomain label)
    if host.endswith(".force.com"):
        org = host.split(".")[0]
        if org:
            return f"{scheme}://{org}.my.salesforce.com"

    return None


async def check_rest_api_access(
    client: AuraClient, *, crm_domain: str | None = None,
) -> RestApiResult:
    """Check REST API access by hitting /services/data/ endpoints directly.

    Args:
        crm_domain: Optional user-specified CRM domain (e.g. "acme.my.salesforce.com").
                     Overrides automatic derivation from the target URL.
    """
    parsed = urlparse(client.base_url)
    target_base = f"{parsed.scheme}://{parsed.netloc}"

    if crm_domain:
        # User-specified override — normalise to a full URL
        if not crm_domain.startswith("http"):
            crm_base = f"{parsed.scheme}://{crm_domain}"
        else:
            crm_base = crm_domain.rstrip("/")
    else:
        crm_base = _derive_crm_base(client.base_url)

    result = RestApiResult(api_base_url=target_base)

    # Extract SID for auth
    sid = client.sid
    if not sid:
        # Try to extract from cookie jar
        for cookie in client._http.cookies.jar:
            if cookie.name == "sid":
                sid = cookie.value
                break

    # Build a clean HTTP client — no Aura headers
    transport_kwargs: dict = {}
    if client.proxy:
        transport_kwargs["proxy"] = client.proxy
    if client.insecure:
        transport_kwargs["verify"] = False

    try:
        import h2  # noqa: F401
        http2_available = True
    except ImportError:
        http2_available = False

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if sid:
        headers["Authorization"] = f"Bearer {sid}"
        headers["Cookie"] = f"sid={sid}"

    async with httpx.AsyncClient(
        timeout=client._http.timeout,
        follow_redirects=True,
        http2=http2_available,
        headers=headers,
        **transport_kwargs,
    ) as rest_http:
        # Check 1: API Versions
        # If we have a CRM base (user-specified or derived), try it first since
        # Experience Cloud domains don't serve /services/data/.
        # Fall back to the target domain if CRM fails or isn't known.
        base = target_base
        check1: RestApiCheck | None = None
        version: str | None = None

        # Bind proxy/insecure so all curl proofs include them
        curl_opts = {"proxy": client.proxy, "insecure": client.insecure}

        if crm_base:
            check1, version = await _check_api_versions(rest_http, crm_base, sid, **curl_opts)
            if check1.success:
                base = crm_base
                result.api_base_url = crm_base
            else:
                logger.info(
                    "REST API not available on CRM domain %s, trying target %s",
                    crm_base, target_base,
                )
                check1, version = await _check_api_versions(rest_http, target_base, sid, **curl_opts)
        else:
            check1, version = await _check_api_versions(rest_http, target_base, sid, **curl_opts)

        result.checks.append(check1)

        if not check1.success or not version:
            return result

        result.api_version = version

        # Checks 2-6: run sequentially on whichever base worked
        check2 = await _check_soql_query(rest_http, base, version, sid, **curl_opts)
        result.checks.append(check2)
        if check2.success:
            result.api_enabled = True
        if check2.proof:
            result.soql_example_curl = check2.proof

        check3 = await _check_sobject_describe(rest_http, base, version, sid, **curl_opts)
        result.checks.append(check3)

        check4 = await _check_tooling_api(rest_http, base, version, sid, **curl_opts)
        result.checks.append(check4)

        check5 = await _check_bulk_api(rest_http, base, version, sid, **curl_opts)
        result.checks.append(check5)

        check6 = await _check_org_limits(rest_http, base, version, sid, **curl_opts)
        result.checks.append(check6)

    return result


def _build_curl(url: str, sid: str | None, proxy: str | None = None, insecure: bool = False) -> str:
    """Build a simple curl command for REST API endpoints."""
    parts = ["curl"]
    if insecure:
        parts.append("-k")
    if proxy:
        parts.append(f"--proxy {proxy}")
    parts.append("-H 'Accept: application/json'")
    if sid:
        parts.append(f"-H 'Authorization: Bearer {sid}'")
        parts.append(f"-b 'sid={sid}'")
    parts.append(f"'{url}'")
    parts.append("| python3 -m json.tool")
    return " ".join(parts)


async def _safe_json(resp: httpx.Response) -> tuple[dict | list | None, str | None]:
    """Try to parse JSON from response. Returns (data, error)."""
    try:
        data = resp.json()
        return data, None
    except Exception:
        ct = resp.headers.get("content-type", "")
        if "text/html" in ct:
            return None, "Redirected to login page"
        return None, f"Non-JSON response (Content-Type: {ct})"


async def _check_api_versions(
    http: httpx.AsyncClient, base: str, sid: str | None,
    *, proxy: str | None = None, insecure: bool = False,
) -> tuple[RestApiCheck, str | None]:
    """GET /services/data/ — list available API versions."""
    url = f"{base}/services/data/"
    check = RestApiCheck(name="API Versions", endpoint="/services/data/")

    try:
        resp = await http.get(url)
        check.status_code = resp.status_code

        if resp.status_code in (401, 403):
            check.error = f"Access denied ({resp.status_code})"
            return check, None

        data, err = await _safe_json(resp)
        if err:
            check.error = err
            return check, None

        if isinstance(data, list) and len(data) > 0:
            check.success = True
            latest = data[-1]
            version = latest.get("version", "")
            check.detail = f"Latest: v{version}"
            check.proof = _build_curl(url, sid, proxy=proxy, insecure=insecure)
            return check, version
        else:
            check.error = "Unexpected response format"
            return check, None

    except httpx.HTTPError as e:
        check.error = str(e)
        return check, None


async def _check_soql_query(
    http: httpx.AsyncClient, base: str, version: str, sid: str | None,
    *, proxy: str | None = None, insecure: bool = False,
) -> RestApiCheck:
    """GET /services/data/vXX/tooling/query/?q=SELECT... — test SOQL access."""
    query = "SELECT%20Id%2C%20Username%2C%20Name%20FROM%20User%20LIMIT%205"
    url = f"{base}/services/data/v{version}/tooling/query/?q={query}"
    check = RestApiCheck(name="SOQL Query", endpoint=f"/services/data/v{version}/tooling/query/")

    try:
        resp = await http.get(url)
        check.status_code = resp.status_code

        data, err = await _safe_json(resp)
        if err:
            check.error = err
            return check

        if isinstance(data, dict) and "records" in data:
            check.success = True
            records = data["records"]
            total = data.get("totalSize", len(records))
            detail = f"{total} total User records"
            if records:
                first = records[0]
                username = first.get("Username") or first.get("Name")
                if username:
                    detail += f" (e.g. {username})"
            check.detail = detail
        elif isinstance(data, dict) and "errorCode" in data:
            check.error = f"{data.get('errorCode')}: {data.get('message', '')}"
        elif isinstance(data, list) and data and "errorCode" in data[0]:
            check.error = f"{data[0].get('errorCode')}: {data[0].get('message', '')}"
        else:
            check.error = "Unexpected response format"

    except httpx.HTTPError as e:
        check.error = str(e)

    check.proof = _build_curl(url, sid, proxy=proxy, insecure=insecure)
    return check


async def _check_sobject_describe(
    http: httpx.AsyncClient, base: str, version: str, sid: str | None,
    *, proxy: str | None = None, insecure: bool = False,
) -> RestApiCheck:
    """GET /services/data/vXX/sobjects/ — list accessible sObjects."""
    url = f"{base}/services/data/v{version}/sobjects/"
    check = RestApiCheck(name="sObject Describe", endpoint=f"/services/data/v{version}/sobjects/")

    try:
        resp = await http.get(url)
        check.status_code = resp.status_code

        data, err = await _safe_json(resp)
        if err:
            check.error = err
            return check

        if isinstance(data, dict) and "sobjects" in data:
            check.success = True
            sobjects = data["sobjects"]
            check.detail = f"{len(sobjects)} sObjects accessible"
        elif isinstance(data, dict) and "errorCode" in data:
            check.error = f"{data.get('errorCode')}: {data.get('message', '')}"
        elif isinstance(data, list) and data and "errorCode" in data[0]:
            check.error = f"{data[0].get('errorCode')}: {data[0].get('message', '')}"
        else:
            check.error = "Unexpected response format"

    except httpx.HTTPError as e:
        check.error = str(e)

    check.proof = _build_curl(url, sid, proxy=proxy, insecure=insecure)
    return check


async def _check_tooling_api(
    http: httpx.AsyncClient, base: str, version: str, sid: str | None,
    *, proxy: str | None = None, insecure: bool = False,
) -> RestApiCheck:
    """GET /services/data/vXX/tooling/ — test Tooling API access."""
    url = f"{base}/services/data/v{version}/tooling/"
    check = RestApiCheck(name="Tooling API", endpoint=f"/services/data/v{version}/tooling/")

    try:
        resp = await http.get(url)
        check.status_code = resp.status_code

        data, err = await _safe_json(resp)
        if err:
            check.error = err
            return check

        if isinstance(data, dict) and resp.status_code == 200:
            check.success = True
            check.detail = "Available"
        elif isinstance(data, dict) and "errorCode" in data:
            check.error = f"{data.get('errorCode')}: {data.get('message', '')}"
        elif isinstance(data, list) and data and "errorCode" in data[0]:
            check.error = f"{data[0].get('errorCode')}: {data[0].get('message', '')}"
        else:
            check.error = f"HTTP {resp.status_code}"

    except httpx.HTTPError as e:
        check.error = str(e)

    check.proof = _build_curl(url, sid, proxy=proxy, insecure=insecure)
    return check


async def _check_bulk_api(
    http: httpx.AsyncClient, base: str, version: str, sid: str | None,
    *, proxy: str | None = None, insecure: bool = False,
) -> RestApiCheck:
    """GET /services/data/vXX/jobs/query — test Bulk API access."""
    url = f"{base}/services/data/v{version}/jobs/query"
    check = RestApiCheck(name="Bulk API", endpoint=f"/services/data/v{version}/jobs/query")

    try:
        resp = await http.get(url)
        check.status_code = resp.status_code

        data, err = await _safe_json(resp)
        if err:
            check.error = err
            return check

        if isinstance(data, dict) and resp.status_code == 200:
            check.success = True
            check.detail = "Available"
        elif isinstance(data, dict) and "errorCode" in data:
            check.error = f"{data.get('errorCode')}: {data.get('message', '')}"
        elif isinstance(data, list) and data and "errorCode" in data[0]:
            check.error = f"{data[0].get('errorCode')}: {data[0].get('message', '')}"
        else:
            check.error = f"HTTP {resp.status_code}"

    except httpx.HTTPError as e:
        check.error = str(e)

    check.proof = _build_curl(url, sid, proxy=proxy, insecure=insecure)
    return check


async def _check_org_limits(
    http: httpx.AsyncClient, base: str, version: str, sid: str | None,
    *, proxy: str | None = None, insecure: bool = False,
) -> RestApiCheck:
    """GET /services/data/vXX/limits/ — test org limits access."""
    url = f"{base}/services/data/v{version}/limits/"
    check = RestApiCheck(name="Org Limits", endpoint=f"/services/data/v{version}/limits/")

    try:
        resp = await http.get(url)
        check.status_code = resp.status_code

        data, err = await _safe_json(resp)
        if err:
            check.error = err
            return check

        if isinstance(data, dict) and resp.status_code == 200:
            check.success = True
            # Pick a few interesting limits
            highlights = []
            for key in ("DailyApiRequests", "DataStorageMB", "FileStorageMB"):
                if key in data:
                    val = data[key]
                    if isinstance(val, dict):
                        highlights.append(f"{key}: {val.get('Remaining', '?')}/{val.get('Max', '?')}")
            check.detail = ", ".join(highlights) if highlights else "Available"
        elif isinstance(data, dict) and "errorCode" in data:
            check.error = f"{data.get('errorCode')}: {data.get('message', '')}"
        elif isinstance(data, list) and data and "errorCode" in data[0]:
            check.error = f"{data[0].get('errorCode')}: {data[0].get('message', '')}"
        else:
            check.error = f"HTTP {resp.status_code}"

    except httpx.HTTPError as e:
        check.error = str(e)

    check.proof = _build_curl(url, sid, proxy=proxy, insecure=insecure)
    return check
