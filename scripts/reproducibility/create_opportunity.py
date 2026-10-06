"""Create opportunity areas from combined WSI and CRPA.

Formula (validated against phase 1 reference):
  opportunity = (CRPA == 4) * (conserve_highsuit + 2 * enhance_highsuit)

Then PADUS-protected areas set to NoData (15).

Encoding:
  0  = no opportunity
  1  = conservation opportunity only
  2  = enhancement opportunity only
  3  = both conservation and enhancement
  15 = PADUS protected (excluded)

Usage:
    python scripts/reproducibility/create_opportunity.py
    python scripts/reproducibility/create_opportunity.py --crpa data/inputs/crpa/apnep-crpa.zip
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

from utils.grid import align_categorical_to_grid
from utils.io import load_zipped_raster, save_raster


def main(con_path, enh_path, crpa_path, padus_path, output_dir):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load highsuit layers (on-disk GeoTIFFs from upstream DVC stages)
    with rasterio.open(con_path) as src:
        con = src.read(1)
        dst_prof = dict(src.profile)

    with rasterio.open(enh_path) as src:
        enh = src.read(1)

    # Load and align CRPA (zipped, categorical uint8)
    crpa_data, crpa_prof = load_zipped_raster(crpa_path)
    crpa = align_categorical_to_grid(crpa_data, crpa_prof, dst_prof)
    print(f"CRPA classes: {dict(zip(*np.unique(crpa, return_counts=True)))}")

    # Load and align PADUS (zipped, categorical)
    padus_data, padus_prof = load_zipped_raster(padus_path)
    padus = align_categorical_to_grid(padus_data, padus_prof, dst_prof)

    # Valid domain
    valid = (con != 255) & (enh != 255) & (crpa != 255)
    print(f"Conservation highsuit valid: {int((con != 255).sum()):,}")
    print(f"Enhancement highsuit valid:  {int((enh != 255).sum()):,}")
    print(f"CRPA valid (not 255):        {int((crpa != 255).sum()):,}")
    print(f"Intersection:                {int(valid.sum()):,}")

    # Apply formula
    opportunity = np.full(con.shape, 15, dtype=np.uint8)
    crpa_300m = (crpa == 4)
    opportunity[valid] = (
        crpa_300m[valid].astype(np.uint8) *
        (con[valid] + 2 * enh[valid])
    ).astype(np.uint8)

    # Apply PADUS mask
    padus_excluded = (padus == 1)
    opportunity[padus_excluded & valid] = 15

    labels = {0: "no opportunity", 1: "conservation only",
              2: "enhancement only", 3: "both", 15: "PADUS protected"}
    for val in [0, 1, 2, 3, 15]:
        count = int((opportunity == val).sum())
        print(f"  {val:>2} ({labels[val]}): {count:,}")

    out_path = out_dir / "apnep-oppareas-padusmask.tif"
    out_prof = dict(dst_prof)
    out_prof.update(dtype="uint8", nodata=15)
    save_raster(out_path, opportunity, out_prof)
    print(f"Saved {out_path}")

    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "crpa_class": "4 (300m buffer)",
        "opportunity_pixels": {
            "0_no_opportunity": int((opportunity == 0).sum()),
            "1_conservation_only": int((opportunity == 1).sum()),
            "2_enhancement_only": int((opportunity == 2).sum()),
            "3_both": int((opportunity == 3).sum()),
            "15_padus_excluded": int((opportunity == 15).sum()),
        },
    }
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"Saved {metrics_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create opportunity areas from WSI highsuit and CRPA")
    parser.add_argument("--con-highsuit", default="data/outputs/wsi/conservation/apnep-wsi-conserve-highsuit.tif")
    parser.add_argument("--enh-highsuit", default="data/outputs/wsi/enhancement/apnep-wsi-enhance-highsuit.tif")
    parser.add_argument("--crpa", default="data/inputs/crpa/apnep-crpa.zip")
    parser.add_argument("--padus", default="data/inputs/apnep-padusmask.zip")
    parser.add_argument("--output-dir", default="data/outputs/opportunity")
    args = parser.parse_args()
    main(args.con_highsuit, args.enh_highsuit, args.crpa, args.padus, args.output_dir)
