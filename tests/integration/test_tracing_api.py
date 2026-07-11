"""Integration tests for OBS-3 — X-Trace-Id header on every response."""

# tests/integration/test_tracing_api.py
import re

from fastapi.testclient import TestClient

_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


def test_x_trace_id_present_on_get_songs(client: TestClient) -> None:
    resp = client.get("/songs")
    assert "x-trace-id" in resp.headers or "X-Trace-Id" in resp.headers


def test_x_trace_id_is_string_on_get_songs(client: TestClient) -> None:
    resp = client.get("/songs")
    value = resp.headers.get("x-trace-id") or resp.headers.get("X-Trace-Id")
    assert isinstance(value, str)
    assert len(value) > 0


def test_x_trace_id_present_on_post_playlists(client: TestClient) -> None:
    resp = client.post("/playlists", json={"name": "trace-test"})
    assert "x-trace-id" in resp.headers or "X-Trace-Id" in resp.headers


def test_x_trace_id_present_on_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert "x-trace-id" in resp.headers or "X-Trace-Id" in resp.headers


def test_x_trace_id_value_is_unknown_or_hex(client: TestClient) -> None:
    """Value is either 'unknown' (no active span in test) or 32-char hex."""
    resp = client.get("/songs")
    value = resp.headers.get("x-trace-id") or resp.headers.get("X-Trace-Id", "")
    assert value == "unknown" or _HEX_RE.match(value), f"bad trace id: {value!r}"
