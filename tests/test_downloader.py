import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

import pytest
import requests

from indexmap_cli.downloader import download_file, get_file_paths_from_wfs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wfs_response(*urls: str) -> MagicMock:
    """Build a mock requests.Response that returns a minimal WFS GeoJSON."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [14.25, 40.85]},
                "properties": {"url": url},
            }
            for url in urls
        ],
    }
    mock_resp = MagicMock()
    mock_resp.content = json.dumps(geojson).encode()
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _make_wfs_response_no_url_field() -> MagicMock:
    """WFS response whose features have no 'url' attribute."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [14.25, 40.85]},
                "properties": {"other_field": "value"},
            }
        ],
    }
    mock_resp = MagicMock()
    mock_resp.content = json.dumps(geojson).encode()
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# get_file_paths_from_wfs — unit tests
# ---------------------------------------------------------------------------


def test_get_file_paths_from_wfs_returns_urls(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    mock_resp = _make_wfs_response("http://example.com/a.tif", "http://example.com/b.tif")
    with patch("indexmap_cli.downloader.requests.get", return_value=mock_resp):
        result = get_file_paths_from_wfs(server_base_url, server_workspace, server_layer, "url")

    assert result == ["http://example.com/a.tif", "http://example.com/b.tif"]


def test_get_file_paths_from_wfs_builds_correct_wfs_url(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    mock_resp = _make_wfs_response("http://example.com/x.tif")
    with patch("indexmap_cli.downloader.requests.get", return_value=mock_resp) as mock_get:
        get_file_paths_from_wfs(server_base_url, server_workspace, server_layer, "url")

    called_url: str = mock_get.call_args[0][0]
    decoded_url = unquote(called_url)
    assert server_base_url.rstrip("/") in decoded_url
    assert server_workspace in decoded_url
    assert f"{server_workspace}:{server_layer}" in decoded_url
    assert "service=WFS" in called_url
    assert "request=GetFeature" in called_url
    assert "outputFormat=application" in called_url


def test_get_file_paths_from_wfs_raises_if_field_missing(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    mock_resp = _make_wfs_response_no_url_field()
    with patch("indexmap_cli.downloader.requests.get", return_value=mock_resp):
        with pytest.raises(ValueError, match="not found in the index map"):
            get_file_paths_from_wfs(server_base_url, server_workspace, server_layer, "url")


def test_get_file_paths_from_wfs_drops_null_urls(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [14.0, 40.0]},
             "properties": {"url": "http://example.com/a.tif"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [14.1, 40.1]},
             "properties": {"url": None}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [14.2, 40.2]},
             "properties": {"url": "http://example.com/b.tif"}},
        ],
    }
    mock_resp = MagicMock()
    mock_resp.content = json.dumps(geojson).encode()
    mock_resp.raise_for_status.return_value = None

    with patch("indexmap_cli.downloader.requests.get", return_value=mock_resp):
        result = get_file_paths_from_wfs(server_base_url, server_workspace, server_layer, "url")

    assert None not in result
    assert len(result) == 2


def test_get_file_paths_from_wfs_raises_on_http_error(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    with patch(
        "indexmap_cli.downloader.requests.get",
        side_effect=requests.RequestException("network error"),
    ):
        with pytest.raises(requests.RequestException):
            get_file_paths_from_wfs(server_base_url, server_workspace, server_layer, "url")


# ---------------------------------------------------------------------------
# get_file_paths_from_wfs — SSL propagation
# ---------------------------------------------------------------------------


def test_get_file_paths_from_wfs_skip_ssl_passes_verify_false(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    mock_resp = _make_wfs_response("http://example.com/a.tif")
    with patch("indexmap_cli.downloader.requests.get", return_value=mock_resp) as mock_get:
        get_file_paths_from_wfs(server_base_url, server_workspace, server_layer, "url", skip_ssl_verify=True)

    assert mock_get.call_args[1]["verify"] is False


def test_get_file_paths_from_wfs_no_skip_ssl_passes_verify_true(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    mock_resp = _make_wfs_response("http://example.com/a.tif")
    with patch("indexmap_cli.downloader.requests.get", return_value=mock_resp) as mock_get:
        get_file_paths_from_wfs(server_base_url, server_workspace, server_layer, "url", skip_ssl_verify=False)

    assert mock_get.call_args[1]["verify"] is True


# ---------------------------------------------------------------------------
# download_file — unit tests
# ---------------------------------------------------------------------------


def test_download_file_creates_output_dir(tmp_output_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"data"]
    mock_response.raise_for_status.return_value = None

    with patch("indexmap_cli.downloader.requests.get", return_value=mock_response):
        download_file("http://example.com/tile.tif", tmp_output_dir)

    assert tmp_output_dir.is_dir()


def test_download_file_saves_content(tmp_output_dir: Path) -> None:
    file_content = b"fake raster data"
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [file_content]
    mock_response.raise_for_status.return_value = None

    with patch("indexmap_cli.downloader.requests.get", return_value=mock_response):
        download_file("http://example.com/tile.tif", tmp_output_dir)

    saved_file = tmp_output_dir / "tile.tif"
    assert saved_file.exists()
    assert saved_file.read_bytes() == file_content


def test_download_file_handles_request_error(tmp_output_dir: Path) -> None:
    with patch(
        "indexmap_cli.downloader.requests.get",
        side_effect=requests.RequestException("connection refused"),
    ):
        with pytest.raises(requests.RequestException, match="connection refused"):
            download_file("http://example.com/tile.tif", tmp_output_dir)


def test_download_file_skip_ssl_passes_verify_false(tmp_output_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"data"]
    mock_response.raise_for_status.return_value = None

    with patch("indexmap_cli.downloader.requests.get", return_value=mock_response) as mock_get:
        download_file("http://example.com/tile.tif", tmp_output_dir, skip_ssl_verify=True)

    mock_get.assert_called_once_with("http://example.com/tile.tif", stream=True, verify=False)


def test_download_file_no_skip_ssl_passes_verify_true(tmp_output_dir: Path) -> None:
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"data"]
    mock_response.raise_for_status.return_value = None

    with patch("indexmap_cli.downloader.requests.get", return_value=mock_response) as mock_get:
        download_file("http://example.com/tile.tif", tmp_output_dir, skip_ssl_verify=False)

    mock_get.assert_called_once_with("http://example.com/tile.tif", stream=True, verify=True)


# ---------------------------------------------------------------------------
# Integration tests — require real .env configuration
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_get_file_paths_from_wfs(
    server_base_url: str, server_workspace: str, server_layer: str, server_url_field: str, skip_ssl: bool
) -> None:
    """Connect to the real WFS server and assert that a non-empty URL list is returned."""
    urls = get_file_paths_from_wfs(server_base_url, server_workspace, server_layer, server_url_field, skip_ssl)
    assert isinstance(urls, list)
    assert len(urls) > 0, "WFS returned no features"
    assert all(isinstance(u, str) and u.startswith("http") for u in urls)
