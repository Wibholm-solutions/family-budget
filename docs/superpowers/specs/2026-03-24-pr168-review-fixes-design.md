# PR #168 Review Fixes — Design Spec

**Date:** 2026-03-24
**PR:** #168 (refactor: extract per-entity validators into src/validators.py)
**Scope:** Fix two code issues identified during review

---

## Fix 1: Use parsed (stripped) values from validators in routes

### Problem

Several routes call `validate_account(name).raise_if_invalid()` or `validate_category(name, icon).raise_if_invalid()` but then pass the original un-stripped `name`/`icon` to the database. The stripped values in `result.parsed` are discarded. This means whitespace like `"  Nordea  "` passes validation but gets stored with leading/trailing spaces.

The `add_account_json` route already does this correctly — it uses `result.parsed["name"]`.

### Solution

Change the pattern in 4 route handlers:

**`src/routes/accounts.py`** — `add_account` and `edit_account`:
```python
result = validate_account(name)
result.raise_if_invalid()
# use result.parsed["name"] instead of raw name
```

**`src/routes/categories.py`** — `add_category` and `edit_category`:
```python
result = validate_category(name, icon)
result.raise_if_invalid()
# use result.parsed["name"] and result.parsed["icon"] instead of raw values
```

### Files changed

- `src/routes/accounts.py` (2 handlers)
- `src/routes/categories.py` (2 handlers)

---

## Fix 2: Add `skip_name` parameter to `validate_expense`

### Problem

The `validate_expense_input` shim in `expenses.py` delegates to `validate_expense()` but filters out name-related errors using substring matching:

```python
non_name_errors = [e for e in result.errors if "navn" not in e.lower()]
```

This is fragile — if error messages change, the filter silently breaks.

### Solution

Add `skip_name: bool = False` parameter to `validate_expense()`. When `True`, skip the `_validate_name()` call entirely. Update the shim to pass `skip_name=True` and remove the substring filter.

### Files changed

- `src/validators.py` — add `skip_name` parameter to `validate_expense()`
- `src/routes/expenses.py` — simplify shim to use `skip_name=True`
- `tests/test_validators.py` — add test for `skip_name=True` behavior

---

## Out of scope

- Plan files (#160/#161) included in the PR diff — not addressed here
- Expense name validation in expense routes — separate concern
- Typed result classes for `parsed` dict — future improvement
