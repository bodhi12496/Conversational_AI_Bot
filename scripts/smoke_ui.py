"""Browser smoke test for the redesigned UI. Uses synthetic data only."""

import os
import time
import urllib.error
import urllib.request

from playwright.sync_api import expect, sync_playwright

BASE = os.getenv("COE_BASE_URL", "http://127.0.0.1:8000")
deadline = time.monotonic() + 20
while True:
    try:
        urllib.request.urlopen(BASE + "/health", timeout=1).close()
        break
    except (urllib.error.URLError, TimeoutError):
        if time.monotonic() > deadline:
            raise
        time.sleep(0.2)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv("COE_CHROMIUM_PATH"))
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(BASE)
    if os.getenv("COE_API_TOKEN"):
        page.get_by_role("button", name="API connection settings", exact=True).click()
        page.get_by_label("API token", exact=True).fill(os.environ["COE_API_TOKEN"])
        page.get_by_role("button", name="Reconnect", exact=True).click()
    page.get_by_role("button", name="New project", exact=True).click()
    page.get_by_label("Project name").fill("Browser verified redesigned UI")
    page.get_by_role("dialog").get_by_role("button", name="Create project", exact=True).click()
    page.get_by_role("button", name="Try sample data", exact=True).click()
    expect(page.get_by_text("Sample data loaded.", exact=False)).to_be_visible()
    nav = page.get_by_role("navigation", name="Main navigation")
    nav.get_by_role("button", name="Semantic model", exact=True).click()
    for message in [
        "Define revenue as amount minus refund in sales.",
        "Exclude cancelled orders from sales.",
        "Link sales.product_id to inventory.product_id as many_to_one.",
    ]:
        page.get_by_role("button", name="Edit with AI", exact=True).click()
        page.get_by_label("What would you like to change?", exact=True).fill(message)
        page.get_by_role("button", name="Preview change", exact=True).click()
        page.get_by_role("button", name="Save to draft", exact=True).click()
        expect(page.get_by_text("Change saved to a new draft.", exact=False)).to_be_visible()
    nav.get_by_role("button", name="Agent setup", exact=True).click()
    page.get_by_role("checkbox", name="I reviewed the definitions", exact=False).check()
    page.get_by_role("button", name="Publish v6", exact=True).click()
    expect(page.get_by_text("Assistant published.", exact=False)).to_be_visible()
    nav.get_by_role("button", name="Chat", exact=True).click()
    page.get_by_role("textbox", name="Ask your data", exact=True).fill(
        "Show sales.revenue and inventory.total_stock by sales.product_id."
    )
    page.get_by_role("button", name="Send", exact=True).click()
    expect(page.get_by_role("cell", name="290", exact=True)).to_be_visible()
    expect(page.get_by_role("cell", name="12", exact=True)).to_be_visible()
    nav.get_by_role("button", name="Overview", exact=True).click()
    if os.getenv("COE_QA_SCREENSHOT"):
        page.screenshot(path=os.environ["COE_QA_SCREENSHOT"], full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    for destination in [
        "Overview",
        "Data sources",
        "Semantic model",
        "Agent setup",
        "Chat",
        "Activity & versions",
    ]:
        nav.get_by_role("button", name=destination, exact=True).click()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
            destination + " overflows"
        )
    assert not errors, errors
    browser.close()
print("Browser walkthrough and responsive layout checks passed.")
