# TUNISIA DROUGHT EARLY WARNING SYSTEM
# ANALYTICAL PIPELINE


# INPUT:
#   GEE-output/tunisia_drought_monthly.csv
#   GEE-output/tunisia_drought_latest.csv
#   GEE-output/governorates_latest.geojson
#   data/exposure.csv
#   data/vulnerability.csv

# OUTPUT:
#   output/final_drought_latest.csv
#   output/latest.json
#   output/governorates_latest.geojson
#   output/governorates/TN_XX.json
#   output/timeseries/TN_XX.json




from pathlib import Path
import json
import re
import unicodedata
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd

from scipy import stats


warnings.filterwarnings("ignore")



# 2. PATHS

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

GEE_MONTHLY_FILE = DATA_DIR / "tunisia_drought_monthly.csv"
GEE_LATEST_FILE = DATA_DIR / "tunisia_drought_latest.csv"
GEE_GEOJSON_FILE = DATA_DIR / "governorates_latest.geojson"

EXPOSURE_FILE = DATA_DIR / "exposure.csv"
VULNERABILITY_FILE = DATA_DIR / "vulnerability.csv"

FINAL_MONTHLY_FILE = OUTPUT_DIR / "final_drought_monthly.csv"
FINAL_LATEST_FILE = OUTPUT_DIR / "final_drought_latest.csv"
LATEST_JSON_FILE = OUTPUT_DIR / "latest.json"
FINAL_GEOJSON_FILE = OUTPUT_DIR / "governorates_latest.geojson"

GOVERNORATES_DIR = OUTPUT_DIR / "governorates"
TIMESERIES_DIR = OUTPUT_DIR / "timeseries"


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GOVERNORATES_DIR.mkdir(parents=True, exist_ok=True)
TIMESERIES_DIR.mkdir(parents=True, exist_ok=True)



# 3. SETTINGS


WATCH_THRESHOLD = 0.25

HAZARD_WEIGHTS = {
    "spi_3": 0.30,
    "spi_6": 0.20,
    "spei_3": 0.20,
    "soil_moisture": 0.15,
    "vhi": 0.15,
}

SPI_SPEI_MIN_HISTORY = 10

TREND_WINDOW = 3
TREND_THRESHOLD = 0.03



# 4. OFFICIAL GOVERNORATE ORDER


CANONICAL_GOVERNORATES = [
    "Tunis",
    "Ariana",
    "Ben Arous",
    "Manouba",
    "Nabeul",
    "Zaghouan",
    "Bizerte",
    "Béja",
    "Jendouba",
    "Le Kef",
    "Siliana",
    "Sousse",
    "Monastir",
    "Mahdia",
    "Sfax",
    "Kairouan",
    "Kasserine",
    "Sidi Bouzid",
    "Gabès",
    "Médenine",
    "Tataouine",
    "Gafsa",
    "Tozeur",
    "Kébili",
]


WEBSITE_ID_MAP = {
    name: f"TN_{i:02d}"
    for i, name in enumerate(
        CANONICAL_GOVERNORATES,
        start=1
    )
}



# 5. GOVERNORATE NAME HARMONIZATION


def normalize_text(value):
    """
    Normalize text for matching.

    Removes:
    - accents
    - punctuation
    - extra whitespace
    - case differences
    """

    if pd.isna(value):
        return ""

    value = str(value).strip().lower()

    value = unicodedata.normalize(
        "NFKD",
        value
    )

    value = "".join(
        c
        for c in value
        if not unicodedata.combining(c)
    )

    value = value.replace(
        "’",
        "'"
    )

    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    return value


GOVERNORATE_ALIASES = {

    "tunis": "Tunis",

    "ariana": "Ariana",

    "ben arous": "Ben Arous",
    "ben arous tunis sud": "Ben Arous",

    "manouba": "Manouba",

    "nabeul": "Nabeul",
    "nabul": "Nabeul",

    "zaghouan": "Zaghouan",
    "saghuan": "Zaghouan",

    "bizerte": "Bizerte",

    "beja": "Béja",

    "jendouba": "Jendouba",

    "le kef": "Le Kef",
    "kef": "Le Kef",

    "siliana": "Siliana",

    "sousse": "Sousse",

    "monastir": "Monastir",

    "mahdia": "Mahdia",
    "mehdia": "Mahdia",

    "sfax": "Sfax",

    "kairouan": "Kairouan",

    "kasserine": "Kasserine",
    "kassrine": "Kasserine",

    "sidi bouzid": "Sidi Bouzid",
    "sidi bou zid": "Sidi Bouzid",
    "sbz": "Sidi Bouzid",

    "gabes": "Gabès",

    "medenine": "Médenine",
    "mednine": "Médenine",

    "tataouine": "Tataouine",
    "tatouine": "Tataouine",

    "gafsa": "Gafsa",

    "tozeur": "Tozeur",

    "kebili": "Kébili",
    "kebli": "Kébili",
}


