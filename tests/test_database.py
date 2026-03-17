"""Unit tests for database operations."""




class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_hash_and_salt(self, db_module):
        """hash_password should return a hash and salt."""
        password_hash, salt = db_module.hash_password("testpassword")

        assert password_hash is not None
        assert salt is not None
        assert len(password_hash) == 64  # SHA-256 hex = 64 chars
        assert len(salt) == 64  # 32 bytes hex = 64 chars

    def test_hash_password_with_same_salt_produces_same_hash(self, db_module):
        """Same password + salt should produce identical hash."""
        _, salt = db_module.hash_password("testpassword")
        salt_bytes = bytes.fromhex(salt)

        hash1, _ = db_module.hash_password("testpassword", salt_bytes)
        hash2, _ = db_module.hash_password("testpassword", salt_bytes)

        assert hash1 == hash2

    def test_different_passwords_produce_different_hashes(self, db_module):
        """Different passwords should produce different hashes."""
        _, salt = db_module.hash_password("password1")
        salt_bytes = bytes.fromhex(salt)

        hash1, _ = db_module.hash_password("password1", salt_bytes)
        hash2, _ = db_module.hash_password("password2", salt_bytes)

        assert hash1 != hash2

    def test_verify_password_correct(self, db_module):
        """verify_password should return True for correct password."""
        password_hash, salt = db_module.hash_password("mypassword")

        assert db_module.verify_password("mypassword", password_hash, salt) is True

    def test_verify_password_incorrect(self, db_module):
        """verify_password should return False for wrong password."""
        password_hash, salt = db_module.hash_password("mypassword")

        assert db_module.verify_password("wrongpassword", password_hash, salt) is False


class TestIncomeOperations:
    """Tests for income CRUD operations."""

    def test_get_all_income_empty_for_new_user(self, db_module):
        """New user should have no income entries."""
        user_id = db_module.create_user("incometest1", "testpass")
        incomes = db_module.get_all_income(user_id)

        assert len(incomes) == 0

    def test_add_income(self, db_module):
        """add_income should create a new income entry."""
        user_id = db_module.create_user("incometest2", "testpass")
        income_id = db_module.add_income(user_id, "Person 1", 30000)

        assert income_id is not None
        incomes = db_module.get_all_income(user_id)
        assert len(incomes) == 1
        assert incomes[0].person == "Person 1"
        assert incomes[0].amount == 30000
        assert incomes[0].frequency == "monthly"
        assert incomes[0].monthly_amount == 30000

    def test_add_income_with_frequency(self, db_module):
        """add_income should support different frequencies."""
        user_id = db_module.create_user("incometest2a", "testpass")
        db_module.add_income(user_id, "Quarterly Bonus", 9000, "quarterly")

        incomes = db_module.get_all_income(user_id)
        assert incomes[0].amount == 9000
        assert incomes[0].frequency == "quarterly"
        assert incomes[0].monthly_amount == 3000  # 9000 / 3

    def test_update_income(self, db_module):
        """update_income should change the amount or create if not exists."""
        user_id = db_module.create_user("incometest3", "testpass")
        db_module.update_income(user_id, "Alice", 35000)

        incomes = db_module.get_all_income(user_id)
        alice_income = next((i for i in incomes if i.person == "Alice"), None)
        assert alice_income is not None
        assert alice_income.amount == 35000
        assert alice_income.monthly_amount == 35000

    def test_update_income_with_frequency(self, db_module):
        """update_income should handle frequency."""
        user_id = db_module.create_user("incometest3a", "testpass")
        db_module.update_income(user_id, "Yearly Dividend", 12000, "yearly")

        incomes = db_module.get_all_income(user_id)
        inc = next(i for i in incomes if i.person == "Yearly Dividend")
        assert inc.amount == 12000
        assert inc.frequency == "yearly"
        assert inc.monthly_amount == 1000  # 12000 / 12

    def test_get_total_income(self, db_module):
        """get_total_income should sum all income entries with frequency conversion."""
        user_id = db_module.create_user("incometest4", "testpass")
        db_module.update_income(user_id, "Alice", 30000, "monthly")  # 30000/month
        db_module.update_income(user_id, "Bob", 12000, "yearly")  # 1000/month

        total = db_module.get_total_income(user_id)
        assert total == 31000  # 30000 + 1000

    def test_income_monthly_amount_quarterly(self, db_module):
        """Income monthly_amount should divide by 3 for quarterly."""
        user_id = db_module.create_user("incometest4a", "testpass")
        db_module.add_income(user_id, "Quarterly", 9000, "quarterly")

        incomes = db_module.get_all_income(user_id)
        assert incomes[0].monthly_amount == 3000

    def test_income_monthly_amount_semiannual(self, db_module):
        """Income monthly_amount should divide by 6 for semi-annual."""
        user_id = db_module.create_user("incometest4b", "testpass")
        db_module.add_income(user_id, "Semi-Annual", 12000, "semi-annual")

        incomes = db_module.get_all_income(user_id)
        assert incomes[0].monthly_amount == 2000  # 12000 / 6

    def test_income_isolation_between_users(self, db_module):
        """Each user should only see their own income."""
        user1 = db_module.create_user("incometest5a", "testpass")
        user2 = db_module.create_user("incometest5b", "testpass")

        db_module.add_income(user1, "User1 Income", 50000)
        db_module.add_income(user2, "User2 Income", 40000)

        incomes1 = db_module.get_all_income(user1)
        incomes2 = db_module.get_all_income(user2)

        assert len(incomes1) == 1
        assert len(incomes2) == 1
        assert incomes1[0].person == "User1 Income"
        assert incomes2[0].person == "User2 Income"


