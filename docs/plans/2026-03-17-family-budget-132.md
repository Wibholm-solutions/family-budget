# Extract validate_expense_input Helper — Issue #132

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate duplicated expense validation logic in `add_expense` and `edit_expense` by extracting it into a shared `validate_expense_input` helper.

**Architecture:** Add a module-level helper `validate_expense_input(amount_str, frequency, months_str)` in `src/routes/expenses.py` immediately after the existing `parse_months` helper. Both route handlers are then reduced to a single call. Unit tests go in a new `tests/test_expense_validation.py` file (separate from `tests/test_expenses.py` to avoid the file-size hook).

**Tech Stack:** Python 3.11, FastAPI, pytest — no new dependencies.

---

## Background: Previous Attempt

PR #151 (`refactor/expense-validation-132`) was closed due to a merge conflict with master caused by PR #149 (auth/demo guard refactor, which also touched `expenses.py`). **Do not rebase or re-open the old branch.** Start fresh from a new branch off `master`.

---

## Chunk 1: Setup and Tests

### Task 1: Create fresh branch and write failing unit tests

**Files:**
- Create: `tests/test_expense_validation.py`

- [ ] **Step 1: Create fresh branch from master**

```bash
cd /home/saabendtsen/projects/family-budget
git checkout master
git pull origin master
git checkout -b refactor/expense-validation-132-v2
```

Expected: on branch `refactor/expense-validation-132-v2`, up to date with master.

- [ ] **Step 2: Create the test file**

```python
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
```

- [ ] **Step 3: Confirm tests fail with ImportError**

```bash
cd /home/saabendtsen/projects/family-budget
venv/bin/pytest tests/test_expense_validation.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'validate_expense_input'`

---

## Chunk 2: Implementation and Refactor

### Task 2: Implement validate_expense_input

**Files:**
- Modify: `src/routes/expenses.py` — insert helper after `parse_months` (after line 56)

- [ ] **Step 1: Insert the helper function**

In `src/routes/expenses.py`, after the closing `return sorted(months)` of `parse_months` (line 56) and before the `@router.get` decorator (line 59), add:

```python
def validate_expense_input(
    amount_str: str,
    frequency: str,
    months_str: str | None,
) -> tuple[float, list[int] | None]:
    """Validate and parse shared expense input fields.

    Raises HTTPException(400) on any validation failure.
    Returns (amount_float, months_list).
    """
    if frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Ugyldig frekvens")

    try:
        amount_float = parse_danish_amount(amount_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldigt beløb format") from None

    if amount_float < 0:
        raise HTTPException(status_code=400, detail="Beløb skal være positivt")
    if amount_float > 1000000:
        raise HTTPException(status_code=400, detail="Beløb er for stort")

    months_list = parse_months(months_str if months_str else None, frequency)

    return amount_float, months_list
```

- [ ] **Step 2: Run the unit tests**

```bash
cd /home/saabendtsen/projects/family-budget
venv/bin/pytest tests/test_expense_validation.py -v 2>&1 | tail -20
```

Expected: All 12 tests PASS.

- [ ] **Step 3: Commit tests + implementation together**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/routes/expenses.py tests/test_expense_validation.py
git commit -m "feat: add validate_expense_input helper with unit tests"
```

---

### Task 3: Refactor route handlers to use the helper

**Files:**
- Modify: `src/routes/expenses.py` — simplify `add_expense` (lines ~110–125) and `edit_expense` (lines ~161–177)

Current master's `add_expense` (lines 110–125) duplicates:
```python
    # Validate frequency
    if frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Ugyldig frekvens")

    # Parse and validate amount
    try:
        amount_float = parse_danish_amount(amount)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldigt beløb format") from None

    if amount_float < 0:
        raise HTTPException(status_code=400, detail="Beløb skal være positivt")
    if amount_float > 1000000:
        raise HTTPException(status_code=400, detail="Beløb er for stort")

    months_list = parse_months(months if months else None, frequency)
```

Same block appears in `edit_expense`. Both are replaced with one line each.

- [ ] **Step 1: Replace duplicated block in add_expense**

Remove the 15-line block above from `add_expense` and replace with:

```python
    amount_float, months_list = validate_expense_input(amount, frequency, months)
```

- [ ] **Step 2: Replace duplicated block in edit_expense**

Remove the identical 15-line block from `edit_expense` and replace with:

```python
    amount_float, months_list = validate_expense_input(amount, frequency, months)
```

- [ ] **Step 3: Run full test suite**

```bash
cd /home/saabendtsen/projects/family-budget
venv/bin/pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests PASS — no regressions.

- [ ] **Step 4: Commit**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/routes/expenses.py
git commit -m "refactor: use validate_expense_input in add_expense and edit_expense"
```

- [ ] **Step 5: Open PR**

```bash
cd /home/saabendtsen/projects/family-budget
gh pr create \
  --title "refactor: extract validate_expense_input helper to eliminate duplicated validation" \
  --body "Closes #132

Extracts shared frequency/amount/months validation from \`add_expense\` and \`edit_expense\` into a single \`validate_expense_input\` helper. Both handlers reduced by ~15 lines each. Unit tests added in \`tests/test_expense_validation.py\`." \
  --base master \
  --label "refactor"
```

---

## Done

- `validate_expense_input` is the single source of truth for expense input validation.
- Both route handlers are ~15 lines shorter each.
- Unit tests in `tests/test_expense_validation.py` cover all validation branches.
- No route behaviour has changed.
