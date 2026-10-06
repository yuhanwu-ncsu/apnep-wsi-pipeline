"""Raster I/O — loading data and extracting metadata from zipped and on-disk GeoTIFFs."""

import numpy as np
import rasterio
import zipfile
from pathlib import Path
from rasterio.io import MemoryFile


def load_zipped_raster(zip_path):
    """Open a zipped GeoTIFF into memory without extracting to disk.

    Returns:
        data (np.ndarray): Pixel values (Band 1).
        profile (dict): Rasterio profile (CRS, transform, nodata, etc.).
    """
    with zipfile.ZipFile(zip_path, "r") as z:
        tif_files = [f for f in z.namelist() if f.endswith(".tif")]
        if not tif_files:
            raise FileNotFoundError(f"No .tif found in {zip_path}")

        with z.open(tif_files[0]) as f:
            with MemoryFile(f) as memfile:
                with memfile.open() as src:
                    return src.read(1), src.profile


def get_raster_profile(file_path):
    """Extract core spatial metadata from an on-disk GeoTIFF."""
    with rasterio.open(file_path) as src:
        return {
            "crs": src.crs.to_epsg() if src.crs else "Unknown",
            "res": src.res,
            "bounds": src.bounds,
            "width": src.width,
            "height": src.height,
            "nodata": src.nodata,
        }


def get_zip_raster_profile(zip_path, verbose=False):
    """Extract raster metadata from a ZIP via /vsizip/.

    If verbose=True, returns full profile (dtype, transform, nodata, tags).
    """
    abs_zip_path = Path(zip_path).resolve().as_posix()

    with zipfile.ZipFile(zip_path, "r") as z:
        tiff_files = [f for f in z.namelist() if f.lower().endswith((".tif", ".tiff"))]
        if not tiff_files:
            raise FileNotFoundError(f"No .tif found inside {zip_path}")
        internal_tif = tiff_files[0]

    vsi_path = f"/vsizip/{abs_zip_path}/{internal_tif}"

    with rasterio.open(vsi_path) as src:
        stats = {
            "filename": Path(zip_path).name,
            "crs": src.crs.to_epsg() if src.crs else "Unknown",
            "res": src.res,
            "width": src.width,
            "height": src.height,
            "internal_name": internal_tif,
        }
        if verbose:
            stats.update({
                "driver": src.driver,
                "count": src.count,
                "dtype": src.dtypes[0],
                "nodata": src.nodata,
                "transform": src.transform,
                "block_size": src.block_shapes[0],
                "tags": src.tags(),
            })
        return stats


def save_raster(path, data, profile, compress="lzw"):
    """Write a single-band GeoTIFF to disk.

    Args:
        path: Output file path.
        data: 2-D numpy array (single band).
        profile: Rasterio profile dict (transform, crs, nodata, etc.).
        compress: Compression algorithm (default "lzw").
    """
    out_profile = dict(profile)
    out_profile.update(
        driver="GTiff",
        count=1,
        dtype=data.dtype,
        compress=compress,
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(data, 1)
