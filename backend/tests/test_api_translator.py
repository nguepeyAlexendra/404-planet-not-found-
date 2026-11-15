from tests.conftest import DEMO_AOI


def _ids(client):
    items = client.get("/api/v1/datasets", params={"include_demo": True, "page_size": 10}).json()["items"]
    items.sort(key=lambda d: d["acquisition_start"])
    return items


def test_ruleset_is_exposed_as_unvalidated_prototype(client):
    r = client.get("/api/v1/translator/ruleset").json()
    assert r["version"].startswith("gcov-lband-proto") and r["validated"] is False
    assert "non validé" in r["name"] and r["config"]["thresholds_db"]["water_hh_max"] == -18.0


def test_classification_summary_whole_scene(client):
    ds = _ids(client)[0]
    r = client.get("/api/v1/translator/classification", params={"dataset_id": ds["id"]})
    assert r.status_code == 200
    j = r.json()
    by = {c["key"]: c for c in j["classes"]}
    assert abs(sum(c["pct"] for c in j["classes"]) - 100) < 0.1
    assert by["dense_vegetation"]["pct"] > 40 and by["water"]["pct"] > 5 and by["urban"]["pct"] > 2
    assert j["is_demo"] and j["ruleset_version"] and "non validées" in j["limits"][0]


def test_classification_over_aoi_and_unknown_dataset(client, h):
    aoi = client.post("/api/v1/analytics/aoi", json={"title": "z", "geometry": DEMO_AOI}, headers=h).json()
    ds = _ids(client)[0]
    r = client.get("/api/v1/translator/classification", params={"dataset_id": ds["id"], "aoi_id": aoi["id"]}, headers=h)
    assert r.status_code == 200 and r.json()["valid_area_km2"] < 200
    assert client.get("/api/v1/translator/classification", params={"dataset_id": 99999}).status_code == 404
    # l'AOI d'une autre session est invisible
    other = client.get("/api/v1/translator/classification", params={"dataset_id": ds["id"], "aoi_id": aoi["id"]},
                       headers={"X-Client-Id": "autre-session-123"})
    assert other.status_code == 404


def test_classification_far_aoi_is_data_unavailable(client, h):
    far = {"type": "Polygon", "coordinates": [[[20, 40], [20.1, 40], [20.1, 40.1], [20, 40.1], [20, 40]]]}
    aoi = client.post("/api/v1/analytics/aoi", json={"title": "loin", "geometry": far}, headers=h).json()
    r = client.get("/api/v1/translator/classification", params={"dataset_id": _ids(client)[0]["id"], "aoi_id": aoi["id"]}, headers=h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "data_unavailable"


def test_change_detection_sees_the_simulated_clearing(client):
    ds = _ids(client)
    r = client.post("/api/v1/translator/changes", json={"before_dataset_id": ds[0]["id"], "after_dataset_id": ds[-1]["id"],
                                                       "band": "HVHV", "threshold_db": 3.0})
    assert r.status_code == 200
    j = r.json()
    assert j["summary"]["decrease_pct"] > 5 and j["summary"]["increase_pct"] < 2 and j["summary"]["changed_area_km2"] > 0
    assert j["is_demo"] and "diagnostic" in j["limits"][0]
    same = client.post("/api/v1/translator/changes", json={"before_dataset_id": ds[0]["id"], "after_dataset_id": ds[0]["id"]})
    assert same.status_code == 422
    bad = client.post("/api/v1/translator/changes", json={"before_dataset_id": ds[0]["id"], "after_dataset_id": ds[1]["id"], "threshold_db": 0})
    assert bad.status_code == 422
    missing = client.post("/api/v1/translator/changes", json={"before_dataset_id": 99999, "after_dataset_id": ds[1]["id"]})
    assert missing.status_code == 404


def test_change_detection_refuses_incompatible_images(client, db):
    from app.models import Dataset
    ds = _ids(client)
    row = db.get(Dataset, ds[1]["id"])
    row.track = 999  # géométrie d'acquisition différente
    db.commit()
    try:
        r = client.post("/api/v1/translator/changes", json={"before_dataset_id": ds[0]["id"], "after_dataset_id": ds[1]["id"]})
        assert r.status_code == 400 and r.json()["error"]["code"] == "incompatible_images"
        assert any("traces" in x for x in r.json()["error"]["details"]["reasons"])
    finally:
        row.track = 77
        db.commit()
