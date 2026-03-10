"""Rich terminal output: tables, panels, progress bars."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ..models import ApexMethodStatus, GraphQLResult, ObjectResult, RestApiResult, RiskLevel, ScanResult

console = Console()

CHECK = "[green]\u2713[/green]"
CROSS = "[red]\u2717[/red]"
DASH = "[dim]\u2014[/dim]"


def print_banner() -> None:
    banner = Text()
    banner.append("aura-privesc", style="bold cyan")
    banner.append(" \u2014 Salesforce Aura Privilege Scanner", style="dim")
    console.print(Panel(banner, border_style="cyan"))


def print_discovery(result: ScanResult) -> None:
    if not result.discovery:
        return

    d = result.discovery
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Target", result.target_url)
    table.add_row("Endpoint", d.endpoint)
    table.add_row("Mode", d.mode)
    if d.fwuid:
        table.add_row("fwuid", d.fwuid)
    if d.app_name:
        table.add_row("App", d.app_name)

    if result.user_info:
        u = result.user_info
        if u.display_name:
            table.add_row("User", u.display_name)
        if u.username:
            table.add_row("Username", u.username)
        if u.email:
            table.add_row("Email", u.email)

    table.add_row("SOQL", CHECK if result.soql_capable else CROSS)

    if result.rest_api:
        table.add_row("REST API", CHECK if result.rest_api.api_enabled else CROSS)
        if result.rest_api.api_version:
            table.add_row("API Version", f"v{result.rest_api.api_version}")

    console.print(Panel(table, title="[bold]Discovery[/bold]", border_style="blue"))


def _crud_cell(obj: ObjectResult, op: str) -> str:
    """Three-state display for C/U/D: proven / failed / not attempted."""
    cv = obj.crud_validation
    if cv is not None:
        result = getattr(cv, op, None)
        if result is not None:
            return CHECK if result.success else CROSS
    return DASH


def print_objects(objects: list[ObjectResult], validated_only: bool = False) -> None:
    accessible = [o for o in objects if o.accessible]

    if validated_only:
        validated = [o for o in accessible if o.validated is True]
        rejected = len(accessible) - len(validated)
        display = validated
    else:
        display = accessible
        rejected = 0

    if not display:
        console.print("[dim]No accessible objects found.[/dim]")
        if rejected:
            console.print(f"[dim]({rejected} finding(s) rejected by validation)[/dim]")
        return

    title = f"Accessible Objects ({len(display)}/{len(objects)})"
    if rejected:
        title += f" [dim]({rejected} rejected by validation)[/dim]"

    table = Table(title=title)
    table.add_column("Object", style="bold")
    table.add_column("R", justify="center")
    table.add_column("C", justify="center")
    table.add_column("U", justify="center")
    table.add_column("D", justify="center")
    table.add_column("Records", justify="right")

    display.sort(key=lambda o: o.name)

    for obj in display:
        count_str = str(obj.record_count) if obj.record_count is not None else "-"

        table.add_row(
            obj.name,
            CHECK if obj.crud.readable else CROSS,
            _crud_cell(obj, "create"),
            _crud_cell(obj, "update"),
            _crud_cell(obj, "delete"),
            count_str,
        )

    console.print(table)


def print_apex(results: list, validated_only: bool = False) -> None:
    if not results:
        return

    callable_results = [r for r in results if r.status == ApexMethodStatus.CALLABLE]

    if validated_only:
        validated_callable = [r for r in callable_results if r.validated is True]
        rejected = len(callable_results) - len(validated_callable)
        # Show validated callable + all non-callable results
        display = validated_callable + [r for r in results if r.status != ApexMethodStatus.CALLABLE]
    else:
        validated_callable = callable_results
        rejected = 0
        display = results

    table = Table(title=f"Apex Controllers ({len(validated_callable)} callable / {len(results)} tested)")
    table.add_column("Controller.Method", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Message")

    if rejected:
        console.print(f"[dim]({rejected} callable finding(s) rejected by validation)[/dim]")

    status_styles = {
        ApexMethodStatus.CALLABLE: "[green]CALLABLE[/green]",
        ApexMethodStatus.DENIED: "[red]DENIED[/red]",
        ApexMethodStatus.NOT_FOUND: "[dim]NOT FOUND[/dim]",
        ApexMethodStatus.ERROR: "[yellow]ERROR[/yellow]",
    }

    # Sort: callable first
    order = {ApexMethodStatus.CALLABLE: 0, ApexMethodStatus.DENIED: 1, ApexMethodStatus.ERROR: 2, ApexMethodStatus.NOT_FOUND: 3}
    sorted_results = sorted(display, key=lambda r: (order.get(r.status, 99), r.controller_method))

    for r in sorted_results:
        table.add_row(
            r.controller_method,
            status_styles.get(r.status, str(r.status)),
            r.message or "",
        )

    console.print(table)


def print_rest_api(rest_api: RestApiResult) -> None:
    """Print REST API access check results."""
    border = "green" if rest_api.api_enabled else "red"
    status = "[green]ENABLED[/green]" if rest_api.api_enabled else "[red]DISABLED[/red]"

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Detail")

    for check in rest_api.checks:
        icon = CHECK if check.success else CROSS
        detail = check.detail or check.error or ""
        table.add_row(check.name, icon, detail)

    console.print(Panel(table, title=f"[bold]REST API (API Enabled)[/bold] — {status}", border_style=border))

    if rest_api.soql_example_curl:
        from rich.syntax import Syntax
        console.print(Panel(
            Syntax(rest_api.soql_example_curl, "bash", theme="monokai", word_wrap=True),
            title="[bold]SOQL Query (REST API)[/bold]",
            border_style="green",
        ))


def print_graphql(graphql_results: list[GraphQLResult], graphql_available: bool) -> None:
    if not graphql_available:
        return
    if not graphql_results:
        console.print("[dim]GraphQL available but no objects enumerated.[/dim]")
        return

    table = Table(title=f"GraphQL Enumeration ({len(graphql_results)} objects)")
    table.add_column("Object", style="bold")
    table.add_column("Record Count", justify="right")
    table.add_column("Fields", justify="right")

    graphql_results_sorted = sorted(graphql_results, key=lambda r: r.object_name)
    for r in graphql_results_sorted:
        count_str = str(r.total_count) if r.total_count is not None else "-"
        fields_str = str(len(r.fields)) if r.fields else "-"
        table.add_row(r.object_name, count_str, fields_str)

    console.print(table)


def print_summary(result: ScanResult, validated_only: bool = False) -> None:
    if validated_only:
        accessible = result.validated_objects
        label = "Objects validated"
    else:
        accessible = result.accessible_objects
        label = "Objects accessible"

    writable = [o for o in accessible if o.crud.has_write]
    proven = [o for o in accessible if o.crud_validation is not None and o.crud_validation.proven_operations]

    lines: list[str] = []
    lines.append(f"Objects scanned: {len(result.objects)}")
    lines.append(f"{label}: {len(accessible)}")

    if writable:
        lines.append(f"Writable objects: {len(writable)}")
    if proven:
        lines.append(f"[bold red]Proven write access: {len(proven)}[/bold red]")
        for obj in proven:
            ops = ", ".join(obj.crud_validation.proven_operations)
            lines.append(f"  [red]\u2022 {obj.name}[/red] ({ops})")

    if validated_only:
        callable_apex = [r for r in result.apex_results if r.status == ApexMethodStatus.CALLABLE and r.validated is True]
    else:
        callable_apex = [r for r in result.apex_results if r.status == ApexMethodStatus.CALLABLE]

    if callable_apex:
        lines.append(f"Callable Apex methods: {len(callable_apex)}")

    if result.graphql_available:
        gql_with_counts = [r for r in result.graphql_results if r.total_count is not None]
        lines.append(f"GraphQL enumerated: {len(result.graphql_results)} objects, {len(gql_with_counts)} with counts")

    if result.rest_api and result.rest_api.api_enabled:
        successful = [c for c in result.rest_api.checks if c.success]
        lines.append(f"[bold green]API Enabled: YES[/bold green] ({len(successful)}/{len(result.rest_api.checks)} checks passed)")

    console.print(Panel("\n".join(lines), title="[bold]Summary[/bold]", border_style="cyan"))


def print_proofs(result: ScanResult, validated_only: bool = False) -> None:
    """Print curl proof commands for accessible objects and callable/denied apex methods."""
    if validated_only:
        proof_objects = result.validated_objects
        proof_apex = [a for a in result.apex_results
                      if a.proof and a.status in (ApexMethodStatus.CALLABLE, ApexMethodStatus.DENIED)
                      and a.validated is True]
    else:
        proof_objects = result.accessible_objects
        proof_apex = [a for a in result.apex_results
                      if a.proof and a.status in (ApexMethodStatus.CALLABLE, ApexMethodStatus.DENIED)]

    has_rest = result.rest_api and result.rest_api.api_enabled and any(c.success and c.proof for c in result.rest_api.checks)
    has_any = any(o.proof for o in proof_objects) or bool(proof_apex) or has_rest

    if not has_any:
        return

    console.print(Panel("[bold]Validation Commands[/bold]", border_style="green"))

    for obj in proof_objects:
        if not obj.proof:
            continue
        console.print(Rule(Text(obj.name, style="bold"), style="dim"))

        console.print(Text("# Metadata \u2014 confirms object is exposed and shows CRUD permissions", style="dim"))
        console.print(Text(obj.proof, style="green"), soft_wrap=True)

        if obj.proof_records:
            console.print()
            console.print(Text("# Records \u2014 retrieves actual data from the object", style="dim"))
            console.print(Text(obj.proof_records, style="green"), soft_wrap=True)

        console.print()

    for apex in proof_apex:
        style = "green" if apex.status == ApexMethodStatus.CALLABLE else "red"
        label = f"{apex.controller_method} ({apex.status.value.upper()})"
        console.print(Rule(Text(label, style=style), style="dim"))
        console.print(Text(apex.proof, style="green"), soft_wrap=True)
        console.print()

    # REST API proofs
    if result.rest_api and result.rest_api.api_enabled:
        rest_proofs = [c for c in result.rest_api.checks if c.success and c.proof]
        if rest_proofs:
            console.print(Rule(Text("REST API", style="bold"), style="dim"))
            for check in rest_proofs:
                console.print(Text(f"# {check.name}", style="dim"))
                console.print(Text(check.proof, style="green"), soft_wrap=True)
                console.print()

    # GraphQL proofs
    gql_proofs = [r for r in result.graphql_results if r.proof_count]
    if gql_proofs:
        console.print(Rule(Text("GraphQL — executeGraphQL", style="bold"), style="dim"))
        # Show proof for the first object as a representative example
        first = gql_proofs[0]
        console.print(Text("# Record count query", style="dim"))
        console.print(Text(first.proof_count, style="green"), soft_wrap=True)
        if first.proof_fields:
            console.print()
            console.print(Text("# Field introspection query", style="dim"))
            console.print(Text(first.proof_fields, style="green"), soft_wrap=True)
        console.print()


def render(result: ScanResult, validated_only: bool = False) -> None:
    """Full rich output rendering."""
    print_banner()
    console.print()
    print_discovery(result)
    console.print()
    if result.rest_api:
        print_rest_api(result.rest_api)
        console.print()
    print_objects(result.objects, validated_only=validated_only)
    console.print()
    if result.apex_results:
        print_apex(result.apex_results, validated_only=validated_only)
        console.print()
    if result.graphql_available:
        print_graphql(result.graphql_results, result.graphql_available)
        console.print()
    print_summary(result, validated_only=validated_only)
    console.print()
    print_proofs(result, validated_only=validated_only)
