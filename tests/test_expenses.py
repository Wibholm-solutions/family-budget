"""Integration tests for expense, category, and account endpoints."""


class TestExpenseEndpoints:
    """Tests for expense management endpoints."""

    def test_expenses_page_loads(self, authenticated_client):
        """Expenses page should load for authenticated users."""
        response = authenticated_client.get("/budget/expenses")

        assert response.status_code == 200

    def test_add_expense(self, authenticated_client):
        """POST to add expense should create expense."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Test Expense",
                "category": "Bolig",
                "amount": "1000",
                "frequency": "monthly"
            },
            follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/budget/expenses"

    def test_add_expense_quarterly(self, authenticated_client, db_module):
        """POST to add expense with quarterly frequency should work."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Quarterly Expense",
                "category": "Forbrug",
                "amount": "2400",
                "frequency": "quarterly"
            },
            follow_redirects=False
        )

        assert response.status_code == 303
        # Verify expense was created with correct frequency
        user_id = authenticated_client.user_id
        expenses = db_module.get_all_expenses(user_id)
        quarterly_expense = next((e for e in expenses if e.name == "Quarterly Expense"), None)
        assert quarterly_expense is not None
        assert quarterly_expense.frequency == "quarterly"
        assert quarterly_expense.monthly_amount == 800  # 2400 / 3

    def test_add_expense_semiannual(self, authenticated_client, db_module):
        """POST to add expense with semi-annual frequency should work."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Semi-Annual Expense",
                "category": "Transport",
                "amount": "4500",
                "frequency": "semi-annual"
            },
            follow_redirects=False
        )

        assert response.status_code == 303
        # Verify expense was created with correct frequency
        user_id = authenticated_client.user_id
        expenses = db_module.get_all_expenses(user_id)
        semiannual_expense = next((e for e in expenses if e.name == "Semi-Annual Expense"), None)
        assert semiannual_expense is not None
        assert semiannual_expense.frequency == "semi-annual"
        assert semiannual_expense.monthly_amount == 750  # 4500 / 6

    def test_add_expense_invalid_frequency(self, authenticated_client):
        """POST to add expense with invalid frequency should reject."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={
                "name": "Invalid Expense",
                "category": "Bolig",
                "amount": "1000",
                "frequency": "invalid_frequency"
            },
            follow_redirects=False
        )

        # Should reject with 400 Bad Request (invalid frequency validation)
        assert response.status_code == 400

    def test_delete_expense(self, authenticated_client, db_module):
        """POST to delete expense should remove it."""
        # First add an expense using the authenticated user's ID
        user_id = authenticated_client.user_id
        expense_id = db_module.add_expense(user_id, "ToDelete", "Bolig", 500, "monthly")

        response = authenticated_client.post(
            f"/budget/expenses/{expense_id}/delete",
            follow_redirects=False
        )

        assert response.status_code == 303

    def test_edit_expense(self, authenticated_client, db_module):
        """POST to edit expense should update it."""
        user_id = authenticated_client.user_id
        expense_id = db_module.add_expense(user_id, "Original", "Bolig", 500, "monthly")

        response = authenticated_client.post(
            f"/budget/expenses/{expense_id}/edit",
            data={
                "name": "Updated",
                "category": "Transport",
                "amount": "750",
                "frequency": "yearly"
            },
            follow_redirects=False
        )

        assert response.status_code == 303


class TestCategoryEndpoints:
    """Tests for category management endpoints."""

    def test_categories_page_loads(self, authenticated_client):
        """Categories page should load for authenticated users."""
        response = authenticated_client.get("/budget/categories")

        assert response.status_code == 200

    def test_add_category(self, authenticated_client):
        """POST to add category should create category."""
        response = authenticated_client.post(
            "/budget/categories/add",
            data={"name": "NewCategory", "icon": "star"},
            follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/budget/categories"

    def test_edit_category(self, authenticated_client, db_module):
        """POST to edit category should update it."""
        category_id = db_module.add_category(authenticated_client.user_id, "OldName", "old-icon")

        response = authenticated_client.post(
            f"/budget/categories/{category_id}/edit",
            data={"name": "NewName", "icon": "new-icon"},
            follow_redirects=False
        )

        assert response.status_code == 303

    def test_edit_category_redirects_to_expenses(self, authenticated_client, db_module):
        """POST to edit category with next=/budget/expenses should redirect there."""
        category_id = db_module.add_category(authenticated_client.user_id, "CatA", "folder")

        response = authenticated_client.post(
            f"/budget/categories/{category_id}/edit",
            data={"name": "CatB", "icon": "folder", "next": "/budget/expenses"},
            follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"].startswith("/budget/expenses")

    def test_edit_category_rejects_unsafe_next(self, authenticated_client, db_module):
        """POST to edit category with unknown next URL should fall back to /budget/categories."""
        category_id = db_module.add_category(authenticated_client.user_id, "CatX", "folder")

        response = authenticated_client.post(
            f"/budget/categories/{category_id}/edit",
            data={"name": "CatY", "icon": "folder", "next": "https://evil.com"},
            follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"].startswith("/budget/categories")

    def test_delete_category(self, authenticated_client, db_module):
        """POST to delete unused category should remove it."""
        category_id = db_module.add_category(authenticated_client.user_id, "Unused", "icon")

        response = authenticated_client.post(
            f"/budget/categories/{category_id}/delete",
            follow_redirects=False
        )

        assert response.status_code == 303


class TestAccountEndpoints:
    """Tests for account management endpoints."""

    def test_add_account_json_success(self, authenticated_client):
        """POST to add-json should create account and return JSON."""
        response = authenticated_client.post(
            "/budget/accounts/add-json",
            data={"name": "Nordea"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["name"] == "Nordea"

    def test_add_account_json_duplicate(self, authenticated_client):
        """POST to add-json with duplicate name should return error."""
        authenticated_client.post(
            "/budget/accounts/add-json",
            data={"name": "Nordea"},
        )
        response = authenticated_client.post(
            "/budget/accounts/add-json",
            data={"name": "Nordea"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "findes allerede" in data["error"]

    def test_add_account_json_empty_name(self, authenticated_client):
        """POST to add-json with empty name should return error."""
        response = authenticated_client.post(
            "/budget/accounts/add-json",
            data={"name": "   "},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False

    def test_add_account_json_requires_auth(self, client):
        """POST to add-json without auth should return 401."""
        response = client.post(
            "/budget/accounts/add-json",
            data={"name": "Test"},
        )

        assert response.status_code in (401, 303)

    def test_add_account_json_demo_mode(self, client):
        """POST to add-json in demo mode should be rejected."""
        # Enter demo mode (sets demo cookie)
        client.get("/budget/demo")
        client.cookies.set("budget_session", "demo")
        response = client.post(
            "/budget/accounts/add-json",
            data={"name": "Test"},
        )

        # Demo mode: check_auth passes but is_demo_mode blocks with 403
        assert response.status_code == 403
        assert response.json()["success"] is False
