"""Tests for income split (distribution) feature."""

import sqlite3

import pytest


class TestIncomeSourceSchema:
    """Tests for multiple income sources per person."""

    def test_add_income_with_source(self, db_module):
        """Income entries should support a source field."""
        user_id = db_module.create_user("splituser1", "testpass")
        income_id = db_module.add_income(user_id, "Person 1", 25000, "monthly", "Løn")
        assert income_id is not None

        incomes = db_module.get_all_income(user_id)
        assert len(incomes) == 1
        assert incomes[0].person == "Person 1"
        assert incomes[0].source == "Løn"
        assert incomes[0].amount == 25000

    def test_multiple_sources_per_person(self, db_module):
        """Same person can have multiple income sources."""
        user_id = db_module.create_user("splituser2", "testpass")
        db_module.add_income(user_id, "Person 1", 25000, "monthly", "Løn")
        db_module.add_income(user_id, "Person 1", 2100, "quarterly", "Børnepenge")

        incomes = db_module.get_all_income(user_id)
        assert len(incomes) == 2
        person1 = [i for i in incomes if i.person == "Person 1"]
        assert len(person1) == 2
        sources = {i.source for i in person1}
        assert sources == {"Løn", "Børnepenge"}

    def test_unique_constraint_person_source(self, db_module):
        """Same person+source combination should be unique per user."""
        user_id = db_module.create_user("splituser3", "testpass")
        db_module.add_income(user_id, "Person 1", 25000, "monthly", "Løn")

        with pytest.raises(sqlite3.IntegrityError):
            db_module.add_income(user_id, "Person 1", 30000, "monthly", "Løn")


class TestSplitEnabled:
    """Tests for income split toggle."""

    def test_split_disabled_by_default(self, db_module):
        user_id = db_module.create_user("split_en1", "testpass")
        assert db_module.is_split_enabled(user_id) is False

    def test_enable_split(self, db_module):
        user_id = db_module.create_user("split_en2", "testpass")
        db_module.set_split_enabled(user_id, True)
        assert db_module.is_split_enabled(user_id) is True

    def test_disable_split(self, db_module):
        user_id = db_module.create_user("split_en3", "testpass")
        db_module.set_split_enabled(user_id, True)
        db_module.set_split_enabled(user_id, False)
        assert db_module.is_split_enabled(user_id) is False


