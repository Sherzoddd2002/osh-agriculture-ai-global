"""FAOSTAT-based global crop forecast baseline with provenance labels."""
from collections import defaultdict
from statistics import median
import re
import unicodedata

import numpy as np
from sklearn.linear_model import Ridge
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import GlobalCropStatistic
from .faostat_catalog import classify_faostat_item, CROP


ALIASES = {
    "WHEAT": {"wheat", "wheat grain"},
    "MAIZE": {"maize", "maize corn", "corn"},
    "RICE": {"rice", "rice paddy", "paddy rice"},
    "BARLEY": {"barley"},
    "SOYBEAN": {"soybean", "soybeans", "soya bean", "soya beans"},
    "COTTON": {"cotton", "cotton lint"},
    "POTATO": {"potato", "potatoes"},
    "SORGHUM": {"sorghum"},
}


def normalize_crop_code(value: str) -> str:
    """Normalize official FAOSTAT item labels and user-provided crop names."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    key = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    for code, aliases in ALIASES.items():
        if key == code.lower() or key in aliases:
            return code
    return key.upper().replace(" ", "_")[:64] or "UNKNOWN"


def _series(rows) -> list[dict]:
    """Build annual yield from paired production/area, else area-weighted yield."""
    totals = defaultdict(lambda: {
        "area_all": 0.0,
        "production": 0.0,
        "area_with_production": 0.0,
        "yield_area": 0.0,
        "yield_weight": 0.0,
    })
    for row in rows:
        area = row.harvested_area_ha
        if area is None or area <= 0:
            continue
        item = totals[int(row.year)]
        item["area_all"] += float(area)
        if row.production_t is not None and row.production_t >= 0:
            item["production"] += float(row.production_t)
            item["area_with_production"] += float(area)
        if row.yield_t_ha is not None and row.yield_t_ha >= 0:
            item["yield_area"] += float(row.yield_t_ha) * float(area)
            item["yield_weight"] += float(area)

    result = []
    for year, values in sorted(totals.items()):
        if values["area_with_production"] > 0:
            yield_value = values["production"] / values["area_with_production"]
        elif values["yield_weight"] > 0:
            yield_value = values["yield_area"] / values["yield_weight"]
        else:
            continue
        if np.isfinite(yield_value) and 0 <= yield_value <= 30:
            result.append({"year": year, "yield_t_ha": float(yield_value)})
    return result


def _fit(series: list[dict], target_year: int) -> dict:
    if len(series) < 8:
        raise ValueError(f"Kamida 8 yillik qator kerak; mavjud: {len(series)}.")

    values = [float(row["yield_t_ha"]) for row in series]
    features = []
    targets = []
    for index in range(3, len(series)):
        window = np.asarray(values[index - 3:index], dtype=float)
        features.append([
            float(series[index]["year"]),
            values[index - 1],
            float(window.mean()),
            float(window.std()),
        ])
        targets.append(values[index])

    errors = []
    persistence_errors = []
    oof_predictions = []
    for split in range(3, len(targets)):
        model = Ridge(alpha=2.0).fit(
            np.asarray(features[:split]), np.asarray(targets[:split])
        )
        predicted = max(
            0.0,
            float(model.predict(np.asarray([features[split]]))[0]),
        )
        actual = targets[split]
        persistence = targets[split - 1]
        errors.append(abs(actual - predicted))
        persistence_errors.append(abs(actual - persistence))
        oof_predictions.append({
            "year": int(series[split + 3]["year"]),
            "actual_t_ha": actual,
            "predicted_t_ha": predicted,
            "absolute_error_t_ha": abs(actual - predicted),
        })

    if not errors:
        raise ValueError("Expanding-window validatsiya uchun yetarli yillar topilmadi.")

    mae = float(np.mean(errors))
    persistence_mae = float(np.mean(persistence_errors))
    recent = np.asarray(values[-3:], dtype=float)
    future_x = np.asarray([[
        float(target_year), values[-1], float(recent.mean()), float(recent.std())
    ]])
    model = Ridge(alpha=2.0).fit(np.asarray(features), np.asarray(targets))
    forecast = max(0.0, float(model.predict(future_x)[0]))

    return {
        "predicted_yield_t_ha": forecast,
        "oof_mae_t_ha": mae,
        "persistence_oof_mae_t_ha": persistence_mae,
        "beats_persistence": mae < persistence_mae,
        "oof_rows": len(errors),
        "oof_predictions": oof_predictions,
        "lower_approx_t_ha": max(0.0, forecast - 1.96 * mae),
        "upper_approx_t_ha": forecast + 1.96 * mae,
        "training_years": len(series),
        "last_observed_year": int(series[-1]["year"]),
    }


def forecast_global_crop_yield(
    db: Session, country_iso3: str, crop_code: str, target_year: int
) -> dict:
    crop = normalize_crop_code(crop_code)
    records = db.scalars(
        select(GlobalCropStatistic)
        .where(GlobalCropStatistic.crop_code == crop)
        .order_by(GlobalCropStatistic.year)
    ).all()
    if not records:
        raise ValueError(f"{crop}: FAOSTAT global bazasi yuklanmagan.")
    item_types = {
        classify_faostat_item(row.item_code, row.crop_name)
        for row in records
    }
    if item_types != {CROP}:
        raise ValueError(
            f"{crop}: prognoz faqat alohida ekin itemlari uchun ruxsat etiladi; "
            "agregat yoki mahsulot shakli tanlangan."
        )

    global_series = _series(records)
    country_series = _series([
        row for row in records if row.country_iso3 == country_iso3.upper()
    ])

    if len(country_series) >= 8:
        fitted = _fit(country_series, target_year)
        prediction_type = "COUNTRY_NATIONAL_TREND"
        adjustment = 1.0
        training_scope = f"{country_iso3.upper()} FAOSTAT national series"
    else:
        fitted = _fit(global_series, target_year)
        global_by_year = {
            row["year"]: row["yield_t_ha"] for row in global_series
        }
        ratios = [
            row["yield_t_ha"] / global_by_year[row["year"]]
            for row in country_series
            if row["year"] in global_by_year and global_by_year[row["year"]] > 0
        ]
        adjustment = (
            min(2.5, max(0.4, float(median(ratios[-5:]))))
            if len(ratios) >= 3 else 1.0
        )
        for key in (
            "predicted_yield_t_ha",
            "lower_approx_t_ha",
            "upper_approx_t_ha",
        ):
            fitted[key] *= adjustment
        prediction_type = (
            "COUNTRY_ADJUSTED_GLOBAL_TREND"
            if len(ratios) >= 3 else "GLOBAL_CROP_TREND_PROXY"
        )
        training_scope = "Global area-weighted FAOSTAT crop series"

    return {
        **fitted,
        "crop_code": crop,
        "country_iso3": country_iso3.upper(),
        "target_year": int(target_year),
        "prediction_type": prediction_type,
        "training_scope": training_scope,
        "country_observed_years": len(country_series),
        "global_observed_years": len(global_series),
        "country_adjustment_factor": adjustment,
        "source": "FAOSTAT QCL",
        "source_url": "https://www.fao.org/faostat/en/#data/QCL",
        "source_license": "CC BY 4.0; attribution to FAO required",
        "spatial_scope": "NATIONAL_OR_GLOBAL_PROXY",
        "limitations": (
            "Bu tuman/dala kuzatuvi emas. FAOSTAT milliy trendiga asoslangan "
            "baseline; raster iqlim/tuproq bilan kalibrlash hali ulanmagan. "
            "Interval vaqt bo‘yicha OOF xatosidan olingan taxminiy diapazon."
        ),
    }
