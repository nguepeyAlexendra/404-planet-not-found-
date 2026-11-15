import os
import subprocess
import sys


def test_la_tache_est_enregistree_quand_le_worker_ne_charge_que_celery_app():
    """Régression : `celery -A app.workers.celery_app worker` doit connaître nisar.run_job."""
    code = ("from app.workers.celery_app import celery\n"
            "celery.loader.import_default_modules()\n"
            "print('REGISTERED' if 'nisar.run_job' in celery.tasks else 'MISSING')")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
                         env={**os.environ, "NV_ENV": "test", "NV_DATABASE_URL": "sqlite://"})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "REGISTERED"
