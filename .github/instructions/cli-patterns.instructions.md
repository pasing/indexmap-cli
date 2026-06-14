---
description: "Use when adding, modifying, or reviewing Typer CLI commands in cli.py. Covers Annotated options, command structure, output style, and Typer best practices."
applyTo: "src/indexmap_cli/cli.py"
---

# CLI Patterns — Typer (indexmap-cli)

## Command structure

- Every command is a function decorated with `@app.command()`.
- Use **`Annotated[T, typer.Option(...)]`** for all option parameters (not the legacy `typer.Option()` as default).
- Mandatory positional arguments use `typer.Argument(...)`.

## Parameters

```python
# ✅ Correct: Annotated pattern
def download(
    base_url: Annotated[str, typer.Option(help="Base URL of OGC Server")] = "http://...",
    output_dir: Annotated[Path, typer.Option(help="Target directory")] = Path("./data/"),
):
```

## Output

- Use `typer.echo()` for normal output.
- Use `typer.style(text, fg=typer.colors.XXX, bold=True)` for coloured output.
- Write errors with `typer.echo(..., err=True)` to send them to stderr.
- Project colour conventions:
  - Start/info: `typer.colors.CYAN`
  - Success: `typer.colors.GREEN`
  - Error: `typer.colors.RED`
  - Warning: `typer.colors.YELLOW`

## New command template

```python
@app.command()
def my_command(
    param: Annotated[str, typer.Option(help="Description of param")] = "default",
    flag: Annotated[bool, typer.Option("--flag/--no-flag", help="Enable feature")] = False,
):
    """
    Short description shown in --help.
    """
    typer.echo(typer.style("Starting...", fg=typer.colors.CYAN))
    try:
        result = business_logic_function(param, flag)
        typer.echo(typer.style("Done!", fg=typer.colors.GREEN, bold=True))
    except ValueError as e:
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED), err=True)
        raise typer.Exit(code=1)
```

## Progress and feedback

- For long-running operations over lists, iterate and print feedback for each item.
- Never use `print()` directly in `cli.py` — always use `typer.echo()`.
