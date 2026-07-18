"""Metrics page — live Prometheus query with preset buttons."""

# admin/pages/metrics.py

from __future__ import annotations

from typing import Any, cast

import requests
import streamlit as st

PROMETHEUS_URL = "http://prometheus:9090"

PRESETS = {
    "Queue depth": "celery_queue_depth",
    "Error rate (5m)": 'rate(http_requests_total{status=~"5.."}[5m])',
    "p99 latency (5m)": (
        "histogram_quantile(0.99,"
        " sum(rate(http_request_duration_seconds_bucket[5m])) by (le))"
    ),
    "Songs by status": "songs_by_status_total",
    "Active tasks": "celery_active_tasks",
}


def _run_query(expr: str) -> list[dict[str, Any]]:
    """Execute a Prometheus instant query and return the result list."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": expr},
            timeout=10,
        )
        response.raise_for_status()

        result = response.json().get("data", {}).get("result", [])
        return cast(list[dict[str, Any]], result)

    except Exception:  # noqa: BLE001
        return []


st.header("Metrics")

# ── Preset buttons ────────────────────────────────────────────────────────────

st.caption("Presets")
preset_cols = st.columns(len(PRESETS))

for col, (label, expr) in zip(
    preset_cols,
    PRESETS.items(),
    strict=True,
):
    if col.button(label, use_container_width=True):
        st.session_state["metrics_query"] = expr

# ── Query input ───────────────────────────────────────────────────────────────

query = st.text_input(
    "PromQL expression",
    key="metrics_query",
    placeholder="e.g. celery_queue_depth",
)

if query:
    results = _run_query(query)

    if not results:
        st.warning("No data returned.")
    else:
        rows: list[dict[str, str]] = []

        for item in results:
            metric = cast(dict[str, str], item["metric"])
            value = cast(list[Any], item["value"])[1]

            metric_labels = ", ".join(
                f'{key}="{val}"'
                for key, val in metric.items()
            )

            rows.append(
                {
                    "metric": metric_labels or "(no labels)",
                    "value": str(value),
                }
            )

        st.dataframe(rows, use_container_width=True)
