import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as c:
        yield c


@pytest.fixture
def project(client):
    p = client.post("/api/projects", json={"name": "Test project"}).json()
    assert client.post(f"/api/projects/{p['id']}/demo").status_code == 200
    return p["id"]


def state(client, project):
    response = client.get(f"/api/projects/{project}")
    assert response.status_code == 200, response.text
    return response.json()


def change(client, project, message):
    response = client.post(
        f"/api/projects/{project}/changes",
        json={
            "message": message,
            "base_version": state(client, project)["project"]["head"],
        },
    )
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["validation"]["valid"], proposal
    applied = client.post(f"/api/projects/{project}/proposals/{proposal['id']}/apply")
    assert applied.status_code == 200, applied.text
    return applied.json()["version"]


def publish(client, project):
    version = state(client, project)["project"]["head"]
    r = client.post(
        f"/api/projects/{project}/publish",
        json={
            "version": version,
            "acknowledge_inferred_definitions": True,
        },
    )
    assert r.status_code == 200, r.text
    return version
