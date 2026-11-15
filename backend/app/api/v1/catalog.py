from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import Event
from app.schemas.api import DatasetOut, LayerOut, Page
from app.services import catalog, pixel
from app.services.dates import parse_date

router = APIRouter(tags=["catalogue et carte"])


def _bbox(value: str | None):
    if value is None:
        return None
    try:
        w, s, e, n = (float(v) for v in value.split(","))
    except ValueError as exc:
        raise AppError("bbox : quatre nombres attendus (ouest,sud,est,nord).", code="invalid_bbox") from exc
    if not (-180 <= w <= e <= 180 and -90 <= s <= n <= 90):
        raise AppError("bbox hors limites ou inversée.", code="invalid_bbox")
    return w, s, e, n


@router.get("/datasets", response_model=Page, summary="Liste paginée des produits disponibles")
def datasets(product_type: str | None = None, maturity: str | None = None, bbox: str | None = None,
             start: date | None = None, end: date | None = None, include_demo: bool = False,
             page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    items, total = catalog.list_datasets(db, product_type=product_type, maturity=maturity, bbox=_bbox(bbox), start=start,
                                         end=end, include_demo=include_demo, page=page, page_size=page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def dataset(dataset_id: int, db: Session = Depends(get_db)):
    return catalog.get_dataset(db, dataset_id)


def _layer_out(db: Session, layer, include_demo: bool, with_coverage: bool = True) -> dict:
    s = get_settings()
    base = s.tile_base_url.rstrip("/") or ""
    out = LayerOut.model_validate(layer).model_dump()
    out["coverage"] = catalog.layer_coverage(db, layer, include_demo) if with_coverage else None
    out["tiles"] = f"{base}/api/v1/tiles/{layer.key}/{{date}}/{{z}}/{{x}}/{{y}}.png" + ("?demo=1" if include_demo else "")
    return out


@router.get("/layers", response_model=list[LayerOut], summary="Couches avec couverture réelle")
def layers(include_demo: bool = False, db: Session = Depends(get_db)):
    return [_layer_out(db, l, include_demo) for l in catalog.list_layers(db)]


@router.get("/layers/{key}/metadata", summary="Métadonnées d'une couche : granules, dates, niveaux de maturité, provenance")
def layer_metadata(key: str, include_demo: bool = False, db: Session = Depends(get_db)):
    layer = catalog.get_layer(db, key)
    dss = catalog.datasets_for_layer(db, layer, include_demo=include_demo)
    return {"layer": _layer_out(db, layer, include_demo),
            "datasets": [{"id": d.id, "source_id": d.source_id, "date": d.acquisition_start.date().isoformat(),
                          "maturity": d.maturity, "is_demo": d.is_demo, "processing_version": d.processing_version,
                          "resolution_m": d.resolution_m, "crs": d.crs, "track": d.track,
                          "orbit_direction": d.orbit_direction, "source_uri": d.source_uri,
                          "checksum_sha256": d.checksum_sha256, "license": d.license, "provenance": d.provenance} for d in dss],
            "note": "Les dates listées sont les seules acquisitions réellement présentes dans le catalogue."}


@router.get("/map/pixel", summary="Valeurs d'un pixel, unités et interprétation prudente")
def map_pixel(lon: float = Query(ge=-180, le=180), lat: float = Query(ge=-90, le=90), date_: str = Query(alias="date"),
              layer: str | None = None, include_demo: bool = False, db: Session = Depends(get_db)):
    return pixel.pixel_info(db, lon, lat, parse_date(date_), layer, include_demo)


@router.get("/events", summary="Événements datés et sourcés")
def events(db: Session = Depends(get_db)):
    rows = db.scalars(select(Event).order_by(Event.date)).all()
    return [{"id": e.id, "title": e.title, "type": e.type, "date": e.date.isoformat(), "location": e.location,
             "source_label": e.source_label, "source_url": e.source_url, "is_example": e.is_example} for e in rows]
