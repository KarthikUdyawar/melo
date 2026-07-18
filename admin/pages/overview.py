"""Overview page — health status and key Prometheus metrics."""

# admin/pages/overview.py

from __future__ import annotations

from typing import Any, cast

import requests
import streamlit as st

MELO_API = "http://api:8000"
PROMETHEUS_URL = "http://prometheus:9090"


def _query_prometheus(expr: str) -> float | None:
    """Return the scalar result of a Prometheus instant query, or None."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": expr},
            timeout=5,
        )
        response.raise_for_status()

        result = response.json().get("data", {}).get("result", [])
        if not result:
            return None

        return float(result[0]["value"][1])

    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def _fetch_health() -> dict[str, Any]:
    """Return parsed health response body, or empty dict on failure."""
    try:
        response = requests.get(f"{MELO_API}/health", timeout=5)
        response.raise_for_status()

        body = response.json().get("body", {})
        return cast(dict[str, Any], body)

    except (requests.RequestException, ValueError):
        return {}


st.header("Overview")

health = _fetch_health()

# ── Service status ────────────────────────────────────────────────────────────

st.subheader("Service Health")
cols = st.columns(4)

services = {
    "API": health.get("status"),
    "DB": health.get("db"),
    "Redis": health.get("redis"),
    "MinIO": health.get("minio"),
}

for col, (name, status) in zip(cols, services.items(), strict=True):
    icon = "🟢" if status in ("ok", "up") else ("🔴" if status else "⚪")
    col.metric(name, f"{icon} {status or 'unknown'}")

st.divider()

# ── Key metrics ───────────────────────────────────────────────────────────────

st.subheader("Key Metrics")
mcols = st.columns(4)

metrics = {
    "Songs (done)": 'songs_by_status_total{status="done"}',
    "Songs (processing)": 'songs_by_status_total{status="processing"}',
    "Queue depth": "celery_queue_depth",
    "Active tasks": "celery_active_tasks",
}

for col, (label, expr) in zip(mcols, metrics.items(), strict=True):
    value = _query_prometheus(expr)
    col.metric(label, int(value) if value is not None else "—")
