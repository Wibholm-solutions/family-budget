"""Tests for currency formatting and amount parsing helpers."""

import pytest


class TestAmountParsing:
    """Tests for Danish amount format parsing."""

    def test_parse_danish_amount_with_comma(self):
        """Should parse comma as decimal separator."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("1234,50") == 1234.50

    def test_parse_danish_amount_with_thousands_and_comma(self):
        """Should handle thousands separator with comma."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("1.234,50") == 1234.50
        assert parse_danish_amount("12.345,67") == 12345.67

    def test_parse_danish_amount_whole_number(self):
        """Should handle whole numbers."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("1234") == 1234.00

    def test_parse_danish_amount_single_decimal(self):
        """Should handle single decimal place."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("1234,5") == 1234.50

    def test_parse_danish_amount_with_whitespace(self):
        """Should trim whitespace."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("  1234,50  ") == 1234.50

    def test_parse_danish_amount_zero(self):
        """Should handle zero."""
        from src.api import parse_danish_amount
        assert parse_danish_amount("0") == 0.00
        assert parse_danish_amount("0,00") == 0.00

    def test_parse_danish_amount_invalid_empty(self):
        """Should raise ValueError for empty string."""
        from src.api import parse_danish_amount
        with pytest.raises(ValueError):
            parse_danish_amount("")

    def test_parse_danish_amount_invalid_text(self):
        """Should raise ValueError for invalid text."""
        from src.api import parse_danish_amount
        with pytest.raises(ValueError):
            parse_danish_amount("abc")

    def test_parse_danish_amount_invalid_multiple_commas(self):
        """Should raise ValueError for multiple commas."""
        from src.api import parse_danish_amount
        with pytest.raises(ValueError):
            parse_danish_amount("12,34,56")


class TestCurrencyFormatting:
    """Tests for currency display formatting."""

    def test_format_currency_with_decimals(self):
        """Should format with 2 decimal places."""
        from src.api import format_currency
        assert format_currency(1234.50) == "1.234,50 kr"

    def test_format_currency_whole_number(self):
        """Should show .00 for whole numbers."""
        from src.api import format_currency
        assert format_currency(1234.0) == "1.234,00 kr"

    def test_format_currency_large_amount(self):
        """Should handle large amounts with thousands separator."""
        from src.api import format_currency
        assert format_currency(123456.78) == "123.456,78 kr"

    def test_format_currency_small_amount(self):
        """Should handle amounts less than 1 kr."""
        from src.api import format_currency
        assert format_currency(0.50) == "0,50 kr"

    def test_format_currency_zero(self):
        """Should format zero correctly."""
        from src.api import format_currency
        assert format_currency(0.00) == "0,00 kr"

    def test_format_currency_thousands(self):
        """format_currency should format Danish-style currency with 2 decimal places."""
        from src.api import format_currency
        assert format_currency(1000) == "1.000,00 kr"
        assert format_currency(1000000) == "1.000.000,00 kr"
        assert format_currency(0) == "0,00 kr"
