"""Traitements géospatiaux : validation d'AOI, surfaces géodésiques, échantillonnage et agrégats raster."""
import math
from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import Geod, Transformer
from rasterio.mask import mask as rio_mask
from rasterio.windows import Window, from_bounds
from shapely.geometry import Point, box, mapping, shape
import shapely
from shapely.validation import explain_validity

from app.core.errors import AppError, TooLarge

GEOD = Geod(ellps="WGS84")


def geodesic_area_km2(geom) -> float:
    area, _ = GEOD.geometry_area_perimeter(geom)
    return abs(area) / 1e6


def validate_aoi_geometry(geojson: dict, max_area_km2: float) -> tuple[dict, float]:
    """Valide une géométrie GeoJSON (Polygon ou MultiPolygon, EPSG:4326). Retourne (géométrie, surface km²)."""
    if not isinstance(geojson, dict):
        raise AppError("La géométrie doit être un objet GeoJSON.", code="invalid_geometry")
    if geojson.get("type") == "Feature":
        geojson = geojson.get("geometry") or {}
    if geojson.get("type") not in ("Polygon", "MultiPolygon"):
        raise AppError("Seuls Polygon et MultiPolygon sont acceptés pour une zone d'intérêt.", code="invalid_geometry")
    try:
        geom = shape(geojson)
    except Exception as exc:  # noqa: BLE001
        raise AppError("Géométrie GeoJSON illisible.", code="invalid_geometry") from exc
    if geom.is_empty:
        raise AppError("La géométrie est vide.", code="invalid_geometry")
    minx, miny, maxx, maxy = geom.bounds
    if not all(math.isfinite(v) for v in (minx, miny, maxx, maxy)) or minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
        raise AppError("Coordonnées hors limites WGS84 (longitude -180..180, latitude -90..90).", code="invalid_geometry")
    if not geom.is_valid:
        raise AppError(f"Géométrie invalide : {explain_validity(geom)}.", code="invalid_geometry")
    area = geodesic_area_km2(geom)
    if area <= 0:
        raise AppError("La zone a une surface nulle.", code="invalid_geometry")
    if area > max_area_km2:
        raise TooLarge(f"Zone trop grande : {area:,.0f} km² (maximum {max_area_km2:,.0f} km²). Réduisez la zone ou découpez-la.",
                       details={"area_km2": round(area, 1), "max_area_km2": max_area_km2})
    return mapping(geom), round(area, 4)


def circle_geojson(lon: float, lat: float, radius_km: float, n: int = 64) -> dict:
    if not (-180 <= lon <= 180 and -90 <= lat <= 90) or radius_km <= 0:
        raise AppError("Centre ou rayon invalide.", code="invalid_geometry")
    pts = [GEOD.fwd(lon, lat, 360.0 * i / n, radius_km * 1000.0)[:2] for i in range(n)]
    pts.append(pts[0])
    return {"type": "Polygon", "coordinates": [[list(p) for p in pts]]}


def bbox_geojson(west: float, south: float, east: float, north: float) -> dict:
    return mapping(box(west, south, east, north))


@dataclass
class PixelSample:
    value: float | None
    reason: str | None  # None si valeur présente ; sinon "out_of_bounds" | "nodata"


def sample_pixel(path: str, lon: float, lat: float) -> PixelSample:
    """Valeur linéaire d'un pixel. Hors emprise ou nodata -> valeur None (jamais 0)."""
    with rasterio.open(path) as src:
        x, y = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(lon, lat)
        if not (src.bounds.left <= x < src.bounds.right and src.bounds.bottom < y <= src.bounds.top):
            return PixelSample(None, "out_of_bounds")
        row, col = src.index(x, y)
        data = src.read(1, window=Window(col, row, 1, 1), masked=True)
        val = data[0, 0]
        if np.ma.is_masked(val) or not np.isfinite(float(val)):
            return PixelSample(None, "nodata")
        return PixelSample(float(val), None)


def pixel_area_km2(src, lat: float) -> float:
    """Surface d'un pixel : produit des pas en CRS projeté, sinon calcul géodésique à la latitude."""
    if src.crs and src.crs.is_projected:
        unit = src.crs.linear_units_factor[1] if src.crs.linear_units_factor else 1.0
        return abs(src.res[0] * src.res[1]) * unit**2 / 1e6
    dx, dy = src.res
    cell = box(0, lat - dy / 2, dx, lat + dy / 2)
    return geodesic_area_km2(cell)


MAX_READ_PIXELS = 40_000_000


def read_aoi(path: str, geometry: dict) -> tuple[np.ndarray, tuple, str, float] | None:
    """Lit les pixels sous l'AOI. Retourne (tableau float NaN=invalide, transform, crs, surface pixel km²)
    ou None si l'AOI ne recoupe pas le raster."""
    with rasterio.open(path) as src:
        to_src = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform
        geom_src = shapely.transform(shape(geometry), lambda c: np.column_stack(to_src(c[:, 0], c[:, 1])))
        if not geom_src.intersects(box(*src.bounds)):
            return None
        win = from_bounds(*geom_src.bounds, transform=src.transform)
        if win.width * win.height > MAX_READ_PIXELS:
            raise TooLarge("Zone trop étendue pour la résolution de ce produit : réduisez la zone ou découpez-la.",
                           details={"pixels": int(win.width * win.height), "max_pixels": MAX_READ_PIXELS})
        arr, transform = rio_mask(src, [mapping(geom_src)], crop=True, filled=False, all_touched=False)
        data = np.ma.filled(arr[0].astype("float64"), np.nan)
        centroid_lat = shape(geometry).centroid.y
        return data, tuple(transform)[:6], str(src.crs), pixel_area_km2(src, centroid_lat)


def dataset_overlaps(ds_bounds: tuple[float, float, float, float], geometry: dict) -> bool:
    return box(*ds_bounds).intersects(shape(geometry))


def point_in_bounds(lon: float, lat: float, bounds: tuple[float, float, float, float]) -> bool:
    return box(*bounds).intersects(Point(lon, lat))
