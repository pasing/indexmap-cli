---
description: "Edit or extend an existing CLI command in indexmap-cli: add missing tests, fix logic, update parameters, improve error handling, or wire a new business-logic module. Use when modifying something that already exists — e.g. 'add test for download', 'add --dry-run flag to merge', 'fix error handling in analyze'."
agent: "agent"
argument-hint: "What to change — e.g. 'add test for download', 'add --verbose flag to analyze'"
tools: [read, edit, search, execute, todo]
---

You are editing or extending an existing CLI command in the `indexmap-cli` package.
Route the work to the right specialist agent based on the change type below.

## Request

$input

## Routing

| Change type | Agent to use |
|-------------|--------------|
| Add / fix tests | **Tester** |
| Add option / flag, fix logic, improve output | **Implementer** |
| Review for correctness or style | **Reviewer** |
| Both tests and logic changes needed | **Implementer** first, then **Tester** |

## Step 0 — Identify the target

1. Read [cli.py](../src/indexmap_cli/cli.py) to find the command function.
2. Identify the business-logic module it calls (e.g. `downloader.py` for `download`).
3. Check `tests/` for any existing tests for this command.

## Step 1 — Understand the current state

Read the relevant files before writing anything:

```
src/indexmap_cli/cli.py
src/indexmap_cli/<module>.py      ← business logic module
tests/test_<module>.py            ← existing tests (may not exist yet)
tests/conftest.py                 ← shared fixtures (may not exist yet)
```

Follow the instructions:
- [cli-patterns.instructions.md](../instructions/cli-patterns.instructions.md) for CLI changes
- [testing.instructions.md](../instructions/testing.instructions.md) for test changes
- [python-standards.instructions.md](../instructions/python-standards.instructions.md) for all Python code

## Step 2 — Implement the change

### If adding / fixing tests (→ Tester agent)

- Create `tests/conftest.py` if it does not exist (shared fixtures: `tmp_output_dir`, `sample_geojson`)
- Create or update `tests/test_<module>.py`
- Cover: **happy path**, **edge cases**, **error / exception path**
- Mock all HTTP and WFS calls with `unittest.mock.patch`
- Test CLI commands via `typer.testing.CliRunner`
- Run: `uv run pytest tests/ -v`

### If adding an option or fixing logic (→ Implementer agent)

- Update the `@app.command()` function in `cli.py` using `Annotated[T, typer.Option(...)]`
- Extract non-trivial logic into the business-logic module, not `cli.py`
- Verify: `uv run indexmap <command> --help`

## Step 3 — Verify

```bash
uv run pytest tests/ -v --cov=indexmap_cli   # all tests pass, coverage ≥ 80%
uv run indexmap --help                        # command still visible
```

## Acceptance Criteria

- [ ] All existing tests still pass (no regressions)
- [ ] New tests cover the changed / added behaviour
- [ ] Coverage ≥ 80% on `src/indexmap_cli/`
- [ ] No type-hint errors, PEP 8 respected
