"""Raster comparison — validation, metrics, and difference maps."""

import numpy as np


def validate_raster_identity(calculated, reference, nodata_val=255):
    """Compare two rasters pixel-by-pixel, ignoring NoData in the reference.

    Returns:
        (match: bool, error_pct: float, diff_map: np.ndarray | None)
    """
    data_mask = reference != nodata_val
    calc_data = calculated[data_mask]
    ref_data = reference[data_mask]

    if np.array_equal(calc_data, ref_data):
        return True, 0.0, None

    diff_map = np.zeros_like(calculated, dtype=float)
    diff_map[data_mask] = calc_data.astype(float) - ref_data.astype(float)

    mismatched = np.count_nonzero(diff_map)
    error_pct = (mismatched / data_mask.sum()) * 100
    return False, error_pct, diff_map


def cast_to_reference(arr: np.ndarray, ref_arr: np.ndarray, ref_nodata) -> np.ndarray:
    """Cast array to match reference dtype, filling non-finite values with ref_nodata."""
    out = arr.copy()
    if ref_nodata is not None:
        out = np.where(np.isfinite(out), out, ref_nodata)
    return out.astype(ref_arr.dtype, copy=False)


def hist_l1_diff(ref, pred, nodata, nbin=40, max_px=500_000):
    """L1 histogram distance between two rasters (subsampled for memory safety).

    Returns a float: sum of absolute differences between normalized histograms.
    """
    if nodata is not None:
        m = (ref != nodata) & (pred != nodata)
    else:
        m = np.isfinite(ref) & np.isfinite(pred)

    flat = np.flatnonzero(m)
    if flat.size == 0:
        return np.nan

    step = max(1, flat.size // max_px)
    sub = flat[::step]
    rv = ref.ravel()[sub].astype(np.float64)
    pv = pred.ravel()[sub].astype(np.float64)

    rmin = float(min(rv.min(), pv.min()))
    rmax = float(max(rv.max(), pv.max()))
    bins = np.linspace(rmin, rmax, nbin + 1)

    hr, _ = np.histogram(rv, bins=bins)
    hp, _ = np.histogram(pv, bins=bins)
    hr = hr / max(hr.sum(), 1)
    hp = hp / max(hp.sum(), 1)

    return float(np.sum(np.abs(hr - hp)))


def raster_stats(arr: np.ndarray, nodata) -> dict:
    """Summary statistics for a raster: valid/nodata counts, quantiles, mean, std."""
    if nodata is None:
        v = arr[np.isfinite(arr)]
        nodata_pixels = int((~np.isfinite(arr)).sum())
    else:
        v = arr[arr != nodata]
        nodata_pixels = int((arr == nodata).sum())

    if v.size == 0:
        return {"valid_pixels": 0, "nodata_pixels": nodata_pixels}

    return {
        "valid_pixels": int(v.size),
        "nodata_pixels": nodata_pixels,
        "min": float(np.min(v)),
        "q25": float(np.quantile(v, 0.25)),
        "median": float(np.quantile(v, 0.5)),
        "q75": float(np.quantile(v, 0.75)),
        "max": float(np.max(v)),
        "mean": float(np.mean(v)),
        "std": float(np.std(v)),
    }


def compare_rasters(raw_path, ref_path):
    """Side-by-side metadata comparison of two on-disk rasters.

    Returns a dict keyed by metadata field, each with {match, raw, ref}.
    """
    from .io import get_raster_profile

    raw = get_raster_profile(raw_path)
    ref = get_raster_profile(ref_path)

    report = {}
    for key in raw:
        report[key] = {"match": raw[key] == ref[key], "raw": raw[key], "ref": ref[key]}
    return report
