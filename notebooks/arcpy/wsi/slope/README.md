# Slope Layer Reproduction Notes

The slope layer is reproduced based on the OT_DEM, and NOAA_DEM found on Google Drive, then recoded into suitability scores for the WSI weighted overlay pipeline.

## Google Drive Links
| DEM Dataset | Resolution | Size | Number of Tiles |
|---| --- | --- | --- |
| [OT_DEM](https://drive.google.com/drive/u/0/folders/1UJuQzCXPm8aik8p9CTX4G69a0mKdDqHt)    | 10m   | 5.8 GB    | 4                 |
| [NOAA_DEM](https://drive.google.com/drive/u/0/folders/1pKhIaJjP1_jGNthvixPkGcBqfFxvtCno)  | 3m    | 14.4 GB   | 5                 |

## Raw Data Sources
> **Citation**:
>> 1. Department of Commerce (DOC), National Oceanic and Atmospheric Administration (NOAA), National Ocean Service (NOS), Office for Coastal Management (OCM). (2026). NOAA Office for Coastal Management Coastal Inundation Digital Elevation Model. Charleston, SC: NOAA's Ocean Service, OCM. Available online: https://coast.noaa.gov/slrdata/DEMs/index.html  
>> 2. United States Geological Survey (2021). United States Geological Survey 3D Elevation Program 1/3 arc-second Digital Elevation Model. Distributed by OpenTopography. https://doi.org/10.5069/G98K778D

Drafted update of the NOAA DEM is based on their [metadata](https://coast.noaa.gov/slrdata/DEMs/NC/NC_Middle1_metadata.xml) files, check file linked here for an example.

## Scripts used to generate the updated version of slope layer
Check [slope notebook](./dem_processing.ipynb)  
Also see the flow chart to get a visual representation of the overall process

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
        OT["OT_DEM Folder<br>(USGS 10m)"]:::input
        NOAA["NOAA_DEM Folder<br>(NOAA 3m)"]:::input
        TPL["WSI Template<br>(apnep-wsi-conserve-wetlands.tif)"]:::input
    end

    subgraph Step1 ["Phase 1: Project & Align (Internal Snapping)"]
        P1["Project 1st OT Tile<br>(Bilinear, 10m)<br>Set as arcpy.env.snapRaster"]:::process1
        P2["Project Remaining OT Tiles<br>(Bilinear, 10m)"]:::process1
        P3["Project NOAA Tiles<br>(Bilinear, 10m)"]:::process1
    end

    subgraph Step2 ["Phase 2: Mosaic to Continuous DEM"]
        M1["MosaicToNewRaster<br>Method: BLEND<br>Type: 32_BIT_FLOAT"]:::process2
        DEM_OUT[("Seamless_DEM_32119_10m.tif")]:::output
    end

    subgraph Step3 ["Phase 3: Topographic Analysis"]
        S1["Calculate Slope<br>Method: PLANAR<br>Units: DEGREE<br>Z-Factor: 1"]:::process3
        SLOPE_OUT[("Project_Slope_10m.tif")]:::output
    end

    subgraph Step4 ["Phase 4: Resample & Mask (Template Snapping)"]
        E1["Lock Global Environments<br>Snap, CellSize, CRS, Extent, Mask<br>locked to WSI Template"]:::process4
        RES1["Resample (In-Memory)<br>Type: Bilinear<br>Cell Size: 30m"]:::process4
        EX1["ExtractByMask<br>Mask: WSI Template<br>Crops irregular boundary"]:::process4
        FINAL_OUT[("Project_Slope_30m.tif<br>(11378 x 9812)")]:::output
    end

    subgraph Step5 ["Phase 5: Suitability Recode"]
        RC1["Con (Nested Conditional)<br>≤1°→1.0<br>≤2°→0.75<br>≤3°→0.5<br>≤5°→0.25<br>>5°→0.0"]:::process5
        WSI_OUT[("apnep-wsi-slope.tif<br>F64 · {0.0, 0.25, 0.5, 0.75, 1.0}")]:::output
    end

    %% Flow logic
    OT --> P1
    P1 -. "Locks Grid For" .-> P2 & P3
    OT --> P2
    NOAA --> P3
    
    P1 --> M1
    P2 --> M1
    P3 --> M1
    M1 --> DEM_OUT
    
    DEM_OUT --> S1
    S1 --> SLOPE_OUT
    
    TPL -. "Guides Environments" .-> E1
    SLOPE_OUT --> E1
    E1 --> RES1
    RES1 --> EX1
    EX1 --> FINAL_OUT

    FINAL_OUT --> RC1
    RC1 --> WSI_OUT
```