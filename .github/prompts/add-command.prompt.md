---
description: "Add a new Typer CLI command to indexmap-cli, including business logic module and tests."
agent: "agent"
argument-hint: "Describe the new command (name, purpose, parameters)"
tools: [read, edit, search, execute, todo]
---

You are implementing a new CLI command for the `indexmap-cli` package. Use the **Implementer** agent for the implementation and then the **Tester** agent to write tests.

## Task

Add the following new command: $input

## Steps

1. **Read existing code** to understand current patterns:
   - [cli.py](../src/indexmap_cli/cli.py)
   - [downloader.py](../src/indexmap_cli/downloader.py)
   - [analyzer.py](../src/indexmap_cli/analyzer.py)

2. **Implement** using the Implementer agent:
   - Create a new module in `src/indexmap_cli/` if business logic is non-trivial
   - Add `@app.command()` to `cli.py` with `Annotated[T, typer.Option(...)]` parameters
   - Follow all patterns in [cli-patterns instructions](../instructions/cli-patterns.instructions.md)

3. **Verify CLI** works:
   ```bash
   uv run indexmap --help
   uv run indexmap <new-command> --help
   ```

4. **Write tests** using the Tester agent:
   - Create `tests/test_<module>.py`
   - Cover happy path + error cases
   - Run: `uv run pytest tests/ -v`

5. **Review** using the Reviewer agent — fix any issues found.

## Acceptance Criteria

- [ ] Command appears in `uv run indexmap --help`
- [ ] `--help` shows all options with descriptions
- [ ] All tests pass
- [ ] No type hint errors
