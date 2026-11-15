"""Traducteur radar : résumés de classification et de changements sur une emprise ou une AOI."""
import numpy as np
from sqlalchemy.orm import Session

from app.core.errors import AppError, DataUnavailable
from app.processing.change import GridInfo, check_compatible, detect_change, summarize_change
from app.processing.classifier import MissingBandsError, classify, load_ruleset
from app.processing.geo import bbox_geojson, read_aoi
from app.services import catalog

PROTOTYPE_NOTE = ("Règles prototype non validées par un expert : aucun chiffre de précision n'est affiché. "
                  "Les seuils sont ceux de la version de règles indiquée.")


def _aoi_geometry(ds, geometry: dict | None) -> dict:
    return geometry or bbox_geojson(ds.west, ds.south, ds.east, ds.north)


def classification_summary(db: Session, dataset_id: int, geometry: dict | None = None) -> dict:
    ds = catalog.get_dataset(db, dataset_id)
    ruleset = load_ruleset()
    arrays, pixel_km2 = {}, None
    geom = _aoi_geometry(ds, geometry)
    for band in ruleset["required_bands"]:
        path = catalog.asset_path(ds, band)
        if path is None:
            raise AppError(f"Bandes requises absentes : {band}.", code="missing_bands",
                           details={"missing": [b for b in ruleset["required_bands"] if catalog.asset_path(ds, b) is None]})
        res = read_aoi(path, geom)
        if res is None:
            raise DataUnavailable("La zone ne recoupe pas ce produit.")
        arrays[band], _, _, pixel_km2 = res
    try:
        classes = classify(arrays, ruleset)
    except MissingBandsError as exc:
        raise AppError(str(exc), code="missing_bands", details={"missing": exc.missing}) from exc
    valid = np.isfinite(arrays["HHHH"]) & np.isfinite(arrays["HVHV"])
    total = int(valid.sum())
    if total == 0:
        raise DataUnavailable("Aucun pixel valide dans cette zone (nodata).")
    rows = []
    for cid, info in ruleset["classes"].items():
        n = int(((classes == int(cid)) & valid).sum())
        rows.append({"class_id": int(cid), "key": info["key"], "label": info["label"], "color": info["color"],
                     "pixels": n, "pct": round(100 * n / total, 2), "area_km2": round(n * pixel_km2, 4)})
    return {"dataset_id": ds.id, "source_id": ds.source_id, "maturity": ds.maturity, "is_demo": ds.is_demo,
            "ruleset_version": ruleset["version"], "ruleset_name": ruleset["name"], "classes": rows,
            "valid_pixels": total, "valid_area_km2": round(total * pixel_km2, 4),
            "method": "classification par seuils HH/HV en dB", "limits": [PROTOTYPE_NOTE]}


def _grid(ds, band: str) -> GridInfo:
    import rasterio
    path = catalog.asset_path(ds, band)
    with rasterio.open(path) as src:
        return GridInfo(crs=str(src.crs), transform=tuple(src.transform)[:6], shape=(src.height, src.width), band=band,
                        resolution=ds.resolution_m, maturity=ds.maturity, track=ds.track, orbit_direction=ds.orbit_direction)


def change_summary(db: Session, before_id: int, after_id: int, band: str = "HHHH", threshold_db: float = 3.0,
                   geometry: dict | None = None) -> dict:
    a, b = catalog.get_dataset(db, before_id), catalog.get_dataset(db, after_id)
    for ds in (a, b):
        if catalog.asset_path(ds, band) is None:
            raise AppError(f"Bande {band} absente du produit {ds.source_id}.", code="missing_bands")
    reasons = check_compatible(_grid(a, band), _grid(b, band))
    if reasons:
        raise AppError("Ces deux images ne sont pas comparables : " + "; ".join(reasons) + ".", code="incompatible_images",
                       details={"reasons": reasons})
    geom = _aoi_geometry(a, geometry)
    ra, rb = read_aoi(catalog.asset_path(a, band), geom), read_aoi(catalog.asset_path(b, band), geom)
    if ra is None or rb is None:
        raise DataUnavailable("La zone ne recoupe pas l'un des produits.")
    classes, delta = detect_change(ra[0], rb[0], threshold_db)
    summary = summarize_change(classes, ra[3])
    if summary["valid_pixels"] == 0:
        raise DataUnavailable("Aucun pixel valide dans les deux images pour cette zone.")
    return {"before": {"dataset_id": a.id, "date": a.acquisition_start.date().isoformat(), "source_id": a.source_id},
            "after": {"dataset_id": b.id, "date": b.acquisition_start.date().isoformat(), "source_id": b.source_id},
            "band": band, "threshold_db": threshold_db, "method": "différence des valeurs en dB (après - avant)",
            "summary": summary, "maturity": a.maturity, "is_demo": a.is_demo or b.is_demo,
            "limits": ["Un changement de rétrodiffusion n'est pas un diagnostic : humidité, rugosité, "
                       "végétation ou bâti peuvent chacun en être la cause."]}
