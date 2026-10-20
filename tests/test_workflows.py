import copy

import pytest
from fastapi.testclient import TestClient

from civiclens.demo import sample_bundle
from civiclens.main import create_app
from civiclens.storage import Store


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "data.db", demo=True)) as client:
        yield client


def test_search_multiple_terms_filters_and_pagination(client):
    result = client.get(
        "/api/agenda", params={"q": "housing transit", "topic": "housing", "limit": 1}
    ).json()
    assert result["total"] == 2 and len(result["items"]) == 1
    second = client.get(
        "/api/agenda", params={"q": "housing transit", "offset": 1, "limit": 1}
    ).json()
    assert second["items"][0]["id"] != result["items"][0]["id"]
    assert client.get("/api/agenda", params={"status": "imaginary"}).status_code == 422
    assert (
        client.get(
            "/api/agenda", params={"after": "2026-12-01", "before": "2026-01-01"}
        ).status_code
        == 422
    )


def test_decision_path_links_same_reference(client):
    data = client.get("/api/agenda/demo-housing-final").json()
    assert [r["status"] for r in data["timeline"]] == ["proposed", "tabled", "approved"]
    assert all(r["meeting"]["is_demo"] for r in data["timeline"])
    assert data["item"]["source_excerpt"].startswith("FICTIONAL")
    assert client.get("/api/agenda/missing").status_code == 404


def test_import_idempotency_revisions_and_persistence(tmp_path):
    path = tmp_path / "data.db"
    store = Store(path)
    bundle = sample_bundle()
    assert store.import_bundle(bundle)["added"] == 6
    assert store.import_bundle(bundle)["unchanged"] == 6
    modified = bundle.model_copy(deep=True)
    modified.items[0].summary = "Staff corrected the expected project duration."
    assert store.import_bundle(modified)["updated"] == 1
    restarted = Store(path)
    assert len(restarted.revisions("demo-bike")) == 2
    assert len(restarted.query()) == 6


def test_invalid_foreign_key_rolls_back_entire_bundle(tmp_path):
    store = Store(tmp_path / "data.db")
    bundle = sample_bundle()
    bundle.items[-1].meeting_id = "missing-meeting"
    with pytest.raises(ValueError):
        store.import_bundle(bundle)
    assert store.meetings() == [] and store.records() == []


def test_same_reference_in_different_city_does_not_link(tmp_path):
    store = Store(tmp_path / "data.db")
    bundle = sample_bundle()
    store.import_bundle(bundle)
    other = bundle.model_copy(deep=True)
    for meeting in other.meetings:
        meeting.id = "other-" + meeting.id
        meeting.jurisdiction = "Another City"
    for item in other.items:
        item.id = "other-" + item.id
        item.meeting_id = "other-" + item.meeting_id
    store.import_bundle(other)
    first = next(row for row in store.records() if row["id"] == "demo-housing-final")
    assert len(store.timeline(first)) == 3


def test_saved_search_counts_track_new_matches_and_survive_restart(tmp_path):
    path = tmp_path / "db"
    with TestClient(create_app(path, demo=True)) as client:
        search = client.post(
            "/api/saved-searches", json={"name": "Housing", "topic": "housing"}
        ).json()
        assert client.get("/api/saved-searches").json()[0]["matches"] == 3
    with TestClient(create_app(path, demo=False)) as client:
        assert client.get("/api/saved-searches").json()[0]["id"] == search["id"]
        assert client.delete("/api/saved-searches/" + search["id"]).status_code == 204
        assert client.get("/api/saved-searches").json() == []
        assert client.delete("/api/saved-searches/" + search["id"]).status_code == 404


def test_write_protection_and_safe_sources(tmp_path):
    with TestClient(create_app(tmp_path / "db", demo=False, write_token="token")) as client:
        bundle = sample_bundle().model_dump(mode="json")
        assert client.post("/api/import", json=bundle).status_code == 401
        headers = {"X-Write-Token": "token"}
        unsafe = copy.deepcopy(bundle)
        unsafe["items"][0]["source_url"] = "javascript:alert(1)"
        assert client.post("/api/import", json=unsafe, headers=headers).status_code == 422
        assert client.post("/api/import", json=bundle, headers=headers).json()["added"] == 6
        assert client.get("/").status_code == 200
        assert "object-src 'none'" in client.get("/").headers["content-security-policy"]


def test_csv_export_respects_filters_and_neutralizes_formulas(client):
    bundle = sample_bundle().model_dump(mode="json")
    bundle["items"][0]["title"] = '=HYPERLINK("https://example.invalid")'
    client.post("/api/import", json=bundle)
    result = client.get("/api/export.csv", params={"topic": "transportation"})
    assert result.status_code == 200
    assert "'=HYPERLINK" in result.text
    assert "housing" not in result.text
    assert result.headers["content-type"].startswith("text/csv")


def test_duplicate_ids_and_unknown_meetings_rejected(client):
    bundle = sample_bundle().model_dump(mode="json")
    bundle["items"].append(bundle["items"][0])
    assert client.post("/api/import", json=bundle).status_code == 422
    bundle["items"].pop()
    bundle["items"][0]["meeting_id"] = "missing"
    assert client.post("/api/import", json=bundle).status_code == 422
