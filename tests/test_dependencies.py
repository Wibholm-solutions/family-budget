"""Behavior tests for auth/demo guard dependencies.

These tests document the expected redirect behavior that must be preserved
after the check_auth/is_demo_mode boilerplate is replaced with Depends().
They serve as regression protection — they pass against both the old and
new implementations.
"""


class TestRequireAuth:
    """require_auth: unauthenticated requests redirect to login."""

    def test_unauthenticated_get_redirects_to_login(self, client):
        """GET /budget/expenses without session cookie should redirect to login."""
        response = client.get("/budget/expenses", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_unauthenticated_post_redirects_to_login(self, client):
        """POST mutation without session cookie should redirect to login."""
        response = client.post(
            "/budget/expenses/add",
            data={"name": "x", "category": "y", "amount": "1", "frequency": "monthly"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_authenticated_get_passes_through(self, authenticated_client):
        """GET /budget/expenses with valid session should not redirect to login."""
        response = authenticated_client.get("/budget/expenses", follow_redirects=False)
        # 200 = page rendered; 303 = some other redirect (e.g. empty state) — both are fine
        assert response.status_code in (200, 303)
        assert response.headers.get("location", "") != "/budget/login"


class TestRequireWrite:
    """require_write: demo mode is blocked on mutation routes."""

    def test_demo_add_expense_redirects_to_expenses(self, client):
        """Demo user POSTing to add expense should redirect back to expenses page."""
        client.cookies.set("budget_session", "demo")
        response = client.post(
            "/budget/expenses/add",
            data={"name": "x", "category": "y", "amount": "1", "frequency": "monthly"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/expenses"

    def test_demo_add_account_redirects_to_accounts(self, client):
        """Demo user POSTing to add account should redirect back to accounts page."""
        client.cookies.set("budget_session", "demo")
        response = client.post(
            "/budget/accounts/add",
            data={"name": "Ny konto"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/accounts"

    def test_demo_update_income_redirects_to_dashboard(self, client):
        """Demo user POSTing income update should redirect to dashboard."""
        client.cookies.set("budget_session", "demo")
        response = client.post("/budget/income", data={}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/"

    def test_authenticated_non_demo_can_add_expense(self, authenticated_client):
        """Authenticated non-demo user should be able to post to write routes."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={"name": "Test", "category": "Bolig", "amount": "500", "frequency": "monthly"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/expenses"


class TestDemoJsonEndpointsUnchanged:
    """JSON endpoints keep explicit 401/403 checks (not replaced by Depends)."""

    def test_add_account_json_unauthenticated_returns_401(self, client):
        """add_account_json: unauthenticated → 401 JSON, not redirect."""
        response = client.post(
            "/budget/accounts/add-json",
            data={"name": "Test"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_add_account_json_demo_returns_403(self, client):
        """add_account_json: demo mode → 403 JSON, not redirect."""
        client.cookies.set("budget_session", "demo")
        response = client.post(
            "/budget/accounts/add-json",
            data={"name": "Test"},
            follow_redirects=False,
        )
        assert response.status_code == 403
        assert response.json()["success"] is False
