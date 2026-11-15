"""Analyses quantitatives sur une AOI : séries temporelles, matrice de transition, projection exploratoire.

Chaque résultat embarque ses paramètres, la méthode, la version, les datasets utilisés et les limites,
pour que l'analyse soit traçable et reproductible.
"""
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, DataUnavailable
from app.models import Dataset
from app.processing.change import GridInfo, check_compatible
from app.processing.classifier import classify, load_ruleset
from app.processing.geo import read_aoi
from app.processing.stats import InsufficientData, linear_trend, projection, transition_matrix
from app.processing.units import to_db
from app.services import catalog
from app.services.dates import day_bounds

METHOD_VERSION = "analytics-1"
BAND_LABEL = {"HHHH": "HH", "HVHV": "HV"}
SCENARIOS = {"business_as_usual": 1.0, "protection_renforcee": 0.5, "acceleration": 1.5}
ProgressFn = Callable[[float, str], None]


def _noop(p: float, m: str) -> None:
    return None


def _datasets_in(db: Session, geometry: dict, start: date, end: date, include_demo: bool) -> list[Dataset]:
    from shapely.geometry import shape
    minx, miny, maxx, maxy = shape(geometry).bounds
    q = (select(Dataset).where(Dataset.status == "available", Dataset.product_type == "GCOV")
         .where(Dataset.acquisition_start >= day_bounds(start)[0], Dataset.acquisition_start < day_bounds(end)[1])
         .where(Dataset.east >= minx, Dataset.west <= maxx, Dataset.north >= miny, Dataset.south <= maxy)
         .options(selectinload(Dataset.assets)).order_by(Dataset.acquisition_start))
    if not include_demo:
        q = q.where(Dataset.is_demo.is_(False))
    return list(db.scalars(q))


def _bucket(d: date, frequency: str) -> str:
    if frequency == "day":
        return d.isoformat()
    if frequency == "week":
        return (d - timedelta(days=d.weekday())).isoformat()
    return f"{d.year}-{d.month:02d}"


def _all_buckets(first: date, last: date, frequency: str) -> list[str]:
    out, cur = [], first
    while cur <= last:
        b = _bucket(cur, frequency)
        if not out or out[-1] != b:
            out.append(b)
        cur += timedelta(days=1)
    return out


def _bucket_day(key: str) -> date:
    return date.fromisoformat(key + "-01") if len(key) == 7 else date.fromisoformat(key)


