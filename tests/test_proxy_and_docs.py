"""Regression tests for reverse-proxy client identity and production docs.

Covers the two pre-publication defects found before publishing the app behind
Caddy: the login rate limiter collapsing into one global bucket, and FastAPI's
interactive docs being served publicly.
"""

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from src.client_ip import (
    DEFAULT_TRUSTED_PROXY_IPS,
    get_client_ip,
    load_trusted_proxies,
    parse_trusted_proxies,
)
from src.helpers import is_development
from src.middleware import RateLimitMiddleware

LOOPBACK = parse_trusted_proxies("127.0.0.1,::1")


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    """Minimal stand-in for a Starlette request."""

    def __init__(self, peer, headers=None):
        self.client = _FakeClient(peer) if peer else None
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}


class TestParseTrustedProxies:
    def test_default_is_loopback_only(self):
        networks = parse_trusted_proxies(DEFAULT_TRUSTED_PROXY_IPS)
        assert len(networks) == 2
        assert str(networks[0]) == "127.0.0.1/32"

    def test_empty_means_trust_nobody(self):
        assert parse_trusted_proxies("") == []
        assert parse_trusted_proxies(None) == []

    def test_accepts_cidr_ranges(self):
        networks = parse_trusted_proxies("10.0.0.0/8, 172.17.0.1")
        assert str(networks[0]) == "10.0.0.0/8"
        assert str(networks[1]) == "172.17.0.1/32"

    def test_ignores_invalid_entries(self):
        assert parse_trusted_proxies("not-an-ip, 127.0.0.1") == parse_trusted_proxies("127.0.0.1")

    def test_loaded_from_environment(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "192.168.1.5")
        assert str(load_trusted_proxies()[0]) == "192.168.1.5/32"

    def test_environment_default_is_safe(self, monkeypatch):
        monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
        assert load_trusted_proxies() == parse_trusted_proxies(DEFAULT_TRUSTED_PROXY_IPS)


class TestGetClientIp:
    def test_uses_forwarded_header_from_trusted_proxy(self):
        request = _FakeRequest("127.0.0.1", {"X-Forwarded-For": "203.0.113.7"})
        assert get_client_ip(request, LOOPBACK) == "203.0.113.7"

    def test_ignores_forwarded_header_from_untrusted_peer(self):
        """A direct caller must not be able to spoof its identity."""
        request = _FakeRequest("198.51.100.9", {"X-Forwarded-For": "203.0.113.7"})
        assert get_client_ip(request, LOOPBACK) == "198.51.100.9"

    def test_picks_closest_untrusted_hop(self):
        request = _FakeRequest(
            "127.0.0.1",
            {"X-Forwarded-For": "203.0.113.7, 198.51.100.4, 127.0.0.1"},
        )
        assert get_client_ip(request, LOOPBACK) == "198.51.100.4"

    def test_falls_back_to_peer_without_header(self):
        assert get_client_ip(_FakeRequest("127.0.0.1"), LOOPBACK) == "127.0.0.1"

    def test_falls_back_to_peer_on_garbage_header(self):
        request = _FakeRequest("127.0.0.1", {"X-Forwarded-For": "not-an-ip"})
        assert get_client_ip(request, LOOPBACK) == "127.0.0.1"

    def test_handles_missing_client(self):
        assert get_client_ip(_FakeRequest(None), LOOPBACK) == "unknown"

    def test_no_trusted_proxies_ignores_header(self):
        request = _FakeRequest("127.0.0.1", {"X-Forwarded-For": "203.0.113.7"})
        assert get_client_ip(request, []) == "127.0.0.1"

    def test_strips_port_from_forwarded_address(self):
        request = _FakeRequest("127.0.0.1", {"X-Forwarded-For": "203.0.113.7:51234"})
        assert get_client_ip(request, LOOPBACK) == "203.0.113.7"


def _proxied_app(trusted_proxies):
    """A tiny app with the real middleware, reachable as if through a proxy."""
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        max_attempts=5,
        window_seconds=300,
        trusted_proxies=trusted_proxies,
    )

    @app.post("/budget/login")
    async def login():
        return PlainTextResponse("ok")

    # Present ourselves as connecting from a loopback proxy hop.
    return TestClient(app, client=("127.0.0.1", 50000))


class TestRateLimitBehindProxy:
    """The client connects from 127.0.0.1, simulating a Caddy proxy hop."""

    def test_two_clients_have_separate_buckets(self):
        client = _proxied_app(parse_trusted_proxies("127.0.0.1"))

        for _ in range(5):
            assert client.post("/budget/login", headers={"X-Forwarded-For": "203.0.113.7"}).status_code == 200

        # First client is now exhausted...
        blocked = client.post("/budget/login", headers={"X-Forwarded-For": "203.0.113.7"})
        assert blocked.status_code == 429
        assert "For mange login forsøg" in blocked.text

        # ...but a different real client must still be able to log in.
        other = client.post("/budget/login", headers={"X-Forwarded-For": "198.51.100.4"})
        assert other.status_code == 200

    def test_spoofed_header_cannot_rotate_identity(self):
        """From an untrusted peer the header is ignored, so the limit holds."""
        client = _proxied_app(parse_trusted_proxies("10.99.99.99"))

        for i in range(5):
            response = client.post("/budget/login", headers={"X-Forwarded-For": f"203.0.113.{i}"})
            assert response.status_code == 200

        blocked = client.post("/budget/login", headers={"X-Forwarded-For": "203.0.113.200"})
        assert blocked.status_code == 429


class TestDocsDisabledInProduction:
    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
    def test_docs_routes_absent(self, client, path):
        """The app under test uses the production default (docs disabled)."""
        assert client.get(path).status_code == 404

    def test_app_has_no_docs_urls_configured(self):
        from src.api import app
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.openapi_url is None

    def test_environment_defaults_to_production(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        assert is_development() is False

    def test_production_value_is_not_development(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert is_development() is False

    @pytest.mark.parametrize("value", ["development", "dev", "local", "DEVELOPMENT"])
    def test_development_values_enable_docs(self, monkeypatch, value):
        monkeypatch.setenv("ENVIRONMENT", value)
        assert is_development() is True
