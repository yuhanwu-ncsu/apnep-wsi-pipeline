"""Grid helpers — NoData masking, grid signatures, and raster alignment."""

import numpy as np
from rasterio.warp import reproject, Resampling


def is_nodata(arr: np.ndarray, nodata) -> np.ndarray:
    """True where pixel is NoData or non-finite.

    Handles both float32 sentinel values (via isclose) and NaN.
    """
    if nodata is None:
        return ~np.isfinite(arr)
    return ~np.isfinite(arr) | np.isclose(arr, nodata, rtol=0, atol=1e-30, equal_nan=True)


def valid_mask(arr: np.ndarray, nodata) -> np.ndarray:
    """True where pixel has valid data."""
    return ~is_nodata(arr, nodata)


def finite_mask(arr: np.ndarray, nodata) -> np.ndarray:
    """True where pixel is valid and finite — convenience wrapper around valid_mask."""
    return valid_mask(arr, nodata)


def grid_signature(profile: dict) -> dict:
    """Extract grid-defining properties from a rasterio profile."""
    return {
        "crs": str(profile.get("crs")),
        "transform": tuple(profile.get("transform")),
        "width": int(profile.get("width")),
        "height": int(profile.get("height")),
        "nodata": profile.get("nodata", None),
    }


def grids_match(prof_a: dict, prof_b: dict) -> bool:
    """Check whether two profiles share the same grid (CRS, transform, shape)."""
    return (
        prof_a.get("crs") == prof_b.get("crs")
        and prof_a.get("transform") == prof_b.get("transform")
        and prof_a.get("width") == prof_b.get("width")
        and prof_a.get("height") == prof_b.get("height")
    )


def _reproject_to_grid(src_arr, src_prof, dst_prof, dst, src_nodata, dst_nodata, resampling):
    """Internal: run rasterio.warp.reproject with profile-derived params."""
    reproject(
        source=src_arr,
        destination=dst,
        src_transform=src_prof["transform"],
        src_crs=src_prof["crs"],
        src_nodata=src_nodata,
        dst_transform=dst_prof["transform"],
        dst_crs=dst_prof["crs"],
        dst_nodata=dst_nodata,
        resampling=resampling,
    )
    return dst


def align_continuous_to_grid(
    src_arr: np.ndarray,
    src_prof: dict,
    dst_prof: dict,
    resampling=Resampling.nearest,
) -> np.ndarray:
    """Reproject a continuous raster to match the destination grid as float32.

    Output is float32 with dst_nodata (or NaN) filling out-of-extent pixels.
    Use for continuous data layers (slope, soil drainage, weighted sums).
    """
    src_nodata = src_prof.get("nodata", None)
    dst_nodata = dst_prof.get("nodata", None)

    fill = dst_nodata if dst_nodata is not None else np.nan
    dst = np.full((dst_prof["height"], dst_prof["width"]), fill, dtype=np.float32)

    return _reproject_to_grid(src_arr, src_prof, dst_prof, dst, src_nodata, dst_nodata, resampling)


def align_categorical_to_grid(
    src_arr: np.ndarray,
    src_prof: dict,
    dst_prof: dict,
    resampling=Resampling.nearest,
) -> np.ndarray:
    """Reproject a categorical raster to match the destination grid.

    Preserves the source dtype (e.g. uint8 for class labels) and fills
    out-of-extent pixels with the source nodata value. Use for integer
    class layers (CRPA, land cover, PADUS masks).
    """
    src_nodata = src_prof.get("nodata", None)
    fill = src_nodata if src_nodata is not None else 0

    dst = np.full((dst_prof["height"], dst_prof["width"]), fill, dtype=src_arr.dtype)

    return _reproject_to_grid(src_arr, src_prof, dst_prof, dst, src_nodata, src_nodata, resampling)