def time_series(db: Session, p: dict, progress: ProgressFn = _noop) -> dict:
    start, end = date.fromisoformat(p["date_start"]), date.fromisoformat(p["date_end"])
    freq = p.get("frequency", "week")
    geometry = p["geometry"]
    datasets = _datasets_in(db, geometry, start, end, p.get("include_demo", False))
    if not datasets:
        raise DataUnavailable("Aucune acquisition NISAR ne couvre cette zone sur cette période.",
                              details={"date_start": p["date_start"], "date_end": p["date_end"]})
    ruleset = load_ruleset()
    want_classes = "classes" in p.get("variables", [])
    obs, skipped = [], []
    for i, ds in enumerate(datasets):
        progress(0.05 + 0.85 * i / len(datasets), f"lecture {ds.source_id}")
        row = {"date": ds.acquisition_start.date(), "dataset_id": ds.id, "bands": {}, "valid_px": 0, "pixel_km2": None}
        arrays = {}
        for band in ("HHHH", "HVHV"):
            path = catalog.asset_path(ds, band)
            if path is None:
                continue
            res = read_aoi(path, geometry)
            if res is None:
                continue
            arrays[band] = res[0]
            row["pixel_km2"] = res[3]
        if not arrays:
            skipped.append(ds.source_id)
            continue
        valid_any = False
        for band, arr in arrays.items():
            ok = np.isfinite(arr) & (arr > 0)
            if ok.any():
                valid_any = True
                row["bands"][band] = {"n": int(ok.sum()), "mean_lin": float(arr[ok].mean()),
                                      "min_db": float(np.nanmin(to_db(arr[ok]))), "max_db": float(np.nanmax(to_db(arr[ok])))}
        if not valid_any:
            skipped.append(ds.source_id)
            continue
        row["valid_px"] = max(b["n"] for b in row["bands"].values())
        if want_classes and {"HHHH", "HVHV"} <= set(arrays):
            valid = np.isfinite(arrays["HHHH"]) & np.isfinite(arrays["HVHV"])
            cls = classify(arrays, ruleset)
            tot = int(valid.sum())
            if tot:
                row["classes"] = {v["key"]: 100 * int(((cls == int(k)) & valid).sum()) / tot for k, v in ruleset["classes"].items()}
        obs.append(row)
    if not obs:
        raise DataUnavailable("Les acquisitions trouvées ne contiennent aucun pixel valide sous cette zone.",
                              details={"skipped": skipped})
    grouped = defaultdict(list)
    for r in obs:
        grouped[_bucket(r["date"], freq)].append(r)
    series = []
    for key in sorted(grouped):
        rows = grouped[key]
        entry = {"period": key, "n_observations": len(rows), "dataset_ids": [r["dataset_id"] for r in rows],
                 "valid_area_km2": round(float(np.mean([r["valid_px"] * (r["pixel_km2"] or 0) for r in rows])), 4), "bands": {}}
        for band in ("HHHH", "HVHV"):
            vals = [(r["bands"][band]["n"], r["bands"][band]["mean_lin"], r["bands"][band]["min_db"], r["bands"][band]["max_db"])
                    for r in rows if band in r["bands"]]
            if vals and band in p.get("variables", ["HHHH", "HVHV"]):
                w = np.array([v[0] for v in vals], dtype=float)
                mean_lin = float(np.average([v[1] for v in vals], weights=w))
                entry["bands"][BAND_LABEL[band]] = {"mean_db": round(float(10 * np.log10(mean_lin)), 3),
                                                    "min_db": round(min(v[2] for v in vals), 3),
                                                    "max_db": round(max(v[3] for v in vals), 3)}
        if want_classes:
            cl = [r["classes"] for r in rows if "classes" in r]
            if cl:
                entry["classes_pct"] = {k: round(float(np.mean([c[k] for c in cl])), 2) for k in cl[0]}
        series.append(entry)
    first, last = _bucket_day(series[0]["period"]), _bucket_day(series[-1]["period"])
    present = {s["period"] for s in series}
    missing = [b for b in _all_buckets(first, last, freq) if b not in present]
    trends = {}
    for label in {b for s in series for b in s["bands"]}:
        pts = [(( _bucket_day(s["period"]) - first).days, s["bands"][label]["mean_db"]) for s in series if label in s["bands"]]
        try:
            t = linear_trend([a for a, _ in pts], [b for _, b in pts])
            trends[label] = {"slope_db_per_day": round(t.slope_per_day, 6), "r2": round(t.r2, 4), "n": t.n}
        except InsufficientData as exc:
            trends[label] = {"error": str(exc)}
    maturities = sorted({d.maturity for d in datasets})
    warnings = ["Moyenne calculée sur les valeurs linéaires puis convertie en dB, en ignorant les pixels nodata."]
    if len(maturities) > 1:
        warnings.append("Niveaux de maturité mélangés (" + ", ".join(maturities) + ") : traitements non strictement équivalents.")
    if any(d.is_demo for d in datasets):
        warnings.append("Contient des données de DÉMONSTRATION simulées : ce ne sont pas des observations NISAR.")
    if want_classes:
        warnings.append("Proportions thématiques issues des règles prototype " + ruleset["version"] + " (non validées).")
    progress(1.0, "terminé")
    return {"series": series, "trend": trends, "missing_periods": missing, "n_datasets": len(datasets),
            "dataset_ids": [d.id for d in datasets], "skipped": skipped, "maturities": maturities, "frequency": freq,
            "units": "dB", "unavailable_variables": ["soil_moisture (aucun produit validé disponible)"],
            "method": "moyenne sur AOI des valeurs linéaires, convertie en dB ; tendance par régression linéaire",
            "method_version": METHOD_VERSION, "has_demo": any(d.is_demo for d in datasets), "warnings": warnings,
            "limits": ["La tendance est descriptive et ne prouve pas une causalité."]}


def _grid(ds: Dataset, band: str) -> GridInfo:
    import rasterio
    with rasterio.open(catalog.asset_path(ds, band)) as src:
        return GridInfo(crs=str(src.crs), transform=tuple(src.transform)[:6], shape=(src.height, src.width), band=band,
                        resolution=ds.resolution_m, maturity=ds.maturity, track=ds.track, orbit_direction=ds.orbit_direction)


