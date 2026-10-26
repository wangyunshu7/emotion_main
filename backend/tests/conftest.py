import os
from pathlib import Path

from cryptography.fernet import Fernet

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://emotion:emotion@127.0.0.1:55432/emotion_test"
)
os.environ["SESSION_TOKEN_PEPPER"] = "test-only-" + "x" * 40
os.environ["PRIVACY_LEDGER_KEY"] = Fernet.generate_key().decode()
os.environ["AI_ENABLED"] = "true"
os.environ["AI_PROVIDER"] = "fake"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database():
    if not engine.url.database.endswith("_test"):
        raise RuntimeError("Tests require a dedicated database ending in _test")
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")


@pytest.fixture(autouse=True)
def isolate(tmp_path):
    get_settings().privacy_ledger_root = tmp_path / "privacy"
    with engine.begin() as connection:
        names = (
            connection.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename != 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        connection.execute(text("TRUNCATE " + ", ".join('"' + n + '"' for n in names) + " CASCADE"))
    yield


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        c.headers["Origin"] = "http://localhost:5173"
        session = c.get("/api/v1/auth/session").json()
        c.headers["X-CSRF-Token"] = session["csrf_token"]
        yield c


def signup(client, email="alice@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "private-password-123",
            "adult_confirmed": True,
            "terms_version": "v1",
            "privacy_version": "v1",
        },
    )
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()["user"]
