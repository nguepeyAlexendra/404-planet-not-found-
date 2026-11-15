"""Accès au catalogue NISAR de l'ASF DAAC via le paquet asf_search.

Découverte et estimation ne téléchargent rien. Le téléchargement exige un jeton Earthdata
(NV_EARTHDATA_TOKEN). Non exécutable depuis le workspace de développement (réseau bloqué) :
testé avec des doubles, à valider en conditions réelles (docs/DONNEES_NISAR.md).
"""
from dataclasses import dataclass
from pathlib import Path

import asf_search as asf

from app.core.config import get_settings
from app.core.errors import AppError, TooLarge


@dataclass
class RemoteGranule:
    source_id: str
    url: str
    size_bytes: int | None
    start_time: str | None
    maturity: str | None
    processing_level: str | None
    product: object | None = None


def discover(wkt: str, start: str, end: str, product_type: str = "GCOV", maturity: list[str] | None = None,
             max_results: int = 25) -> list[RemoteGranule]:
    """Cherche des granules NISAR L-band. Aucun téléchargement."""
    kwargs = dict(dataset=asf.DATASET.NISAR, processingLevel=product_type, intersectsWith=wkt, start=start, end=end,
                  maxResults=max_results)
    if maturity:
        kwargs["dataMaturity"] = [m.upper() for m in maturity]
    results = asf.search(**kwargs)
    out = []
    for p in results:
        props = p.properties
        out.append(RemoteGranule(source_id=props.get("fileID") or props.get("sceneName") or props.get("fileName"),
                                 url=props.get("url"), size_bytes=props.get("bytes"),
                                 start_time=props.get("startTime"), maturity=props.get("dataMaturity"),
                                 processing_level=props.get("processingLevel"), product=p))
    return out


def estimate_size_gb(granules: list[RemoteGranule]) -> float:
    return sum((g.size_bytes or 0) for g in granules) / 1e9


def check_budget(granules: list[RemoteGranule], confirm: bool = False) -> float:
    """Refuse un téléchargement qui dépasse le plafond configuré, sauf confirmation explicite."""
    total = estimate_size_gb(granules)
    limit = get_settings().ingest_max_download_gb
    if total > limit and not confirm:
        raise TooLarge(f"Téléchargement estimé à {total:.1f} Go, au-delà du plafond de {limit:.0f} Go. "
                       "Relancez avec confirmation explicite.", details={"estimated_gb": round(total, 2), "limit_gb": limit})
    return total


def download(granule: RemoteGranule, dest_dir: Path) -> Path:
    token = get_settings().earthdata_token
    if not token:
        raise AppError("Jeton Earthdata manquant (variable NV_EARTHDATA_TOKEN).", code="missing_credentials", status_code=400)
    dest_dir.mkdir(parents=True, exist_ok=True)
    session = asf.ASFSession().auth_with_token(token)
    granule.product.download(path=str(dest_dir), session=session)
    files = sorted(dest_dir.glob(f"{granule.source_id}*")) or sorted(dest_dir.glob("*.h5"))
    if not files:
        raise AppError(f"Téléchargement terminé mais fichier introuvable pour {granule.source_id}.", code="download_failed")
    return files[0]
