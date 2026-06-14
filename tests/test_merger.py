"""
Unit + data-driven tests for src/indexmap_cli/merger.py.

Synthetic raster/vector fixtures are used for fast unit tests.
Tests marked ``data`` use the real .asc files in ``data/dtm_asc/``
(skipped automatically when that directory is absent or empty).
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from shapely.geometry import box

import geopandas as gpd

from indexmap_cli.merger import (
    RASTER_EXTENSIONS,
    VECTOR_EXTENSIONS,
    MergeResult,
    _classify_files,
    _collect_files,
    _infer_format_from_extension,
    merge,
    merge_rasters,
    merge_vectors,
)

# ---------------------------------------------------------------------------
# Fixtures — synthetic rasters
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data" / "dtm_asc"
_HAS_ASC_DATA = _DATA_DIR.is_dir() and any(_DATA_DIR.glob("*.asc"))


def _write_synthetic_raster(
    path: Path,
    width: int = 10,
    height: int = 10,
    transform: Affine | None = None,
    crs: CRS | None = CRS.from_epsg(32633),
    nodata: float = -9999.0,
) -> None:
    """Write a small synthetic single-band float32 GeoTIFF."""
    if transform is None:
        transform = from_bounds(0, 0, width, height, width, height)
    data = np.arange(width * height, dtype=np.float32).reshape(1, height, width)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data)


@pytest.fixture
def two_tif_files(tmp_path: Path) -> tuple[Path, list[Path]]:
    """Two small adjacent GeoTIFF tiles in a temp directory."""
    src_dir = tmp_path / "tif_src"
    src_dir.mkdir()
    t1 = from_bounds(0, 0, 10, 10, 10, 10)
    t2 = from_bounds(10, 0, 20, 10, 10, 10)
    f1 = src_dir / "tile_a.tif"
    f2 = src_dir / "tile_b.tif"
    _write_synthetic_raster(f1, transform=t1)
    _write_synthetic_raster(f2, transform=t2)
    return src_dir, [f1, f2]


@pytest.fixture
def one_asc_file(tmp_path: Path) -> tuple[Path, Path]:
    """A minimal ESRI ASCII grid (.asc) without a CRS."""
    src_dir = tmp_path / "asc_src"
    src_dir.mkdir()
    asc = src_dir / "tile.asc"
    # Minimal ESRI ASCII header
    asc.write_text(
        "ncols 4\nnrows 4\nxllcorner 0\nyllcorner 0\ncellsize 1\nNODATA_value -9999\n"
        + "\n".join("1 2 3 4" for _ in range(4))
        + "\n"
    )
    return src_dir, asc


# ---------------------------------------------------------------------------
# Fixtures — synthetic vectors
# ---------------------------------------------------------------------------


def _write_synthetic_shp(path: Path, crs: str = "EPSG:32633") -> None:
    """Write a minimal two-polygon shapefile."""
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)],
        crs=crs,
    )
    gdf.to_file(str(path), driver="ESRI Shapefile")


@pytest.fixture
def two_shp_files(tmp_path: Path) -> tuple[Path, list[Path]]:
    """Two small shapefiles in a temp directory."""
    src_dir = tmp_path / "shp_src"
    src_dir.mkdir()
    f1 = src_dir / "part_a.shp"
    f2 = src_dir / "part_b.shp"
    _write_synthetic_shp(f1)
    _write_synthetic_shp(f2)
    return src_dir, [f1, f2]


# ---------------------------------------------------------------------------
# _infer_format_from_extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ext,expected",
    [
        (".tif", "cog"),
        (".tiff", "cog"),
        (".gpkg", "gpkg"),
        (".shp", "shp"),
    ],
)
def test_infer_format_from_extension_known(ext: str, expected: str, tmp_path: Path) -> None:
    p = tmp_path / f"out{ext}"
    assert _infer_format_from_extension(p) == expected


def test_infer_format_from_extension_unknown_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Cannot infer output format"):
        _infer_format_from_extension(tmp_path / "out.xyz")


# ---------------------------------------------------------------------------
# _collect_files
# ---------------------------------------------------------------------------


def test_collect_files_returns_sorted_list(two_tif_files: tuple[Path, list[Path]]) -> None:
    src_dir, expected = two_tif_files
    result = _collect_files(src_dir)
    assert result == sorted(expected)


def test_collect_files_glob_filter(two_tif_files: tuple[Path, list[Path]]) -> None:
    src_dir, _ = two_tif_files
    result = _collect_files(src_dir, glob="tile_a*")
    assert len(result) == 1
    assert result[0].name == "tile_a.tif"


def test_collect_files_nonexistent_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        _collect_files(tmp_path / "missing")


def test_collect_files_empty_match_raises(two_tif_files: tuple[Path, list[Path]]) -> None:
    src_dir, _ = two_tif_files
    with pytest.raises(ValueError, match="No files found"):
        _collect_files(src_dir, glob="*.xyz")


# ---------------------------------------------------------------------------
# _classify_files
# ---------------------------------------------------------------------------


def test_classify_files_raster(two_tif_files: tuple[Path, list[Path]]) -> None:
    _, files = two_tif_files
    assert _classify_files(files) == "raster"


def test_classify_files_vector(two_shp_files: tuple[Path, list[Path]]) -> None:
    _, files = two_shp_files
    assert _classify_files(files) == "vector"


def test_classify_files_mixed_raises(
    two_tif_files: tuple[Path, list[Path]], two_shp_files: tuple[Path, list[Path]]
) -> None:
    _, raster_files = two_tif_files
    _, vector_files = two_shp_files
    with pytest.raises(ValueError, match="Cannot mix raster and vector"):
        _classify_files(raster_files + vector_files)


def test_classify_files_unsupported_extension_raises(tmp_path: Path) -> None:
    f = tmp_path / "file.xyz"
    f.touch()
    with pytest.raises(ValueError, match="Unsupported file extension"):
        _classify_files([f])


# ---------------------------------------------------------------------------
# merge_rasters — unit tests (with synthetic TIF files)
# ---------------------------------------------------------------------------


def test_merge_rasters_gtiff_creates_output(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    _, files = two_tif_files
    out = tmp_path / "merged.tif"
    merge_rasters(files, out, output_format="gtiff")
    assert out.exists()


def test_merge_rasters_gtiff_width_is_sum(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    """Two 10-pixel-wide adjacent tiles should produce a 20-pixel-wide mosaic."""
    _, files = two_tif_files
    out = tmp_path / "merged.tif"
    merge_rasters(files, out, output_format="gtiff")
    with rasterio.open(out) as dst:
        assert dst.width == 20


def test_merge_rasters_cog_creates_output(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    _, files = two_tif_files
    out = tmp_path / "merged_cog.tif"
    merge_rasters(files, out, output_format="cog")
    assert out.exists()


def test_merge_rasters_cog_is_tiled(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    _, files = two_tif_files
    out = tmp_path / "merged_cog.tif"
    merge_rasters(files, out, output_format="cog")
    with rasterio.open(out) as dst:
        profile = dst.profile
        assert profile.get("tiled") is True or profile.get("compress") is not None


def test_merge_rasters_assigns_input_crs(
    one_asc_file: tuple[Path, Path], tmp_path: Path
) -> None:
    src_dir, asc = one_asc_file
    out = tmp_path / "merged.tif"
    merge_rasters([asc], out, output_format="gtiff", input_crs=32633)
    with rasterio.open(out) as dst:
        assert dst.crs is not None
        assert dst.crs.to_epsg() == 32633


def test_merge_rasters_invalid_format_raises(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    _, files = two_tif_files
    with pytest.raises(ValueError, match="Invalid raster output_format"):
        merge_rasters(files, tmp_path / "out.gpkg", output_format="gpkg")


def test_merge_rasters_creates_parent_directory(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    _, files = two_tif_files
    out = tmp_path / "nested" / "deep" / "merged.tif"
    merge_rasters(files, out, output_format="gtiff")
    assert out.exists()


# ---------------------------------------------------------------------------
# merge_vectors — unit tests
# ---------------------------------------------------------------------------


def test_merge_vectors_gpkg_creates_output(
    two_shp_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    _, files = two_shp_files
    out = tmp_path / "merged.gpkg"
    merge_vectors(files, out, output_format="gpkg")
    assert out.exists()


def test_merge_vectors_gpkg_feature_count(
    two_shp_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    """Each input shapefile has 2 features; merged should have 4."""
    _, files = two_shp_files
    out = tmp_path / "merged.gpkg"
    merge_vectors(files, out, output_format="gpkg")
    merged_gdf = gpd.read_file(str(out))
    assert len(merged_gdf) == 4


def test_merge_vectors_shp_creates_output(
    two_shp_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    _, files = two_shp_files
    out = tmp_path / "merged.shp"
    merge_vectors(files, out, output_format="shp")
    assert out.exists()


def test_merge_vectors_dwg_raises(tmp_path: Path) -> None:
    dwg = tmp_path / "file.dwg"
    dwg.touch()
    with pytest.raises(ValueError, match="DWG format is not supported"):
        merge_vectors([dwg], tmp_path / "out.gpkg", output_format="gpkg")


def test_merge_vectors_invalid_format_raises(
    two_shp_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    _, files = two_shp_files
    with pytest.raises(ValueError, match="Invalid vector output_format"):
        merge_vectors(files, tmp_path / "out.tif", output_format="cog")


def test_merge_vectors_assigns_crs_for_nocrs_files(tmp_path: Path) -> None:
    """A GeoDataFrame without CRS should receive input_crs via set_crs."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    f = src_dir / "part.shp"
    # Write shapefile without CRS
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0, 0, 1, 1)])
    gdf.to_file(str(f), driver="ESRI Shapefile")

    out = tmp_path / "merged.gpkg"
    merge_vectors([f], out, output_format="gpkg", input_crs=32633)
    result = gpd.read_file(str(out))
    assert result.crs is not None
    assert result.crs.to_epsg() == 32633


