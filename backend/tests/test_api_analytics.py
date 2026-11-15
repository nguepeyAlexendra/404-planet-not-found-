import csv
import io
import json

import pytest

from tests.conftest import DEMO_AOI

START, END = "2026-03-01", "2026-08-31"


def _aoi(client, h, geometry=DEMO_AOI, title="zone"):
    r = client.post("/api/v1/analytics/aoi", json={"title": title, "geometry": geometry}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _ts(client, h, aoi_id, **kw):
    body = {"aoi_id": aoi_id, "date_start": START, "date_end": END, "frequency": "month", "include_demo": True, **kw}
    return client.post("/api/v1/analytics/time-series", json=body, headers=h)


def test_aoi_creation_from_geojson_radius_bbox(client, h):
    a = _aoi(client, h)
    assert a["source"] == "geojson" and 50 < a["area_km2"] < 100
    r = client.post("/api/v1/analytics/aoi", json={"title": "r", "center": [9.7, 4.05], "radius_km": 5}, headers=h).json()
    assert r["source"] == "radius" and 70 < r["area_km2"] < 85
    b = client.post("/api/v1/analytics/aoi", json={"title": "b", "bbox": [9.66, 4.02, 9.74, 4.09]}, headers=h).json()
    assert b["source"] == "drawn"
    feature = {"type": "Feature", "geometry": DEMO_AOI, "properties": {}}
    assert _aoi(client, h, feature)["area_km2"] > 0  # Feature GeoJSON accepté


@pytest.mark.parametrize("body,status", [
    ({"title": "x"}, 422),
    ({"title": "x", "geometry": DEMO_AOI, "bbox": [0, 0, 1, 1]}, 422),
    ({"title": "x", "center": [0, 0]}, 422),
    ({"title": "", "geometry": DEMO_AOI}, 422),
    ({"title": "x", "bbox": [5, 0, 1, 1]}, 400),
    ({"title": "x", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}}, 400),
    ({"title": "x", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}}, 400),
    ({"title": "x", "bbox": [0, 0, 40, 40]}, 400),  # trop grande
])
def test_aoi_validation_errors(client, h, body, status):
    r = client.post("/api/v1/analytics/aoi", json=body, headers=h)
    assert r.status_code == status
    assert "error" in r.json()


def test_aoi_requires_client_id_and_is_private(client, h):
    assert client.post("/api/v1/analytics/aoi", json={"title": "x", "bbox": [0, 0, 1, 1]}).status_code == 400
    assert client.post("/api/v1/analytics/aoi", json={"title": "x", "bbox": [0, 0, 1, 1]}, headers={"X-Client-Id": "court"}).status_code == 400
    a = _aoi(client, h)
    assert client.get(f"/api/v1/analytics/aoi/{a['id']}", headers=h).status_code == 200
    assert client.get(f"/api/v1/analytics/aoi/{a['id']}", headers={"X-Client-Id": "autre-session-xyz"}).status_code == 404


def test_time_series_job_end_to_end(client, h):
    aoi = _aoi(client, h)
    r = _ts(client, h, aoi["id"], variables=["HHHH", "HVHV", "classes"])
    assert r.status_code == 202
    job = client.get(f"/api/v1/jobs/{r.json()['job_id']}", headers=h).json()
    assert job["status"] == "succeeded" and job["progress"] == 1.0 and job["finished_at"]
    res = job["result"]
    assert len(res["series"]) == 6 and res["n_datasets"] == 6 and res["has_demo"] and res["units"] == "dB"
    hv = [s["bands"]["HV"]["mean_db"] for s in res["series"]]
    assert hv[0] > hv[-1] + 0.3  # la forêt simulée disparaît : HV baisse
    assert res["trend"]["HV"]["slope_db_per_day"] < 0 and res["trend"]["HV"]["n"] == 6
    assert res["series"][0]["classes_pct"]["dense_vegetation"] > res["series"][-1]["classes_pct"]["dense_vegetation"]
    assert any("DÉMONSTRATION" in w for w in res["warnings"]) and res["method_version"] and res["dataset_ids"]
    assert res["missing_periods"] == [] and "soil_moisture" in res["unavailable_variables"][0]
    assert "geometry" in job["params"] and "client_id" not in job["params"]


def test_time_series_reports_missing_periods_with_weekly_frequency(client, h):
    res = client.get(f"/api/v1/jobs/{_ts(client, h, _aoi(client, h)['id'], frequency='week').json()['job_id']}", headers=h).json()["result"]
    assert len(res["missing_periods"]) > 10  # les trous restent visibles, jamais comblés


