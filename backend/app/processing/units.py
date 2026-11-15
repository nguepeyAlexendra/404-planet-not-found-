"""Conversions d'unités. Les valeurs linéaires restent la référence pour les calculs ;
le dB sert à l'affichage et aux seuils."""
import numpy as np


def to_db(linear: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """10*log10(x). Les valeurs nodata, NaN, nulles ou négatives deviennent NaN (jamais -inf)."""
    arr = np.asarray(linear, dtype="float64")
    invalid = ~np.isfinite(arr) | (arr <= 0)
    if nodata is not None:
        invalid |= arr == nodata
    out = np.full(arr.shape, np.nan, dtype="float64")
    np.log10(arr, out=out, where=~invalid)
    out = 10.0 * out
    out[invalid] = np.nan
    return out


def from_db(db: float | np.ndarray) -> float | np.ndarray:
    return np.power(10.0, np.asarray(db, dtype="float64") / 10.0)


def mean_db(linear: np.ndarray, nodata: float | None = None) -> float | None:
    """dB de la moyenne linéaire (et non moyenne des dB), sur les pixels valides seulement."""
    arr = np.asarray(linear, dtype="float64")
    valid = np.isfinite(arr) & (arr > 0)
    if nodata is not None:
        valid &= arr != nodata
    if not valid.any():
        return None
    return float(10.0 * np.log10(arr[valid].mean()))