def harmonize_governorate(value):

    normalized = normalize_text(value)

    return GOVERNORATE_ALIASES.get(
        normalized,
        None
    )



# 6. STANDARDIZE COLUMNS


def standardize_columns(df):

    df = df.copy()

    df.columns = [
        str(c).strip().lower()
        for c in df.columns
    ]

    return df



# 7. NUMERIC CONVERSION


def convert_numeric_columns(
    df,
    columns
):

    df = df.copy()

    for column in columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    return df



# 8. LOAD GEE MONTHLY DATA


def load_monthly_data():

    if not GEE_MONTHLY_FILE.exists():

        raise FileNotFoundError(
            f"\nMissing:\n{GEE_MONTHLY_FILE}\n"
        )

    df = pd.read_csv(
        GEE_MONTHLY_FILE
    )

    df = standardize_columns(df)

    # GEE export normally contains gid and shape1.
    if "gid" in df.columns:

        df = df.rename(
            columns={
                "gid":
                    "governorate_id"
            }
        )

    if "shape1" in df.columns:

        df = df.rename(
            columns={
                "shape1":
                    "governorate_name"
            }
        )

    required = [
        "governorate_id",
        "governorate_name",
        "date",
        "rainfall_mm",
        "temperature_c",
        "pet_mm",
    ]

    missing = [
        c
        for c in required
        if c not in df.columns
    ]

    if missing:

        raise ValueError(
            "GEE monthly dataset is missing "
            f"required columns: {missing}"
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["date"]
    )

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    numeric_columns = [
        "rainfall_mm",
        "temperature_c",
        "pet_mm",
        "ndvi",
        "ndvi_anomaly",
        "vci",
        "lst_c",
        "lst_anomaly",
        "tci",
        "soil_moisture",
        "soil_moisture_anomaly",
        "soil_moisture_anomaly_pct",
        "vhi",
    ]

    df = convert_numeric_columns(
        df,
        numeric_columns
    )

    # Canonical governorate name
    df["governorate_canonical"] = (
        df["governorate_name"]
        .apply(harmonize_governorate)
    )

    unknown = sorted(
        df.loc[
            df["governorate_canonical"].isna(),
            "governorate_name"
        ]
        .dropna()
        .astype(str)
        .unique()
    )


    # Replace display name with canonical name.
    df["governorate_name"] = (
        df["governorate_canonical"]
    )

    df = df.drop(
        columns=["governorate_canonical"]
    )

    # Remove duplicates
    df = (
        df
        .sort_values(
            [
                "governorate_name",
                "date"
            ]
        )
        .drop_duplicates(
            subset=[
                "governorate_name",
                "date"
            ],
            keep="last"
        )
        .reset_index(drop=True)
    )

    return df



# 9. LOAD LATEST GEE DATA


def load_latest_data():

    if not GEE_LATEST_FILE.exists():

        return None

    df = pd.read_csv(
        GEE_LATEST_FILE
    )

    df = standardize_columns(df)

    if "gid" in df.columns:

        df = df.rename(
            columns={
                "gid":
                    "governorate_id"
            }
        )

    if "shape1" in df.columns:

        df = df.rename(
            columns={
                "shape1":
                    "governorate_name"
            }
        )

    if "governorate_name" in df.columns:

        df["governorate_name"] = (
            df["governorate_name"]
            .apply(harmonize_governorate)
        )

    if "date" in df.columns:

        df["date"] = pd.to_datetime(
            df["date"],
            errors="coerce"
        )

    return df



# 10. LOAD EXPOSURE


def load_exposure():

    if not EXPOSURE_FILE.exists():

        raise FileNotFoundError(
            f"\nMissing:\n{EXPOSURE_FILE}\n"
        )

    df = pd.read_csv(
        EXPOSURE_FILE
    )

    df = standardize_columns(df)

    required = [
        "governorate_name",
        "population",
        "livestock_heads",
        "irrigated_crop_area_ha",
        "irrigated_cereal_area_ha",
        "exposure_score",
    ]

    missing = [
        c
        for c in required
        if c not in df.columns
    ]

    if missing:

        raise ValueError(
            "exposure.csv is missing "
            f"required columns: {missing}"
        )

    df["governorate_name"] = (
        df["governorate_name"]
        .apply(harmonize_governorate)
    )

    numeric = [
        "population",
        "livestock_heads",
        "irrigated_crop_area_ha",
        "irrigated_cereal_area_ha",
        "exposure_score",
    ]

    df = convert_numeric_columns(
        df,
        numeric
    )

    if df["governorate_name"].isna().any():

        raise ValueError(
            "Some exposure governorates "
            "could not be harmonized."
        )

    if df["governorate_name"].duplicated().any():

        raise ValueError(
            "exposure.csv contains duplicate "
            "governorates."
        )

    if len(df) != 24:

        raise ValueError(
            "exposure.csv must contain exactly "
            f"24 governorates. Found {len(df)}."
        )

    if (
        df["exposure_score"].dropna().lt(0).any()
        or
        df["exposure_score"].dropna().gt(1).any()
    ):

        raise ValueError(
            "exposure_score must be between 0 and 1."
        )

    return df



