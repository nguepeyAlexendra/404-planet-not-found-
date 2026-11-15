"""Détection de changements entre deux images alignées (différence en dB)."""
from dataclasses import dataclass

import numpy as np

from app.processing.units import to_db

DECREASE, STABLE, INCREASE, INVALID = 0, 1, 2, 255


class IncompatibleImages(ValueError):
    def __init__(self, reasons: list[str]):
        super().__init__("Images non comparables : " + "; ".join(reasons))
        self.reasons = reasons


@dataclass
class GridInfo:
    crs: str
    transform: tuple
    shape: tuple
    band: str
    resolution: float | None = None
    maturity: str | None = None
    track: int | None = None
    orbit_direction: str | None = None


def check_compatible(a: GridInfo, b: GridInfo) -> list[str]:
    """Liste des raisons d'incompatibilité (vide si les deux images sont comparables)."""
    reasons = []
    if a.crs != b.crs:
        reasons.append(f"CRS différents ({a.crs} / {b.crs})")
    if a.shape != b.shape:
        reasons.append(f"grilles de tailles différentes ({a.shape} / {b.shape})")
    elif not np.allclose(a.transform, b.transform, atol=1e-6):
        reasons.append("grilles non alignées")
    if a.band != b.band:
        reasons.append(f"polarisations différentes ({a.band} / {b.band})")
    if a.track is not None and b.track is not None and a.track != b.track:
        reasons.append("traces orbitales différentes (géométrie d'acquisition différente)")
    if a.orbit_direction and b.orbit_direction and a.orbit_direction != b.orbit_direction:
        reasons.append("sens d'orbite différents")
    if a.maturity and b.maturity and a.maturity != b.maturity:
        reasons.append(f"niveaux de maturité différents ({a.maturity} / {b.maturity}) : traitements non équivalents")
    return reasons


def detect_change(before_linear: np.ndarray, after_linear: np.ndarray, threshold_db: float = 3.0,
                  nodata: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Retourne (classes, delta_db). Pixels invalides dans l'une des images : 255 / NaN."""
    if before_linear.shape != after_linear.shape:
        raise IncompatibleImages(["grilles de tailles différentes"])
    if threshold_db <= 0:
        raise ValueError("Le seuil doit être strictement positif.")
    a, b = to_db(before_linear, nodata), to_db(after_linear, nodata)
    delta = b - a
    out = np.full(delta.shape, INVALID, dtype="uint8")
    ok = np.isfinite(delta)
    out[ok & (delta >= threshold_db)] = INCREASE
    out[ok & (delta <= -threshold_db)] = DECREASE
    out[ok & (np.abs(delta) < threshold_db)] = STABLE
    return out, delta


def summarize_change(classes: np.ndarray, pixel_area_km2: float) -> dict:
    valid = classes != INVALID
    n = int(valid.sum())
    if n == 0:
        return {"valid_pixels": 0, "stable_pct": None, "increase_pct": None, "decrease_pct": None,
                "changed_area_km2": None, "valid_area_km2": 0.0}
    inc, dec, sta = (int((classes == c).sum()) for c in (INCREASE, DECREASE, STABLE))
    return {"valid_pixels": n, "stable_pct": round(100 * sta / n, 2), "increase_pct": round(100 * inc / n, 2),
            "decrease_pct": round(100 * dec / n, 2), "changed_area_km2": round((inc + dec) * pixel_area_km2, 4),
            "valid_area_km2": round(n * pixel_area_km2, 4)}