class TestIncomeByPerson:
    """Tests for income grouped by person."""

    def test_income_by_person_single(self, db_module):
        user_id = db_module.create_user("ibp1", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        result = db_module.get_income_by_person(user_id)
        assert result == {"Alice": 30000.0}

    def test_income_by_person_multiple_sources(self, db_module):
        user_id = db_module.create_user("ibp2", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.add_income(user_id, "Alice", 6000, "quarterly", "Børnepenge")
        result = db_module.get_income_by_person(user_id)
        assert result == {"Alice": 32000.0}  # 30000 + 6000/3

    def test_income_by_person_two_persons(self, db_module):
        user_id = db_module.create_user("ibp3", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.add_income(user_id, "Bob", 20000, "monthly", "Løn")
        result = db_module.get_income_by_person(user_id)
        assert result == {"Alice": 30000.0, "Bob": 20000.0}


class TestSplitPercentages:
    """Tests for split percentage calculation."""

    def test_proportional_split_two_persons(self, db_module):
        user_id = db_module.create_user("sp1", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.add_income(user_id, "Bob", 20000, "monthly", "Løn")
        result = db_module.get_split_percentages(user_id)
        assert result == {"Alice": 60.0, "Bob": 40.0}

    def test_override_split(self, db_module):
        user_id = db_module.create_user("sp2", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.add_income(user_id, "Bob", 20000, "monthly", "Løn")
        db_module.set_split_override(user_id, "Alice", 55.0)
        db_module.set_split_override(user_id, "Bob", 45.0)
        result = db_module.get_split_percentages(user_id)
        assert result == {"Alice": 55.0, "Bob": 45.0}

    def test_empty_income_returns_empty(self, db_module):
        user_id = db_module.create_user("sp3", "testpass")
        result = db_module.get_split_percentages(user_id)
        assert result == {}

    def test_single_person_is_100(self, db_module):
        user_id = db_module.create_user("sp4", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        result = db_module.get_split_percentages(user_id)
        assert result == {"Alice": 100.0}


class TestTransferPlan:
    """Tests for transfer plan calculation."""

    def test_basic_transfer_plan(self, db_module):
        user_id = db_module.create_user("tp1", "testpass")
        # Income: Alice 60%, Bob 40%
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.add_income(user_id, "Bob", 20000, "monthly", "Løn")
        db_module.set_split_enabled(user_id, True)
        # Add account and expense
        db_module.add_account(user_id, "Budgetkonto")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly", "Budgetkonto")

        plan = db_module.get_transfer_plan(user_id)
        assert len(plan.persons) == 2

        alice = next(p for p in plan.persons if p.person == "Alice")
        bob = next(p for p in plan.persons if p.person == "Bob")

        # Alice: 60% of 10000 = 6000, Bob: 40% of 10000 = 4000
        alice_budget = next(t for t in alice.transfers if t.account == "Budgetkonto")
        bob_budget = next(t for t in bob.transfers if t.account == "Budgetkonto")
        assert alice_budget.amount == 6000
        assert bob_budget.amount == 4000

        # Available: Alice 30000-6000=24000, Bob 20000-4000=16000
        assert alice.available == 24000
        assert bob.available == 16000

    def test_rounding_remainder_to_largest_payer(self, db_module):
        user_id = db_module.create_user("tp2", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.add_income(user_id, "Bob", 20000, "monthly", "Løn")
        db_module.set_split_enabled(user_id, True)
        db_module.add_account(user_id, "Konto")
        # 10001 * 0.6 = 6000.6 -> 6000, 10001 * 0.4 = 4000.4 -> 4000
        # remainder = 10001 - 10000 = 1 -> goes to Alice (largest payer)
        db_module.add_expense(user_id, "Test", "Bolig", 10001, "monthly", "Konto")

        plan = db_module.get_transfer_plan(user_id)
        alice = next(p for p in plan.persons if p.person == "Alice")
        bob = next(p for p in plan.persons if p.person == "Bob")
        alice_amt = next(t for t in alice.transfers if t.account == "Konto").amount
        bob_amt = next(t for t in bob.transfers if t.account == "Konto").amount
        assert alice_amt + bob_amt == 10001
        # Alice is largest payer, gets the remainder
        assert alice_amt == 6001
        assert bob_amt == 4000

    def test_unassigned_expenses_in_plan(self, db_module):
        user_id = db_module.create_user("tp3", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.set_split_enabled(user_id, True)
        # Expenses without account
        db_module.add_expense(user_id, "Netflix", "Abonnementer", 129, "monthly")
        db_module.add_expense(user_id, "Spotify", "Abonnementer", 99, "monthly")

        plan = db_module.get_transfer_plan(user_id)
        assert plan.unassigned_count == 2
        assert "Netflix" in plan.unassigned_expenses
        assert "Spotify" in plan.unassigned_expenses


class TestUnassignedExpenses:
    """Tests for unassigned expense detection."""

    def test_no_unassigned(self, db_module):
        user_id = db_module.create_user("ue1", "testpass")
        db_module.add_account(user_id, "Konto")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly", "Konto")
        names, count = db_module.get_unassigned_expenses(user_id)
        assert names == []
        assert count == 0

    def test_some_unassigned(self, db_module):
        user_id = db_module.create_user("ue2", "testpass")
        db_module.add_expense(user_id, "Netflix", "Abonnementer", 129, "monthly")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly", "Budgetkonto")
        names, count = db_module.get_unassigned_expenses(user_id)
        assert count == 1
        assert names == ["Netflix"]

    def test_limit_unassigned(self, db_module):
        user_id = db_module.create_user("ue3", "testpass")
        for i in range(10):
            db_module.add_expense(user_id, f"Expense {i}", "Andet", 100, "monthly")
        names, count = db_module.get_unassigned_expenses(user_id, limit=5)
        assert count == 10
        assert len(names) == 5


class TestSplitIntegration:
    """Integration tests for income split full flow."""

    def test_full_flow_two_persons(self, db_module):
        """Full flow: add income, enable split, get transfer plan."""
        user_id = db_module.create_user("integ1", "testpass")

        # Add income
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.add_income(user_id, "Alice", 3000, "quarterly", "Børnepenge")
        db_module.add_income(user_id, "Bob", 20000, "monthly", "Løn")

        # Add accounts and expenses
        db_module.add_account(user_id, "Budgetkonto")
        db_module.add_account(user_id, "Madkonto")
        db_module.add_expense(user_id, "Husleje", "Bolig", 12000, "monthly", "Budgetkonto")
        db_module.add_expense(user_id, "Dagligvarer", "Mad", 6000, "monthly", "Madkonto")
        db_module.add_expense(user_id, "Netflix", "Abonnementer", 129, "monthly")  # No account

        # Enable split
        db_module.set_split_enabled(user_id, True)

        # Get plan
        plan = db_module.get_transfer_plan(user_id)
        assert len(plan.persons) == 2
        assert plan.unassigned_count == 1
        assert "Netflix" in plan.unassigned_expenses

        # Verify amounts sum correctly per account
        for account_name in ["Budgetkonto", "Madkonto"]:
            total = sum(
                t.amount
                for p in plan.persons
                for t in p.transfers
                if t.account == account_name
            )
            # Account total should match expense total for that account
            account_totals = db_module.get_account_totals(user_id)
            assert total == int(round(account_totals[account_name]))

    def test_single_person_split(self, db_module):
        """Single person gets 100% of everything."""
        user_id = db_module.create_user("integ2", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.set_split_enabled(user_id, True)
        db_module.add_account(user_id, "Konto")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly", "Konto")

        plan = db_module.get_transfer_plan(user_id)
        assert len(plan.persons) == 1
        assert plan.persons[0].person == "Alice"
        assert plan.persons[0].transfers[0].amount == 10000
        assert plan.persons[0].available == 20000

    def test_no_accounts_empty_plan(self, db_module):
        """No accounts means empty transfers but plan still works."""
        user_id = db_module.create_user("integ3", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.set_split_enabled(user_id, True)

        plan = db_module.get_transfer_plan(user_id)
        assert len(plan.persons) == 1
        assert plan.persons[0].transfers == []
        assert plan.persons[0].total_transfer == 0
        assert plan.persons[0].available == 30000

    def test_zero_income_empty_percentages(self, db_module):
        """Zero income returns empty percentages."""
        user_id = db_module.create_user("integ4", "testpass")
        result = db_module.get_split_percentages(user_id)
        assert result == {}

    def test_override_persists_after_toggle(self, db_module):
        """Overrides should persist when toggling split off and on."""
        user_id = db_module.create_user("integ5", "testpass")
        db_module.add_income(user_id, "Alice", 30000, "monthly", "Løn")
        db_module.add_income(user_id, "Bob", 20000, "monthly", "Løn")
        db_module.set_split_override(user_id, "Alice", 55.0)
        db_module.set_split_override(user_id, "Bob", 45.0)

        db_module.set_split_enabled(user_id, False)
        db_module.set_split_enabled(user_id, True)

        result = db_module.get_split_percentages(user_id)
        assert result == {"Alice": 55.0, "Bob": 45.0}
