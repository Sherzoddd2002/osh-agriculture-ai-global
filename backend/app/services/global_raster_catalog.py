"""Versioned catalog for global crop raster datasets.

Sources:
- CROPGRIDS v1.08 (2020), CC BY 4.0.
- IFPRI MAPSPAM 2020 v2r2, CC BY-SA 4.0.
"""
from __future__ import annotations

import os
from itertools import product
from pathlib import Path


CROPGRIDS = {
    "dataset_id": "cropgrids-2020-v1.08",
    "title": "CROPGRIDS v1.08 NetCDF maps",
    "reference_year": 2020,
    "crop_count": 173,
    "resolution_degrees": 0.05,
    "resolution_km_at_equator": 5.6,
    "format": "ZIP containing NetCDF4 maps",
    "url": "https://ndownloader.figshare.com/files/44950942",
    "filename": "CROPGRIDSv1.08_NC_maps.zip",
    "expected_size_bytes": 806855203,
    "expected_md5": "2773d0b1f83518cf7a4e271a73e62a57",
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "citation": "Tang et al. (2024), CROPGRIDS, Figshare, https://doi.org/10.6084/m9.figshare.22491997.v9",
    "variables": ["crop_physical_area", "harvested_area"],
    "limitations": (
        "2020 reference year only; crop-area distribution, not production or yield. "
        "Harvested area can exceed physical area because multiple cropping cycles count."
    ),
}

MAPSPAM_VARIABLES = {
    "physical_area": {"unit": "ha", "aggregation": "sum"},
    "harvested_area": {"unit": "ha", "aggregation": "sum"},
    "production": {"unit": "t", "aggregation": "sum"},
    "yield": {"unit": "kg/ha", "aggregation": "harvested-area-weighted mean"},
}
MAPSPAM_TECHNOLOGIES = ("all", "irrigated", "rainfed")

# The band order is the crop dimension order published in the MAPSPAM v2r2
# catalog. Raster bands are 1-based, so each tuple position maps to band i + 1.
MAPSPAM_CROPS = (
    ("whea", "Wheat"),
    ("rice", "Rice"),
    ("maiz", "Maize"),
    ("barl", "Barley"),
    ("mill", "Small millet"),
    ("pmil", "Pearl millet"),
    ("sorg", "Sorghum"),
    ("ocer", "Other cereals"),
    ("pota", "Potato"),
    ("swpo", "Sweet potato"),
    ("yams", "Yams"),
    ("cass", "Cassava"),
    ("orts", "Other roots"),
    ("bean", "Bean"),
    ("chic", "Chickpea"),
    ("cowp", "Cowpea"),
    ("pige", "Pigeon pea"),
    ("lent", "Lentil"),
    ("opul", "Other pulses"),
    ("soyb", "Soybean"),
    ("grou", "Groundnut"),
    ("cnut", "Coconut"),
    ("oilp", "Oil palm"),
    ("sunf", "Sunflower"),
    ("rape", "Rapeseed"),
    ("sesa", "Sesame seed"),
    ("ooil", "Other oil crops"),
    ("sugc", "Sugarcane"),
    ("sugb", "Sugarbeet"),
    ("cott", "Cotton"),
    ("ofib", "Other fibre crops"),
    ("coff", "Arabica coffee"),
    ("rcof", "Robusta coffee"),
    ("coco", "Cocoa"),
    ("teas", "Tea"),
    ("toba", "Tobacco"),
    ("bana", "Banana"),
    ("plnt", "Plantain"),
    ("citr", "Citrus"),
    ("trof", "Other tropical fruit"),
    ("temf", "Temperate fruit"),
    ("toma", "Tomato"),
    ("onio", "Onion"),
    ("vege", "Other vegetables"),
    ("rubb", "Rubber"),
    ("rest", "Rest of crops"),
)

MAPSPAM_BASE_URL = (
    "https://digital-atlas.s3.amazonaws.com/cdh/data/"
    "mapspam2020-v2r2/cog"
)
MAPSPAM_CROP_CODES_URL = (
    "https://digital-atlas.s3.amazonaws.com/cdh/data/"
    "mapspam2020-v2r2/crop-codes.json"
)



def default_global_data_dir() -> Path:
    """Resolve persistent global data storage without writing into the source tree."""
    explicit = os.environ.get("OSH_AGRI_DATA_DIR")
    if explicit:
        return Path(explicit).expanduser()
    home = os.environ.get("OSH_AGRI_HOME")
    if home:
        return Path(home).expanduser() / "global-data"
    return Path("data/global")

def mapspam_cog_assets() -> list[dict]:
    """Return the 12 documented COG variable/technology combinations."""
    assets = []
    for variable, technology in product(
        MAPSPAM_VARIABLES.keys(), MAPSPAM_TECHNOLOGIES
    ):
        filename = f"spam2020-{variable}-{technology}.tif"
        assets.append({
            "asset_id": f"{variable}-{technology}",
            "filename": filename,
            "url": f"{MAPSPAM_BASE_URL}/{filename}",
            "variable": variable,
            "technology": technology,
            "unit": MAPSPAM_VARIABLES[variable]["unit"],
            "aggregation": MAPSPAM_VARIABLES[variable]["aggregation"],
        })
    assets.append({
        "asset_id": "crop-codes",
        "filename": "crop-codes.json",
        "url": MAPSPAM_CROP_CODES_URL,
        "variable": "crop_dimension_metadata",
        "technology": None,
        "unit": None,
        "aggregation": "metadata",
    })
    return assets


MAPSPAM = {
    "dataset_id": "mapspam-2020-v2r2",
    "title": "IFPRI Global Spatially-Disaggregated Crop Production Statistics",
    "reference_year": 2020,
    "crop_count": 46,
    "resolution_arc_minutes": 5,
    "resolution_km_at_equator": 9.3,
    "crs": "EPSG:4326",
    "format": "Cloud Optimized GeoTIFF",
    "license": "CC BY-SA 4.0",
    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "citation": "IFPRI (2026), MAPSPAM 2020 v2r2, Harvard Dataverse, https://doi.org/10.7910/DVN/SWPENT",
    "variables": MAPSPAM_VARIABLES,
    "technologies": list(MAPSPAM_TECHNOLOGIES),
    "assets": mapspam_cog_assets,
    "limitations": (
        "Global 5 arc-minute grid. Appropriate for regional and subnational summaries, "
        "not field-scale management. Yield is a rate and must be aggregated using "
        "harvested-area weights, never summed."
    ),
}


def catalog_summary() -> dict:
    """Small JSON-safe catalog summary for CLI/API output."""
    return {
        "cropgrids": {
            key: value for key, value in CROPGRIDS.items()
            if key not in {"expected_md5"}
        },
        "mapspam": {
            key: value for key, value in MAPSPAM.items()
            if key != "assets"
        } | {
            "assets": mapspam_cog_assets(),
            "crops": [
                {"code": code, "name": name, "band": index + 1}
                for index, (code, name) in enumerate(MAPSPAM_CROPS)
            ],
        },
    }
