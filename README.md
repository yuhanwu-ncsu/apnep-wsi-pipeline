# APNEP WSI Pipeline

Reproducible Phase 1 Wetland Suitability Index (WSI) pipeline for the Albemarle-Pamlico National Estuary Partnership (APNEP) spatial targeting project. Extracted from the internal `apnep-spatial-targeting` repository.

Environment management via [Pixi](https://pixi.prefix.dev/), data versioning via [DVC](https://dvc.org/).

## Repository structure

| Path | Purpose |
|---|---|
| `dvc.yaml` / `dvc.lock` | Pipeline stage definitions and locked outputs |
| `pixi.toml` / `pixi.lock` | Environments: `default` (Python + DVC) and `processing` (full spatial stack) |
| `scripts/reproducibility/` | Core pipeline: recreate WSI, combine scenarios, opportunity areas |
| `scripts/agol/` | Build multiband rasters for ArcGIS Online popups |
| `scripts/metadata/` | Generate ISO metadata `.tif.xml` sidecars |
| `src/` | Reusable engine: spatial utils, I/O, grid ops |
| `notebooks/arcpy/` | Record of how slope (DEM) and soil drainage (SSURGO) input layers were derived; requires ArcGIS Pro (not part of the pixi/DVC pipeline) |
| `data/metadata/` | Configs for reproduction weights and ISO metadata |
| `data/*.dvc` | DVC pointers to inputs, raw, and reference archives |

## Quick start

[Install Pixi](https://pixi.sh/latest/#installation) first. The `processing` environment is ~2.3 GB (full spatial stack); the `default` environment is ~600 MB (Python + DVC only, enough for pulling data).

```bash
# 1. Install the environment
pixi install -e processing

# 2. Configure DVC credentials (private Google Shared Drive)
#    Place the service account key at .secrets/dvc_key.json, then:
pixi run -e processing dvc remote modify --local myremote gdrive_use_service_account true
pixi run -e processing dvc remote modify --local myremote gdrive_service_account_json_file_path .secrets/dvc_key.json

# 3. Pull pipeline inputs and reference benchmarks (both required)
pixi run -e processing dvc pull data/inputs.dvc data/reference.dvc

#    Optional: frozen raw archives from the previous phase
pixi run -e processing dvc pull data/raw.dvc

# 4. Run the pipeline
pixi run -e processing reproduce
```

## Pipeline

| Stage | Output |
|---|---|
| `wsi-conservation` | Conservation WSI + high-suitability rasters |
| `wsi-enhancement` | Enhancement WSI + high-suitability rasters |
| `wsi-combine` | Combined high-suitability raster |
| `opportunity` | Opportunity areas (CRPA intersection, PADUS-masked) |
| `agol-multiband` | Multiband raster + county map for ArcGIS Online |
| `metadata` | ISO metadata sidecars for all outputs |

## Data versioning (DVC)

Git tracks only code, configs, and lightweight `.dvc` pointers; all spatial data lives on a Google Shared Drive. You need a service account key from the repo owner to access it.

| Directory | What's there | Tracked by |
|---|---|---|
| `data/inputs/` | Active pipeline inputs | `data/inputs.dvc` |
| `data/raw/` | Previous-phase inputs (frozen) | `data/raw.dvc` |
| `data/reference/` | Previous-phase outputs used as validation benchmark | `data/reference.dvc` |
| `data/outputs/` | Pipeline results | `dvc.yaml` stages |
| `data/interim/`, `data/tmp/` | Scratch space | Git-ignored |

Everyday commands:

```bash
pixi run -e processing dvc data status            # are pulled files up to date?
pixi run -e processing dvc status                 # pipeline stage status
pixi run -e processing dvc pull data/inputs.dvc data/reference.dvc   # fetch inputs + reference benchmarks
pixi run -e processing dvc push                   # upload new outputs after dvc repro
```

The remote authenticates with a Google service account. Place the key at `.secrets/dvc_key.json` and run the `dvc remote modify --local` commands from Quick start; both the key and `.dvc/config.local` are gitignored.

The reference benchmark is frozen by design. If the pipeline is deliberately revised and the new outputs are validated, promote them to `data/reference/` with `dvc add` and re-run `dvc repro` to re-establish the comparison.

## License

Code and documentation: Creative Commons Attribution 4.0 International (CC BY 4.0), matching the Zenodo deliverables. See `LICENSE`.

## Data availability

Phase 1 deliverables (the pipeline **outputs**) are archived on Zenodo:
<https://doi.org/10.5281/zenodo.21075002>

If you only need the results, download them from Zenodo; no credentials required. Pipeline inputs, raw, and reference archives live on the Google Shared Drive above and are available on request.