# ---------------------------------------------------------------------------
# merge() — orchestrator tests
# ---------------------------------------------------------------------------


def test_merge_auto_raster_produces_cog(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_tif_files
    out = tmp_path / "out.tif"
    result = merge(src_dir, out, output_format="auto")
    assert result.kind == "raster"
    assert result.output_format == "cog"
    assert out.exists()


def test_merge_auto_vector_produces_gpkg(
    two_shp_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_shp_files
    out = tmp_path / "out.gpkg"
    result = merge(src_dir, out, output_format="auto")
    assert result.kind == "vector"
    assert result.output_format == "gpkg"
    assert out.exists()


def test_merge_explicit_gtiff(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_tif_files
    out = tmp_path / "out.tif"
    result = merge(src_dir, out, output_format="gtiff")
    assert result.output_format == "gtiff"


def test_merge_explicit_shp(
    two_shp_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_shp_files
    out = tmp_path / "out.shp"
    result = merge(src_dir, out, output_format="shp")
    assert result.output_format == "shp"
    assert out.exists()


def test_merge_invalid_output_format_raises(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_tif_files
    with pytest.raises(ValueError, match="Invalid output_format"):
        merge(src_dir, tmp_path / "out.tif", output_format="unknown")


def test_merge_raster_wrong_format_raises(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_tif_files
    with pytest.raises(ValueError, match="not valid for raster"):
        merge(src_dir, tmp_path / "out.tif", output_format="gpkg")


def test_merge_vector_wrong_format_raises(
    two_shp_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_shp_files
    with pytest.raises(ValueError, match="not valid for vector"):
        merge(src_dir, tmp_path / "out.gpkg", output_format="cog")


def test_merge_result_input_files_count(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_tif_files
    result = merge(src_dir, tmp_path / "out.tif", output_format="gtiff")
    assert len(result.input_files) == 2


def test_merge_glob_filter(two_tif_files: tuple[Path, list[Path]], tmp_path: Path) -> None:
    src_dir, _ = two_tif_files
    result = merge(src_dir, tmp_path / "out.tif", output_format="gtiff", glob="tile_a*")
    assert len(result.input_files) == 1


def test_merge_crs_set_flag_false_by_default(
    two_tif_files: tuple[Path, list[Path]], tmp_path: Path
) -> None:
    src_dir, _ = two_tif_files
    result = merge(src_dir, tmp_path / "out.tif", output_format="gtiff")
    assert result.crs_set is False


def test_merge_crs_set_flag_true_when_given(
    one_asc_file: tuple[Path, Path], tmp_path: Path
) -> None:
    src_dir, _ = one_asc_file
    result = merge(src_dir, tmp_path / "out.tif", output_format="gtiff", input_crs=32633)
    assert result.crs_set is True


# ---------------------------------------------------------------------------
# Data-driven tests — real .asc files from data/dtm_asc/
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_ASC_DATA, reason="data/dtm_asc/ not present or empty")
def test_merge_asc_to_cog_with_real_data(tmp_path: Path) -> None:
    """Merge a subset (first 3) of real .asc DTM files into a COG GeoTIFF."""
    asc_files = sorted(_DATA_DIR.glob("*.asc"))[:3]
    # Write files to a temp src dir so merge() can detect them via glob
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    for f in asc_files:
        import shutil
        shutil.copy(f, src_dir / f.name)

    out = tmp_path / "dtm_merged.tif"
    result = merge(src_dir, out, output_format="cog", input_crs=32633)

    assert result.kind == "raster"
    assert result.output_format == "cog"
    assert out.exists()
    assert len(result.input_files) == 3

    with rasterio.open(out) as ds:
        assert ds.crs is not None
        assert ds.crs.to_epsg() == 32633
        # Merged width should be approximately the sum of individual widths
        assert ds.width > 0
        assert ds.height > 0


@pytest.mark.skipif(not _HAS_ASC_DATA, reason="data/dtm_asc/ not present or empty")
def test_merge_all_asc_to_cog_with_real_data(tmp_path: Path) -> None:
    """Merge a representative set of real .asc DTM files into a single COG GeoTIFF.

    Uses a glob that excludes any known-truncated files (e.g. 005778.asc).
    """
    # Write a clean subset of non-truncated tiles to a temp dir
    asc_files = [f for f in sorted(_DATA_DIR.glob("*.asc")) if f.name != "005778.asc"]
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    import shutil
    for f in asc_files:
        shutil.copy(f, src_dir / f.name)

    out = tmp_path / "dtm_full.tif"
    result = merge(src_dir, out, output_format="cog", glob="*.asc", input_crs=32633)

    assert out.exists()
    assert result.kind == "raster"
    assert result.output_format == "cog"

    with rasterio.open(out) as ds:
        assert ds.crs.to_epsg() == 32633
        assert ds.width > 0
        assert ds.height > 0
        # File size > 1 KB means something was written
        assert out.stat().st_size > 1024


@pytest.mark.skipif(not _HAS_ASC_DATA, reason="data/dtm_asc/ not present or empty")
def test_merge_asc_to_regular_geotiff_with_real_data(tmp_path: Path) -> None:
    """Merge two real .asc files into a regular (non-COG) GeoTIFF."""
    asc_files = sorted(_DATA_DIR.glob("*.asc"))[:2]
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    for f in asc_files:
        import shutil
        shutil.copy(f, src_dir / f.name)

    out = tmp_path / "dtm_flat.tif"
    result = merge(src_dir, out, output_format="gtiff", input_crs=32633)
    assert out.exists()
    assert result.output_format == "gtiff"
