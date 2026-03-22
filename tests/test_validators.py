"""Unit tests for src/validators module."""

import pytest
from fastapi import HTTPException

from src.validators import ValidationResult, validate_expense


class TestValidationResult:
    def test_ok_when_no_errors(self):
        result = ValidationResult(errors=[], parsed={"amount": 100.0})
        assert result.ok is True

    def test_not_ok_with_errors(self):
        result = ValidationResult(errors=["bad input"], parsed={})
        assert result.ok is False

    def test_raise_if_invalid_raises_400(self):
        result = ValidationResult(errors=["err1", "err2"], parsed={})
        with pytest.raises(HTTPException) as exc_info:
            result.raise_if_invalid()
        assert exc_info.value.status_code == 400
        assert "err1" in exc_info.value.detail
        assert "err2" in exc_info.value.detail

    def test_raise_if_invalid_noop_when_ok(self):
        result = ValidationResult(errors=[], parsed={"amount": 1.0})
        result.raise_if_invalid()  # should not raise


class TestValidateExpense:
    def test_valid_monthly_expense(self):
        result = validate_expense("Husleje", "1000", "monthly", "", None)
        assert result.ok
        assert result.parsed["amount"] == 1000.0
        assert result.parsed["months"] is None

    def test_danish_decimal_amount(self):
        result = validate_expense("Husleje", "1.500,50", "monthly", "", None)
        assert result.ok
        assert result.parsed["amount"] == 1500.50

    def test_quarterly_with_months(self):
        result = validate_expense("Forsikring", "3000", "quarterly", "3,6,9,12", None)
        assert result.ok
        assert result.parsed["amount"] == 3000.0
        assert result.parsed["months"] == [3, 6, 9, 12]

    def test_semi_annual_with_months(self):
        result = validate_expense("Bil", "6000", "semi-annual", "1,7", None)
        assert result.ok
        assert result.parsed["months"] == [1, 7]

    def test_yearly_with_month(self):
        result = validate_expense("Licens", "12000", "yearly", "1", None)
        assert result.ok
        assert result.parsed["months"] == [1]

    def test_invalid_frequency(self):
        result = validate_expense("Test", "1000", "biweekly", "", None)
        assert not result.ok
        assert any("frekvens" in e.lower() for e in result.errors)

    def test_invalid_amount_format(self):
        result = validate_expense("Test", "not-a-number", "monthly", "", None)
        assert not result.ok

    def test_negative_amount(self):
        result = validate_expense("Test", "-1", "monthly", "", None)
        assert not result.ok
        assert any("positivt" in e for e in result.errors)

    def test_zero_amount_allowed(self):
        result = validate_expense("Test", "0", "monthly", "", None)
        assert result.ok
        assert result.parsed["amount"] == 0.0

    def test_amount_at_upper_limit(self):
        result = validate_expense("Test", "1000000", "monthly", "", None)
        assert result.ok
        assert result.parsed["amount"] == 1_000_000.0

    def test_amount_over_limit(self):
        result = validate_expense("Test", "1000001", "monthly", "", None)
        assert not result.ok
        assert any("stor" in e for e in result.errors)

    def test_invalid_months_format(self):
        result = validate_expense("Test", "1000", "quarterly", "a,b,c,d", None)
        assert not result.ok

    def test_months_out_of_range(self):
        result = validate_expense("Test", "1000", "quarterly", "0,6,9,13", None)
        assert not result.ok

    def test_wrong_month_count(self):
        result = validate_expense("Test", "1000", "quarterly", "1,2", None)
        assert not result.ok
