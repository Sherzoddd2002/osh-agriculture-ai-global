from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
import time

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "index.html"
ASSETS = ROOT / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
frames = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 920}, device_scale_factor=1)
    page.goto(PAGE.as_uri(), wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("#map canvas", timeout=30000)
        page.wait_for_timeout(9000)
    except Exception:
        # Keep the designed UI screenshot even if a third-party map tile host is slow.
        page.wait_for_timeout(5000)

    frames.append(Image.open(__import__("io").BytesIO(page.screenshot(full_page=True))).convert("RGB"))
    page.evaluate("window.__setDemoState && window.__setDemoState('selected')")
    page.wait_for_timeout(1300)
    frames.append(Image.open(__import__("io").BytesIO(page.screenshot(full_page=True))).convert("RGB"))
    page.evaluate("window.__setDemoState && window.__setDemoState('result')")
    page.wait_for_timeout(900)
    frames.append(Image.open(__import__("io").BytesIO(page.screenshot(full_page=True))).convert("RGB"))
    browser.close()

# README screenshot is the selected-country state, not a synthetic forecast result.
frames[1].save(ASSETS / "osh-global-preview.png", optimize=True)
# Compact animated walkthrough: globe -> selected country -> honest API readiness notice.
frames[0].save(
    ASSETS / "demo-walkthrough.gif",
    save_all=True,
    append_images=frames[1:],
    duration=[1300, 1500, 2200],
    loop=0,
    optimize=True,
)
print("Created public demo screenshot and walkthrough GIF.")
