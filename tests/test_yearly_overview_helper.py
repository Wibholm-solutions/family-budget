"""Tests for the private _calculate_yearly_overview helper."""

import pytest


class TestCalculateYearlyOverview:
    """Tests for the private _calculate_yearly_overview helper."""

    def test_empty_inputs_return_zero_structure(self, db_module):
        """Empty expenses and income return correct zero-filled structure."""
        result = db_module._calculate_yearly_overview([], [])
        assert result['categories'] == {}
        assert result['year_total'] == 0.0
        assert list(result['totals'].keys()) == list(range(1, 13))
        assert all(result['totals'][m] == 0 for m in range(1, 13))
        assert all(result['income'][m] == 0 for m in range(1, 13))
        assert all(result['balance'][m] == 0 for m in range(1, 13))

    def test_monthly_expense_appears_every_month(self, db_module):
        """A monthly expense spreads evenly across all 12 months."""
        from src.database import Expense
        expenses = [Expense(id=1, user_id=0, name="Husleje", category="Bolig",
                            amount=10000, frequency="monthly")]
        result = db_module._calculate_yearly_overview(expenses, [])
        assert all(result['categories']['Bolig'][m] == 10000 for m in range(1, 13))
        assert result['year_total'] == 120000

    def test_expense_with_specific_months(self, db_module):
        """Expense with months=[3,9] only appears in those months."""
        from src.database import Expense
        expenses = [Expense(id=1, user_id=0, name="Forsikring", category="Forsikring",
                            amount=6000, frequency="semi-annual", months=[3, 9])]
        result = db_module._calculate_yearly_overview(expenses, [])
        assert result['categories']['Forsikring'][3] == 3000
        assert result['categories']['Forsikring'][9] == 3000
        assert result['categories']['Forsikring'][1] == 0
        assert result['year_total'] == 6000

    def test_monthly_income_spread_evenly(self, db_module):
        """Monthly income spreads evenly across all 12 months."""
        from src.database import Income
        income = [Income(id=1, user_id=0, person="Person 1",
                         amount=30000, frequency="monthly")]
        result = db_module._calculate_yearly_overview([], income)
        assert all(result['income'][m] == 30000 for m in range(1, 13))

    def test_balance_is_income_minus_expenses(self, db_module):
        """Balance = income - totals for each month."""
        from src.database import Expense, Income
        expenses = [Expense(id=1, user_id=0, name="Husleje", category="Bolig",
                            amount=10000, frequency="monthly")]
        income = [Income(id=1, user_id=0, person="Person 1",
                         amount=30000, frequency="monthly")]
        result = db_module._calculate_yearly_overview(expenses, income)
        assert all(result['balance'][m] == 20000 for m in range(1, 13))

    def test_multiple_categories_sum_correctly(self, db_module):
        """Multiple expense categories aggregate independently."""
        from src.database import Expense
        expenses = [
            Expense(id=1, user_id=0, name="Husleje", category="Bolig",
                    amount=5000, frequency="monthly"),
            Expense(id=2, user_id=0, name="Mad", category="Mad",
                    amount=3000, frequency="monthly"),
        ]
        result = db_module._calculate_yearly_overview(expenses, [])
        assert all(result['categories']['Bolig'][m] == 5000 for m in range(1, 13))
        assert all(result['categories']['Mad'][m] == 3000 for m in range(1, 13))
        assert all(result['totals'][m] == 8000 for m in range(1, 13))

    def test_return_structure_has_all_keys(self, db_module):
        """Return value always has all five expected keys."""
        result = db_module._calculate_yearly_overview([], [])
        assert set(result.keys()) == {'categories', 'totals', 'income', 'balance', 'year_total'}