def change_matrix(db: Session, p: dict, progress: ProgressFn = _noop) -> dict:
    geometry = p["geometry"]
    sets = {}
    for tag, key in (("a", "date_a"), ("b", "date_b")):
        d = date.fromisoformat(p[key])
        found = _datasets_in(db, geometry, d, d, p.get("include_demo", False))
        if not found:
            raise DataUnavailable(f"Aucune acquisition ne couvre la zone le {p[key]}.", details={"date": p[key]})
        sets[tag] = found[0]
    ruleset = load_ruleset()
    for ds in sets.values():
        for band in ruleset["required_bands"]:
            if catalog.asset_path(ds, band) is None:
                raise AppError(f"Bande {band} absente de {ds.source_id}.", code="missing_bands")
    reasons = check_compatible(_grid(sets["a"], "HHHH"), _grid(sets["b"], "HHHH"))
    if reasons:
        raise AppError("Classes non comparables : " + "; ".join(reasons) + ".", code="incompatible_images",
                       details={"reasons": reasons})
    progress(0.3, "classification date A")
    maps = {}
    for tag, ds in sets.items():
        arrs, px = {}, None
        for band in ruleset["required_bands"]:
            res = read_aoi(catalog.asset_path(ds, band), geometry)
            if res is None:
                raise DataUnavailable("La zone ne recoupe pas le produit.")
            arrs[band], px = res[0], res[3]
        valid = np.isfinite(arrs["HHHH"]) & np.isfinite(arrs["HVHV"])
        cls = classify(arrs, ruleset).astype("int16")
        cls[~valid] = -1
        maps[tag] = (cls, px)
        progress(0.3 + 0.3 * (tag == "b") + 0.3, f"classification date {tag.upper()}")
    class_ids = [int(k) for k in ruleset["classes"]]
    matrix = transition_matrix(maps["a"][0], maps["b"][0], class_ids, maps["a"][1])
    if matrix["valid_pixels"] == 0:
        raise DataUnavailable("Aucun pixel valide commun aux deux dates.")
    labels = [ruleset["classes"][str(c)]["label"] for c in class_ids]
    net = matrix["net_km2"]
    i_gain, i_loss = int(np.argmax(net)), int(np.argmin(net))
    summary = (f"Entre le {p['date_a']} et le {p['date_b']}, la classe qui gagne le plus de surface est « {labels[i_gain]} » "
               f"({net[i_gain]:+.2f} km²) et celle qui en perd le plus est « {labels[i_loss]} » ({net[i_loss]:+.2f} km²).")
    progress(1.0, "terminé")
    return {"date_a": p["date_a"], "date_b": p["date_b"], "dataset_ids": [sets["a"].id, sets["b"].id], "labels": labels,
            "class_keys": [ruleset["classes"][str(c)]["key"] for c in class_ids],
            "colors": [ruleset["classes"][str(c)]["color"] for c in class_ids], "matrix": matrix, "summary_text": summary,
            "ruleset_version": ruleset["version"], "resolution_m": sets["a"].resolution_m, "method_version": METHOD_VERSION,
            "has_demo": sets["a"].is_demo or sets["b"].is_demo,
            "warnings": ["Règles prototype non validées : les surfaces gagnées ou perdues sont indicatives.",
                         f"Résolution des produits : {sets['a'].resolution_m:.0f} m, des petits objets peuvent échapper à l'analyse."]}


def run_projection(db: Session, p: dict, progress: ProgressFn = _noop) -> dict:
    ts = time_series(db, {**p, "variables": list({*p.get("variables", []), "HHHH", "HVHV", "classes"})}, progress)
    variable = p.get("variable", "HH")
    pts = []
    for s in ts["series"]:
        if variable in s["bands"]:
            pts.append((s["period"], s["bands"][variable]["mean_db"]))
        elif variable.startswith("class:") and "classes_pct" in s:
            pts.append((s["period"], s["classes_pct"].get(variable[6:], None)))
    pts = [(k, v) for k, v in pts if v is not None]
    first = _bucket_day(pts[0][0]) if pts else None
    days = [(_bucket_day(k) - first).days for k, _ in pts] if pts else []
    vals = [v for _, v in pts]
    horizon = [days[-1] + 30 * m for m in range(1, int(p.get("horizon_months", 6)) + 1)] if days else []
    try:
        scenarios = {name: projection(days, vals, horizon, slope_factor=f) for name, f in SCENARIOS.items()}
    except InsufficientData as exc:
        raise AppError(str(exc), code="insufficient_data", details={"n_points": len(days)}) from exc
    return {"variable": variable, "history": [{"period": k, "day": d, "value": v} for (k, v), d in zip(pts, days)],
            "scenarios": scenarios, "first_period": pts[0][0], "dataset_ids": ts["dataset_ids"], "method_version": METHOD_VERSION,
            "method": "régression linéaire avec intervalle de prédiction à 95 % ; facteur de scénario appliqué à la pente",
            "has_demo": ts["has_demo"], "maturities": ts["maturities"],
            "warnings": ["Projection EXPLORATOIRE : extrapolation d'une tendance passée, pas une prévision certifiée.",
                         "Hypothèse : la tendance observée se prolonge ; les scénarios modifient seulement la pente."] + ts["warnings"]}
