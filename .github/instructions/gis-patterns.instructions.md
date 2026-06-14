---
description: "Use when writing geospatial code that uses geopandas, rasterio, shapely, or WFS/WMS/OGC services. Covers data loading, CRS handling, raster operations, and GeoServer integration."
applyTo: "src/indexmap_cli/*.py"
---

# GIS Code Patterns — indexmap-cli

## GeoPandas

- Always read vector data with `gpd.read_file(url_or_path)`.
- Always verify that required columns exist before accessing them.
- Check the CRS before spatial operations; reproject with `.to_crs()` if necessary.
- Use `.dropna()` on fields that may contain null values (e.g. URLs).

```python
# ✅ CRS check pattern
if gdf.crs is None:
    raise ValueError("GeoDataFrame has no CRS defined.")
if gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)
```

## WFS / GeoServer

- Build WFS URLs with `urlencode()` from `urllib.parse` — never concatenate query strings manually.
- Standard WFS parameters: `service=WFS`, `version=1.0.0`, `request=GetFeature`, `outputFormat=application/json`.
- URL pattern: `{base_url}/{workspace}/ows?{query_string}`.
- Call `rstrip("/")` on `base_url` before using it.

```python
query_string = {
    "service": "WFS",
    "version": "1.0.0",
    "request": "GetFeature",
    "typeName": f"{workspace}:{layer}",
    "outputFormat": "application/json",
}
service_url = f"{clean_base_url}/{workspace}/ows?{urlencode(query_string)}"
```

## Rasterio

- Always open rasters with a context manager `with rasterio.open(path) as src:`.
- Read metadata with `src.meta`, `src.crs`, `src.transform`, `src.count`.
- Use `src.read()` to read bands as NumPy arrays.
- For merge/mosaic operations, use `rasterio.merge.merge()`.
- To create a Cloud Optimised GeoTIFF (COG):
  1. Write the merged data to a temporary GeoTIFF.
  2. Reopen with `"r+"` and call `build_overviews([2,4,8,16,32], Resampling.average)`.
  3. Use `rasterio.shutil.copy(tmp_path, output_path, copy_src_overviews=True, tiled=True, compress="deflate", blockxsize=512, blockysize=512)`.

```python
with rasterio.open(file_path) as src:
    meta = src.meta
    data = src.read()
```

## Shapely

- Use `shapely.geometry` to create geometries (Point, Polygon, LineString).
- For union/intersection operations, use GeoPandas `.union()`, `.intersection()` methods.

## SSL / TLS certificate verification

- Both `get_file_paths_from_wfs` and `download_file` accept a `skip_ssl_verify: bool` parameter (default `True`).
- When `skip_ssl_verify=True`:
  - Set `GDAL_HTTP_UNSAFESSL=YES` env var around the `gpd.read_file()` call (restore it afterwards with try/finally).
  - Pass `verify=False` to `requests.get()`.
  - Call `urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)` to suppress the warning.
- Controlled at CLI level by `--skip-ssl-verify / --no-skip-ssl-verify` and `INDEXMAP_SKIP_SSL_VERIFY` env var.

## File download

- Use `requests.get(url, stream=True, verify=not skip_ssl_verify)` for large files.
- Call `response.raise_for_status()` before writing to disk.
- Standard chunk size: `8192` bytes.
- Create the output directory with `output_dir.mkdir(parents=True, exist_ok=True)`.
