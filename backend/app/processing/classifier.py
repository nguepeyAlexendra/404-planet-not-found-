"""Classification par règles (prototype configurable, fonctions pures).

Les seuils viennent d'un fichier versionné (config/rulesets). Ils ne sont pas validés :
tout résultat doit afficher la version des règles et rester qualifié de prototype.
"""
import json
from pathlib import Path

import numpy as np

from app.processing.units import to_db

RULESET_DIR = Path(__file__).resolve().parent.parent / "config" / "rulesets"
INDETERMINATE, WATER, DENSE_VEG, SPARSE_VEG, URBAN, BARE = 0, 1, 2, 3, 4, 5


class MissingBandsError(ValueError):
    def __init__(self, missing: list[str]):
        super().__init__(f"Bandes requises absentes : {', '.join(missing)}")
        self.missing = missing


def load_ruleset(name: str = "gcov_lband_prototype_v0_1") -> dict:
    return json.loads((RULESET_DIR / f"{name}.json").read_text(encoding="utf-8"))


def classify(bands_linear: dict[str, np.ndarray], ruleset: dict, nodata: float | None = None) -> np.ndarray:
    """Retourne un tableau uint8 de classes. Pixel invalide ou règle non satisfaite -> 0 (indéterminé)."""
    missing = [b for b in ruleset["required_bands"] if b not in bands_linear]
    if missing:
        raise MissingBandsError(missing)
    hh = to_db(bands_linear["HHHH"], nodata)
    hv = to_db(bands_linear["HVHV"], nodata)
    if hh.shape != hv.shape:
        raise ValueError("Les bandes HH et HV n'ont pas la même grille.")
    t = ruleset["thresholds_db"]
    out = np.zeros(hh.shape, dtype="uint8")
    valid = np.isfinite(hh) & np.isfinite(hv)
    with np.errstate(invalid="ignore"):
        water = valid & (hh < t["water_hh_max"]) & (hv < t["water_hv_max"])
        urban = valid & ~water & (hh > t["urban_hh_min"])
        dense = valid & ~water & ~urban & (hv >= t["dense_veg_hv_min"])
        sparse = valid & ~water & ~urban & ~dense & (hv >= t["sparse_veg_hv_min"])
        bare = valid & ~water & ~urban & ~dense & ~sparse & (hh >= t["water_hh_max"])
    out[water], out[urban], out[dense], out[sparse], out[bare] = WATER, URBAN, DENSE_VEG, SPARSE_VEG, BARE
    return out


def classify_pixel(hh_linear: float | None, hv_linear: float | None, ruleset: dict) -> dict:
    """Explication d'un pixel : classe, valeurs en dB, texte issu des règles documentées."""
    if hh_linear is None or hv_linear is None:
        return {"class_id": INDETERMINATE, "class_key": "indeterminate", "label": "Indéterminé",
                "hh_db": None, "hv_db": None, "ratio_db": None,
                "explanation": ruleset["explanations"]["indeterminate"], "ruleset_version": ruleset["version"]}
    arr = classify({"HHHH": np.array([[hh_linear]]), "HVHV": np.array([[hv_linear]])}, ruleset)
    cid = int(arr[0, 0])
    info = ruleset["classes"][str(cid)]
    hh_db = float(to_db(np.array([hh_linear]))[0])
    hv_db = float(to_db(np.array([hv_linear]))[0])
    return {"class_id": cid, "class_key": info["key"], "label": info["label"],
            "hh_db": None if np.isnan(hh_db) else round(hh_db, 2),
            "hv_db": None if np.isnan(hv_db) else round(hv_db, 2),
            "ratio_db": None if np.isnan(hh_db) or np.isnan(hv_db) else round(hh_db - hv_db, 2),
            "explanation": ruleset["explanations"][info["key"]], "ruleset_version": ruleset["version"]}
