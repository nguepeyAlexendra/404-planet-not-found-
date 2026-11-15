from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Frequency = Literal["day", "week", "month"]


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: str
    source: str
    sensor: str
    frequency_band: str
    product_type: str
    maturity: str
    acquisition_start: datetime
    acquisition_end: datetime | None
    track: int | None
    orbit_direction: str | None
    polarizations: list[str]
    resolution_m: float | None
    crs: str
    west: float
    south: float
    east: float
    north: float
    units: str
    nodata: float | None
    processing_version: str | None
    license: str | None
    status: str
    is_demo: bool
    bands: list[str] = []
    extent: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def _bands(cls, v):
        if hasattr(v, "assets"):
            data = {k: getattr(v, k) for k in cls.model_fields if hasattr(v, k) and k != "bands"}
            data["bands"] = [a.band for a in v.assets]
            return data
        return v


class Page(BaseModel):
    items: list[DatasetOut]
    total: int
    page: int
    page_size: int


class LayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    label: str
    group: str
    product_type: str
    band: str
    source: str
    unit: str
    style: dict
    default_opacity: float
    description: str
    coverage: dict | None = None
    tiles: str | None = None


class AOICreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    geometry: dict | None = None
    center: tuple[float, float] | None = Field(default=None, description="[longitude, latitude]")
    radius_km: float | None = Field(default=None, gt=0, le=1000)
    bbox: tuple[float, float, float, float] | None = Field(default=None, description="[ouest, sud, est, nord]")

    @model_validator(mode="after")
    def _one_source(self):
        given = sum(x is not None for x in (self.geometry, self.center, self.bbox))
        if given != 1:
            raise ValueError("Fournir exactement une source : geometry, center+radius_km ou bbox.")
        if self.center is not None and self.radius_km is None:
            raise ValueError("radius_km est requis avec center.")
        return self


class AOIOut(BaseModel):
    id: int
    title: str
    geometry: dict
    source: str
    area_km2: float
    created_at: datetime


class _Period(BaseModel):
    date_start: date
    date_end: date
    include_demo: bool = False

    @model_validator(mode="after")
    def _order(self):
        if self.date_end < self.date_start:
            raise ValueError("date_end doit être postérieure ou égale à date_start.")
        return self


class TimeSeriesRequest(_Period):
    aoi_id: int
    frequency: Frequency = "week"
    variables: list[Literal["HHHH", "HVHV", "classes"]] = ["HHHH", "HVHV"]


class ChangeMatrixRequest(BaseModel):
    aoi_id: int
    date_a: date
    date_b: date
    include_demo: bool = False


class ProjectionRequest(TimeSeriesRequest):
    variable: str = "HH"
    horizon_months: int = Field(default=6, ge=1, le=24)


class ExportRequest(BaseModel):
    job_id: str
    format: Literal["csv", "geojson", "svg", "pdf"]


class ChangesRequest(BaseModel):
    before_dataset_id: int
    after_dataset_id: int
    band: Literal["HHHH", "HVHV"] = "HHHH"
    threshold_db: float = Field(default=3.0, gt=0, le=20)
    aoi_id: int | None = None

    @field_validator("after_dataset_id")
    @classmethod
    def _distinct(cls, v, info):
        if info.data.get("before_dataset_id") == v:
            raise ValueError("Les deux datasets doivent être différents.")
        return v


class JobOut(BaseModel):
    job_id: str
    kind: str
    status: str
    progress: float
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    result: dict | None = None
    params: dict | None = None
    method_version: str | None = None
    result_url: str | None = None


class AttemptRequest(BaseModel):
    answers: dict[int, int]


class CertificateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
