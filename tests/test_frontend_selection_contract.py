from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
APP_HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index + len(start))
    return source[start_index:end_index]


def test_selecting_a_region_does_not_require_login_before_opening_auth_modal():
    select_feature = section(APP_JS, "function selectFeature(", "async function loadBoundaries(")
    save_handler = section(
        APP_JS,
        "$('save-location').addEventListener('click'",
        "function openAuth()",
    )
    auth_ui = section(APP_JS, "function setAuthUI(user)", "function logout(")

    assert "$('save-location').disabled=!selectedFeature;" in select_feature
    assert "$('save-location').disabled=!token" not in select_feature
    assert "if(!token)" in save_handler
    assert "openAuth();" in save_handler
    assert "$('save-location').disabled=!selectedFeature;" in auth_ui


def test_full_app_exposes_custom_small_area_drawing_controls():
    for element_id in ("draw-aoi-start", "draw-aoi-finish", "draw-aoi-cancel"):
        assert f'id="{element_id}"' in APP_HTML

    assert "function startAOIDrawing()" in APP_JS
    assert "function finishAOIDrawing()" in APP_JS
    assert "drawingPoints.length<3" in APP_JS
    assert "__custom_aoi:true" in APP_JS
    assert "admin_level:level" in APP_JS


def test_public_faostat_trend_scenario_is_not_blocked_by_user_login():
    forecast = section(APP_JS, "async function runGlobalYieldForecast()", "$('global-item-type')")
    assert "openAuth()" not in forecast
    assert "'/global-predictions/yield'" in forecast
