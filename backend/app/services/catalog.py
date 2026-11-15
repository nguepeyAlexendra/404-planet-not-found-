"""Catalogue : datasets, couches, couverture temporelle et spatiale."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFound
from app.models import Dataset, Layer, RasterAsset
from app.services.dates import day_bounds


def _base(include_demo: bool):
    q = select(Dataset).where(Dataset.status == "available").options(selectinload(Dataset.assets))
    if not include_demo:
        q = q.where(Dataset.is_demo.is_(False))
    return q


def list_datasets(db: Session, *, product_type: str | None = None, maturity: str | None = None,
                  bbox: tuple[float, float, float, float] | None = None, start: date | None = None,
                  end: date | None = None, include_demo: bool = False, page: int = 1, page_size: int = 50):
    q = _base(include_demo)
    if product_type:
        q = q.where(Dataset.product_type == product_type)
    if maturity:
        q = q.where(Dataset.maturity == maturity)
    if bbox:
        w, s, e, n = bbox
        q = q.where(Dataset.east >= w, Dataset.west <= e, Dataset.north >= s, Dataset.south <= n)
    if start:
        q = q.where(Dataset.acquisition_start >= day_bounds(start)[0])
    if end:
        q = q.where(Dataset.acquisition_start < day_bounds(end)[1])
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    items = db.scalars(q.order_by(Dataset.acquisition_start.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total or 0


def get_dataset(db: Session, dataset_id: int) -> Dataset:
    ds = db.scalar(select(Dataset).where(Dataset.id == dataset_id).options(selectinload(Dataset.assets)))
    if ds is None:
        raise NotFound(f"Dataset {dataset_id} introuvable.")
    return ds


def list_layers(db: Session) -> list[Layer]:
    return list(db.scalars(select(Layer).order_by(Layer.sort_order, Layer.key)))


def get_layer(db: Session, key: str) -> Layer:
    layer = db.scalar(select(Layer).where(Layer.key == key))
    if layer is None:
        raise NotFound(f"Couche {key!r} introuvable.")
    return layer


def datasets_for_layer(db: Session, layer: Layer, *, day: date | None = None, include_demo: bool = False,
                       bbox: tuple[float, float, float, float] | None = None) -> list[Dataset]:
    q = (_base(include_demo).where(Dataset.product_type == layer.product_type)
         .where(Dataset.id.in_(select(RasterAsset.dataset_id).where(RasterAsset.band == layer.band))))
    if day:
        lo, hi = day_bounds(day)
        q = q.where(Dataset.acquisition_start >= lo, Dataset.acquisition_start < hi)
    if bbox:
        w, s, e, n = bbox
        q = q.where(Dataset.east >= w, Dataset.west <= e, Dataset.north >= s, Dataset.south <= n)
    return list(db.scalars(q.order_by(Dataset.acquisition_start)))


def layer_coverage(db: Session, layer: Layer, include_demo: bool = False) -> dict:
    """Couverture réelle : dates disponibles (les trous restent visibles), emprise, niveaux de maturité."""
    dss = datasets_for_layer(db, layer, include_demo=include_demo)
    if not dss:
        return {"available": False, "dates": [], "count": 0, "bounds": None, "maturities": [], "has_demo": False}
    return {"available": True, "dates": sorted({d.acquisition_start.date().isoformat() for d in dss}), "count": len(dss),
            "bounds": [min(d.west for d in dss), min(d.south for d in dss), max(d.east for d in dss), max(d.north for d in dss)],
            "maturities": sorted({d.maturity for d in dss}), "has_demo": any(d.is_demo for d in dss)}


def asset_path(ds: Dataset, band: str) -> str | None:
    for a in ds.assets:
        if a.band == band:
            return a.uri
    return None
