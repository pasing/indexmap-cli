"""
merger.py — Multi-format tile merge for indexmap-cli.

Supported conversion matrix
───────────────────────────
  Input extension(s)       Output format
  ─────────────────────────────────────────────────────────────────────────
  .asc                  →  GeoTIFF (COG by default) / regular GeoTIFF
  .tif / .tiff          →  GeoTIFF (COG by default) / regular GeoTIFF
  .shp                  →  GeoPackage (.gpkg)
  .dxf                  →  Shapefile (.shp) or GeoPackage (.gpkg)

Notes
─────
- DWG is **not** supported by the bundled GDAL build; a clear error is raised.
- ASC / DXF files usually carry no embedded CRS.  Pass ``input_crs`` (EPSG
  integer) to stamp the CRS on the merged output.
- When ``output_format="auto"`` the format is inferred from the output file
  extension: ``.tif`` → COG, ``.gpkg`` → GeoPackage, ``.shp`` → Shapefile.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge as rasterio_merge
from rasterio.shutil import copy as rio_copy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: File extensions recognised as raster tiles.
RASTER_EXTENSIONS: frozenset[str] = frozenset({".asc", ".tif", ".tiff"})

#: File extensions recognised as vector tiles.
VECTOR_EXTENSIONS: frozenset[str] = frozenset({".shp", ".dxf", ".dwg"})

#: Auxiliary / sidecar extensions that accompany main data files and are silently
#: ignored when scanning a directory (e.g. Shapefile companions .dbf, .shx …).
_SIDECAR_EXTENSIONS: frozenset[str] = frozenset({
    # Shapefile
    ".dbf", ".shx", ".prj", ".cpg", ".sbn", ".sbx",
    ".fbn", ".fbx", ".ain", ".aih", ".qix", ".atx",
    # Raster
    ".aux", ".ovr", ".tfw", ".jgw", ".pgw", ".wld",
    ".rrd", ".rsc",
})

#: Valid values for the ``output_format`` parameter.
VALID_OUTPUT_FORMATS: frozenset[str] = frozenset({"auto", "cog", "gtiff", "gpkg", "shp"})

#: Map from ``output_format`` keyword to the file extension it produces.
FORMAT_TO_EXTENSION: dict[str, str] = {
    "cog": ".tif",
    "gtiff": ".tif",
    "gpkg": ".gpkg",
    "shp": ".shp",
}

#: COG GeoTIFF creation profile for rasterio.
_COG_PROFILE: dict[str, object] = {
    "driver": "GTiff",
    "compress": "deflate",
    "tiled": True,
    "blockxsize": 512,
    "blockysize": 512,
}

#: Overview decimation levels applied when building a COG.
_COG_OVERVIEW_LEVELS: list[int] = [2, 4, 8, 16, 32]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class MergeResult:
    """Summary of a completed merge operation."""

    kind: str  # "raster" or "vector"
    input_files: list[Path] = field(default_factory=list)
    output_file: Path = Path()
    output_format: str = ""
    crs_set: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _infer_format_from_extension(path: Path) -> str:
    """
    Infer the ``output_format`` keyword from a file path's extension.

    Returns one of ``"cog"``, ``"gpkg"``, ``"shp"``.

    Raises:
        ValueError: If the extension is not recognised.
    """
    ext = path.suffix.lower()
    mapping: dict[str, str] = {
        ".tif": "cog",
        ".tiff": "cog",
        ".gpkg": "gpkg",
        ".shp": "shp",
    }
    if ext not in mapping:
        raise ValueError(
            f"Cannot infer output format from extension '{ext}'. "
            "Use --output-format to specify one of: cog, gtiff, gpkg, shp."
        )
    return mapping[ext]


def _collect_files(input_dir: Path, glob: str = "*") -> list[Path]:
    """
    Return all regular files in *input_dir* matching *glob* (non-recursive).

    Raises:
        ValueError: If *input_dir* does not exist or no files match.
    """
    if not input_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {input_dir}")
    files = sorted(
        f for f in input_dir.glob(glob)
        if f.is_file() and f.suffix.lower() not in _SIDECAR_EXTENSIONS
    )
    if not files:
        raise ValueError(f"No files found in '{input_dir}' matching pattern '{glob}'.")
    return files


def _classify_files(files: list[Path]) -> str:
    """
    Determine whether *files* are all raster, all vector, or mixed.

    Returns:
        ``"raster"`` or ``"vector"``.

    Raises:
        ValueError: If files are of mixed kind or contain unsupported extensions.
    """
    kinds: set[str] = set()
    unknown: list[str] = []

    for f in files:
        ext = f.suffix.lower()
        if ext in RASTER_EXTENSIONS:
            kinds.add("raster")
        elif ext in VECTOR_EXTENSIONS:
            kinds.add("vector")
        else:
            unknown.append(ext)

    if unknown:
        raise ValueError(
            f"Unsupported file extension(s): {', '.join(sorted(set(unknown)))}. "
            f"Supported raster: {sorted(RASTER_EXTENSIONS)}; "
            f"vector: {sorted(VECTOR_EXTENSIONS)}."
        )
    if len(kinds) > 1:
        raise ValueError(
            "Cannot mix raster and vector files in a single merge. "
            "Separate them into different directories."
        )
    return kinds.pop()


def _ensure_parent(path: Path) -> None:
    """Create the parent directory of *path* if it does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Raster merge
