"""Tests for /budget/health endpoint."""

from unittest.mock import patch


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_ok_with_db_status(self, client):
        """Health endpoint should return 200 with database status."""
        response = client.get("/budget/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"

    def test_health_returns_503_when_db_unavailable(self, client):
        """Health endpoint should return 503 when database is unreachable."""
        with patch("src.routes.api_endpoints.db.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("DB unavailable")
            response = client.get("/budget/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "error"
        assert "detail" in data
