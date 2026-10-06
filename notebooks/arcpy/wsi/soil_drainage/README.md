# Soil Layer Reproduction Notes

The soil drainage layer is reproduced from the SSURGO database via an SQLite portal, then recoded into suitability scores for the WSI weighted overlay pipeline.

## SSURGO guide & links
**Tutorial**:  
[SSURGO Soil Survey Data Youtube Guide](https://www.youtube.com/watch?v=4FGuxqxbCG0)  

**SSURGO Soil Survey Data Portal**:  
[SSURGO Soil Survey Data Portal Main Site](https://www.nrcs.usda.gov/resources/data-and-reports/ssurgo-portal)  
[SSURGO Soil Survey Data Portal User Guide](https://www.nrcs.usda.gov/sites/default/files/2024-11/SSURGO-Portal-User-Guide.pdf)

**SSURGO Soil Survey Data Bulk Downloader (ArcGIS Pro Toolbox)**:  
[SSURGO Soil Survey Data Bulk Downloader Guide](https://www.nrcs.usda.gov/sites/default/files/2023-09/SSURGO-Bulk-Downloader-ArcGIS-Pro-Installation-and-User-Guide.pdf)  
[SSURGO Soil Survey Data Bulk Downloader Download Link](https://www.nrcs.usda.gov/sites/default/files/2023-09/SSURGO-Bulk-Downloader-ArcGIS-Pro.zip)

## Data acquisition
Steps below can be treated as companions to the `SSURGO Bulk Downloader` and the `SSURGO Portal` guides and tutorials, whether pdf version or the youtube demo

1. Using `SSURGO Bulk Downloader` to get NC + VA Soil data into a local folder with ArcGIS Pro, [`SSURGO Bulk Downloader`](https://www.nrcs.usda.gov/sites/default/files/2023-09/SSURGO-Bulk-Downloader-ArcGIS-Pro.zip) is a ArcGIS Pro tool (also has a version for QGIS), the correct params for getting all NC/VA counties is `'NC*,VA*'`
2. Follow the guide to install and set up the `SSURGO Data Portal` on your machine and then create a database through the launched SSURGO Portal using the option of `sqlite` database in the drop down. (Note: geopackage version is not tested here and the [notebook](./ssurgo_soil_processing.ipynb) for processing afterwards are only compactible with sqlite database working with ArcGIS Pro at thie point)
3. Point the data folder to the working folder of step 1 to allow the portal to import the data (208 in total). 
4. After step 3, a `muraster_10m.tif` which would be automatically generated if following the tutorial of the portal, which is a map unit raster file for the region. The value of 'mukey' is a unique value for joining different category of soil rating data for downstream analysis.
5. On the SSURGO Portal, navigate to the SSURGO Data in Database Page, select all and then go to Soil Data Viewer tab of the portal, and search by `Drainage Class`. The dataset in this analysis used the option of `Dominant Condition`, which is the default aggregation method on the Portal. When you select it and click on 'Generate rating', a sqlite table `rating_DrainClass_DCD` would be generated

## Data dictionary
For the Drainage Class table, it does not have any kind of ranking for the `string` based decriptions, the following dictionary was used during the analysis process.
```
drainage_dict = {
    "Excessively drained": 1,
    "Somewhat excessively drained": 2,
    "Well drained": 3,
    "Moderately well drained": 4,
    "Somewhat poorly drained": 5,
    "Poorly drained": 6,
    "Very poorly drained": 7,
    "Subaqueous": 8
}
```

## Noteboook reproduction notes

1. There is a `base_directory` hard coded into the notebook for working with arcpy inside ArcGIS Pro pointing to the project folder root.  
2. There is a `raw_raster` and a `sqlite_db_path` associated with previous steps on interacting with
These need to be changed if reproducing using the [notebook](./ssurgo_soil_processing.ipynb)

## Flowchart exaplaining updated workflow inside the notebook
```mermaid
flowchart TD
    %% Define external styling classes
    classDef input fill:#eceff1,stroke:#607d8b,stroke-width:2px,color:#263238
    classDef process1 fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px,color:#4a148c
    classDef process2 fill:#e0f7fa,stroke:#00acc1,stroke-width:2px,color:#006064
    classDef process3 fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1
    classDef process4 fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef process5 fill:#fce4ec,stroke:#c62828,stroke-width:2px,color:#b71c1c
    classDef output fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100

    subgraph Inputs ["Data Inputs"]
        SQL["SQLite Database<br>(rating_DrainClass_DCD<br>text drainage classes)"]:::input
        MUR["muraster_10m.tif<br>(pixels = mukey · Albers CRS)"]:::input
        TPL["WSI Template<br>(apnep-wsi-conserve-wetlands.tif)"]:::input
    end

    subgraph Step1 ["Phase 1: Text-to-Integer Mapping"]
        Q1["Query SQLite<br>Extract mukey + DrainClass_DCD<br>into pandas DataFrame"]:::process1
        MAP["pandas .map() Drainage_Rank<br>1=Excessively<br>2=Somewhat excessively<br>3=Well<br>4=Moderately well<br>5=Somewhat poorly<br>6=Poorly<br>7=Very poorly<br>8=Subaqueous"]:::process1
        CSV_OUT[("Cached CSV → scratch GDB")]:::output
    end

    subgraph Step2 ["Phase 2: Join + Bake Raster"]
        J1["AddJoin<br>(raster mukey ↔ table mukey)"]:::process2
        L1["Lookup<br>field = Drainage_Rank"]:::process2
        BAKE_OUT[("Baked_Drainage_10m.tif<br>S8 · NoData=15 · Albers CRS")]:::output
    end

    subgraph Step3 ["Phase 3: Project to Target CRS"]
        PR1["ProjectRaster<br>CRS → 32119 · cellSize=10<br>NEAREST (categorical)"]:::process3
        PROJ_OUT[("Proj_Drainage_10m.tif<br>S8 · NoData=15")]:::output
    end

    subgraph Step4 ["Phase 4: Resample & Mask (Template Snapping)"]
        E1["Lock Global Environments<br>Snap, CellSize, CRS, Extent, Mask<br>locked to WSI Template"]:::process4
        RES1["Resample → 30m<br>MAJORITY (categorical)"]:::process4
        EX1["ExtractByMask<br>Mask: WSI Template"]:::process4
        RAT["BuildRAT + AddField<br>DrainClass text labels"]:::process4
        FINAL_OUT[("APNEP_Drainage_30m.tif<br>S8 · 11378 × 9812")]:::output
    end

    subgraph Step5 ["Phase 5: Suitability Recode"]
        RC1["Lookup WSI_Score + SetNull<br>1-3 → 0.0<br>4-5 → 0.5<br>6-7 → 1.0<br>8 → NoData"]:::process5
        WSI_OUT[("apnep-wsi-soildrainage.tif<br>F32 · {0.0, 0.5, 1.0}")]:::output
    end

    %% Flow logic
    SQL --> Q1
    Q1 --> MAP
    MAP --> CSV_OUT
    CSV_OUT --> J1
    MUR --> J1
    J1 --> L1
    L1 --> BAKE_OUT

    BAKE_OUT --> PR1
    PR1 --> PROJ_OUT

    TPL -. "Guides Environments" .-> E1
    PROJ_OUT --> E1
    E1 --> RES1
    RES1 --> EX1
    EX1 --> RAT
    RAT --> FINAL_OUT

    FINAL_OUT --> RC1
    RC1 --> WSI_OUT
```
