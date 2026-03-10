"""Integration tests for feedback, rate limiting, and amount parsing."""

import time

import pytest


class TestHelpers:
    """Tests for helper functions."""

    def test_format_currency(self):
        """format_currency should format Danish-style currency with 2 decimal places."""
        from src.api import format_currency

        assert format_currency(1000) == "1.000,00 kr"
        assert format_currency(1000000) == "1.000.000,00 kr"
        assert format_currency(0) == "0,00 kr"


class TestFeedback:
    """Tests for feedback functionality."""

    def test_feedback_page_requires_auth(self, client):
        """Feedback page should require authentication."""
        response = client.get("/budget/feedback", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_feedback_page_loads(self, authenticated_client):
        """Feedback page should load for authenticated users."""
        response = authenticated_client.get("/budget/feedback")
        assert response.status_code == 200
        assert "feedback" in response.text.lower()

    def test_feedback_submit_requires_auth(self, client):
        """Feedback submission should require authentication."""
        response = client.post(
            "/budget/feedback",
            data={
                "feedback_type": "feedback",
                "description": "This is test feedback.",
            },
            follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_feedback_submit_validates_description(self, authenticated_client):
        """Feedback should require minimum description length."""
        response = authenticated_client.post(
            "/budget/feedback",
            data={
                "feedback_type": "feedback",
                "description": "Short",
            }
        )
        assert response.status_code == 200
        assert "mindst 10 tegn" in response.text

    def test_feedback_submit_success(self, authenticated_client):
        """Valid feedback should be accepted."""
        response = authenticated_client.post(
            "/budget/feedback",
            data={
                "feedback_type": "feature",
                "description": "This is a valid feature request with enough text.",
            }
        )
        assert response.status_code == 200
        assert "Tak for din feedback" in response.text

    def test_feedback_honeypot_rejects_bots(self, authenticated_client):
        """Honeypot field should silently reject bot submissions."""
        response = authenticated_client.post(
            "/budget/feedback",
            data={
                "feedback_type": "feedback",
                "description": "This is spam from a bot.",
                "website": "http://spam.com",  # Honeypot filled = bot
            }
        )
        # Should pretend success to fool bots
        assert response.status_code == 200
        assert "Tak for din feedback" in response.text

    def test_feedback_rate_limit(self, authenticated_client):
        """Should show rate limit error after too many submissions."""
        import src.api as api_module

        # Pre-fill rate limit for testclient IP (TestClient default host)
        client_ip = "testclient"
        now = time.time()
        api_module.feedback_attempts[client_ip] = [now] * api_module.FEEDBACK_RATE_LIMIT

        response = authenticated_client.post(
            "/budget/feedback",
            data={
                "feedback_type": "feedback",
                "description": "This is a valid description with enough text.",
            }
        )
        assert response.status_code == 200
        assert "For mange henvendelser" in response.text

        # Cleanup to avoid affecting other tests
        api_module.feedback_attempts.pop(client_ip, None)

    def test_feedback_github_api_failure(self, authenticated_client, monkeypatch):
        """GitHub API errors should show a user-friendly error message."""
        import httpx

        import src.api as api_module

        monkeypatch.setattr(api_module, "GITHUB_TOKEN", "fake-token")

        async def mock_post(*args, **kwargs):
            raise httpx.ConnectError("Connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        response = authenticated_client.post(
            "/budget/feedback",
            data={
                "feedback_type": "feedback",
                "description": "This is a valid description with enough text.",
            }
        )
        assert response.status_code == 200
        assert "Kunne ikke sende feedback" in response.text

    def test_about_page_has_feedback_link(self, authenticated_client):
        """About page should have a link to feedback."""
        response = authenticated_client.get("/budget/om")
        assert response.status_code == 200
        assert "/budget/feedback" in response.text

    def test_about_page_shows_donation_section(self, authenticated_client):
        """About page should show donation buttons for authenticated users."""
        response = authenticated_client.get("/budget/om")
        assert response.status_code == 200
        assert "Køb mig en kaffe" in response.text
        assert "buy.stripe.com" in response.text
        assert "10 kr." in response.text
        assert "25 kr." in response.text
        assert "50 kr." in response.text

    def test_about_page_hides_donation_in_demo_mode(self, client):
        """About page should not show donation buttons in demo mode."""
        client.get("/budget/demo")
        response = client.get("/budget/om")
        assert response.status_code == 200
        assert "Støt projektet" not in response.text

    def test_about_page_shows_self_hosting_info(self, authenticated_client):
        """About page should show self-hosting info box."""
        response = authenticated_client.get("/budget/om")
        assert response.status_code == 200
        assert "hjemmeserver" in response.text


class TestRateLimiting:
    """Tests for rate limiting middleware."""

    def test_rate_limit_after_many_attempts(self, client, db_module):
        """Should rate limit after too many failed login attempts."""
        db_module.create_user("ratelimit", "password123")

        # Make 5 failed attempts
        for _ in range(5):
            client.post(
                "/budget/login",
                data={"username": "ratelimit", "password": "wrong"}
            )

        # 6th attempt should be rate limited
        response = client.post(
            "/budget/login",
            data={"username": "ratelimit", "password": "wrong"}
        )

        assert response.status_code == 429
        assert "for mange" in response.text.lower()


class TestAmountParsing:
    """Tests for Danish amount format parsing."""

    def test_parse_danish_amount_with_comma(self):
        """Should parse comma as decimal separator."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("1234,50") == 1234.50

    def test_parse_danish_amount_with_thousands_and_comma(self):
        """Should handle thousands separator with comma."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("1.234,50") == 1234.50
        assert parse_danish_amount("12.345,67") == 12345.67

    def test_parse_danish_amount_whole_number(self):
        """Should handle whole numbers."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("1234") == 1234.00

    def test_parse_danish_amount_single_decimal(self):
        """Should handle single decimal place."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("1234,5") == 1234.50

    def test_parse_danish_amount_with_whitespace(self):
        """Should trim whitespace."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("  1234,50  ") == 1234.50

    def test_parse_danish_amount_zero(self):
        """Should handle zero."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("0") == 0.00
        assert parse_danish_amount("0,00") == 0.00

    def test_parse_danish_amount_invalid_empty(self):
        """Should raise ValueError for empty string."""
        from src.api import parse_danish_amount
        with pytest.raises(ValueError):
            parse_danish_amount("")

    def test_parse_danish_amount_invalid_text(self):
        """Should raise ValueError for invalid text."""
        from src.api import parse_danish_amount
        with pytest.raises(ValueError):
            parse_danish_amount("abc")

    def test_parse_danish_amount_invalid_multiple_commas(self):
        """Should raise ValueError for multiple commas."""
        from src.api import parse_danish_amount
        with pytest.raises(ValueError):
            parse_danish_amount("12,34,56")


class TestCurrencyFormatting:
    """Tests for currency display formatting."""

    def test_format_currency_with_decimals(self):
        """Should format with 2 decimal places."""
        from src.api import format_currency
        assert format_currency(1234.50) == "1.234,50 kr"

    def test_format_currency_whole_number(self):
        """Should show .00 for whole numbers."""
        from src.api import format_currency
        assert format_currency(1234.0) == "1.234,00 kr"

    def test_format_currency_large_amount(self):
        """Should handle large amounts with thousands separator."""
        from src.api import format_currency
        assert format_currency(123456.78) == "123.456,78 kr"

    def test_format_currency_small_amount(self):
        """Should handle amounts less than 1 kr."""
        from src.api import format_currency
        assert format_currency(0.50) == "0,50 kr"

    def test_format_currency_zero(self):
        """Should format zero correctly."""
        from src.api import format_currency
        assert format_currency(0.00) == "0,00 kr"
