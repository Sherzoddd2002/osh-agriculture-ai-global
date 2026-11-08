"""Fast static-site integrity and inline-JavaScript syntax checks."""
from __future__ import annotations

import re
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "index.html"
html = HTML_PATH.read_text(encoding="utf-8")

required_ids = {
    "map", "region-iso3", "region-level", "region-load", "region-search",
    "region-select", "region-analyze", "region-yield-file", "region-run-model",
    "region-model-result", "crop-select", "crop-chips",
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

print("PASS: dashboard UI IDs, GitHub Pages-only boundary wiring and JavaScript syntax")
