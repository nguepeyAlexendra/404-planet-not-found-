from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.catalog import utcnow

JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")


class Job(Base):
    """Calcul asynchrone (analyse, export). Porte paramètres, version de méthode et résultat (traçabilité)."""
    __tablename__ = "analysis_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # time_series|change_matrix|projection|export|change_detection
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    params: Mapped[dict] = mapped_column(JSON)
    method_version: Mapped[str] = mapped_column(String(32), default="1")
    owner_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    log: Mapped[str] = mapped_column(Text, default="")
    aoi_id: Mapped[int | None] = mapped_column(ForeignKey("aoi.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Export(Base):
    __tablename__ = "export"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("analysis_job.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(16))  # csv|geojson|png|pdf
    path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
