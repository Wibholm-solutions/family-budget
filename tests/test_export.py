"""Tests for export data API endpoint."""


class TestExportDataEndpoint:
    """Tests for /budget/api/export-data endpoint."""

    def test_export_data_requires_auth(self, client):
        """Export data endpoint should require authentication."""
        response = client.get("/budget/api/export-data", follow_redirects=False)
        assert response.status_code == 303

    def test_export_data_returns_json(self, authenticated_client):
        """Endpoint should return valid JSON."""
        response = authenticated_client.get("/budget/api/export-data")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_export_data_has_required_fields(self, authenticated_client):
        """Response should include all required fields."""
        response = authenticated_client.get("/budget/api/export-data")
        data = response.json()

        assert "date_label" in data
        assert "total_income" in data
        assert "total_expenses" in data
        assert "remaining" in data
        assert "incomes" in data
        assert "category_totals" in data
        assert "expenses_by_category" in data

        assert isinstance(data["date_label"], str)
        assert isinstance(data["total_income"], (int, float))
        assert isinstance(data["total_expenses"], (int, float))
        assert isinstance(data["remaining"], (int, float))
        assert isinstance(data["incomes"], list)
        assert isinstance(data["category_totals"], dict)
        assert isinstance(data["expenses_by_category"], dict)

    def test_export_data_empty_user(self, authenticated_client):
        """New user with no data should return zero values."""
        response = authenticated_client.get("/budget/api/export-data")
        data = response.json()

        assert data["total_income"] == 0
        assert data["total_expenses"] == 0
        assert data["remaining"] == 0
        assert data["incomes"] == []
        assert data["category_totals"] == {}
        assert data["expenses_by_category"] == {}

    def test_export_data_with_data(self, authenticated_client, db_module):
        """Endpoint should return structured data with expenses and income."""
        user_id = authenticated_client.user_id

        db_module.add_income(user_id, "Salary", 30000, "monthly")
        db_module.add_expense(user_id, "Rent", "Bolig", 12000, "monthly")
        db_module.add_expense(user_id, "Car", "Transport", 6000, "yearly")

        response = authenticated_client.get("/budget/api/export-data")
        data = response.json()

        assert data["total_income"] == 30000
        assert data["total_expenses"] == 12500  # 12000 + 6000/12
        assert data["remaining"] == 17500

        # Incomes structure
        assert len(data["incomes"]) == 1
        assert data["incomes"][0]["person"] == "Salary"
        assert data["incomes"][0]["amount"] == 30000

        # Category totals with icons
        assert "Bolig" in data["category_totals"]
        assert data["category_totals"]["Bolig"]["total"] == 12000
        assert "icon" in data["category_totals"]["Bolig"]

        # Expenses by category
        assert "Bolig" in data["expenses_by_category"]
        assert len(data["expenses_by_category"]["Bolig"]) == 1
        assert data["expenses_by_category"]["Bolig"][0]["name"] == "Rent"
        assert data["expenses_by_category"]["Bolig"][0]["amount"] == 12000

    def test_export_data_expense_account_field(self, authenticated_client, db_module):
        """Expenses should include account field (nullable)."""
        user_id = authenticated_client.user_id

        db_module.add_expense(user_id, "Rent", "Bolig", 12000, "monthly", account="Fælleskonto")
        db_module.add_expense(user_id, "Netflix", "Underholdning", 149, "monthly")

        response = authenticated_client.get("/budget/api/export-data")
        data = response.json()

        bolig_expenses = data["expenses_by_category"]["Bolig"]
        assert bolig_expenses[0]["account"] == "Fælleskonto"

        underholdning_expenses = data["expenses_by_category"]["Underholdning"]
        assert underholdning_expenses[0]["account"] is None


class TestExportDataDemoMode:
    """Tests for export data in demo mode."""

    def test_demo_mode_returns_data(self, client):
        """Demo users should be able to use export-data."""
        demo_response = client.get("/budget/demo", follow_redirects=False)
        demo_cookie = demo_response.cookies.get("budget_session")
        client.cookies.set("budget_session", demo_cookie)

        response = client.get("/budget/api/export-data")
        assert response.status_code == 200

        data = response.json()
        assert data["total_income"] > 0
        assert data["total_expenses"] > 0
        assert len(data["incomes"]) > 0
        assert len(data["category_totals"]) > 0
