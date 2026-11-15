"""Pipeline d'ingestion testé sur des fichiers de DÉMONSTRATION (jamais présentés comme réels)."""
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pytest
import rasterio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.errors import AppError, TooLarge
from app.ingestion import asf_client
from app.ingestion.demo import make_demo_gcov
from app.ingestion.hdf5_gcov import ProductFormatError, read_gcov
from app.ingestion.pipeline import IngestError, ingest_file
from app.ingestion.validate import validate_product
from app.models import Base, Dataset, IngestionRun, RasterAsset

T0 = datetime(2026, 9, 1, 5, tzinfo=timezone.utc)


@pytest.fixture()
def env(tmp_path):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = Settings(data_dir=tmp_path / "data", database_url="sqlite://")
    return sessionmaker(engine)(), s, tmp_path


def test_ingest_registers_dataset_assets_cog_and_manifest(env):
    db, s, tmp = env
    f = make_demo_gcov(tmp / "A.h5", T0)
    ds = ingest_file(db, f, maturity="provisional", is_demo=True, settings=s)
    assert ds.status == "available" and ds.is_demo and ds.maturity == "demo" and ds.source == "DEMO"
    assert sorted(a.band for a in ds.assets) == ["HHHH", "HVHV"]
    assert -180 < ds.west < ds.east < 180 and -90 < ds.south < ds.north < 90
    from rio_cogeo.cogeo import cog_validate
    assert cog_validate(ds.assets[0].uri)[0]  # COG valide (le fichier de démo est trop petit pour avoir des overviews)
    with rasterio.open(ds.assets[0].uri) as src:
        assert src.crs.to_epsg() == 32632 and src.nodata is not None
    assert (s.data_dir / "manifests" / "A.manifest.json").exists()
    run = db.scalars(select(IngestionRun)).one()
    assert run.status == "succeeded" and "publish" in run.log and run.finished_at


def test_ingest_is_idempotent(env):
    db, s, tmp = env
    f = make_demo_gcov(tmp / "A.h5", T0)
    first = ingest_file(db, f, maturity="demo", is_demo=True, settings=s)
    again = ingest_file(db, f, maturity="demo", is_demo=True, settings=s)
    assert again.id == first.id
    assert db.query(Dataset).count() == 1 and db.query(RasterAsset).count() == 2


def test_changed_file_reingest_replaces_old_version(env):
    db, s, tmp = env
    ingest_file(db, make_demo_gcov(tmp / "A.h5", T0, seed=1), maturity="demo", is_demo=True, settings=s)
    new = ingest_file(db, make_demo_gcov(tmp / "A.h5", T0, seed=2), maturity="demo", is_demo=True, settings=s)
    assert db.query(Dataset).count() == 1 and new.status == "available" and db.query(RasterAsset).count() == 2


def test_not_hdf5_goes_to_quarantine_and_publishes_nothing(env):
    db, s, tmp = env
    bad = tmp / "bad.h5"
    bad.write_bytes(b"ceci n'est pas du HDF5")
    with pytest.raises(IngestError, match="quarantaine"):
        ingest_file(db, bad, maturity="provisional", settings=s)
    assert db.query(Dataset).count() == 0
    assert (s.quarantine_dir / "bad.h5").exists()
    assert db.scalars(select(IngestionRun)).one().status == "quarantined"


def test_missing_group_is_quarantined(env):
    db, s, tmp = env
    p = tmp / "empty.h5"
    with h5py.File(p, "w") as h:
        h.create_group("autre")
    with pytest.raises(IngestError):
        ingest_file(db, p, maturity="provisional", settings=s)
    assert db.query(Dataset).count() == 0


def test_all_nodata_band_is_rejected(env):
    db, s, tmp = env
    f = make_demo_gcov(tmp / "N.h5", T0)
    with h5py.File(f, "r+") as h:
        h["science/LSAR/GCOV/grids/frequencyA/HHHH"][...] = np.nan
    with pytest.raises(IngestError, match="entièrement invalide"):
        ingest_file(db, f, maturity="provisional", settings=s)
    assert db.query(Dataset).count() == 0


def test_negative_values_are_rejected(env):
    db, s, tmp = env
    f = make_demo_gcov(tmp / "neg.h5", T0)
    with h5py.File(f, "r+") as h:
        h["science/LSAR/GCOV/grids/frequencyA/HVHV"][0, 0] = -1.0
    with pytest.raises(IngestError, match="négatives"):
        ingest_file(db, f, maturity="provisional", settings=s)


def test_failure_midway_leaves_no_partial_dataset(env, monkeypatch):
    db, s, tmp = env
    f = make_demo_gcov(tmp / "A.h5", T0)
    calls = {"n": 0}
    from app.ingestion import pipeline
    real = pipeline.write_cog

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("disque plein")
        return real(*a, **k)

    monkeypatch.setattr(pipeline, "write_cog", flaky)
    with pytest.raises(IngestError, match="disque plein"):
        ingest_file(db, f, maturity="provisional", is_demo=True, settings=s)
    assert db.query(Dataset).count() == 0 and db.query(RasterAsset).count() == 0
    assert not (s.cog_dir / "A").exists()
    assert db.scalars(select(IngestionRun)).one().status == "failed"
    monkeypatch.setattr(pipeline, "write_cog", real)  # reprise après correction de la panne
    assert ingest_file(db, f, maturity="provisional", is_demo=True, settings=s).status == "available"


def test_reader_reports_precise_errors(tmp_path):
    p = make_demo_gcov(tmp_path / "A.h5", T0)
    product = read_gcov(p)
    assert set(product.bands) == {"HHHH", "HVHV"} and product.epsg == 32632 and product.meta["track"] == 77
    assert validate_product(product) == []
    with h5py.File(p, "r+") as h:
        del h["science/LSAR/identification/zeroDopplerStartTime"]
    with pytest.raises(ProductFormatError, match="zeroDopplerStartTime"):
        read_gcov(p)


def test_validate_flags_irregular_grid(tmp_path):
    product = read_gcov(make_demo_gcov(tmp_path / "A.h5", T0))
    product.x[5] += 40.0
    assert "grille non régulière" in validate_product(product)


class _G:
    def __init__(self, gb):
        self.size_bytes, self.source_id = int(gb * 1e9), "g"


def test_download_budget_blocks_large_requests_without_confirmation():
    with pytest.raises(TooLarge):
        asf_client.check_budget([_G(15), _G(10)])
    assert asf_client.check_budget([_G(15), _G(10)], confirm=True) == pytest.approx(25.0)
    assert asf_client.check_budget([_G(1)]) == pytest.approx(1.0)


def test_download_requires_token(monkeypatch, tmp_path):
    monkeypatch.setattr(asf_client, "get_settings", lambda: Settings(earthdata_token=None))
    with pytest.raises(AppError, match="Jeton Earthdata"):
        asf_client.download(asf_client.RemoteGranule("g", "u", 1, None, None, None), tmp_path)


def test_discover_maps_catalogue_results(monkeypatch):
    class P:
        properties = {"fileID": "NISAR_X", "url": "https://x/y.h5", "bytes": 123, "startTime": "2026-08-01T00:00:00Z",
                      "dataMaturity": "PROVISIONAL", "processingLevel": "GCOV"}

    monkeypatch.setattr(asf_client.asf, "search", lambda **kw: [P()])
    out = asf_client.discover("POLYGON((0 0,1 0,1 1,0 1,0 0))", "2026-08-01", "2026-08-31", maturity=["provisional"])
    assert out[0].source_id == "NISAR_X" and out[0].size_bytes == 123 and out[0].maturity == "PROVISIONAL"