class TestExpenseOperations:
    """Tests for expense CRUD operations."""

    def test_add_expense(self, db_module):
        """add_expense should create a new expense."""
        user_id = db_module.create_user("expensetest1", "testpass")
        expense_id = db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly")

        assert expense_id is not None
        expense = db_module.get_expense_by_id(expense_id, user_id)
        assert expense.name == "Husleje"
        assert expense.category == "Bolig"
        assert expense.amount == 10000
        assert expense.frequency == "monthly"

    def test_expense_monthly_amount_for_monthly(self, db_module):
        """monthly_amount should return same amount for monthly expenses."""
        user_id = db_module.create_user("expensetest2", "testpass")
        expense_id = db_module.add_expense(user_id, "Test", "Bolig", 1000, "monthly")
        expense = db_module.get_expense_by_id(expense_id, user_id)

        assert expense.monthly_amount == 1000

    def test_expense_monthly_amount_for_yearly(self, db_module):
        """monthly_amount should divide by 12 for yearly expenses."""
        user_id = db_module.create_user("expensetest3", "testpass")
        expense_id = db_module.add_expense(user_id, "Forsikring", "Forsikring", 12000, "yearly")
        expense = db_module.get_expense_by_id(expense_id, user_id)

        assert expense.monthly_amount == 1000  # 12000 / 12

    def test_expense_monthly_amount_for_quarterly(self, db_module):
        """monthly_amount should divide by 3 for quarterly expenses."""
        user_id = db_module.create_user("expensetest3a", "testpass")
        expense_id = db_module.add_expense(user_id, "Vand", "Forbrug", 2400, "quarterly")
        expense = db_module.get_expense_by_id(expense_id, user_id)

        assert expense.monthly_amount == 800  # 2400 / 3

    def test_expense_monthly_amount_for_semiannual(self, db_module):
        """monthly_amount should divide by 6 for semi-annual expenses."""
        user_id = db_module.create_user("expensetest3b", "testpass")
        expense_id = db_module.add_expense(user_id, "Bilservice", "Transport", 4500, "semi-annual")
        expense = db_module.get_expense_by_id(expense_id, user_id)

        assert expense.monthly_amount == 750  # 4500 / 6

    def test_update_expense(self, db_module):
        """update_expense should modify existing expense."""
        user_id = db_module.create_user("expensetest4", "testpass")
        expense_id = db_module.add_expense(user_id, "Old Name", "Bolig", 5000, "monthly")
        db_module.update_expense(expense_id, user_id, "New Name", "Transport", 6000, "yearly")

        expense = db_module.get_expense_by_id(expense_id, user_id)
        assert expense.name == "New Name"
        assert expense.category == "Transport"
        assert expense.amount == 6000
        assert expense.frequency == "yearly"

    def test_delete_expense(self, db_module):
        """delete_expense should remove the expense."""
        user_id = db_module.create_user("expensetest5", "testpass")
        expense_id = db_module.add_expense(user_id, "To Delete", "Bolig", 1000, "monthly")
        db_module.delete_expense(expense_id, user_id)

        expense = db_module.get_expense_by_id(expense_id, user_id)
        assert expense is None

    def test_get_total_monthly_expenses(self, db_module):
        """get_total_monthly_expenses should calculate correct total with all frequencies."""
        user_id = db_module.create_user("expensetest6", "testpass")
        db_module.add_expense(user_id, "Monthly", "Bolig", 1000, "monthly")  # 1000/month
        db_module.add_expense(user_id, "Quarterly", "Forbrug", 900, "quarterly")  # 300/month
        db_module.add_expense(user_id, "Semi-Annual", "Transport", 600, "semi-annual")  # 100/month
        db_module.add_expense(user_id, "Yearly", "Forsikring", 1200, "yearly")  # 100/month

        total = db_module.get_total_monthly_expenses(user_id)
        assert total == 1500  # 1000 + 300 + 100 + 100

    def test_get_expenses_by_category(self, db_module):
        """get_expenses_by_category should group expenses correctly."""
        user_id = db_module.create_user("expensetest7", "testpass")
        db_module.add_expense(user_id, "Expense 1", "Bolig", 1000, "monthly")
        db_module.add_expense(user_id, "Expense 2", "Bolig", 2000, "monthly")
        db_module.add_expense(user_id, "Expense 3", "Transport", 500, "monthly")

        grouped = db_module.get_expenses_by_category(user_id)

        assert len(grouped["Bolig"]) == 2
        assert len(grouped["Transport"]) == 1

    def test_get_category_totals(self, db_module):
        """get_category_totals should sum monthly amounts per category."""
        user_id = db_module.create_user("expensetest8", "testpass")
        db_module.add_expense(user_id, "Rent", "Bolig", 10000, "monthly")
        db_module.add_expense(user_id, "Tax", "Bolig", 12000, "yearly")  # 1000/month

        totals = db_module.get_category_totals(user_id)

        assert totals["Bolig"] == 11000  # 10000 + 1000

    def test_expense_isolation_between_users(self, db_module):
        """Each user should only see their own expenses."""
        user1 = db_module.create_user("expensetest9a", "testpass")
        user2 = db_module.create_user("expensetest9b", "testpass")

        db_module.add_expense(user1, "User1 Expense", "Bolig", 5000, "monthly")
        db_module.add_expense(user2, "User2 Expense", "Bolig", 3000, "monthly")

        expenses1 = db_module.get_all_expenses(user1)
        expenses2 = db_module.get_all_expenses(user2)

        assert len(expenses1) == 1
        assert len(expenses2) == 1
        assert expenses1[0].name == "User1 Expense"
        assert expenses2[0].name == "User2 Expense"


class TestCategoryOperations:
    """Tests for category CRUD operations."""

    def test_default_categories_exist(self, db_module):
        """Database should have default categories for demo user."""
        # Demo user (user_id = 0) should have default categories
        categories = db_module.get_all_categories(0)

        names = {c.name for c in categories}
        assert "Bolig" in names
        assert "Transport" in names
        assert "Mad" in names

    def test_add_category(self, db_module):
        """add_category should create a new category for a user."""
        user_id = db_module.create_user("catuser1", "testpass")
        category_id = db_module.add_category(user_id, "Custom", "star")

        category = db_module.get_category_by_id(category_id)
        assert category.name == "Custom"
        assert category.icon == "star"

    def test_update_category(self, db_module):
        """update_category should modify existing category for a user."""
        user_id = db_module.create_user("catuser2", "testpass")
        category_id = db_module.add_category(user_id, "OldName", "old-icon")
        db_module.update_category(category_id, user_id, "NewName", "new-icon")

        category = db_module.get_category_by_id(category_id)
        assert category.name == "NewName"
        assert category.icon == "new-icon"

    def test_update_category_updates_expenses(self, db_module):
        """Renaming a category should update expenses using it."""
        user_id = db_module.create_user("cattest1", "testpass")
        category_id = db_module.add_category(user_id, "OldCat", "icon")
        db_module.add_expense(user_id, "Test Expense", "OldCat", 100, "monthly")

        db_module.update_category(category_id, user_id, "NewCat", "icon")

        expenses = db_module.get_all_expenses(user_id)
        expense = next(e for e in expenses if e.name == "Test Expense")
        assert expense.category == "NewCat"

    def test_update_category_returns_count(self, db_module):
        """update_category should return the number of updated expenses."""
        user_id = db_module.create_user("catcount1", "testpass")
        category_id = db_module.add_category(user_id, "CountCat", "icon")
        db_module.add_expense(user_id, "Expense 1", "CountCat", 50, "monthly")
        db_module.add_expense(user_id, "Expense 2", "CountCat", 75, "monthly")

        # Rename should return 2 (two expenses updated)
        count = db_module.update_category(category_id, user_id, "RenamedCat", "icon")
        assert count == 2

        # Icon-only change (no rename) should return 0
        count = db_module.update_category(category_id, user_id, "RenamedCat", "new-icon")
        assert count == 0

    def test_delete_category_not_in_use(self, db_module):
        """delete_category should work when category is not in use."""
        user_id = db_module.create_user("catuser3", "testpass")
        category_id = db_module.add_category(user_id, "Unused", "icon")

        result = db_module.delete_category(category_id, user_id)

        assert result is True
        assert db_module.get_category_by_id(category_id) is None

    def test_delete_category_in_use_fails(self, db_module):
        """delete_category should fail when category has expenses."""
        user_id = db_module.create_user("cattest2", "testpass")
        category_id = db_module.add_category(user_id, "InUse", "icon")
        db_module.add_expense(user_id, "Uses Category", "InUse", 100, "monthly")

        result = db_module.delete_category(category_id, user_id)

        assert result is False
        assert db_module.get_category_by_id(category_id) is not None

    def test_get_category_usage_count(self, db_module):
        """get_category_usage_count should return correct count for specific user."""
        user_id = db_module.create_user("cattest3", "testpass")
        db_module.add_category(user_id, "TestCat", "icon")
        db_module.add_expense(user_id, "Exp1", "TestCat", 100, "monthly")
        db_module.add_expense(user_id, "Exp2", "TestCat", 200, "monthly")

        count = db_module.get_category_usage_count("TestCat", user_id)
        assert count == 2

    def test_get_category_usage_count_user_isolation(self, db_module):
        """get_category_usage_count should only count expenses for the specified user."""
        user1 = db_module.create_user("catuser1", "testpass")
        user2 = db_module.create_user("catuser2", "testpass")
        # Each user gets their own categories automatically
        db_module.add_category(user1, "SharedCat", "icon")
        db_module.add_category(user2, "SharedCat", "icon")

        # User 1 has 3 expenses
        db_module.add_expense(user1, "Exp1", "SharedCat", 100, "monthly")
        db_module.add_expense(user1, "Exp2", "SharedCat", 200, "monthly")
        db_module.add_expense(user1, "Exp3", "SharedCat", 300, "monthly")

        # User 2 has 1 expense
        db_module.add_expense(user2, "Exp4", "SharedCat", 400, "monthly")

        # Each user should only see their own count
        assert db_module.get_category_usage_count("SharedCat", user1) == 3
        assert db_module.get_category_usage_count("SharedCat", user2) == 1


class TestAccountOperations:
    """Tests for account CRUD operations."""

    def test_add_account(self, db_module):
        """add_account should create a new account for a user."""
        user_id = db_module.create_user("accuser1", "testpass")
        account_id = db_module.add_account(user_id, "Lønkonto")

        account = db_module.get_account_by_id(account_id, user_id)
        assert account.name == "Lønkonto"

    def test_get_all_accounts(self, db_module):
        """get_all_accounts should return all accounts for a user."""
        user_id = db_module.create_user("accuser2", "testpass")
        db_module.add_account(user_id, "Lønkonto")
        db_module.add_account(user_id, "Budgetkonto")

        accounts = db_module.get_all_accounts(user_id)
        names = {a.name for a in accounts}
        assert names == {"Lønkonto", "Budgetkonto"}

    def test_update_account(self, db_module):
        """update_account should modify existing account for a user."""
        user_id = db_module.create_user("accuser3", "testpass")
        account_id = db_module.add_account(user_id, "OldName")
        db_module.update_account(account_id, user_id, "NewName")

        account = db_module.get_account_by_id(account_id, user_id)
        assert account.name == "NewName"

    def test_update_account_updates_expenses(self, db_module):
        """Renaming an account should update expenses using it."""
        user_id = db_module.create_user("acctest1", "testpass")
        account_id = db_module.add_account(user_id, "OldAcc")
        db_module.add_expense(user_id, "Test Expense", "Bolig", 100, "monthly", "OldAcc")

        db_module.update_account(account_id, user_id, "NewAcc")

        expenses = db_module.get_all_expenses(user_id)
        expense = next(e for e in expenses if e.name == "Test Expense")
        assert expense.account == "NewAcc"

    def test_update_account_returns_count(self, db_module):
        """update_account should return the number of updated expenses."""
        user_id = db_module.create_user("acccount1", "testpass")
        account_id = db_module.add_account(user_id, "CountAcc")
        db_module.add_expense(user_id, "Exp 1", "Bolig", 50, "monthly", "CountAcc")
        db_module.add_expense(user_id, "Exp 2", "Bolig", 75, "monthly", "CountAcc")

        # Rename should return 2 (two expenses updated)
        count = db_module.update_account(account_id, user_id, "RenamedAcc")
        assert count == 2

        # Same name (no rename) should return 0
        count = db_module.update_account(account_id, user_id, "RenamedAcc")
        assert count == 0

    def test_delete_account_not_in_use(self, db_module):
        """delete_account should work when account is not in use."""
        user_id = db_module.create_user("accuser4", "testpass")
        account_id = db_module.add_account(user_id, "Unused")

        result = db_module.delete_account(account_id, user_id)

        assert result is True
        assert db_module.get_account_by_id(account_id, user_id) is None

    def test_delete_account_in_use_fails(self, db_module):
        """delete_account should fail when account has expenses."""
        user_id = db_module.create_user("acctest2", "testpass")
        account_id = db_module.add_account(user_id, "InUse")
        db_module.add_expense(user_id, "Uses Account", "Bolig", 100, "monthly", "InUse")

        result = db_module.delete_account(account_id, user_id)

        assert result is False
        assert db_module.get_account_by_id(account_id, user_id) is not None

    def test_get_account_usage_count(self, db_module):
        """get_account_usage_count should return correct count for specific user."""
        user_id = db_module.create_user("acctest3", "testpass")
        db_module.add_account(user_id, "TestAcc")
        db_module.add_expense(user_id, "Exp1", "Bolig", 100, "monthly", "TestAcc")
        db_module.add_expense(user_id, "Exp2", "Bolig", 200, "monthly", "TestAcc")

        count = db_module.get_account_usage_count("TestAcc", user_id)
        assert count == 2

    def test_get_account_usage_count_user_isolation(self, db_module):
        """get_account_usage_count should only count expenses for the specified user."""
        user1 = db_module.create_user("acciso1", "testpass")
        user2 = db_module.create_user("acciso2", "testpass")
        db_module.add_account(user1, "SharedAcc")
        db_module.add_account(user2, "SharedAcc")

        db_module.add_expense(user1, "Exp1", "Bolig", 100, "monthly", "SharedAcc")
        db_module.add_expense(user1, "Exp2", "Bolig", 200, "monthly", "SharedAcc")
        db_module.add_expense(user2, "Exp3", "Bolig", 300, "monthly", "SharedAcc")

        assert db_module.get_account_usage_count("SharedAcc", user1) == 2
        assert db_module.get_account_usage_count("SharedAcc", user2) == 1

    def test_get_account_totals(self, db_module):
        """get_account_totals should return monthly totals per account."""
        user_id = db_module.create_user("acctotal1", "testpass")
        db_module.add_account(user_id, "Lønkonto")
        db_module.add_account(user_id, "Budgetkonto")

        db_module.add_expense(user_id, "Husleje", "Bolig", 12000, "monthly", "Budgetkonto")
        db_module.add_expense(user_id, "El", "Forbrug", 600, "monthly", "Budgetkonto")
        db_module.add_expense(user_id, "Netflix", "Abonnementer", 129, "monthly", "Lønkonto")
        db_module.add_expense(user_id, "Ingen konto", "Andet", 500, "monthly")  # No account

        totals = db_module.get_account_totals(user_id)
        assert totals["Budgetkonto"] == 12600
        assert totals["Lønkonto"] == 129
        assert "Ingen konto" not in totals  # Expenses without account excluded

    def test_get_account_totals_with_frequencies(self, db_module):
        """get_account_totals should convert all frequencies to monthly."""
        user_id = db_module.create_user("acctotal2", "testpass")
        db_module.add_account(user_id, "Budget")

        db_module.add_expense(user_id, "Monthly", "Bolig", 1200, "monthly", "Budget")
        db_module.add_expense(user_id, "Yearly", "Bolig", 12000, "yearly", "Budget")

        totals = db_module.get_account_totals(user_id)
        assert totals["Budget"] == 2200  # 1200 + 12000/12

    def test_expense_account_is_optional(self, db_module):
        """Expenses should work with and without an account."""
        user_id = db_module.create_user("accopt1", "testpass")

        # Add expense without account
        exp_id = db_module.add_expense(user_id, "No Account", "Bolig", 100, "monthly")
        expense = db_module.get_expense_by_id(exp_id, user_id)
        assert expense.account is None

        # Add expense with account
        db_module.add_account(user_id, "TestAcc")
        exp_id2 = db_module.add_expense(user_id, "With Account", "Bolig", 200, "monthly", "TestAcc")
        expense2 = db_module.get_expense_by_id(exp_id2, user_id)
        assert expense2.account == "TestAcc"


class TestUserOperations:
    """Tests for user CRUD and authentication."""

    def test_create_user(self, db_module):
        """create_user should create a new user."""
        user_id = db_module.create_user("newuser", "password123")

        assert user_id is not None
        user = db_module.get_user_by_username("newuser")
        assert user is not None
        assert user.username == "newuser"

    def test_create_user_duplicate_fails(self, db_module):
        """create_user should return None for duplicate username."""
        db_module.create_user("duplicate", "pass1")
        result = db_module.create_user("duplicate", "pass2")

        assert result is None

    def test_create_user_case_insensitive(self, db_module):
        """Username should be case-insensitive for uniqueness."""
        db_module.create_user("TestUser", "pass1")
        result = db_module.create_user("testuser", "pass2")

        assert result is None

    def test_authenticate_user_correct(self, db_module):
        """authenticate_user should return user for correct credentials."""
        db_module.create_user("authuser", "correctpass")

        user = db_module.authenticate_user("authuser", "correctpass")

        assert user is not None
        assert user.username == "authuser"

    def test_authenticate_user_wrong_password(self, db_module):
        """authenticate_user should return None for wrong password."""
        db_module.create_user("authuser2", "correctpass")

        user = db_module.authenticate_user("authuser2", "wrongpass")

        assert user is None

    def test_authenticate_user_unknown_user(self, db_module):
        """authenticate_user should return None for unknown user."""
        user = db_module.authenticate_user("unknown", "anypass")

        assert user is None

    def test_get_user_count(self, db_module):
        """get_user_count should return correct count."""
        initial_count = db_module.get_user_count()

        db_module.create_user("user1x", "pass")
        db_module.create_user("user2x", "pass")

        assert db_module.get_user_count() == initial_count + 2