# ---------------------------------------------------------------------------


def merge_rasters(
    files: list[Path],
    output_file: Path,
    output_format: str = "cog",
    input_crs: int | None = None,
) -> None:
    """
    Merge one or more raster tiles into a single GeoTIFF.

    Args:
        files: Input raster paths (.asc, .tif, .tiff).
        output_file: Destination path for the merged raster.
        output_format: ``"cog"`` (default) for Cloud Optimised GeoTIFF, or
            ``"gtiff"`` for a regular flat GeoTIFF.
        input_crs: EPSG code to assign when source files carry no CRS
            (e.g. ESRI ASCII Grid files).

    Raises:
        ValueError: If *output_format* is not ``"cog"`` or ``"gtiff"``.
        RuntimeError: If rasterio cannot open or process the input files.
    """
    if output_format not in {"cog", "gtiff"}:
        raise ValueError(
            f"Invalid raster output_format '{output_format}'. Choose 'cog' or 'gtiff'."
        )

    _ensure_parent(output_file)

    datasets: list[rasterio.DatasetReader] = []
    try:
        datasets = [rasterio.open(f) for f in files]
        merged_data, merged_transform = rasterio_merge(datasets)
    finally:
        for ds in datasets:
            ds.close()

    # Build output profile from the first source
    with rasterio.open(files[0]) as src:
        profile = src.profile.copy()

    crs = profile.get("crs")
    if crs is None and input_crs is not None:
        crs = rasterio.crs.CRS.from_epsg(input_crs)

    profile.update(
        driver="GTiff",
        height=merged_data.shape[1],
        width=merged_data.shape[2],
        transform=merged_transform,
        crs=crs,
    )
    profile.pop("compress", None)  # will be re-set below

    if output_format == "gtiff":
        with rasterio.open(output_file, "w", **profile) as dst:
            dst.write(merged_data)
        return

    # --- COG path -----------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "merged_tmp.tif"

        with rasterio.open(tmp_path, "w", **profile) as tmp_ds:
            tmp_ds.write(merged_data)

        # Build overviews (requires "r+" mode after initial write)
        with rasterio.open(tmp_path, "r+") as tmp_ds:
            tmp_ds.build_overviews(_COG_OVERVIEW_LEVELS, Resampling.average)
            tmp_ds.update_tags(ns="rio_overview", resampling="average")

        # Write COG — copy_src_overviews places them before the imagery data
        rio_copy(
            str(tmp_path),
            str(output_file),
            copy_src_overviews=True,
            **_COG_PROFILE,
        )


# ---------------------------------------------------------------------------
# Vector merge
# ---------------------------------------------------------------------------

#: Map from ``output_format`` keyword to the driver string used by geopandas.
_VECTOR_DRIVER_MAP: dict[str, str] = {
    "gpkg": "GPKG",
    "shp": "ESRI Shapefile",
}


