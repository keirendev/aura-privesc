"""Click CLI — wires everything together."""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from rich.console import Console

from . import __version__
from .apex import build_apex_list, discover_apex_from_js, test_apex_methods
from .client import AuraClient
from .discovery import run_discovery
from .enumerator import build_object_list, enumerate_objects
from .exceptions import AuraError, DiscoveryError
from .models import ScanResult
from .interactive import run_interactive_validation
from .output import html_output, json_output, rich_output
from .permissions import check_soql_capability, get_config_objects, get_user_info

console = Console(stderr=True)


@click.command()
@click.option("-u", "--url", required=True, help="Target Salesforce base/community URL")
@click.option("-t", "--token", default=None, help="Aura token (omit for guest mode)")
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
@click.version_option(version=__version__)
def main(
    url: str,
    token: str | None,
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
    """Salesforce Aura/Lightning privilege escalation scanner."""
    if interactive and json_mode:
        console.print("[red]Error:[/red] --interactive and --json cannot be used together.")
        sys.exit(1)

    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    asyncio.run(
        _run(
            url=url,
            token=token,
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


async def _run(
    *,
    url: str,
    token: str | None,
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
        except DiscoveryError as e:
            if json_mode:
                result.discovery = None
            else:
                console.print(f"[red]Discovery failed:[/red] {e}")
            _output(result, json_mode, validated_only=not skip_validation)
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

        result.objects = await enumerate_objects(
            client,
            all_objects,
            skip_crud=skip_crud,
            skip_records=skip_records,
            skip_validation=skip_validation,
        )

        # Phase 4: Apex testing
        if not skip_apex:
            if not json_mode:
                console.print(f"[cyan]Phase 4:[/cyan] Apex controller testing{validation_tag}...", highlight=False)

            discovered_apex = await discover_apex_from_js(client, base_url)
            user_apex = _load_lines(apex_file) if apex_file else None
            apex_list = build_apex_list(discovered_apex, user_apex)

            if apex_list:
                result.apex_results = await test_apex_methods(
                    client, apex_list, skip_validation=skip_validation,
                )

        # Phase 5: Interactive CRUD validation
        if interactive:
            if not json_mode:
                console.print("[cyan]Phase 5:[/cyan] Interactive CRUD validation...", highlight=False)
            result.interactive_mode = True
            result.objects = await run_interactive_validation(client, result.objects)

    validated_only = not skip_validation
    _output(result, json_mode, validated_only=validated_only)

    # Phase 6: HTML report
    if report and not json_mode:
        report_path = html_output.write_report(result, validated_only=validated_only, output_dir=report_dir)
        console.print(f"[green]Report written to:[/green] {report_path}")


def _output(result: ScanResult, json_mode: bool, *, validated_only: bool = False) -> None:
    if json_mode:
        json_output.render(result, validated_only=validated_only)
    else:
        rich_output.render(result, validated_only=validated_only)


def _load_lines(path: str) -> list[str]:
    """Load non-empty, non-comment lines from a file."""
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines
