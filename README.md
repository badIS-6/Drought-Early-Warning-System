# Drought Early Warning System

## 1. Overview
This project implements the **data-processing and analytical backend** of a Tunisia-focused **Drought Early Warning System** and **Drought Risk & Impact Assessment**.

Demo link: https://badis-6.github.io/Drought-Early-Warning-System/


# 2. Project Context




# 3. Main Technologies
* Google Earth Engine
* Python




# 4. Input Data

## Environmental Dataset
The main input is:

```text
tunisia_drought_monthly.csv
```



# 5. Governorate Boundaries

```text
tunisia_governorates.geojson
```

The GeoJSON is used to generate:

```text
governorates_latest.geojson
```


# 6. Exposure Data

```text
exposure.csv
```

Exposure represents **what is located in an area that can be affected by drought**.

* Population
* Agricultural land
* Livestock
* Irrigated areas
* Water-demanding sectors



# 7. Vulnerability Data

```text
vulnerability.csv
```


# 8. GEE Processing
The script generates a monthly governorate-level environmental dataset.

### Meteorological variables
```text
rainfall_mm
temperature_c
PET
```

### Vegetation variables
```text
NDVI
NDVI anomaly
VCI
```

### Thermal variables

```text
LST
LST anomaly
TCI
```

### Soil variables

```text
soil moisture
soil moisture anomaly
```

### Vegetation-health indicator

```text
VHI
```



# 9. Formula:
SPEI calculation:
```text
Water balance = precipitation - PET
```
So the final GEE dataset should include pet_mm from an appropriate reanalysis dataset ERA5-Land.

The current Python pipeline contains a Thornthwaite PET fallback, but this should not be considered the preferred final scientific implementation.



# 11. Standardized Precipitation Index SPI.

It measures precipitation conditions relative to the historical climate.

|          SPI | Interpretation   |
| --: | - |
|          ≥ 0 | Normal/wet       |
|    -1.0 to 0 | Mild dryness     |
| -1.5 to -1.0 | Moderate drought |
| -2.0 to -1.5 | Severe drought   |
|       ≤ -2.0 | Extreme drought  |


### SPI-1
Short-term precipitation conditions.
* Recent rainfall deficits
* Rapid agricultural stress

### SPI-3
Short-to-medium-term drought.
* Agriculture
* Seasonal water availability

### SPI-6
Medium-term drought.
* Agricultural impacts
* Reservoir/water-resource conditions

### SPI-12
Long-term precipitation deficit.
* Hydrological conditions
* Long-term drought monitoring



# 11. Standardized Precipitation Evapotranspiration Index SPEI.

```text
precipitation + atmospheric water demand
```

The basic water balance is:

```text
D = P - PET
```

SPEI is particularly useful for Tunisia because drought can intensify when temperatures and evaporative demand increase even if precipitation deficits alone do not fully capture the stress.



# 12. NDVI

NDVI measures vegetation greenness.

```text
NDVI = (NIR - Red) / (NIR + Red)
```

Lower-than-normal NDVI can indicate vegetation stress. However, NDVI alone should not be interpreted as drought.



# 13.Vegetation Condition Index VCI
It compares current vegetation conditions with historical minimum and maximum conditions.

```text
VCI = (current NDVI - historical minimum) - (historical maximum - historical minimum) × 100
```

Low VCI indicates vegetation conditions are poor relative to historical conditions.



# 14. Temperature Condition Index TCI

It uses land-surface temperature to identify thermal stress.

High temperatures generally correspond to stronger vegetation stress when combined with low vegetation condition.



# 15. Vegetation Health Index VHI
The simplified relationship used is:

```text
VHI = 0.5 × VCI + 0.5 × TCI
```



# 16. Soil Moisture

```text
soil_moisture_anomaly_pct
```

This compares current soil moisture against the historical monthly climatology and indicates substantial soil-moisture depletion.



# 17. Drought Hazard

The system combines multiple indicators into a composite:

```text
Hazard = SPI + SPEI + soil moisture + vegetation condition
```

The current MVP weighting is approximately:

```text
SPI-3             30%
SPI-6             20%
SPEI-3            20%
Soil moisture     15%
VHI               15%
```

This produces hazard_score between approximately 0 and 1




# 18. Drought Classification


```text
Normal
Watch
Moderate
Severe
Extreme
```

| Hazard score | Class    |
| --: | -- |
|       < 0.25 | Normal   |
|    0.25–0.50 | Watch    |
|    0.50–0.75 | Moderate |
|    0.75–0.90 | Severe   |
|       ≥ 0.90 | Extreme  |

