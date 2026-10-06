"""Recreate WSI (Weighted Site Index) weighted overlay for a given scenario.

Extracts the weighted overlay logic from notebooks 03a/03b into a reusable
pipeline script callable by DVC. Computes quarter-step classified WSI and
binary HighSuit outputs with quality metrics.

Usage:
    python scripts/reproducibility/recreate_wsi.py --scenario conservation
    python scripts/reproducibility/recreate_wsi.py --scenario enhancement
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

# Allow running as script with src/ on PYTHONPATH
from utils.io import load_zipped_raster, save_raster
from utils.grid import valid_mask
from utils.ops import (
    validate_inputs,
    recode_binary,
    build_exclusion_mask,
    weighted_sum,
    apply_mask,
    classify_quarter_step,
    highsuit_threshold,
    distribution_summary,
    focal_circular_mean,
)

SCENARIO_CONFIG = {
    "conservation": {
        "yaml_section": "conservation_2024",
        "prefix": "conserve",
        "input_subdir": "wsi/conservation",
        "benchmark_wsi": "wsi/conservation/apnep-wsi-conserve.zip",
        "benchmark_highsuit": "wsi/conservation/apnep-wsi-conserve-highsuit.zip",
        "highsuit_threshold": 3.5,
        # YAML key -> file suffix (shared layers resolved separately)
        "layer_map": {
            "existing_wetlands": "wetlands",
            "riparian_areas": "riparian",
            "low_barrier_landcover": "lowbarrier",
            "open_water": "water",
            "high_barrier_landcover": "highbarrier",
        },
    },
    "enhancement": {
        "yaml_section": "enhancement_2070",
        "prefix": "enhance",
        "input_subdir": "wsi/enhancement",
        "benchmark_wsi": "wsi/enhancement/apnep-wsi-enhance.zip",
        "benchmark_highsuit": "wsi/enhancement/apnep-wsi-enhance-highsuit.zip",
        "highsuit_threshold": 3.5,
        "layer_map": {
            "potential_wetlands_2070": "wetlands",
            "riparian_areas_2070": "riparian",
            "low_barrier_landcover_2070": "lowbarrier",
            "open_water_2070": "water",
            "high_barrier_landcover_2070": "highbarrier",
        },
    },
}

# Layers shared across both scenarios (live in wsi/ root, not per-scenario subdir)
SHARED_LAYER_MAP = {
    "soil_drainage": "soildrainage",
    "slope": "slope",
    "soil_groundwater_hazards": "contaminated",
}


def resolve_layer_path(key, cfg, input_dir):
    """Build the zip path for a given YAML layer key."""
    prefix = cfg["prefix"]
    subdir = cfg["input_subdir"]

    if key in SHARED_LAYER_MAP:
        suffix = SHARED_LAYER_MAP[key]
        return Path(input_dir) / "wsi" / f"apnep-wsi-{suffix}.zip"
    elif key in cfg["layer_map"]:
        suffix = cfg["layer_map"][key]
        return Path(input_dir) / subdir / f"apnep-wsi-{prefix}-{suffix}.zip"
    else:
        raise ValueError(f"Unknown layer key: {key}")


def load_benchmark(benchmark_dir, rel_path):
    """Load a benchmark raster from the reference directory."""
    p = Path(benchmark_dir) / rel_path
    if not p.exists():
        return None, None, None
    data, profile = load_zipped_raster(p)
    return data, profile, profile.get("nodata")


def compute_benchmark_comparison(output, benchmark_data, benchmark_nodata, valid, step=0.25):
    """Compare output against phase 1 benchmark."""
    if benchmark_data is None:
        return {"note": "benchmark not available"}

    # Mask benchmark nodata — profile nodata value AND non-finite
    bmask = np.isfinite(benchmark_data) & valid
    if benchmark_nodata is not None:
        bmask &= ~np.isclose(benchmark_data, benchmark_nodata, rtol=0, atol=1e-30)
    omask = np.isfinite(output) & valid
    both = bmask & omask

    if both.sum() == 0:
        return {"note": "no overlapping valid pixels"}

    match_pct = float(np.sum(output[both] == benchmark_data[both]) / both.sum() * 100)

    out_dist = distribution_summary(output, omask, step=step)
    bmk_dist = distribution_summary(benchmark_data, bmask, step=step)

    return {
        "pixel_match_pct": round(match_pct, 2),
        "distribution_comparison": {
            "output": out_dist["distribution"],
            "phase1_benchmark": bmk_dist["distribution"],
        },
        "note": "informational only — phase 1 produced with unclear processing steps",
    }


def run_scenario(scenario, input_dir, benchmark_dir, output_dir, config_path, highsuit_threshold_override, focal_radius=None):
    cfg = SCENARIO_CONFIG[scenario]
    prefix = cfg["prefix"]

    # 1. Parse YAML weights
    with open(config_path, encoding="utf-8") as f:
        weight_cfg = yaml.safe_load(f)

    layers_yaml = weight_cfg["wsi"][cfg["yaml_section"]]["layers"]

    score_keys = []
    score_weights = []
    mask_keys = []
    for layer in layers_yaml:
        if layer["weight"] is not None:
            score_keys.append(layer["key"])
            score_weights.append(layer["weight"])
        else:
            mask_keys.append(layer["key"])

    total_weight = sum(score_weights)
    print(f"[{scenario}] Score layers: {score_keys}")
    print(f"[{scenario}] Weights: {score_weights} (sum={total_weight})")
    print(f"[{scenario}] Mask layers: {mask_keys}")

    # 2. Load all rasters
    all_keys = score_keys + mask_keys
    arrays = {}
    profiles = {}
    for key in all_keys:
        path = resolve_layer_path(key, cfg, input_dir)
        print(f"  Loading {key}: {path}")
        data, prof = load_zipped_raster(path)
        arrays[key] = data
        profiles[key] = prof

    # Load benchmark template for output profile
    bmark_wsi_data, bmark_wsi_prof, bmark_nodata = load_benchmark(benchmark_dir, cfg["benchmark_wsi"])
    template_prof = bmark_wsi_prof if bmark_wsi_prof is not None else profiles[all_keys[0]]
    print(f"  Template profile CRS={template_prof.get('crs')}, shape=({template_prof['height']},{template_prof['width']})")

    # 3. Guardrail validation
    validate_inputs(arrays, profiles)
    print(f"[{scenario}] Input validation passed")

    # Determine valid domain — intersection of all score layer valid masks
    nodata_val = template_prof.get("nodata", np.nan)
    first_key = score_keys[0]
    analysis_valid = valid_mask(arrays[first_key], profiles[first_key].get("nodata"))

    for key in score_keys[1:]:
        nd = profiles[key].get("nodata")
        analysis_valid &= valid_mask(arrays[key], nd)

    valid_count = analysis_valid.sum()
    total_count = analysis_valid.size
    print(f"[{scenario}] Analysis domain: {valid_count}/{total_count} valid pixels ({valid_count/total_count*100:.1f}%)")

    # 4. Build exclusion mask from mask layers
    mask_arrays = []
    for key in mask_keys:
        nd = profiles[key].get("nodata")
        v = valid_mask(arrays[key], nd)
        recoded = recode_binary(arrays[key].astype(np.float32), v, nodata_val=np.nan)
        mask_arrays.append(recoded)

    excluded = build_exclusion_mask(mask_arrays, analysis_valid)
    scored_valid = analysis_valid & (~excluded)
    print(f"[{scenario}] Excluded: {excluded.sum()} pixels, scored: {scored_valid.sum()} pixels")

    # 5. Weighted sum — score layers
    score_recoded = []
    for key in score_keys:
        nd = profiles[key].get("nodata")
        v = valid_mask(arrays[key], nd)
        recoded = recode_binary(arrays[key].astype(np.float32), v, nodata_val=np.nan)
        score_recoded.append(recoded)

    raw = weighted_sum(score_recoded, score_weights, analysis_valid, nodata_val=np.nan)
    raw_valid = np.isfinite(raw) & analysis_valid
    raw_on_valid = raw[raw_valid]
    print(f"[{scenario}] Raw weighted sum range: [{raw_on_valid.min():.4f}, {raw_on_valid.max():.4f}]")

    # 6. Quarter-step classification (no normalization)
    quarter = classify_quarter_step(raw, analysis_valid, fill_value=np.nan, step=0.25)

    # 7. Apply exclusion mask
    quarter = apply_mask(quarter, excluded, fill_value=np.nan)

    # 7.5 Optional focal smoothing
    smoothed = False
    pixels_changed = 0
    pre_smooth_hs_count = 0
    post_smooth_hs_count = 0
    if focal_radius is not None and focal_radius > 0:
        smoothed = True
        hs_thresh = cfg["highsuit_threshold"]
        if highsuit_threshold_override is not None:
            hs_thresh = highsuit_threshold_override
        pre_smooth_hs_count = int((quarter[scored_valid] >= hs_thresh).sum())
        quarter_smooth = focal_circular_mean(quarter, scored_valid, focal_radius)
        # Re-snap to quarter steps
        sv = np.isfinite(quarter_smooth)
        quarter_smooth[sv] = np.clip(np.round(quarter_smooth[sv] / 0.25) * 0.25, 0.0, 5.0)
        quarter_smooth[~scored_valid] = np.nan
        pixels_changed = int(np.sum(np.abs(quarter_smooth[scored_valid] - quarter[scored_valid]) > 1e-6))
        post_smooth_hs_count = int((quarter_smooth[scored_valid] >= hs_thresh).sum())
        quarter = quarter_smooth
        print(f"[{scenario}] Focal smooth r={focal_radius}px: {pixels_changed:,} pixels changed")

    # 8. HighSuit threshold
    hs_threshold = highsuit_threshold_override if highsuit_threshold_override is not None else cfg["highsuit_threshold"]
    hs = highsuit_threshold(quarter, hs_threshold, scored_valid, fill_value=np.nan)
    hs_coverage = np.nan_to_num(hs[scored_valid], nan=0).sum() / scored_valid.sum() * 100
    print(f"[{scenario}] HighSuit (threshold>={hs_threshold}): {hs_coverage:.1f}% of scored area")

    # 9. Export GeoTIFFs
    out_dir = Path(output_dir) / scenario
    out_dir.mkdir(parents=True, exist_ok=True)

    wsi_path = out_dir / f"apnep-wsi-{prefix}.tif"
    hs_path = out_dir / f"apnep-wsi-{prefix}-highsuit.tif"

    out_prof = dict(template_prof)
    out_prof.update(nodata=np.nan, dtype="float32")

    save_raster(wsi_path, quarter, out_prof)
    print(f"  Saved {wsi_path}")

    hs_prof = dict(template_prof)
    hs_prof.update(nodata=255, dtype="uint8")
    hs_out = np.where(np.isfinite(hs), hs, 255).astype(np.uint8)
    save_raster(hs_path, hs_out, hs_prof)
    print(f"  Saved {hs_path}")

    # 10. Generate metrics JSON
    quarter_valid = np.isfinite(quarter) & scored_valid

    input_metrics = {}
    for key in score_keys + mask_keys:
        nd = profiles[key].get("nodata")
        v = valid_mask(arrays[key], nd)
        vals = arrays[key][v].astype(np.float64)
        unique_sorted = sorted(set(np.round(vals, 4).tolist()))
        m = {
            "valid_pct": round(v.sum() / v.size * 100, 1),
            "dtype": str(arrays[key].dtype),
        }
        if len(unique_sorted) <= 10:
            m["unique"] = unique_sorted
        if key in mask_keys:
            pct_1 = float((vals == 1).sum() / len(vals) * 100)
            m["value_1_pct"] = round(pct_1, 2)
        input_metrics[key] = m

    # Per-layer mean contribution to weighted sum (on scored area only)
    layer_contributions = {}
    for key, w in zip(score_keys, score_weights):
        nd = profiles[key].get("nodata")
        v = valid_mask(arrays[key], nd) & scored_valid
        mean_score = float(np.nanmean(arrays[key].astype(np.float32)[v]))
        layer_contributions[key] = {
            "weight": w,
            "mean_score": round(mean_score, 4),
            "mean_contribution": round(mean_score * w, 4),
        }

    wsi_stats = distribution_summary(quarter, quarter_valid, step=0.25)
    benchmark_comparison = compute_benchmark_comparison(
        quarter, bmark_wsi_data, bmark_nodata, scored_valid, step=0.25
    )

    # Flat summary for dvc metrics show
    metrics = {
        "scenario": scenario,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mean": wsi_stats["mean"],
        "std": wsi_stats["std"],
        "effective_max": round(float(raw_on_valid.max()), 4),
        "highsuit_threshold": hs_threshold,
        "highsuit_coverage_pct": round(hs_coverage, 2),
        "scored_pixels": int(scored_valid.sum()),
        "phase1_pixel_match_pct": benchmark_comparison.get("pixel_match_pct"),
        "smoothed": smoothed,
        "focal_radius": focal_radius,
    }

    # Full details for programmatic access
    report = {
        "scenario": scenario,
        "timestamp": metrics["timestamp"],
        "weights": {k: w for k, w in zip(score_keys, score_weights)},
        "domain": {
            "total_pixels": int(total_count),
            "valid_pixels": int(valid_count),
            "excluded_pixels": int(excluded.sum()),
            "scored_pixels": int(scored_valid.sum()),
        },
        "inputs": input_metrics,
        "layer_contributions": layer_contributions,
        "smoothing": {
            "applied": smoothed,
            "focal_radius": focal_radius,
            "kernel_diameter_m": focal_radius * 2 * 30 if focal_radius else None,
            "pixels_changed": pixels_changed if smoothed else None,
            "highsuit_before": pre_smooth_hs_count if smoothed else None,
            "highsuit_after": post_smooth_hs_count if smoothed else None,
        },
        "output": {
            "wsi_quarter": wsi_stats,
            "highsuit": {
                "coverage_pct": round(hs_coverage, 2),
                "valid_pixels": int(scored_valid.sum()),
            },
        },
        "phase1_benchmark": benchmark_comparison,
    }

    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"  Saved {metrics_path}")

    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"  Saved {report_path}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Recreate WSI weighted overlay")
    parser.add_argument("--scenario", required=True, choices=["conservation", "enhancement"])
    parser.add_argument("--input-dir", default="data/inputs")
    parser.add_argument("--benchmark-dir", default="data/reference")
    parser.add_argument("--output-dir", default="data/outputs/wsi")
    parser.add_argument("--config", default="data/metadata/repro_weight.yaml")
    parser.add_argument("--highsuit-threshold", type=float, default=None)
    parser.add_argument("--focal-radius", type=int, default=None,
                        help="Apply circular focal mean with this radius (pixels) before highsuit thresholding")
    args = parser.parse_args()

    metrics = run_scenario(
        scenario=args.scenario,
        input_dir=args.input_dir,
        benchmark_dir=args.benchmark_dir,
        output_dir=args.output_dir,
        config_path=args.config,
        highsuit_threshold_override=args.highsuit_threshold,
        focal_radius=args.focal_radius,
    )

    print(f"\nDone. WSI quarter mean={metrics['mean']:.4f}")


if __name__ == "__main__":
    main()
