from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_search_filters_by_topic():
    response = client.get("/api/agenda", params={"topic": "housing"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "approved"


def test_search_matches_summary():
    response = client.get("/api/agenda", params={"q": "stormwater"})
    assert response.status_code == 200
    assert response.json()[0]["id"] == "a-103"

