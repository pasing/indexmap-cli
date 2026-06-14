# indexmap-cli — Agent Instructions

## Project Overview

`indexmap-cli` is a Python CLI tool for analyzing, downloading, and merging data from geographic index maps (quadrants). It exposes Typer commands that communicate with OGC/WFS servers (GeoServer and others) and manipulate geospatial raster/vector files.

## Agent Workflow

- Use the `Orchestrator` agent for complex multi-step tasks that span design, implementation, tests, and review.
- Use the `Architect` agent when planning new features, designing module structure, or evaluating technical trade-offs before implementation.
- Use the `Implementer` agent for CLI features, business logic changes, and command wiring.
- Use the `Tester` agent for new tests, test fixes, and coverage work.
- Use the `Reviewer` agent for correctness and style review before merging.
- Use the `Release` agent for version bumps, builds, and publish prep.
- Prefer the prompt files under `.github/prompts/` when the task is a new command, an existing command edit, or a test-only change.

## Tech Stack

| Layer | Libraries |
|-------|-----------|
| CLI | `typer` |
| Vector GIS | `geopandas`, `shapely` |
| Raster GIS | `rasterio` |
| HTTP | `requests` |
| Build/env | `uv`, `uv_build` |
| Test | `pytest`, `pytest-cov` |

## Source Structure

```
src/indexmap_cli/
  __init__.py        # __version__
  cli.py             # Typer commands (download, analyze, merge, …)
  analyzer.py        # WFS layer analysis logic (LayerStats, analyze_layer)
  downloader.py      # WFS logic + file download
  merger.py          # Multi-format tile merge (raster COG, vector GPKG/SHP)
  py.typed           # PEP 561 marker
```

## Code Conventions

- Python ≥ 3.11, type hints everywhere.
- Every new module goes in `src/indexmap_cli/`.
- CLI commands in `cli.py`, business logic in separate modules.
- Use `Annotated[T, typer.Option(...)]` for CLI parameters.
- Handle exceptions in the CLI layer with `typer.echo` + `raise typer.Exit(code=1)`.
- Never print directly in business logic modules — use return values or exceptions.
- Follow `PEP 8`; max line length 100.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|--------|
| `INDEXMAP_BASE_URL` | Base URL of the OGC/GeoServer | — |
| `INDEXMAP_WORKSPACE` | GeoServer workspace name | — |
| `INDEXMAP_LAYER` | Layer name in the workspace | — |
| `INDEXMAP_URL_FIELD` | Attribute field containing download URLs | `url` |
| `INDEXMAP_OUTPUT_DIR` | Local directory for downloaded files | `./data/` |
| `INDEXMAP_SKIP_SSL_VERIFY` | Skip TLS certificate verification (`true`/`false`) | `true` |
| `INDEXMAP_INPUT_DIR` | Input directory for the merge command | — |
| `INDEXMAP_OUTPUT_FILE` | Output file path for the merge command | — |
| `INDEXMAP_OUTPUT_FORMAT` | Merge output format (`auto`/`cog`/`gtiff`/`gpkg`/`shp`) | `auto` |
| `INDEXMAP_GLOB` | Glob pattern to filter input files in merge | `*` |
| `INDEXMAP_INPUT_CRS` | EPSG code to assign CRS to files without one | `None` |

## CLI Commands

### download

`indexmap download [OPTIONS]`

Downloads files referenced in a WFS index-map layer into a local directory.

| Option | Env var | Default |
|--------|---------|---------|
| `--base-url` | `INDEXMAP_BASE_URL` | — (required) |
| `--workspace` | `INDEXMAP_WORKSPACE` | — (required) |
| `--layer` | `INDEXMAP_LAYER` | — (required) |
| `--url-field` | `INDEXMAP_URL_FIELD` | `url` |
| `--output-dir` | `INDEXMAP_OUTPUT_DIR` | `./data/` |
| `--skip-ssl-verify / --no-skip-ssl-verify` | `INDEXMAP_SKIP_SSL_VERIFY` | `true` |

Business logic: `downloader.get_file_paths_from_wfs()` + `downloader.download_file()`.

---

### analyze

`indexmap analyze [OPTIONS]`

Fetches a WFS layer and prints statistics: EPSG code, bounding box, property types with URL-field auto-detection, quadrant count/numbering (progressive or discontinuous), and attachment file formats.

| Option | Env var | Default |
|--------|---------|---------|
| `--base-url` | `INDEXMAP_BASE_URL` | — (required) |
| `--workspace` | `INDEXMAP_WORKSPACE` | — (required) |
| `--layer` | `INDEXMAP_LAYER` | — (required) |
| `--skip-ssl-verify / --no-skip-ssl-verify` | `INDEXMAP_SKIP_SSL_VERIFY` | `true` |

Business logic: `analyzer.analyze_layer()` → returns `analyzer.LayerStats`.

Output sections: **Layer metadata**, **Properties** (with `[URL]` tags), **Quadrants**, **File formats**.

---

### merge

`indexmap merge <input_dir> <output_file> [OPTIONS]`

Merges downloaded tiles into a single output file.

| Option | Env var | Default |
|--------|---------|---------|
| `input_dir` (positional) | `INDEXMAP_INPUT_DIR` | — (required) |
| `output_file` (positional) | `INDEXMAP_OUTPUT_FILE` | — (required) |
| `--output-format` | `INDEXMAP_OUTPUT_FORMAT` | `auto` |
| `--glob` | `INDEXMAP_GLOB` | `*` |
| `--input-crs` | `INDEXMAP_INPUT_CRS` | `None` |

Supported conversion matrix:

| Input extension(s)     | Output format               |
|------------------------|-----------------------------|
| `.asc`                 | GeoTIFF (COG by default)    |
| `.tif` / `.tiff`       | GeoTIFF (COG by default)    |
| `.shp`                 | GeoPackage (`.gpkg`)        |
| `.dxf`                 | Shapefile (`.shp`) or GPKG  |

- `--output-format auto` infers the format from the output file extension.
- `--input-crs <epsg>` assigns a CRS to files without embedded CRS (e.g. `.asc`).
- DWG is **not** supported by the bundled GDAL build.

Business logic: `merger.merge()` → returns `merger.MergeResult`.

---

All variables can be placed in a `.env` file (see `.env.example`).

## Test Conventions

- `tests/` directory at the project root.
- `tests/conftest.py` with shared fixtures.
- Test names: `test_<module>_<behaviour>.py`.
- Mock HTTP calls with `unittest.mock`.
- Coverage target ≥ 80%.
- Run with: `uv run pytest tests/ -v --cov=indexmap_cli`.
- Exclude integration tests: `uv run pytest tests/ -v -m "not integration"`.
- Integration tests are marked with `@pytest.mark.integration` and require `.env` vars to be set.

## Release Conventions

- Version: `uv version --bump "X.Y.Z"`.
- Build: `uv build`.
- Publish: `uv publish`.

## Useful Development Commands

```bash
uv run indexmap --help          # quick CLI smoke test
uv run pytest tests/ -v         # run tests
uv run pytest --cov=indexmap_cli # with coverage
uv build                        # build wheel + sdist
```
