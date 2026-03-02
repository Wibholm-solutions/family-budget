"""Tests for chart data API endpoint."""



class TestChartDataEndpoint:
    """Tests for /budget/api/chart-data endpoint."""

    def test_chart_data_requires_auth(self, client):
        """Chart data endpoint should require authentication."""
        response = client.get("/budget/api/chart-data", follow_redirects=False)
        assert response.status_code == 303  # Redirect to login

    def test_chart_data_returns_json(self, authenticated_client):
        """Endpoint should return valid JSON."""
        response = authenticated_client.get("/budget/api/chart-data")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_chart_data_has_required_fields(self, authenticated_client):
        """Response should include all required fields."""
        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        assert "category_totals" in data
        assert "total_income" in data
        assert "total_expenses" in data
        assert "top_expenses" in data

        assert isinstance(data["category_totals"], dict)
        assert isinstance(data["total_income"], (int, float))
        assert isinstance(data["total_expenses"], (int, float))
        assert isinstance(data["top_expenses"], list)

    def test_chart_data_empty_user_returns_zeros(self, authenticated_client):
        """New user with no data should return zero values."""
        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        assert data["total_income"] == 0
        assert data["total_expenses"] == 0
        assert data["category_totals"] == {}
        assert data["top_expenses"] == []

    def test_chart_data_with_expenses(self, authenticated_client, db_module):
        """Endpoint should return correct monthly amounts."""
        user_id = authenticated_client.user_id

        # Add some test expenses
        db_module.add_expense(user_id, "Rent", "Bolig", 12000, "monthly")
        db_module.add_expense(user_id, "Car", "Transport", 6000, "yearly")

        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        # Should return monthly equivalents
        assert data["category_totals"]["Bolig"] == 12000
        assert data["category_totals"]["Transport"] == 500  # 6000/12
        assert data["total_expenses"] == 12500

    def test_chart_data_with_income(self, authenticated_client, db_module):
        """Endpoint should return correct income total."""
        user_id = authenticated_client.user_id

        # Add income sources
        db_module.add_income(user_id, "Salary", 30000, "monthly")
        db_module.add_income(user_id, "Bonus", 12000, "yearly")

        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        # Should return monthly equivalents
        assert data["total_income"] == 31000  # 30000 + 12000/12

    def test_chart_data_top_expenses_sorted(self, authenticated_client, db_module):
        """Top expenses should be sorted by monthly amount descending."""
        user_id = authenticated_client.user_id

        db_module.add_expense(user_id, "Small", "Andet", 100, "monthly")
        db_module.add_expense(user_id, "Large", "Bolig", 10000, "monthly")
        db_module.add_expense(user_id, "Medium", "Transport", 5000, "monthly")

        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        assert len(data["top_expenses"]) >= 3
        assert data["top_expenses"][0]["name"] == "Large"
        assert data["top_expenses"][1]["name"] == "Medium"
        assert data["top_expenses"][2]["name"] == "Small"

    def test_chart_data_top_expenses_limit(self, authenticated_client, db_module):
        """Top expenses should be limited to 5 items."""
        user_id = authenticated_client.user_id

        for i in range(10):
            db_module.add_expense(user_id, f"Expense {i}", "Andet", 100 * (i + 1), "monthly")

        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        assert len(data["top_expenses"]) == 5

    def test_chart_data_top_expenses_structure(self, authenticated_client, db_module):
        """Top expenses should have correct structure."""
        user_id = authenticated_client.user_id

        db_module.add_expense(user_id, "Test Expense", "Bolig", 5000, "monthly")

        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        assert len(data["top_expenses"]) == 1
        expense = data["top_expenses"][0]
        assert expense["name"] == "Test Expense"
        assert expense["amount"] == 5000
        assert expense["category"] == "Bolig"


class TestChartDataDemoMode:
    """Tests for chart data in demo mode."""

    def test_demo_mode_returns_demo_data(self, client):
        """Demo mode should return demo data."""
        # Enter demo mode - cookie is set on redirect response
        demo_response = client.get("/budget/demo", follow_redirects=False)
        assert demo_response.status_code == 303

        # Get the demo cookie and set it manually
        demo_cookie = demo_response.cookies.get("budget_session")
        client.cookies.set("budget_session", demo_cookie)

        response = client.get("/budget/api/chart-data")
        assert response.status_code == 200

        data = response.json()
        # Demo data has known values
        assert data["total_income"] > 0
        assert data["total_expenses"] > 0
        assert len(data["category_totals"]) > 0
        assert len(data["top_expenses"]) > 0

    def test_demo_mode_income_value(self, client):
        """Demo mode should return expected income total."""
        # Enter demo mode
        demo_response = client.get("/budget/demo", follow_redirects=False)
        demo_cookie = demo_response.cookies.get("budget_session")
        client.cookies.set("budget_session", demo_cookie)

        response = client.get("/budget/api/chart-data")
        data = response.json()

        # Demo income: 28000 + 22000 + 30000/6 = 55000
        assert data["total_income"] == 55000

    def test_demo_mode_has_categories(self, client):
        """Demo mode should have multiple expense categories."""
        # Enter demo mode
        demo_response = client.get("/budget/demo", follow_redirects=False)
        demo_cookie = demo_response.cookies.get("budget_session")
        client.cookies.set("budget_session", demo_cookie)

        response = client.get("/budget/api/chart-data")
        data = response.json()

        # Demo data has various categories
        assert "Bolig" in data["category_totals"]
        assert "Transport" in data["category_totals"]
        assert "Mad" in data["category_totals"]


class TestChartDataCategoryGrouping:
    """Tests for category grouping when there are many categories."""

    def test_categories_grouped_when_more_than_six(self, authenticated_client, db_module):
        """Categories should be grouped when more than 6."""
        user_id = authenticated_client.user_id

        # Add 8 different category expenses
        categories = ["Bolig", "Transport", "Mad", "Forsikring", "Abonnementer", "Børn", "Opsparing", "Andet"]
        for i, cat in enumerate(categories):
            db_module.add_expense(user_id, f"Expense {i}", cat, (i + 1) * 1000, "monthly")

        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        # Should have max 7 categories (6 + "Andet (samlet)")
        assert len(data["category_totals"]) <= 7

    def test_six_or_fewer_categories_not_grouped(self, authenticated_client, db_module):
        """Categories should not be grouped when 6 or fewer."""
        user_id = authenticated_client.user_id

        # Add 6 different category expenses
        categories = ["Bolig", "Transport", "Mad", "Forsikring", "Abonnementer", "Børn"]
        for i, cat in enumerate(categories):
            db_module.add_expense(user_id, f"Expense {i}", cat, (i + 1) * 1000, "monthly")

        response = authenticated_client.get("/budget/api/chart-data")
        data = response.json()

        # All 6 categories should be present
        assert len(data["category_totals"]) == 6
        for cat in categories:
            assert cat in data["category_totals"]
