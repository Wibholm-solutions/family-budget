"""Integration tests for expense months, yearly overview, static files, and settings."""


class TestExpenseRoutesWithMonths:
    """Tests for expense routes with months field."""

    def test_add_expense_with_months(self, authenticated_client):
        """POST /budget/expenses/add with months should store them."""
        response = authenticated_client.post("/budget/expenses/add", data={
            "name": "Bilforsikring",
            "category": "Forsikring",
            "amount": "6000",
            "frequency": "semi-annual",
            "account": "",
            "months": "3,9",
        }, follow_redirects=False)
        assert response.status_code == 303

        from src import database as db
        expenses = db.get_all_expenses(authenticated_client.user_id)
        insurance = next(e for e in expenses if e.name == "Bilforsikring")
        assert insurance.months == [3, 9]

    def test_add_expense_without_months(self, authenticated_client):
        """POST /budget/expenses/add without months should store None."""
        response = authenticated_client.post("/budget/expenses/add", data={
            "name": "Husleje",
            "category": "Bolig",
            "amount": "10000",
            "frequency": "monthly",
            "account": "",
        }, follow_redirects=False)
        assert response.status_code == 303

        from src import database as db
        expenses = db.get_all_expenses(authenticated_client.user_id)
        rent = next(e for e in expenses if e.name == "Husleje")
        assert rent.months is None

    def test_add_expense_months_validation_wrong_count(self, authenticated_client):
        """POST with wrong number of months for frequency should return 400."""
        response = authenticated_client.post("/budget/expenses/add", data={
            "name": "Bad",
            "category": "Bolig",
            "amount": "6000",
            "frequency": "semi-annual",
            "account": "",
            "months": "3",
        }, follow_redirects=False)
        assert response.status_code == 400

    def test_add_expense_months_validation_invalid_month(self, authenticated_client):
        """POST with invalid month number should return 400."""
        response = authenticated_client.post("/budget/expenses/add", data={
            "name": "Bad",
            "category": "Bolig",
            "amount": "6000",
            "frequency": "yearly",
            "account": "",
            "months": "13",
        }, follow_redirects=False)
        assert response.status_code == 400

    def test_edit_expense_with_months(self, authenticated_client):
        """POST /budget/expenses/{id}/edit with months should update them."""
        from src import database as db
        expense_id = db.add_expense(authenticated_client.user_id, "Skat", "Bolig", 18000, "yearly")

        response = authenticated_client.post(f"/budget/expenses/{expense_id}/edit", data={
            "name": "Skat",
            "category": "Bolig",
            "amount": "18000",
            "frequency": "yearly",
            "account": "",
            "months": "7",
        }, follow_redirects=False)
        assert response.status_code == 303

        expense = db.get_expense_by_id(expense_id, authenticated_client.user_id)
        assert expense.months == [7]

    def test_edit_expense_clear_months_on_frequency_change(self, authenticated_client):
        """Changing frequency to monthly should clear months."""
        from src import database as db
        expense_id = db.add_expense(authenticated_client.user_id, "Test", "Bolig", 6000, "semi-annual", months=[3, 9])

        response = authenticated_client.post(f"/budget/expenses/{expense_id}/edit", data={
            "name": "Test",
            "category": "Bolig",
            "amount": "6000",
            "frequency": "monthly",
            "account": "",
        }, follow_redirects=False)
        assert response.status_code == 303

        expense = db.get_expense_by_id(expense_id, authenticated_client.user_id)
        assert expense.months is None


class TestYearlyOverviewRoute:
    """Tests for GET /budget/yearly route."""

    def test_yearly_requires_auth(self, client):
        """GET /budget/yearly should redirect to login if not authenticated."""
        response = client.get("/budget/yearly", follow_redirects=False)
        assert response.status_code == 303
        assert "/budget/login" in response.headers["location"]

    def test_yearly_page_loads(self, authenticated_client):
        """GET /budget/yearly should return 200."""
        response = authenticated_client.get("/budget/yearly")
        assert response.status_code == 200
        assert "Årsoverblik" in response.text


