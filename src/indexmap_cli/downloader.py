"""
downloader.py — WFS feature fetch and file download for indexmap-cli.

Provides two public functions:

- :func:`get_file_paths_from_wfs`: queries a WFS endpoint and extracts the
  download URLs stored in a specified attribute column.
- :func:`download_file`: streams a single URL to a local file inside a given
  output directory.

Both functions accept a ``skip_ssl_verify`` flag that suppresses TLS warnings
when connecting to servers with self-signed certificates.
"""
import io
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import geopandas as gpd
import requests
import urllib3


def get_file_paths_from_wfs(
    base_url: str,
    workspace: str,
    layer: str,
    url_field: str,
    skip_ssl_verify: bool = True,
) -> list[str]:
    """Fetch the index map via WFS and extract download URLs from the specified attribute."""
    clean_base_url = base_url.rstrip("/")
    full_layer_name = f"{workspace}:{layer}"

    query_string = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": full_layer_name,
        "outputFormat": "application/json",
    }

    service_url = f"{clean_base_url}/{workspace}/ows?{urlencode(query_string)}"

    if skip_ssl_verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Fetch via requests so that SSL verification is controlled explicitly.
    # gpd.read_file(url) uses Python's urllib internally and ignores GDAL_HTTP_UNSAFESSL.
    response = requests.get(service_url, verify=not skip_ssl_verify)
    response.raise_for_status()

    gdf = gpd.read_file(io.BytesIO(response.content))

    if url_field not in gdf.columns:
        raise ValueError(f"Attribute field '{url_field}' not found in the index map.")

    return gdf[url_field].dropna().tolist()


def download_file(url: str, output_dir: Path, skip_ssl_verify: bool = True) -> Path:
    """Download a single file to the target directory and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urlsplit(url).path).name
    destination = output_dir / filename

    if skip_ssl_verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    response = requests.get(url, stream=True, verify=not skip_ssl_verify)
    response.raise_for_status()

    with open(destination, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return destination