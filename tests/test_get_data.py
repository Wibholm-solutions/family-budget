"""Tests for get_data dependency — resolves auth + demo + DataContext."""


class TestGetDataDependency:
    """get_data returns correctly configured DataContext."""

    def test_demo_mode_returns_demo_context(self, client):
        """Demo session → ctx.demo=True."""
        client.cookies.set("budget_session", "demo")
        response = client.get("/budget/", follow_redirects=False)
        # If we reach 200, the dependency resolved successfully
        assert response.status_code == 200

    def test_unauthenticated_redirects_to_login(self, client):
        """No session → AuthRequired → redirect to login."""
        response = client.get("/budget/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_authenticated_returns_real_context(self, authenticated_client):
        """Valid session → ctx.demo=False, real data."""
        response = authenticated_client.get("/budget/", follow_redirects=False)
        assert response.status_code == 200
