from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import client_id_optional, client_id_required
from app.core.db import get_db
from app.core.errors import NotFound
from app.models import Certificate, Story
from app.schemas.api import AttemptRequest, CertificateRequest
from app.services import learning

router = APIRouter(tags=["récits et apprentissage"])


def _scene(s) -> dict:
    return {"order": s.order, "title": s.title, "body": s.body, "center": [s.center_lon, s.center_lat], "zoom": s.zoom,
            "layers": s.layer_keys, "date_start": s.date_start, "date_end": s.date_end, "annotation": s.annotation,
            "figure": s.figure, "provenance": s.provenance, "limits": s.limits}


@router.get("/stories", summary="Catalogue des récits")
def stories(db: Session = Depends(get_db)):
    rows = db.scalars(select(Story).where(Story.status == "published").options(selectinload(Story.scenes))).all()
    return [{"id": s.id, "slug": s.slug, "title": s.title, "theme": s.theme, "synopsis": s.synopsis,
             "duration_min": s.duration_min, "is_example": s.is_example, "scene_count": len(s.scenes)} for s in rows]


@router.get("/stories/{story_id}", summary="Récit complet : scènes, couches, sources, provenance")
def story(story_id: str, db: Session = Depends(get_db)):
    q = select(Story).options(selectinload(Story.scenes))
    s = db.scalar(q.where(Story.id == int(story_id))) if story_id.isdigit() else db.scalar(q.where(Story.slug == story_id))
    if s is None:
        raise NotFound("Récit introuvable.")
    return {"id": s.id, "slug": s.slug, "title": s.title, "theme": s.theme, "synopsis": s.synopsis,
            "duration_min": s.duration_min, "is_example": s.is_example, "sources": s.sources,
            "scenes": [_scene(x) for x in s.scenes]}


@router.get("/learning/levels")
def levels(db: Session = Depends(get_db), client: str | None = Depends(client_id_optional)):
    return learning.list_levels(db, client)


@router.get("/learning/levels/{level_id}")
def level(level_id: int, db: Session = Depends(get_db), client: str | None = Depends(client_id_optional)):
    return learning.get_level(db, level_id, client)


@router.post("/learning/quiz/{quiz_id}/attempts", status_code=201, summary="Soumet un quiz : score, XP et badge calculés côté serveur")
def attempt(quiz_id: int, body: AttemptRequest, db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    return learning.submit_attempt(db, quiz_id, client, body.answers)


@router.get("/learning/progress")
def progress(db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    return learning.progress(db, client)


@router.get("/learning/badges")
def badges(db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    return learning.progress(db, client)["badges"]


@router.get("/learning/glossary")
def glossary(q: str | None = Query(None, max_length=80), level: int | None = Query(None, ge=1, le=5), db: Session = Depends(get_db)):
    return [{"term": t.term, "definition": t.definition, "example": t.example, "level": t.level_number}
            for t in learning.glossary(db, q, level)]


@router.post("/learning/certificate", status_code=201, summary="Délivre le certificat après les cinq niveaux")
def certificate(body: CertificateRequest, db: Session = Depends(get_db), client: str = Depends(client_id_required)):
    c = learning.issue_certificate(db, client, body.name)
    return {"code": c.code, "holder_name": c.holder_name, "issued_at": c.issued_at, "verify_url": f"/api/v1/learning/certificate/{c.code}"}


@router.get("/learning/certificate/{code}", summary="Vérifie un certificat (le nom est masqué en partie)")
def verify(code: str, db: Session = Depends(get_db)):
    c = db.scalar(select(Certificate).where(Certificate.code == code.upper()))
    if c is None:
        raise NotFound("Certificat inconnu.")
    parts = c.holder_name.split()
    masked = " ".join(p[0] + "." if i else p for i, p in enumerate(parts)) if len(parts) > 1 else c.holder_name
    return {"valid": True, "code": c.code, "holder": masked, "issued_at": c.issued_at}


@router.get("/learning/certificate/{code}/pdf")
def certificate_pdf(code: str, db: Session = Depends(get_db)):
    import io
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    c = db.scalar(select(Certificate).where(Certificate.code == code.upper()))
    if c is None:
        raise NotFound("Certificat inconnu.")
    buf = io.BytesIO()
    w, h = landscape(A4)
    pdf = canvas.Canvas(buf, pagesize=landscape(A4))
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(w / 2, h - 120, "Certificat NISAR Vision")
    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(w / 2, h - 190, "Décerné à")
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(w / 2, h - 230, c.holder_name)
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(w / 2, h - 290, "pour avoir validé les cinq niveaux du parcours de télédétection radar.")
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(w / 2, 90, f"Émis le {c.issued_at.date().isoformat()} · code de vérification {c.code}")
    pdf.drawCentredString(w / 2, 70, f"Vérification : /api/v1/learning/certificate/{c.code}")
    pdf.save()
    return Response(buf.getvalue(), media_type="application/pdf")
