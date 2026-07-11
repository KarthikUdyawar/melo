"""Pyroscope continuous profiling setup.

Configures always-on wall-clock and CPU profiling for the given service.
No-ops gracefully when PYROSCOPE_SERVER_URL is unset or pyroscope is
not installed, so local development is unaffected.
"""

# app/core/profiling.py
from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_pyroscope(app_name: str) -> None:
    """Start Pyroscope continuous profiling for the named service.

    Args:
        app_name: Profiling label, e.g. ``"melo.api"`` or ``"melo.worker"``.
    """
    from app.core.config import get_settings

    settings = get_settings()
    server_url = settings.pyroscope_server_url

    if not server_url:
        logger.info("pyroscope_skipped", reason="PYROSCOPE_SERVER_URL not set")
        return

    try:
        import pyroscope_io as pyroscope

        pyroscope.configure(
            application_name=app_name,
            server_address=server_url,
            tags={"env": settings.app_env},
        )
        logger.info("pyroscope_started", app_name=app_name, server=server_url)
    except Exception:  # noqa: BLE001
        logger.exception("pyroscope_start_failed", app_name=app_name)
