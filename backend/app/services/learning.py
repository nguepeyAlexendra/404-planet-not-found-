"""Parcours éducatif : niveaux, quiz, XP, badges, certificat. Tout est validé côté serveur."""
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, Conflict, NotFound
from app.models import (Attempt, Badge, Certificate, GlossaryTerm, LearningLevel, Quiz, Question, UserBadge, UserProgress)

CLIENT_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def check_client(client_id: str | None) -> str:
    if not client_id or not CLIENT_RE.match(client_id):
        raise AppError("Identifiant de session invalide (en-tête X-Client-Id requis : 8 à 64 caractères).", code="invalid_client_id")
    return client_id


def _completed(db: Session, client_id: str) -> set[int]:
    rows = db.scalars(select(LearningLevel.number).join(UserProgress, UserProgress.level_id == LearningLevel.id)
                      .where(UserProgress.client_id == client_id, UserProgress.completed.is_(True)))
    return set(rows)


def _levels(db: Session) -> list[LearningLevel]:
    return list(db.scalars(select(LearningLevel).order_by(LearningLevel.number)))


def list_levels(db: Session, client_id: str | None) -> list[dict]:
    done = _completed(db, client_id) if client_id else set()
    out = []
    for lv in _levels(db):
        unlocked = lv.number == 1 or (lv.number - 1) in done
        out.append({"id": lv.id, "number": lv.number, "title": lv.title, "summary": lv.summary, "xp": lv.xp,
                    "badge_key": lv.badge_key, "simulator": lv.simulator, "unlocked": unlocked, "completed": lv.number in done})
    return out


def get_level(db: Session, level_id: int, client_id: str | None) -> dict:
    lv = db.scalar(select(LearningLevel).where(LearningLevel.id == level_id)
                   .options(selectinload(LearningLevel.lessons), selectinload(LearningLevel.quiz).selectinload(Quiz.questions).selectinload(Question.options)))
    if lv is None:
        raise NotFound(f"Niveau {level_id} introuvable.")
    done = _completed(db, client_id) if client_id else set()
    if lv.number != 1 and (lv.number - 1) not in done:
        raise AppError(f"Niveau verrouillé : terminez d'abord le niveau {lv.number - 1}.", code="level_locked", status_code=403)
    return {"id": lv.id, "number": lv.number, "title": lv.title, "summary": lv.summary, "xp": lv.xp, "simulator": lv.simulator,
            "lessons": [{"order": x.order, "title": x.title, "content": x.content} for x in lv.lessons],
            "quiz": {"id": lv.quiz.id, "pass_ratio": lv.quiz.pass_ratio,
                     "questions": [{"id": q.id, "order": q.order, "text": q.text,
                                    "options": [{"id": o.id, "text": o.text} for o in q.options]} for q in lv.quiz.questions]},
            "completed": lv.number in done}


def submit_attempt(db: Session, quiz_id: int, client_id: str, answers: dict[int, int]) -> dict:
    quiz = db.scalar(select(Quiz).where(Quiz.id == quiz_id).options(selectinload(Quiz.questions).selectinload(Question.options),
                                                                  selectinload(Quiz.level)))
    if quiz is None:
        raise NotFound(f"Quiz {quiz_id} introuvable.")
    level = quiz.level
    done = _completed(db, client_id)
    if level.number != 1 and (level.number - 1) not in done:
        raise AppError("Niveau verrouillé.", code="level_locked", status_code=403)
    qids = {q.id for q in quiz.questions}
    if set(answers) != qids:
        raise AppError("Toutes les questions doivent recevoir une réponse.", code="invalid_answers",
                       details={"expected": sorted(qids), "received": sorted(answers)})
    results, correct = [], 0
    for q in quiz.questions:
        valid_ids = {o.id for o in q.options}
        chosen = answers[q.id]
        if chosen not in valid_ids:
            raise AppError(f"Option {chosen} invalide pour la question {q.id}.", code="invalid_answers")
        good = next(o.id for o in q.options if o.is_correct)
        ok = chosen == good
        correct += ok
        results.append({"question_id": q.id, "chosen": chosen, "correct_option_id": good, "is_correct": ok,
                        "explanation": q.explanation})
    score = correct / len(quiz.questions)
    passed = score >= quiz.pass_ratio
    award_key = f"{client_id}:{level.id}" if passed else None
    xp, new_badge = 0, None
    if passed and not db.scalar(select(Attempt).where(Attempt.award_key == award_key)):
        xp = level.xp
        if not db.scalar(select(UserBadge).where(UserBadge.client_id == client_id, UserBadge.badge_key == level.badge_key)):
            db.add(UserBadge(client_id=client_id, badge_key=level.badge_key))
            new_badge = level.badge_key
    else:
        award_key = None  # déjà récompensé (ou échec) : aucune clé, aucun XP
    db.add(Attempt(client_id=client_id, quiz_id=quiz.id, score=score, passed=passed, answers={str(k): v for k, v in answers.items()},
                   xp_awarded=xp, award_key=award_key))
    prog = db.scalar(select(UserProgress).where(UserProgress.client_id == client_id, UserProgress.level_id == level.id))
    if prog is None:
        prog = UserProgress(client_id=client_id, level_id=level.id, best_score=0)
        db.add(prog)
    prog.best_score = max(prog.best_score or 0, score)
    if passed and not prog.completed:
        prog.completed, prog.completed_at = True, datetime.now(timezone.utc)
    db.commit()
    return {"score": round(score, 3), "passed": passed, "correct": correct, "total": len(quiz.questions), "xp_awarded": xp,
            "new_badge": new_badge, "results": results, "pass_ratio": quiz.pass_ratio}


def progress(db: Session, client_id: str) -> dict:
    xp = db.scalar(select(func.coalesce(func.sum(Attempt.xp_awarded), 0)).where(Attempt.client_id == client_id)) or 0
    done = sorted(_completed(db, client_id))
    badges = db.scalars(select(Badge).join(UserBadge, UserBadge.badge_key == Badge.key).where(UserBadge.client_id == client_id)).all()
    total = db.scalar(select(func.count()).select_from(LearningLevel)) or 0
    cert = db.scalar(select(Certificate).where(Certificate.client_id == client_id))
    return {"xp": int(xp), "completed_levels": done, "total_levels": total,
            "badges": [{"key": b.key, "label": b.label, "description": b.description} for b in badges],
            "certificate_eligible": total > 0 and len(done) == total, "certificate_code": cert.code if cert else None}


def issue_certificate(db: Session, client_id: str, name: str) -> Certificate:
    name = name.strip()
    if not 2 <= len(name) <= 80:
        raise AppError("Le nom doit contenir entre 2 et 80 caractères.", code="invalid_name")
    info = progress(db, client_id)
    if not info["certificate_eligible"]:
        raise AppError("Le certificat n'est délivré qu'après validation des cinq niveaux.", code="not_eligible", status_code=403)
    existing = db.scalar(select(Certificate).where(Certificate.client_id == client_id))
    if existing:
        raise Conflict("Un certificat existe déjà pour cette session.")
    cert = Certificate(code=uuid.uuid4().hex[:16].upper(), client_id=client_id, holder_name=name)
    db.add(cert)
    db.commit()
    return cert


def glossary(db: Session, q: str | None = None, level: int | None = None) -> list[GlossaryTerm]:
    query = select(GlossaryTerm).order_by(GlossaryTerm.term)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(func.lower(GlossaryTerm.term).like(like) | func.lower(GlossaryTerm.definition).like(like))
    if level:
        query = query.where(GlossaryTerm.level_number == level)
    return list(db.scalars(query))
