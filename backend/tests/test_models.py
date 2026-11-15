from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Attempt, Dataset, Job, Quiz, Scene, Story, UserBadge

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _ds(**kw):
    base = dict(source_id="X", product_type="GCOV", acquisition_start=NOW, west=0, south=0, east=1, north=1)
    base.update(kw)
    return Dataset(**base)


def test_dataset_check_constraints(db):
    db.add(_ds(source_id="bad-maturity", maturity="inconnue"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(_ds(source_id="bad-status", status="publié"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_dataset_source_id_unique(db):
    db.add(_ds(source_id="dup-1"))
    db.commit()
    db.add(_ds(source_id="dup-1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.query(Dataset).filter_by(source_id="dup-1").delete()
    db.commit()


def test_scene_order_unique_per_story(db):
    s = Story(slug="t-order", title="t", theme="t", synopsis="t")
    s.scenes += [Scene(order=1, title="a", body="a", center_lon=0, center_lat=0), Scene(order=1, title="b", body="b", center_lon=0, center_lat=0)]
    db.add(s)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_award_key_and_badge_uniqueness(db):
    quiz_id = db.query(Quiz).first().id
    db.add(Attempt(client_id="c" * 10, quiz_id=quiz_id, score=1, passed=True, answers={}, award_key="uniq-key"))
    db.commit()
    db.add(Attempt(client_id="c" * 10, quiz_id=quiz_id, score=1, passed=True, answers={}, award_key="uniq-key"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add_all([UserBadge(client_id="d" * 10, badge_key="b"), UserBadge(client_id="d" * 10, badge_key="b")])
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_job_idempotency_key_unique(db):
    db.add(Job(id="j-1", kind="time_series", params={}, idempotency_key="k-unique"))
    db.commit()
    db.add(Job(id="j-2", kind="time_series", params={}, idempotency_key="k-unique"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_geometry_roundtrip_geojson(db):
    from app.models import AOI
    geom = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    a = AOI(title="g", geometry=geom, area_km2=1.0)
    db.add(a)
    db.commit()
    db.expire_all()
    assert db.get(AOI, a.id).geometry == geom
