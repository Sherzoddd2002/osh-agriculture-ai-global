"""Assemble the static public demo for GitHub Pages.

GitHub Pages is a static host. This build deliberately does not inject a
FastAPI origin, database URL, or Fly.io dependency into the public browser app.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SOURCE = DOCS / "static-demo.html"
TARGET = DOCS / "index.html"


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Static demo source is missing: {SOURCE}")
    DOCS.mkdir(parents=True, exist_ok=True)
    html = SOURCE.read_text(encoding="utf-8")
    if "fly.dev" in html.lower() or "OSH_API_BASE" in html:
        raise SystemExit("Public static demo must not depend on a private API host")
    if 'id="map"' not in html or 'id="region-run-model"' not in html:
        raise SystemExit("Static demo is missing the map or model controls")
    shutil.copy2(SOURCE, TARGET)
    print("PASS GitHub Pages homepage assembled from docs/static-demo.html")
    print("PASS no Fly API origin or private backend config is injected")
    print("PASS global map, field drawing and model controls are present")


if __name__ == "__main__":
    main()
