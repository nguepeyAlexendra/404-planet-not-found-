import math

import numpy as np
import pytest

from app.processing import change, classifier, geo, stats, units


def test_to_db_basic_and_invalid_values():
    out = units.to_db(np.array([1.0, 0.1, 100.0, 0.0, -2.0, np.nan, np.inf]))
    assert out[:3].tolist() == pytest.approx([0.0, -10.0, 20.0])
    assert np.isnan(out[3:]).all()  # jamais -inf ni valeur trompeuse


def test_to_db_masks_nodata_value():
    out = units.to_db(np.array([1.0, -9999.0, 2.0]), nodata=-9999.0)
    assert np.isnan(out[1]) and not np.isnan(out[0])


def test_mean_db_is_mean_of_linear_not_of_db():
    # moyenne linéaire de 1 et 0.01 = 0.505 -> -2.97 dB (la moyenne des dB donnerait -10)
    assert units.mean_db(np.array([1.0, 0.01])) == pytest.approx(10 * math.log10(0.505))
    assert units.mean_db(np.array([np.nan, 0.0])) is None


def test_from_db_roundtrip():
    assert units.from_db(-10.0) == pytest.approx(0.1)


def _bands(hh_db, hv_db):
    return {"HHHH": np.array([[10 ** (v / 10) for v in hh_db]]), "HVHV": np.array([[10 ** (v / 10) for v in hv_db]])}


def test_classifier_each_class():
    rs = classifier.load_ruleset()
    # eau, urbain, forêt dense, végétation clairsemée, sol nu
    out = classifier.classify(_bands([-23, -3, -8, -11, -13], [-30, -14.5, -12.5, -17, -23]), rs)[0]
    assert out.tolist() == [classifier.WATER, classifier.URBAN, classifier.DENSE_VEG, classifier.SPARSE_VEG, classifier.BARE]


def test_classifier_invalid_pixels_are_indeterminate():
    rs = classifier.load_ruleset()
    bands = {"HHHH": np.array([[np.nan, 0.0]]), "HVHV": np.array([[0.1, 0.1]])}
    assert classifier.classify(bands, rs)[0].tolist() == [0, 0]


def test_classifier_missing_band_is_explicit_error():
    rs = classifier.load_ruleset()
    with pytest.raises(classifier.MissingBandsError) as e:
        classifier.classify({"HHHH": np.ones((2, 2))}, rs)
    assert e.value.missing == ["HVHV"]


def test_classify_pixel_explanation_and_missing_value():
    rs = classifier.load_ruleset()
    info = classifier.classify_pixel(10 ** (-23 / 10), 10 ** (-30 / 10), rs)
    assert info["class_key"] == "water" and info["ratio_db"] == pytest.approx(7.0, abs=0.01)
    assert info["ruleset_version"] == rs["version"]
    none = classifier.classify_pixel(None, 0.1, rs)
    assert none["class_key"] == "indeterminate" and none["hh_db"] is None


def test_detect_change_three_classes_and_threshold():
    a = np.array([[1.0, 1.0, 1.0, np.nan]])
    b = np.array([[2.5, 0.4, 1.2, 1.0]])  # +3.98 dB, -3.98 dB, +0.79 dB, invalide
    classes, delta = change.detect_change(a, b, threshold_db=3.0)
    assert classes[0].tolist() == [change.INCREASE, change.DECREASE, change.STABLE, change.INVALID]
    assert np.isnan(delta[0, 3])


def test_detect_change_rejects_bad_input():
    with pytest.raises(change.IncompatibleImages):
        change.detect_change(np.ones((2, 2)), np.ones((3, 3)))
    with pytest.raises(ValueError):
        change.detect_change(np.ones((2, 2)), np.ones((2, 2)), threshold_db=0)


def test_summarize_change_and_all_invalid():
    classes = np.array([[change.INCREASE, change.STABLE, change.STABLE, change.INVALID]], dtype="uint8")
    s = change.summarize_change(classes, 0.5)
    assert s["valid_pixels"] == 3 and s["increase_pct"] == pytest.approx(33.33, abs=0.01) and s["changed_area_km2"] == 0.5
    empty = change.summarize_change(np.full((2, 2), change.INVALID, dtype="uint8"), 1.0)
    assert empty["valid_pixels"] == 0 and empty["stable_pct"] is None


