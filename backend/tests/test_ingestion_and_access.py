import io

import pytest
from app.config import Settings
from app.main import create_app
from conftest import publish, state
from fastapi.testclient import TestClient
from openpyxl import Workbook


def create(client):
    return client.post("/api/projects", json={"name": "Imports"}).json()["id"]


def upload(client, pid, content, filename="data.csv"):
    return client.post(f"/api/projects/{pid}/datasets", files={"file": (filename, content)})


def test_profile_keeps_identifier_zeroes_and_blocks_sensitive_columns(client):
    pid = create(client)
    r = upload(client, pid, b"customer_id,email,value\n001,a@b.com,10\n002,c@b.com,20\n")
    assert r.status_code == 201, r.text
    s = state(client, pid)
    columns = {c["name"]: c for c in s["model"]["views"][0]["columns"]}
    assert columns["customer_id"]["dtype"] == "text"
    assert columns["email"]["sensitive"]
    publish(client, pid)
    r = client.post(
        f"/api/projects/{pid}/query", json={"metrics": ["data.total_value"], "group_by": "data.customer_id"}
    )
    assert r.json()["rows"][0]["data.customer_id"] == "001"
    assert (
        client.post(
            f"/api/projects/{pid}/query", json={"metrics": ["data.row_count"], "group_by": "data.email"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "content,filename",
    [
        (b"a,A\n1,2\n", "bad.csv"),
        (b"a,b\n1\n", "bad.csv"),
        (b"a,b\n", "empty.csv"),
        (b",b\n1,2\n", "no_header.csv"),
        (b"not an xlsx", "bad.xlsx"),
        (b"a\n1", "bad.json"),
    ],
)
def test_bad_upload_is_atomic(client, content, filename):
    pid = create(client)
    assert upload(client, pid, content, filename).status_code == 422
    s = state(client, pid)
    assert s["project"]["head"] == 1
    assert s["datasets"] == []


def test_row_and_size_limits(client):
    pid = create(client)
    assert upload(client, pid, b"value\n" + b"1\n" * 25001).status_code == 413
    assert upload(client, pid, b"x" * (5 * 1024 * 1024 + 1)).status_code == 413


def test_xlsx_values_supported_and_formula_rejected(client):
    pid = create(client)
    book = Workbook()
    sheet = book.active
    sheet.append(["product_id", "amount"])
    sheet.append(["001", 42])
    stream = io.BytesIO()
    book.save(stream)
    assert upload(client, pid, stream.getvalue(), "orders.xlsx").status_code == 201
    sheet["B2"] = "=1+2"
    stream = io.BytesIO()
    book.save(stream)
    assert upload(client, pid, stream.getvalue(), "formulas.xlsx").status_code == 422


def test_project_scoping_rejects_foreign_proposals_and_runs(client, project):
    foreign = create(client)
    head = state(client, project)["project"]["head"]
    p = client.post(
        f"/api/projects/{project}/changes",
        json={"base_version": head, "message": "Set grain of sales to one row per order."},
    ).json()
    assert client.post(f"/api/projects/{foreign}/proposals/{p['id']}/apply").status_code == 404
    publish(client, project)
    r = client.post(f"/api/projects/{project}/ask", json={"message": "Show sales.total_amount."}).json()
    assert client.get(f"/api/projects/{foreign}/runs/{r['id']}").status_code == 404


def test_token_origin_and_host_boundaries(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, api_token="secret"))) as c:
        assert c.get("/api/projects").status_code == 401
        assert c.get("/api/projects", headers={"Authorization": "Bearer secret"}).status_code == 200
        assert (
            c.post(
                "/api/projects",
                json={"name": "x"},
                headers={"Authorization": "Bearer secret", "Origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        assert c.get("/health", headers={"Host": "untrusted.example"}).status_code == 400


def test_null_keys_and_type_mismatch_block_relationship(client):
    pid = create(client)
    upload(client, pid, b"product_id,value\nP1,10\n,20\n", "left.csv")
    upload(client, pid, b"product_id,stock\nP1,4\n", "right.csv")
    p = client.post(
        f"/api/projects/{pid}/changes",
        json={
            "base_version": state(client, pid)["project"]["head"],
            "message": "Link left.product_id to right.product_id as many_to_one.",
        },
    ).json()
    assert not p["validation"]["valid"]
    assert any("null" in e for e in p["validation"]["errors"])


def test_group_limits_fail_closed_instead_of_merging_partial_data(client):
    pid = create(client)
    upload(client, pid, ("id,value\n" + "".join(f"P{i},1\n" for i in range(501))).encode())
    publish(client, pid)
    assert (
        client.post(
            f"/api/projects/{pid}/query", json={"metrics": ["data.total_value"], "group_by": "data.id"}
        ).status_code
        == 422
    )
