"""Exports d'une analyse : CSV, GeoJSON, SVG, PDF. Chaque fichier embarque données, unités, AOI,
période, sources, date d'exécution, méthode, paramètres et limites."""
import csv
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.models import Export, Job

FORMATS = ("csv", "geojson", "svg", "pdf")


def _meta(src: Job) -> dict:
    r = src.result or {}
    return {"job_id": src.id, "kind": src.kind, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "method": r.get("method"), "method_version": r.get("method_version"), "params": src.params,
            "dataset_ids": r.get("dataset_ids"), "has_demo": r.get("has_demo", False), "warnings": r.get("warnings", []),
            "limits": r.get("limits", [])}


def _csv(src: Job) -> bytes:
    r, m = src.result, _meta(src)
    out = io.StringIO()
    out.write(f"# NISAR Vision, export {src.kind}, généré le {m['generated_at']}\n")
    out.write(f"# analyse: {src.id}, méthode: {m['method']} ({m['method_version']})\n")
    out.write(f"# paramètres: {json.dumps({k: v for k, v in src.params.items() if k != 'geometry'}, ensure_ascii=False)}\n")
    out.write(f"# datasets: {m['dataset_ids']}\n")
    if m["has_demo"]:
        out.write("# ATTENTION: contient des données de DÉMONSTRATION simulées, pas des observations NISAR\n")
    for w in m["warnings"] + m["limits"]:
        out.write(f"# {w}\n")
    w = csv.writer(out)
    if src.kind == "time_series":
        w.writerow(["periode", "n_observations", "bande", "moyenne_dB", "min_dB", "max_dB", "surface_valide_km2"])
        for s in r["series"]:
            for band, v in s["bands"].items():
                w.writerow([s["period"], s["n_observations"], band, v["mean_db"], v["min_db"], v["max_db"], s["valid_area_km2"]])
    elif src.kind == "change_matrix":
        labels = r["labels"]
        w.writerow(["classe_date_A \\ classe_date_B", *labels])
        for i, row in enumerate(r["matrix"]["area_km2"]):
            w.writerow([labels[i], *row])
        w.writerow([])
        w.writerow(["classe", "perdu_km2", "gagne_km2", "net_km2"])
        for i, lab in enumerate(labels):
            w.writerow([lab, r["matrix"]["lost_km2"][i], r["matrix"]["gained_km2"][i], r["matrix"]["net_km2"][i]])
    elif src.kind == "projection":
        w.writerow(["scenario", "jour", "valeur", "bas_95", "haut_95"])
        for name, sc in r["scenarios"].items():
            for pt in sc["points"]:
                w.writerow([name, pt["day"], round(pt["value"], 4), round(pt["low"], 4), round(pt["high"], 4)])
    else:
        raise AppError(f"Export CSV non pris en charge pour {src.kind}.", code="unsupported_export")
    return out.getvalue().encode("utf-8-sig")


def _geojson(src: Job) -> bytes:
    geometry = src.params.get("geometry")
    if not geometry:
        raise AppError("Cette analyse n'a pas de zone à exporter.", code="unsupported_export")
    feature = {"type": "Feature", "geometry": geometry, "properties": {**_meta(src), "result": src.result}}
    return json.dumps({"type": "FeatureCollection", "features": [feature],
                       "crs_note": "WGS84 (EPSG:4326)"}, ensure_ascii=False).encode("utf-8")


def _svg(src: Job) -> bytes:
    r = src.result
    if src.kind != "time_series":
        raise AppError("L'export SVG est disponible pour les séries temporelles.", code="unsupported_export")
    pts = [(i, s["bands"].get("HH", {}).get("mean_db")) for i, s in enumerate(r["series"])]
    pts = [(i, v) for i, v in pts if v is not None]
    if not pts:
        raise AppError("Aucune valeur HH à tracer.", code="unsupported_export")
    W, H, pad = 640, 320, 48
    ys = [v for _, v in pts]
    lo, hi = min(ys) - 0.5, max(ys) + 0.5
    n = max(len(r["series"]) - 1, 1)
    X = lambda i: pad + (W - 2 * pad) * i / n  # noqa: E731
    Y = lambda v: H - pad - (H - 2 * pad) * (v - lo) / (hi - lo)  # noqa: E731
    path = " ".join(("M" if k == 0 else "L") + f"{X(i):.1f} {Y(v):.1f}" for k, (i, v) in enumerate(pts))
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' font-family='sans-serif' font-size='12'>"
           f"<text x='{pad}' y='20' font-weight='600'>Rétrodiffusion moyenne HH (dB), {r['frequency']}</text>"
           f"<line x1='{pad}' y1='{H - pad}' x2='{W - pad}' y2='{H - pad}' stroke='#888'/>"
           f"<line x1='{pad}' y1='{pad}' x2='{pad}' y2='{H - pad}' stroke='#888'/>"
           f"<path d='{path}' fill='none' stroke='#0b57d0' stroke-width='2'/>"
           f"<text x='{pad}' y='{H - 12}'>{r['series'][0]['period']}</text>"
           f"<text x='{W - pad}' y='{H - 12}' text-anchor='end'>{r['series'][-1]['period']}</text>"
           f"<text x='8' y='{Y(hi - 0.5):.0f}'>{hi - 0.5:.1f}</text><text x='8' y='{Y(lo + 0.5):.0f}'>{lo + 0.5:.1f}</text>"
           f"<text x='{pad}' y='{H - 30}' fill='#555'>Source NISAR, unité dB, méthode {r['method_version']}</text></svg>")
    return svg.encode("utf-8")


