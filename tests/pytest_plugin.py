# tests/pytest_plugin.py
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.setdefault("LOG_FILE_PATH", f"{_tmp}/app.log")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://melo_test:melo_test@localhost:15432/melo_test",
)
