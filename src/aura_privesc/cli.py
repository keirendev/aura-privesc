"""Click CLI — wires everything together."""

from __future__ import annotations

import asyncio
import logging
import sys
import webbrowser

import click
from rich.console import Console
from rich.progress import Progress, BarColumn, MofNCompleteColumn, TimeElapsedColumn

from . import __version__
from .engine import ScanConfig, ScanEngine
from .exceptions import AuraError, DiscoveryError, ReconError
from .models import ApexMethodStatus, ScanResult
from .output import html_output, json_output

console = Console(stderr=True)


class DefaultGroup(click.Group):
    """Falls back to 'serve' when no subcommand matches, or 'scan' when flags present."""

    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and args[0] not in ("--help", "-h", "--version"):
            # If first arg starts with - or is -u, it's a scan invocation
            if args[0].startswith("-"):
                args = ["scan"] + list(args)
            else:
                args = ["scan"] + list(args)
        elif not args:
            # No args at all -> serve
            args = ["serve"]
        return super().parse_args(ctx, args)


@click.group(cls=DefaultGroup)
@click.version_option(version=__version__)
def main():
    """Salesforce Aura/Lightning privilege escalation scanner."""


@main.command()
@click.option("-u", "--url", required=True, help="Target Salesforce base/community URL")
@click.option("--authenticated", is_flag=True, help="Authenticated scan mode (prompts for sid and token)")
@click.option("--context", "manual_context", default=None, help="Manual aura.context JSON")
@click.option("--endpoint", "manual_endpoint", default=None, help="Manual aura endpoint path")
@click.option("--objects-file", type=click.Path(exists=True), help="File with additional object API names")
@click.option("--apex-file", type=click.Path(exists=True), help="File with Apex controller.method pairs")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON")
@click.option("--skip-crud", is_flag=True, help="Skip per-object CRUD permission checks")
@click.option("--skip-records", is_flag=True, help="Skip record count enumeration")
@click.option("--skip-apex", is_flag=True, help="Skip Apex controller testing")
@click.option("--skip-validation", is_flag=True, help="Skip finding validation (faster, may include false positives)")
@click.option("--skip-crud-test", is_flag=True, help="Skip automated CRUD write testing")
@click.option("--skip-graphql", is_flag=True, help="Skip GraphQL enumeration (record counts and field introspection)")
@click.option("--timeout", default=30, type=int, help="HTTP timeout in seconds")
@click.option("--delay", default=0, type=int, help="Delay between requests in ms")
@click.option("--concurrency", default=5, type=int, help="Max concurrent requests")
@click.option("--proxy", default=None, help="HTTP proxy URL")
@click.option("--crm-domain", default=None, help="CRM domain for REST API checks (e.g. acme.my.salesforce.com)")
@click.option("--insecure", is_flag=True, help="Disable TLS verification")
@click.option("-v", "--verbose", is_flag=True, help="Show raw request/response data")
@click.option("--report/--no-report", default=True, help="Generate HTML report (default: on)")
@click.option("--report-dir", type=click.Path(file_okay=False), default=".", help="Directory for HTML report output")
def scan(
    url: str,
    authenticated: bool,
    manual_context: str | None,
    manual_endpoint: str | None,
    objects_file: str | None,
    apex_file: str | None,
    json_mode: bool,
    skip_crud: bool,
    skip_records: bool,
    skip_apex: bool,
    skip_validation: bool,
    skip_crud_test: bool,
    skip_graphql: bool,
    timeout: int,
    delay: int,
    concurrency: int,
    proxy: str | None,
    crm_domain: str | None,
    insecure: bool,
    verbose: bool,
    report: bool,
    report_dir: str,
) -> None:
    """Run the Aura privilege escalation scan."""
    # Prompt for credentials when running in authenticated mode
    sid: str | None = None
    token: str | None = None
    if authenticated:
        sid = console.input("[cyan]Session ID (sid):[/cyan] ").strip() or None
        token = console.input("[cyan]Aura token:[/cyan] ").strip() or None
        if not sid and not token:
            console.print("[red]Error:[/red] --authenticated requires at least a sid or token.")
            sys.exit(1)

    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    config = ScanConfig(
        url=url,
        token=token,
        sid=sid,
        manual_context=manual_context,
        manual_endpoint=manual_endpoint,
        objects_file=objects_file,
        apex_file=apex_file,
        skip_crud=skip_crud,
        skip_records=skip_records,
        skip_apex=skip_apex,
        skip_validation=skip_validation,
        skip_crud_test=skip_crud_test,
        skip_graphql=skip_graphql,
        timeout=timeout,
        delay=delay,
        concurrency=concurrency,
        proxy=proxy,
        crm_domain=crm_domain,
        insecure=insecure,
        verbose=verbose,
    )

    asyncio.run(
        _run_cli_scan(config, json_mode=json_mode, report=report, report_dir=report_dir)
    )