class TestDemoData:
    """Tests for demo data functions."""

    def test_get_demo_income(self, db_module):
        """get_demo_income should return demo income entries with frequencies."""
        incomes = db_module.get_demo_income()

        assert len(incomes) == 3  # Person 1, Person 2, Bonus
        assert all(i.monthly_amount > 0 for i in incomes)
        # Verify frequency support
        frequencies = {i.frequency for i in incomes}
        assert "monthly" in frequencies
        assert "semi-annual" in frequencies  # Bonus is semi-annual

    def test_get_demo_total_income(self, db_module):
        """get_demo_total_income should return positive total with frequency conversion."""
        total = db_module.get_demo_total_income()

        assert total > 0
        assert total == sum(i.monthly_amount for i in db_module.get_demo_income())

    def test_get_demo_expenses(self, db_module):
        """get_demo_expenses should return demo expenses with all frequencies."""
        expenses = db_module.get_demo_expenses()

        assert len(expenses) > 0
        assert all(e.amount > 0 for e in expenses)
        # Verify all frequency types are represented
        frequencies = {e.frequency for e in expenses}
        assert "monthly" in frequencies
        assert "quarterly" in frequencies  # Vand, Tandlægeforsikring
        assert "semi-annual" in frequencies  # Bilservice
        assert "yearly" in frequencies  # Ejendomsskat, etc.

    def test_get_demo_total_expenses(self, db_module):
        """get_demo_total_expenses should return positive total."""
        total = db_module.get_demo_total_expenses()

        assert total > 0

    def test_demo_data_is_read_only(self, db_module):
        """Demo data should be independent of database state."""
        # Add real expense (need user first)
        user_id = db_module.create_user("demotest1", "testpass")
        db_module.add_expense(user_id, "Real Expense", "Bolig", 99999, "monthly")

        # Demo data should not include it
        demo_expenses = db_module.get_demo_expenses()
        names = {e.name for e in demo_expenses}

        assert "Real Expense" not in names


class TestEmailHashing:
    """Tests for email hashing function."""

    def test_hash_email_returns_hex_string(self, db_module):
        """hash_email should return a SHA-256 hex string."""
        email_hash = db_module.hash_email("test@example.com")

        assert email_hash is not None
        assert len(email_hash) == 64  # SHA-256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in email_hash)

    def test_hash_email_is_case_insensitive(self, db_module):
        """hash_email should produce same hash regardless of case."""
        hash1 = db_module.hash_email("Test@Example.COM")
        hash2 = db_module.hash_email("test@example.com")
        hash3 = db_module.hash_email("TEST@EXAMPLE.COM")

        assert hash1 == hash2 == hash3

    def test_hash_email_strips_whitespace(self, db_module):
        """hash_email should strip leading/trailing whitespace."""
        hash1 = db_module.hash_email("test@example.com")
        hash2 = db_module.hash_email("  test@example.com  ")
        hash3 = db_module.hash_email("\ttest@example.com\n")

        assert hash1 == hash2 == hash3

    def test_hash_email_different_emails_produce_different_hashes(self, db_module):
        """Different emails should produce different hashes."""
        hash1 = db_module.hash_email("user1@example.com")
        hash2 = db_module.hash_email("user2@example.com")

        assert hash1 != hash2


class TestUserEmailOperations:
    """Tests for user email update and lookup operations."""

    def test_update_user_email_stores_hash(self, db_module):
        """update_user_email should store email hash for user."""
        user_id = db_module.create_user("emailuser1", "testpass")

        db_module.update_user_email(user_id, "user@example.com")

        user = db_module.get_user_by_id(user_id)
        assert user.email_hash is not None

    def test_update_user_email_clears_email_when_empty(self, db_module):
        """update_user_email should clear email when passed empty value."""
        user_id = db_module.create_user("emailuser2", "testpass")
        db_module.update_user_email(user_id, "user@example.com")

        # Clear email
        db_module.update_user_email(user_id, None)

        user = db_module.get_user_by_id(user_id)
        assert user.email_hash is None

    def test_update_user_email_clears_with_empty_string(self, db_module):
        """update_user_email should clear when email is empty string."""
        user_id = db_module.create_user("emailuser3", "testpass")
        db_module.update_user_email(user_id, "user@example.com")

        # Clear email with empty string
        db_module.update_user_email(user_id, "")

        user = db_module.get_user_by_id(user_id)
        assert user.email_hash is None

    def test_get_user_by_email_returns_user(self, db_module):
        """get_user_by_email should return user with matching email."""
        user_id = db_module.create_user("emailuser4", "testpass")
        db_module.update_user_email(user_id, "findme@example.com")

        found_user = db_module.get_user_by_email("findme@example.com")

        assert found_user is not None
        assert found_user.id == user_id
        assert found_user.username == "emailuser4"

    def test_get_user_by_email_is_case_insensitive(self, db_module):
        """get_user_by_email should find user regardless of email case."""
        user_id = db_module.create_user("emailuser5", "testpass")
        db_module.update_user_email(user_id, "CaseSensitive@Example.COM")

        # Should find with different case
        found_user = db_module.get_user_by_email("casesensitive@example.com")

        assert found_user is not None
        assert found_user.id == user_id

    def test_get_user_by_email_strips_whitespace(self, db_module):
        """get_user_by_email should find user even with whitespace in query."""
        user_id = db_module.create_user("emailuser6", "testpass")
        db_module.update_user_email(user_id, "test@example.com")

        # Should find with whitespace
        found_user = db_module.get_user_by_email("  test@example.com  ")

        assert found_user is not None
        assert found_user.id == user_id

    def test_get_user_by_email_returns_none_for_nonexistent(self, db_module):
        """get_user_by_email should return None for unknown email."""
        found_user = db_module.get_user_by_email("nobody@example.com")

        assert found_user is None

    def test_get_user_by_email_returns_none_for_user_without_email(self, db_module):
        """get_user_by_email should not find users without email set."""
        db_module.create_user("noemailuser", "testpass")

        found_user = db_module.get_user_by_email("noemailuser@example.com")

        assert found_user is None

    def test_user_has_email_returns_true_when_set(self, db_module):
        """User.has_email() should return True when email is set."""
        user_id = db_module.create_user("hasemailuser", "testpass")
        db_module.update_user_email(user_id, "has@example.com")

        user = db_module.get_user_by_id(user_id)

        assert user.has_email() is True

    def test_user_has_email_returns_false_when_not_set(self, db_module):
        """User.has_email() should return False when email is not set."""
        user_id = db_module.create_user("noemailuser2", "testpass")

        user = db_module.get_user_by_id(user_id)

        assert user.has_email() is False


