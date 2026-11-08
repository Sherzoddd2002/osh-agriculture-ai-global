"""Public GitHub Pages integration, data and JavaScript integrity checks."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
HTML_PATH = DOCS / "index.html"
html = HTML_PATH.read_text(encoding="utf-8")

required_ids = {
    "map", "region-iso3", "region-level", "region-load", "region-search",
    "region-select", "region-analyze", "region-yield-file", "region-run-model",
    "region-model-result", "region-crop-select", "region-mapspam-result", "crop-select", "crop-chips",
}
found_ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', html))
missing = sorted(required_ids - found_ids)
if missing:
    raise SystemExit(f"FAIL: missing required UI IDs: {missing}")

if "fly.dev" in html.lower() or "osh backend" in html.lower():
    raise SystemExit("FAIL: public GitHub Pages HTML still references a private backend/Fly service")

if "./data/boundaries/" not in html:
    raise SystemExit("FAIL: static GitHub Pages GeoJSON path is not wired into the UI")

# Static Uzbekistan ADM must boot before the optional external world-country layer.
adm_source_position = html.find('map.addSource("admin-areas"')
world_fetch_position = html.find(
    'fetch("https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson"'
)
map_load_position = html.find('map.on("load",async function(){')
auto_adm_position = html.find("loadRegionBoundaries();", map_load_position)
if min(adm_source_position, world_fetch_position, map_load_position, auto_adm_position) < 0:
    raise SystemExit("FAIL: map bootstrap is missing its static ADM or country GeoJSON wiring")
if not (map_load_position < adm_source_position < auto_adm_position < world_fetch_position):
    raise SystemExit("FAIL: UZB ADM layers must initialize and load before the optional world-country GeoJSON")
if "World-country outlines are optional" not in html:
    raise SystemExit("FAIL: world-country network failure is not isolated from the static ADM layer")
if "features.includes(f)" not in html:
    raise SystemExit("FAIL: country feature-state updates must ignore the local UZB fallback feature")
if "clearYieldInputOnContextChange" not in html:
    raise SystemExit("FAIL: stale yield CSV invalidation is missing")
if "html{scroll-padding-top:132px}" not in html or "aria-label=\"Maydon tahlili\"" not in html:
    raise SystemExit("FAIL: mobile navigation offset or accessible section labels are missing")

if html.count('$("region-run-model").addEventListener("click"') != 1:
    raise SystemExit("FAIL: AI prediction button must have exactly one click handler")
if html.count('$("region-yield-file").addEventListener("change"') != 1:
    raise SystemExit("FAIL: CSV upload control must have exactly one change handler")

if 'region-crop-select' not in html or '$("region-crop-select").addEventListener("change"' not in html:
    raise SystemExit("FAIL: AI crop selector is not available and synchronized with MAPSPAM")
if 'id="region-crop-select"' not in html[:html.index('id="region-run-model"')]:
    raise SystemExit("FAIL: choose the AI crop before opening model analysis")

if not all(label in html for label in ("ADM1 · Viloyatlar", "ADM2 · Tumanlar")):
    raise SystemExit("FAIL: public district selector must expose ADM1 and ADM2 only")
if "loadRegionBoundaries();" not in html:
    raise SystemExit("FAIL: default Uzbekistan ADM2 layer is not auto-loaded")
if "fetchYieldClimateHistory(center,series" not in html or "Persistence" not in html:
    raise SystemExit("FAIL: browser ML is not linked to historic ERA5-Land and Persistence validation")
if "./data/templates/yield-template.csv" not in html:
    raise SystemExit("FAIL: local CSV template download is not linked")

crop_match = re.search(r"const cropList=\[(.*?)\n\s*\];", html, flags=re.DOTALL)
if not crop_match:
    raise SystemExit("FAIL: MAPSPAM crop catalogue block was not found")
crop_pairs = re.findall(r'\["([a-z]{4})","([^"]+)"\]', crop_match.group(1))
crop_codes = [code for code, _ in crop_pairs]
if len(crop_codes) != 46 or len(set(crop_codes)) != 46:
    raise SystemExit(
        f"FAIL: MAPSPAM catalogue must contain 46 unique crop codes; found {len(crop_codes)}"
    )

# The boundary files are produced earlier in the same Pages workflow. Check the
# actual generated artifacts, not just the builder's source code.
boundary_dir = DOCS / "data" / "boundaries"
manifest_path = boundary_dir / "manifest.json"
if not manifest_path.is_file():
    raise SystemExit("FAIL: public boundary manifest missing from Pages build artifact")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("country_iso3") != "UZB":
    raise SystemExit("FAIL: boundary manifest country is not UZB")

boundary_ids_by_level: dict[str, dict[str, str]] = {}
for level, expected_count in (("ADM1", 14), ("ADM2", 199)):
    details = (manifest.get("levels") or {}).get(level) or {}
    filename = details.get("file")
    if not filename:
        raise SystemExit(f"FAIL: UZB {level} manifest filename missing")
    path = boundary_dir.parent / filename
    if not path.is_file():
        raise SystemExit(f"FAIL: UZB {level} GeoJSON missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise SystemExit(f"FAIL: UZB {level} is not a FeatureCollection")
    if len(payload.get("features", [])) != expected_count:
        raise SystemExit(
            f"FAIL: UZB {level} expected {expected_count} features, "
            f"received {len(payload.get('features', []))}"
        )
    metadata = payload.get("metadata") or {}
    if metadata.get("country_iso3") != "UZB" or metadata.get("admin_level") != level:
        raise SystemExit(f"FAIL: UZB {level} metadata identity mismatch")
    boundary_ids: dict[str, str] = {}
    for index, feature in enumerate(payload["features"]):
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        if not geometry:
            raise SystemExit(f"FAIL: UZB {level} feature {index} has no geometry")
        parsed = shape(geometry)
        if parsed.is_empty or not parsed.is_valid or parsed.geom_type not in {"Polygon", "MultiPolygon"}:
            raise SystemExit(f"FAIL: UZB {level} feature {index} has invalid geometry")
        props = feature.get("properties") or {}
        shape_id = str(props.get("shapeID") or "")
        shape_name = str(props.get("shapeName") or "")
        if not shape_id or not shape_name or shape_id in boundary_ids:
            raise SystemExit(f"FAIL: UZB {level} feature {index} has missing/duplicate shapeID or shapeName")
        boundary_ids[shape_id] = shape_name
    boundary_ids_by_level[level] = boundary_ids
    print(f"PASS: UZB {level}: {len(payload['features'])} valid polygon features")

official_info = manifest.get("official_yield") or {}
official_path = DOCS / "data" / str(official_info.get("file") or "")
if not official_path.is_file():
    raise SystemExit("FAIL: official SIAT wheat province dataset missing")
official = json.loads(official_path.read_text(encoding="utf-8"))
if official.get("admin_level") != "ADM1" or official.get("crop_code") != "whea":
    raise SystemExit("FAIL: official SIAT dataset must be UZB ADM1 wheat")
if official.get("license") != "CC BY 4.0" or official.get("district_yield_available") is not False:
    raise SystemExit("FAIL: official SIAT dataset provenance or geographic scope is missing")
if len(official.get("regions", [])) != 13:
    raise SystemExit("FAIL: expected 13 agricultural province yield series from SIAT")
for region in official["regions"]:
    records = region.get("records", [])
    years = [row.get("year") for row in records]
    if len(records) < 12 or years != sorted(set(years)):
        raise SystemExit(f"FAIL: incomplete or duplicate official SIAT series for {region.get('name_uz')}")
    for row in records:
        value = row.get("yield")
        if not isinstance(value, (int, float)) or not 0 < value < 30:
            raise SystemExit(f"FAIL: invalid official wheat yield row: {region.get('name_uz')} / {row}")
print(f"PASS SIAT province wheat yield: {len(official['regions'])} regions, {sum(len(r['records']) for r in official['regions'])} records")

# The public MAPSPAM snapshot is built from the real-data Actions artifact and
# joined by exact geoBoundaries shapeID, not by approximate district-name text.
mapspam_path = DOCS / "data" / "mapspam" / "UZB_MAPSPAM_2020_ADM1_ADM2.json"
if not mapspam_path.is_file():
    raise SystemExit("FAIL: validated public MAPSPAM 2020 ADM1/ADM2 dataset is missing")
mapspam = json.loads(mapspam_path.read_text(encoding="utf-8"))
if (
    mapspam.get("country_iso3") != "UZB"
    or mapspam.get("dataset_id") != "mapspam-2020-v2r2"
    or mapspam.get("source_year") != 2020
    or mapspam.get("technology") != "all"
    or mapspam.get("license") != "CC BY-SA 4.0"
    or mapspam.get("source_url") != "https://doi.org/10.7910/DVN/SWPENT"
):
    raise SystemExit("FAIL: MAPSPAM public snapshot metadata/license/source is invalid")
if "renderMapspamReference" not in html or "./data/mapspam/UZB_MAPSPAM_2020_ADM1_ADM2.json" not in html:
    raise SystemExit("FAIL: MAPSPAM 2020 public data is not connected to the selected-area UI")
if "NO_RASTER_CELLS" not in html or "NULL / mavjud emas" not in html:
    raise SystemExit("FAIL: no-raster-cell MAPSPAM rows must display NULL, not zero yield")
mapspam_levels = mapspam.get("levels") or {}
for level, expected_count in (("ADM1", 14), ("ADM2", 199)):
    level_data = mapspam_levels.get(level) or {}
    areas = level_data.get("areas") or {}
    if level_data.get("area_count") != expected_count or set(areas) != set(boundary_ids_by_level[level]):
        raise SystemExit(f"FAIL: MAPSPAM {level} area IDs/count do not match public boundaries")
    if level_data.get("crop_count") != 46:
        raise SystemExit(f"FAIL: MAPSPAM {level} does not declare 46 crop layers")
    if str(level_data.get("boundary_year")) != str((manifest.get("levels") or {}).get(level, {}).get("boundary_year")):
        raise SystemExit(f"FAIL: MAPSPAM {level} boundary vintage does not match public GeoJSON")
    for area_id, area in areas.items():
        if area.get("name") != boundary_ids_by_level[level][area_id]:
            raise SystemExit(f"FAIL: MAPSPAM {level} area name does not match its shapeID")
        crops = area.get("crops") or {}
        if set(crops) != set(crop_codes):
            raise SystemExit(f"FAIL: MAPSPAM {level} {area_id} must contain exactly 46 crop rows")
        if level == "ADM2" and area.get("parent_admin_id") not in mapspam_levels.get("ADM1", {}).get("areas", {}):
            raise SystemExit(f"FAIL: MAPSPAM ADM2 {area_id} has an unknown ADM1 parent")
        for crop_code, row in crops.items():
            status = row.get("spatial_status")
            cells = row.get("valid_cells")
            yield_value = row.get("yield_t_ha")
            if status == "NO_RASTER_CELLS":
                if cells != 0 or yield_value is not None:
                    raise SystemExit(f"FAIL: MAPSPAM {level}/{area_id}/{crop_code} must keep NULL yield when no raster cells exist")
            elif status == "ESTIMATED":
                if not isinstance(cells, int) or cells <= 0 or not isinstance(yield_value, (int, float)) or not 0 < yield_value < 200:
                    raise SystemExit(f"FAIL: MAPSPAM {level}/{area_id}/{crop_code} has invalid estimated yield/cell count")
            else:
                raise SystemExit(f"FAIL: MAPSPAM {level}/{area_id}/{crop_code} has unknown spatial status")
            for field in ("physical_area_ha", "harvested_area_ha", "production_t"):
                value = row.get(field)
                if not isinstance(value, (int, float)) or not (value >= 0):
                    raise SystemExit(f"FAIL: MAPSPAM {level}/{area_id}/{crop_code} invalid {field}")
print(
    "PASS MAPSPAM 2020 public reference: "
    f"{mapspam_levels['ADM1']['area_count']} ADM1 / "
    f"{mapspam_levels['ADM2']['area_count']} ADM2 / 46 crops; "
    "shapeID and parent links verified"
)

scripts = re.findall(r"<script>([\s\S]*?)</script>", html, flags=re.IGNORECASE)
if len(scripts) != 1:
    raise SystemExit(f"FAIL: expected one inline dashboard script, found {len(scripts)}")

with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as temp:
    temp.write(scripts[0])
    temp_path = temp.name
try:
    subprocess.run(["node", "--check", temp_path], check=True)
finally:
    Path(temp_path).unlink(missing_ok=True)

subprocess.run(["node", str(ROOT / "scripts" / "test_public_model.mjs")], check=True)
subprocess.run(["node", str(ROOT / "scripts" / "test_public_map_names.mjs")], check=True)

print("PASS: dashboard IDs, Pages-only API wiring, 46 crops, localized ADM names, polygon centroids and JavaScript syntax")
