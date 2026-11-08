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
    "region-model-result", "region-crop-select", "crop-select", "crop-chips",
}
found_ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', html))
missing = sorted(required_ids - found_ids)
if missing:
    raise SystemExit(f"FAIL: missing required UI IDs: {missing}")

if "fly.dev" in html.lower() or "osh backend" in html.lower():
    raise SystemExit("FAIL: public GitHub Pages HTML still references a private backend/Fly service")

if "./data/boundaries/" not in html:
    raise SystemExit("FAIL: static GitHub Pages GeoJSON path is not wired into the UI")

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
    for index, feature in enumerate(payload["features"]):
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        if not geometry:
            raise SystemExit(f"FAIL: UZB {level} feature {index} has no geometry")
        parsed = shape(geometry)
        if parsed.is_empty or not parsed.is_valid or parsed.geom_type not in {"Polygon", "MultiPolygon"}:
            raise SystemExit(f"FAIL: UZB {level} feature {index} has invalid geometry")
    print(f"PASS: UZB {level}: {len(payload['features'])} valid polygon features")

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
