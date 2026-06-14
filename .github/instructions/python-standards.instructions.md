---
description: "Use when writing or reviewing Python source code in this project. Covers PEP 8, type hints, module structure, error handling, and project-specific conventions."
applyTo: "src/**/*.py"
---

# Python Code Standards — indexmap-cli

## General

- Python ≥ 3.11. Use modern syntax: `X | Y` union types, `match` statements where appropriate.
- Type hints on every function and method: parameters, return values, complex variables.
- Max line length: **100 characters**.
- Follow PEP 8 throughout. Use `snake_case` for functions/variables, `PascalCase` for classes.

## Modules and packages

- Every new module goes in `src/indexmap_cli/`.
- Business logic belongs in dedicated modules (e.g. `downloader.py`, `merger.py`).
- CLI commands belong in `cli.py` and import from the business logic.
- Expose only the necessary APIs; keep internal implementation private.

## Error handling

- In the CLI layer: catch specific exceptions, use `typer.echo(..., err=True)` + `raise typer.Exit(code=1)`.
- In business logic modules: raise typed exceptions (`ValueError`, `RuntimeError`, custom), never print directly.
- Never use bare `except:` — always catch a specific exception type.

## Imports

- Order: stdlib → third-party → local (`from indexmap_cli.xxx import yyy`).
- Use absolute imports. Avoid `from module import *`.

## Examples

```python
# ✅ Correct: typed function, specific exception
def get_file_paths_from_wfs(base_url: str, workspace: str, layer: str, url_field: str) -> list[str]:
    gdf = gpd.read_file(service_url)
    if url_field not in gdf.columns:
        raise ValueError(f"Attribute field '{url_field}' not found in the index map.")
    return gdf[url_field].dropna().tolist()

# ✅ Correct: CLI error handling
except Exception as e:
    typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED), err=True)
    raise typer.Exit(code=1)
```
