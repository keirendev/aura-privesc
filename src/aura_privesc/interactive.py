"""Interactive CRUD validation flow with Rich prompts."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from .client import AuraClient
from .crud import (
    build_test_values,
    create_record,
    delete_record,
    extract_required_fields,
    get_object_field_metadata,
    read_records,
    update_record,
)
from .models import CrudValidationResult, ObjectResult, RiskLevel

console = Console(stderr=True)

RISK_COLORS = {
    RiskLevel.CRITICAL: "bold red",
    RiskLevel.HIGH: "red",
    RiskLevel.MEDIUM: "yellow",
    RiskLevel.LOW: "green",
    RiskLevel.INFO: "dim",
}

CHECK = "[green]\u2713[/green]"
CROSS = "[red]\u2717[/red]"
SKIP = "[dim]\u2014[/dim]"


def _risk_badge(risk: RiskLevel) -> str:
    style = RISK_COLORS.get(risk, "")
    return f"[{style}]{risk.value.upper()}[/{style}]"


def _op_status(success: bool | None) -> str:
    if success is None:
        return SKIP
    return CHECK if success else CROSS


def _show_object_header(obj: ObjectResult) -> None:
    """Display object info panel before prompting."""
    c = obj.crud
    perms = []
    if c.readable:
        perms.append("R")
    if c.createable:
        perms.append("C")
    if c.updateable:
        perms.append("U")
    if c.deletable:
        perms.append("D")
    if c.queryable:
        perms.append("Q")
    perm_str = "/".join(perms) if perms else "none"

    count_str = str(obj.record_count) if obj.record_count is not None else "?"
    risk_style = RISK_COLORS.get(obj.risk, "")
    header = Text()
    header.append(obj.name, style="bold")
    header.append("  ")
    header.append(obj.risk.value.upper(), style=risk_style)
    header.append(f"  Perms: {perm_str}  Records: {count_str}")
    console.print(Panel(header, border_style="cyan"))


async def _validate_single_object(
    client: AuraClient, obj: ObjectResult,
) -> ObjectResult:
    """Run interactive CRUD validation for one object."""
    _show_object_header(obj)

    if not Confirm.ask(f"  Validate [bold]{obj.name}[/bold]?", default=True):
        obj.crud_validation = CrudValidationResult(
            object_name=obj.name, skipped=True, skip_reason="User skipped",
        )
        console.print()
        return obj

    validation = CrudValidationResult(object_name=obj.name)

    # --- READ ---
    console.print("  [cyan]READ:[/cyan] Attempting to read records...")
    read_result = await read_records(client, obj.name)
    validation.read = read_result

    if read_result.success:
        count = read_result.record_data.get("count") if read_result.record_data else None
        console.print(f"  {CHECK} Read succeeded — {count} record(s) found")
        sample_id = read_result.record_id
    else:
        console.print(f"  {CROSS} Read failed: {read_result.error}")
        sample_id = None

    # --- WRITE OPERATIONS ---
    has_write = obj.crud.createable or obj.crud.updateable or obj.crud.deletable
    created_id: str | None = None

    if has_write:
        if not Confirm.ask("  Test [bold yellow]write operations[/bold yellow]?", default=False):
            console.print("  [dim]Write operations skipped.[/dim]")
            obj.crud_validation = validation
            console.print()
            return obj

        # --- CREATE ---
        if obj.crud.createable:
            console.print("  [cyan]CREATE:[/cyan] Fetching field metadata...")
            obj_info = await get_object_field_metadata(client, obj.name)

            if obj_info:
                required = extract_required_fields(obj_info)
                if required:
                    test_vals = build_test_values(required)
                    console.print(f"  [dim]Fields: {', '.join(test_vals.keys())}[/dim]")
                    create_result = await create_record(client, obj.name, test_vals)
                else:
                    # No required fields — try with empty (some objects allow it)
                    create_result = await create_record(client, obj.name, {})
            else:
                # No metadata — try with empty fields
                create_result = await create_record(client, obj.name, {})

            validation.create = create_result

            if create_result.success:
                created_id = create_result.record_id
                console.print(f"  {CHECK} Create succeeded — ID: {created_id}")
            else:
                console.print(f"  {CROSS} Create failed: {create_result.error}")

        # --- UPDATE ---
        if obj.crud.updateable:
            target_id = created_id or sample_id

            if not target_id:
                target_id = Prompt.ask(
                    "  Enter a record ID for update test (or 'skip')",
                    default="skip",
                )
                if target_id.lower() == "skip":
                    target_id = None

            if target_id:
                console.print(f"  [cyan]UPDATE:[/cyan] Updating {target_id}...")
                # Use a harmless field update — try to re-set an existing value
                obj_info = obj_info if obj.crud.createable and obj_info else await get_object_field_metadata(client, obj.name)
                update_fields: dict = {}
                if obj_info:
                    fields_meta = obj_info.get("fields", {})
                    for fname, fmeta in fields_meta.items():
                        if isinstance(fmeta, dict) and fmeta.get("updateable") and fmeta.get("dataType") == "String":
                            update_fields[fname] = "AuraPrivescTest_update"
                            break
                if not update_fields:
                    update_fields = {"Description": "AuraPrivescTest_update"}

                update_result = await update_record(client, obj.name, target_id, update_fields)
                validation.update = update_result

                if update_result.success:
                    console.print(f"  {CHECK} Update succeeded on {target_id}")
                else:
                    console.print(f"  {CROSS} Update failed: {update_result.error}")

        # --- DELETE ---
        if obj.crud.deletable:
            # Prefer deleting the record we created (cleanup)
            if created_id:
                target_id = created_id
                console.print(f"  [cyan]DELETE:[/cyan] Cleaning up created record {target_id}...")
                if Confirm.ask(f"  Confirm DELETE of [bold red]{target_id}[/bold red]?", default=True):
                    delete_result = await delete_record(client, target_id)
                    validation.delete = delete_result
                    if delete_result.success:
                        console.print(f"  {CHECK} Delete succeeded — {target_id} removed")
                    else:
                        console.print(f"  {CROSS} Delete failed: {delete_result.error}")
                else:
                    console.print("  [dim]Delete skipped by user.[/dim]")
            else:
                target_id = Prompt.ask(
                    "  Enter a record ID for delete test (or 'skip')",
                    default="skip",
                )
                if target_id.lower() != "skip":
                    if Confirm.ask(f"  Confirm DELETE of [bold red]{target_id}[/bold red]?", default=False):
                        delete_result = await delete_record(client, target_id)
                        validation.delete = delete_result
                        if delete_result.success:
                            console.print(f"  {CHECK} Delete succeeded — {target_id} removed")
                        else:
                            console.print(f"  {CROSS} Delete failed: {delete_result.error}")
                    else:
                        console.print("  [dim]Delete skipped by user.[/dim]")

    obj.crud_validation = validation
    console.print()
    return obj


async def run_interactive_validation(
    client: AuraClient,
    objects: list[ObjectResult],
) -> list[ObjectResult]:
    """Walk user through per-object CRUD validation for accessible objects.

    Returns the full object list with crud_validation populated on tested objects.
    """
    accessible = [o for o in objects if o.accessible]

    if not accessible:
        console.print("[dim]No accessible objects to validate.[/dim]")
        return objects

    console.print()
    console.print(
        Panel(
            f"[bold]Interactive CRUD Validation[/bold]\n"
            f"{len(accessible)} accessible object(s) to validate.\n"
            f"You will be prompted for each object.",
            border_style="magenta",
        )
    )
    console.print()

    for obj in accessible:
        await _validate_single_object(client, obj)

    return objects
