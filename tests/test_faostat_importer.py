from io import BytesIO, StringIO
from zipfile import ZipFile
import csv

import pandas as pd

from backend.app.sync_global_data import (
    parse_faostat_zip,
    parse_faostat_csv,
    convert_value,
    country_iso3_from_m49,
    faostat_crop_code,
)


def make_zip():
    rows = [
        ["004", "Afghanistan", "15", "Wheat", "Area harvested", "2020", "1000 ha", "100", "A"],
        ["004", "Afghanistan", "15", "Wheat", "Production", "2020", "1000 t", "300", "A"],
        ["004", "Afghanistan", "15", "Wheat", "Yield", "2020", "hg/ha", "30000", "A"],
        ["004", "Afghanistan", "56", "Maize (corn)", "Area harvested", "2020", "1000 ha", "10", "A"],
        ["004", "Afghanistan", "56", "Maize (corn)", "Production", "2020", "1000 t", "50", "E"],
        ["004", "Afghanistan", "27", "Rice, paddy", "Area harvested", "2020", "1000 ha", "20", "A"],
        ["004", "Afghanistan", "27", "Rice, paddy", "Production", "2020", "1000 t", "80", "A"],
        ["004", "Afghanistan", "236", "Soya beans", "Area harvested", "2020", "1000 ha", "5", "A"],
        ["004", "Afghanistan", "236", "Soya beans", "Yield", "2020", "hg/ha", "20000", "A"],
        ["001", "World", "15", "Wheat", "Area harvested", "2020", "1000 ha", "200000", "A"],
        ["001", "World", "15", "Wheat", "Production", "2020", "1000 t", "700000", "A"],
    ]
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        name = "Production_Crops_Livestock_E_All_Data_(Normalized).csv"
        text = StringIO(newline="")
        writer = csv.writer(text, lineterminator="\n")
        writer.writerow([
            "Area Code (M49)", "Area", "Item Code", "Item",
            "Element", "Year", "Unit", "Value", "Flag",
        ])
        writer.writerows(rows)
        archive.writestr(name, text.getvalue().encode("utf-8"))
    return payload.getvalue()


def test_unit_conversion_and_m49_country_mapping():
    assert convert_value(100, "1000 ha", "area") == 100000
    assert convert_value(300, "1000 t", "production") == 300000
    assert convert_value(30000, "hg/ha", "yield") == 3
    assert country_iso3_from_m49("004") == "AFG"
    assert country_iso3_from_m49("'004") == "AFG"
    assert faostat_crop_code("656", "Coffee, green") == "FAO_656"
    assert faostat_crop_code("236", "Soya beans") == "SOYBEAN"
    assert faostat_crop_code("9", "Some other item") == "FAO_9"


def test_faostat_zip_parser_normalizes_crops_and_skips_world_aggregate():
    records = parse_faostat_zip(make_zip(), source_release="2026-11-04")
    by_crop = {row["crop_code"]: row for row in records}
    assert set(by_crop) == {"WHEAT", "MAIZE", "RICE", "SOYBEAN"}
    assert by_crop["WHEAT"]["harvested_area_ha"] == 100000
    assert by_crop["WHEAT"]["production_t"] == 300000
    assert by_crop["WHEAT"]["yield_t_ha"] == 3
    assert by_crop["MAIZE"]["production_flag"] == "E"
    assert by_crop["RICE"]["yield_t_ha"] == 4
    assert by_crop["SOYBEAN"]["yield_flag"] == "A"
    assert all(row["country_iso3"] == "AFG" for row in records)


def test_local_csv_streaming_keeps_all_crop_items_and_excludes_livestock(tmp_path):
    csv_path = tmp_path / "faostat.csv"
    rows = [
        ["'004", "Afghanistan", "'15", "Wheat", "Area harvested", 2020, "ha", 100, "A"],
        ["'004", "Afghanistan", "'15", "Wheat", "Production", 2020, "t", 300, "A"],
        ["'004", "Afghanistan", "'15", "Wheat", "Yield", 2020, "kg/ha", 3000, "A"],
        ["'004", "Afghanistan", "'656", "Coffee, green", "Area harvested", 2020, "ha", 20, "A"],
        ["'004", "Afghanistan", "'656", "Coffee, green", "Production", 2020, "t", 40, "A"],
        ["'004", "Afghanistan", "'656", "Coffee, green", "Yield", 2020, "kg/ha", 2000, "A"],
        ["'004", "Afghanistan", "'866", "Cattle", "Producing Animals/Slaughtered", 2020, "An", 100, "A"],
    ]
    pd.DataFrame(rows, columns=[
        "Area Code (M49)", "Area", "Item Code", "Item", "Element",
        "Year", "Unit", "Value", "Flag",
    ]).to_csv(csv_path, index=False)

    # A one-row chunk forces Area, Production and Yield across chunk boundaries.
    records = parse_faostat_csv(csv_path, source_release="test", chunksize=1)
    by_crop = {row["crop_code"]: row for row in records}

    assert set(by_crop) == {"WHEAT", "FAO_656"}
    assert by_crop["WHEAT"]["country_iso3"] == "AFG"
    assert by_crop["WHEAT"]["harvested_area_ha"] == 100
    assert by_crop["WHEAT"]["production_t"] == 300
    assert by_crop["WHEAT"]["yield_t_ha"] == 3
    assert by_crop["FAO_656"]["crop_name"] == "Coffee, green"
    assert by_crop["FAO_656"]["yield_t_ha"] == 2
