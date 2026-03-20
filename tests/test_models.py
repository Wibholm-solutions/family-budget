"""Unit tests for domain models — pure computation, no DB needed."""


class TestMonthlyMixin:
    """Tests for shared monthly_amount and get_monthly_amounts logic."""

    def test_monthly_income_amount(self):
        from src.db.models import Income
        inc = Income(id=1, user_id=1, person="Test", amount=12000, frequency="monthly")
        assert inc.monthly_amount == 12000.0

    def test_yearly_income_monthly_amount(self):
        from src.db.models import Income
        inc = Income(id=1, user_id=1, person="Test", amount=12000, frequency="yearly")
        assert inc.monthly_amount == 1000.0

    def test_quarterly_expense_monthly_amount(self):
        from src.db.models import Expense
        exp = Expense(id=1, user_id=1, name="Test", category="Bolig", amount=3000, frequency="quarterly")
        assert exp.monthly_amount == 1000.0

    def test_semi_annual_monthly_amount(self):
        from src.db.models import Expense
        exp = Expense(id=1, user_id=1, name="Test", category="Bolig", amount=6000, frequency="semi-annual")
        assert exp.monthly_amount == 1000.0

    def test_get_monthly_amounts_monthly_spreads_evenly(self):
        from src.db.models import Expense
        exp = Expense(id=1, user_id=1, name="Test", category="Bolig", amount=1200, frequency="monthly")
        amounts = exp.get_monthly_amounts()
        assert all(amounts[m] == 1200.0 for m in range(1, 13))

    def test_get_monthly_amounts_with_specific_months(self):
        from src.db.models import Expense
        exp = Expense(id=1, user_id=1, name="Test", category="Bolig", amount=6000, frequency="semi-annual", months=[6, 12])
        amounts = exp.get_monthly_amounts()
        assert amounts[6] == 3000.0
        assert amounts[12] == 3000.0
        assert amounts[1] == 0.0

    def test_get_monthly_amounts_no_months_spreads_evenly(self):
        from src.db.models import Income
        inc = Income(id=1, user_id=1, person="Test", amount=12000, frequency="yearly")
        amounts = inc.get_monthly_amounts()
        assert all(amounts[m] == 1000.0 for m in range(1, 13))

    def test_income_and_expense_share_same_logic(self):
        """Both Income and Expense should produce identical monthly_amount for same inputs."""
        from src.db.models import Expense, Income
        inc = Income(id=1, user_id=1, person="X", amount=2400, frequency="quarterly")
        exp = Expense(id=1, user_id=1, name="X", category="C", amount=2400, frequency="quarterly")
        assert inc.monthly_amount == exp.monthly_amount


class TestUserModel:
    def test_has_email_true(self):
        from src.db.models import User
        u = User(id=1, username="test", password_hash="h", salt="s", email_hash="abc")
        assert u.has_email() is True

    def test_has_email_false(self):
        from src.db.models import User
        u = User(id=1, username="test", password_hash="h", salt="s")
        assert u.has_email() is False
