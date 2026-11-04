"""Environmental source registry. Unconfigured sources are explicitly unavailable."""

SOURCE_REGISTRY = {
    "NASA_POWER": {
        "status": "ACTIVE",
        "coverage": "Global point / grid weather time series",
        "outputs": ["temperature", "precipitation", "humidity", "wind", "solar_radiation", "GDD", "hot_days", "frost_days"],
        "note": "MVP samples the selected polygon's representative point; not polygon-wide zonal statistics.",
        "url": "https://power.larc.nasa.gov/",
    },
    "OPEN_METEO_FORECAST": {
        "status": "ACTIVE",
        "coverage": "Current conditions and up to 16-day point forecast",
        "outputs": ["temperature", "apparent_temperature", "relative_humidity", "precipitation", "precipitation_probability", "wind", "reference_evapotranspiration"],
        "note": "Weather-model forecast for the saved location's representative point; forecast is not a measurement.",
        "url": "https://open-meteo.com/",
    },
    "SENTINEL2_NDVI": {
        "status": "PLANNED_CONNECTOR",
        "coverage": "Requires STAC search, cloud masking, raster processing and seasonal aggregation",
        "outputs": ["NDVI mean", "NDVI median", "NDVI max", "valid pixel count", "cloud coverage"],
        "note": "Not yet fetched by this MVP. Never represented as available until the raster job is configured.",
        "url": "https://dataspace.copernicus.eu/",
    },
    "NASA_SMAP": {
        "status": "PLANNED_CONNECTOR",
        "coverage": "Requires product selection, access policy, raster processing and quality flags",
        "outputs": ["surface soil moisture", "root-zone moisture where supported", "observation count"],
        "note": "Not yet fetched by this MVP. Product depth and units must be checked per product.",
        "url": "https://nsidc.org/data/smap",
    },
    "SOILGRIDS": {
        "status": "PLANNED_CONNECTOR",
        "coverage": "Static / slowly varying soil-property raster context",
        "outputs": ["pH", "SOC", "nitrogen", "clay", "sand", "silt", "bulk density", "CEC", "coarse fragments"],
        "note": "Not yet fetched by this MVP. Regional zonal statistics are not field laboratory tests.",
        "url": "https://soilgrids.org/",
    },
}
