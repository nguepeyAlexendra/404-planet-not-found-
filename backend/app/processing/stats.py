"""Statistiques d'analyse : tendance, projection exploratoire, matrice de transition."""
from dataclasses import dataclass

import numpy as np
from scipy import stats as sps


class InsufficientData(ValueError):
    pass


@dataclass
class Trend:
    slope_per_day: float
    intercept: float
    r2: float
    se_slope: float
    n: int


def linear_trend(days: list[float], values: list[float]) -> Trend:
    x, y = np.asarray(days, dtype=float), np.asarray(values, dtype=float)
    if len(x) < 3:
        raise InsufficientData("Au moins 3 observations sont nécessaires pour une tendance.")
    if np.ptp(x) == 0:
        raise InsufficientData("Toutes les observations ont la même date.")
    res = sps.linregress(x, y)
    return Trend(float(res.slope), float(res.intercept), float(res.rvalue**2), float(res.stderr), len(x))


def projection(days: list[float], values: list[float], horizon_days: list[float], slope_factor: float = 1.0,
               min_points: int = 6, confidence: float = 0.95) -> dict:
    """Projection linéaire exploratoire avec intervalle de prédiction.

    slope_factor ajuste la pente observée pour un scénario (1 = tendance observée).
    Refuse de produire une courbe si la série est trop courte.
    """
    if len(days) < min_points:
        raise InsufficientData(f"Série trop courte pour une projection ({len(days)} observations, minimum {min_points}).")
    x, y = np.asarray(days, dtype=float), np.asarray(values, dtype=float)
    tr = linear_trend(days, values)
    n = len(x)
    resid = y - (tr.intercept + tr.slope_per_day * x)
    s = float(np.sqrt((resid**2).sum() / (n - 2)))
    xbar = x.mean()
    sxx = ((x - xbar) ** 2).sum()
    tcrit = float(sps.t.ppf(0.5 + confidence / 2, n - 2))
    last_x, last_fit = x.max(), tr.intercept + tr.slope_per_day * x.max()
    out = []
    for h in horizon_days:
        xp = float(h)
        center_fit = tr.intercept + tr.slope_per_day * xp
        # le facteur de scénario modifie la pente à partir de la dernière observation
        center = last_fit + (center_fit - last_fit) * slope_factor if xp > last_x else center_fit
        se = s * np.sqrt(1 + 1 / n + (xp - xbar) ** 2 / sxx)
        out.append({"day": xp, "value": float(center), "low": float(center - tcrit * se), "high": float(center + tcrit * se)})
    return {"points": out, "residual_std": s, "confidence": confidence, "slope_per_day": tr.slope_per_day,
            "r2": tr.r2, "n": n, "slope_factor": slope_factor}


def transition_matrix(a: np.ndarray, b: np.ndarray, class_ids: list[int], pixel_area_km2: float) -> dict:
    """Matrice de transition entre deux rasters de classes (même grille). Pixels invalides (-1) ignorés."""
    if a.shape != b.shape:
        raise ValueError("Les deux rasters de classes n'ont pas la même grille.")
    valid = (a >= 0) & (b >= 0)
    n = len(class_ids)
    idx = {c: i for i, c in enumerate(class_ids)}
    counts = np.zeros((n, n), dtype=np.int64)
    for ca in class_ids:
        ma = valid & (a == ca)
        for cb in class_ids:
            counts[idx[ca], idx[cb]] = int((ma & (b == cb)).sum())
    area = counts * pixel_area_km2
    lost = [float(area[i].sum() - area[i, i]) for i in range(n)]
    gained = [float(area[:, i].sum() - area[i, i]) for i in range(n)]
    return {"class_ids": class_ids, "counts": counts.tolist(), "area_km2": np.round(area, 4).tolist(),
            "lost_km2": [round(v, 4) for v in lost], "gained_km2": [round(v, 4) for v in gained],
            "net_km2": [round(g - l, 4) for g, l in zip(gained, lost)], "valid_pixels": int(valid.sum())}
