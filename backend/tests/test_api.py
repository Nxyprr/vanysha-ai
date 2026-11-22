"""Pruebas de la API completa. Requieren: pip install -r requirements-dev.txt"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ADMIN = {"email": "admin@vanysha.ai", "password": "ClaveDePrueba123"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def auth(client, creds=ADMIN):
    r = client.post("/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_health_is_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["mode"] == "DEMO"


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": ADMIN["email"], "password": "mala"})
    assert r.status_code == 401


def test_requires_token(client):
    assert client.get("/api/alerts").status_code == 401


def test_admin_creates_user_and_roles_are_enforced(client):
    h = auth(client)
    r = client.post("/api/users", headers=h, json={"name": "Aud Itor", "email": "aud@x.com", "role": "auditor", "password": "Auditoria123"})
    assert r.status_code == 201
    ha = auth(client, {"email": "aud@x.com", "password": "Auditoria123"})
    assert client.get("/api/users", headers=ha).status_code == 403                       # solo admin
    assert client.get("/api/audit", headers=ha).status_code == 200                       # auditor sí ve auditoría
    assert client.post("/api/analyses", headers=ha, json={"scenario": "seg", "alert": True}).status_code == 403
    assert client.post("/api/users", headers=h, json={"name": "Aud Itor", "email": "aud@x.com", "role": "auditor", "password": "Auditoria123"}).status_code == 409


def test_cannot_delete_self_or_last_admin(client):
    h = auth(client)
    me = client.get("/api/auth/me", headers=h).json()
    assert client.delete("/api/users/" + me["id"], headers=h).status_code == 400


def test_analysis_creates_alert_and_can_be_reviewed(client):
    h = auth(client)
    r = client.post("/api/analyses", headers=h, json={"scenario": "alm", "alert": True})
    assert r.status_code == 201 and r.json()["alert"]["r"] == "Zona restringida"
    aid = r.json()["alert"]["id"]
    p = client.patch("/api/alerts/" + aid, headers=h, json={"status": "revisada", "note": "ok"})
    assert p.json()["e"] == "revisada" and p.json()["n"] == "ok"
    assert client.patch("/api/alerts/" + aid, headers=h, json={"status": "rara"}).status_code == 400


def test_disabled_rule_creates_no_alert(client):
    h = auth(client)
    client.patch("/api/rules/ret", headers=h, json={"enabled": False})
    r = client.post("/api/analyses", headers=h, json={"scenario": "ret", "alert": True})
    assert r.json()["alert"] is None
    client.patch("/api/rules/ret", headers=h, json={"enabled": True})


def test_csv_export(client):
    h = auth(client)
    r = client.get("/api/analyses.csv", headers=h)
    assert r.status_code == 200 and r.text.startswith("id,fecha,escenario")


def test_evidence_path_traversal_blocked(client):
    h = auth(client)
    assert client.get("/api/alerts/..%2F..%2Fetc/evidence", headers=h).status_code in (400, 404)
