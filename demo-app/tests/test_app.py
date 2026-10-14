from fastapi.testclient import TestClient 


from app import app 

client = TestClient(app)

def test_index_reports_configured_version(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "test-v1")

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "deploybox-demo",
        "version": "test-v1",
    }

def test_index_defaults_to_dev(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["version"] == "dev"


def test_health_is_healthy_by_default(monkeypatch):
    monkeypatch.delenv("FAIL_HEALTH", raising=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_health_can_fail(monkeypatch):
    monkeypatch.setenv("FAIL_HEALTH", "1")

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy"}