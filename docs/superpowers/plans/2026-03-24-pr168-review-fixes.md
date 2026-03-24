# PR #168 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two code issues in PR #168: (1) use stripped/parsed values from validators in route handlers, (2) replace fragile substring-based error filtering in the expense shim with a `skip_name` parameter.

**Architecture:** All changes target the `feat/validators-162-v2` branch. Fix 1 is a mechanical variable reassignment in 4 route handlers. Fix 2 adds a boolean parameter to `validate_expense()` and simplifies the shim.

**Tech Stack:** Python 3.12, FastAPI, pytest

**Spec:** `docs/superpowers/specs/2026-03-24-pr168-review-fixes-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/validators.py:101-107` | Add `skip_name` parameter to `validate_expense()` |
| Modify | `src/routes/accounts.py:50,94` | Use `result.parsed["name"]` in `add_account`, `edit_account` |
| Modify | `src/routes/categories.py:49,72` | Use `result.parsed["name"]` and `result.parsed["icon"]` in `add_category`, `edit_category` |
| Modify | `src/routes/expenses.py:26-36` | Simplify shim to use `skip_name=True` |
| Modify | `tests/test_validators.py` | Add test for `skip_name=True` behavior |

---

### Task 1: Add `skip_name` parameter to `validate_expense`

**Files:**
- Modify: `src/validators.py:101-107`
- Test: `tests/test_validators.py`

- [ ] **Step 1: Write the failing test**

Add to `TestValidateExpense` in `tests/test_validators.py`:

```python
def test_skip_name_omits_name_validation(self):
    result = validate_expense(None, "1000", "monthly", "", None, skip_name=True)
    assert result.ok
    assert "name" not in result.parsed
    assert result.parsed["amount"] == 1000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -m pytest tests/test_validators.py::TestValidateExpense::test_skip_name_omits_name_validation -v`
Expected: FAIL with `TypeError: validate_expense() got an unexpected keyword argument 'skip_name'`

- [ ] **Step 3: Add `skip_name` parameter to `validate_expense()`**

In `src/validators.py`, change the `validate_expense` signature and body:

```python
def validate_expense(
    name: str | None,
    amount_str: str,
    frequency: str,
    months_str: str | None,
    account: str | None,
    *,
    skip_name: bool = False,
) -> ValidationResult:
    """Validate expense input fields."""
    errors: list[str] = []
    parsed: dict[str, object] = {}

    if not skip_name:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -m pytest tests/test_validators.py::TestValidateExpense::test_skip_name_omits_name_validation -v`
Expected: PASS

- [ ] **Step 5: Run full test_validators.py to check no regressions**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -m pytest tests/test_validators.py -v`
Expected: All tests pass (existing tests don't use `skip_name`, so default `False` preserves behavior)

- [ ] **Step 6: Lint check**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/ruff check src/validators.py tests/test_validators.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add src/validators.py tests/test_validators.py
git commit -m "feat: add skip_name parameter to validate_expense

Refs #162"
```

---

### Task 2: Simplify the expense shim to use `skip_name=True`

**Files:**
- Modify: `src/routes/expenses.py:26-36`

- [ ] **Step 1: Replace the shim implementation**

In `src/routes/expenses.py`, replace `validate_expense_input`:

```python
def validate_expense_input(
    amount_str: str,
    frequency: str,
    months_str: str | None,
) -> tuple[float, list[int] | None]:
    """Shim: delegates to validate_expense() for backward compatibility."""
    result = validate_expense(None, amount_str, frequency, months_str, None, skip_name=True)
    result.raise_if_invalid()
    return result.parsed["amount"], result.parsed["months"]
```

- [ ] **Step 2: Run existing expense validation tests**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -m pytest tests/test_expense_validation.py -v`
Expected: All 16 existing tests pass (shim behavior unchanged)

- [ ] **Step 3: Lint check**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/ruff check src/routes/expenses.py`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add src/routes/expenses.py
git commit -m "refactor: simplify expense shim to use skip_name=True

Remove fragile substring-based error filtering.

Refs #162"
```

---

### Task 3: Use parsed values in account route handlers

**Files:**
- Modify: `src/routes/accounts.py:50,94`

- [ ] **Step 1: Update `add_account` handler**

In `src/routes/accounts.py`, in `add_account`:

```python
# Before:
    validate_account(name).raise_if_invalid()
    user_id = get_user_id(request)

# After:
    result = validate_account(name)
    result.raise_if_invalid()
    name = result.parsed["name"]
    user_id = get_user_id(request)
```

- [ ] **Step 2: Update `edit_account` handler**

In `src/routes/accounts.py`, in `edit_account`:

```python
# Before:
    validate_account(name).raise_if_invalid()
    user_id = get_user_id(request)

# After:
    result = validate_account(name)
    result.raise_if_invalid()
    name = result.parsed["name"]
    user_id = get_user_id(request)
```

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -m pytest tests/ e2e/ -q 2>&1 | tail -40`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/routes/accounts.py
git commit -m "fix: use stripped name from validator in account routes

Ensures whitespace-padded names are stored stripped and
error messages show the cleaned value.

Refs #162"
```

---

### Task 4: Use parsed values in category route handlers

**Files:**
- Modify: `src/routes/categories.py:49,72`

- [ ] **Step 1: Update `add_category` handler**

In `src/routes/categories.py`, in `add_category`:

```python
# Before:
    validate_category(name, icon).raise_if_invalid()
    user_id = get_user_id(request)

# After:
    result = validate_category(name, icon)
    result.raise_if_invalid()
    name = result.parsed["name"]
    icon = result.parsed["icon"]
    user_id = get_user_id(request)
```

- [ ] **Step 2: Update `edit_category` handler**

In `src/routes/categories.py`, in `edit_category`:

```python
# Before:
    validate_category(name, icon).raise_if_invalid()
    user_id = get_user_id(request)

# After:
    result = validate_category(name, icon)
    result.raise_if_invalid()
    name = result.parsed["name"]
    icon = result.parsed["icon"]
    user_id = get_user_id(request)
```

- [ ] **Step 3: Run full test suite**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -m pytest tests/ e2e/ -q 2>&1 | tail -40`
Expected: All tests pass

- [ ] **Step 4: Lint check on all changed files**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/ruff check src/validators.py src/routes/expenses.py src/routes/accounts.py src/routes/categories.py`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add src/routes/categories.py
git commit -m "fix: use stripped values from validator in category routes

Ensures whitespace-padded names and icons are stored stripped
and error messages show the cleaned values.

Refs #162"
```