def test_time_series_without_data_fails_explicitly(client, h):
    aoi = _aoi(client, h)
    r = client.post("/api/v1/analytics/time-series", json={"aoi_id": aoi["id"], "date_start": START, "date_end": END}, headers=h)
    job = client.get(f"/api/v1/jobs/{r.json()['job_id']}", headers=h).json()  # démo masquée par défaut
    assert job["status"] == "failed" and "Aucune acquisition" in job["error_message"] and job["result"]["error_code"] == "data_unavailable"
    far = {"type": "Polygon", "coordinates": [[[20, 40], [20.1, 40], [20.1, 40.1], [20, 40.1], [20, 40]]]}
    job2 = client.get(f"/api/v1/jobs/{_ts(client, h, _aoi(client, h, far)['id']).json()['job_id']}", headers=h).json()
    assert job2["status"] == "failed"


@pytest.mark.parametrize("patch,status", [({"date_end": "2026-02-01"}, 422), ({"date_start": "2020-01-01", "date_end": "2026-08-01"}, 400),
                                          ({"frequency": "an"}, 422), ({"variables": ["VVVV"]}, 422), ({"aoi_id": 424242}, 404)])
def test_time_series_request_validation(client, h, patch, status):
    aoi = _aoi(client, h)
    body = {"aoi_id": aoi["id"], "date_start": START, "date_end": END, "include_demo": True, **patch}
    assert client.post("/api/v1/analytics/time-series", json=body, headers=h).status_code == status


def test_idempotency_key_prevents_duplicate_jobs(client, h):
    aoi = _aoi(client, h)
    heads = {**h, "Idempotency-Key": "soumission-1"}
    a = _ts(client, heads, aoi["id"]).json()
    b = _ts(client, heads, aoi["id"]).json()
    assert a["job_id"] == b["job_id"]
    c = _ts(client, h, aoi["id"]).json()
    assert c["job_id"] != a["job_id"]


def test_jobs_are_private_and_cancel_rules(client, h):
    job = _ts(client, h, _aoi(client, h)["id"]).json()
    assert client.get(f"/api/v1/jobs/{job['job_id']}", headers={"X-Client-Id": "autre-session-xyz"}).status_code == 404
    assert client.get("/api/v1/jobs/inexistant", headers=h).status_code == 404
    assert client.post(f"/api/v1/jobs/{job['job_id']}/cancel", headers=h).status_code == 409  # déjà terminé


def test_cancel_queued_job_and_run_is_skipped(client, h, db):
    from app.services import jobs
    j, _ = jobs.create_job(db, "time_series", {"geometry": DEMO_AOI, "date_start": START, "date_end": END, "include_demo": True})
    j.owner_id = h["X-Client-Id"]
    db.commit()
    assert client.post(f"/api/v1/jobs/{j.id}/cancel", headers=h).json()["status"] == "cancelled"
    jobs.run_job(j.id)
    db.expire_all()
    assert jobs.get_job(db, j.id).status == "cancelled"


def test_change_matrix_shows_forest_loss(client, h):
    aoi = _aoi(client, h)
    r = client.post("/api/v1/analytics/change-matrix", json={"aoi_id": aoi["id"], "date_a": "2026-03-04", "date_b": "2026-08-11",
                                                            "include_demo": True}, headers=h)
    job = client.get(f"/api/v1/jobs/{r.json()['job_id']}", headers=h).json()
    assert job["status"] == "succeeded", job
    res = job["result"]
    i = res["class_keys"].index("dense_vegetation")
    assert res["matrix"]["net_km2"][i] < 0 and "gagne le plus" in res["summary_text"]
    assert any("non validées" in w for w in res["warnings"]) and res["ruleset_version"]
    assert client.post("/api/v1/analytics/change-matrix", json={"aoi_id": aoi["id"], "date_a": "2026-03-04", "date_b": "2026-03-04"}, headers=h).status_code == 400
    nodate = client.post("/api/v1/analytics/change-matrix", json={"aoi_id": aoi["id"], "date_a": "2026-01-01", "date_b": "2026-08-11", "include_demo": True}, headers=h)
    assert client.get(f"/api/v1/jobs/{nodate.json()['job_id']}", headers=h).json()["status"] == "failed"


