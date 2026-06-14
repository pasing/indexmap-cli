---
description: "Use when writing, running, or reviewing tests for this project. Covers pytest structure, fixture patterns, mocking HTTP calls, CLI testing with CliRunner, and coverage targets."
applyTo: "tests/**/*.py"
---

# Testing Patterns — indexmap-cli

## Structure

```
tests/
  conftest.py          # Shared fixtures
  test_downloader.py   # Tests for src/indexmap_cli/downloader.py
  test_analyzer.py     # Tests for src/indexmap_cli/analyzer.py
  test_merger.py       # Tests for src/indexmap_cli/merger.py
  test_cli.py          # Tests for src/indexmap_cli/cli.py commands
  test_<module>.py     # One file per module
```

## Naming

- Files: `test_<module_name>.py`
- Functions: `test_<expected_behaviour>()` — descriptive, no abbreviations.
- Examples: `test_get_file_paths_raises_if_field_missing()`, `test_download_creates_output_dir()`

## Fixtures in conftest.py

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    return tmp_path / "output"

@pytest.fixture
def sample_geojson() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [14.25, 40.85]},
            "properties": {"url": "http://example.com/file.tif"}
        }]
    }
```

## Mocking HTTP (WFS / requests)

Use `unittest.mock.patch` to mock HTTP calls in business logic modules.

```python
from unittest.mock import patch, MagicMock
import geopandas as gpd

def test_get_file_paths_from_wfs_success():
    mock_gdf = gpd.GeoDataFrame({"url": ["http://example.com/a.tif", "http://example.com/b.tif"]})
    with patch("indexmap_cli.downloader.requests.get") as mock_get, \
         patch("indexmap_cli.downloader.gpd.read_file", return_value=mock_gdf):
        from indexmap_cli.downloader import get_file_paths_from_wfs
        result = get_file_paths_from_wfs("http://server", "ws", "layer", "url")
    assert result == ["http://example.com/a.tif", "http://example.com/b.tif"]
```

## Testing analyze_layer (analyzer.py)

Mock both `requests.get` and `gpd.read_file`. Build a `GeoDataFrame` with the expected columns.

```python
from unittest.mock import patch, MagicMock
import geopandas as gpd
from shapely.geometry import Point
from indexmap_cli.analyzer import analyze_layer, LayerStats

def test_analyze_layer_returns_layer_stats():
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2], "url": ["http://x.com/001.asc", "http://x.com/002.asc"]},
        geometry=[Point(14.0, 41.0), Point(14.1, 41.1)],
        crs="EPSG:4326",
    )
    mock_resp = MagicMock()
    mock_resp.content = b"{}"
    mock_resp.raise_for_status = lambda: None
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp), \
         patch("indexmap_cli.analyzer.gpd.read_file", return_value=gdf):
        stats = analyze_layer("http://server", "ws", "layer")
    assert isinstance(stats, LayerStats)
    assert stats.feature_count == 2
    assert stats.epsg == 4326
    assert "url" in stats.url_properties
```

Key assertions for `LayerStats`:
- `stats.layer_name` — `"{workspace}:{layer}"` string
- `stats.epsg` — integer EPSG code or `None`
- `stats.bbox` — 4-tuple `(minx, miny, maxx, maxy)`
- `stats.feature_count` — total features in the layer
- `stats.properties` — list of `PropertyInfo(name, dtype, contains_urls)`
- `stats.url_properties` — list of column names that contain URLs
- `stats.quadrant_start` / `stats.quadrant_end` — first/last quadrant identifier
- `stats.numbering_type` — `"progressive"`, `"discontinuous"`, or `"n/a"`
- `stats.file_formats` — list of unique extensions found in URL columns (e.g. `[".asc"]`)

## Testing merge (merger.py)

Use `tmp_path` to create real small raster/vector fixtures. Prefer synthetic GeoTIFF files over mocking rasterio internals.

```python
import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from pathlib import Path
from indexmap_cli.merger import merge, MergeResult

def _write_tif(path: Path) -> None:
    transform = from_bounds(0, 0, 10, 10, 10, 10)
    data = np.ones((1, 10, 10), dtype=np.float32)
    with rasterio.open(path, "w", driver="GTiff", height=10, width=10,
                       count=1, dtype="float32", crs=CRS.from_epsg(32633),
                       transform=transform) as dst:
        dst.write(data)

def test_merge_two_tif_files(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    _write_tif(src / "a.tif")
    _write_tif(src / "b.tif")
    out = tmp_path / "merged.tif"
    result = merge(input_dir=src, output_file=out)
    assert isinstance(result, MergeResult)
    assert result.kind == "raster"
    assert len(result.input_files) == 2
    assert out.exists()
```

Key assertions for `MergeResult`:
- `result.kind` — `"raster"` or `"vector"`
- `result.input_files` — list of `Path` objects that were merged
- `result.output_file` — `Path` to the output file (must exist after merge)
- `result.output_format` — `"cog"`, `"gtiff"`, `"gpkg"`, or `"shp"`
- `result.crs_set` — `True` if `--input-crs` was applied

## Testing CLI with CliRunner

```python
from typer.testing import CliRunner
from indexmap_cli.cli import app

runner = CliRunner()

def test_download_command_exits_on_error():
    with patch("indexmap_cli.cli.get_file_paths_from_wfs", side_effect=ValueError("bad field")):
        result = runner.invoke(app, ["download", "--base-url", "http://x", "--workspace", "w", "--layer", "l"])
    assert result.exit_code == 1

def test_merge_command_exits_on_invalid_format(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    result = runner.invoke(app, ["merge", str(src), str(tmp_path / "out.tif"), "--output-format", "bad"])
    assert result.exit_code == 1
    assert "output-format" in result.output.lower()
```

## Integration Tests

Mark with `@pytest.mark.integration`. These require real `.env` vars:
```python
@pytest.mark.integration
def test_integration_analyze_command(...):
    ...
```

Exclude integration tests during normal runs: `uv run pytest tests/ -v -m "not integration"`.

## Commands

```bash
uv run pytest tests/ -v                       # all unit tests, verbose
uv run pytest tests/ -v -m "not integration"  # skip integration tests
uv run pytest tests/ -v --cov=indexmap_cli    # with coverage
uv run pytest tests/test_downloader.py -v     # single file
uv run pytest -k "test_download" -v           # filter by name
```

## Targets

- Coverage ≥ 80% on `src/indexmap_cli/`.
- Every public function in business logic modules must have at least one test.
- CLI commands must have tests for the happy path and the error case.
- All four modules (`downloader`, `analyzer`, `merger`, `cli`) must be covered.
