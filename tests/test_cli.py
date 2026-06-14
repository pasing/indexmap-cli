from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from indexmap_cli.analyzer import LayerStats, PropertyInfo
from indexmap_cli.merger import MergeResult
from indexmap_cli.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Validation: missing required options
# ---------------------------------------------------------------------------


def test_download_exits_if_base_url_missing(server_workspace: str, server_layer: str) -> None:
    # Pass explicit empty string to override any INDEXMAP_BASE_URL env var that
    # may be set in the environment, since CLI defaults are frozen at import time.
    result = runner.invoke(
        app,
        ["download", "--base-url", "", "--workspace", server_workspace, "--layer", server_layer],
    )
    assert result.exit_code == 1
    assert "base-url" in result.output.lower() or "base-url" in (result.stderr or "").lower()


def test_download_exits_if_workspace_missing(server_base_url: str, server_layer: str) -> None:
    result = runner.invoke(
        app,
        ["download", "--base-url", server_base_url, "--workspace", "", "--layer", server_layer],
    )
    assert result.exit_code == 1
    assert "workspace" in result.output.lower() or "workspace" in (result.stderr or "").lower()


def test_download_exits_if_layer_missing(server_base_url: str, server_workspace: str) -> None:
    result = runner.invoke(
        app,
        ["download", "--base-url", server_base_url, "--workspace", server_workspace, "--layer", ""],
    )
    assert result.exit_code == 1
    assert "layer" in result.output.lower() or "layer" in (result.stderr or "").lower()


# ---------------------------------------------------------------------------
# Happy path (mocked WFS + mocked file download)
# ---------------------------------------------------------------------------


def test_download_command_happy_path(
    server_base_url: str, server_workspace: str, server_layer: str, tmp_output_dir: Path
) -> None:
    with (
        patch(
            "indexmap_cli.cli.get_file_paths_from_wfs",
            return_value=["http://example.com/a.tif", "http://example.com/b.tif"],
        ),
        patch(
            "indexmap_cli.cli.download_file",
            side_effect=[tmp_output_dir / "a.tif", tmp_output_dir / "b.tif"],
        ) as mock_download,
    ):
        result = runner.invoke(
            app,
            [
                "download",
                "--base-url", server_base_url,
                "--workspace", server_workspace,
                "--layer", server_layer,
                "--output-dir", str(tmp_output_dir),
            ],
        )

    assert result.exit_code == 0
    assert mock_download.call_count == 2
    assert "2 files" in result.output
    assert "Downloaded: a.tif" in result.output
    assert "Downloaded: b.tif" in result.output


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------


