"""Isolate API tests from the application's configured database and storage."""

import os
import shutil
import tempfile
from pathlib import Path


_test_root = Path(tempfile.mkdtemp(prefix="terraguard-pytest-"))
_test_database = _test_root / "terraguard-test.sqlite3"

# Set these before importing any application modules: Settings and the SQLAlchemy
# engine are constructed at import time, and the app's .env must not override
# the test database selection.
os.environ["DATABASE_URL"] = f"sqlite:///{_test_database.as_posix()}"
os.environ["STORAGE_DIR"] = str(_test_root / "storage")
os.environ["DEMO_DATA_DIR"] = str(_test_root / "demo_data")

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_database():
    from app import models  # noqa: F401 - register every mapped table
    from app.database import Base, engine
    from app.seed import seed_database_if_empty

    # Guard against accidental changes to environment/config allowing the
    # application's real database to be used by this fixture.
    database_path = Path(engine.url.database).resolve()
    if database_path == (Path(__file__).resolve().parents[1] / "terraguard.db").resolve():
        raise RuntimeError("Refusing to run tests against the application database")

    Base.metadata.create_all(bind=engine)
    seed_database_if_empty()
    yield
    engine.dispose()


def pytest_unconfigure(config):
    # Pytest invokes this after fixture teardown; disposing again is safe and
    # ensures SQLite has released the file before Windows removes the folder.
    from app.database import engine

    engine.dispose()
    shutil.rmtree(_test_root, ignore_errors=True)
