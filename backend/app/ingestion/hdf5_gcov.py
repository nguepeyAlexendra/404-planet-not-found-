"""Lecture d'un produit NISAR L2 GCOV (HDF5).

ATTENTION : la structure interne ci-dessous (/science/LSAR/GCOV/grids/frequencyA/...) suit la
documentation publique telle que je la connais, mais n'a PAS pu être confrontée à un vrai granule
dans cet environnement (accès ASF bloqué). À confirmer sur un granule réel avant production :
voir docs/DONNEES_NISAR.md. Toute différence se corrige dans ce seul fichier.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

GRID_PATH = "science/LSAR/GCOV/grids/frequencyA"
ID_PATH = "science/LSAR/identification"


class ProductFormatError(ValueError):
    """Le fichier n'a pas la structure attendue d'un produit GCOV."""


@dataclass
class GcovProduct:
    bands: dict[str, np.ndarray]
    x: np.ndarray
    y: np.ndarray
    epsg: int
    nodata: float | None
    meta: dict = field(default_factory=dict)

    @property
    def pixel_size(self) -> tuple[float, float]:
        return float(abs(self.x[1] - self.x[0])), float(abs(self.y[1] - self.y[0]))


def _s(v) -> str:
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray) and v.shape == ():
        return _s(v.item())
    return str(v)


def _parse_time(v) -> datetime:
    text = _s(v).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ProductFormatError(f"Date illisible : {text!r}") from exc
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _get(h, path: str):
    if path not in h:
        raise ProductFormatError(f"Élément HDF5 absent : /{path}")
    return h[path][()]


def read_gcov(path: Path) -> GcovProduct:
    try:
        h = h5py.File(path, "r")
    except OSError as exc:
        raise ProductFormatError(f"Fichier HDF5 illisible : {exc}") from exc
    with h:
        if GRID_PATH not in h:
            raise ProductFormatError(f"Groupe /{GRID_PATH} absent : ce n'est pas un produit GCOV attendu.")
        grp = h[GRID_PATH]
        x = np.asarray(grp["xCoordinates"][()], dtype="float64") if "xCoordinates" in grp else None
        y = np.asarray(grp["yCoordinates"][()], dtype="float64") if "yCoordinates" in grp else None
        if x is None or y is None or len(x) < 2 or len(y) < 2:
            raise ProductFormatError("Coordonnées de grille (xCoordinates/yCoordinates) absentes ou trop courtes.")
        if "projection" not in grp:
            raise ProductFormatError("Projection absente.")
        proj = grp["projection"]
        epsg = proj.attrs.get("epsg_code", proj[()] if proj.shape == () else None)
        try:
            epsg = int(np.asarray(epsg).item())
        except (TypeError, ValueError) as exc:
            raise ProductFormatError("Code EPSG illisible.") from exc
        terms = [_s(t) for t in np.atleast_1d(grp["listOfCovarianceTerms"][()])] if "listOfCovarianceTerms" in grp else []
        bands: dict[str, np.ndarray] = {}
        nodata = None
        for name in terms:
            if name not in grp:
                continue
            ds = grp[name]
            if ds.shape != (len(y), len(x)):
                raise ProductFormatError(f"Bande {name} : forme {ds.shape} incohérente avec la grille ({len(y)}, {len(x)}).")
            if np.dtype(ds.dtype).kind == "c":
                continue  # termes croisés complexes : hors périmètre du MVP
            bands[name] = ds[()].astype("float32")
            fv = ds.attrs.get("_FillValue")
            if fv is not None:
                nodata = float(np.asarray(fv).item())
        if not bands:
            raise ProductFormatError("Aucune bande de covariance réelle (HHHH, HVHV...) trouvée.")
        ident = h[ID_PATH] if ID_PATH in h else None
        if ident is None:
            raise ProductFormatError(f"Groupe /{ID_PATH} absent.")
        meta = {
            "mission": _s(ident["missionId"][()]) if "missionId" in ident else "NISAR",
            "track": int(ident["trackNumber"][()]) if "trackNumber" in ident else None,
            "orbit_direction": _s(ident["orbitPassDirection"][()]) if "orbitPassDirection" in ident else None,
            "start": _parse_time(_get(h, f"{ID_PATH}/zeroDopplerStartTime")),
            "end": _parse_time(ident["zeroDopplerEndTime"][()]) if "zeroDopplerEndTime" in ident else None,
            "product_version": _s(ident["productVersion"][()]) if "productVersion" in ident else None,
            "frequency_band": "L",
            "polarizations": [_s(p) for p in np.atleast_1d(grp["listOfPolarizations"][()])] if "listOfPolarizations" in grp else [],
        }
    return GcovProduct(bands=bands, x=x, y=y, epsg=epsg, nodata=nodata, meta=meta)
