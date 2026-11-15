from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Dataset

router = APIRouter(tags=["santé"])


@router.get("/health", summary="Liveness : le processus répond")
def health():
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness : base joignable, catalogue lisible")
def ready(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    total = db.scalar(select(func.count()).select_from(Dataset)) or 0
    real = db.scalar(select(func.count()).select_from(Dataset).where(Dataset.is_demo.is_(False), Dataset.status == "available")) or 0
    return {"status": "ready", "datasets_total": total, "datasets_real_available": real}
