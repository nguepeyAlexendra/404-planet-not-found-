"""Validation d'un produit lu avant toute publication."""
import numpy as np
from pyproj import CRS, Transformer

from app.ingestion.hdf5_gcov import GcovProduct


def validate_product(p: GcovProduct) -> list[str]:
    errors: list[str] = []
    try:
        CRS.from_epsg(p.epsg)
    except Exception:  # noqa: BLE001
        errors.append(f"EPSG:{p.epsg} inconnu")
        return errors
    dx = np.diff(p.x)
    dy = np.diff(p.y)
    if not (np.allclose(dx, dx[0], rtol=1e-3) and np.allclose(dy, dy[0], rtol=1e-3)):
        errors.append("grille non régulière")
    if dx[0] <= 0:
        errors.append("xCoordinates doit croître")
    if dy[0] >= 0:
        errors.append("yCoordinates doit décroître (origine en haut)")
    for name, arr in p.bands.items():
        arr64 = arr.astype("float64")
        if p.nodata is not None and not np.isnan(p.nodata):
            arr64 = np.where(arr64 == p.nodata, np.nan, arr64)
        finite = np.isfinite(arr64)
        if not finite.any():
            errors.append(f"bande {name} entièrement invalide")
            continue
        if (arr64[finite] < 0).any():
            errors.append(f"bande {name} contient des valeurs négatives (attendu : puissance linéaire)")
    if p.meta.get("start") is None:
        errors.append("date d'acquisition absente")
    try:
        tr = Transformer.from_crs(f"EPSG:{p.epsg}", "EPSG:4326", always_xy=True)
        lon, lat = tr.transform([p.x.min(), p.x.max()], [p.y.min(), p.y.max()])
        if not (np.all(np.abs(lon) <= 180) and np.all(np.abs(lat) <= 90)) or not np.all(np.isfinite(lon + lat)):
            errors.append("emprise hors limites géographiques")
    except Exception:  # noqa: BLE001
        errors.append("emprise non transformable en EPSG:4326")
    return errors


def bounds_wgs84(p: GcovProduct) -> tuple[float, float, float, float]:
    px, py = p.pixel_size
    tr = Transformer.from_crs(f"EPSG:{p.epsg}", "EPSG:4326", always_xy=True)
    xs = [p.x.min() - px / 2, p.x.max() + px / 2, p.x.min() - px / 2, p.x.max() + px / 2]
    ys = [p.y.min() - py / 2, p.y.min() - py / 2, p.y.max() + py / 2, p.y.max() + py / 2]
    lon, lat = tr.transform(xs, ys)
    return float(min(lon)), float(min(lat)), float(max(lon)), float(max(lat))
