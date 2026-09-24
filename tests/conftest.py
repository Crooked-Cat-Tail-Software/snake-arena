"""Backend/API tests run against a real Postgres database now, not a
throwaway SQLite file -- see docs/ai-usage-report.md for why. This needs
a reachable Postgres server: `docker compose up -d db` starts one (and
creates the snake_arena_test database this points at by default -- see
db-init/001-create-test-db.sql), or point TEST_DATABASE_URL at any other
Postgres you have.

Unlike a fresh SQLite file per test, a real server can't be spun up fresh
for free, so isolation instead comes from dropping and recreating every
table before each test runs.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
from app.database import Base, get_db  # noqa: E402

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://snake_arena:snake_arena@localhost:5432/snake_arena_test",
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client():
    """A TestClient wired to a real Postgres database, reset before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
