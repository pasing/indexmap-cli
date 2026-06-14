import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env so that real server variables are available to all tests.
load_dotenv()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test that connects to the real server",
    )


# ---------------------------------------------------------------------------
# Generic fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    return tmp_path / "output"


@pytest.fixture
def sample_geojson() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [14.25, 40.85]},
                "properties": {"url": "http://example.com/file.tif"},
            }
        ],
    }


# ---------------------------------------------------------------------------
# Server configuration fixtures — loaded from .env
# ---------------------------------------------------------------------------


@pytest.fixture
def server_base_url() -> str:
    """Base URL for the OGC server. Loaded from INDEXMAP_BASE_URL."""
    return os.environ.get("INDEXMAP_BASE_URL", "http://geoserver.test")


@pytest.fixture
def server_workspace() -> str:
    """Workspace name. Loaded from INDEXMAP_WORKSPACE."""
    return os.environ.get("INDEXMAP_WORKSPACE", "test_workspace")


@pytest.fixture
def server_layer() -> str:
    """Layer name. Loaded from INDEXMAP_LAYER."""
    return os.environ.get("INDEXMAP_LAYER", "test_layer")


@pytest.fixture
def server_url_field() -> str:
    """URL field name. Loaded from INDEXMAP_URL_FIELD."""
    return os.environ.get("INDEXMAP_URL_FIELD", "url")


@pytest.fixture
def skip_ssl() -> bool:
    """Whether to skip SSL verification. Loaded from INDEXMAP_SKIP_SSL_VERIFY."""
    val = os.environ.get("INDEXMAP_SKIP_SSL_VERIFY", "true").lower()
    return val in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Integration guard — skip if server is not configured
# ---------------------------------------------------------------------------

_REQUIRED_INTEGRATION_VARS = ("INDEXMAP_BASE_URL", "INDEXMAP_WORKSPACE", "INDEXMAP_LAYER")


def _integration_server_configured() -> bool:
    return all(os.environ.get(v, "").strip() for v in _REQUIRED_INTEGRATION_VARS)


@pytest.fixture(autouse=True)
def skip_integration_if_not_configured(request: pytest.FixtureRequest) -> None:
    """Automatically skip @pytest.mark.integration tests when server env vars are not set."""
    if request.node.get_closest_marker("integration") and not _integration_server_configured():
        pytest.skip("Integration test skipped: set INDEXMAP_BASE_URL, INDEXMAP_WORKSPACE, INDEXMAP_LAYER in .env")
