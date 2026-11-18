"""Test isolation: every pytest session runs on a throw-away SQLite file.

backend.app.db reads DATABASE_URL from the environment at import time and
load_dotenv() never overrides a variable that is already set, so setting it
here (before any test module imports the app) keeps tests away from the real
database configured in backend/.env.
"""
import os
import shutil
import tempfile

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="qaqpan_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR.replace(os.sep, '/')}/test.db"


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    from backend.app.db import init_db
    init_db()


def pytest_sessionfinish(session, exitstatus):
    try:
        from backend.app.db import engine
        engine.dispose()
    finally:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
