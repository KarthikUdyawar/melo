"""Unit tests for OBS-3 tracing."""

# tests/unit/test_tracing.py
import pytest


@pytest.fixture(autouse=True)
def reset_tracing():
    import app.core.tracing as t

    t._CONFIGURED = False
    yield
    t._CONFIGURED = False


def test_extract_trace_id_returns_unknown_without_active_span():
    from app.core.tracing import configure_tracing, extract_trace_id

    configure_tracing("melo.test")
    assert extract_trace_id() == "unknown"


def test_extract_trace_id_returns_hex_string_with_active_span():
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("test")

    with tracer.start_as_current_span("test-span"):
        from app.core.tracing import extract_trace_id

        tid = extract_trace_id()

    assert tid != "unknown"
    assert len(tid) == 32
    assert all(c in "0123456789abcdef" for c in tid)


def test_configure_tracing_is_idempotent():
    from app.core.tracing import configure_tracing

    configure_tracing("melo.test")
    configure_tracing("melo.test")  # second call — no error, no double-register


def test_celery_task_headers_contain_traceparent_after_inject():
    """_inject_trace_context_into_task injects traceparent into headers."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("test")

    captured_headers: list[dict] = []

    class FakeTask:
        def apply_async(self, args, headers):
            captured_headers.append(headers)

        def delay(self, *args):
            captured_headers.append({})

    with tracer.start_as_current_span("enqueue-span"):
        from app.api.songs import _inject_trace_context_into_task

        _inject_trace_context_into_task(FakeTask(), "song-id", "http://yt.com")

    assert len(captured_headers) == 1
    assert "traceparent" in captured_headers[0]
