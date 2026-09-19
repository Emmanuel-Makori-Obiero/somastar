"""Test setup: an isolated SQLite file, temp upload dir and the offline mock LLM.
Env vars must be set BEFORE the app is imported (settings are read at import)."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="somastar-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["STORAGE_LOCAL_DIR"] = f"{_TMP}/uploads"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["ENV"] = "development"

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import login_limiter, register_limiter
from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    login_limiter.reset_all()
    register_limiter.reset_all()
    yield


@pytest.fixture
def client():
    # No `with`: skips lifespan (migrations); tables are created by fresh_db.
    return TestClient(app)


def _register(client, email="student@example.com", name="Sam", password="Passw0rdX"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return _register(client)


@pytest.fixture
def make_user(client):
    return lambda email: _register(client, email=email)


BREAKDOWN = "Q1 | Algebra | 10 | 9 | Mathematical reasoning\nQ2 | Geometry | 10 | 3 | Diagram interpretation\nQ3 | Essay | 10 | 8 | graph  reading"


@pytest.fixture
def upload(client, auth):
    def _upload(text=BREAKDOWN, headers=None, **extra):
        data = {"title": "Mid-Term", "subject_name": "Maths", "extracted_text": text, **extra}
        return client.post("/api/exams", data=data, headers=headers or auth)
    return _upload
