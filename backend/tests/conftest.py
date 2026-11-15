import os
import tempfile
import uuid

_TMP = tempfile.mkdtemp(prefix="nv-tests-")
os.environ.update({"NV_ENV": "test", "NV_DATABASE_URL": os.environ.get("NV_TEST_DATABASE_URL", "sqlite://"), "NV_DATA_DIR": _TMP, "NV_RATE_LIMIT_PER_MINUTE": "0",
                   "NV_CELERY_ALWAYS_EAGER": "true", "NV_LOG_LEVEL": "WARNING"})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402,F401
from app.main import app  # noqa: E402
from app.seed.runner import seed_demo_data, seed_reference  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_reference(db)
    seed_demo_data(db)
    db.close()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture()
def cid():
    """Identifiant de session unique par test : isole AOI, jobs et progression."""
    return "t" + uuid.uuid4().hex[:20]


@pytest.fixture()
def h(cid):
    return {"X-Client-Id": cid}


@pytest.fixture()
def settings():
    return get_settings()


DEMO_AOI = {"type": "Polygon", "coordinates": [[[9.66, 4.02], [9.74, 4.02], [9.74, 4.09], [9.66, 4.09], [9.66, 4.02]]]}
CENTER_LON, CENTER_LAT = 9.70, 4.05
