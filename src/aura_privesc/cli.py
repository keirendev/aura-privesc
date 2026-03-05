"""Click CLI — wires everything together."""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.progress import Progress, BarColumn, MofNCompleteColumn, TimeElapsedColumn

from . import __version__
from .apex import build_apex_list, discover_apex_from_js, test_apex_methods
from .client import AuraClient
from .discovery import run_discovery
from .enumerator import build_object_list, enumerate_objects
from .exceptions import AuraError, DiscoveryError, ReconError
from .models import ApexMethodStatus, ScanResult
from .interactive import run_interactive_validation
from .output import html_output, json_output
from .permissions import check_soql_capability, get_config_objects, get_user_info

console = Console(stderr=True)


class DefaultGroup(click.Group):
    """Falls back to 'scan' when no subcommand matches."""

    def parse_args(self, ctx, args):
        # Let --help and --version be handled by the group itself
        if args and args[0] not in self.commands and args[0] not in ("--help", "-h", "--version"):
            args = ["scan"] + list(args)
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
@click.option("--timeout", default=30, type=int, help="HTTP timeout in seconds")
@click.option("--delay", default=0, type=int, help="Delay between requests in ms")
@click.option("--concurrency", default=5, type=int, help="Max concurrent requests")
@click.option("--proxy", default=None, help="HTTP proxy URL")
@click.option("--insecure", is_flag=True, help="Disable TLS verification")
@click.option("-v", "--verbose", is_flag=True, help="Show raw request/response data")
@click.option("-i", "--interactive", is_flag=True, help="Interactive CRUD validation mode")
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
    timeout: int,
    delay: int,
    concurrency: int,
    proxy: str | None,
    insecure: bool,
    verbose: bool,
    interactive: bool,
    report: bool,
    report_dir: str,
) -> None:
    """Run the Aura privilege escalation scan."""
    if interactive and json_mode:
        console.print("[red]Error:[/red] --interactive and --json cannot be used together.")
        sys.exit(1)

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

    asyncio.run(
        _run(
            url=url,
            token=token,
            sid=sid,
            manual_context=manual_context,
            manual_endpoint=manual_endpoint,
            objects_file=objects_file,
            apex_file=apex_file,
            json_mode=json_mode,
            skip_crud=skip_crud,
            skip_records=skip_records,
            skip_apex=skip_apex,
            skip_validation=skip_validation,
            timeout=timeout,
            delay=delay,
            concurrency=concurrency,
            proxy=proxy,
            insecure=insecure,
            verbose=verbose,
            interactive=interactive,
            report=report,
            report_dir=report_dir,
        )
    )


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


async def _run(
    *,
    url: str,
    token: str | None,
    sid: str | None = None,
    manual_context: str | None,
    manual_endpoint: str | None,
    objects_file: str | None,
    apex_file: str | None,
    json_mode: bool,
    skip_crud: bool,
    skip_records: bool,
    skip_apex: bool,
    skip_validation: bool,
    timeout: int,
    delay: int,
    concurrency: int,
    proxy: str | None,
    insecure: bool,
    verbose: bool,
    interactive: bool = False,
    report: bool = True,
    report_dir: str = ".",
) -> None:
    base_url = url.rstrip("/")
    result = ScanResult(target_url=base_url)

    async with AuraClient(
        base_url=base_url,
        endpoint="/s/sfsites/aura",  # placeholder, discovery will update
        token=token,
        concurrency=concurrency,
        delay_ms=delay,
        timeout=timeout,
        proxy=proxy,
        insecure=insecure,
        verbose=verbose,
        sid=sid,
    ) as client:
        # Phase 1: Discovery
        if not json_mode:
            console.print("[cyan]Phase 1:[/cyan] Discovery...", highlight=False)

        try:
            discovery = await run_discovery(
                client,
                base_url,
                manual_endpoint=manual_endpoint,
                manual_context=manual_context,
            )
            result.discovery = discovery
            result.aura_url = client.aura_url
            result.aura_token = client.aura_token
            result.aura_context = client._build_context()
            result.sid = client.sid
        except DiscoveryError as e:
            if json_mode:
                result.discovery = None
                json_output.render(result, validated_only=not skip_validation)
            else:
                console.print(f"[red]Discovery failed:[/red] {e}")
            sys.exit(1)

        # Phase 2: User context + SOQL check
        if not json_mode:
            console.print("[cyan]Phase 2:[/cyan] Connectivity & user context...", highlight=False)

        result.user_info = await get_user_info(client)
        result.soql_capable = await check_soql_capability(client)

        # Gather discovered objects from config
        config_objects = await get_config_objects(client)

        # Phase 3: Object enumeration
        user_objects = _load_lines(objects_file) if objects_file else None
        all_objects = build_object_list(config_objects, user_objects)

        validation_tag = " (with validation)" if not skip_validation else ""

        if not json_mode:
            console.print(
                f"[cyan]Phase 3:[/cyan] Enumerating {len(all_objects)} objects{validation_tag}...",
                highlight=False,
            )

        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            disable=json_mode,
        ) as progress:
            tid = progress.add_task("Enumerating objects", total=len(all_objects))
            result.objects = await enumerate_objects(
                client,
                all_objects,
                skip_crud=skip_crud,
                skip_records=skip_records,
                skip_validation=skip_validation,
                progress=progress,
                task_id=tid,
            )

        # Phase 4: Apex testing
        if not skip_apex:
            if not json_mode:
                console.print(f"[cyan]Phase 4:[/cyan] Apex controller testing{validation_tag}...", highlight=False)

            discovered_apex = await discover_apex_from_js(client, base_url)
            user_apex = _load_lines(apex_file) if apex_file else None
            apex_list = build_apex_list(discovered_apex, user_apex)

            if apex_list:
                with Progress(
                    "[progress.description]{task.description}",
                    BarColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=console,
                    disable=json_mode,
                ) as progress:
                    tid = progress.add_task("Testing Apex methods", total=len(apex_list))
                    result.apex_results = await test_apex_methods(
                        client, apex_list, skip_validation=skip_validation,
                        progress=progress, task_id=tid,
                    )

        # Phase 5: Interactive CRUD validation
        if interactive:
            if not json_mode:
                console.print("[cyan]Phase 5:[/cyan] Interactive CRUD validation...", highlight=False)
            result.interactive_mode = True
            result.objects = await run_interactive_validation(client, result.objects)

    validated_only = not skip_validation

    if json_mode:
        json_output.render(result, validated_only=validated_only)
    else:
        # Summary stats
        accessible = result.validated_objects if validated_only else result.accessible_objects
        callable_apex = [
            r for r in result.apex_results
            if r.status == ApexMethodStatus.CALLABLE and (not validated_only or r.validated is True)
        ]
        console.print()
        console.print(
            f"[green]Scan complete:[/green] "
            f"{len(accessible)} accessible objects, "
            f"{len(callable_apex)} callable Apex methods"
        )

        # HTML report
        if report:
            report_path = html_output.write_report(result, output_dir=report_dir, validated_only=validated_only)
            console.print(f"[green]Report:[/green] {report_path}")


def _load_lines(path: str) -> list[str]:
    """Load non-empty, non-comment lines from a file."""
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines
