# Weight Metadata for Reproducibility

Table 1. Biophysical and built environmental data sources for input variables used in the Conservation WSI and source information for the inventories of current existing wetlands. Where 1 contributes positively to suitability and -1 is masked.

| Variable | Description | Conserve Score (2024) | Weight | Source |
| :--- | :--- | :---: | :---: | :--- |
| **Existing Wetlands** | Represents stable, high-functioning wetland systems that anchor hydrologic and ecological processes. | 1 | 2 | (USGS, 2024) |
| **Riparian Areas** | Buffer around existing wetlands, providing necessary water flow and connectivity for wetland ecosystems. | 1 | 2 | 50m buffer from Existing Wetlands (constructed by authors) |
| **Open Water** | Permanently inundated areas such as lakes and ponds are excluded because they do not provide conservation opportunity. | 1 | – | (USGS, 2024) |
| **Low Barrier Landcover** | Forests, shrublands, and grasslands (Natural Areas) offering minimal resistance to wetland conservation and hydrologic connectivity. | 1 | 1 | (USGS, 2024) |
| **High Barrier Landcover** | Intensively developed or impervious surfaces (Developed & Cultivated) that disrupt natural hydrology and constrain conservation potential. | 1 | – | (USGS, 2024) |
| **Soil-Groundwater Hazards** | Polluted areas excluded to avoid ecological and community health risks during conservation planning. | -1 | – | (US EPA, n.d.) |
| **Soil Drainage** | Poorly or somewhat poorly drained soils support wetland persistence; excessively drained soils excluded. | 1 | 1 | (Soil Survey Staff, 2025) |
| **Slope** | Gentle slopes (< 5°) favor water retention and hydrologic stability for existing wetlands. | 1 | 1 | (NOAA, 2014; USGS, 2021) |

---

Table 2. Biophysical and built environmental data sources for input variables used in the Enhancement WSI and source information for the inventories of current existing wetlands. Where 1 contributes positively to suitability and -1 is masked.

| Variable | Description | Enhancement Score (2070) | Weight | Source |
| :--- | :--- | :---: | :---: | :--- |
| **Potential Wetlands - 2070** | Current wetlands, areas prioritized for conservation and proximity to remnant systems. | 1 | 2 | Sohl et al., 2018 |
| **Riparian Areas - 2070** | 50-meter buffer around existing wetlands, providing necessary water flow and connectivity for wetland ecosystems. | 1 | 2 | 50m buffer from Potential Wetlands (constructed by authors) |
| **Open Water - 2070** | Permanent open water areas are excluded since they lack restoration feasibility and are already inundated. | 1 | – | Sohl et al., 2018 |
| **Low Barrier Landcover - 2070** | Areas of natural landscapes that provide minimal resistance to restoration (e.g., forests, shrublands, and other vegetated cover). | 1 | 1 | Sohl et al., 2018 |
| **High Barrier Landcover - 2070** | Areas of high-intensity developed infrastructure, which pose significant challenges to wetland restoration (e.g., buildings and impervious surfaces). | -1 | – | Sohl et al., 2018 |
| **Soil-Groundwater Hazards** | Areas polluted by hazardous substances, used as constraints or exclusions to avoid prioritizing contaminated areas. | -1 | – | (US EPA, n.d.) |
| **Soil Drainage** | Poorly drained soils enhance hydrologic retention and restoration viability. | 1 | 1 | (Soil Survey Staff, 2025) |
| **Slope** | Gentle slopes (0–5°) promote water retention; steep slopes (> 5°) excluded due to poor restoration potential. | 1 | 1 | (NOAA, 2014; USGS, 2021) |

---

Table 3. Recoded data and suitability classifications for land use, contamination, protected areas, slope, and soil drainage. Suitability values are standardized from 0 to 1 to enable consistent integration within the weighted overlay framework.

| Variable | Category / Range | Recode Value | Rationale |
| :--- | :--- | :---: | :--- |
| **Land Use / Land Cover** | Presence of natural or undeveloped land | 1.0 | Indicates open or natural landscapes suitable for wetland conservation or enhancement. |
| | Absence (developed / cultivated) | 0 | Developed or cultivated land unsuitable for wetland feasibility. |
| **Contaminated Land** | Presence | 1.0 | Identifies areas with documented contamination to ensure proper exclusion and monitoring. |
| | Absence | 0 | No contamination; suitable for inclusion in suitability analysis. |
| **Protected Areas** | Presence | 1.0 | Lands permanently protected and managed primarily for biodiversity conservation. Excluded from opportunity-area targeting. |
| | Absence | 0 | Unprotected landscapes eligible for new conservation or enhancement investments. |
| **Slope (degrees)** | 0–1 | 1.00 | Very flat terrain with stable hydrology; ideal for wetland formation, persistence, and surface-water retention. |
| | 1–2 | 0.75 | Gently sloping areas that retain water but drain slightly faster; good enhancement potential. |
| | 2–3 | 0.50 | Moderately sloped ground with some runoff; limited but possible enhancement feasibility. |
| | 3–5 | 0.25 | Steeper terrain with faster drainage; less suitable for long-term hydrologic retention. |
| | >5 | 0 | Too steep for wetland development; high runoff and erosion risk. |
| **Soil Drainage Class** | Very poorly drained | 1.00 | Hydric soils with sustained saturation; ideal wetland conditions. |
| | Poorly drained | 1.00 | High water table and persistent moisture; excellent for wetland persistence. |
| | Somewhat poorly drained | 0.50 | Moderately wet soils with transitional potential for wetland establishment. |
| | Moderately well drained | 0.50 | Retains limited moisture; borderline feasibility for enhancement. |
| | Well / Somewhat excessively / Excessively drained | 0 | Too dry; unsuitable for wetland hydrology. |