from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200


def test_free_fall_endpoint():
    payload = {"height": 50.0, "mass": 1.0, "gravity": 9.81}
    response = client.post("/api/experiments/analyze/free-fall", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "parameters" in data
    assert "series" in data
