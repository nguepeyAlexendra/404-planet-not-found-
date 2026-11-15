"""Configuration par variables d'environnement (aucun secret dans le dépôt)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NV_", extra="ignore")

    env: str = "dev"  # dev | test | staging | prod
    database_url: str = "sqlite:///./nisar_vision.db"
    use_postgis: bool = True  # PostgreSQL : colonnes PostGIS ; false = GeoJSON en texte (serveur sans PostGIS)
    data_dir: Path = Path("./data")
    redis_url: str = "redis://localhost:6379/0"
    celery_always_eager: bool = True  # True: les jobs tournent en ligne (dev/tests)
    cors_origins: str = "http://localhost:5173"
    tile_base_url: str = ""  # préfixe les URL de tuiles renvoyées par /layers ; le front construit pour l instant ses propres URL (src/lib/tiles.ts)
    earthdata_token: str | None = None
    max_aoi_km2: float = 250_000.0
    max_period_days: int = 800
    export_ttl_hours: int = 24
    ingest_max_download_gb: float = 20.0
    rate_limit_per_minute: int = 240
    log_level: str = "INFO"

    @property
    def cog_dir(self) -> Path:
        return self.data_dir / "cogs"

    @property
    def export_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def quarantine_dir(self) -> Path:
        return self.data_dir / "quarantine"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
