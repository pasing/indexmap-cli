"""
cli.py — Typer command-line interface for indexmap-cli.

Exposes three commands:

- ``download``: fetch a WFS index-map layer and download all referenced files.
- ``analyze``: inspect a WFS layer and print statistics (EPSG, bbox, properties,
  quadrant numbering, file formats).
- ``merge``: merge a directory of raster or vector tiles into a single output file.

All options can be supplied via environment variables or a local ``.env`` file.
"""
import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from indexmap_cli.analyzer import analyze_layer
from indexmap_cli.downloader import get_file_paths_from_wfs, download_file
from indexmap_cli.merger import VALID_OUTPUT_FORMATS, merge as merge_tiles

load_dotenv()

app = typer.Typer(help="CLI tool to manage and download data from index maps.")


def _env_bool(key: str, default: bool) -> bool:
    """Parse a boolean value from an environment variable."""
    val = os.environ.get(key, "").lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


@app.command()
def download(
    base_url: Annotated[
        str, typer.Option(help="Base URL of OGC Server (or set INDEXMAP_BASE_URL env var)")
    ] = os.environ.get("INDEXMAP_BASE_URL", ""),
    workspace: Annotated[
        str, typer.Option(help="Workspace name (or set INDEXMAP_WORKSPACE env var)")
    ] = os.environ.get("INDEXMAP_WORKSPACE", ""),
    layer: Annotated[
        str, typer.Option(help="Layer name (or set INDEXMAP_LAYER env var)")
    ] = os.environ.get("INDEXMAP_LAYER", ""),
    url_field: Annotated[
        str, typer.Option(help="URL field name attribute (or set INDEXMAP_URL_FIELD env var)")
    ] = os.environ.get("INDEXMAP_URL_FIELD", "url"),
    output_dir: Annotated[
        Path, typer.Option(help="Target directory for downloaded data (or set INDEXMAP_OUTPUT_DIR env var)")
    ] = Path(os.environ.get("INDEXMAP_OUTPUT_DIR", "./data/")),
    skip_ssl_verify: Annotated[
        bool,
        typer.Option(
            "--skip-ssl-verify/--no-skip-ssl-verify",
            help="Skip TLS certificate verification (or set INDEXMAP_SKIP_SSL_VERIFY env var)",
        ),
    ] = _env_bool("INDEXMAP_SKIP_SSL_VERIFY", True),
):
    """
    Download index map assets based on WFS layer attributes.
    """
    if not base_url:
        typer.echo(
            typer.style("Error: --base-url is required (or set INDEXMAP_BASE_URL in .env)", fg=typer.colors.RED),
            err=True,
        )
        raise typer.Exit(code=1)
    if not workspace:
        typer.echo(
            typer.style("Error: --workspace is required (or set INDEXMAP_WORKSPACE in .env)", fg=typer.colors.RED),
            err=True,
        )
        raise typer.Exit(code=1)
    if not layer:
        typer.echo(
            typer.style("Error: --layer is required (or set INDEXMAP_LAYER in .env)", fg=typer.colors.RED),
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(style_text("🚀 Starting Index Map Downloader...", fg=typer.colors.CYAN))
    if skip_ssl_verify:
        typer.echo(typer.style("⚠️  TLS certificate verification is disabled.", fg=typer.colors.YELLOW))

    try:
        urls = get_file_paths_from_wfs(base_url, workspace, layer, url_field, skip_ssl_verify)
        typer.echo(f"Found {len(urls)} files to download.\n")

        downloaded_count = 0
        failed_count = 0
        for url in urls:
            try:
                downloaded_file = download_file(url, output_dir, skip_ssl_verify)
            except Exception as e:
                failed_count += 1
                typer.echo(
                    typer.style(
                        f"  Failed: {Path(url).name} ({e})",
                        fg=typer.colors.YELLOW,
                    )
                )
                continue

            downloaded_count += 1
            typer.echo(typer.style(f"  Downloaded: {downloaded_file.name}", fg=typer.colors.GREEN))

        if downloaded_count == 0:
            raise RuntimeError("No files were downloaded successfully.")

        if failed_count > 0:
            typer.echo(
                typer.style(
                    f"\n⚠️  Completed with {failed_count} failed download(s).",
                    fg=typer.colors.YELLOW,
                )
            )

        typer.echo(typer.style("\n🎉 Download completed!", fg=typer.colors.GREEN, bold=True))
    except Exception as e:
        typer.echo(typer.style(f"💥 Error: {e}", fg=typer.colors.RED), err=True)
        raise typer.Exit(code=1)


@app.command()
def analyze(
    base_url: Annotated[
        str, typer.Option(help="Base URL of OGC Server (or set INDEXMAP_BASE_URL env var)")
    ] = os.environ.get("INDEXMAP_BASE_URL", ""),
    workspace: Annotated[
        str, typer.Option(help="Workspace name (or set INDEXMAP_WORKSPACE env var)")
    ] = os.environ.get("INDEXMAP_WORKSPACE", ""),
    layer: Annotated[
        str, typer.Option(help="Layer name (or set INDEXMAP_LAYER env var)")
    ] = os.environ.get("INDEXMAP_LAYER", ""),
    skip_ssl_verify: Annotated[
        bool,
        typer.Option(
            "--skip-ssl-verify/--no-skip-ssl-verify",
            help="Skip TLS certificate verification (or set INDEXMAP_SKIP_SSL_VERIFY env var)",
        ),
    ] = _env_bool("INDEXMAP_SKIP_SSL_VERIFY", True),
):
    """
    Analyse a WFS index-map layer and print statistics to the console.

    Reports layer metadata (EPSG, bounding box), property types with URL-field
    auto-detection, quadrant count / numbering, and attachment file formats.
    """
    if not base_url:
        typer.echo(
            typer.style("Error: --base-url is required (or set INDEXMAP_BASE_URL in .env)", fg=typer.colors.RED),
            err=True,
        )
        raise typer.Exit(code=1)
    if not workspace:
        typer.echo(
            typer.style("Error: --workspace is required (or set INDEXMAP_WORKSPACE in .env)", fg=typer.colors.RED),
            err=True,
        )
        raise typer.Exit(code=1)
    if not layer:
        typer.echo(
            typer.style("Error: --layer is required (or set INDEXMAP_LAYER in .env)", fg=typer.colors.RED),
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(typer.style("🔍 Analysing Index Map Layer...", fg=typer.colors.CYAN))
    if skip_ssl_verify:
        typer.echo(typer.style("⚠️  TLS certificate verification is disabled.", fg=typer.colors.YELLOW))

    try:
        stats = analyze_layer(base_url, workspace, layer, skip_ssl_verify)
    except Exception as e:
        typer.echo(typer.style(f"💥 Error: {e}", fg=typer.colors.RED), err=True)
        raise typer.Exit(code=1)

    # --- Layer metadata -------------------------------------------------------
    typer.echo("")
    typer.echo(typer.style("── Layer metadata ─────────────────────────────", fg=typer.colors.CYAN))
    typer.echo(f"  Layer   : {stats.layer_name}")
    typer.echo(f"  EPSG    : {stats.epsg if stats.epsg is not None else 'unknown'}")
    minx, miny, maxx, maxy = stats.bbox
    typer.echo(f"  BBox    : minx={minx:.6f}  miny={miny:.6f}  maxx={maxx:.6f}  maxy={maxy:.6f}")

    # --- Properties -----------------------------------------------------------
    typer.echo("")
    typer.echo(typer.style("── Properties ─────────────────────────────────", fg=typer.colors.CYAN))
    for prop in stats.properties:
        url_tag = typer.style(" [URL]", fg=typer.colors.YELLOW, bold=True) if prop.contains_urls else ""
        typer.echo(f"  {prop.name:<24}  {prop.dtype:<12}{url_tag}")

    if stats.url_properties:
        count = len(stats.url_properties)
        label = "single" if count == 1 else "multi"
        names = ", ".join(stats.url_properties)
        typer.echo(typer.style(f"\n  URL field(s) detected ({label}): {names}", fg=typer.colors.GREEN))
    else:
        typer.echo(typer.style("\n  No URL fields detected.", fg=typer.colors.YELLOW))

    # --- Quadrants ------------------------------------------------------------
    typer.echo("")
    typer.echo(typer.style("── Quadrants ──────────────────────────────────", fg=typer.colors.CYAN))
    typer.echo(f"  Count       : {stats.feature_count}")
    typer.echo(f"  Start       : {stats.quadrant_start or 'n/a'}")
    typer.echo(f"  End         : {stats.quadrant_end or 'n/a'}")
    typer.echo(f"  Numbering   : {stats.numbering_type}")

    # --- File formats ---------------------------------------------------------
    typer.echo("")
    typer.echo(typer.style("── File formats ───────────────────────────────", fg=typer.colors.CYAN))
    typer.echo(f"  {', '.join(stats.file_formats) if stats.file_formats else 'none detected'}")

    typer.echo("")
    typer.echo(typer.style("✅ Analysis complete.", fg=typer.colors.GREEN, bold=True))


@app.command()
def merge(
    input_dir: Annotated[
        Path, typer.Argument(help="Directory containing downloaded tiles to merge (or set INDEXMAP_INPUT_DIR env var).")
    ] = Path(os.environ.get("INDEXMAP_INPUT_DIR", "")),
    output_file: Annotated[
        Path, typer.Argument(help="Destination path for the merged output file (or set INDEXMAP_OUTPUT_FILE env var).")
    ] = Path(os.environ.get("INDEXMAP_OUTPUT_FILE", "")),
    output_format: Annotated[
        str,
        typer.Option(
            help=(
                "Output format: auto (infer from extension) | cog (Cloud Optimised GeoTIFF) "
                "| gtiff (regular GeoTIFF) | gpkg (GeoPackage) | shp (Shapefile). "
                "Defaults to 'auto'."
            )
        ),
    ] = os.environ.get("INDEXMAP_OUTPUT_FORMAT", "auto"),
    glob: Annotated[
        str,
        typer.Option(help="Glob pattern to filter input files (default: '*').")
    ] = os.environ.get("INDEXMAP_GLOB", "*"),
    input_crs: Annotated[
        int | None,
        typer.Option(
            help=(
                "EPSG code to assign to the merged output when input files "
                "carry no embedded CRS (e.g. ESRI ASCII Grid .asc files)."
            )
        ),
    ] = int(os.environ.get("INDEXMAP_INPUT_CRS", 4326)) if os.environ.get("INDEXMAP_INPUT_CRS") else None
):
    """
    Merge downloaded tiles into a single output file.

    Auto-detects whether the source files are raster or vector and selects
    the appropriate merge strategy:

    \b
      .asc  / .tif / .tiff  →  GeoTIFF  (COG by default)
      .shp                  →  GeoPackage (.gpkg) by default
      .dxf                  →  Shapefile (.shp) or GeoPackage (.gpkg)

    The output format is inferred from the output file extension unless
    --output-format is given explicitly.
    """
    valid = sorted(VALID_OUTPUT_FORMATS)
    if output_format not in VALID_OUTPUT_FORMATS:
        typer.echo(
            typer.style(
                f"Error: --output-format must be one of: {valid}",
                fg=typer.colors.RED,
            ),
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(typer.style("🔀 Starting Merge...", fg=typer.colors.CYAN))
    typer.echo(f"  Input dir   : {input_dir}")
    typer.echo(f"  Output file : {output_file}")
    typer.echo(f"  Format      : {output_format}")
    if input_crs:
        typer.echo(f"  Input CRS   : EPSG:{input_crs}")
    if glob != "*":
        typer.echo(f"  File filter : {glob}")

    try:
        result = merge_tiles(
            input_dir=input_dir,
            output_file=output_file,
            output_format=output_format,
            glob=glob,
            input_crs=input_crs,
        )
    except Exception as e:
        typer.echo(typer.style(f"💥 Error: {e}", fg=typer.colors.RED), err=True)
        raise typer.Exit(code=1)

    typer.echo("")
    typer.echo(typer.style("── Merge summary ─────────────────────────────", fg=typer.colors.CYAN))
    typer.echo(f"  Kind        : {result.kind}")
    typer.echo(f"  Files read  : {len(result.input_files)}")
    typer.echo(f"  Format      : {result.output_format}")
    typer.echo(f"  Output      : {result.output_file}")
    if result.crs_set:
        typer.echo(f"  CRS stamped : EPSG:{input_crs}")
    typer.echo("")
    typer.echo(typer.style("✅ Merge complete.", fg=typer.colors.GREEN, bold=True))


def style_text(text: str, fg: str | None = None) -> str:
    """Return *text* styled with the given foreground colour via :func:`typer.style`."""
    return typer.style(text, fg=fg)


if __name__ == "__main__":
    app()