# 11. LOAD VULNERABILITY


def load_vulnerability():

    if not VULNERABILITY_FILE.exists():

        raise FileNotFoundError(
            f"\nMissing:\n{VULNERABILITY_FILE}\n"
        )

    df = pd.read_csv(
        VULNERABILITY_FILE
    )

    df = standardize_columns(df)

    required = [
        "governorate_name",
        "unemployment_rate",
        "regional_development_indicator",
        "equipped_irrigation_ha",
        "treated_wastewater_irrigation_ha",
        "irrigation_capacity_score",
        "treated_wastewater_dependency_score",
        "socioeconomic_vulnerability_score",
        "infrastructure_vulnerability_score",
        "vulnerability_score",
    ]

    missing = [
        c
        for c in required
        if c not in df.columns
    ]

    if missing:

        raise ValueError(
            "vulnerability.csv is missing "
            f"required columns: {missing}"
        )

    df["governorate_name"] = (
        df["governorate_name"]
        .apply(harmonize_governorate)
    )

    numeric = [
        "poverty_rate",
        "unemployment_rate",
        "regional_development_indicator",
        "equipped_irrigation_ha",
        "treated_wastewater_irrigation_ha",
        "irrigation_capacity_score",
        "treated_wastewater_dependency_score",
        "socioeconomic_vulnerability_score",
        "infrastructure_vulnerability_score",
        "vulnerability_score",
    ]

    df = convert_numeric_columns(
        df,
        numeric
    )

    if df["governorate_name"].isna().any():

        raise ValueError(
            "Some vulnerability governorates "
            "could not be harmonized."
        )

    if df["governorate_name"].duplicated().any():

        raise ValueError(
            "vulnerability.csv contains duplicate "
            "governorates."
        )

    if len(df) != 24:

        raise ValueError(
            "vulnerability.csv must contain exactly "
            f"24 governorates. Found {len(df)}."
        )

    score = df["vulnerability_score"]

    if (
        score.dropna().lt(0).any()
        or score.dropna().gt(1).any()
    ):

        raise ValueError(
            "vulnerability_score must be between 0 and 1."
        )

    return df



# 12. VALIDATE 24 GOVERNORATES


def validate_governorates(
    monthly,
    exposure,
    vulnerability
):

    expected = set(
        CANONICAL_GOVERNORATES
    )

    monthly_govs = set(
        monthly["governorate_name"]
    )

    exposure_govs = set(
        exposure["governorate_name"]
    )

    vulnerability_govs = set(
        vulnerability["governorate_name"]
    )

    

    if exposure_govs != expected:

        raise ValueError(
            "Exposure dataset does not match "
            "the expected 24 governorates.\n"
            f"Missing: {expected - exposure_govs}\n"
            f"Extra: {exposure_govs - expected}"
        )

    if vulnerability_govs != expected:

        raise ValueError(
            "Vulnerability dataset does not match "
            "the expected 24 governorates.\n"
            f"Missing: {expected - vulnerability_govs}\n"
            f"Extra: {vulnerability_govs - expected}"
        )

    print("✓ All datasets contain the same 24 governorates.")



# 13. CREATE WEBSITE IDs


def add_website_ids(df):

    df = df.copy()

    df["website_id"] = (
        df["governorate_name"]
        .map(WEBSITE_ID_MAP)
    )

    return df



# 14. SPI


def gamma_spi(values):

    values = pd.Series(
        values,
        dtype=float
    )

    result = pd.Series(
        np.nan,
        index=values.index
    )

    valid = values.notna()

    x = values.loc[valid]

    if len(x) < SPI_SPEI_MIN_HISTORY:

        return result


    zero_probability = (
        (x <= 0).sum() / len(x)
    )

    positive = x[x > 0]

    if len(positive) < 5:

        return result

    try:

        shape, loc, scale = stats.gamma.fit(
            positive,
            floc=0
        )

        probabilities = np.where(
            x <= 0,
            zero_probability * 0.5,
            zero_probability
            +
            (1 - zero_probability)
            *
            stats.gamma.cdf(
                x,
                shape,
                loc=0,
                scale=scale
            )
        )

        probabilities = np.clip(
            probabilities,
            1e-6,
            1 - 1e-6
        )

        result.loc[valid] = stats.norm.ppf(
            probabilities
        )

    except Exception:

        return result

    return result


def calculate_spi_group(
    group,
    scale
):

    group = group.copy()

    accumulation = (
        group["rainfall_mm"]
        .rolling(
            window=scale,
            min_periods=scale
        )
        .sum()
    )

    output = pd.Series(
        np.nan,
        index=group.index
    )

    temp = pd.DataFrame({
        "value": accumulation,
        "month": group["month"]
    })

    for month in range(1, 13):

        mask = (
            temp["month"] == month
        )

        if mask.sum() == 0:
            continue

        output.loc[
            temp.loc[mask].index
        ] = gamma_spi(
            temp.loc[
                mask,
                "value"
            ]
        ).values

    return output



