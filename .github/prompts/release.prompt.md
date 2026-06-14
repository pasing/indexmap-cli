---
description: "Prepare and publish a new release of indexmap-cli: bump version, run tests, build wheel, and optionally publish to PyPI."
agent: "agent"
argument-hint: "patch | minor | major (default: patch)"
tools: [read, edit, execute, todo]
---

You are preparing a new release of the `indexmap-cli` package. Use the **Release** agent to manage this process safely.

## Release Type

Requested bump: $input (default: patch if not specified)

| Type | When to use |
|------|-------------|
| `patch` | Bug fixes, docs, minor improvements |
| `minor` | New backward-compatible commands or features |
| `major` | Breaking changes to CLI interface or APIs |

## Steps

1. **Read current version**:
   - [\_\_init\_\_.py](../src/indexmap_cli/__init__.py) → `__version__`
   - [pyproject.toml](../pyproject.toml) → `[project] version`
   - Confirm both match.

2. **Run tests** — abort if any fail:
   ```bash
   uv run pytest tests/ -v
   ```

3. **Calculate new version** from bump type and current version.

4. **Update version** in BOTH files:
   - `src/indexmap_cli/__init__.py`: `__version__ = "X.Y.Z"`
   - `pyproject.toml`: `version = "X.Y.Z"`

5. **Build package**:
   ```bash
   uv build
   ```
   Verify `dist/indexmap_cli-X.Y.Z-py3-none-any.whl` and `dist/indexmap_cli-X.Y.Z.tar.gz` exist.

6. **Ask user to confirm** before publishing:
   > Ready to publish version X.Y.Z to PyPI. Confirm with `uv publish`?

7. **Publish** (only after confirmation):
   ```bash
   uv publish
   ```

## Acceptance Criteria

- [ ] Both version files updated and in sync
- [ ] All tests pass before build
- [ ] `dist/` contains wheel and sdist for the new version
- [ ] Published to PyPI (if confirmed)
