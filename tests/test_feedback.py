"""Integration tests for feedback and rate limiting."""

import time


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

    def test_feedback_submit_success(self, authenticated_client, monkeypatch):
        """Valid feedback should be accepted."""
        import httpx

        import src.routes.pages as pages_module

        monkeypatch.setattr(pages_module, "FEEDBACK_API_URL", "http://fake-feedback-api:3000")

        async def mock_post(*args, **kwargs):
            class MockResponse:
                status_code = 201
                def json(self_inner):
                    return {"message": "Feedback received", "issue_url": "https://github.com/test/issues/1"}
            return MockResponse()

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

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
        import src.routes.pages as pages_module

        # Pre-fill rate limit for testclient IP (TestClient default host)
        client_ip = "testclient"
        now = time.time()
        pages_module.feedback_attempts[client_ip] = [now] * pages_module.FEEDBACK_RATE_LIMIT

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
        pages_module.feedback_attempts.pop(client_ip, None)

    def test_feedback_calls_feedback_api(self, authenticated_client, monkeypatch):
        """Feedback should POST to feedback-api instead of GitHub directly."""
        import httpx

        import src.routes.pages as pages_module

        monkeypatch.setattr(pages_module, "FEEDBACK_API_URL", "http://fake-feedback-api:3000")

        captured = {}

        async def mock_post(*args, **kwargs):
            captured["url"] = str(args[1])
            captured["json"] = kwargs.get("json")

            class MockResponse:
                status_code = 201
                def json(self_inner):
                    return {"message": "Feedback received", "issue_url": "https://github.com/test/issues/1"}
            return MockResponse()

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        response = authenticated_client.post(
            "/budget/feedback",
            data={
                "feedback_type": "feature",
                "description": "This is a valid feature request with enough text.",
            }
        )
        assert response.status_code == 200
        assert "Tak for din feedback" in response.text
        assert captured["url"] == "http://fake-feedback-api:3000/api/feedback"
        assert captured["json"]["repo"] == pages_module.GITHUB_REPO
        assert captured["json"]["type"] == "feature"
        assert captured["json"]["title"].startswith("Feature request:")

    def test_feedback_api_failure(self, authenticated_client, monkeypatch):
        """feedback-api errors should show a user-friendly error message."""
        import httpx

        import src.routes.pages as pages_module

        monkeypatch.setattr(pages_module, "FEEDBACK_API_URL", "http://fake-feedback-api:3000")

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