def _pdf(src: Job) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    m, r = _meta(src), src.result
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Analyse NISAR Vision {src.id}")
    st = getSampleStyleSheet()
    story = [Paragraph("NISAR Vision : rapport d'analyse", st["Title"]),
             Paragraph(f"Type : {src.kind} · généré le {m['generated_at']} · analyse {src.id}", st["Normal"]), Spacer(1, 10)]
    if m["has_demo"]:
        story += [Paragraph("<b>ATTENTION : ce rapport contient des données de démonstration simulées, "
                            "pas des observations NISAR.</b>", st["Normal"]), Spacer(1, 8)]
    params = {k: v for k, v in src.params.items() if k != "geometry"}
    story += [Paragraph("Paramètres", st["Heading2"]), Paragraph(json.dumps(params, ensure_ascii=False), st["Normal"]),
              Paragraph("Méthode", st["Heading2"]), Paragraph(f"{m['method']} (version {m['method_version']})", st["Normal"]),
              Paragraph(f"Datasets sources : {m['dataset_ids']}", st["Normal"])]
    if src.kind == "time_series":
        rows = [["Période", "Obs.", "HH moy. (dB)", "HV moy. (dB)"]]
        for s in r["series"]:
            rows.append([s["period"], s["n_observations"], s["bands"].get("HH", {}).get("mean_db", "n.d."),
                         s["bands"].get("HV", {}).get("mean_db", "n.d.")])
        story += [Paragraph("Résultats", st["Heading2"]), Table(rows)]
    elif src.kind == "change_matrix":
        story += [Paragraph("Résultats", st["Heading2"]), Paragraph(r["summary_text"], st["Normal"])]
    elif src.kind == "projection":
        story += [Paragraph("Résultats", st["Heading2"]), Paragraph(f"Variable : {r['variable']} · scénarios : "
                                                                    f"{', '.join(r['scenarios'])}", st["Normal"])]
    story.append(Paragraph("Limites", st["Heading2"]))
    for w in m["warnings"] + m["limits"]:
        story.append(Paragraph("• " + w, st["Normal"]))
    story.append(Paragraph("Source des données : NISAR (NASA-ISRO), distribué par l'ASF DAAC.", st["Normal"]))
    doc.build(story)
    return buf.getvalue()


BUILDERS = {"csv": (_csv, "text/csv"), "geojson": (_geojson, "application/geo+json"),
            "svg": (_svg, "image/svg+xml"), "pdf": (_pdf, "application/pdf")}


def build_export(db: Session, source_job_id: str, fmt: str, export_job_id: str) -> Export:
    if fmt not in BUILDERS:
        raise AppError(f"Format inconnu : {fmt}.", code="unsupported_export", details={"formats": list(FORMATS)})
    src = db.get(Job, source_job_id)
    if src is None:
        raise NotFound(f"Analyse {source_job_id} introuvable.")
    if src.status != "succeeded" or not src.result:
        raise AppError("L'analyse source n'est pas terminée avec succès.", code="job_not_ready")
    data = BUILDERS[fmt][0](src)
    s = get_settings()
    s.export_dir.mkdir(parents=True, exist_ok=True)
    eid = str(uuid.uuid4())
    path = s.export_dir / f"{eid}.{fmt}"
    path.write_bytes(data)
    exp = Export(id=eid, job_id=export_job_id, format=fmt, path=str(path), size_bytes=len(data),
                 expires_at=datetime.now(timezone.utc) + timedelta(hours=s.export_ttl_hours))
    db.add(exp)
    db.commit()
    return exp


def purge_expired(db: Session) -> int:
    now = datetime.now(timezone.utc)
    n = 0
    for exp in db.scalars(select(Export)).all():
        expires = exp.expires_at if exp.expires_at.tzinfo else exp.expires_at.replace(tzinfo=timezone.utc)
        if expires < now:
            Path(exp.path).unlink(missing_ok=True)
            db.delete(exp)
            n += 1
    db.commit()
    return n
