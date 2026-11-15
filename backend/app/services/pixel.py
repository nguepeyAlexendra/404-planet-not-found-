"""Clic pixel : valeurs, unités, interprétation prudente, mini série temporelle."""
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import DataUnavailable
from app.processing.classifier import classify_pixel, load_ruleset
from app.processing.geo import point_in_bounds, sample_pixel
from app.processing.units import to_db
from app.services import catalog
from app.services.dates import day_bounds  # noqa: F401

BANDS = ("HHHH", "HVHV")
LABEL = {"HHHH": "HH", "HVHV": "HV"}


def _db(v: float | None) -> float | None:
    if v is None:
        return None
    import numpy as np
    r = float(to_db(np.array([v]))[0])
    return None if r != r else round(r, 2)


def pixel_info(db: Session, lon: float, lat: float, day: date, layer_key: str | None, include_demo: bool) -> dict:
    layer = catalog.get_layer(db, layer_key) if layer_key else catalog.get_layer(db, "nisar-gcov-hh")
    candidates = [d for d in catalog.datasets_for_layer(db, layer, day=day, include_demo=include_demo,
                                                        bbox=(lon, lat, lon, lat))
                  if point_in_bounds(lon, lat, (d.west, d.south, d.east, d.north))]
    if not candidates:
        raise DataUnavailable("Aucune acquisition ne couvre ce point à cette date.",
                              details={"lon": lon, "lat": lat, "date": day.isoformat()})
    ds = candidates[0]
    values, reasons = {}, {}
    for band in BANDS:
        path = catalog.asset_path(ds, band)
        if path is None:
            values[band], reasons[band] = None, "bande absente du produit"
            continue
        s = sample_pixel(path, lon, lat)
        values[band], reasons[band] = s.value, {"out_of_bounds": "hors emprise", "nodata": "pas de donnée (nodata)"}.get(s.reason)
    bands = {LABEL[b]: {"linear": values[b], "db": _db(values[b]),
                        "status": "ok" if values[b] is not None else "non disponible",
                        "reason": reasons[b]} for b in BANDS}
    ruleset = load_ruleset()
    interp = classify_pixel(values["HHHH"], values["HVHV"], ruleset)
    interp["caution"] = ("Interprétation issue d'un prototype de règles non validé. Elle indique une hypothèse "
                         "probable, pas une certitude.")
    series = []
    for other in catalog.datasets_for_layer(db, layer, include_demo=include_demo, bbox=(lon, lat, lon, lat))[:60]:
        path = catalog.asset_path(other, layer.band)
        if path and point_in_bounds(lon, lat, (other.west, other.south, other.east, other.north)):
            s = sample_pixel(path, lon, lat)
            series.append({"date": other.acquisition_start.date().isoformat(), "db": _db(s.value)})
    return {"lon": lon, "lat": lat, "date": day.isoformat(), "dataset_id": ds.id, "source_id": ds.source_id,
            "sensor": f"{ds.source} {ds.sensor} {ds.frequency_band}-band", "product_type": ds.product_type,
            "maturity": ds.maturity, "is_demo": ds.is_demo, "units": "dB (10·log10 de la puissance linéaire)",
            "bands": bands, "interpretation": interp, "series": series}
