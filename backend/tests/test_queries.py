import pytest
from conftest import change, publish, state


def test_cross_view_aggregates_before_merge(client, project):
    change(client, project, "Define revenue as amount minus refund in sales.")
    change(client, project, "Exclude cancelled orders from sales.")
    change(client, project, "Link sales.product_id to inventory.product_id as many_to_one.")
    publish(client, project)
    r = client.post(
        f"/api/projects/{project}/ask",
        json={"message": "Show sales.revenue and inventory.total_stock by sales.product_id."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["rows"] == [
        {"sales.product_id": "P001", "sales.revenue": 290, "inventory.total_stock": 12},
        {"sales.product_id": "P002", "sales.revenue": 75, "inventory.total_stock": 3},
        {"sales.product_id": "P003", "sales.revenue": 50, "inventory.total_stock": 8},
        {"sales.product_id": "P004", "sales.revenue": None, "inventory.total_stock": 15},
    ]
    # Stock for P001 must remain 12 even though there are two sales rows.
    assert all("JOIN" not in q["sql"] for q in r.json()["queries"])


def test_missing_relationship_cannot_be_guessed(client, project):
    publish(client, project)
    r = client.post(
        f"/api/projects/{project}/query",
        json={
            "metrics": ["sales.total_amount", "inventory.total_stock"],
            "group_by": "sales.product_id",
        },
    )
    assert r.status_code == 422
    assert "relationship" in r.json()["detail"]


def test_false_cardinality_blocks_apply(client, project):
    r = client.post(
        f"/api/projects/{project}/changes",
        json={
            "base_version": state(client, project)["project"]["head"],
            "message": "Link sales.product_id to inventory.product_id as one_to_one.",
        },
    ).json()
    assert not r["validation"]["valid"]
    assert any("not unique" in e for e in r["validation"]["errors"])


def test_deselected_view_unreachable_after_publish(client, project):
    head = state(client, project)["project"]["head"]
    r = client.post(
        f"/api/projects/{project}/changes/structured",
        json={
            "base_version": head,
            "changes": {
                "summary": "Only sales",
                "operations": [{"op": "select_views", "view_ids": ["sales"]}],
            },
        },
    ).json()
    assert client.post(f"/api/projects/{project}/proposals/{r['id']}/apply").status_code == 200
    s = state(client, project)
    assert list(s["instructions"]["metric_catalog"]) == ["sales"]
    publish(client, project)
    assert (
        client.post(f"/api/projects/{project}/query", json={"metrics": ["inventory.total_stock"]}).status_code
        == 422
    )


@pytest.mark.parametrize(
    "expression",
    [
        '__import__("os").system("id")',
        "amount; DROP TABLE projects",
        "amount / refund",
        "amount ** 2",
        "email",
        "unknown + 1",
    ],
)
def test_unsafe_or_unsupported_metric_never_commits(client, project, expression):
    head = state(client, project)["project"]["head"]
    r = client.post(
        f"/api/projects/{project}/changes/structured",
        json={
            "base_version": head,
            "changes": {
                "summary": "Bad formula",
                "operations": [
                    {
                        "op": "upsert_metric",
                        "view_id": "sales",
                        "metric": {
                            "name": "bad",
                            "expression": expression,
                            "aggregation": "sum",
                            "description": "Invalid test",
                        },
                    }
                ],
            },
        },
    )
    assert r.status_code == 200, r.text
    assert not r.json()["validation"]["valid"]
    assert client.post(f"/api/projects/{project}/proposals/{r.json()['id']}/apply").status_code == 422
    assert state(client, project)["project"]["head"] == head


def test_filter_injection_remains_bound_value(client, project):
    publish(client, project)
    r = client.post(
        f"/api/projects/{project}/query",
        json={
            "metrics": ["sales.total_amount"],
            "filters": {"sales": [{"column": "status", "op": "eq", "value": "' OR 1=1 --"}]},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["rows"] == [{"sales.total_amount": None}]
    assert "?" in r.json()["queries"][0]["sql"]


def test_unsupported_question_is_not_approximated(client, project):
    publish(client, project)
    r = client.post(
        f"/api/projects/{project}/ask", json={"message": "Show revenue growth and rank top products."}
    )
    assert r.json()["clarification"]


def test_arbitrary_plan_fields_and_invalid_limit_rejected(client, project):
    assert (
        client.post(
            f"/api/projects/{project}/query",
            json={"metrics": ["sales.total_amount"], "sql": "SELECT * FROM projects"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/projects/{project}/query", json={"metrics": ["sales.total_amount"], "limit": 10000}
        ).status_code
        == 422
    )