def _grid(**kw):
    base = dict(crs="EPSG:32632", transform=(90, 0, 0, 0, -90, 0), shape=(10, 10), band="HHHH", maturity="provisional", track=1,
                orbit_direction="Ascending")
    base.update(kw)
    return change.GridInfo(**base)


def test_check_compatible_reports_every_reason():
    assert change.check_compatible(_grid(), _grid()) == []
    reasons = change.check_compatible(_grid(), _grid(crs="EPSG:32633", band="HVHV", track=2, maturity="beta",
                                                     orbit_direction="Descending", shape=(11, 10)))
    text = " ".join(reasons)
    for word in ("CRS", "grilles", "polarisations", "traces", "orbite", "maturité"):
        assert word in text


def test_linear_trend_and_errors():
    t = stats.linear_trend([0, 1, 2, 3], [1, 3, 5, 7])
    assert t.slope_per_day == pytest.approx(2.0) and t.r2 == pytest.approx(1.0)
    with pytest.raises(stats.InsufficientData):
        stats.linear_trend([0, 1], [1, 2])
    with pytest.raises(stats.InsufficientData):
        stats.linear_trend([5, 5, 5], [1, 2, 3])


def test_projection_requires_enough_points_and_scenarios_differ():
    days, vals = [0, 30, 60, 90, 120, 150], [-10, -10.2, -10.5, -10.6, -11, -11.1]
    base = stats.projection(days, vals, [210], slope_factor=1.0)
    slow = stats.projection(days, vals, [210], slope_factor=0.5)
    fast = stats.projection(days, vals, [210], slope_factor=1.5)
    b, s, f = (x["points"][0] for x in (base, slow, fast))
    assert f["value"] < b["value"] < s["value"]
    assert b["low"] < b["value"] < b["high"]
    with pytest.raises(stats.InsufficientData):
        stats.projection(days[:4], vals[:4], [210])


def test_transition_matrix_counts_areas_and_invalid():
    a = np.array([[0, 0, 1, 1, -1]])
    b = np.array([[0, 1, 1, 1, 0]])
    m = stats.transition_matrix(a, b, [0, 1], pixel_area_km2=2.0)
    assert m["counts"] == [[1, 1], [0, 2]] and m["valid_pixels"] == 4
    assert m["lost_km2"] == [2.0, 0.0] and m["gained_km2"] == [0.0, 2.0] and m["net_km2"] == [-2.0, 2.0]
    with pytest.raises(ValueError):
        stats.transition_matrix(np.zeros((1, 2)), np.zeros((2, 2)), [0], 1.0)


def test_validate_aoi_geometry_ok_and_area():
    geom, area = geo.validate_aoi_geometry({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}, 1e6)
    assert geom["type"] == "Polygon" and 12000 < area < 12500  # ~1°x1° à l'équateur


@pytest.mark.parametrize("bad,code", [
    ({"type": "Point", "coordinates": [0, 0]}, "invalid_geometry"),
    ({"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}, "invalid_geometry"),  # papillon
    ({"type": "Polygon", "coordinates": [[[170, 0], [190, 0], [190, 1], [170, 1], [170, 0]]]}, "invalid_geometry"),
    ({"type": "Polygon", "coordinates": []}, "invalid_geometry"),
    ("pas un objet", "invalid_geometry"),
])
def test_validate_aoi_geometry_rejects(bad, code):
    from app.core.errors import AppError
    with pytest.raises(AppError) as e:
        geo.validate_aoi_geometry(bad, 1e6)
    assert e.value.code == code


def test_validate_aoi_geometry_too_large():
    from app.core.errors import TooLarge
    with pytest.raises(TooLarge):
        geo.validate_aoi_geometry({"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}, 1000)


def test_circle_and_bbox_helpers():
    c = geo.circle_geojson(9.7, 4.05, 10)
    _, area = geo.validate_aoi_geometry(c, 1e6)
    assert area == pytest.approx(math.pi * 100, rel=0.01)
    assert geo.bbox_geojson(0, 0, 1, 1)["type"] == "Polygon"
