from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.geotypes import GeoJSONGeometry


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


MATURITIES = ("beta", "provisional", "validated")
DATASET_STATUSES = ("quarantined", "processing", "available")


class Dataset(Base):
    """Un produit (granule) avec ses métadonnées minimales et sa provenance."""
    __tablename__ = "dataset"
    __table_args__ = (
        CheckConstraint("maturity in ('beta','provisional','validated','demo')", name="ck_dataset_maturity"),
        CheckConstraint("status in ('quarantined','processing','available')", name="ck_dataset_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="NISAR")
    sensor: Mapped[str] = mapped_column(String(32), default="L-SAR")
    frequency_band: Mapped[str] = mapped_column(String(8), default="L")
    product_type: Mapped[str] = mapped_column(String(16), index=True)  # GCOV, GSLC...
    maturity: Mapped[str] = mapped_column(String(16), default="provisional")
    acquisition_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acquisition_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    track: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orbit_direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    polarizations: Mapped[list] = mapped_column(JSON, default=list)
    resolution_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    crs: Mapped[str] = mapped_column(String(32), default="EPSG:4326")
    extent: Mapped[dict | None] = mapped_column(GeoJSONGeometry, nullable=True)
    west: Mapped[float] = mapped_column(Float)
    south: Mapped[float] = mapped_column(Float)
    east: Mapped[float] = mapped_column(Float)
    north: Mapped[float] = mapped_column(Float)
    units: Mapped[str] = mapped_column(String(64), default="linear power (gamma0)")
    nodata: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="processing", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assets: Mapped[list["RasterAsset"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class RasterAsset(Base):
    """Fichier COG d'une bande d'un dataset (la base garde l'URI, pas le raster)."""
    __tablename__ = "raster_asset"
    __table_args__ = (UniqueConstraint("dataset_id", "band", name="uq_asset_dataset_band"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id", ondelete="CASCADE"), index=True)
    band: Mapped[str] = mapped_column(String(16))  # HHHH, HVHV, VVVV...
    uri: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(16), default="COG")
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    crs: Mapped[str] = mapped_column(String(32))
    nodata: Mapped[float | None] = mapped_column(Float, nullable=True)
    dtype: Mapped[str] = mapped_column(String(16), default="float32")
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="assets")


class IngestionRun(Base):
    """Historique d'une ingestion : étape atteinte, journal, erreur éventuelle."""
    __tablename__ = "ingestion_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|succeeded|failed|quarantined
    step: Mapped[str] = mapped_column(String(32), default="discover")
    log: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Layer(Base):
    """Couche affichable : un type de produit + une bande/polarisation."""
    __tablename__ = "layer"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(128))
    group: Mapped[str] = mapped_column(String(32))  # RADAR, OPTIQUE, HUMAIN, HYDROLOGIE, VEGETATION
    product_type: Mapped[str] = mapped_column(String(16))
    band: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(64), default="NISAR")
    unit: Mapped[str] = mapped_column(String(32), default="dB")
    style: Mapped[dict] = mapped_column(JSON, default=dict)  # rescale, colormap
    default_opacity: Mapped[float] = mapped_column(Float, default=0.85)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")


class AOI(Base):
    __tablename__ = "aoi"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    geometry: Mapped[dict] = mapped_column(GeoJSONGeometry)
    source: Mapped[str] = mapped_column(String(16), default="drawn")  # drawn|geojson|preset|radius
    area_km2: Mapped[float] = mapped_column(Float)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClassificationRuleset(Base):
    """Version des règles et seuils du traducteur (jamais figés dans l'interface)."""
    __tablename__ = "classification_ruleset"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    config: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)  # validation par expert
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
