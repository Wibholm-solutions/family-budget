# tests/test_expense_validation.py
"""Unit tests for validate_expense_input helper."""
import pytest
from fastapi import HTTPException

from src.routes.expenses import validate_expense_input


class TestValidateExpenseInput:
    """Unit tests for the validate_expense_input helper."""

    # --- Happy path ---

    def test_valid_monthly_amount(self):
        amount, months = validate_expense_input("1000", "monthly", "")
        assert amount == 1000.0
        assert months is None

    def test_valid_danish_decimal(self):
        amount, months = validate_expense_input("1.500,50", "monthly", "")
        assert amount == 1500.50
        assert months is None

    def test_valid_quarterly_with_months(self):
        amount, months = validate_expense_input("3000", "quarterly", "3,6,9,12")
        assert amount == 3000.0
        assert months == [3, 6, 9, 12]

    def test_valid_semi_annual_with_months(self):
        amount, months = validate_expense_input("6000", "semi-annual", "1,7")
        assert amount == 6000.0
        assert months == [1, 7]

    def test_valid_yearly_with_month(self):
        amount, months = validate_expense_input("12000", "yearly", "1")
        assert amount == 12000.0
        assert months == [1]

    # --- Frequency validation ---

    def test_invalid_frequency_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_expense_input("1000", "biweekly", "")
        assert exc_info.value.status_code == 400
        assert "frekvens" in exc_info.value.detail.lower()

    # --- Amount parsing ---

    def test_invalid_amount_format_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_expense_input("not-a-number", "monthly", "")
        assert exc_info.value.status_code == 400

    # --- Amount bounds ---

    def test_negative_amount_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_expense_input("-1", "monthly", "")
        assert exc_info.value.status_code == 400
        assert "positivt" in exc_info.value.detail

    def test_zero_amount_is_allowed(self):
        amount, _ = validate_expense_input("0", "monthly", "")
        assert amount == 0.0

    def test_amount_at_upper_limit_is_allowed(self):
        amount, _ = validate_expense_input("1000000", "monthly", "")
        assert amount == 1_000_000.0

    def test_amount_over_limit_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_expense_input("1000001", "monthly", "")
        assert exc_info.value.status_code == 400
        assert "stor" in exc_info.value.detail

    # --- Months parsing delegated to parse_months ---

    def test_invalid_months_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_expense_input("1000", "quarterly", "a,b,c,d")
        assert exc_info.value.status_code == 400
