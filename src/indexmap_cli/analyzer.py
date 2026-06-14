"""
analyzer.py — WFS layer analysis for indexmap-cli.

Fetches a WFS layer and computes statistics about its metadata,
properties, quadrant numbering, and attachment file formats.
"""
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import requests
import urllib3

_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


@dataclass
class PropertyInfo:
    """Metadata about a single layer property (attribute column)."""

    name: str
    dtype: str
    contains_urls: bool
    sample_value: str | None = None


@dataclass
class LayerStats:
    """Aggregated statistics for a single WFS index-map layer."""

    layer_name: str
    epsg: int | None
    bbox: tuple[float, float, float, float]  # (minx, miny, maxx, maxy)
    feature_count: int
    properties: list[PropertyInfo] = field(default_factory=list)
    url_properties: list[str] = field(default_factory=list)
    quadrant_start: str | None = None
    quadrant_end: str | None = None
    numbering_type: str = "n/a"  # "progressive" | "discontinuous" | "n/a"
    file_formats: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_url_properties(gdf: gpd.GeoDataFrame) -> list[str]:
    """Return the names of columns whose values look like URLs (http/https)."""
    url_cols: list[str] = []
    for col in gdf.columns:
        if col == "geometry":
            continue
        sample = gdf[col].dropna().astype(str)
        if sample.empty:
            continue
        if sample.apply(lambda v: bool(_URL_PATTERN.match(v))).any():
            url_cols.append(col)
    return url_cols


def _detect_file_formats(gdf: gpd.GeoDataFrame, url_cols: list[str]) -> list[str]:
    """Extract unique file extensions (lower-cased) from URL attribute columns."""
    formats: set[str] = set()
    for col in url_cols:
        for val in gdf[col].dropna().astype(str):
            ext = Path(val.split("?")[0]).suffix.lower()
            if ext:
                formats.add(ext)
    return sorted(formats)


def _detect_quadrant_numbering(
    gdf: gpd.GeoDataFrame,
    url_cols: list[str],
) -> tuple[str | None, str | None, str]:
    """
    Determine quadrant start, end, and whether numbering is progressive or discontinuous.

    Strategy:
    1. Look for a non-URL integer column to use as the quadrant identifier.
    2. If none is found, fall back to extracting the numeric stem from URL filenames.

    Returns:
        (start, end, numbering_type) where numbering_type is one of
        "progressive", "discontinuous", or "n/a".
    """
    id_series: list[int] | None = None

    # 1. Integer (non-URL) columns
    for col in gdf.columns:
        if col == "geometry" or col in url_cols:
            continue
        try:
            nums = gdf[col].dropna().astype(int).tolist()
            if nums:
                id_series = sorted(nums)
                break
        except (ValueError, TypeError):
            continue

    # 2. Numeric stem from URL filenames
    if id_series is None and url_cols:
        col = url_cols[0]
        nums = []
        for val in gdf[col].dropna().astype(str):
            stem = Path(val.split("?")[0]).stem
            if stem.isdigit():
                nums.append(int(stem))
        if nums:
            id_series = sorted(nums)

    if not id_series:
        return None, None, "n/a"

    start = str(id_series[0])
    end = str(id_series[-1])
    expected = list(range(id_series[0], id_series[-1] + 1))
    numbering_type = "progressive" if id_series == expected else "discontinuous"
    return start, end, numbering_type


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_layer(
    base_url: str,
    workspace: str,
    layer: str,
    skip_ssl_verify: bool = True,
) -> LayerStats:
    """
    Fetch a WFS layer and return its statistics.

    Args:
        base_url: Base URL of the OGC/GeoServer instance (e.g. ``https://host/geoserver``).
        workspace: GeoServer workspace name.
        layer: Layer name within the workspace.
        skip_ssl_verify: When ``True``, TLS certificate verification is skipped.

    Returns:
        A :class:`LayerStats` instance populated with metadata, property info,
        quadrant numbering, and detected file formats.

    Raises:
        requests.RequestException: If the WFS HTTP request fails.
        ValueError: If the WFS response cannot be parsed.
    """
    clean_base_url = base_url.rstrip("/")
    full_layer_name = f"{workspace}:{layer}"

    query_params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": full_layer_name,
        "outputFormat": "application/json",
    }
    service_url = f"{clean_base_url}/{workspace}/ows?{urlencode(query_params)}"

    if skip_ssl_verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    response = requests.get(service_url, verify=not skip_ssl_verify)
    response.raise_for_status()

    gdf = gpd.read_file(io.BytesIO(response.content))

    # --- Bounding box ---------------------------------------------------------
    bounds = gdf.total_bounds  # (minx, miny, maxx, maxy)
    bbox = (float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))

    # --- CRS / EPSG -----------------------------------------------------------
    epsg: int | None = None
    if gdf.crs is not None:
        epsg = gdf.crs.to_epsg()

    # --- Properties -----------------------------------------------------------
    url_cols = _detect_url_properties(gdf)
    properties: list[PropertyInfo] = []
    for col in gdf.columns:
        if col == "geometry":
            continue
        contains_urls = col in url_cols
        sample = gdf[col].dropna()
        sample_val = str(sample.iloc[0]) if not sample.empty and contains_urls else None
        properties.append(
            PropertyInfo(
                name=col,
                dtype=str(gdf[col].dtype),
                contains_urls=contains_urls,
                sample_value=sample_val,
            )
        )

    # --- File formats ---------------------------------------------------------
    file_formats = _detect_file_formats(gdf, url_cols)

    # --- Quadrant numbering ---------------------------------------------------
    q_start, q_end, numbering_type = _detect_quadrant_numbering(gdf, url_cols)

    return LayerStats(
        layer_name=full_layer_name,
        epsg=epsg,
        bbox=bbox,
        feature_count=len(gdf),
        properties=properties,
        url_properties=url_cols,
        quadrant_start=q_start,
        quadrant_end=q_end,
        numbering_type=numbering_type,
        file_formats=file_formats,
    )
