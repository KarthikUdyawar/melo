"""Melo admin dashboard — entry point, login gate, and sidebar navigation."""

# admin/app.py

from __future__ import annotations

import importlib
import os

import requests
import streamlit as st
from auth import is_authenticated, login_page

st.set_page_config(
    page_title="Melo Admin",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not is_authenticated():
    login_page()
    st.stop()


def _has_critical_alert() -> bool:
    """Return True if any alert with severity=critical is currently firing."""
    try:
        response = requests.get(
            "http://grafana:3000/api/alertmanager/grafana/api/v2/alerts",
            auth=("admin", os.environ.get("GRAFANA_ADMIN_PASSWORD", "admin")),
            timeout=3,
        )
        response.raise_for_status()
        return any(
            alert.get("labels", {}).get("severity") == "critical"
            for alert in response.json()
        )
    except Exception:  # noqa: BLE001
        return False


# ── Sidebar ───────────────────────────────────────────────────────────────────

PAGES = {
    "Overview": "pages.overview",
    "Songs": "pages.songs",
    "Logs": "pages.logs",
    "Metrics": "pages.metrics",
    "Alerts": "pages.alerts",
    "DB Health": "pages.db_health",
}

EXTERNAL_LINKS = {
    "Grafana": "http://localhost:3001",
    "Prometheus": "http://localhost:9090",
    "MinIO Console": "http://localhost:9001",
    "Adminer": "http://localhost:8080",
    "Flower": "http://localhost:5555",
}

_alert_badge = " 🔴" if _has_critical_alert() else ""

display_labels = {
    name: name + _alert_badge if name == "Alerts" else name
    for name in PAGES
}

with st.sidebar:
    st.title("🎵 Melo Admin")
    st.divider()

    selected_label = st.radio(
        "Navigate",
        list(display_labels.values()),
        label_visibility="collapsed",
    )

    selected = next(
        name
        for name, label in display_labels.items()
        if label == selected_label
    )

    st.divider()
    st.caption("External Tools")

    for name, url in EXTERNAL_LINKS.items():
        st.markdown(f"[{name}]({url})", unsafe_allow_html=True)

    st.divider()

    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ── Page dispatch ─────────────────────────────────────────────────────────────

module = importlib.import_module(PAGES[selected])
importlib.reload(module)
