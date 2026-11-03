from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge, ElasticNet
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODEL_FACTORIES = {
    "LINEAR_REGRESSION": lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LinearRegression()),
    "RIDGE": lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0)),
    "ELASTIC_NET": lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), ElasticNet(alpha=0.03, l1_ratio=0.25, max_iter=20000)),
    "RANDOM_FOREST": lambda: make_pipeline(SimpleImputer(strategy="median"), RandomForestRegressor(n_estimators=400, min_samples_leaf=2, max_features=0.8, random_state=42, n_jobs=-1)),
    "EXTRA_TREES": lambda: make_pipeline(SimpleImputer(strategy="median"), ExtraTreesRegressor(n_estimators=400, min_samples_leaf=2, max_features=0.8, random_state=42, n_jobs=-1)),
    "HIST_GRADIENT_BOOSTING": lambda: make_pipeline(SimpleImputer(strategy="median"), HistGradientBoostingRegressor(max_iter=150, learning_rate=0.04, l2_regularization=1.0, random_state=42)),
}

FEATURES = ["wx_t2m_mean_c", "wx_tmax_mean_c", "wx_tmin_mean_c", "wx_precip_sum_mm", "wx_rh_mean_pct", "wx_wind_mean_m_s", "wx_solar_mean_mj_m2_day", "wx_hot_days_ge_35c", "wx_frost_days_lt_0c", "wx_gdd_base5_cday"]


def evaluate_and_predict(rows: list[dict], target_year: int, requested_model: str | None = None) -> dict:
    df = pd.DataFrame(rows).sort_values("year")
    df["yield_t_ha"] = pd.to_numeric(df["yield_t_ha"], errors="coerce")
    for col in FEATURES:
        if col not in df:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["yield_t_ha"])
    if len(df) < 8:
        raise ValueError(f"Prognoz uchun kamida 8 ta hosildorlik kuzatuvi va mos environmental qator talab qilinadi. Hozir: {len(df)}.")
    usable = df[FEATURES].notna().any(axis=1)
    df = df.loc[usable].copy()
    active_features = [c for c in FEATURES if df[c].notna().any()]
    if len(active_features) < 2:
        raise ValueError("Model uchun kamida 2 ta ishlatiladigan ob-havo feature topilmadi.")
    df = df[["year", "yield_t_ha"] + active_features].copy()
    if len(df) < 8:
        raise ValueError(f"Weather bilan birlashtirilgan valid qator 8 tadan kam: {len(df)}. Avval ma’lumotni to‘ldirish/tekshirish jobini yakunlang.")

    # Expanding chronological validation; at least 5 earlier years before each OOF prediction.
    predictions = {name: [] for name in MODEL_FACTORIES}
    persist_errors = []
    actuals = []
    years = df["year"].astype(int).tolist()
    for idx in range(5, len(df)):
        train = df.iloc[:idx]
        valid = df.iloc[[idx]]
        y_train = train["yield_t_ha"].to_numpy(dtype=float)
        y_true = float(valid["yield_t_ha"].iloc[0])
        prev_yield = float(train["yield_t_ha"].iloc[-1])
        persist_errors.append(abs(y_true - prev_yield))
        actuals.append(y_true)
        for model_id, factory in MODEL_FACTORIES.items():
            model = factory()
            model.fit(train[active_features], y_train)
            pred = float(model.predict(valid[active_features])[0])
            predictions[model_id].append({"year": years[idx], "actual": y_true, "predicted": pred, "absolute_error": abs(y_true-pred)})

    persist_mae = float(np.mean(persist_errors))
    summary = []
    for model_id, pred_rows in predictions.items():
        errors = [r["absolute_error"] for r in pred_rows]
        mae = float(np.mean(errors)) if errors else None
        summary.append({"model": model_id, "oof_rows": len(errors), "oof_mae_t_ha": mae, "beats_persistence": bool(mae is not None and mae < persist_mae)})
    summary.sort(key=lambda x: x["oof_mae_t_ha"] if x["oof_mae_t_ha"] is not None else float("inf"))
    selected = requested_model.upper() if requested_model else summary[0]["model"]
    if selected not in MODEL_FACTORIES:
        raise ValueError(f"Noma’lum model: {selected}")

    # A future-season forecast cannot know actual future weather. Use recent observed weather normal and label it.
    latest_year = int(df["year"].max())
    recent = df[df["year"] >= latest_year - 4]
    future_x = recent[active_features].mean(numeric_only=True).to_frame().T
    full_model = MODEL_FACTORIES[selected]().fit(df[active_features], df["yield_t_ha"].to_numpy(dtype=float))
    forecast = float(full_model.predict(future_x)[0])
    forecast = max(0.0, forecast)
    persistence = float(df["yield_t_ha"].iloc[-1])
    selected_row = next(x for x in summary if x["model"] == selected)
    benchmark_status = "BEATS_PERSISTENCE" if selected_row["beats_persistence"] else "BELOW_PERSISTENCE"
    return {
        "target_year": target_year,
        "last_observed_year": latest_year,
        "predicted_yield_t_ha": forecast,
        "reference_last_observed_yield_t_ha": persistence,
        "prediction_type": "CLIMATOLOGY_SCENARIO",
        "weather_assumption": f"Oxirgi 5 yil ({max(int(df.year.min()), latest_year-4)}–{latest_year}) kuzatilgan ob-havo feature'larining o‘rtachasi; haqiqiy kelajak ob-havosi emas.",
        "selected_model": selected,
        "selected_model_oof_mae_t_ha": selected_row["oof_mae_t_ha"],
        "persistence_oof_mae_t_ha": persist_mae,
        "benchmark_status": benchmark_status,
        "oof_rows": selected_row["oof_rows"],
        "model_comparison": summary,
        "oof_predictions": predictions[selected],
        "governance_note": "Bu bitta foydalanuvchi datasetiga moslangan research scenario. Global umumiy model sifatida tasdiqlanmagan. Hindcast/forecast qiymatlari OBSERVED target sifatida saqlanmaydi.",
    }
