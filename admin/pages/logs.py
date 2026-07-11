"""Logs page — tail recent log lines from Loki."""

# admin/pages/logs.py

from __future__ import annotations

import datetime
import time
from typing import Any, cast

import requests
import streamlit as st

LOKI_URL = "http://loki:3100"


def _fetch_logs(service: str, level: str, limit: int) -> list[dict[str, str]]:
    """Return recent log entries from Loki matching service and level filters."""
    query = f'{{service="{service}"}}'
    if level != "all":
        query = f'{{service="{service}", level="{level}"}}'

    end_ns = int(time.time() * 1e9)
    start_ns = end_ns - int(2 * 3600 * 1e9)  # last 2 hours

    params: dict[str, str | int] = {
        "query": query,
        "start": start_ns,
        "end": end_ns,
        "limit": limit,
        "direction": "backward",
    }

    try:
        response = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params=params,
            timeout=10,
        )
        response.raise_for_status()

        streams = cast(
            list[dict[str, Any]],
            response.json().get("data", {}).get("result", []),
        )

        rows: list[dict[str, str]] = []

        for stream in streams:
            labels = cast(dict[str, str], stream.get("stream", {}))
            values = cast(list[list[str]], stream.get("values", []))

            for ts, line in values:
                rows.append(
                    {
                        "timestamp": ts,
                        "service": labels.get("service", ""),
                        "level": labels.get("level", ""),
                        "line": line,
                    }
                )

        rows.sort(key=lambda row: row["timestamp"], reverse=True)
        return rows

    except Exception:  # noqa: BLE001
        return []


st.header("Logs")

fcols = st.columns(3)

service = fcols[0].selectbox("Service", ["api", "worker"])
level = fcols[1].selectbox("Level", ["all", "info", "warning", "error"])
limit = fcols[2].number_input(
    "Lines",
    min_value=10,
    max_value=500,
    value=100,
    step=10,
)

if st.button("Refresh"):
    st.rerun()

rows = _fetch_logs(service, level, int(limit))

if not rows:
    st.info("No log lines found. Check that Loki is running and Promtail is scraping.")
else:
    st.caption(f"{len(rows)} lines")

    for row in rows:
        ts_sec = int(row["timestamp"]) // int(1e9)
        ts_str = datetime.datetime.fromtimestamp(
            ts_sec,
            tz=datetime.UTC,
        ).strftime("%Y-%m-%d %H:%M:%S")

        lvl = row["level"].upper() or "—"
        color = {
            "ERROR": "🔴",
            "WARNING": "🟡",
            "INFO": "🟢",
        }.get(lvl, "⚪")

        st.text(f"{color} {ts_str}  {lvl:8s}  {row['line'][:200]}")