class TestPasswordResetTokens:
    """Tests for password reset token operations."""

    def test_create_password_reset_token_returns_id(self, db_module):
        """create_password_reset_token should return a token ID."""
        user_id = db_module.create_user("resetuser1", "testpass")
        token_hash = "abc123hash"
        expires_at = "2099-12-31 23:59:59"

        token_id = db_module.create_password_reset_token(user_id, token_hash, expires_at)

        assert token_id is not None
        assert isinstance(token_id, int)

    def test_create_password_reset_token_invalidates_old_tokens(self, db_module):
        """create_password_reset_token should invalidate previous tokens."""
        user_id = db_module.create_user("resetuser2", "testpass")
        expires_at = "2099-12-31 23:59:59"

        # Create first token
        db_module.create_password_reset_token(user_id, "firsthash", expires_at)

        # Create second token (should invalidate first)
        db_module.create_password_reset_token(user_id, "secondhash", expires_at)

        # First token should now be invalid (used=1)
        first_token = db_module.get_valid_reset_token("firsthash")
        second_token = db_module.get_valid_reset_token("secondhash")

        assert first_token is None  # Invalidated
        assert second_token is not None  # Still valid

    def test_get_valid_reset_token_returns_token(self, db_module):
        """get_valid_reset_token should return valid token."""
        user_id = db_module.create_user("resetuser3", "testpass")
        token_hash = "validhash123"
        expires_at = "2099-12-31 23:59:59"

        db_module.create_password_reset_token(user_id, token_hash, expires_at)
        token = db_module.get_valid_reset_token(token_hash)

        assert token is not None
        assert token.user_id == user_id
        assert token.token_hash == token_hash
        assert token.used is False

    def test_get_valid_reset_token_returns_none_for_unknown(self, db_module):
        """get_valid_reset_token should return None for unknown hash."""
        token = db_module.get_valid_reset_token("unknownhash")

        assert token is None

    def test_get_valid_reset_token_returns_none_for_expired(self, db_module):
        """get_valid_reset_token should return None for expired token."""
        user_id = db_module.create_user("resetuser4", "testpass")
        token_hash = "expiredhash"
        expires_at = "2000-01-01 00:00:00"  # Already expired

        db_module.create_password_reset_token(user_id, token_hash, expires_at)
        token = db_module.get_valid_reset_token(token_hash)

        assert token is None

    def test_get_valid_reset_token_returns_none_for_used(self, db_module):
        """get_valid_reset_token should return None for used token."""
        user_id = db_module.create_user("resetuser5", "testpass")
        token_hash = "usedhash"
        expires_at = "2099-12-31 23:59:59"

        token_id = db_module.create_password_reset_token(user_id, token_hash, expires_at)
        db_module.mark_reset_token_used(token_id)

        token = db_module.get_valid_reset_token(token_hash)

        assert token is None

    def test_mark_reset_token_used(self, db_module):
        """mark_reset_token_used should mark token as used."""
        user_id = db_module.create_user("resetuser6", "testpass")
        token_hash = "markusedhash"
        expires_at = "2099-12-31 23:59:59"

        token_id = db_module.create_password_reset_token(user_id, token_hash, expires_at)

        # Token should be valid before marking
        assert db_module.get_valid_reset_token(token_hash) is not None

        db_module.mark_reset_token_used(token_id)

        # Token should be invalid after marking
        assert db_module.get_valid_reset_token(token_hash) is None

    def test_update_user_password(self, db_module):
        """update_user_password should change user's password."""
        user_id = db_module.create_user("resetuser7", "oldpassword")

        # Verify old password works
        assert db_module.authenticate_user("resetuser7", "oldpassword") is not None

        # Update password
        db_module.update_user_password(user_id, "newpassword")

        # Old password should fail, new should work
        assert db_module.authenticate_user("resetuser7", "oldpassword") is None
        assert db_module.authenticate_user("resetuser7", "newpassword") is not None


