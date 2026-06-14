# indexmap-cli

`indexmap-cli` is a Python CLI tool for analysing, downloading, and merging data from geographic index maps (quadrants). It communicates with OGC/WFS servers (GeoServer and compatible) and supports raster and vector tile merging.

## Requirements

- Python 3.11 or newer
- `uv`
- Optional: access to a GeoServer / WFS endpoint for `download` and `analyze` commands

## Installation

```bash
uv pip install indexmap-cli
```

After installation the `indexmap` entry point is available on your PATH.

### Development install

```bash
git clone https://github.com/pasing/indexmap-cli.git
cd indexmap-cli
uv pip install -e .
```

## Configuration

All options can be supplied as CLI flags **or** via environment variables (or a `.env` file in the working directory).

| Variable | Description | Default |
|---|---|---|
| `INDEXMAP_BASE_URL` | Base URL of the OGC/GeoServer | — |
| `INDEXMAP_WORKSPACE` | GeoServer workspace name | — |
| `INDEXMAP_LAYER` | Layer name in the workspace | — |
| `INDEXMAP_URL_FIELD` | Attribute field containing download URLs | `url` |
| `INDEXMAP_OUTPUT_DIR` | Local directory for downloaded files | `./data/` |
| `INDEXMAP_SKIP_SSL_VERIFY` | Skip TLS certificate verification | `true` |
| `INDEXMAP_INPUT_DIR` | Input directory for the `merge` command | — |
| `INDEXMAP_OUTPUT_FILE` | Output file path for the `merge` command | — |
| `INDEXMAP_OUTPUT_FORMAT` | Merge output format (`auto`/`cog`/`gtiff`/`gpkg`/`shp`) | `auto` |
| `INDEXMAP_GLOB` | Glob pattern to filter input files in `merge` | `*` |
| `INDEXMAP_INPUT_CRS` | EPSG code to assign to files that have no embedded CRS | — |

`INDEXMAP_SKIP_SSL_VERIFY` accepts `true`, `false`, `1`, `0`, `yes`, and `no`.

Example `.env` file:

```bash
INDEXMAP_BASE_URL=https://example.org/geoserver
INDEXMAP_WORKSPACE=my_workspace
INDEXMAP_LAYER=my_layer
INDEXMAP_URL_FIELD=url
INDEXMAP_OUTPUT_DIR=./data/
INDEXMAP_SKIP_SSL_VERIFY=true
```

## Commands

### `indexmap analyze`

Inspect a WFS index-map layer and print statistics to the console.

```bash
indexmap analyze \
  --base-url  https://example.org/geoserver \
  --workspace my_workspace \
  --layer     my_layer
```

**Output sections:**

| Section | What it shows |
|---|---|
| **Layer metadata** | Layer name, EPSG code, bounding box |
| **Properties** | Attribute columns with data types; URL-bearing columns are tagged `[URL]` |
| **Quadrants** | Total feature count, first/last quadrant identifier, numbering type (`progressive` / `discontinuous`) |
| **File formats** | Unique file extensions found in URL attribute columns (e.g. `.asc`, `.tif`) |

**Options:**

| Option | Env var | Default |
|---|---|---|
| `--base-url` | `INDEXMAP_BASE_URL` | required |
| `--workspace` | `INDEXMAP_WORKSPACE` | required |
| `--layer` | `INDEXMAP_LAYER` | required |
| `--skip-ssl-verify / --no-skip-ssl-verify` | `INDEXMAP_SKIP_SSL_VERIFY` | `true` |

---

### `indexmap download`

Download all files referenced in a WFS index-map layer into a local directory.

```bash
indexmap download \
  --base-url  https://example.org/geoserver \
  --workspace my_workspace \
  --layer     my_layer \
  --url-field url \
  --output-dir ./data/
```

**Options:**

| Option | Env var | Default |
|---|---|---|
| `--base-url` | `INDEXMAP_BASE_URL` | required |
| `--workspace` | `INDEXMAP_WORKSPACE` | required |
| `--layer` | `INDEXMAP_LAYER` | required |
| `--url-field` | `INDEXMAP_URL_FIELD` | `url` |
| `--output-dir` | `INDEXMAP_OUTPUT_DIR` | `./data/` |
| `--skip-ssl-verify / --no-skip-ssl-verify` | `INDEXMAP_SKIP_SSL_VERIFY` | `true` |

