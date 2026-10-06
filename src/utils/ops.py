"""Raster operations — combining, overlaying, and producing new raster arrays."""

import numpy as np
from scipy import ndimage


def combine_binary_union(raster_a, raster_b, nodata_val=255):
    """Boolean OR (union) of two binary rasters, respecting NoData.

    Result: 1 where either is 1, 0 where both are 0, nodata where both are nodata.
    """
    mask_a = raster_a != nodata_val
    mask_b = raster_b != nodata_val

    result = np.full(raster_a.shape, nodata_val, dtype=raster_a.dtype)
    valid = mask_a | mask_b
    result[valid] = (
        (raster_a[valid] == 1) | (raster_b[valid] == 1)
    ).astype(raster_a.dtype)
    return result


def validate_inputs(layers, profiles):
    """Guardrail: check dtypes, value ranges, and grid alignment of loaded rasters.

    Args:
        layers: dict of {name: np.ndarray}
        profiles: dict of {name: rasterio profile dict}

    Raises:
        ValueError with details if any check fails.
    """
    errors = []

    # Grid alignment — all profiles must match the first
    ref_name = next(iter(profiles))
    ref_sig = {
        "crs": str(profiles[ref_name].get("crs")),
        "transform": tuple(profiles[ref_name].get("transform")),
        "width": profiles[ref_name].get("width"),
        "height": profiles[ref_name].get("height"),
    }
    for name, prof in profiles.items():
        sig = {
            "crs": str(prof.get("crs")),
            "transform": tuple(prof.get("transform")),
            "width": prof.get("width"),
            "height": prof.get("height"),
        }
        if sig != ref_sig:
            errors.append(f"{name}: grid mismatch with {ref_name}")

    # Shape consistency
    ref_shape = next(iter(layers.values())).shape
    for name, arr in layers.items():
        if arr.shape != ref_shape:
            errors.append(f"{name}: shape {arr.shape} != expected {ref_shape}")

    if errors:
        raise ValueError("Input validation failed:\n  " + "\n  ".join(errors))


def recode_binary(arr, valid, nodata_val=np.nan):
    """Clip valid pixels to [0, 1]. Binary layers should already be {0, 1}."""
    out = np.where(valid, np.clip(arr, 0, 1), nodata_val).astype(np.float32)
    return out


def build_exclusion_mask(mask_arrays, valid, nodata_val=np.nan):
    """OR-combine binary mask layers into a single boolean exclusion mask.

    A pixel is excluded if any mask layer has value 1 at that pixel.
    Only considers pixels that are valid (not nodata) across all layers.

    Args:
        mask_arrays: list of np.ndarray (each is binary {0, 1})
        valid: boolean array — True where data is valid
        nodata_val: unused, kept for API consistency

    Returns:
        Boolean array — True where pixel should be excluded.
    """
    excluded = np.zeros_like(valid, dtype=bool)
    for arr in mask_arrays:
        finite = np.isfinite(arr)
        excluded |= (finite & (arr == 1))
    return excluded


def weighted_sum(score_arrays, weights, valid, nodata_val=np.nan):
    """Compute weighted sum of score layers on valid pixels.

    Args:
        score_arrays: list of np.ndarray (recoded to [0, 1])
        weights: list of float weights (same length as score_arrays)
        valid: boolean array — True where data is valid
        nodata_val: fill value for invalid pixels

    Returns:
        np.ndarray — raw weighted sum (naturally 0–5 range for WSI).
    """
    result = np.zeros(score_arrays[0].shape, dtype=np.float32)
    for arr, w in zip(score_arrays, weights):
        result += np.float32(w) * arr
    result[~valid] = nodata_val
    return result


def apply_mask(arr, excluded, fill_value=np.nan):
    """Set excluded pixels to fill_value (NoData)."""
    out = arr.copy()
    out[excluded] = fill_value
    return out


def classify_quarter_step(raw_weighted, valid, fill_value=np.nan, step=0.25):
    """Round valid pixels to nearest quarter-step, clip to [0, 5].

    No normalization — the raw weighted sum is already on a 0–5 scale.

    Args:
        raw_weighted: np.ndarray — raw weighted sum
        valid: boolean array
        fill_value: value for invalid/excluded pixels
        step: rounding step (default 0.25)

    Returns:
        np.ndarray — classified values in {0.0, 0.25, 0.5, ..., 5.0}
    """
    out = np.full(raw_weighted.shape, fill_value, dtype=np.float32)
    v = raw_weighted[valid]
    out[valid] = np.clip(np.round(v / step) * step, 0.0, 5.0)
    return out


def highsuit_threshold(classified, threshold, valid, fill_value=np.nan):
    """Binary classification: 1 where classified >= threshold, 0 otherwise.

    Only applies to valid pixels; others get fill_value.
    """
    out = np.full(classified.shape, fill_value, dtype=np.float32)
    out[valid] = (classified[valid] >= threshold).astype(np.float32)
    return out


def focal_circular_mean(arr, valid, radius):
    """NaN-aware circular focal mean on a raster array.

    Computes the mean of valid pixels within a circular neighbourhood of
    the given radius (in pixels). Invalid pixels are excluded from both the
    sum and the count so edges and NoData boundaries do not bias the result.

    Args:
        arr: np.ndarray — input raster values
        valid: boolean array — True where data is valid
        radius: int — neighbourhood radius in pixels

    Returns:
        np.ndarray — smoothed values (NaN where no valid neighbours exist)
    """
    y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    kernel = ((x ** 2 + y ** 2) <= radius ** 2).astype(np.float32)

    filled = np.where(valid, arr, 0.0).astype(np.float32)
    count = valid.astype(np.float32)

    s = ndimage.convolve(filled, kernel, mode='constant', cval=0.0)
    c = ndimage.convolve(count, kernel, mode='constant', cval=0.0)

    out = np.full_like(arr, np.nan, dtype=np.float32)
    has_neighbours = c > 0
    out[has_neighbours] = s[has_neighbours] / c[has_neighbours]
    out[~valid] = np.nan
    return out


def distribution_summary(arr, valid, step=None):
    """Compute value distribution for metrics JSON.

    Args:
        arr: np.ndarray
        valid: boolean array
        step: if provided, round values to this step before counting

    Returns:
        dict with keys: distribution, mean, std, valid_pixels, raw_range
    """
    v = arr[valid].astype(np.float64)
    if step is not None:
        v = np.round(v / step) * step

    total = len(v)
    unique, counts = np.unique(v, return_counts=True)
    dist = {}
    for val, cnt in zip(unique, counts):
        key = f"{val:.2f}"
        dist[key] = f"{cnt / total * 100:.1f}%"

    return {
        "distribution": dist,
        "raw_range": [float(v.min()), float(v.max())],
        "mean": round(float(v.mean()), 4),
        "std": round(float(v.std()), 4),
        "valid_pixels": int(total),
    }
