"""Génère un petit produit DE DÉMONSTRATION au format GCOV supposé (voir hdf5_gcov.py).

Les valeurs sont SIMULÉES (eau, forêt, ville, sol nu) : ce ne sont pas des observations NISAR.
Tout ce qui en découle porte is_demo=True et la maturité « demo ».
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

DEMO_CENTER = (9.70, 4.05)  # lon, lat : région de Douala (démo seulement)
DEMO_EPSG = 32632
SIZE = 160
PIXEL = 90.0  # m


def _scene(seed: int, deforest: float) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    hh_db = np.full((SIZE, SIZE), -11.0)
    hv_db = np.full((SIZE, SIZE), -17.0)  # végétation par défaut
    water = ((xx - 40) ** 2 + (yy - 110) ** 2) < 28**2
    hh_db[water], hv_db[water] = -23.0, -30.0
    urban = (xx > 105) & (xx < 140) & (yy > 20) & (yy < 55)
    hh_db[urban], hv_db[urban] = -3.0, -14.5
    bare = (xx < 60) & (yy < 40)
    hh_db[bare], hv_db[bare] = -13.0, -23.0
    # zone défrichée qui grandit avec deforest (0..1) : forêt dense -> sol nu
    clear = (xx > 70) & (xx < 70 + int(45 * deforest)) & (yy > 70) & (yy < 125)
    hh_db[clear], hv_db[clear] = -13.0, -23.0
    forest = ~water & ~urban & ~bare & ~clear
    hv_db[forest] = -12.5
    hh_db[forest] = -8.0
    hh_db += rng.normal(0, 0.6, hh_db.shape)
    hv_db += rng.normal(0, 0.6, hv_db.shape)
    return (10 ** (hh_db / 10)).astype("float32"), (10 ** (hv_db / 10)).astype("float32")


def make_demo_gcov(path: Path, start: datetime, seed: int = 1, deforest: float = 0.0, track: int = 77) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    hh, hv = _scene(seed, deforest)
    cx, cy = Transformer.from_crs("EPSG:4326", f"EPSG:{DEMO_EPSG}", always_xy=True).transform(*DEMO_CENTER)
    x = cx - SIZE * PIXEL / 2 + PIXEL / 2 + PIXEL * np.arange(SIZE)
    y = cy + SIZE * PIXEL / 2 - PIXEL / 2 - PIXEL * np.arange(SIZE)
    with h5py.File(path, "w") as h:
        ident = h.create_group("science/LSAR/identification")
        ident["missionId"] = "NISAR-DEMO"
        ident["trackNumber"] = track
        ident["orbitPassDirection"] = "Ascending"
        ident["zeroDopplerStartTime"] = start.astimezone(timezone.utc).isoformat()
        ident["zeroDopplerEndTime"] = (start + timedelta(seconds=30)).astimezone(timezone.utc).isoformat()
        ident["productVersion"] = "demo-1"
        g = h.create_group("science/LSAR/GCOV/grids/frequencyA")
        g["xCoordinates"], g["yCoordinates"] = x, y
        p = g.create_dataset("projection", data=DEMO_EPSG)
        p.attrs["epsg_code"] = DEMO_EPSG
        g["listOfPolarizations"] = np.array([b"HH", b"HV"])
        g["listOfCovarianceTerms"] = np.array([b"HHHH", b"HVHV"])
        for name, arr in (("HHHH", hh), ("HVHV", hv)):
            ds = g.create_dataset(name, data=arr)
            ds.attrs["_FillValue"] = np.float32("nan")
    return path
