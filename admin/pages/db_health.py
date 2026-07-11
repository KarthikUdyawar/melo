"""DB Health page — PostgreSQL and Redis metrics from exporters."""

# admin/pages/db_health.py
import requests
import streamlit as st

PROMETHEUS_URL = "http://prometheus:9090"


def _query(expr: str) -> str:
    """Return scalar string result of a Prometheus instant query."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": expr},
            timeout=5,
        )
        response.raise_for_status()

        result = response.json().get("data", {}).get("result", [])
        if not result:
            return "—"

        raw = str(result[0]["value"][1])

        try:
            return f"{float(raw):.2f}"
        except ValueError:
            return raw

    except requests.RequestException:
        return "—"


st.header("DB Health")

pg_col, redis_col = st.columns(2)

# ── PostgreSQL ────────────────────────────────────────────────────────────────
with pg_col:
    st.subheader("PostgreSQL")
    pg_metrics = {
        "Active connections": "pg_stat_activity_count",
        "Max connections": "pg_settings_max_connections",
        "Dead tuples (all tables)": "sum(pg_stat_user_tables_n_dead_tup)",
        "Cache hit ratio": (
            "sum(pg_stat_database_blks_hit) / "
            "(sum(pg_stat_database_blks_hit) + sum(pg_stat_database_blks_read) + 1)"
        ),
        "Transactions/s (5m)": "rate(pg_stat_database_xact_commit[5m])",
    }
    rows = [{"metric": k, "value": _query(v)} for k, v in pg_metrics.items()]
    st.dataframe(rows, use_container_width=True)

# ── Redis ─────────────────────────────────────────────────────────────────────
with redis_col:
    st.subheader("Redis")
    redis_metrics = {
        "Memory used (bytes)": "redis_memory_used_bytes",
        "Connected clients": "redis_connected_clients",
        "Keyspace hits": "redis_keyspace_hits_total",
        "Keyspace misses": "redis_keyspace_misses_total",
        "Evicted keys": "redis_evicted_keys_total",
        "Hit ratio": (
            "redis_keyspace_hits_total / "
            "(redis_keyspace_hits_total + redis_keyspace_misses_total + 1)"
        ),
    }
    rows = [{"metric": k, "value": _query(v)} for k, v in redis_metrics.items()]
    st.dataframe(rows, use_container_width=True)
