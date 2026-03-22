"""Centralized input validators for Family Budget entities."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException

from .helpers import parse_danish_amount

VALID_FREQUENCIES = ("monthly", "quarterly", "semi-annual", "yearly")

MONTHS_REQUIRED = {
    "quarterly": 4,
    "semi-annual": 2,
    "yearly": 1,
}


@dataclass(frozen=True)
class ValidationResult:
    """Immutable result of a validation pass."""

    errors: list[str] = field(default_factory=list)
    parsed: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def raise_if_invalid(self) -> None:
        """Raise HTTPException(400) if there are validation errors."""
        if not self.ok:
            raise HTTPException(status_code=400, detail="; ".join(self.errors))


def _validate_name(name: str | None, entity: str, errors: list[str]) -> str | None:
    """Validate an entity name. Returns stripped name or None."""
    if name is None or not name.strip():
        errors.append(f"{entity} navn er påkrævet")
        return None
    stripped = name.strip()
    if len(stripped) > 200:
        errors.append(f"{entity} navn er for langt (maks 200 tegn)")
        return None
    return stripped


def _parse_and_validate_amount(amount_str: str, errors: list[str]) -> float | None:
    """Parse a Danish-format amount string and validate bounds."""
    try:
        amount = parse_danish_amount(amount_str)
    except ValueError:
        errors.append("Ugyldigt beløb format")
        return None

    if amount < 0:
        errors.append("Beløb skal være positivt")
        return None
    if amount > 1_000_000:
        errors.append("Beløb er for stort")
        return None
    return amount


def _validate_frequency(freq: str, errors: list[str]) -> str | None:
    """Validate frequency value."""
    if freq not in VALID_FREQUENCIES:
        errors.append("Ugyldig frekvens")
        return None
    return freq


def _parse_and_validate_months(
    months_str: str | None, freq: str, errors: list[str]
) -> list[int] | None:
    """Parse comma-separated month ints, validate range and count."""
    if freq == "monthly":
        return None
    if not months_str or not months_str.strip():
        return None

    try:
        months = [int(m.strip()) for m in months_str.split(",")]
    except ValueError:
        errors.append("Ugyldige måneder")
        return None

    if any(m < 1 or m > 12 for m in months):
        errors.append("Måneder skal være mellem 1 og 12")
        return None

    expected = MONTHS_REQUIRED.get(freq)
    if expected and len(months) != expected:
        errors.append(f"Vælg præcis {expected} måneder for denne frekvens")
        return None

    return sorted(months)


def validate_expense(
    name: str | None,
    amount_str: str,
    frequency: str,
    months_str: str | None,
    account: str | None,
) -> ValidationResult:
    """Validate expense input fields."""
    errors: list[str] = []
    parsed: dict[str, object] = {}

    validated_name = _validate_name(name, "Udgift", errors)
    if validated_name is not None:
        parsed["name"] = validated_name

    validated_freq = _validate_frequency(frequency, errors)

    amount = _parse_and_validate_amount(amount_str, errors)
    if amount is not None:
        parsed["amount"] = amount

    # Only parse months if frequency was valid
    if validated_freq is not None:
        months = _parse_and_validate_months(months_str, validated_freq, errors)
        parsed["months"] = months

    if account:
        parsed["account"] = account

    return ValidationResult(errors=errors, parsed=parsed)
