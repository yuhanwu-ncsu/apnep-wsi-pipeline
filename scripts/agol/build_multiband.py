"""Build the 3-band multiband GeoTIFF for AGOL from current WSI output rasters.

Reads the latest conservation and enhancement WSI rasters from data/outputs/,
rasterizes county GEOIDs from Census TIGER, masks to the APNEP boundary, and
writes a single GeoTIFF with band descriptions.

Output:  data/outputs/agol/multiband_wsi_county.tif
        data/outputs/agol/county_map.json  (GEOID int -> county label)

Usage:
  python scripts/agol/build_multiband.py
"""

from __future__ import annotations

import json
import urllib.request
import zipfile
from pathlib import Path
from typing import Tuple

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "outputs"
RAW = REPO / "data" / "raw"
TMP = REPO / "data" / "tmp"

CON_TIF = DATA / "wsi" / "conservation" / "apnep-wsi-conserve.tif"
ENH_TIF = DATA / "wsi" / "enhancement" / "apnep-wsi-enhance.tif"
BND_ZIP = RAW / "boundaries" / "apnep-bnd-boundary.zip"

OUT_DIR = REPO / "data" / "outputs" / "agol"
OUT_TIF = OUT_DIR / "multiband_wsi_county.tif"
COUNTY_MAP_JSON = OUT_DIR / "county_map.json"

COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
COUNTY_CACHE = TMP / "boundaries" / "cb_2024_us_county_500k.zip"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _first_inner(zip_path: Path, suffixes: Tuple[str, ...]) -> str:
    with zipfile.ZipFile(zip_path, "r") as z:
        candidates = []
        for name in z.namelist():
            if not name.lower().endswith(suffixes):
                continue
            norm = name.replace("\\", "/")
            if "__MACOSX" in norm or Path(name).name.startswith("._"):
                continue
            candidates.append(name)
        if not candidates:
            raise FileNotFoundError(f"No usable {suffixes} in {zip_path}")
        return sorted(candidates)[0]


def _open_zip_shp(zip_path: Path) -> gpd.GeoDataFrame:
    inner = _first_inner(zip_path, (".shp",))
    return gpd.read_file(f"zip://{zip_path.resolve().as_posix()}!{inner}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # 1. Read current WSI rasters
    with rasterio.open(CON_TIF) as src:
        con = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        nodata_con = src.nodata
        height, width = src.height, src.width
        transform = src.transform
        crs = src.crs
    print(f"Read conservation: {CON_TIF}")

    with rasterio.open(ENH_TIF) as src:
        enh = src.read(1).astype(np.float32)
        nodata_enh = src.nodata
        prof_enh = src.profile.copy()

    # Align enhancement to conservation grid if needed
    if (
        prof_enh["transform"] != profile["transform"]
        or prof_enh["height"] != height
        or prof_enh["width"] != width
    ):
        print("Reprojecting enhancement to conservation grid …")
        aligned = np.empty((height, width), dtype=np.float32)
        reproject(
            source=enh, destination=aligned,
            src_transform=prof_enh["transform"], src_crs=prof_enh["crs"],
            dst_transform=transform, dst_crs=crs,
            resampling=Resampling.bilinear,
        )
        enh = aligned

    print(f"Grid: {width} x {height} | CRS: {crs}")

    # 2. County GEOID band
    if not COUNTY_CACHE.exists():
        COUNTY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        print("Downloading TIGER counties …")
        urllib.request.urlretrieve(COUNTY_URL, COUNTY_CACHE)

    bnd = _open_zip_shp(BND_ZIP)
    counties = _open_zip_shp(COUNTY_CACHE)
    clipped = gpd.clip(counties, bnd.to_crs(counties.crs)).to_crs(crs)

    shapes = [
        (geom, int(g))
        for geom, g in zip(clipped.geometry, clipped["GEOID"].astype(str))
        if geom is not None and not geom.is_empty
    ]
    fips = rasterize(shapes, out_shape=(height, width), transform=transform,
                     fill=0, dtype=np.uint32).astype(np.float32)
    print(f"Rasterized {len(shapes)} counties")

    # 3. APNEP boundary mask
    boundary = unary_union(bnd.to_crs(crs).geometry)
    mask = rasterize([(boundary, 1)], out_shape=(height, width),
                     transform=transform, fill=0, dtype=np.uint8)
    inside = mask == 1

    def _mask(arr, nd):
        out = arr.copy()
        if nd is not None:
            out[~inside] = np.float32(nd)
        else:
            out[~inside] = np.nan
        return out

    con_out = _mask(con, nodata_con)
    enh_out = _mask(enh, nodata_enh)
    fips_out = np.where(inside, fips, 0.0).astype(np.float32)

    # 4. Write multiband
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_profile = profile.copy()
    out_profile.update(count=3, dtype=rasterio.float32, compress="deflate",
                       tiled=True, blockxsize=256, blockysize=256)
    out_profile.pop("nodata", None)

    with rasterio.open(OUT_TIF, "w", **out_profile) as dst:
        dst.write(con_out, 1)
        dst.write(enh_out, 2)
        dst.write(fips_out, 3)
        dst.set_band_description(1, "conservation_wsi")
        dst.set_band_description(2, "enhancement_wsi")
        dst.set_band_description(3, "county_geoid_int")

    print(f"Wrote: {OUT_TIF.resolve()}")

    # 5. County lookup for AGOL popup config
    def _label(row):
        return f"{row.get('NAME', '')}, {row.get('STUSPS', '')}".strip(", ")

    co = clipped.drop_duplicates(subset=["GEOID"]).copy()
    county_map = {int(r["GEOID"]): _label(r) for _, r in co.iterrows()}

    COUNTY_MAP_JSON.write_text(json.dumps(county_map, indent=2), encoding="utf-8")
    print(f"Wrote county map: {COUNTY_MAP_JSON}  ({len(county_map)} entries)")


if __name__ == "__main__":
    main()
