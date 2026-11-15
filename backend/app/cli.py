"""Commandes d'exploitation : python -m app.cli <commande>."""
import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.ingestion import asf_client
from app.ingestion.pipeline import IngestError, ingest_file
from app.seed.runner import seed_demo_data, seed_reference
from app.services.exports import purge_expired


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nisar-vision")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-reference", help="couches, règles, récits, parcours, glossaire (sans donnée satellite)")
    sub.add_parser("seed-demo", help="six granules SIMULÉS étiquetés demo")
    loc = sub.add_parser("ingest-local", help="ingère un fichier GCOV HDF5 déjà téléchargé")
    loc.add_argument("path", type=Path)
    loc.add_argument("--maturity", choices=["beta", "provisional", "validated"], required=True)
    rem = sub.add_parser("ingest-remote", help="cherche puis ingère des granules NISAR via ASF (jeton Earthdata requis)")
    rem.add_argument("--wkt", required=True, help="zone au format WKT (EPSG:4326)")
    rem.add_argument("--start", required=True)
    rem.add_argument("--end", required=True)
    rem.add_argument("--maturity", nargs="+", default=["provisional", "validated"])
    rem.add_argument("--max-results", type=int, default=5)
    rem.add_argument("--dry-run", action="store_true", help="liste et estime la taille, ne télécharge rien")
    rem.add_argument("--confirm", action="store_true", help="autorise un téléchargement au-delà du plafond")
    sub.add_parser("purge-exports", help="supprime les exports expirés")
    args = p.parse_args(argv)
    db = SessionLocal()
    s = get_settings()
    try:
        if args.cmd == "seed-reference":
            seed_reference(db)
            print("Données de référence prêtes.")
        elif args.cmd == "seed-demo":
            seed_reference(db)
            print(f"{len(seed_demo_data(db))} granules de démonstration (simulés) ingérés.")
        elif args.cmd == "ingest-local":
            ds = ingest_file(db, args.path, maturity=args.maturity)
            print(f"OK {ds.source_id} ({ds.maturity}, {ds.status})")
        elif args.cmd == "ingest-remote":
            granules = asf_client.discover(args.wkt, args.start, args.end, maturity=args.maturity, max_results=args.max_results)
            print(f"{len(granules)} granule(s), {asf_client.estimate_size_gb(granules):.2f} Go estimés")
            for g in granules:
                print(f"  {g.source_id}  {g.start_time}  {g.maturity}  {(g.size_bytes or 0) / 1e9:.2f} Go")
            if args.dry_run or not granules:
                return 0
            asf_client.check_budget(granules, args.confirm)
            for g in granules:
                path = asf_client.download(g, s.raw_dir)
                try:
                    ds = ingest_file(db, path, maturity=(g.maturity or "provisional").lower(), source_uri=g.url,
                                     source_id=g.source_id, license_="NASA Earthdata, usage libre avec citation")
                    print(f"OK {ds.source_id}")
                except IngestError as exc:
                    print(f"ÉCHEC {exc}", file=sys.stderr)
        elif args.cmd == "purge-exports":
            print(f"{purge_expired(db)} export(s) supprimé(s).")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
