from backend.app.ml.forecast import evaluate_and_predict, FEATURES


def test_forecast_uses_time_ordered_oof_and_persistence():
    rows = []
    for year in range(2005, 2017):
        row = {"year": year, "yield_t_ha": 3.2 + (year - 2005) * 0.04}
        for i, feature in enumerate(FEATURES):
            row[feature] = float(i + (year - 2005) * 0.1)
        rows.append(row)
    result = evaluate_and_predict(rows, target_year=2017, requested_model="RIDGE")
    assert result["prediction_type"] == "CLIMATOLOGY_SCENARIO"
    assert result["target_year"] == 2017
    assert result["oof_rows"] == 7
    assert result["persistence_oof_mae_t_ha"] >= 0
    assert result["selected_model"] == "RIDGE"
    assert len(result["model_comparison"]) == 6