**Behaviour:**

- Creates `--output-dir` if it does not exist.
- Skips already-failed files (warns) and counts successes vs failures.
- Exits with code `1` if no file is downloaded successfully.

---

### `indexmap merge`

Merge a directory of raster or vector tile files into a single output file.

```bash
indexmap merge <input_dir> <output_file> [OPTIONS]
```

```bash
# Merge ESRI ASCII grids into a Cloud Optimised GeoTIFF
indexmap merge data/dtm_asc merged.tif --output-format cog --input-crs 32633

# Merge Shapefiles into a GeoPackage
indexmap merge data/parcels merged.gpkg

# Merge only files matching a glob pattern
indexmap merge data/tiles merged.tif --glob "*.tif"
```

**Supported conversion matrix:**

| Input extension(s) | Default output format |
|---|---|
| `.asc` | COG GeoTIFF (`.tif`) |
| `.tif` / `.tiff` | COG GeoTIFF (`.tif`) |
| `.shp` | GeoPackage (`.gpkg`) |
| `.dxf` | Shapefile (`.shp`) or GeoPackage (`.gpkg`) |

> **Note:** DWG is **not** supported by the bundled GDAL. Convert to DXF first.

**Options:**

| Option | Env var | Default | Description |
|---|---|---|---|
| `input_dir` (positional) | `INDEXMAP_INPUT_DIR` | required | Directory containing tiles to merge |
| `output_file` (positional) | `INDEXMAP_OUTPUT_FILE` | required | Destination file |
| `--output-format` | `INDEXMAP_OUTPUT_FORMAT` | `auto` | `auto` \| `cog` \| `gtiff` \| `gpkg` \| `shp` |
| `--glob` | `INDEXMAP_GLOB` | `*` | Glob pattern to filter input files |
| `--input-crs` | `INDEXMAP_INPUT_CRS` | — | EPSG code to assign when files carry no CRS |

`--output-format auto` infers the format from the output file extension (`.tif` → COG, `.gpkg` → GeoPackage, `.shp` → Shapefile).

**Merge summary output:**

```
── Merge summary ─────────────────────────────
  Kind        : raster
  Files read  : 3
  Format      : cog
  Output      : merged.tif
  CRS stamped : EPSG:32633
```

---

## Examples

### Inspect a layer before downloading

```bash
indexmap analyze \
  --base-url  https://example.org/geoserver \
  --workspace my_workspace \
  --layer     my_layer
```

### Download using environment variables

```bash
export INDEXMAP_BASE_URL=https://example.org/geoserver
export INDEXMAP_WORKSPACE=my_workspace
export INDEXMAP_LAYER=my_layer
indexmap download
```

### Merge ASCII grids into a COG

```bash
indexmap merge data/dtm_asc merged.tif --output-format cog --input-crs 32633
```

### Merge only `.asc` files, assign CRS

```bash
indexmap merge data/dtm_asc merged.tif --glob "*.asc" --input-crs 25832
```

### Get help on any command

```bash
indexmap --help
indexmap download --help
indexmap analyze --help
indexmap merge --help
```

---

## Testing

Run the full test suite:

```bash
uv run pytest tests/ -v --cov=indexmap_cli
```

Skip integration tests (requires a live server):

```bash
uv run pytest tests/ -v -m "not integration"
```

Integration tests are enabled when `INDEXMAP_BASE_URL`, `INDEXMAP_WORKSPACE`, and `INDEXMAP_LAYER` are set in the environment or `.env` file.

---

## Project Layout

```text
src/indexmap_cli/
  __init__.py     # Package version
  cli.py          # Typer commands (download, analyze, merge)
  analyzer.py     # WFS layer analysis — LayerStats, analyze_layer()
  downloader.py   # WFS fetch + file download
  merger.py       # Multi-format tile merge (raster COG, vector GPKG/SHP)
  py.typed        # PEP 561 marker
tests/
  conftest.py
  test_analyzer.py
  test_cli.py
  test_downloader.py
  test_merger.py
```

---

## License

See [LICENSE.md](LICENSE.md).
