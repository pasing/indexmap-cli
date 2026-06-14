# Contributing to indexmap-cli

Thanks for helping improve `indexmap-cli`.

## Before You Start

- Read the project documentation and existing issues before opening a new one.
- Keep changes focused and consistent with the current code style.
- Prefer small, reviewable pull requests.

## Development Setup

1. Install the project in editable mode:

   `uv pip install -e .`

2. Run the test suite:

   `uv run pytest tests/ -v`

3. Run a narrower test target when iterating on a specific area:

   `uv run pytest tests/test_cli.py -v`

## Code Guidelines

- Use Python 3.11+ and type hints.
- Keep CLI behavior in `src/indexmap_cli/cli.py` and business logic in the module files under `src/indexmap_cli/`.
- Use `typer` for command-line interfaces.
- Handle user-facing errors in the CLI layer with clear messages and non-zero exit codes.
- Avoid direct printing from business logic modules.

## Tests

- Add or update tests for behavior changes.
- Use `pytest` conventions already established in `tests/`.
- Mock external HTTP or filesystem dependencies where practical.

## Pull Requests

- Include a concise description of the change and why it is needed.
- Mention any new environment variables, dependencies, or user-facing behavior.
- Confirm tests were run and note any limitations.

## Questions

If something is unclear, open an issue or ask in the pull request before starting larger changes.