# 15. SPEI


# D = precipitation - PET


def calculate_spei_group(
    group,
    scale
):

    group = group.copy()

    balance = (
        group["rainfall_mm"]
        -
        group["pet_mm"]
    )

    accumulated = (
        balance
        .rolling(
            window=scale,
            min_periods=scale
        )
        .sum()
    )

    output = pd.Series(
        np.nan,
        index=group.index
    )

    temp = pd.DataFrame({
        "value": accumulated,
        "month": group["month"]
    })

    for month in range(1, 13):

        mask = (
            temp["month"] == month
        )

        values = (
            temp.loc[
                mask,
                "value"
            ]
        )

        valid = values.dropna()

        if len(valid) < SPI_SPEI_MIN_HISTORY:

            continue

        # Shift so that values are positive.
        shift = max(
            0,
            -float(valid.min()) + 1e-6
        )

        shifted = valid + shift

        try:

            shape, loc, scale_param = (
                stats.fisk.fit(
                    shifted,
                    floc=0
                )
            )

            probabilities = stats.fisk.cdf(
                values + shift,
                shape,
                loc=0,
                scale=scale_param
            )

            probabilities = np.clip(
                probabilities,
                1e-6,
                1 - 1e-6
            )

            output.loc[
                values.index
            ] = stats.norm.ppf(
                probabilities
            )

        except Exception:

            continue

    return output



# 16. CALCULATE CLIMATE INDICES


def calculate_climate_indices(
    monthly
):

    monthly = monthly.copy()

    monthly = monthly.sort_values(
        [
            "governorate_name",
            "date"
        ]
    )

    for scale in [1, 3, 6, 12]:

        monthly[
            f"spi_{scale}"
        ] = np.nan

        monthly[
            f"spei_{scale}"
        ] = np.nan

    output_groups = []

    for gov, group in monthly.groupby(
        "governorate_name",
        sort=False
    ):

        group = group.sort_values(
            "date"
        ).copy()

        for scale in [1, 3, 6, 12]:

            group[
                f"spi_{scale}"
            ] = calculate_spi_group(
                group,
                scale
            )

            group[
                f"spei_{scale}"
            ] = calculate_spei_group(
                group,
                scale
            )

        output_groups.append(
            group
        )

    return pd.concat(
        output_groups,
        ignore_index=True
    )



# 17. CONVERT INDICATOR TO DROUGHT STRESS


def index_to_stress(value):

    if pd.isna(value):

        return np.nan

    return float(
        np.clip(
            -value / 2.0,
            0,
            1
        )
    )


def vhi_to_stress(value):

    if pd.isna(value):

        return np.nan

    return float(
        np.clip(
            (60.0 - value) / 60.0,
            0,
            1
        )
    )


def soil_to_stress(value):

    if pd.isna(value):

        return np.nan

    # soil_moisture_anomaly_pct is negative when soil moisture is below normal
    # -50% -> 1
    #   0% -> 0

    return float(
        np.clip(
            -value / 50.0,
            0,
            1
        )
    )



# 18. HAZARD SCORE


def calculate_hazard(
    row
):

    components = [

        (
            index_to_stress(
                row.get("spi_3")
            ),
            0.30
        ),

        (
            index_to_stress(
                row.get("spi_6")
            ),
            0.20
        ),

        (
            index_to_stress(
                row.get("spei_3")
            ),
            0.20
        ),

        (
            soil_to_stress(
                row.get(
                    "soil_moisture_anomaly_pct"
                )
            ),
            0.15
        ),

        (
            vhi_to_stress(
                row.get("vhi")
            ),
            0.15
        ),
    ]

    valid = [
        (value, weight)
        for value, weight in components
        if pd.notna(value)
    ]

    if not valid:

        return np.nan

    total_weight = sum(
        weight
        for _, weight in valid
    )

    weighted_sum = sum(
        value * weight
        for value, weight in valid
    )

    return float(
        np.clip(
            weighted_sum / total_weight,
            0,
            1
        )
    )



# 19. HAZARD CLASSIFICATION


def classify_hazard(score):

    if pd.isna(score):
        return "Unknown"

    if score < 0.25:
        return "Normal"

    if score < 0.50:
        return "Watch"

    if score < 0.75:
        return "Moderate"

    if score < 0.90:
        return "Severe"

    return "Extreme"



# 20. PERSISTENCE


def calculate_persistence(
    group
):

    group = group.sort_values(
        "date"
    ).copy()

    values = []

    current = 0

    for score in group[
        "hazard_score"
    ]:

        if (
            pd.notna(score)
            and score >= WATCH_THRESHOLD
        ):

            current += 1

        else:

            current = 0

        values.append(current)

    group[
        "drought_persistence_months"
    ] = values

    return group



