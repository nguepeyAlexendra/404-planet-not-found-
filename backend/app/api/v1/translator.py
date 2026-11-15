from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import client_id_optional
from app.core.db import get_db
from app.models import ClassificationRuleset
from app.schemas.api import ChangesRequest
from app.services import translator
from app.services.analytics_aoi import aoi_geometry

router = APIRouter(prefix="/translator", tags=["traducteur radar"])


@router.get("/ruleset", summary="Règles de classification actives (version, seuils, notes)")
def ruleset(db: Session = Depends(get_db)):
    from sqlalchemy import select
    rs = db.scalar(select(ClassificationRuleset).where(ClassificationRuleset.is_active.is_(True)))
    return {"version": rs.version, "name": rs.name, "validated": rs.validated, "notes": rs.notes, "config": rs.config}


@router.get("/classification", summary="Proportions de classes sur un produit (emprise entière ou AOI)")
def classification(dataset_id: int, aoi_id: int | None = None, db: Session = Depends(get_db),
                   client: str | None = Depends(client_id_optional)):
    geometry = aoi_geometry(db, aoi_id, client) if aoi_id else None
    return translator.classification_summary(db, dataset_id, geometry)


@router.post("/changes", summary="Détection de changements entre deux produits comparables")
def changes(body: ChangesRequest, db: Session = Depends(get_db), client: str | None = Depends(client_id_optional)):
    geometry = aoi_geometry(db, body.aoi_id, client) if body.aoi_id else None
    return translator.change_summary(db, body.before_dataset_id, body.after_dataset_id, body.band, body.threshold_db, geometry)
