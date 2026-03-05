"""Rich terminal output: tables, panels, progress bars."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ..models import ApexMethodStatus, CrudValidationResult, ObjectResult, RiskLevel, ScanResult

console = Console()

RISK_COLORS = {
    RiskLevel.CRITICAL: "bold red",
    RiskLevel.HIGH: "red",
    RiskLevel.MEDIUM: "yellow",
    RiskLevel.LOW: "green",
    RiskLevel.INFO: "dim",
}

CHECK = "[green]\u2713[/green]"
CROSS = "[dim]\u2717[/dim]"


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

    console.print(Panel(table, title="[bold]Discovery[/bold]", border_style="blue"))


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
    table.add_column("Q", justify="center")
    table.add_column("Records", justify="right")
    table.add_column("Risk", justify="center")

    # Sort: critical first, then high, medium, low
    risk_order = {RiskLevel.CRITICAL: 0, RiskLevel.HIGH: 1, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 3, RiskLevel.INFO: 4}
    display.sort(key=lambda o: (risk_order.get(o.risk, 99), o.name))

    for obj in display:
        c = obj.crud
        count_str = str(obj.record_count) if obj.record_count is not None else "-"
        risk_style = RISK_COLORS.get(obj.risk, "")
        risk_text = Text(obj.risk.value.upper(), style=risk_style)

        table.add_row(
            obj.name,
            CHECK if c.readable else CROSS,
            CHECK if c.createable else CROSS,
            CHECK if c.updateable else CROSS,
            CHECK if c.deletable else CROSS,
            CHECK if c.queryable else CROSS,
            count_str,
            risk_text,
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


def print_summary(result: ScanResult, validated_only: bool = False) -> None:
    if validated_only:
        accessible = result.validated_objects
        label = "Objects validated"
    else:
        accessible = result.accessible_objects
        label = "Objects accessible"

    critical = [o for o in accessible if o.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)]

    lines: list[str] = []
    lines.append(f"Objects scanned: {len(result.objects)}")
    lines.append(f"{label}: {len(accessible)}")

    if critical:
        lines.append(f"[bold red]High-risk findings: {len(critical)}[/bold red]")
        for obj in critical:
            perms = []
            if obj.crud.createable:
                perms.append("C")
            if obj.crud.readable:
                perms.append("R")
            if obj.crud.updateable:
                perms.append("U")
            if obj.crud.deletable:
                perms.append("D")
            lines.append(f"  [red]\u2022 {obj.name}[/red] ({'/'.join(perms)})")
    else:
        lines.append("[green]No high-risk findings.[/green]")

    if validated_only:
        callable_apex = [r for r in result.apex_results if r.status == ApexMethodStatus.CALLABLE and r.validated is True]
    else:
        callable_apex = [r for r in result.apex_results if r.status == ApexMethodStatus.CALLABLE]

    if callable_apex:
        lines.append(f"Callable Apex methods: {len(callable_apex)}")

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

    has_any = any(o.proof for o in proof_objects) or bool(proof_apex)

    if not has_any:
        return

    console.print(Panel("[bold]Validation Commands[/bold]", border_style="green"))

    for obj in proof_objects:
        if not obj.proof:
            continue
        risk_style = RISK_COLORS.get(obj.risk, "")
        label = f"{obj.name} ({obj.risk.value.upper()})"
        console.print(Rule(Text(label, style=risk_style), style="dim"))

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


def _crud_op_cell(cv: CrudValidationResult, op: str) -> str:
    """Return a check/cross/skip for a CRUD operation."""
    result = getattr(cv, op, None)
    if result is None:
        return "[dim]\u2014[/dim]"
    return CHECK if result.success else "[red]\u2717[/red]"


def print_crud_validation(objects: list[ObjectResult]) -> None:
    """Print CRUD validation results table for interactive mode."""
    validated = [o for o in objects if o.crud_validation is not None and not o.crud_validation.skipped]

    if not validated:
        console.print("[dim]No CRUD validations performed.[/dim]")
        return

    table = Table(title=f"CRUD Validation Results ({len(validated)} objects)")
    table.add_column("Object", style="bold")
    table.add_column("Read", justify="center")
    table.add_column("Create", justify="center")
    table.add_column("Update", justify="center")
    table.add_column("Delete", justify="center")
    table.add_column("Proven Ops", justify="left")

    for obj in validated:
        cv = obj.crud_validation
        assert cv is not None
        proven = ", ".join(cv.proven_operations) if cv.proven_operations else "[dim]none[/dim]"
        table.add_row(
            obj.name,
            _crud_op_cell(cv, "read"),
            _crud_op_cell(cv, "create"),
            _crud_op_cell(cv, "update"),
            _crud_op_cell(cv, "delete"),
            proven,
        )

    console.print(table)


def render(result: ScanResult, validated_only: bool = False) -> None:
    """Full rich output rendering."""
    print_banner()
    console.print()
    print_discovery(result)
    console.print()
    print_objects(result.objects, validated_only=validated_only)
    console.print()
    if result.apex_results:
        print_apex(result.apex_results, validated_only=validated_only)
        console.print()
    if result.interactive_mode:
        print_crud_validation(result.objects)
        console.print()
    print_summary(result, validated_only=validated_only)
    console.print()
    print_proofs(result, validated_only=validated_only)