def test_download_command_exits_on_wfs_error(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    with patch(
        "indexmap_cli.cli.get_file_paths_from_wfs",
        side_effect=ValueError("url field not found"),
    ):
        result = runner.invoke(
            app,
            [
                "download",
                "--base-url", server_base_url,
                "--workspace", server_workspace,
                "--layer", server_layer,
            ],
        )

    assert result.exit_code == 1
    assert "url field not found" in result.output


def test_download_command_exits_on_download_error(
    server_base_url: str, server_workspace: str, server_layer: str, tmp_output_dir: Path
) -> None:
    with (
        patch(
            "indexmap_cli.cli.get_file_paths_from_wfs",
            return_value=["http://example.com/a.tif"],
        ),
        patch(
            "indexmap_cli.cli.download_file",
            side_effect=RuntimeError("disk full"),
        ),
    ):
        result = runner.invoke(
            app,
            [
                "download",
                "--base-url", server_base_url,
                "--workspace", server_workspace,
                "--layer", server_layer,
                "--output-dir", str(tmp_output_dir),
            ],
        )

    assert result.exit_code == 1
    assert "disk full" in result.output


# ---------------------------------------------------------------------------
# SSL option propagation
# ---------------------------------------------------------------------------


def test_download_command_passes_skip_ssl_to_business_logic(
    server_base_url: str, server_workspace: str, server_layer: str, tmp_output_dir: Path
) -> None:
    """--skip-ssl-verify flag must be forwarded to get_file_paths_from_wfs and download_file."""
    with (
        patch("indexmap_cli.cli.get_file_paths_from_wfs", return_value=["http://example.com/a.tif"]) as mock_wfs,
        patch("indexmap_cli.cli.download_file") as mock_dl,
    ):
        result = runner.invoke(
            app,
            [
                "download",
                "--base-url", server_base_url,
                "--workspace", server_workspace,
                "--layer", server_layer,
                "--output-dir", str(tmp_output_dir),
                "--skip-ssl-verify",
            ],
        )

    assert result.exit_code == 0
    _, _, _, _, skip = mock_wfs.call_args[0]
    assert skip is True
    _, _, skip_dl = mock_dl.call_args[0]
    assert skip_dl is True


def test_download_command_no_skip_ssl_passes_false(
    server_base_url: str, server_workspace: str, server_layer: str, tmp_output_dir: Path
) -> None:
    """--no-skip-ssl-verify must forward skip_ssl_verify=False to business logic."""
    with (
        patch("indexmap_cli.cli.get_file_paths_from_wfs", return_value=["http://example.com/a.tif"]) as mock_wfs,
        patch("indexmap_cli.cli.download_file") as mock_dl,
    ):
        result = runner.invoke(
            app,
            [
                "download",
                "--base-url", server_base_url,
                "--workspace", server_workspace,
                "--layer", server_layer,
                "--output-dir", str(tmp_output_dir),
                "--no-skip-ssl-verify",
            ],
        )

    assert result.exit_code == 0
    _, _, _, _, skip = mock_wfs.call_args[0]
    assert skip is False
    _, _, skip_dl = mock_dl.call_args[0]
    assert skip_dl is False


def test_download_command_warns_when_skip_ssl_enabled(
    server_base_url: str, server_workspace: str, server_layer: str, tmp_output_dir: Path
) -> None:
    with (
        patch(
            "indexmap_cli.cli.get_file_paths_from_wfs",
            return_value=["http://example.com/a.tif"],
        ),
        patch(
            "indexmap_cli.cli.download_file",
            return_value=tmp_output_dir / "a.tif",
        ),
    ):
        result = runner.invoke(
            app,
            [
                "download",
                "--base-url", server_base_url,
                "--workspace", server_workspace,
                "--layer", server_layer,
                "--output-dir", str(tmp_output_dir),
                "--skip-ssl-verify",
            ],
        )

    assert result.exit_code == 0
    assert "tls" in result.output.lower() or "certificate" in result.output.lower()


# ---------------------------------------------------------------------------
# Integration test — requires real .env configuration
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_download_command(
    server_base_url: str,
    server_workspace: str,
    server_layer: str,
    server_url_field: str,
    skip_ssl: bool,
    tmp_output_dir: Path,
) -> None:
    """Run the download command against the real server; verify at least one file is downloaded."""
    result = runner.invoke(
        app,
        [
            "download",
            "--base-url", server_base_url,
            "--workspace", server_workspace,
            "--layer", server_layer,
            "--url-field", server_url_field,
            "--output-dir", str(tmp_output_dir),
            "--skip-ssl-verify" if skip_ssl else "--no-skip-ssl-verify",
        ],
    )
    assert result.exit_code == 0, f"CLI failed:\n{result.output}"
    downloaded = list(tmp_output_dir.iterdir())
    assert len(downloaded) > 0, "No files were downloaded"


# ---------------------------------------------------------------------------
# analyze command — validation
# ---------------------------------------------------------------------------


def test_analyze_exits_if_base_url_missing(server_workspace: str, server_layer: str) -> None:
    result = runner.invoke(
        app,
        ["analyze", "--base-url", "", "--workspace", server_workspace, "--layer", server_layer],
    )
    assert result.exit_code == 1
    assert "base-url" in result.output.lower() or "base-url" in (result.stderr or "").lower()


def test_analyze_exits_if_workspace_missing(server_base_url: str, server_layer: str) -> None:
    result = runner.invoke(
        app,
        ["analyze", "--base-url", server_base_url, "--workspace", "", "--layer", server_layer],
    )
    assert result.exit_code == 1
    assert "workspace" in result.output.lower() or "workspace" in (result.stderr or "").lower()


def test_analyze_exits_if_layer_missing(server_base_url: str, server_workspace: str) -> None:
    result = runner.invoke(
        app,
        ["analyze", "--base-url", server_base_url, "--workspace", server_workspace, "--layer", ""],
    )
    assert result.exit_code == 1
    assert "layer" in result.output.lower() or "layer" in (result.stderr or "").lower()


# ---------------------------------------------------------------------------
# analyze command — happy path (mocked analyze_layer)
# ---------------------------------------------------------------------------


def _sample_stats(workspace: str, layer: str) -> LayerStats:
    return LayerStats(
        layer_name=f"{workspace}:{layer}",
        epsg=32633,
        bbox=(14.0, 40.0, 15.0, 41.0),
        feature_count=35,
        properties=[
            PropertyInfo(name="id", dtype="int64", contains_urls=False),
            PropertyInfo(
                name="url",
                dtype="object",
                contains_urls=True,
                sample_value="http://example.com/005770.asc",
            ),
        ],
        url_properties=["url"],
        quadrant_start="5770",
        quadrant_end="5804",
        numbering_type="discontinuous",
        file_formats=[".asc"],
    )


def test_analyze_command_happy_path(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    stats = _sample_stats(server_workspace, server_layer)
    with patch("indexmap_cli.cli.analyze_layer", return_value=stats):
        result = runner.invoke(
            app,
            [
                "analyze",
                "--base-url", server_base_url,
                "--workspace", server_workspace,
                "--layer", server_layer,
            ],
        )
    assert result.exit_code == 0
    assert "32633" in result.output
    assert "35" in result.output
    assert "5770" in result.output
    assert "5804" in result.output
    assert "discontinuous" in result.output
    assert ".asc" in result.output
    assert "[URL]" in result.output


def test_analyze_command_shows_single_url_field_label(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    stats = _sample_stats(server_workspace, server_layer)
    with patch("indexmap_cli.cli.analyze_layer", return_value=stats):
        result = runner.invoke(
            app,
            ["analyze", "--base-url", server_base_url, "--workspace", server_workspace, "--layer", server_layer],
        )
    assert "single" in result.output


def test_analyze_command_shows_multi_url_field_label(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    stats = _sample_stats(server_workspace, server_layer)
    stats.url_properties = ["url_dem", "url_ortho"]
    with patch("indexmap_cli.cli.analyze_layer", return_value=stats):
        result = runner.invoke(
            app,
            ["analyze", "--base-url", server_base_url, "--workspace", server_workspace, "--layer", server_layer],
        )
    assert "multi" in result.output


def test_analyze_command_shows_no_url_fields_warning(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    stats = _sample_stats(server_workspace, server_layer)
    stats.url_properties = []
    stats.properties = [PropertyInfo(name="id", dtype="int64", contains_urls=False)]
    with patch("indexmap_cli.cli.analyze_layer", return_value=stats):
        result = runner.invoke(
            app,
            ["analyze", "--base-url", server_base_url, "--workspace", server_workspace, "--layer", server_layer],
        )
    assert "no url fields" in result.output.lower()


def test_analyze_command_exits_on_error(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    with patch("indexmap_cli.cli.analyze_layer", side_effect=ValueError("parse error")):
        result = runner.invoke(
            app,
            ["analyze", "--base-url", server_base_url, "--workspace", server_workspace, "--layer", server_layer],
        )
    assert result.exit_code == 1
    assert "parse error" in result.output


def test_analyze_command_warns_when_skip_ssl_enabled(
    server_base_url: str, server_workspace: str, server_layer: str
) -> None:
    stats = _sample_stats(server_workspace, server_layer)
    with patch("indexmap_cli.cli.analyze_layer", return_value=stats):
        result = runner.invoke(
            app,
            [
                "analyze",
                "--base-url", server_base_url,
                "--workspace", server_workspace,
                "--layer", server_layer,
                "--skip-ssl-verify",
            ],
        )
    assert result.exit_code == 0
    assert "tls" in result.output.lower() or "certificate" in result.output.lower()


# ---------------------------------------------------------------------------
# analyze command — integration test
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_analyze_command(
    server_base_url: str,
    server_workspace: str,
    server_layer: str,
    skip_ssl: bool,
) -> None:
    """Run the analyze command against the real server."""
    result = runner.invoke(
        app,
        [
            "analyze",
            "--base-url", server_base_url,
            "--workspace", server_workspace,
            "--layer", server_layer,
            "--skip-ssl-verify" if skip_ssl else "--no-skip-ssl-verify",
        ],
    )
    assert result.exit_code == 0, f"CLI failed:\n{result.output}"
    assert "layer" in result.output.lower()
    assert "epsg" in result.output.lower()
    assert "quadrants" in result.output.lower()


# ---------------------------------------------------------------------------
# merge command — validation
# ---------------------------------------------------------------------------


def test_merge_exits_on_invalid_output_format(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    result = runner.invoke(
        app,
        ["merge", str(src), str(tmp_path / "out.tif"), "--output-format", "badformat"],
    )
    assert result.exit_code == 1
    assert "output-format" in result.output.lower()


# ---------------------------------------------------------------------------
# merge command — happy path (mocked merge_tiles)
# ---------------------------------------------------------------------------


def _sample_merge_result(src_dir: Path, out: Path) -> MergeResult:
    return MergeResult(
        kind="raster",
        input_files=[src_dir / "a.tif", src_dir / "b.tif"],
        output_file=out,
        output_format="cog",
        crs_set=False,
    )


def test_merge_command_happy_path(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out.tif"
    fake_result = _sample_merge_result(src, out)
    with patch("indexmap_cli.cli.merge_tiles", return_value=fake_result):
        result = runner.invoke(app, ["merge", str(src), str(out)])
    assert result.exit_code == 0
    assert "raster" in result.output
    assert "cog" in result.output
    assert "2" in result.output  # files read count


def test_merge_command_prints_input_crs_when_provided(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out.tif"
    fake_result = MergeResult(
        kind="raster",
        input_files=[src / "a.tif"],
        output_file=out,
        output_format="cog",
        crs_set=True,
    )
    with patch("indexmap_cli.cli.merge_tiles", return_value=fake_result):
        result = runner.invoke(
            app, ["merge", str(src), str(out), "--input-crs", "32633"]
        )
    assert result.exit_code == 0
    assert "32633" in result.output


def test_merge_command_prints_glob_when_not_default(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out.tif"
    fake_result = _sample_merge_result(src, out)
    with patch("indexmap_cli.cli.merge_tiles", return_value=fake_result):
        result = runner.invoke(
            app, ["merge", str(src), str(out), "--glob", "*.asc"]
        )
    assert result.exit_code == 0
    assert "*.asc" in result.output


def test_merge_command_exits_on_error(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out.tif"
    with patch("indexmap_cli.cli.merge_tiles", side_effect=ValueError("no files found")):
        result = runner.invoke(app, ["merge", str(src), str(out)])
    assert result.exit_code == 1
    assert "no files found" in result.output


def test_merge_command_vector_summary(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out.gpkg"
    fake_result = MergeResult(
        kind="vector",
        input_files=[src / "a.shp", src / "b.shp"],
        output_file=out,
        output_format="gpkg",
        crs_set=False,
    )
    with patch("indexmap_cli.cli.merge_tiles", return_value=fake_result):
        result = runner.invoke(app, ["merge", str(src), str(out)])
    assert result.exit_code == 0
    assert "vector" in result.output
    assert "gpkg" in result.output
