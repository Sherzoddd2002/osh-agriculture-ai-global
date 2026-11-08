from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from threading import Thread
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "index.html"
ASSETS = ROOT / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
frames = []
server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT / "docs")))
Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}/"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 920}, device_scale_factor=1)
    page_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
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

    # Browser smoke test: draw a small custom AOI and ensure analysis is enabled.
    page.locator("#region-draw-start").click()
    canvas = page.locator("#map canvas").first
    canvas.click(position={"x": 480, "y": 210})
    canvas.click(position={"x": 555, "y": 215})
    canvas.click(position={"x": 520, "y": 285})
    page.locator("#region-draw-finish").click()
    page.wait_for_function(
        "() => !document.querySelector('#region-analyze').disabled && "
        "document.querySelector('#region-name').textContent.includes('Foydalanuvchi')",
        timeout=10000,
    )
    page.locator("#region-analyze").click()
    page.wait_for_timeout(8000)
    frames.append(Image.open(__import__("io").BytesIO(page.screenshot(full_page=True))).convert("RGB"))

    # Forecast smoke test uses an isolated CI-only fixture; it is never saved
    # into the public screenshot or the user's data.
    fixture_csv = (
        "year,yield_t_ha\\n"
        "2015,3.72\\n2016,3.81\\n2017,3.76\\n2018,3.94\\n"
        "2019,4.02\\n2020,3.88\\n2021,4.11\\n2022,4.18\\n"
    )
    page.locator("#region-yield-file").set_input_files({
        "name": "ci-yield-smoke.csv",
        "mimeType": "text/csv",
        "buffer": fixture_csv.encode("utf-8"),
    })
    page.locator("#region-run-model").click()
    page.wait_for_function(
        "() => document.querySelector('#region-model-result').textContent.includes('Ridge + ERA5-Land ssenariysi') "
        "|| document.querySelector('#region-model-result').textContent.includes('AI ssenariysi ishga tushmadi')",
        timeout=90000,
    )
    model_text = page.locator("#region-model-result").inner_text()
    if "Ridge + ERA5-Land ssenariysi" not in model_text:
        raise RuntimeError("ERA5-Land/Ridge forecast smoke test failed: " + model_text)
    if page_errors:
        raise RuntimeError("Browser JavaScript errors: " + " | ".join(page_errors))
    browser.close()

server.shutdown()

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