def merge_vectors(
    files: list[Path],
    output_file: Path,
    output_format: str = "gpkg",
    input_crs: int | None = None,
) -> None:
    """
    Merge one or more vector tiles into a single file.

    Supported input formats: .shp, .dxf (DWG is not supported by the bundled GDAL).

    Args:
        files: Input vector paths.
        output_file: Destination path for the merged vector dataset.
        output_format: ``"gpkg"`` (GeoPackage, default) or ``"shp"`` (Shapefile).
        input_crs: EPSG code to assign when source files carry no CRS.

    Raises:
        ValueError: If *output_format* is unsupported, or DWG files are present,
            or the source CRS is unknown and *input_crs* is not provided.
        RuntimeError: If geopandas cannot read one of the input files.
    """
    if output_format not in _VECTOR_DRIVER_MAP:
        raise ValueError(
            f"Invalid vector output_format '{output_format}'. Choose 'gpkg' or 'shp'."
        )

    # Reject DWG explicitly (driver not available)
    dwg_files = [f for f in files if f.suffix.lower() == ".dwg"]
    if dwg_files:
        raise ValueError(
            "DWG format is not supported by the bundled GDAL. "
            "Convert to DXF first, or provide the files in a supported format."
        )

    _ensure_parent(output_file)

    gdfs: list[gpd.GeoDataFrame] = []
    for f in files:
        gdf = gpd.read_file(f)
        if gdf.crs is None and input_crs is not None:
            gdf = gdf.set_crs(epsg=input_crs)
        gdfs.append(gdf)

    merged_gdf = gpd.pd.concat(gdfs, ignore_index=True)  # type: ignore[attr-defined]

    # Ensure it is still a GeoDataFrame (pd.concat can downgrade to DataFrame)
    if not isinstance(merged_gdf, gpd.GeoDataFrame):
        merged_gdf = gpd.GeoDataFrame(merged_gdf)

    # Align CRS: reproject all to the CRS of the first layer if needed
    target_crs = gdfs[0].crs
    if target_crs is not None and merged_gdf.crs != target_crs:
        merged_gdf = merged_gdf.to_crs(target_crs)

    driver = _VECTOR_DRIVER_MAP[output_format]
    merged_gdf.to_file(str(output_file), driver=driver)


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


def merge(
    input_dir: Path,
    output_file: Path,
    output_format: str = "auto",
    glob: str = "*",
    input_crs: int | None = None,
) -> MergeResult:
    """
    Detect the file kind in *input_dir* and run the appropriate merge.

    Args:
        input_dir: Directory containing the tiles to merge.
        output_file: Destination path for the merged output.
        output_format: One of ``"auto"``, ``"cog"``, ``"gtiff"``, ``"gpkg"``,
            ``"shp"``.  ``"auto"`` infers the format from *output_file*'s
            extension.
        glob: Glob pattern used to filter files in *input_dir* (default ``"*"``).
        input_crs: EPSG integer to assign when input files carry no CRS.

    Returns:
        A :class:`MergeResult` describing the completed operation.

    Raises:
        ValueError: For unsupported formats, mixed-kind inputs, or missing files.
    """
    if output_format not in VALID_OUTPUT_FORMATS:
        raise ValueError(
            f"Invalid output_format '{output_format}'. "
            f"Choose one of: {sorted(VALID_OUTPUT_FORMATS)}."
        )

    files = _collect_files(input_dir, glob)
    kind = _classify_files(files)

    effective_format = output_format
    if effective_format == "auto":
        effective_format = _infer_format_from_extension(output_file)

    if kind == "raster":
        if effective_format not in {"cog", "gtiff"}:
            raise ValueError(
                f"Output format '{effective_format}' is not valid for raster inputs. "
                "Use 'cog', 'gtiff', or a .tif extension."
            )
        merge_rasters(files, output_file, effective_format, input_crs)
    else:
        if effective_format not in {"gpkg", "shp"}:
            raise ValueError(
                f"Output format '{effective_format}' is not valid for vector inputs. "
                "Use 'gpkg', 'shp', or a .gpkg / .shp extension."
            )
        merge_vectors(files, output_file, effective_format, input_crs)

    return MergeResult(
        kind=kind,
        input_files=files,
        output_file=output_file,
        output_format=effective_format,
        crs_set=(input_crs is not None),
    )
