from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.geotypes import GeoJSONGeometry
from app.models.catalog import utcnow


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(32))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    location: Mapped[dict | None] = mapped_column(GeoJSONGeometry, nullable=True)
    source_label: Mapped[str] = mapped_column(String(200), default="")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_example: Mapped[bool] = mapped_column(Boolean, default=True)


class Story(Base):
    __tablename__ = "story"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    theme: Mapped[str] = mapped_column(String(64))
    synopsis: Mapped[str] = mapped_column(Text)
    duration_min: Mapped[int] = mapped_column(Integer, default=5)
    is_example: Mapped[bool] = mapped_column(Boolean, default=True)  # chiffres non vérifiés = exemple
    status: Mapped[str] = mapped_column(String(16), default="published")
    sources: Mapped[list] = mapped_column(JSON, default=list)

    scenes: Mapped[list["Scene"]] = relationship(back_populates="story", cascade="all, delete-orphan",
                                                 order_by="Scene.order")


class Scene(Base):
    __tablename__ = "scene"
    __table_args__ = (UniqueConstraint("story_id", "order", name="uq_scene_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("story.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    center_lon: Mapped[float] = mapped_column(Float)
    center_lat: Mapped[float] = mapped_column(Float)
    zoom: Mapped[float] = mapped_column(Float, default=4)
    layer_keys: Mapped[list] = mapped_column(JSON, default=list)
    date_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    date_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    annotation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    figure: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {label,value,unit,source,verified}
    provenance: Mapped[str] = mapped_column(Text, default="")
    limits: Mapped[str] = mapped_column(Text, default="")

    story: Mapped[Story] = relationship(back_populates="scenes")


class LearningLevel(Base):
    __tablename__ = "learning_level"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text)
    xp: Mapped[int] = mapped_column(Integer)
    badge_key: Mapped[str] = mapped_column(String(64))
    simulator: Mapped[str] = mapped_column(String(32))  # clé du simulateur côté frontend

    lessons: Mapped[list["Lesson"]] = relationship(cascade="all, delete-orphan", order_by="Lesson.order")
    quiz: Mapped["Quiz"] = relationship(back_populates="level", uselist=False, cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lesson"

    id: Mapped[int] = mapped_column(primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("learning_level.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text)


class Quiz(Base):
    __tablename__ = "quiz"

    id: Mapped[int] = mapped_column(primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("learning_level.id", ondelete="CASCADE"), unique=True)
    pass_ratio: Mapped[float] = mapped_column(Float, default=0.7)

    level: Mapped[LearningLevel] = relationship(back_populates="quiz")
    questions: Mapped[list["Question"]] = relationship(cascade="all, delete-orphan", order_by="Question.order")


class Question(Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quiz.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)

    options: Mapped[list["AnswerOption"]] = relationship(cascade="all, delete-orphan", order_by="AnswerOption.id")


class AnswerOption(Base):
    __tablename__ = "answer_option"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)


class Attempt(Base):
    """Tentative de quiz. XP et badge ne sont accordés qu'une fois (award_key unique)."""
    __tablename__ = "attempt"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quiz.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    answers: Mapped[dict] = mapped_column(JSON)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    award_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserProgress(Base):
    __tablename__ = "user_progress"
    __table_args__ = (UniqueConstraint("client_id", "level_id", name="uq_progress"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("learning_level.id", ondelete="CASCADE"))
    best_score: Mapped[float] = mapped_column(Float, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Badge(Base):
    __tablename__ = "badge"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)


class UserBadge(Base):
    __tablename__ = "user_badge"
    __table_args__ = (UniqueConstraint("client_id", "badge_key", name="uq_user_badge"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    badge_key: Mapped[str] = mapped_column(String(64))
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Certificate(Base):
    __tablename__ = "certificate"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    holder_name: Mapped[str] = mapped_column(String(120))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GlossaryTerm(Base):
    __tablename__ = "glossary_term"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(120), unique=True)
    definition: Mapped[str] = mapped_column(Text)
    example: Mapped[str] = mapped_column(Text, default="")
    level_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
