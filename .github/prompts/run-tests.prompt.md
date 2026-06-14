---
description: "Run the full test suite for indexmap-cli, diagnose failures, and fix them until all tests pass with ≥80% coverage."
agent: "agent"
tools: [read, edit, search, execute, todo]
---

You are running and fixing the test suite for the `indexmap-cli` package. Use the **Tester** agent to diagnose and fix any issues.

## Steps

1. **Run all tests** and capture output:
   ```bash
   uv run pytest tests/ -v --cov=indexmap_cli --cov-report=term-missing
   ```

2. **If tests pass**: Report coverage. If coverage < 80%, identify uncovered code and add tests.

3. **If tests fail**:
   - Read the failing test(s) and the module under test
   - Identify root cause (implementation bug vs. test bug)
   - Fix the issue (prefer fixing the test if it's a test-only issue, fix the implementation if it's a real bug)
   - Re-run tests to confirm fix

4. **If `tests/` directory is missing or empty**:
   - Create `tests/conftest.py` with shared fixtures
   - Create `tests/test_downloader.py` and `tests/test_cli.py`
   - Follow the [testing instructions](../instructions/testing.instructions.md)

5. **Final run** — all tests must pass:
   ```bash
   uv run pytest tests/ -v --cov=indexmap_cli
   ```

## Acceptance Criteria

- [ ] All tests pass (0 failures, 0 errors)
- [ ] Coverage ≥ 80% on `src/indexmap_cli/`
- [ ] No real HTTP calls in tests (all mocked)
