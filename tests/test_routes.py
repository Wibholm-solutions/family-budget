"""Integration tests for general routes and dashboard."""


class TestProtectedEndpoints:
    """Tests for endpoint authentication requirements."""

    def test_dashboard_requires_auth(self, client):
        """Dashboard should redirect to login without auth."""
        response = client.get("/budget/", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_income_requires_auth(self, client):
        """Income page should redirect to login without auth."""
        response = client.get("/budget/income", follow_redirects=False)

        assert response.status_code == 303

    def test_expenses_requires_auth(self, client):
        """Expenses page should redirect to login without auth."""
        response = client.get("/budget/expenses", follow_redirects=False)

        assert response.status_code == 303

    def test_categories_requires_auth(self, client):
        """Categories page should redirect to login without auth."""
        response = client.get("/budget/categories", follow_redirects=False)

        assert response.status_code == 303

    def test_about_accessible_without_auth(self, client):
        """About page should be accessible without auth."""
        response = client.get("/budget/om", follow_redirects=False)

        assert response.status_code == 200

    def test_help_redirects_to_about(self, client):
        """Old help URL should redirect to about page."""
        response = client.get("/budget/help", follow_redirects=False)

        assert response.status_code == 301
        assert response.headers["location"] == "/budget/om"


class TestPrivacyPolicy:
    """Tests for privacy policy page."""

    def test_privacy_accessible_without_auth(self, client):
        """Privacy page should be accessible without authentication."""
        response = client.get("/budget/privacy")

        assert response.status_code == 200

    def test_privacy_contains_required_sections(self, client):
        """Privacy page should contain required GDPR information."""
        response = client.get("/budget/privacy")

        # Required sections for GDPR compliance
        assert "privatlivspolitik" in response.text.lower()
        assert "data" in response.text.lower()
        assert "cookies" in response.text.lower()
        assert "rettigheder" in response.text.lower()
        assert "kontakt" in response.text.lower()

    def test_privacy_accessible_when_authenticated(self, authenticated_client):
        """Privacy page should also be accessible when logged in."""
        response = authenticated_client.get("/budget/privacy")

        assert response.status_code == 200


class TestOmPage:
    """Tests for the Om page."""

    def test_om_page_has_install_button(self, authenticated_client):
        """Om page should have install guide trigger."""
        response = authenticated_client.get("/budget/om")
        assert response.status_code == 200
        assert 'openInstallGuide()' in response.text
        assert 'Installer som app' in response.text


class TestDashboard:
    """Tests for dashboard functionality."""

    def test_dashboard_accessible_when_authenticated(self, authenticated_client):
        """Dashboard should be accessible when logged in."""
        response = authenticated_client.get("/budget/")

        assert response.status_code == 200

    def test_dashboard_shows_budget_info(self, authenticated_client):
        """Dashboard should display budget information."""
        response = authenticated_client.get("/budget/")

        # Should contain budget-related content
        assert "budget" in response.text.lower() or "overblik" in response.text.lower()

    def test_demo_mode_shows_demo_data(self, client):
        """Demo mode should show demo data."""
        # Enter demo mode
        client.get("/budget/demo")

        response = client.get("/budget/")

        assert response.status_code == 200
        # Demo mode indicator or demo data should be present
        assert "demo" in response.text.lower() or "Person 1" in response.text

    def test_dashboard_has_sortable_sections(self, authenticated_client):
        """Dashboard should have sortable sections container with all section IDs."""
        response = authenticated_client.get("/budget/")

        assert 'id="sortable-sections"' in response.text
        assert 'data-section-id="expenses-breakdown"' in response.text
        assert 'data-section-id="transfer-summary"' in response.text
        assert 'data-section-id="income-breakdown"' in response.text
        assert 'data-section-id="category-chart"' in response.text

    def test_dashboard_has_drag_handles(self, authenticated_client):
        """Dashboard should have drag handles for sortable sections."""
        response = authenticated_client.get("/budget/")

        assert 'drag-handle' in response.text

    def test_demo_dashboard_has_sortable_sections(self, client):
        """Demo mode dashboard should also have sortable sections."""
        # Set demo cookie directly (secure=True prevents TestClient from persisting it via redirect)
        client.cookies.set("budget_session", "demo")

        response = client.get("/budget/")

        assert response.status_code == 200
        assert 'id="sortable-sections"' in response.text
        assert 'data-section-id="expenses-breakdown"' in response.text
        assert 'data-section-id="income-breakdown"' in response.text
        assert 'data-section-id="category-chart"' in response.text


class TestIncomeEndpoints:
    """Tests for income management endpoints."""

    def test_income_page_loads(self, authenticated_client):
        """Income page should load for authenticated users."""
        response = authenticated_client.get("/budget/income")

        assert response.status_code == 200

    def test_update_income(self, authenticated_client):
        """POST to income should update values."""
        response = authenticated_client.post(
            "/budget/income",
            data={
                "income_name_0": "Alice",
                "income_amount_0": "35000",
                "income_frequency_0": "monthly",
                "income_name_1": "Bob",
                "income_amount_1": "28000",
                "income_frequency_1": "monthly"
            },
            follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/budget/"

    def test_update_income_with_frequency(self, authenticated_client, db_module):
        """POST to income with different frequencies should save correctly."""
        response = authenticated_client.post(
            "/budget/income",
            data={
                "income_name_0": "Monthly Salary",
                "income_amount_0": "30000",
                "income_frequency_0": "monthly",
                "income_name_1": "Quarterly Bonus",
                "income_amount_1": "9000",
                "income_frequency_1": "quarterly",
                "income_name_2": "Annual Bonus",
                "income_amount_2": "24000",
                "income_frequency_2": "yearly"
            },
            follow_redirects=False
        )

        assert response.status_code == 303
        # Verify income was saved with correct frequencies
        user_id = authenticated_client.user_id
        incomes = db_module.get_all_income(user_id)

        monthly = next((i for i in incomes if i.person == "Monthly Salary"), None)
        quarterly = next((i for i in incomes if i.person == "Quarterly Bonus"), None)
        yearly = next((i for i in incomes if i.person == "Annual Bonus"), None)

        assert monthly is not None and monthly.frequency == "monthly"
        assert quarterly is not None and quarterly.frequency == "quarterly"
        assert quarterly.monthly_amount == 3000  # 9000 / 3
        assert yearly is not None and yearly.frequency == "yearly"
        assert yearly.monthly_amount == 2000  # 24000 / 12

    def test_update_income_semiannual(self, authenticated_client, db_module):
        """POST to income with semi-annual frequency should work."""
        response = authenticated_client.post(
            "/budget/income",
            data={
                "income_name_0": "Semi-Annual Payment",
                "income_amount_0": "12000",
                "income_frequency_0": "semi-annual"
            },
            follow_redirects=False
        )

        assert response.status_code == 303
        user_id = authenticated_client.user_id
        incomes = db_module.get_all_income(user_id)
        semiannual = next((i for i in incomes if i.person == "Semi-Annual Payment"), None)

        assert semiannual is not None
        assert semiannual.frequency == "semi-annual"
        assert semiannual.monthly_amount == 2000  # 12000 / 6
