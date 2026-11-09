"""Assemble the full FastAPI frontend as the public GitHub Pages homepage.

GitHub Pages serves the static frontend; API-backed actions call the Fly.io
FastAPI service. Relative asset paths keep both Pages and Fly root hosting valid.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"
FLY_TOML = ROOT / "fly.toml"


def fly_app_name() -> str:
    text = FLY_TOML.read_text(encoding="utf-8")
    match = re.search(r'^\s*app\s*=\s*"([a-z0-9-]+)"\s*$', text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("Cannot determine Fly app name from fly.toml")
    return match.group(1)


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    app_name = fly_app_name()
    api_origin = f"https://{app_name}.fly.dev"

    source_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for old, new in (
        ('href="/styles.css"', 'href="./styles.css"'),
        ('src="/i18n.js"', 'src="./i18n.js"'),
        ('src="/app.js"', 'src="./app.js"'),
    ):
        source_html = source_html.replace(old, new)
    app_script = '<script src="./app.js"></script>'
    if app_script not in source_html:
        raise RuntimeError("Frontend app.js script tag not found")
    if "OSH_API_BASE" in source_html:
        raise RuntimeError("API base should be injected only by the Pages assembler")
    config_script = (
        f'<script>window.OSH_API_BASE = "{api_origin}";</script>\n'
    )
    source_html = source_html.replace(app_script, config_script + app_script)
    if 'href="/styles.css"' in source_html or 'src="/app.js"' in source_html:
        raise RuntimeError("Absolute root paths are incompatible with project GitHub Pages")

    (DOCS / "index.html").write_text(source_html, encoding="utf-8")
    for name in ("app.js", "i18n.js", "styles.css"):
        shutil.copy2(FRONTEND / name, DOCS / name)

    assets_out = DOCS / "assets"
    assets_out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FRONTEND / "assets" / "hero-field.jpg", assets_out / "hero-field.jpg")

    print(f"PASS assembled full frontend: {api_origin}")
    print("PASS copied app.js, i18n.js, styles.css and hero-field.jpg")
    print("PASS static boundary bundles remain available under docs/data/boundaries/")


if __name__ == "__main__":
    main()
