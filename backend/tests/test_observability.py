"""Smoke tests for D11 observability surface: middleware, /healthz, /metrics."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_returns_ok_with_db(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "version" in body


def test_readyz_returns_ok(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"ready": True}


def test_request_id_header_set_on_response(client: TestClient) -> None:
    r = client.get("/healthz")
    assert "x-request-id" in {k.lower() for k in r.headers}
    rid = r.headers["x-request-id"]
    assert rid and len(rid) >= 8


def test_request_id_propagated_when_supplied(client: TestClient) -> None:
    given = "test-rid-abcdef"
    r = client.get("/healthz", headers={"X-Request-ID": given})
    assert r.headers.get("x-request-id") == given


def test_metrics_endpoint_returns_prom_text(client: TestClient) -> None:
    # Hit a few routes so counters have non-zero values.
    client.get("/healthz")
    client.get("/api/painpoints/top?limit=1")
    client.get("/does-not-exist")

    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "demandradar_http_requests_total" in body
    assert "demandradar_http_request_duration_seconds" in body
    # The bucket family is always emitted by the Histogram type.
    assert "demandradar_http_request_duration_seconds_bucket" in body


def test_metrics_disabled_returns_404(monkeypatch, client: TestClient) -> None:  # type: ignore[no-untyped-def]
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "metrics_enabled", False, raising=False)
    r = client.get("/metrics")
    assert r.status_code == 404


def test_json_logging_sink_serialises(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Ensure the JSON sink emits a valid one-line JSON object containing
    the bound contextual fields."""
    import io
    import json
    import sys

    from app.core.logging import _json_sink, logger

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)

    sink_id = logger.add(_json_sink, level="INFO", format="{message}")
    try:
        logger.bind(request_id="rid123", method="GET", path="/x").info("hello")
    finally:
        logger.remove(sink_id)

    line = buf.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["msg"] == "hello"
    assert payload["request_id"] == "rid123"
    assert payload["method"] == "GET"
    assert payload["path"] == "/x"
    assert payload["level"] == "INFO"
