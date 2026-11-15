"""Orchestration des jobs asynchrones : création idempotente, exécution, statut, annulation."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.errors import AppError, NotFound
from app.models import Job
from app.services import analytics, exports

log = logging.getLogger("nisar.jobs")
RUNNERS = {"time_series": analytics.time_series, "change_matrix": analytics.change_matrix,
           "projection": analytics.run_projection}


def create_job(db: Session, kind: str, params: dict, idempotency_key: str | None = None, aoi_id: int | None = None) -> tuple[Job, bool]:
    """Retourne (job, créé). Avec une clé d'idempotence déjà vue, renvoie le job existant sans doublon."""
    if kind not in RUNNERS and kind != "export":
        raise AppError(f"Type d'analyse inconnu : {kind}.", code="unknown_job_kind")
    if idempotency_key:
        existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing:
            return existing, False
    job = Job(id=str(uuid.uuid4()), kind=kind, params=params, idempotency_key=idempotency_key, aoi_id=aoi_id,
              method_version=analytics.METHOD_VERSION)
    db.add(job)
    db.commit()
    return job, True


def get_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFound(f"Job {job_id} introuvable.")
    return job


def cancel_job(db: Session, job_id: str) -> Job:
    job = get_job(db, job_id)
    if job.status in ("succeeded", "failed", "cancelled"):
        raise AppError(f"Le job est déjà {job.status}.", code="conflict", status_code=409)
    job.status = "cancelled"
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    return job


def run_job(job_id: str) -> None:
    """Exécute un job avec sa propre session (worker ou mode eager). Les erreurs sont journalisées dans le job."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None or job.status != "queued":
            return
        job.status, job.started_at = "running", datetime.now(timezone.utc)
        db.commit()

        def progress(p: float, msg: str) -> None:
            job.progress = round(p, 3)
            job.log += f"{msg}\n"
            db.commit()

        try:
            if job.kind == "export":
                exp = exports.build_export(db, job.params["source_job_id"], job.params["format"], job.id)
                result = {"export_id": exp.id, "format": exp.format, "size_bytes": exp.size_bytes,
                          "download_path": f"/api/v1/exports/{exp.id}/download", "expires_at": exp.expires_at.isoformat()}
            else:
                result = RUNNERS[job.kind](db, job.params, progress)
            db.refresh(job)  # une annulation pendant le calcul est respectée
            if job.status == "cancelled":
                return
            job.result, job.status, job.progress = result, "succeeded", 1.0
        except AppError as exc:
            job.status, job.error_message = "failed", exc.message
            job.result = {"error_code": exc.code, "details": exc.details}
        except Exception as exc:  # noqa: BLE001
            log.exception("job en échec", extra={"job_id": job_id})
            job.status, job.error_message = "failed", "Erreur interne pendant le calcul."
            job.log += f"{type(exc).__name__}: {exc}\n"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