async def _run_cli_scan(
    config: ScanConfig,
    *,
    json_mode: bool = False,
    report: bool = True,
    report_dir: str = ".",
) -> None:
    """Run scan with Rich progress output."""
    _progress_state: dict = {"bar": None, "task_id": None, "phase": None}

    # Rich progress bar — create one per phase
    progress_bars: dict[str, Progress] = {}

    async def on_progress(phase: str, current: int, total: int, detail: str) -> None:
        if json_mode:
            return

        # Phase message
        if detail and (phase != _progress_state.get("phase") or current == 0):
            phase_labels = {
                "discovery": "Phase 1",
                "user_context": "Phase 2",
                "enumeration": "Phase 3",
                "crud_test": "Phase 3b",
                "apex": "Phase 4",
                "graphql": "Phase 5",
                "complete": "Done",
            }
            label = phase_labels.get(phase, phase)
            console.print(f"[cyan]{label}:[/cyan] {detail}", highlight=False)
            _progress_state["phase"] = phase

    try:
        engine = ScanEngine(config, on_progress=on_progress)
        result = await engine.run()
    except DiscoveryError as e:
        if json_mode:
            result = ScanResult(target_url=config.url)
            json_output.render(result, validated_only=not config.skip_validation)
        else:
            console.print(f"[red]Discovery failed:[/red] {e}")
        sys.exit(1)

    validated_only = not config.skip_validation

    if json_mode:
        json_output.render(result, validated_only=validated_only)
    else:
        # Summary stats
        accessible = result.validated_objects if validated_only else result.accessible_objects
        callable_apex = [
            r for r in result.apex_results
            if r.status == ApexMethodStatus.CALLABLE and (not validated_only or r.validated is True)
        ]
        gql_count = len(result.graphql_results) if result.graphql_available else 0

        console.print()
        summary_parts = [
            f"{len(accessible)} accessible objects",
            f"{len(callable_apex)} callable Apex methods",
        ]
        if gql_count:
            summary_parts.append(f"{gql_count} GraphQL-enumerated objects")
        console.print(f"[green]Scan complete:[/green] " + ", ".join(summary_parts))

        # HTML report
        if report:
            report_path = html_output.write_report(result, output_dir=report_dir, validated_only=validated_only)
            console.print(f"[green]Report:[/green] {report_path}")


@main.command()
@click.option("-u", "--url", required=True, help="Salesforce instance URL")
@click.option("--alias", default=None, help="Org alias for sf CLI")
@click.option("--output-dir", type=click.Path(file_okay=False), default=".", help="Directory for output files")
@click.option("--skip-apex", is_flag=True, help="Skip Apex class enumeration")
@click.option("--skip-objects", is_flag=True, help="Skip sObject enumeration")
@click.option("-v", "--verbose", is_flag=True, help="Debug output")
def recon(
    url: str,
    alias: str | None,
    output_dir: str,
    skip_apex: bool,
    skip_objects: bool,
    verbose: bool,
) -> None:
    """Enumerate objects and Apex methods via Salesforce CLI (requires sf)."""
    from .recon import (
        ReconResult,
        check_sf_cli,
        enumerate_aura_methods,
        enumerate_objects as recon_enumerate_objects,
        save_results,
        sf_login,
    )

    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    instance_url = url.rstrip("/")
    result = ReconResult(instance_url=instance_url)

    try:
        console.print("[cyan]Step 1:[/cyan] Checking sf CLI...", highlight=False)
        sf_path = check_sf_cli()
        console.print(f"  Found: {sf_path}")

        console.print("[cyan]Step 2:[/cyan] Browser login...", highlight=False)
        console.print("  Opening browser — complete the login flow...")
        username = sf_login(instance_url, alias=alias)
        result.username = username
        target_org = alias or username
        console.print(f"  Authenticated as: [green]{username}[/green]")

        if not skip_objects:
            console.print("[cyan]Step 3:[/cyan] Enumerating sObjects...", highlight=False)
            result.objects = recon_enumerate_objects(target_org)
            console.print(f"  Found [green]{len(result.objects)}[/green] objects")

        if not skip_apex:
            step = "4" if not skip_objects else "3"
            console.print(f"[cyan]Step {step}:[/cyan] Querying @AuraEnabled Apex methods...", highlight=False)
            result.apex_methods = enumerate_aura_methods(target_org)
            console.print(f"  Found [green]{len(result.apex_methods)}[/green] methods")

        objects_path, apex_path = save_results(result, output_dir=output_dir)

        console.print()
        console.print("[green]Recon complete![/green]")
        if objects_path:
            console.print(f"  Objects file: {objects_path}")
        if apex_path:
            console.print(f"  Apex file:    {apex_path}")

        # Print next-steps command
        console.print()
        console.print("[cyan]Next steps — run scan with recon output:[/cyan]")
        cmd_parts = ["aura-privesc scan -u <TARGET_COMMUNITY_URL>"]
        if objects_path:
            cmd_parts.append(f"  --objects-file {objects_path}")
        if apex_path:
            cmd_parts.append(f"  --apex-file {apex_path}")
        console.print(" \\\n".join(cmd_parts))

    except ReconError as e:
        console.print(f"[red]Recon error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.option("--port", default=8888, type=int, help="Port to serve on")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
def serve(port: int, no_browser: bool, host: str) -> None:
    """Start the web UI."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error:[/red] Web UI requires extra dependencies. Install with:")
        console.print("  pip install 'aura-privesc[web]'")
        sys.exit(1)

    if host != "127.0.0.1":
        console.print("[yellow]WARNING: Binding to non-localhost. API has no authentication.[/yellow]")

    console.print(f"[cyan]Starting aura-privesc web UI on http://{host}:{port}[/cyan]")

    if not no_browser:
        # Open browser after a short delay to let server start
        import threading
        def _open():
            import time
            time.sleep(1)
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        "aura_privesc.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        log_level="info",
    )