# 21. TREND


def calculate_trend(
    group
):

    group = group.sort_values(
        "date"
    ).copy()

    slopes = []

    scores = group[
        "hazard_score"
    ].values

    for i in range(
        len(group)
    ):

        if i + 1 < TREND_WINDOW:

            slopes.append(np.nan)

            continue

        window = scores[
            i + 1 - TREND_WINDOW:
            i + 1
        ]

        if np.isnan(window).any():

            slopes.append(np.nan)

            continue

        x = np.arange(
            TREND_WINDOW
        )

        slope = np.polyfit(
            x,
            window,
            1
        )[0]

        slopes.append(
            float(slope)
        )

    group[
        "hazard_trend_slope"
    ] = slopes

    group[
        "drought_trend"
    ] = np.where(
        group[
            "hazard_trend_slope"
        ] > TREND_THRESHOLD,
        "Deteriorating",
        np.where(
            group[
                "hazard_trend_slope"
            ] < -TREND_THRESHOLD,
            "Improving",
            "Stable"
        )
    )

    group.loc[
        group["hazard_trend_slope"].isna(),
        "drought_trend"
    ] = "Unknown"

    return group



# 22. MERGE EXPOSURE


def merge_exposure(
    monthly,
    exposure
):

    exposure = exposure.copy()

    columns_to_keep = [
        "governorate_name",
        "population",
        "livestock_heads",
        "irrigated_crop_area_ha",
        "irrigated_cereal_area_ha",
        "exposure_score",
    ]

    exposure = exposure[
        columns_to_keep
    ]

    monthly = monthly.merge(
        exposure,
        on="governorate_name",
        how="left",
        validate="many_to_one"
    )

    return monthly



# 23. MERGE VULNERABILITY


def merge_vulnerability(
    monthly,
    vulnerability
):

    vulnerability = vulnerability.copy()

    columns_to_keep = [
        "governorate_name",

        # National poverty is retained only as metadata.
        "poverty_rate",

        "unemployment_rate",

        "regional_development_indicator",

        "equipped_irrigation_ha",

        "treated_wastewater_irrigation_ha",

        "irrigation_capacity_score",

        "treated_wastewater_dependency_score",

        "socioeconomic_vulnerability_score",

        "infrastructure_vulnerability_score",

        "vulnerability_score",
    ]

    vulnerability = vulnerability[
        columns_to_keep
    ]

    monthly = monthly.merge(
        vulnerability,
        on="governorate_name",
        how="left",
        validate="many_to_one"
    )

    return monthly



# 24. RISK


def calculate_risk(
    row
):

    hazard = row.get(
        "hazard_score"
    )

    exposure = row.get(
        "exposure_score"
    )

    vulnerability = row.get(
        "vulnerability_score"
    )

    if any(
        pd.isna(x)
        for x in [
            hazard,
            exposure,
            vulnerability
        ]
    ):

        return np.nan

    return float(
        np.clip(
            hazard
            *
            exposure
            *
            vulnerability,
            0,
            1
        )
    )



# 25. RISK CLASSIFICATION


def classify_risk(score):

    if pd.isna(score):
        return "Unknown"

    if score < 0.20:
        return "Low"

    if score < 0.40:
        return "Moderate"

    if score < 0.60:
        return "High"

    if score < 0.80:
        return "Very High"

    return "Extreme"



# 26. IMPACT ASSESSMENT

# Population exposed = population × hazard
# Cropland affected = irrigated_crop_area × hazard



def calculate_impacts(
    df
):

    df = df.copy()

    hazard = df[
        "hazard_score"
    ]

    population = pd.to_numeric(
        df["population"],
        errors="coerce"
    )

    irrigated_crops = pd.to_numeric(
        df["irrigated_crop_area_ha"],
        errors="coerce"
    )

    df[
        "population_exposed"
    ] = population * hazard

    df[
        "cropland_affected_km2"
    ] = (
        irrigated_crops
        * hazard
        / 100.0
    )

    df[
        "cropland_affected_pct"
    ] = hazard * 100.0

    return df



# 27. EARLY WARNING


def calculate_warning_level(
    row
):

    hazard = row.get(
        "hazard_score"
    )

    persistence = row.get(
        "drought_persistence_months"
    )

    trend = row.get(
        "drought_trend"
    )

    if pd.isna(hazard):

        return "Unknown"

    if hazard >= 0.90:

        return "Extreme Warning"

    if (
        hazard >= 0.75
        and (
            persistence >= 2
            or trend == "Deteriorating"
        )
    ):

        return "Severe Warning"

    if (
        hazard >= 0.50
        and trend == "Deteriorating"
    ):

        return "Early Warning"

    if hazard >= 0.25:

        return "Watch"

    return "Normal"



