"""Run the complete core flow against an already running local server."""

import json
import os
import urllib.error
import urllib.request

BASE = os.getenv("COE_BASE_URL", "http://127.0.0.1:8000")


def api(path, data=None):
    headers = {"Content-Type": "application/json"}
    token = os.getenv("COE_API_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        BASE + "/api" + path, headers=headers, data=json.dumps(data).encode() if data is not None else None
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode()) from exc


def main():
    project = api("/projects", {"name": "Verified sales & inventory demo"})
    prefix = "/projects/" + project["id"]
    api(prefix + "/demo", {})
    for message in [
        "Define revenue as amount minus refund in sales.",
        "Exclude cancelled orders from sales.",
        "Set grain of sales to one row per order.",
        "Link sales.product_id to inventory.product_id as many_to_one.",
    ]:
        state = api(prefix)
        proposal = api(prefix + "/changes", {"base_version": state["project"]["head"], "message": message})
        assert proposal.get("validation", {}).get("valid"), proposal
        api(prefix + "/proposals/" + proposal["id"] + "/apply", {})
    # Manually checked: 100-10 + 200 + 80-5 + 50 = 415, excluding the cancelled 150.
    api(
        prefix + "/regressions",
        {
            "name": "Manually checked net revenue",
            "plan": {"metrics": ["sales.revenue"]},
            "expected_rows": [{"sales.revenue": 415}],
        },
    )
    head = api(prefix)["project"]["head"]
    api(prefix + "/publish", {"version": head, "acknowledge_inferred_definitions": True})
    result = api(
        prefix + "/ask", {"message": "Show sales.revenue and inventory.total_stock by sales.product_id."}
    )
    assert result["rows"] == [
        {"sales.product_id": "P001", "sales.revenue": 290, "inventory.total_stock": 12},
        {"sales.product_id": "P002", "sales.revenue": 75, "inventory.total_stock": 3},
        {"sales.product_id": "P003", "sales.revenue": 50, "inventory.total_stock": 8},
        {"sales.product_id": "P004", "sales.revenue": None, "inventory.total_stock": 15},
    ], result
    print(json.dumps({"project": project["id"], "version": head, "verified_rows": result["rows"]}, indent=2))


if __name__ == "__main__":
    main()
