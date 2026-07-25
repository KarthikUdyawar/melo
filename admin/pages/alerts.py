"""Alerts page — active Grafana alert rules."""

# admin/pages/alerts.py

from __future__ import annotations

import os
from typing import Any, cast

import requests
import streamlit as st

GRAFANA_URL = "http://grafana:3000"


def _fetch_alerts() -> list[dict[str, Any]]:
    """Return active alert instances from the Grafana Alerting API."""
    password = os.environ.get("GRAFANA_ADMIN_PASSWORD", "")

    try:
        response = requests.get(
            f"{GRAFANA_URL}/api/v1/provisioning/alert-rules",
            auth=("admin", password),
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        if isinstance(data, list):
            return cast(list[dict[str, Any]], data)

        return []

    except Exception:  # noqa: BLE001
        return []


def _fetch_firing() -> list[dict[str, Any]]:
    """Return currently firing alert instances."""
    password = os.environ.get("GRAFANA_ADMIN_PASSWORD", "")

    try:
        response = requests.get(
            f"{GRAFANA_URL}/api/alertmanager/grafana/api/v2/alerts",
            auth=("admin", password),
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        if isinstance(data, list):
            return cast(list[dict[str, Any]], data)

        return []

    except Exception:  # noqa: BLE001
        return []


st.header("Alerts")

firing = _fetch_firing()

if firing:
    st.error(f"🔴 {len(firing)} alert(s) firing")

    for alert in firing:
        labels = cast(dict[str, Any], alert.get("labels", {}))

        st.warning(
            f"**{labels.get('alertname', 'unknown')}** — "
            f"severity: {labels.get('severity', '?')} — "
            f"since: {alert.get('startsAt', '?')}"
        )
else:
    st.success("✅ No alerts firing.")

st.divider()
st.subheader("All Rules")

rules = _fetch_alerts()

if not rules:
    st.info("No alert rules found or Grafana unreachable.")
else:
    rows: list[dict[str, str]] = [
        {
            "uid": str(rule.get("uid", "")),
            "title": str(rule.get("title", "")),
            "for": str(rule.get("for", "")),
            "labels": str(rule.get("labels", {})),
        }
        for rule in rules
    ]

    st.dataframe(rows, use_container_width=True)
