from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.processing.classifier import load_ruleset
from app.services import catalog, tiles
from app.services.dates import parse_date

router = APIRouter(tags=["tuiles"])
CACHE = {"Cache-Control": "public, max-age=300"}


def _check_zxy(z: int, x: int, y: int) -> None:
    if not (0 <= z <= 22) or not (0 <= x < 2**z) or not (0 <= y < 2**z):
        raise AppError("Tuile hors grille.", code="invalid_tile")


def _paths(db, layer, day: date, demo: bool, band: str | None = None) -> list[str]:
    out = []
    for ds in catalog.datasets_for_layer(db, layer, day=day, include_demo=demo):
        p = catalog.asset_path(ds, band or layer.band)
        if p:
            out.append(p)
    return out


@router.get("/tiles/{layer_key}/{date_}/{z}/{x}/{y}.png", summary="Tuile d'une couche à une date (amplitude ou classes)")
def tile(layer_key: str, date_: str, z: int, x: int, y: int, mode: str = Query("amplitude", pattern="^(amplitude|classes)$"),
         demo: bool = False, db: Session = Depends(get_db)):
    _check_zxy(z, x, y)
    day = parse_date(date_)
    layer = catalog.get_layer(db, layer_key)
    if mode == "classes":
        png = tiles.render_classes(_paths(db, layer, day, demo, "HHHH"), _paths(db, layer, day, demo, "HVHV"), z, x, y,
                                   load_ruleset())
    else:
        png = tiles.render_amplitude(_paths(db, layer, day, demo), z, x, y, layer.style)
    return Response(png, media_type="image/png", headers=CACHE)


@router.get("/tiles/change/{layer_key}/{date_a}/{date_b}/{z}/{x}/{y}.png", summary="Tuile de changement (delta dB entre deux dates)")
def change_tile(layer_key: str, date_a: str, date_b: str, z: int, x: int, y: int, threshold_db: float = Query(3.0, gt=0, le=20),
                demo: bool = False, db: Session = Depends(get_db)):
    _check_zxy(z, x, y)
    layer = catalog.get_layer(db, layer_key)
    png = tiles.render_change(_paths(db, layer, parse_date(date_a), demo), _paths(db, layer, parse_date(date_b), demo),
                              z, x, y, threshold_db)
    return Response(png, media_type="image/png", headers=CACHE)