These are **initial operational thresholds** and not validated regional thresholds.



# 19. Drought Persistence

The system tracks consecutive drought months, for example:

```text
Jan  Normal
Feb  Watch
Mar  Moderate
Apr  Severe
May  Severe
Jun  Moderate
Jul  Normal
```

April and May represent:

```text
drought_persistence_months = 2
```

Persistence is important because a single anomalous month is not necessarily a major drought.



# 20. Drought Trend

The pipeline examines the recent hazard-score trajectory, like:

```text
Improving
Stable
Deteriorating
```

For example:

```text
January    0.30
February   0.38
March      0.51
April      0.66
May        0.78
June       0.84
```

The trend would be:

```text
Deteriorating
```


# 21. Risk Assessment

Drought hazard is not the same as drought risk.

The system separates:

```text
Hazard
Exposure
Vulnerability
```
Formula:

```text
Risk = Hazard × Exposure × Vulnerability
```

### Hazard
How severe is the drought?

### Exposure
What is located in the affected area?

### Vulnerability
* Dependence on rainfed agriculture
* Water stress
* Poverty
* Irrigation limitations
* Agricultural dependence



# 22. Risk Classification

Current categories:

```text
Low
Moderate
High
Very High
Extreme
```


# 23. Impact Assessment

The system can produce indicators such as:

```text
population_exposed
cropland_affected_km2
cropland_affected_pct
```

Example output:

```text
Hazard:
Severe

Cropland affected:
1,250 km²

Population exposed:
320,000

Risk:
Very High
```

These are much more useful for decision-makers than simply showing:

```text
SPI = -1.8
```



# 24. Running the Pipeline

1. In Google Earth Engine (https://code.earthengine.google.com/), upload Tunisia_gov shapefiles and run:
```text
run drought_pipeline_1.js
```
Download the outputs from Drive:
```text
GEE-output/tunisia_drought_monthly.csv
GEE-output/tunisia_drought_latest.csv
GEE-output/governorates_latest.geojson
```

2. To generate exposure.csv and vulnerability.csv, run:
```text
Exposure & Vulnerability/exposure_vulnerability_datasets_creation.R
```
after placing it in the same file directory as:
```text
Exposure & Vulnerability/Areas equiped for irrigation.csv
Exposure & Vulnerability/Distribution of cereal irrigated areas by governorate in ha.csv
Exposure & Vulnerability/Evolution of the cattle herds by governorate.csv
Exposure & Vulnerability/Overall area of irrigated crops by governorate in ha.csv
Exposure & Vulnerability/Population_2026.csv
Exposure & Vulnerability/Regional PPIs irrigated by treated wastewater.csv
Exposure & Vulnerability/Regional_development_index_tunisia.csv
Exposure & Vulnerability/Unemployment_rate_tunisia.csv
```

   
3. Run:
```bash
drought_pipeline_2.py
```


# 25. Main Output
The main analytical dataset is:
```text
output/final_drought_monthly.csv
```
Each row represents:

```text
Governorate × Month
```




# 26. Latest Results

```text
output/final_drought_latest.csv
```



# 27. GeoJSON Output

```text
output/governorates_latest.geojson
```

This contains the governorate geometries plus current drought information.

This is the primary file that can be connected to a web map.



# 28. Website API JSON

```text
output/latest.json
```

It contains:

```text
system information
latest date
summary statistics
governorate results
drought indicators
risk
```


# 29. Governorate JSON

Individual governorate files are generated under:

```text
output/governorates/
```

Each file contains:

```text
current status
drought indicators
risk
impact
historical time series
```
This makes it easy for the website to load information when a user **clicks** a governorate.



# 30. Time-Series JSON

Files under:

```text
output/timeseries/
```

contain the historical evolution of drought.



# 32. Website Integration

The website should primarily consume:
```text
latest.json
governorates_latest.geojson
TN_*.json
```



# 33. Website Components

The data produced by this project supports:

### Tunisia overview

```text
Current drought status
Number of severe/extreme governorates
Agricultural area affected
```

### Interactive map
```text
Governorate
    ↓
Drought class
    ↓
Hazard score
    ↓
Risk score
```

### Governorate dashboard

```text
Current status
Trend
Persistence
Risk
```

### Historical graph

```text
Date vs Drought severity
```

### Early-warning component

```text
Current condition + Trend + Persistence = Warning level
```



