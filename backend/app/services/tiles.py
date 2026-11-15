"""Rendu de tuiles depuis les COG (rio-tiler, le moteur de TiTiler).

Trois modes : amplitude (dB + palette), classes (traducteur) et changements (delta dB entre deux dates).
Les trous (hors emprise, nodata) restent transparents : jamais de zéro affiché.
"""
import numpy as np
from rio_tiler.colormap import cmap
from rio_tiler.errors import EmptyMosaicError, TileOutsideBounds
from rio_tiler.io import Reader
from rio_tiler.models import ImageData
from rio_tiler.mosaic import mosaic_reader

from app.processing.change import DECREASE, INCREASE, INVALID, detect_change
from app.processing.classifier import classify
from app.processing.units import to_db

TILE = 256


def transparent_png() -> bytes:
    img = ImageData(np.ma.MaskedArray(np.zeros((1, TILE, TILE), dtype="uint8"), mask=np.ones((1, TILE, TILE), dtype=bool)))
    return img.render(img_format="PNG")


def _read(path: str, z: int, x: int, y: int) -> ImageData:
    with Reader(path) as src:
        return src.tile(x, y, z, tilesize=TILE, resampling_method="average")


def _tile_reader(path: str, x: int, y: int, z: int) -> ImageData:
    return _read(path, z, x, y)


def render_amplitude(paths: list[str], z: int, x: int, y: int, style: dict) -> bytes:
    try:
        img, _ = mosaic_reader(paths, _tile_reader, x, y, z, allowed_exceptions=(TileOutsideBounds,))
    except EmptyMosaicError:
        return transparent_png()
    lo, hi = style.get("rescale", [-25, 0])
    data = np.ma.masked_invalid(img.array[0].astype("float64"))
    db = to_db(np.ma.filled(data, np.nan))
    invalid = ~np.isfinite(db) | np.ma.getmaskarray(img.array[0])
    scaled = np.clip((np.nan_to_num(db, nan=lo) - lo) / (hi - lo) * 255, 0, 255).astype("uint8")
    out = ImageData(np.ma.MaskedArray(scaled[None], mask=invalid[None]))
    return out.render(img_format="PNG", colormap=cmap.get(style.get("colormap", "gray")))


def _first_tile(paths: list[str], z: int, x: int, y: int) -> ImageData | None:
    try:
        img, _ = mosaic_reader(paths, _tile_reader, x, y, z, allowed_exceptions=(TileOutsideBounds,))
        return img
    except EmptyMosaicError:
        return None


def _hex_rgba(color: str, alpha: int = 200) -> tuple[int, int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), alpha


def render_classes(hh_paths: list[str], hv_paths: list[str], z: int, x: int, y: int, ruleset: dict) -> bytes:
    hh, hv = _first_tile(hh_paths, z, x, y), _first_tile(hv_paths, z, x, y)
    if hh is None or hv is None:
        return transparent_png()
    a, b = np.ma.filled(hh.array[0].astype("float64"), np.nan), np.ma.filled(hv.array[0].astype("float64"), np.nan)
    classes = classify({"HHHH": a, "HVHV": b}, ruleset)
    invalid = ~(np.isfinite(a) & np.isfinite(b))
    out = ImageData(np.ma.MaskedArray(classes[None], mask=invalid[None]))
    colormap = {int(k): _hex_rgba(v["color"]) for k, v in ruleset["classes"].items()}
    return out.render(img_format="PNG", colormap=colormap)


def render_change(before_paths: list[str], after_paths: list[str], z: int, x: int, y: int, threshold_db: float) -> bytes:
    a, b = _first_tile(before_paths, z, x, y), _first_tile(after_paths, z, x, y)
    if a is None or b is None:
        return transparent_png()
    classes, _ = detect_change(np.ma.filled(a.array[0].astype("float64"), np.nan),
                               np.ma.filled(b.array[0].astype("float64"), np.nan), threshold_db)
    hidden = (classes == INVALID) | (classes == 1)  # invalides et stables restent transparents
    out = ImageData(np.ma.MaskedArray(classes[None], mask=hidden[None]))
    colormap = {INCREASE: (214, 59, 47, 210), DECREASE: (31, 111, 209, 210)}
    return out.render(img_format="PNG", colormap=colormap)
