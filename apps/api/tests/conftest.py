import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://fieldops:fieldops@localhost:5432/fieldops_test",
)
os.environ["SEED_ON_STARTUP"] = "false"

from app.config import get_settings

get_settings.cache_clear()

from app.db import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed_all  # noqa: E402
import app.models  # noqa: E402, F401


def _ensure_database(url: str) -> None:
    admin = create_engine(url.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT")
    db_name = url.rsplit("/", 1)[-1]
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": db_name}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()


@pytest.fixture()
def client():
    settings = get_settings()
    _ensure_database(settings.database_url)
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    seed_session = Session()
    seed_all(seed_session)
    seed_session.close()

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    eng.dispose()


@pytest.fixture()
def auth_headers(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@fieldops.pt", "password": "fieldops"},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