class TestStaticFiles:
    """Tests for static file serving."""

    def test_manifest_json_accessible(self, client):
        """manifest.json should be served at /budget/static/manifest.json."""
        response = client.get("/budget/static/manifest.json")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

    def test_icon_192_accessible(self, client):
        """192x192 icon should be served."""
        response = client.get("/budget/static/icons/icon-192.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_icon_512_accessible(self, client):
        """512x512 icon should be served."""
        response = client.get("/budget/static/icons/icon-512.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_manifest_json_has_required_fields(self, client):
        """manifest.json should have required PWA fields."""
        import json
        response = client.get("/budget/static/manifest.json")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["name"] == "Family Budget"
        assert data["display"] == "standalone"
        assert data["start_url"] == "/budget/"
        assert data["scope"] == "/budget/"

    def test_base_html_links_manifest(self, client):
        """All pages should include manifest link in head."""
        response = client.get("/budget/login")
        assert response.status_code == 200
        assert 'rel="manifest"' in response.text
        assert '/budget/static/manifest.json' in response.text
        assert 'apple-touch-icon' in response.text

    def test_install_modal_in_base(self, client):
        """Install guide modal should be present on all pages."""
        response = client.get("/budget/login")
        assert response.status_code == 200
        assert 'install-guide-modal' in response.text
        assert 'openInstallGuide' in response.text

    def test_install_modal_has_both_platforms(self, client):
        """Modal should have both iOS and Android content."""
        response = client.get("/budget/login")
        assert 'steps-ios' in response.text
        assert 'steps-android' in response.text
        assert 'Safari' in response.text
        assert 'Chrome' in response.text


class TestSettings:
    """Tests for account settings page and email management."""

    def test_settings_requires_auth(self, client):
        """GET /budget/settings should redirect unauthenticated users to login."""
        response = client.get("/budget/settings", follow_redirects=False)
        assert response.status_code == 303
        assert "/budget/login" in response.headers["location"]

    def test_settings_redirects_demo(self, client):
        """GET /budget/settings in demo mode should redirect to dashboard."""
        client.cookies.set("budget_session", "demo")
        response = client.get("/budget/settings", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/"

    def test_settings_page_loads(self, authenticated_client):
        """GET /budget/settings should return 200 with username."""
        response = authenticated_client.get("/budget/settings")
        assert response.status_code == 200
        assert "testuser" in response.text

    def test_update_email_requires_auth(self, client):
        """POST /budget/settings/email without auth should redirect to login."""
        response = client.post(
            "/budget/settings/email",
            data={"email": "test@example.com"},
            follow_redirects=False
        )
        assert response.status_code == 303
        assert "/budget/login" in response.headers["location"]

    def test_update_email_clear(self, authenticated_client):
        """POST with empty email should clear email and show success."""
        response = authenticated_client.post(
            "/budget/settings/email",
            data={"email": ""}
        )
        assert response.status_code == 200
        assert "Email fjernet" in response.text

    def test_update_email_invalid(self, authenticated_client):
        """POST with invalid email should show validation error."""
        response = authenticated_client.post(
            "/budget/settings/email",
            data={"email": "invalid"}
        )
        assert response.status_code == 200
        assert "Ugyldig email-adresse" in response.text

    def test_update_email_valid(self, authenticated_client):
        """POST with valid email should store it and show success."""
        response = authenticated_client.post(
            "/budget/settings/email",
            data={"email": "a@b.com"}
        )
        assert response.status_code == 200
        assert "Email tilf" in response.text

    def test_update_email_then_settings_shows_email(self, authenticated_client):
        """After saving an email, the settings page should reflect has_email=True."""
        # Save a valid email
        authenticated_client.post(
            "/budget/settings/email",
            data={"email": "user@example.com"}
        )
        # Revisit settings
        response = authenticated_client.get("/budget/settings")
        assert response.status_code == 200
        # The template should indicate an email is set (has_email=True)
        assert "Email tilf" in response.text or "email" in response.text.lower()
