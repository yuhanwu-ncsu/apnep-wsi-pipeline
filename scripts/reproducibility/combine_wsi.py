"""Combine conservation and enhancement HighSuit into a single WSI layer.

Encoding:
  0 = neither
  1 = conservation HighSuit only
  2 = enhancement HighSuit only
  3 = both conservation and enhancement HighSuit

Usage:
    python scripts/reproducibility/combine_wsi.py
    python scripts/reproducibility/combine_wsi.py --output-dir data/outputs/wsi
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

from utils.io import save_raster


def main(con_path, enh_path, output_dir):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(con_path) as src:
        con = src.read(1)
        profile = dict(src.profile)

    with rasterio.open(enh_path) as src:
        enh = src.read(1)

    valid = (con != 255) & (enh != 255)
    print(f"Conservation valid: {(con != 255).sum():,}")
    print(f"Enhancement valid:  {(enh != 255).sum():,}")
    print(f"Intersection:       {valid.sum():,}")

    combined = np.full(con.shape, 255, dtype=np.uint8)
    combined[valid] = (con[valid].astype(np.uint8) + 2 * enh[valid].astype(np.uint8))

    for val in [0, 1, 2, 3]:
        count = int((combined[valid] == val).sum())
        label = {0: "neither", 1: "conservation only", 2: "enhancement only", 3: "both"}[val]
        print(f"  {val} ({label}): {count:,}")

    out_path = out_dir / "apnep-wsi-combine.tif"
    profile.update(dtype="uint8", nodata=255)
    save_raster(out_path, combined, profile)
    print(f"Saved {out_path}")

    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conservation_valid": int((con != 255).sum()),
        "enhancement_valid": int((enh != 255).sum()),
        "intersection_valid": int(valid.sum()),
        "classes": {
            "0_neither": int((combined[valid] == 0).sum()),
            "1_conservation_only": int((combined[valid] == 1).sum()),
            "2_enhancement_only": int((combined[valid] == 2).sum()),
            "3_both": int((combined[valid] == 3).sum()),
        },
    }
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"Saved {metrics_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine conservation and enhancement HighSuit layers")
    parser.add_argument("--con-highsuit", default="data/outputs/wsi/conservation/apnep-wsi-conserve-highsuit.tif")
    parser.add_argument("--enh-highsuit", default="data/outputs/wsi/enhancement/apnep-wsi-enhance-highsuit.tif")
    parser.add_argument("--output-dir", default="data/outputs/wsi/combined")
    args = parser.parse_args()
    main(args.con_highsuit, args.enh_highsuit, args.output_dir)
