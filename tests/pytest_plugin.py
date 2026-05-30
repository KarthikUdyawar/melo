# tests/pytest_plugin.py
#
# Runs at pytest plugin load time — before any conftest.py is processed.
# Sets the bare minimum so app modules can be imported without crashing.
#
# Uses setdefault so that:
#   - tests/conftest.py (integration) can override APP_ENV → "test"
#   - tests/unit/conftest.py can override DATABASE_URL → SQLite
#
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_FILE_PATH", f"{_tmp}/app.log")
