"""
Command-line interface for LineageGuard.
"""

import sys
import json
import click
from lineageguard.client import OpenMetadataClient
from lineageguard.lineage import walk_downstream
from lineageguard.governance import fetch_signals_for_many
from lineageguard.ranker import rank_signals
from lineageguard.formatter import to_json, to_markdown


@click.group()
def main() -> None:
    """LineageGuard: Semantic dependency analysis for data platforms."""
    # Ensure stdout handles emojis even when piped on Windows
    sys.stdout.reconfigure(encoding='utf-8')


@main.command()
@click.option('--table', '-t', required=True, help="Fully qualified name of the table being changed.")
@click.option('--drop-column', help="Simulate dropping a column. Mutually exclusive with --rename-column and --drop-table.")
@click.option('--rename-column', help='Format "old_name:new_name". Mutually exclusive with --drop-column and --drop-table.')
@click.option('--drop-table', is_flag=True, help="Simulate dropping the whole table.")
@click.option('--depth', '-d', type=int, default=5, help="Lineage traversal depth. Default 5.")
@click.option('--format', '-f', 'output_format', type=click.Choice(["markdown", "json"]), default="markdown", help='Output format. Default "markdown".')
def analyze(table: str, drop_column: str | None, rename_column: str | None, drop_table: bool, depth: int, output_format: str) -> None:
    """
    Analyze the downstream impact of a schema change.
    
    Example:
      lineageguard analyze \
          --table Stripe.stripe_db.public.raw_stripe_data \
          --drop-column revenue_cents
    """
    # 1. Validation
    changes = [bool(drop_column), bool(rename_column), drop_table]
    if sum(changes) != 1:
        click.echo("[ERROR] Exactly one of --drop-column, --rename-column, or --drop-table must be provided.", err=True)
        sys.exit(2)
        
    change_type_str = ""
    change_details_obj = {}
    human_change = ""
    formatted_change = ""
    
    if drop_column:
        change_type_str = "drop_column"
        change_details_obj = {"column_name": drop_column}
        human_change = f"drop column '{drop_column}'"
        formatted_change = drop_column
    elif rename_column:
        if ":" not in rename_column:
            click.echo("[ERROR] --rename-column value must contain ':' (e.g., old:new).", err=True)
            sys.exit(2)
        old_col, new_col = rename_column.split(":", 1)
        change_type_str = "rename_column"
        change_details_obj = {"old_name": old_col, "new_name": new_col}
        human_change = f"rename column '{old_col}' -> '{new_col}'"
        formatted_change = f"'{old_col}' -> '{new_col}'"
    elif drop_table:
        change_type_str = "drop_table"
        change_details_obj = {}
        human_change = "drop entire table"
        formatted_change = "N/A"

    # Print initial info to STDERR
    click.echo(f"[INFO] LineageGuard analyzing: {table}", err=True)
    click.echo(f"[INFO] Change: {human_change}", err=True)
    click.echo(f"[INFO] Traversal depth: {depth}", err=True)

    try:
        with OpenMetadataClient() as client:
            entities = walk_downstream(client, table, entity_type="table", max_depth=depth)
            signals = fetch_signals_for_many(client, entities)
            result = rank_signals(table, signals)
            
            if output_format == "json":
                json_dict = to_json(result)
                json_dict["change_spec"] = {
                    "table_fqn": table,
                    "change_type": change_type_str,
                    "change_details": change_details_obj
                }
                click.echo(json.dumps(json_dict, indent=2))
            else:
                md_str = to_markdown(result)
                lines = md_str.split("\n")
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if line.startswith("**Source entity:**"):
                        new_lines.append(f"**Change type:** {change_type_str}")
                        new_lines.append(f"**Change details:** {formatted_change}")
                click.echo("\n".join(new_lines))
                
            N = len(result.findings)
            C = result.summary.get('critical', 0)
            H = result.summary.get('high', 0)
            W = result.summary.get('warning', 0)
            I = result.summary.get('info', 0)
            
            click.echo(f"[OK] {N} findings: {C} CRITICAL, {H} HIGH, {W} WARNING, {I} INFO", err=True)
            
            if C > 0:
                sys.exit(2)
            sys.exit(0)
            
    except RuntimeError as e:
        click.echo(f"[ERROR] {str(e)}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("[ABORTED]", err=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
