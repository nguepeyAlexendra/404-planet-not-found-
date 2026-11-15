from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models import AOI


def aoi_geometry(db: Session, aoi_id: int, client_id: str | None) -> dict:
    """Une AOI appartient à la session qui l'a créée : une autre session reçoit un 404 (pas de fuite)."""
    aoi = db.get(AOI, aoi_id)
    if aoi is None or (aoi.owner_id and aoi.owner_id != client_id):
        raise NotFound(f"Zone {aoi_id} introuvable.")
    return aoi.geometry
