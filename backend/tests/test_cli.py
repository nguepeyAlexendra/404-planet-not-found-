import pytest

from app import cli
from app.ingestion.pipeline import IngestError


def test_seed_reference_est_idempotent(capsys):
    assert cli.main(["seed-reference"]) == 0
    assert cli.main(["seed-reference"]) == 0
    assert "prêtes" in capsys.readouterr().out


def test_purge_exports(capsys):
    assert cli.main(["purge-exports"]) == 0
    assert "export(s) supprimé(s)" in capsys.readouterr().out


def test_ingest_local_fichier_absent_echoue_proprement(tmp_path):
    with pytest.raises(IngestError):
        cli.main(["ingest-local", str(tmp_path / "absent.h5"), "--maturity", "beta"])


def test_ingest_remote_dry_run_ne_telecharge_rien(monkeypatch, capsys):
    from app.ingestion import asf_client

    g = asf_client.RemoteGranule("NISAR_X", "https://example.invalid/x.h5", 2_000_000_000, "2026-11-01T00:00:00Z", "Validated", "L2")
    monkeypatch.setattr(asf_client, "discover", lambda *a, **k: [g])
    monkeypatch.setattr(asf_client, "download", lambda *a, **k: pytest.fail("téléchargement interdit en dry-run"))
    assert cli.main(["ingest-remote", "--wkt", "POINT(9.7 4.05)", "--start", "2026-10-21", "--end", "2026-11-05", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "1 granule(s)" in out and "NISAR_X" in out


def test_ingest_remote_refuse_au_dessus_du_plafond(monkeypatch):
    from app.core.errors import TooLarge
    from app.ingestion import asf_client

    g = asf_client.RemoteGranule("BIG", "https://example.invalid/b.h5", 500 * 10**9, None, "Validated", "L2")
    monkeypatch.setattr(asf_client, "discover", lambda *a, **k: [g])
    monkeypatch.setattr(asf_client, "download", lambda *a, **k: pytest.fail("ne doit pas télécharger"))
    with pytest.raises(TooLarge):
        cli.main(["ingest-remote", "--wkt", "POINT(9.7 4.05)", "--start", "2026-10-21", "--end", "2026-11-05"])
