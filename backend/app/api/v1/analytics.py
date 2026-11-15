from fastapi import APIRouter, Depends, Header
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import client_id_required
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError, NotFound
from app.models import AOI, Export, Job
from app.processing.geo import bbox_geojson, circle_geojson, validate_aoi_geometry
from app.schemas.api import (AOICreate, AOIOut, ChangeMatrixRequest, ExportRequest, JobOut, ProjectionRequest,
                             TimeSeriesRequest)
from app.services import jobs
from app.services.analytics_aoi import aoi_geometry
from app.workers.tasks import run_job_task

router = APIRouter(tags=["dashboard analytique"])


def _job_out(job: Job) -> dict:
    params = {k: v for k, v in job.params.items() if k not in ("client_id",)}
    return {"job_id": job.id, "kind": job.kind, "status": job.status, "progress": job.progress, "created_at": job.created_at,
            "started_at": job.started_at, "finished_at": job.finished_at, "error_message": job.error_message,
            "result": job.result, "params": params, "method_version": job.method_version,
            "result_url": f"/api/v1/jobs/{job.id}" if job.status == "succeeded" else None}


def _owned_job(db: Session, job_id: str, client: str) -> Job:
    job = jobs.get_job(db, job_id)
    if job.owner_id and job.owner_id != client:
        raise NotFound(f"Job {job_id} introuvable.")
    return job


def _submit(db: Session, kind: str, params: dict, client: str, idem: str | None, aoi_id: int | None):
    key = f"{client}:{idem}" if idem else None
    job, created = jobs.create_job(db, kind, params, key, aoi_id)
    if created:
        job.owner_id = client
        db.commit()
        run_job_task.delay(job.id)
        db.refresh(job)
    return _job_out(job)


@router.post("/analytics/aoi", response_model=AOIOut, status_code=201, summary="Crée une zone d'intérêt (GeoJSON, rayon ou rectangle)")
def create_aoi(body: AOICreate, db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    s = get_settings()
    if body.geometry is not None:
        source, geom = "geojson", body.geometry
    elif body.center is not None:
        source, geom = "radius", circle_geojson(body.center[0], body.center[1], body.radius_km)
    else:
        w, so, e, n = body.bbox
        if not (w < e and so < n):
            raise AppError("bbox invalide : ouest < est et sud < nord requis.", code="invalid_geometry")
        source, geom = "drawn", bbox_geojson(w, so, e, n)
    geometry, area = validate_aoi_geometry(geom, s.max_aoi_km2)
    aoi = AOI(title=body.title, geometry=geometry, source=source, area_km2=area, owner_id=client)
    db.add(aoi)
    db.commit()
    return aoi


@router.get("/analytics/aoi/{aoi_id}", response_model=AOIOut)
def get_aoi(aoi_id: int, db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    geometry = aoi_geometry(db, aoi_id, client)
    aoi = db.get(AOI, aoi_id)
    return {**{c: getattr(aoi, c) for c in ("id", "title", "source", "area_km2", "created_at")}, "geometry": geometry}


def _period_check(req) -> None:
    days = (req.date_end - req.date_start).days
    if days > get_settings().max_period_days:
        raise AppError(f"Période trop longue : {days} jours (maximum {get_settings().max_period_days}).", code="too_large")


@router.post("/analytics/time-series", response_model=JobOut, status_code=202, summary="Série temporelle sur une AOI (job asynchrone)")
def time_series(body: TimeSeriesRequest, db: Session = Depends(get_db), client: str = Depends(client_id_required),
                idempotency_key: str | None = Header(default=None)):
    _period_check(body)
    geometry = aoi_geometry(db, body.aoi_id, client)
    params = {"geometry": geometry, "aoi_id": body.aoi_id, "date_start": body.date_start.isoformat(),
              "date_end": body.date_end.isoformat(), "frequency": body.frequency, "variables": body.variables,
              "include_demo": body.include_demo}
    return _submit(db, "time_series", params, client, idempotency_key, body.aoi_id)


@router.post("/analytics/change-matrix", response_model=JobOut, status_code=202, summary="Matrice de transition entre deux dates")
def change_matrix(body: ChangeMatrixRequest, db: Session = Depends(get_db), client: str = Depends(client_id_required),
                  idempotency_key: str | None = Header(default=None)):
    if body.date_a == body.date_b:
        raise AppError("Les deux dates doivent être différentes.", code="validation_error")
    geometry = aoi_geometry(db, body.aoi_id, client)
    params = {"geometry": geometry, "aoi_id": body.aoi_id, "date_a": body.date_a.isoformat(), "date_b": body.date_b.isoformat(),
              "include_demo": body.include_demo}
    return _submit(db, "change_matrix", params, client, idempotency_key, body.aoi_id)


@router.post("/analytics/projection", response_model=JobOut, status_code=202, summary="Projection exploratoire (what-if)")
def projection(body: ProjectionRequest, db: Session = Depends(get_db), client: str = Depends(client_id_required),
               idempotency_key: str | None = Header(default=None)):
    _period_check(body)
    geometry = aoi_geometry(db, body.aoi_id, client)
    params = {"geometry": geometry, "aoi_id": body.aoi_id, "date_start": body.date_start.isoformat(),
              "date_end": body.date_end.isoformat(), "frequency": body.frequency, "variables": body.variables,
              "variable": body.variable, "horizon_months": body.horizon_months, "include_demo": body.include_demo}
    return _submit(db, "projection", params, client, idempotency_key, body.aoi_id)


@router.get("/jobs/{job_id}", response_model=JobOut, summary="Statut, progression et résultat d'un job")
def job(job_id: str, db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    return _job_out(_owned_job(db, job_id, client))


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel(job_id: str, db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    _owned_job(db, job_id, client)
    return _job_out(jobs.cancel_job(db, job_id))


@router.post("/exports", response_model=JobOut, status_code=202, summary="Export d'une analyse (CSV, GeoJSON, SVG, PDF)")
def create_export(body: ExportRequest, db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    _owned_job(db, body.job_id, client)
    return _submit(db, "export", {"source_job_id": body.job_id, "format": body.format}, client, None, None)


@router.get("/exports/{export_id}/download", summary="Télécharge un export (lien à durée limitée)")
def download(export_id: str, db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    from datetime import datetime, timezone
    from pathlib import Path
    exp = db.get(Export, export_id)
    if exp is None:
        raise NotFound("Export introuvable ou expiré.")
    owner_job = db.get(Job, exp.job_id)
    if owner_job is None or (owner_job.owner_id and owner_job.owner_id != client):
        raise NotFound("Export introuvable ou expiré.")
    expires = exp.expires_at if exp.expires_at.tzinfo else exp.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc) or not Path(exp.path).exists():
        raise NotFound("Export introuvable ou expiré.")
    media = {"csv": "text/csv", "geojson": "application/geo+json", "svg": "image/svg+xml", "pdf": "application/pdf"}[exp.format]
    return FileResponse(exp.path, media_type=media, filename=f"nisar-vision-{export_id[:8]}.{exp.format}")
