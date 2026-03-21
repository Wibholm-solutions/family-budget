"""Tests for DataContext facade — verifies demo transparency."""


class TestDataContextDemo:
    """DataContext with demo=True should return demo data without DB."""

    def test_expenses_returns_demo_data(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        expenses = ctx.expenses()
        assert len(expenses) > 0
        assert expenses[0].name == "Husleje/boliglån"

    def test_income_returns_demo_data(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        income = ctx.income()
        assert len(income) >= 3

    def test_categories_returns_demo_categories(self, db_module):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        cats = ctx.categories()
        assert len(cats) > 0

    def test_category_totals(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        totals = ctx.category_totals()
        assert "Bolig" in totals
        assert totals["Bolig"] > 0

    def test_total_income(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        assert ctx.total_income() > 0

    def test_total_expenses(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        assert ctx.total_expenses() > 0

    def test_yearly_overview(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        overview = ctx.yearly_overview()
        assert "categories" in overview
        assert "totals" in overview

    def test_expenses_by_category(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        grouped = ctx.expenses_by_category()
        assert "Bolig" in grouped

    def test_account_totals_advanced(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True, advanced=True)
        totals = ctx.account_totals()
        assert "Budgetkonto" in totals

    def test_accounts_advanced(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True, advanced=True)
        accounts = ctx.accounts()
        assert len(accounts) > 0

    def test_category_usage_demo_is_zero(self, db_module):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        usage = ctx.category_usage()
        assert all(v == 0 for v in usage.values())


class TestBudgetReaderProtocol:
    """DataContext must satisfy BudgetReader at runtime."""

    def test_datacontext_satisfies_budget_reader(self):
        from src.db.facade import DataContext
        from src.db.ports import BudgetReader
        ctx = DataContext(user_id=0, demo=True)
        assert isinstance(ctx, BudgetReader)


class TestWritableProperty:
    """writable is False in demo, True in real mode."""

    def test_demo_not_writable(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        assert ctx.writable is False

    def test_real_is_writable(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=1, demo=False)
        assert ctx.writable is True


class TestDataContextReal:
    """DataContext with demo=False should query the real DB."""

    def test_expenses_empty_for_new_user(self, db_module):
        from src.db.facade import DataContext
        user_id = db_module.create_user("ctx_test", "pass123")
        ctx = DataContext(user_id=user_id, demo=False)
        assert ctx.expenses() == []

    def test_income_empty_for_new_user(self, db_module):
        from src.db.facade import DataContext
        user_id = db_module.create_user("ctx_test2", "pass123")
        ctx = DataContext(user_id=user_id, demo=False)
        assert ctx.income() == []

    def test_total_income_zero_for_new_user(self, db_module):
        from src.db.facade import DataContext
        user_id = db_module.create_user("ctx_test3", "pass123")
        ctx = DataContext(user_id=user_id, demo=False)
        assert ctx.total_income() == 0.0

    def test_categories_has_defaults(self, db_module):
        from src.db.facade import DataContext
        user_id = db_module.create_user("ctx_test4", "pass123")
        ctx = DataContext(user_id=user_id, demo=False)
        cats = ctx.categories()
        assert len(cats) == 9  # DEFAULT_CATEGORIES count