class TestDecimalCalculations:
    """Tests for decimal amount calculations."""

    def test_income_monthly_amount_with_decimals(self, db_module):
        """monthly_amount should handle decimals correctly."""
        user_id = db_module.create_user("decimaltest1", "testpass")
        db_module.add_income(user_id, "Person 1", 1234.56, "monthly")

        incomes = db_module.get_all_income(user_id)
        assert incomes[0].amount == 1234.56
        assert incomes[0].monthly_amount == 1234.56

    def test_expense_monthly_amount_with_decimals(self, db_module):
        """Expense monthly_amount should handle decimals correctly."""
        user_id = db_module.create_user("decimaltest2", "testpass")
        db_module.add_expense(user_id, "Test Expense", "Bolig", 1234.56, "monthly")

        expenses = db_module.get_all_expenses(user_id)
        assert expenses[0].amount == 1234.56
        assert expenses[0].monthly_amount == 1234.56

    def test_income_quarterly_to_monthly_with_decimals(self, db_module):
        """Should correctly convert quarterly to monthly with decimals."""
        user_id = db_module.create_user("decimaltest3", "testpass")
        db_module.add_income(user_id, "Bonus", 3000.00, "quarterly")

        incomes = db_module.get_all_income(user_id)
        assert incomes[0].amount == 3000.00
        assert incomes[0].monthly_amount == 1000.00

    def test_expense_yearly_to_monthly_with_rounding(self, db_module):
        """Should correctly convert yearly to monthly with rounding."""
        user_id = db_module.create_user("decimaltest4", "testpass")
        db_module.add_expense(user_id, "Insurance", "Forsikring", 1200.50, "yearly")

        expenses = db_module.get_all_expenses(user_id)
        # 1200.50 / 12 = 100.041666... should round to 100.04
        assert expenses[0].amount == 1200.50
        assert expenses[0].monthly_amount == 100.04

    def test_income_semi_annual_to_monthly_with_decimals(self, db_module):
        """Should correctly convert semi-annual to monthly."""
        user_id = db_module.create_user("decimaltest5", "testpass")
        db_module.add_income(user_id, "Semi-annual Bonus", 6000.60, "semi-annual")

        incomes = db_module.get_all_income(user_id)
        # 6000.60 / 6 = 1000.10
        assert incomes[0].amount == 6000.60
        assert incomes[0].monthly_amount == 1000.10

    def test_expense_with_precise_division(self, db_module):
        """Should handle precise division with proper rounding."""
        user_id = db_module.create_user("decimaltest6", "testpass")
        # 100.00 / 3 = 33.333... should round to 33.33
        db_module.add_expense(user_id, "Quarterly Fee", "Andet", 100.00, "quarterly")

        expenses = db_module.get_all_expenses(user_id)
        assert expenses[0].monthly_amount == 33.33

    def test_total_income_with_decimals(self, db_module):
        """Total income should handle decimals correctly."""
        user_id = db_module.create_user("decimaltest7", "testpass")
        db_module.add_income(user_id, "Person 1", 1234.56, "monthly")
        db_module.add_income(user_id, "Person 2", 2345.67, "monthly")

        total = db_module.get_total_income(user_id)
        assert total == 3580.23

    def test_total_expenses_with_decimals(self, db_module):
        """Total expenses should handle decimals correctly."""
        user_id = db_module.create_user("decimaltest8", "testpass")
        db_module.add_expense(user_id, "Expense 1", "Bolig", 1234.56, "monthly")
        db_module.add_expense(user_id, "Expense 2", "Mad", 2345.67, "monthly")

        total = db_module.get_total_monthly_expenses(user_id)
        assert total == 3580.23


class TestExpenseMonthlyAmounts:
    """Tests for Expense.get_monthly_amounts() method."""

    def test_monthly_expense_no_months(self, db_module):
        exp = db_module.Expense(id=1, user_id=1, name="Husleje", category="Bolig",
                                amount=6000, frequency="monthly", months=None)
        result = exp.get_monthly_amounts()
        assert len(result) == 12
        assert all(v == 6000 for v in result.values())

    def test_yearly_expense_no_months(self, db_module):
        exp = db_module.Expense(id=1, user_id=1, name="Forsikring", category="Forsikring",
                                amount=12000, frequency="yearly", months=None)
        result = exp.get_monthly_amounts()
        assert len(result) == 12
        assert all(v == 1000 for v in result.values())

    def test_semi_annual_expense_no_months(self, db_module):
        exp = db_module.Expense(id=1, user_id=1, name="Service", category="Transport",
                                amount=6000, frequency="semi-annual", months=None)
        result = exp.get_monthly_amounts()
        assert len(result) == 12
        assert all(v == 1000 for v in result.values())

    def test_quarterly_expense_no_months(self, db_module):
        exp = db_module.Expense(id=1, user_id=1, name="Vand", category="Forbrug",
                                amount=2400, frequency="quarterly", months=None)
        result = exp.get_monthly_amounts()
        assert len(result) == 12
        assert all(v == 800 for v in result.values())

    def test_yearly_expense_with_months(self, db_module):
        exp = db_module.Expense(id=1, user_id=1, name="Skat", category="Bolig",
                                amount=18000, frequency="yearly", months=[1])
        result = exp.get_monthly_amounts()
        assert result[1] == 18000
        assert all(result[m] == 0 for m in range(2, 13))

    def test_semi_annual_with_months(self, db_module):
        exp = db_module.Expense(id=1, user_id=1, name="Forsikring", category="Forsikring",
                                amount=6000, frequency="semi-annual", months=[3, 9])
        result = exp.get_monthly_amounts()
        assert result[3] == 3000
        assert result[9] == 3000
        assert all(result[m] == 0 for m in range(1, 13) if m not in [3, 9])

    def test_quarterly_with_months(self, db_module):
        exp = db_module.Expense(id=1, user_id=1, name="Vand", category="Forbrug",
                                amount=2400, frequency="quarterly", months=[1, 4, 7, 10])
        result = exp.get_monthly_amounts()
        assert result[1] == 600
        assert result[4] == 600
        assert result[7] == 600
        assert result[10] == 600
        assert all(result[m] == 0 for m in [2, 3, 5, 6, 8, 9, 11, 12])


