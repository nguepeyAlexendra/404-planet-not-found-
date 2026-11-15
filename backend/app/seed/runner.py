"""Données de référence (couches, règles, récits, parcours, glossaire) et données de démonstration."""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.demo import make_demo_gcov
from app.ingestion.pipeline import ingest_file
from app.models import (AnswerOption, Badge, ClassificationRuleset, GlossaryTerm, Layer, LearningLevel, Lesson, Question,
                        Quiz, Scene, Story)
from app.processing.classifier import load_ruleset
from app.seed.demo_dates import DEMO_DATES, DEMO_DEFOREST
from app.seed.glossary import GLOSSARY
from app.seed.learning import LEVELS
from app.seed.stories import STORIES

LAYERS = [
    dict(key="nisar-gcov-hh", label="NISAR L-band, rétrodiffusion HH", group="RADAR", product_type="GCOV", band="HHHH",
         unit="dB", style={"rescale": [-25, 0], "colormap": "gray"}, sort_order=1,
         description="Rétrodiffusion en polarisation HH (GCOV, puissance linéaire affichée en dB)."),
    dict(key="nisar-gcov-hv", label="NISAR L-band, rétrodiffusion HV", group="RADAR", product_type="GCOV", band="HVHV",
         unit="dB", style={"rescale": [-30, -5], "colormap": "gray"}, sort_order=2,
         description="Rétrodiffusion en polarisation croisée HV, sensible à la diffusion de volume."),
]


def seed_reference(db: Session) -> None:
    for spec in LAYERS:
        if not db.scalar(select(Layer).where(Layer.key == spec["key"])):
            db.add(Layer(**spec))
    rs = load_ruleset()
    if not db.scalar(select(ClassificationRuleset).where(ClassificationRuleset.version == rs["version"])):
        db.add(ClassificationRuleset(version=rs["version"], name=rs["name"], config=rs, notes=rs["notes"], is_active=True,
                                     validated=False))
    for term, definition, example, level in GLOSSARY:
        if not db.scalar(select(GlossaryTerm).where(GlossaryTerm.term == term)):
            db.add(GlossaryTerm(term=term, definition=definition, example=example or "", level_number=level))
    for spec in STORIES:
        if db.scalar(select(Story).where(Story.slug == spec["slug"])):
            continue
        story = Story(slug=spec["slug"], title=spec["title"], theme=spec["theme"], synopsis=spec["synopsis"],
                      duration_min=spec["duration_min"], is_example=spec["is_example"], sources=spec["sources"])
        for i, sc in enumerate(spec["scenes"], start=1):
            story.scenes.append(Scene(order=i, title=sc["title"], body=sc["body"], center_lon=sc["lon"], center_lat=sc["lat"],
                                      zoom=sc["zoom"], layer_keys=sc["layers"], date_start=sc.get("start"), date_end=sc.get("end"),
                                      provenance=sc["provenance"], limits=sc["limits"]))
        db.add(story)
    for lv in LEVELS:
        if db.scalar(select(LearningLevel).where(LearningLevel.number == lv["number"])):
            continue
        key, label = lv["badge"]
        if not db.scalar(select(Badge).where(Badge.key == key)):
            db.add(Badge(key=key, label=label, description=f"Niveau {lv['number']} terminé : {lv['title']}."))
        level = LearningLevel(number=lv["number"], title=lv["title"], summary=lv["summary"], xp=lv["xp"], badge_key=key,
                              simulator=lv["simulator"])
        for i, (t, c) in enumerate(lv["lessons"], start=1):
            level.lessons.append(Lesson(order=i, title=t, content=c))
        quiz = Quiz(pass_ratio=0.7)
        for i, (text, options, correct, expl) in enumerate(lv["questions"], start=1):
            q = Question(order=i, text=text, explanation=expl)
            for j, opt in enumerate(options):
                q.options.append(AnswerOption(text=opt, is_correct=(j == correct)))
            quiz.questions.append(q)
        level.quiz = quiz
        db.add(level)
    db.commit()


def seed_demo_data(db: Session) -> list[int]:
    """Six granules SIMULÉS (is_demo=True, maturité « demo »), jamais mélangés au catalogue réel."""
    s = get_settings()
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (d, f) in enumerate(zip(DEMO_DATES, DEMO_DEFOREST)):
            start = datetime.fromisoformat(d).replace(hour=5, tzinfo=timezone.utc)
            path = make_demo_gcov(Path(tmp) / f"DEMO_NISAR_L2_GCOV_{d}.h5", start, seed=10 + i, deforest=f)
            ds = ingest_file(db, path, maturity="demo", is_demo=True, source_id=f"DEMO_NISAR_L2_GCOV_{d}",
                             source_uri="simulated://nisar-vision/demo", license_="Données simulées, libres", settings=s)
            out.append(ds.id)
    return out
