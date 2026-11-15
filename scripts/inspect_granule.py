#!/usr/bin/env python3
"""Vérifie qu'un fichier NISAR GCOV (HDF5) a la structure attendue par NISAR Vision.

Usage : python scripts/inspect_granule.py chemin/vers/granule.h5 [--tree]

Le lecteur (backend/app/ingestion/hdf5_gcov.py) suppose certains chemins HDF5. Ils suivent la
documentation publique mais n'ont pas pu être confrontés à un granule réel pendant le développement.
Ce script dit, chemin par chemin, ce qui est présent ou absent, et propose --tree pour afficher
l'arborescence complète afin d'ajuster hdf5_gcov.py si besoin.
"""
import argparse
import sys

import h5py

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0] + "/backend")
from app.ingestion.hdf5_gcov import GRID_PATH, ID_PATH, ProductFormatError, read_gcov  # noqa: E402

EXPECTED = [
    f"{GRID_PATH}/xCoordinates", f"{GRID_PATH}/yCoordinates", f"{GRID_PATH}/projection", f"{GRID_PATH}/listOfCovarianceTerms",
    f"{GRID_PATH}/listOfPolarizations", f"{ID_PATH}/zeroDopplerStartTime", f"{ID_PATH}/zeroDopplerEndTime", f"{ID_PATH}/trackNumber",
    f"{ID_PATH}/orbitPassDirection", f"{ID_PATH}/productVersion", f"{ID_PATH}/missionId",
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--tree", action="store_true")
    a = p.parse_args()
    try:
        h = h5py.File(a.path, "r")
    except OSError as exc:
        print(f"Fichier HDF5 illisible : {exc}")
        return 1
    with h:
        print("Chemins attendus :")
        missing = 0
        for e in EXPECTED:
            ok = e in h
            missing += not ok
            print(f"  [{'OK ' if ok else 'ABSENT'}] /{e}")
        if a.tree:
            print("\nArborescence :")
            h.visititems(lambda n, o: print(f"  /{n}  {'shape=' + str(o.shape) + ' dtype=' + str(o.dtype) if isinstance(o, h5py.Dataset) else ''}"))
    print()
    try:
        prod = read_gcov(a.path)
        print(f"Lecture réussie : bandes {sorted(prod.bands)}, EPSG:{prod.epsg}, taille {len(prod.y)}x{len(prod.x)}, début {prod.meta['start']}")
        return 0
    except ProductFormatError as exc:
        print(f"Lecture impossible : {exc}")
        print(f"{missing} chemin(s) attendu(s) absent(s). Relancez avec --tree et adaptez backend/app/ingestion/hdf5_gcov.py.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
