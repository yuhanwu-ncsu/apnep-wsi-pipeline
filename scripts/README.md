# Scripts

## Phase 1

### Metadata generation

`scripts/metadata/generate_iso_metadata.py` writes ArcGIS-flattened metadata into
`.tif.xml` sidecars that ArcGIS Pro reads automatically. It pulls from
`data/metadata/iso_metadata_config.yaml`.

```bash
# .tif.xml sidecars next to each raster in data/outputs/
python scripts/metadata/generate_iso_metadata.py

# Collect standalone XML into a folder (for AGOL metadata import)
python scripts/metadata/generate_iso_metadata.py --outdir data/phase1_agol_metadata
```

With pixi: `pixi run -e processing python scripts/metadata/generate_iso_metadata.py`

### Reproducibility

These rebuild the core Phase 1 outputs from weighted overlay parameters:

- `scripts/reproducibility/recreate_wsi.py`  -  runs the full WSI pipeline
- `scripts/reproducibility/combine_wsi.py`  -  overlays conservation and enhancement high-suitability rasters
- `scripts/reproducibility/create_opportunity.py`  -  intersects high-suitability areas with CRPA buffers and masks out PADUS

### Other directories

- `agol/`  -  build multiband rasters for ArcGIS Online popup configurations
