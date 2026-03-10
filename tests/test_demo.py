"""Integration tests for demo mode and decimal expense handling."""


class TestExpensesWithDecimals:
    """Tests for decimal amounts in expenses."""

    def test_add_expense_with_decimals(self, authenticated_client, db_module):
        """Should accept decimal amounts in Danish format."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Test Expense",
                "category": "Bolig",
                "amount": "1234,50",
                "frequency": "monthly"
            },
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_add_expense_with_thousands_separator(self, authenticated_client, db_module):
        """Should accept thousands separator."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Expensive Item",
                "category": "Bolig",
                "amount": "12.345,67",
                "frequency": "monthly"
            },
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_add_expense_rejects_invalid_format(self, authenticated_client, db_module):
        """Should reject invalid amount format."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Test",
                "category": "Bolig",
                "amount": "abc",
                "frequency": "monthly"
            }
        )
        assert response.status_code == 400

    def test_add_expense_rejects_negative_amount(self, authenticated_client, db_module):
        """Should reject negative amounts."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Test",
                "category": "Bolig",
                "amount": "-100,00",
                "frequency": "monthly"
            }
        )
        assert response.status_code == 400

    def test_edit_expense_with_decimals(self, authenticated_client, db_module):
        """Should accept decimal amounts when editing."""
        # First create an expense
        authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Test Expense",
                "category": "Bolig",
                "amount": "1000,00",
                "frequency": "monthly"
            }
        )
        # Get the expense ID from the database
        from src.database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM expenses ORDER BY id DESC LIMIT 1")
        expense_id = cur.fetchone()[0]
        conn.close()

        # Now edit it
        response = authenticated_client.post(
            f"/budget/expenses/{expense_id}/edit",
            data={
                "name": "Updated Expense",
                "category": "Bolig",
                "amount": "1234,56",
                "frequency": "monthly"
            },
            follow_redirects=False
        )
        assert response.status_code == 303


class TestAdvancedDemoData:
    """Tests for advanced demo data functions."""

    def test_advanced_expenses_have_accounts(self, db_module):
        """Advanced demo expenses should all have account assignments."""
        expenses = db_module.get_demo_expenses(advanced=True)
        for exp in expenses:
            assert exp.account is not None, f"Expense '{exp.name}' missing account"

    def test_advanced_income_has_extra_source(self, db_module):
        """Advanced demo income should have more sources than simple."""
        simple = db_module.get_demo_income(advanced=False)
        advanced = db_module.get_demo_income(advanced=True)
        assert len(advanced) > len(simple)

    def test_simple_expenses_have_no_accounts(self, db_module):
        """Simple demo expenses should have no account assignments."""
        expenses = db_module.get_demo_expenses(advanced=False)
        for exp in expenses:
            assert exp.account is None

    def test_advanced_account_totals_not_empty(self, db_module):
        """Advanced demo should return account totals."""
        totals = db_module.get_demo_account_totals(advanced=True)
        assert len(totals) > 0

    def test_simple_account_totals_empty(self, db_module):
        """Simple demo should return empty account totals."""
        totals = db_module.get_demo_account_totals(advanced=False)
        assert len(totals) == 0


class TestDemoToggle:
    """Tests for demo simple/advanced toggle."""

    def test_is_demo_advanced_defaults_to_false(self, client):
        """Demo mode should default to simple (not advanced)."""
        client.cookies.set("budget_session", "demo")
        response = client.get("/budget/")
        # Should not have account totals in simple mode
        assert "Budgetkonto" not in response.text

    def test_toggle_sets_advanced_cookie(self, client):
        """Toggle endpoint should set demo_level=advanced cookie."""
        client.cookies.set("budget_session", "demo")
        response = client.get("/budget/demo/toggle", follow_redirects=False)
        assert response.status_code == 303
        assert response.cookies.get("demo_level") == "advanced"

    def test_toggle_flips_back_to_simple(self, client):
        """Toggle should flip advanced back to simple."""
        client.cookies.set("budget_session", "demo")
        client.cookies.set("demo_level", "advanced")
        response = client.get("/budget/demo/toggle", follow_redirects=False)
        assert response.status_code == 303
        assert response.cookies.get("demo_level") == "simple"

    def test_toggle_requires_demo_mode(self, client):
        """Toggle should redirect to login if not in demo mode."""
        response = client.get("/budget/demo/toggle", follow_redirects=False)
        assert response.status_code == 303
        assert "/budget/login" in response.headers["location"]


class TestAdvancedDemoRoutes:
    """Tests that advanced mode shows richer data on all routes."""

    def test_dashboard_advanced_shows_accounts(self, client):
        """Dashboard in advanced mode should show account totals."""
        client.cookies.set("budget_session", "demo")
        client.cookies.set("demo_level", "advanced")
        response = client.get("/budget/")
        assert "Budgetkonto" in response.text

    def test_dashboard_simple_hides_accounts(self, client):
        """Dashboard in simple mode should not show accounts."""
        client.cookies.set("budget_session", "demo")
        response = client.get("/budget/")
        assert "Budgetkonto" not in response.text

    def test_expenses_advanced_shows_accounts(self, client):
        """Expenses page in advanced mode should show account list."""
        client.cookies.set("budget_session", "demo")
        client.cookies.set("demo_level", "advanced")
        response = client.get("/budget/expenses")
        assert "Budgetkonto" in response.text

    def test_income_advanced_shows_extra_source(self, client):
        """Income page in advanced mode should show Børnepenge as a value."""
        client.cookies.set("budget_session", "demo")
        client.cookies.set("demo_level", "advanced")
        response = client.get("/budget/income")
        # Check it appears as a form value, not just a placeholder
        assert 'value="Børnepenge"' in response.text

    def test_income_simple_no_extra_source(self, client):
        """Income page in simple mode should not have Børnepenge as a value."""
        client.cookies.set("budget_session", "demo")
        response = client.get("/budget/income")
        assert 'value="Børnepenge"' not in response.text

    def test_chart_data_advanced_has_higher_income(self, client):
        """Chart API in advanced mode should have higher total income."""
        client.cookies.set("budget_session", "demo")
        # Simple mode
        simple_resp = client.get("/budget/api/chart-data")
        simple_data = simple_resp.json()
        # Advanced mode
        client.cookies.set("demo_level", "advanced")
        adv_resp = client.get("/budget/api/chart-data")
        adv_data = adv_resp.json()
        assert adv_data["total_income"] > simple_data["total_income"]