def test_projection_is_exploratory_and_needs_enough_points(client, h):
    aoi = _aoi(client, h)
    r = client.post("/api/v1/analytics/projection", json={"aoi_id": aoi["id"], "date_start": START, "date_end": END, "frequency": "month",
                                                         "variable": "HV", "horizon_months": 3, "include_demo": True}, headers=h)
    job = client.get(f"/api/v1/jobs/{r.json()['job_id']}", headers=h).json()
    assert job["status"] == "succeeded", job
    sc = job["result"]["scenarios"]
    assert set(sc) == {"business_as_usual", "protection_renforcee", "acceleration"}
    last = {k: v["points"][-1]["value"] for k, v in sc.items()}
    assert last["acceleration"] < last["business_as_usual"] < last["protection_renforcee"]
    assert any("EXPLORATOIRE" in w for w in job["result"]["warnings"])
    short = client.post("/api/v1/analytics/projection", json={"aoi_id": aoi["id"], "date_start": "2026-03-01", "date_end": "2026-05-31",
                                                             "frequency": "month", "include_demo": True}, headers=h)
    j2 = client.get(f"/api/v1/jobs/{short.json()['job_id']}", headers=h).json()
    assert j2["status"] == "failed" and "trop courte" in j2["error_message"]


def _export(client, h, job_id, fmt):
    r = client.post("/api/v1/exports", json={"job_id": job_id, "format": fmt}, headers=h)
    assert r.status_code == 202, r.text
    j = client.get(f"/api/v1/jobs/{r.json()['job_id']}", headers=h).json()
    return j


def test_exports_all_formats_carry_metadata(client, h):
    aoi = _aoi(client, h)
    ts = _ts(client, h, aoi["id"]).json()["job_id"]
    j = _export(client, h, ts, "csv")
    assert j["status"] == "succeeded"
    body = client.get(j["result"]["download_path"], headers=h)
    text = body.content.decode("utf-8-sig")
    assert body.status_code == 200 and "DÉMONSTRATION" in text and "# méthode" not in text and "méthode:" in text
    rows = list(csv.reader(line for line in text.splitlines() if not line.startswith("#")))
    assert rows[0][0] == "periode" and len(rows) > 6
    g = _export(client, h, ts, "geojson")
    gj = json.loads(client.get(g["result"]["download_path"], headers=h).content)
    assert gj["features"][0]["geometry"]["type"] == "Polygon" and gj["features"][0]["properties"]["method"]
    s = _export(client, h, ts, "svg")
    assert client.get(s["result"]["download_path"], headers=h).content.startswith(b"<svg")
    p = _export(client, h, ts, "pdf")
    assert client.get(p["result"]["download_path"], headers=h).content[:5] == b"%PDF-"


def test_export_errors_and_permissions(client, h, db):
    ts = _ts(client, h, _aoi(client, h)["id"]).json()["job_id"]
    assert client.post("/api/v1/exports", json={"job_id": ts, "format": "docx"}, headers=h).status_code == 422
    assert client.post("/api/v1/exports", json={"job_id": "inconnu", "format": "csv"}, headers=h).status_code == 404
    assert client.post("/api/v1/exports", json={"job_id": ts, "format": "csv"}, headers={"X-Client-Id": "autre-session-xyz"}).status_code == 404
    failing = _ts(client, h, _aoi(client, h)["id"], date_start="2020-01-01", date_end="2020-02-01").json()["job_id"]
    j = _export(client, h, failing, "csv")
    assert j["status"] == "failed" and "pas terminée" in j["error_message"]
    ok = _export(client, h, ts, "csv")
    path = ok["result"]["download_path"]
    assert client.get(path, headers={"X-Client-Id": "autre-session-xyz"}).status_code == 404  # privé par défaut
    # expiration : le lien cesse de fonctionner et le nettoyage supprime le fichier
    from datetime import datetime, timedelta, timezone
    from app.models import Export
    from app.services.exports import purge_expired
    exp = db.get(Export, ok["result"]["export_id"])
    exp.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    assert client.get(path, headers=h).status_code == 404
    assert purge_expired(db) >= 1


def test_svg_export_unsupported_for_change_matrix(client, h):
    aoi = _aoi(client, h)
    cm = client.post("/api/v1/analytics/change-matrix", json={"aoi_id": aoi["id"], "date_a": "2026-03-04", "date_b": "2026-08-11", "include_demo": True}, headers=h).json()["job_id"]
    assert _export(client, h, cm, "svg")["status"] == "failed"
    assert _export(client, h, cm, "csv")["status"] == "succeeded"
