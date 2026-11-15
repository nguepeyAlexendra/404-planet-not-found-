import pytest

from tests.conftest import CENTER_LAT, CENTER_LON

D0, D5 = "2026-03-04", "2026-08-11"


def test_health_and_ready(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    r = client.get("/api/v1/health/ready").json()
    assert r["status"] == "ready" and r["datasets_total"] >= 6 and r["datasets_real_available"] == 0


def test_errors_are_structured_with_request_id(client):
    r = client.get("/api/v1/datasets/99999", headers={"X-Request-ID": "abc123"})
    body = r.json()["error"]
    assert r.status_code == 404 and body["code"] == "not_found" and body["request_id"] == "abc123"
    assert r.headers["X-Request-ID"] == "abc123"
    r = client.get("/api/v1/nexiste-pas")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_demo_data_hidden_by_default_and_never_mixed_with_real_catalog(client):
    assert client.get("/api/v1/datasets").json()["total"] == 0
    r = client.get("/api/v1/datasets", params={"include_demo": True}).json()
    assert r["total"] == 6 and all(d["is_demo"] and d["maturity"] == "demo" for d in r["items"])
    layers = client.get("/api/v1/layers").json()
    assert all(not l["coverage"]["available"] for l in layers)  # sans démo : aucune couverture


def test_datasets_filters_pagination_and_validation(client):
    p = {"include_demo": True}
    page1 = client.get("/api/v1/datasets", params={**p, "page_size": 4}).json()
    page2 = client.get("/api/v1/datasets", params={**p, "page_size": 4, "page": 2}).json()
    assert len(page1["items"]) == 4 and len(page2["items"]) == 2 and page1["total"] == 6
    assert page1["items"][0]["acquisition_start"] > page1["items"][-1]["acquisition_start"]
    assert client.get("/api/v1/datasets", params={**p, "start": "2026-05-01", "end": "2026-06-30"}).json()["total"] == 2
    assert client.get("/api/v1/datasets", params={**p, "bbox": "100,0,101,1"}).json()["total"] == 0
    assert client.get("/api/v1/datasets", params={**p, "bbox": "9,3,10,5"}).json()["total"] == 6
    assert client.get("/api/v1/datasets", params={**p, "maturity": "beta"}).json()["total"] == 0
    assert client.get("/api/v1/datasets", params={"bbox": "a,b"}).json()["error"]["code"] == "invalid_bbox"
    assert client.get("/api/v1/datasets", params={"bbox": "10,0,5,1"}).status_code == 400
    assert client.get("/api/v1/datasets", params={"page": 0}).status_code == 422
    assert client.get("/api/v1/datasets", params={"page_size": 500}).status_code == 422


def test_dataset_detail_exposes_metadata_and_bands(client):
    first = client.get("/api/v1/datasets", params={"include_demo": True}).json()["items"][0]
    d = client.get(f"/api/v1/datasets/{first['id']}").json()
    assert d["bands"] == ["HHHH", "HVHV"] and d["crs"] == "EPSG:32632" and d["track"] == 77 and d["product_type"] == "GCOV"
    assert d["extent"]["type"] == "Polygon"


def test_layers_report_real_coverage_dates(client):
    layers = {l["key"]: l for l in client.get("/api/v1/layers", params={"include_demo": True}).json()}
    cov = layers["nisar-gcov-hh"]["coverage"]
    assert cov["available"] and cov["count"] == 6 and cov["dates"][0] == D0 and cov["dates"][-1] == D5 and cov["has_demo"]
    assert "{date}" in layers["nisar-gcov-hh"]["tiles"]
    meta = client.get("/api/v1/layers/nisar-gcov-hv/metadata", params={"include_demo": True}).json()
    assert len(meta["datasets"]) == 6 and meta["datasets"][0]["checksum_sha256"] and meta["datasets"][0]["is_demo"]
    assert client.get("/api/v1/layers/inconnue/metadata").status_code == 404


def test_pixel_values_units_and_interpretation(client):
    r = client.get("/api/v1/map/pixel", params={"lon": CENTER_LON, "lat": CENTER_LAT, "date": D0, "include_demo": True})
    assert r.status_code == 200
    j = r.json()
    assert j["bands"]["HH"]["status"] == "ok" and j["bands"]["HH"]["db"] < 5 and j["is_demo"] and j["maturity"] == "demo"
    assert "dB" in j["units"] and len(j["series"]) == 6
    assert j["interpretation"]["ruleset_version"] and "prototype" in j["interpretation"]["caution"]


def test_pixel_water_pixel_is_classified_water(client):
    # le lac simulé est à l'ouest du centre : on cherche un point d'eau en balayant quelques positions
    classes = set()
    for dlon in (-0.04, -0.03, -0.025):
        r = client.get("/api/v1/map/pixel", params={"lon": CENTER_LON + dlon, "lat": CENTER_LAT - 0.02, "date": D0, "include_demo": True})
        if r.status_code == 200:
            classes.add(r.json()["interpretation"]["class_key"])
    assert "water" in classes


def test_pixel_outside_coverage_or_without_acquisition_is_explicit_not_zero(client):
    far = client.get("/api/v1/map/pixel", params={"lon": 20, "lat": 40, "date": D0, "include_demo": True})
    assert far.status_code == 404 and far.json()["error"]["code"] == "data_unavailable"
    nodate = client.get("/api/v1/map/pixel", params={"lon": CENTER_LON, "lat": CENTER_LAT, "date": "2026-01-01", "include_demo": True})
    assert nodate.status_code == 404 and "Aucune acquisition" in nodate.json()["error"]["message"]
    hidden = client.get("/api/v1/map/pixel", params={"lon": CENTER_LON, "lat": CENTER_LAT, "date": D0})
    assert hidden.status_code == 404  # démo masquée par défaut


@pytest.mark.parametrize("params", [{"lon": 200, "lat": 0, "date": D0}, {"lon": 0, "lat": 95, "date": D0},
                                    {"lon": 0, "lat": 0, "date": "pas-une-date"}, {"lon": 0, "lat": 0}])
def test_pixel_validates_inputs(client, params):
    assert client.get("/api/v1/map/pixel", params=params).status_code in (400, 422)


def test_tiles_png_transparent_and_validation(client):
    z, x, y = 11, 1073, 1000  # recalcul ci-dessous
    import math
    n = 2**z
    x = int((CENTER_LON + 180) / 360 * n)
    lat = math.radians(CENTER_LAT)
    y = int((1 - math.asinh(math.tan(lat)) / math.pi) / 2 * n)
    r = client.get(f"/api/v1/tiles/nisar-gcov-hh/{D0}/{z}/{x}/{y}.png", params={"demo": True})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:8] == b"\x89PNG\r\n\x1a\n"
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    assert img.size == (256, 256) and img.getextrema()[3][1] == 255  # des pixels opaques
    far = client.get(f"/api/v1/tiles/nisar-gcov-hh/{D0}/{z}/0/0.png", params={"demo": True})
    assert Image.open(io.BytesIO(far.content)).convert("RGBA").getextrema()[3] == (0, 0)  # hors emprise : transparent
    assert client.get(f"/api/v1/tiles/nisar-gcov-hh/{D0}/{z}/{x}/{y}.png").content  # démo masquée : tuile vide, pas d'erreur
    assert client.get(f"/api/v1/tiles/nisar-gcov-hh/{D0}/2/9/0.png").status_code == 400
    assert client.get(f"/api/v1/tiles/nisar-gcov-hh/xx/{z}/{x}/{y}.png").status_code == 400
    assert client.get(f"/api/v1/tiles/inconnue/{D0}/{z}/{x}/{y}.png").status_code == 404
    cls = client.get(f"/api/v1/tiles/nisar-gcov-hh/{D0}/{z}/{x}/{y}.png", params={"demo": True, "mode": "classes"})
    assert cls.status_code == 200
    assert client.get(f"/api/v1/tiles/nisar-gcov-hh/{D0}/{z}/{x}/{y}.png", params={"mode": "x"}).status_code == 422
    ch = client.get(f"/api/v1/tiles/change/nisar-gcov-hv/{D0}/{D5}/{z}/{x}/{y}.png", params={"demo": True})
    assert ch.status_code == 200 and ch.headers["content-type"] == "image/png"


def test_rate_limit_returns_429(client, monkeypatch):
    import app.main as m
    monkeypatch.setattr(m.settings, "rate_limit_per_minute", 3)
    m._hits.clear()
    codes = [client.get("/api/v1/datasets").status_code for _ in range(5)]
    assert codes[:3] == [200] * 3 and codes[3] == 429
    r = client.get("/api/v1/datasets")
    assert r.json()["error"]["code"] == "rate_limited" and r.headers["Retry-After"] == "60"
    m._hits.clear()
