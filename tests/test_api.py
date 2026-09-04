from fastapi.testclient import TestClient

from helixgate.api.main import app

client = TestClient(app)


def test_health_and_docs():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "helixgate"
    assert client.get("/").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/docs").status_code == 200


def test_token_invoke_roundtrip():
    token = client.post("/api/gateway/token", json={"audience": "cc-api", "subject": "qa"}).json()["token"]
    allowed = client.post("/api/gateway/invoke", json={"route_id": "rt-creative-cloud", "token": token})
    assert allowed.status_code == 200
    assert allowed.json()["status"] in {200, 429}


def test_wrong_audience_is_unauthorized():
    token = client.post("/api/gateway/token", json={"audience": "firefly", "subject": "qa"}).json()["token"]
    denied = client.post("/api/gateway/invoke", json={"route_id": "rt-creative-cloud", "token": token})
    assert denied.json()["status"] == 401
