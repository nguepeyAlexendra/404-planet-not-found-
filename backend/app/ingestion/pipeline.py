"""Pipeline d'ingestion : 10 étapes, idempotent par granule et version, reprise possible, quarantaine.

 1 découverte  2 estimation  3 récupération  4 checksum+manifest  5 métadonnées
 6 validation  7 traitement  8 COG  9 enregistrement + test de rendu  10 publication
Un échec ne publie jamais un dataset incomplet : le granule est mis en quarantaine ou les
éléments partiels sont supprimés, et le journal est conservé dans IngestionRun.
"""
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from shapely.geometry import box, mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.ingestion.cog import raster_info, write_cog
from app.ingestion.hdf5_gcov import ProductFormatError, read_gcov
from app.ingestion.manifest import sha256_file, write_manifest
from app.ingestion.validate import bounds_wgs84, validate_product
from app.models import Dataset, IngestionRun, RasterAsset

log = logging.getLogger("nisar.ingest")
STEPS = ["discover", "estimate", "retrieve", "checksum", "metadata", "validate", "process", "cog", "register", "publish"]


class IngestError(Exception):
    pass


class _Run:
    def __init__(self, db: Session, source_id: str):
        self.db = db
        self.row = IngestionRun(source_id=source_id)
        db.add(self.row)
        db.commit()

    def step(self, name: str, msg: str = "") -> None:
        self.row.step = name
        self.row.log += f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {name}: {msg}\n"
        self.db.commit()

    def finish(self, status: str, error: str | None = None) -> None:
        self.row.status, self.row.error = status, error
        self.row.finished_at = datetime.now(timezone.utc)
        self.db.commit()


def _cleanup_partial(db: Session, ds: Dataset | None, cog_dir: Path) -> None:
    if ds is not None:
        db.delete(ds)
        db.commit()
    shutil.rmtree(cog_dir, ignore_errors=True)


def _render_check(path: Path) -> None:
    """Test de visualisation : une lecture décimée doit contenir des pixels valides."""
    with rasterio.open(path) as src:
        data = src.read(1, out_shape=(min(32, src.height), min(32, src.width)), masked=True)
    if np.ma.count(data) == 0:
        raise IngestError("test de rendu : aucun pixel valide dans l'aperçu")


def ingest_file(db: Session, path: Path, *, maturity: str, is_demo: bool = False, source_uri: str | None = None,
                source_id: str | None = None, license_: str | None = None, settings: Settings | None = None) -> Dataset:
    s = settings or get_settings()
    path = Path(path)
    source_id = source_id or path.stem
    run = _Run(db, source_id)
    ds: Dataset | None = None
    cog_dir = s.cog_dir / source_id
    try:
        run.step("discover", f"fichier local {path.name}")
        run.step("estimate", f"{path.stat().st_size / 1e6:.1f} Mo")
        run.step("retrieve", "fichier déjà présent")
        checksum = sha256_file(path)
        existing = db.scalar(select(Dataset).where(Dataset.source_id == source_id))
        if existing and existing.status == "available" and existing.checksum_sha256 == checksum:
            run.step("checksum", "déjà ingéré, identique : rien à faire (idempotence)")
            run.finish("succeeded")
            return existing
        if existing:  # reprise : on repart d'un état propre
            run.step("checksum", "ingestion précédente incomplète ou différente : reprise à zéro")
            _cleanup_partial(db, existing, cog_dir)
        else:
            run.step("checksum", checksum[:16] + "…")
        run.step("metadata", "lecture HDF5")
        product = read_gcov(path)
        run.step("validate")
        errors = validate_product(product)
        if errors:
            raise ProductFormatError("; ".join(errors))
        run.step("process", f"bandes {', '.join(product.bands)}")
        west, south, east, north = bounds_wgs84(product)
        px, _ = product.pixel_size
        meta = product.meta
        ds = Dataset(
            source_id=source_id, source="NISAR" if not is_demo else "DEMO", product_type="GCOV",
            maturity="demo" if is_demo else maturity, acquisition_start=meta["start"], acquisition_end=meta["end"],
            track=meta["track"], orbit_direction=meta["orbit_direction"], polarizations=meta["polarizations"],
            resolution_m=px, crs=f"EPSG:{product.epsg}", extent=mapping(box(west, south, east, north)),
            west=west, south=south, east=east, north=north, nodata=product.nodata,
            processing_version=meta["product_version"], license=license_, source_uri=source_uri,
            checksum_sha256=checksum, status="processing", is_demo=is_demo,
            provenance={"ingested_with": "nisar-vision pipeline", "input_file": path.name,
                        "format_structure": "GCOV HDF5 (structure à confirmer sur granule réel)"})
        db.add(ds)
        db.commit()
        run.step("cog", "génération COG + overviews")
        manifest_assets = []
        for band, arr in product.bands.items():
            out = write_cog(arr, product.x, product.y, product.epsg, cog_dir / f"{band}.tif", product.nodata)
            info = raster_info(out)
            asset_sum = sha256_file(out)
            db.add(RasterAsset(dataset_id=ds.id, band=band, uri=str(out), width=info["width"], height=info["height"],
                               crs=info["crs"], nodata=info["nodata"], dtype=info["dtype"], checksum_sha256=asset_sum))
            manifest_assets.append({"band": band, "uri": str(out), "sha256": asset_sum})
            _render_check(out)
        db.commit()
        run.step("register", "dataset et assets enregistrés, rendu testé")
        write_manifest(s.data_dir / "manifests", source_id,
                       {"source_uri": source_uri, "input_sha256": checksum, "maturity": ds.maturity, "is_demo": is_demo,
                        "processing_version": ds.processing_version, "assets": manifest_assets,
                        "tools": {"rasterio": rasterio.__version__, "pipeline": "nisar-vision/1"}})
        ds.status = "available"
        db.commit()
        run.step("publish", "status=available")
        run.finish("succeeded")
        return ds
    except ProductFormatError as exc:
        log.warning("granule mis en quarantaine: %s", exc)
        _cleanup_partial(db, ds, cog_dir)
        q = s.quarantine_dir
        q.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, q / path.name)
        except OSError:
            pass
        run.finish("quarantined", str(exc))
        raise IngestError(f"{source_id} en quarantaine : {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("échec d'ingestion")
        db.rollback()
        _cleanup_partial(db, db.scalar(select(Dataset).where(Dataset.source_id == source_id)), cog_dir)
        run.finish("failed", str(exc))
        raise IngestError(f"{source_id} : échec d'ingestion : {exc}") from exc
