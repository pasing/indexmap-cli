"""
Unit tests for src/indexmap_cli/analyzer.py.

All HTTP calls are mocked so that the test suite can run without a live server.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from indexmap_cli.analyzer import (
    LayerStats,
    PropertyInfo,
    _detect_file_formats,
    _detect_quadrant_numbering,
    _detect_url_properties,
    analyze_layer,
)
import geopandas as gpd
from shapely.geometry import Point


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wfs_mock(features: list[dict]) -> MagicMock:
    """Build a mock requests.Response that returns a minimal WFS GeoJSON."""
    geojson = {"type": "FeatureCollection", "features": features}
    mock_resp = MagicMock()
    mock_resp.content = json.dumps(geojson).encode()
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _point_feature(properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [14.25, 40.85]},
        "properties": properties,
    }


# ---------------------------------------------------------------------------
# _detect_url_properties
# ---------------------------------------------------------------------------


def test_detect_url_properties_single_url_column() -> None:
    gdf = gpd.GeoDataFrame(
        {"url": ["http://example.com/a.asc", "http://example.com/b.asc"], "id": [1, 2]},
        geometry=[Point(14, 40), Point(15, 41)],
    )
    result = _detect_url_properties(gdf)
    assert result == ["url"]


def test_detect_url_properties_multiple_url_columns() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "url_dem": ["http://example.com/a.asc"],
            "url_ortho": ["https://example.com/a.tif"],
            "id": [1],
        },
        geometry=[Point(14, 40)],
    )
    result = _detect_url_properties(gdf)
    assert set(result) == {"url_dem", "url_ortho"}


def test_detect_url_properties_no_url_column() -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["tile_a", "tile_b"], "code": [1, 2]},
        geometry=[Point(14, 40), Point(15, 41)],
    )
    result = _detect_url_properties(gdf)
    assert result == []


def test_detect_url_properties_ignores_geometry_column() -> None:
    gdf = gpd.GeoDataFrame(
        {"url": ["http://example.com/a.asc"]},
        geometry=[Point(14, 40)],
    )
    result = _detect_url_properties(gdf)
    assert "geometry" not in result


# ---------------------------------------------------------------------------
# _detect_file_formats
# ---------------------------------------------------------------------------


def test_detect_file_formats_single_format() -> None:
    gdf = gpd.GeoDataFrame(
        {"url": ["http://example.com/005770.asc", "http://example.com/005771.asc"]},
        geometry=[Point(14, 40), Point(15, 41)],
    )
    result = _detect_file_formats(gdf, ["url"])
    assert result == [".asc"]


def test_detect_file_formats_multiple_formats() -> None:
    gdf = gpd.GeoDataFrame(
        {"url": ["http://example.com/a.tif", "http://example.com/b.asc"]},
        geometry=[Point(14, 40), Point(15, 41)],
    )
    result = _detect_file_formats(gdf, ["url"])
    assert set(result) == {".tif", ".asc"}


def test_detect_file_formats_no_extension() -> None:
    gdf = gpd.GeoDataFrame(
        {"url": ["http://example.com/download?id=1"]},
        geometry=[Point(14, 40)],
    )
    result = _detect_file_formats(gdf, ["url"])
    assert result == []


def test_detect_file_formats_empty_url_cols() -> None:
    gdf = gpd.GeoDataFrame(
        {"url": ["http://example.com/a.asc"]},
        geometry=[Point(14, 40)],
    )
    result = _detect_file_formats(gdf, [])
    assert result == []


# ---------------------------------------------------------------------------
# _detect_quadrant_numbering
# ---------------------------------------------------------------------------


def test_detect_quadrant_numbering_progressive_from_int_column() -> None:
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2, 3, 4], "url": ["http://x.com/a.asc"] * 4},
        geometry=[Point(14, 40)] * 4,
    )
    start, end, ntype = _detect_quadrant_numbering(gdf, ["url"])
    assert start == "1"
    assert end == "4"
    assert ntype == "progressive"


def test_detect_quadrant_numbering_discontinuous_from_int_column() -> None:
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2, 5, 6], "url": ["http://x.com/a.asc"] * 4},
        geometry=[Point(14, 40)] * 4,
    )
    start, end, ntype = _detect_quadrant_numbering(gdf, ["url"])
    assert start == "1"
    assert end == "6"
    assert ntype == "discontinuous"


def test_detect_quadrant_numbering_from_url_stem_progressive() -> None:
    gdf = gpd.GeoDataFrame(
        {"url": ["http://x.com/005770.asc", "http://x.com/005771.asc", "http://x.com/005772.asc"]},
        geometry=[Point(14, 40)] * 3,
    )
    start, end, ntype = _detect_quadrant_numbering(gdf, ["url"])
    assert start == "5770"
    assert end == "5772"
    assert ntype == "progressive"


def test_detect_quadrant_numbering_from_url_stem_discontinuous() -> None:
    gdf = gpd.GeoDataFrame(
        {"url": ["http://x.com/005770.asc", "http://x.com/005772.asc"]},
        geometry=[Point(14, 40)] * 2,
    )
    _, _, ntype = _detect_quadrant_numbering(gdf, ["url"])
    assert ntype == "discontinuous"


def test_detect_quadrant_numbering_no_numeric_data() -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["tile_a", "tile_b"]},
        geometry=[Point(14, 40)] * 2,
    )
    start, end, ntype = _detect_quadrant_numbering(gdf, [])
    assert start is None
    assert end is None
    assert ntype == "n/a"


# ---------------------------------------------------------------------------
# analyze_layer — unit tests (mocked HTTP)
# ---------------------------------------------------------------------------


def test_analyze_layer_returns_correct_feature_count(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [_point_feature({"url": f"http://example.com/{i:06d}.asc"}) for i in range(5)]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    assert stats.feature_count == 5


def test_analyze_layer_detects_url_property(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [_point_feature({"id": 1, "url": "http://example.com/005770.asc"})]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    assert "url" in stats.url_properties
    assert "id" not in stats.url_properties


def test_analyze_layer_detects_multi_url_properties(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [
        _point_feature({"url_dem": "http://example.com/a.asc", "url_ortho": "https://example.com/a.tif"})
    ]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    assert set(stats.url_properties) == {"url_dem", "url_ortho"}


def test_analyze_layer_detects_file_format(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [_point_feature({"url": "http://example.com/005770.asc"})]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    assert ".asc" in stats.file_formats


def test_analyze_layer_builds_correct_layer_name(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [_point_feature({"url": "http://example.com/a.tif"})]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    assert stats.layer_name == f"{server_workspace}:{server_layer}"


def test_analyze_layer_raises_on_http_error(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    import requests as req_lib

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError("503 Service Unavailable")
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        with pytest.raises(req_lib.HTTPError):
            analyze_layer(server_base_url, server_workspace, server_layer)


def test_analyze_layer_progressive_numbering(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [
        _point_feature({"id": i, "url": f"http://example.com/{i:06d}.asc"}) for i in range(1, 4)
    ]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    assert stats.quadrant_start == "1"
    assert stats.quadrant_end == "3"
    assert stats.numbering_type == "progressive"


def test_analyze_layer_discontinuous_numbering(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [
        _point_feature({"id": i, "url": f"http://example.com/{i:06d}.asc"}) for i in [1, 2, 5]
    ]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    assert stats.numbering_type == "discontinuous"


def test_analyze_layer_property_info_dtype(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [_point_feature({"id": 1, "url": "http://example.com/a.asc"})]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    prop_names = [p.name for p in stats.properties]
    assert "id" in prop_names
    assert "url" in prop_names
    url_prop = next(p for p in stats.properties if p.name == "url")
    assert url_prop.contains_urls is True
    assert url_prop.sample_value == "http://example.com/a.asc"


def test_analyze_layer_no_url_properties(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    features = [_point_feature({"id": 1, "name": "tile_a"})]
    mock_resp = _make_wfs_mock(features)
    with patch("indexmap_cli.analyzer.requests.get", return_value=mock_resp):
        stats = analyze_layer(server_base_url, server_workspace, server_layer)
    assert stats.url_properties == []
    assert stats.file_formats == []


# ---------------------------------------------------------------------------
# Integration test (real server) — skipped unless configured
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_analyze_layer_integration(
    server_base_url: str, server_workspace: str, server_layer: str, skip_ssl: bool
) -> None:
    """End-to-end test against a live server. Requires env vars to be set."""
    stats = analyze_layer(server_base_url, server_workspace, server_layer, skip_ssl)
    assert stats.feature_count > 0
    assert stats.epsg is not None
    assert stats.bbox[2] > stats.bbox[0]  # maxx > minx
    assert stats.bbox[3] > stats.bbox[1]  # maxy > miny