class TestExpenseSchemaColumns:
    """Tests that expense schema has all required columns."""

    def test_months_column_exists_after_init(self, db_module):
        conn = db_module.get_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(expenses)")
        columns = [col[1] for col in cur.fetchall()]
        conn.close()
        assert "months" in columns

    def test_existing_expenses_have_null_months(self, db_module):
        user_id = db_module.create_user("migrationtest", "testpass")
        expense_id = db_module.add_expense(user_id, "Test", "Bolig", 1000, "monthly")
        expense = db_module.get_expense_by_id(expense_id, user_id)
        assert expense.months is None


class TestExpenseCRUDWithMonths:
    """Tests for expense CRUD operations with months field."""

    def test_add_expense_with_months(self, db_module):
        """add_expense should store months as JSON."""
        user_id = db_module.create_user("monthstest1", "testpass")
        expense_id = db_module.add_expense(user_id, "Forsikring", "Forsikring", 6000, "semi-annual", months=[3, 9])
        expense = db_module.get_expense_by_id(expense_id, user_id)
        assert expense.months == [3, 9]

    def test_add_expense_without_months(self, db_module):
        """add_expense without months should store None."""
        user_id = db_module.create_user("monthstest2", "testpass")
        expense_id = db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly")
        expense = db_module.get_expense_by_id(expense_id, user_id)
        assert expense.months is None

    def test_update_expense_with_months(self, db_module):
        """update_expense should update months field."""
        user_id = db_module.create_user("monthstest3", "testpass")
        expense_id = db_module.add_expense(user_id, "Skat", "Bolig", 18000, "yearly")
        db_module.update_expense(expense_id, user_id, "Skat", "Bolig", 18000, "yearly", months=[7])
        expense = db_module.get_expense_by_id(expense_id, user_id)
        assert expense.months == [7]

    def test_update_expense_clear_months(self, db_module):
        """update_expense with months=None should clear months."""
        user_id = db_module.create_user("monthstest4", "testpass")
        expense_id = db_module.add_expense(user_id, "Skat", "Bolig", 18000, "yearly", months=[1])
        db_module.update_expense(expense_id, user_id, "Skat", "Bolig", 18000, "yearly", months=None)
        expense = db_module.get_expense_by_id(expense_id, user_id)
        assert expense.months is None

    def test_get_all_expenses_includes_months(self, db_module):
        """get_all_expenses should include months field."""
        user_id = db_module.create_user("monthstest5", "testpass")
        db_module.add_expense(user_id, "Forsikring", "Forsikring", 6000, "semi-annual", months=[3, 9])
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly")
        expenses = db_module.get_all_expenses(user_id)
        months_map = {e.name: e.months for e in expenses}
        assert months_map["Forsikring"] == [3, 9]
        assert months_map["Husleje"] is None


class TestYearlyOverview:
    """Tests for yearly overview data calculation."""

    def test_yearly_overview_empty(self, db_module):
        """Empty budget should return zeros."""
        user_id = db_module.create_user("yearlytest1", "testpass")
        result = db_module.get_yearly_overview(user_id)
        assert result['categories'] == {}
        assert all(result['totals'][m] == 0 for m in range(1, 13))

    def test_yearly_overview_monthly_expense(self, db_module):
        """Monthly expense shows same amount every month."""
        user_id = db_module.create_user("yearlytest2", "testpass")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly")
        result = db_module.get_yearly_overview(user_id)
        assert all(result['categories']['Bolig'][m] == 10000 for m in range(1, 13))
        assert result['year_total'] == 120000

    def test_yearly_overview_with_months(self, db_module):
        """Expense with months assigned shows in correct months."""
        user_id = db_module.create_user("yearlytest3", "testpass")
        db_module.add_expense(user_id, "Forsikring", "Forsikring", 6000, "semi-annual", months=[3, 9])
        result = db_module.get_yearly_overview(user_id)
        assert result['categories']['Forsikring'][3] == 3000
        assert result['categories']['Forsikring'][9] == 3000
        assert result['categories']['Forsikring'][1] == 0
        assert result['year_total'] == 6000

    def test_yearly_overview_mixed_expenses(self, db_module):
        """Multiple expenses combine correctly per category."""
        user_id = db_module.create_user("yearlytest4", "testpass")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly")
        db_module.add_expense(user_id, "Ejendomsskat", "Bolig", 18000, "yearly", months=[1])
        result = db_module.get_yearly_overview(user_id)
        assert result['categories']['Bolig'][1] == 28000  # 10000 + 18000
        assert result['categories']['Bolig'][2] == 10000   # Only husleje

    def test_yearly_overview_totals(self, db_module):
        """Totals row sums all categories per month."""
        user_id = db_module.create_user("yearlytest5", "testpass")
        db_module.add_expense(user_id, "Husleje", "Bolig", 5000, "monthly")
        db_module.add_expense(user_id, "Mad", "Mad", 3000, "monthly")
        result = db_module.get_yearly_overview(user_id)
        assert all(result['totals'][m] == 8000 for m in range(1, 13))

    def test_yearly_overview_income(self, db_module):
        """Income is spread equally (no months support)."""
        user_id = db_module.create_user("yearlytest6", "testpass")
        db_module.add_income(user_id, "Løn", 30000, "monthly")
        result = db_module.get_yearly_overview(user_id)
        assert all(result['income'][m] == 30000 for m in range(1, 13))

    def test_yearly_overview_balance(self, db_module):
        """Balance = income - expenses per month."""
        user_id = db_module.create_user("yearlytest7", "testpass")
        db_module.add_income(user_id, "Løn", 30000, "monthly")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000, "monthly")
        db_module.add_expense(user_id, "Skat", "Bolig", 18000, "yearly", months=[1])
        result = db_module.get_yearly_overview(user_id)
        assert result['balance'][1] == 2000   # 30000 - 10000 - 18000
        assert result['balance'][2] == 20000  # 30000 - 10000