# 28. GEOJSON LOADER
def load_geojson():

    if not GEE_GEOJSON_FILE.exists():
        return None

    gdf = gpd.read_file(GEE_GEOJSON_FILE)

    gdf.columns = [
        str(c).strip().lower()
        for c in gdf.columns
    ]

    # Safely rename gid only if governorate_id doesn't already exist
    if "gid" in gdf.columns and "governorate_id" not in gdf.columns:
        gdf = gdf.rename(columns={"gid": "governorate_id"})

    # Safely rename shape1 only if governorate_name doesn't already exist
    if "shape1" in gdf.columns and "governorate_name" not in gdf.columns:
        gdf = gdf.rename(columns={"shape1": "governorate_name"})

    # Strip out any duplicated columns that would cause DataFrame vs Series conflicts
    gdf = gdf.loc[:, ~gdf.columns.duplicated()]

    if "governorate_name" not in gdf.columns:
        raise ValueError(
            "GeoJSON must contain a governorate name field."
        )

    gdf["governorate_name"] = (
        gdf["governorate_name"].apply(harmonize_governorate)
    )

    return gdf



# 29. LATEST GEOJSON


def create_latest_geojson(
    latest
):

    gdf = load_geojson()

    if gdf is None:

        print(
            "WARNING: governorates_latest.geojson "
            "not found. Skipping GeoJSON output."
        )

        return

    # Ensure one geometry per governorate.
    if gdf[
        "governorate_name"
    ].duplicated().any():

        raise ValueError(
            "GeoJSON contains duplicate governorates."
        )

    gdf["website_id"] = (
        gdf["governorate_name"]
        .map(WEBSITE_ID_MAP)
    )

    map_columns = [

        "governorate_name",
        "website_id",

        "date",

        "spi_3",
        "spi_6",

        "spei_3",

        "vci",
        "tci",
        "vhi",

        "soil_moisture",
        "soil_moisture_anomaly_pct",

        "hazard_score",
        "drought_class",

        "drought_persistence_months",
        "drought_trend",

        "exposure_score",
        "vulnerability_score",

        "risk_score",
        "risk_class",

        "warning_level",

        "population_exposed",
        "cropland_affected_km2",
        "cropland_affected_pct",
    ]

    map_columns = [
        c
        for c in map_columns
        if c in latest.columns
    ]

    latest_map = latest[
        map_columns
    ].copy()

    gdf = gdf.merge(
        latest_map,
        on="governorate_name",
        how="left",
        validate="one_to_one"
    )

    gdf.to_file(
        FINAL_GEOJSON_FILE,
        driver="GeoJSON"
    )

    print(
        f"✓ Written: {FINAL_GEOJSON_FILE}"
    )



# 30. JSON CLEANER


def clean_for_json(
    value
):

    if isinstance(
        value,
        dict
    ):

        return {
            str(k):
                clean_for_json(v)
            for k, v in value.items()
        }

    if isinstance(
        value,
        list
    ):

        return [
            clean_for_json(v)
            for v in value
        ]

    if value is None:

        return None

    if isinstance(
        value,
        pd.Timestamp
    ):

        return value.strftime(
            "%Y-%m-%d"
        )

    if isinstance(
        value,
        (
            np.integer,
            np.int64,
            np.int32
        )
    ):

        return int(value)

    if isinstance(
        value,
        (
            np.floating,
            np.float64,
            np.float32
        )
    ):

        if np.isnan(value):

            return None

        return float(value)

    try:

        if pd.isna(value):

            return None

    except Exception:

        pass

    return value



# 31. GOVERNORATE JSON


def create_governorate_json(
    gov_data
):

    gov_data = (
        gov_data
        .sort_values("date")
    )

    latest = (
        gov_data
        .iloc[-1]
        .to_dict()
    )

    website_id = latest[
        "website_id"
    ]

    historical = []

    for _, row in gov_data.iterrows():

        historical.append({

            "date":
                row["date"],

            "hazard_score":
                row.get(
                    "hazard_score"
                ),

            "drought_class":
                row.get(
                    "drought_class"
                ),

            "warning_level":
                row.get(
                    "warning_level"
                ),

            "drought_persistence_months":
                row.get(
                    "drought_persistence_months"
                ),

            "drought_trend":
                row.get(
                    "drought_trend"
                ),

            "spi_1":
                row.get("spi_1"),

            "spi_3":
                row.get("spi_3"),

            "spi_6":
                row.get("spi_6"),

            "spi_12":
                row.get("spi_12"),

            "spei_3":
                row.get("spei_3"),

            "spei_6":
                row.get("spei_6"),

            "vci":
                row.get("vci"),

            "tci":
                row.get("tci"),

            "vhi":
                row.get("vhi"),

            "soil_moisture_anomaly_pct":
                row.get(
                    "soil_moisture_anomaly_pct"
                ),

            "risk_score":
                row.get(
                    "risk_score"
                ),

            "risk_class":
                row.get(
                    "risk_class"
                ),
        })

    output = {

        "system": {
            "name":
                "Tunisia Drought Early Warning System"
        },

        "governorate": {

            "website_id":
                website_id,

            "governorate_id":
                latest.get(
                    "governorate_id"
                ),

            "name":
                latest.get(
                    "governorate_name"
                ),

        },

        "current":
            latest,

        "historical":
            historical,
    }

    output_file = (
        GOVERNORATES_DIR
        /
        f"{website_id}.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            clean_for_json(output),
            f,
            ensure_ascii=False,
            indent=2
        )



