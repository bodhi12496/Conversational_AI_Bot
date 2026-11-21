from concurrent.futures import ThreadPoolExecutor

from app.config import Settings
from app.main import create_app
from conftest import change, publish, state
from fastapi.testclient import TestClient


def test_complete_correction_flow_pins_published_answers(client, project):
    assert (
        client.post(f"/api/projects/{project}/ask", json={"message": "Show sales.total_amount."}).status_code
        == 422
    )
    original = publish(client, project)
    r = client.post(f"/api/projects/{project}/ask", json={"message": "Show sales.total_amount."}).json()
    assert r["rows"] == [{"sales.total_amount": 580}]
    assert r["version"] == original
    change(client, project, "Define revenue as amount minus refund in sales.")
    change(client, project, "Exclude cancelled orders from sales.")
    # An unpublished definition is not reachable by the published runtime.
    r = client.post(f"/api/projects/{project}/ask", json={"message": "Show sales.revenue."}).json()
    assert "clarification" in r
    active = publish(client, project)
    r = client.post(f"/api/projects/{project}/ask", json={"message": "Show sales.revenue."}).json()
    assert r["rows"] == [{"sales.revenue": 415}]
    assert r["version"] == active
    assert r["evidence"][0]["view_filters"][0]["value"] == "cancelled"
    assert r["evidence"][0]["sha256"]
    assert client.get(f"/api/projects/{project}/runs/{r['id']}").json()["rows"] == r["rows"]


def test_stale_and_double_apply_rejected(client, project):
    base = state(client, project)["project"]["head"]
    body = {"base_version": base, "message": "Set grain of sales to one row per order."}
    a = client.post(f"/api/projects/{project}/changes", json=body).json()
    b = client.post(f"/api/projects/{project}/changes", json=body).json()
    assert client.post(f"/api/projects/{project}/proposals/{a['id']}/apply").status_code == 200
    assert client.post(f"/api/projects/{project}/proposals/{a['id']}/apply").status_code == 409
    assert client.post(f"/api/projects/{project}/proposals/{b['id']}/apply").status_code == 409
    assert client.post(f"/api/projects/{project}/changes", json=body).status_code == 409


def test_concurrent_apply_has_one_winner(client, project):
    base = state(client, project)["project"]["head"]
    props = [
        client.post(
            f"/api/projects/{project}/changes",
            json={"base_version": base, "message": f"Describe sales.amount as Definition {i}."},
        ).json()["id"]
        for i in range(2)
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda pid: client.post(f"/api/projects/{project}/proposals/{pid}/apply").status_code, props
            )
        )
    assert sorted(statuses) == [200, 409]


def test_rollback_is_new_draft_and_preserves_audit(client, project):
    original = publish(client, project)
    change(client, project, "Exclude cancelled orders from sales.")
    publish(client, project)
    s = state(client, project)
    r = client.post(
        f"/api/projects/{project}/rollback",
        json={"base_version": s["project"]["head"], "target_version": original},
    )
    assert r.status_code == 200
    assert r.json()["version"] > s["project"]["head"]
    assert state(client, project)["project"]["active"] == s["project"]["active"]
    publish(client, project)
    r = client.post(f"/api/projects/{project}/ask", json={"message": "Show sales.total_amount."}).json()
    assert r["rows"] == [{"sales.total_amount": 580}]
    assert any(e["kind"] == "published" for e in client.get(f"/api/projects/{project}/audit").json())


def test_independent_reference_blocks_regression(client, project):
    change(client, project, "Define revenue as amount minus refund in sales.")
    change(client, project, "Exclude cancelled orders from sales.")
    r = client.post(
        f"/api/projects/{project}/regressions",
        json={
            "name": "Finance checked net revenue",
            "plan": {"metrics": ["sales.revenue"]},
            "expected_rows": [{"sales.revenue": 415}],
        },
    )
    assert r.status_code == 201
    publish(client, project)
    head = state(client, project)["project"]["head"]
    r = client.post(
        f"/api/projects/{project}/changes",
        json={
            "base_version": head,
            "message": "Define revenue as amount in sales.",
        },
    ).json()
    assert not r["validation"]["valid"]
    assert client.post(f"/api/projects/{project}/proposals/{r['id']}/apply").status_code == 422
    assert state(client, project)["project"]["head"] == head


def test_unknown_business_request_requires_clarification(client, project):
    head = state(client, project)["project"]["head"]
    r = client.post(
        f"/api/projects/{project}/changes",
        json={
            "base_version": head,
            "message": "Fix everything so sales are correct.",
        },
    ).json()
    assert r["clarification"]
    assert state(client, project)["project"]["head"] == head


def test_publish_needs_review(client, project):
    head = state(client, project)["project"]["head"]
    assert client.post(f"/api/projects/{project}/publish", json={"version": head}).status_code == 422


def test_data_and_versions_survive_restart(tmp_path):
    settings = Settings(data_dir=tmp_path)
    with TestClient(create_app(settings)) as c:
        pid = c.post("/api/projects", json={"name": "Persistent"}).json()["id"]
        c.post(f"/api/projects/{pid}/demo")
        publish(c, pid)
    with TestClient(create_app(settings)) as c:
        assert state(c, pid)["model"]["views"][0]["id"] == "sales"
        assert c.post(f"/api/projects/{pid}/ask", json={"message": "Show sales.total_amount."}).json()[
            "rows"
        ] == [{"sales.total_amount": 580}]