# 32. TIMESERIES JSON


def create_timeseries_json(
    gov_data
):

    gov_data = (
        gov_data
        .sort_values("date")
    )

    website_id = (
        gov_data.iloc[0]["website_id"]
    )

    timeseries = []

    for _, row in gov_data.iterrows():

        timeseries.append({

            "date":
                row["date"],

            "hazard_score":
                row.get(
                    "hazard_score"
                ),

            "drought_class":
                row.get(
                    "drought_class"
                ),

            "warning_level":
                row.get(
                    "warning_level"
                ),

            "drought_persistence_months":
                row.get(
                    "drought_persistence_months"
                ),

            "drought_trend":
                row.get(
                    "drought_trend"
                ),

            "spi_1":
                row.get("spi_1"),

            "spi_3":
                row.get("spi_3"),

            "spi_6":
                row.get("spi_6"),

            "spi_12":
                row.get("spi_12"),

            "spei_3":
                row.get("spei_3"),

            "spei_6":
                row.get("spei_6"),

            "vci":
                row.get("vci"),

            "tci":
                row.get("tci"),

            "vhi":
                row.get("vhi"),

            "soil_moisture":
                row.get(
                    "soil_moisture"
                ),

            "soil_moisture_anomaly_pct":
                row.get(
                    "soil_moisture_anomaly_pct"
                ),

            "exposure_score":
                row.get(
                    "exposure_score"
                ),

            "vulnerability_score":
                row.get(
                    "vulnerability_score"
                ),

            "risk_score":
                row.get(
                    "risk_score"
                ),

            "risk_class":
                row.get(
                    "risk_class"
                ),
        })

    output_file = (
        TIMESERIES_DIR
        /
        f"{website_id}.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            clean_for_json(timeseries),
            f,
            ensure_ascii=False,
            indent=2
        )



# 33. LATEST JSON


def create_latest_json(
    latest
):

    latest_date = latest[
        "date"
    ].max()

    class_counts = (
        latest[
            "drought_class"
        ]
        .value_counts()
        .to_dict()
    )

    risk_counts = (
        latest[
            "risk_class"
        ]
        .value_counts()
        .to_dict()
    )

    severe_count = int(
        latest[
            "drought_class"
        ]
        .isin(
            [
                "Severe",
                "Extreme"
            ]
        )
        .sum()
    )

    extreme_count = int(
        (
            latest[
                "drought_class"
            ]
            == "Extreme"
        )
        .sum()
    )

    population_exposed = (
        latest[
            "population_exposed"
        ]
        .sum(
            min_count=1
        )
    )

    cropland_affected = (
        latest[
            "cropland_affected_km2"
        ]
        .sum(
            min_count=1
        )
    )

    governorates = []

    for _, row in latest.iterrows():

        governorates.append({

            "website_id":
                row.get(
                    "website_id"
                ),

            "governorate_id":
                row.get(
                    "governorate_id"
                ),

            "name":
                row.get(
                    "governorate_name"
                ),

            "drought_class":
                row.get(
                    "drought_class"
                ),

            "hazard_score":
                row.get(
                    "hazard_score"
                ),

            "drought_trend":
                row.get(
                    "drought_trend"
                ),

            "drought_persistence_months":
                row.get(
                    "drought_persistence_months"
                ),

            "warning_level":
                row.get(
                    "warning_level"
                ),

            "exposure_score":
                row.get(
                    "exposure_score"
                ),

            "vulnerability_score":
                row.get(
                    "vulnerability_score"
                ),

            "risk_score":
                row.get(
                    "risk_score"
                ),

            "risk_class":
                row.get(
                    "risk_class"
                ),

            "population_exposed":
                row.get(
                    "population_exposed"
                ),

            "cropland_affected_km2":
                row.get(
                    "cropland_affected_km2"
                ),

            "cropland_affected_pct":
                row.get(
                    "cropland_affected_pct"
                ),
        })

    output = {

        "system": {

            "name":
                "Tunisia Drought Early Warning System",

            "version":
                "MVP-2"
        },

        "latest_date":
            latest_date,

        "summary": {

            "governorates":
                len(latest),

            "drought_classes":
                class_counts,

            "risk_classes":
                risk_counts,

            "severe_or_extreme_governorates":
                severe_count,

            "extreme_governorates":
                extreme_count,

            "population_exposed":
                population_exposed,

            "cropland_affected_km2":
                cropland_affected,
        },

        "governorates":
            governorates,
    }

    with open(
        LATEST_JSON_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            clean_for_json(output),
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"✓ Written: {LATEST_JSON_FILE}"
    )



# 34. ALL JSON OUTPUTS


def create_json_outputs(
    monthly,
    latest
):

    create_latest_json(
        latest
    )

    for _, gov_data in monthly.groupby(
        "governorate_name",
        sort=False
    ):

        create_governorate_json(
            gov_data
        )

        create_timeseries_json(
            gov_data
        )

    print(
        "✓ Governorate JSON files created."
    )



# 35. VALIDATE FINAL DATA


def validate_final_dataset(
    monthly
):

    expected = 24

    actual = (
        monthly[
            "governorate_name"
        ]
        .nunique()
    )

    

    duplicate_count = (
        monthly
        .duplicated(
            [
                "governorate_name",
                "date"
            ]
        )
        .sum()
    )

    if duplicate_count:

        raise ValueError(
            f"Found {duplicate_count} duplicate "
            "governorate-month records."
        )

    for column in [
        "hazard_score",
        "exposure_score",
        "vulnerability_score",
        "risk_score",
    ]:

        if column not in monthly.columns:

            raise ValueError(
                f"Missing final column: {column}"
            )

        values = monthly[
            column
        ].dropna()

        if values.empty:
            continue

        if values.lt(0).any() or values.gt(1).any():

            raise ValueError(
                f"{column} contains values outside [0,1]."
            )

    print(
        "✓ Final dataset validation passed."
    )



# 36. MAIN PIPELINE


def run_pipeline():

    # LOAD

    print(
        "[1/9] Loading GEE environmental data..."
    )

    monthly = load_monthly_data()

    print(
        f"      {len(monthly):,} monthly records"
    )

    # LOAD STATIC DATA

    print(
        "[2/9] Loading exposure and vulnerability..."
    )

    exposure = load_exposure()
    vulnerability = load_vulnerability()

    validate_governorates(
        monthly,
        exposure,
        vulnerability
    )

    # WEBSITE IDS

    print(
        "[3/9] Assigning website IDs..."
    )

    monthly = add_website_ids(
        monthly
    )

    # SPI / SPEI

    print(
        "[4/9] Calculating SPI and SPEI..."
    )

    monthly = calculate_climate_indices(
        monthly
    )

    # HAZARD

    print(
        "[5/9] Calculating drought hazard..."
    )

    monthly[
        "hazard_score"
    ] = monthly.apply(
        calculate_hazard,
        axis=1
    )

    monthly[
        "drought_class"
    ] = monthly[
        "hazard_score"
    ].apply(
        classify_hazard
    )

    # PERSISTENCE / TREND

    groups = []

    for _, group in monthly.groupby(
        "governorate_name",
        sort=False
    ):

        group = calculate_persistence(
            group
        )

        group = calculate_trend(
            group
        )

        groups.append(group)

    monthly = pd.concat(
        groups,
        ignore_index=True
    )

    # EXPOSURE

    print(
        "[6/9] Joining exposure..."
    )

    monthly = merge_exposure(
        monthly,
        exposure
    )


    # VULNERABILITY

    print(
        "[7/9] Joining vulnerability..."
    )

    monthly = merge_vulnerability(
        monthly,
        vulnerability
    )

    

    # RISK

    print(
        "[8/9] Calculating risk and impacts..."
    )

    monthly[
        "risk_score"
    ] = monthly.apply(
        calculate_risk,
        axis=1
    )

    monthly[
        "risk_class"
    ] = monthly[
        "risk_score"
    ].apply(
        classify_risk
    )

    monthly = calculate_impacts(
        monthly
    )

    monthly[
        "warning_level"
    ] = monthly.apply(
        calculate_warning_level,
        axis=1
    )

    # SORT

    monthly = (
        monthly
        .sort_values(
            [
                "date",
                "governorate_name"
            ]
        )
        .reset_index(drop=True)
    )

    # VALIDATE

    validate_final_dataset(
        monthly
    )

    # SAVE MONTHLY

    monthly.to_csv(
        FINAL_MONTHLY_FILE,
        index=False
    )

    print(
        f"✓ {FINAL_MONTHLY_FILE}"
    )

    # LATEST

    latest_date = monthly[
        "date"
    ].max()

    latest = (
        monthly[
            monthly["date"] == latest_date
        ]
        .copy()
    )

    latest = latest.sort_values(
        "governorate_name"
    )

    latest.to_csv(
        FINAL_LATEST_FILE,
        index=False
    )

    print(
        f"✓ {FINAL_LATEST_FILE}"
    )

    # GEOJSON

    create_latest_geojson(
        latest
    )

    # JSON

    create_json_outputs(
        monthly,
        latest
    )


    print(
        f"Governorates: {len(latest)}"
    )

    print(
        f"Monthly records: {len(monthly):,}"
    )

    print(
        f"Output directory: {OUTPUT_DIR}"
    )



# 37. RUN


if __name__ == "__main__":

    run_pipeline()

