"""Tests for cross-domain operations."""


class TestCategoryUpdateResult:
    """Tests for rename_category_and_cascade_expenses."""

    def test_rename_cascades_to_expenses(self, db_module):
        """Renaming a category should update all expenses with the old name."""
        from src.db.operations import rename_category_and_cascade_expenses

        user_id = db_module.create_user("catcascade1", "testpass")
        cat_id = db_module.add_category(user_id, "OldCat", "house")
        db_module.add_expense(user_id, "Rent", "OldCat", 1000, "monthly")
        db_module.add_expense(user_id, "Power", "OldCat", 200, "monthly")

        result = rename_category_and_cascade_expenses(cat_id, user_id, "NewCat", "house")

        assert result.cascaded_expense_count == 2
        expenses = db_module.get_all_expenses(user_id)
        assert all(e.category == "NewCat" for e in expenses)

    def test_rename_no_cascade_when_name_unchanged(self, db_module):
        """No cascade when only icon changes."""
        from src.db.operations import rename_category_and_cascade_expenses

        user_id = db_module.create_user("catcascade2", "testpass")
        cat_id = db_module.add_category(user_id, "SameCat", "house")
        db_module.add_expense(user_id, "Rent", "SameCat", 1000, "monthly")

        result = rename_category_and_cascade_expenses(cat_id, user_id, "SameCat", "zap")
        assert result.cascaded_expense_count == 0


class TestDeleteResult:
    """Tests for delete_category_if_unused and delete_account_if_unused."""

    def test_delete_unused_category(self, db_module):
        """Should delete category with no expenses."""
        from src.db.operations import delete_category_if_unused

        user_id = db_module.create_user("catdel1", "testpass")
        cat_id = db_module.add_category(user_id, "Empty", "house")

        result = delete_category_if_unused(cat_id, user_id)
        assert result.deleted is True
        assert result.reason == "ok"

    def test_delete_category_in_use(self, db_module):
        """Should refuse to delete category with expenses."""
        from src.db.operations import delete_category_if_unused

        user_id = db_module.create_user("catdel2", "testpass")
        cat_id = db_module.add_category(user_id, "InUse", "house")
        db_module.add_expense(user_id, "Rent", "InUse", 1000, "monthly")

        result = delete_category_if_unused(cat_id, user_id)
        assert result.deleted is False
        assert result.reason == "in_use"

    def test_delete_category_not_found(self, db_module):
        """Should return not_found for nonexistent category."""
        from src.db.operations import delete_category_if_unused

        user_id = db_module.create_user("catdel3", "testpass")
        result = delete_category_if_unused(99999, user_id)
        assert result.deleted is False
        assert result.reason == "not_found"

    def test_delete_unused_account(self, db_module):
        """Should delete account with no expenses."""
        from src.db.operations import delete_account_if_unused

        user_id = db_module.create_user("acctdel1", "testpass")
        acct_id = db_module.add_account(user_id, "Empty Acct")

        result = delete_account_if_unused(acct_id, user_id)
        assert result.deleted is True
        assert result.reason == "ok"

    def test_delete_account_in_use(self, db_module):
        """Should refuse to delete account with expenses."""
        from src.db.operations import delete_account_if_unused

        user_id = db_module.create_user("acctdel2", "testpass")
        acct_id = db_module.add_account(user_id, "UsedAcct")
        db_module.add_expense(user_id, "Rent", "Bolig", 1000, "monthly", account="UsedAcct")

        result = delete_account_if_unused(acct_id, user_id)
        assert result.deleted is False
        assert result.reason == "in_use"


class TestCreateUserWithDefaultCategories:
    """Tests for atomic user creation."""

    def test_creates_user_and_categories_atomically(self, db_module):
        """User and default categories should be created in one transaction."""
        from src.db.operations import create_user_with_default_categories

        user_id = create_user_with_default_categories("atomicuser", "testpass")
        assert user_id is not None

        categories = db_module.get_all_categories(user_id)
        assert len(categories) == 9  # DEFAULT_CATEGORIES has 9 entries

    def test_duplicate_username_returns_none(self, db_module):
        """Duplicate username should return None."""
        from src.db.operations import create_user_with_default_categories

        create_user_with_default_categories("dupuser", "testpass")
        result = create_user_with_default_categories("dupuser", "testpass2")
        assert result is None

    def test_email_hash_stored(self, db_module):
        """Email hash should be stored when email provided."""
        from src.db.operations import create_user_with_default_categories

        user_id = create_user_with_default_categories("emailuser", "testpass", email="test@example.com")
        user = db_module.get_user_by_id(user_id)
        assert user.email_hash is not None


class TestAccountRename:
    """Tests for rename_account_and_cascade_expenses."""

    def test_rename_cascades_to_expenses(self, db_module):
        """Renaming an account should update all expenses with the old name."""
        from src.db.operations import rename_account_and_cascade_expenses

        user_id = db_module.create_user("acctren1", "testpass")
        acct_id = db_module.add_account(user_id, "OldAcct")
        db_module.add_expense(user_id, "Rent", "Bolig", 1000, "monthly", account="OldAcct")

        count = rename_account_and_cascade_expenses(acct_id, user_id, "NewAcct")
        assert count == 1

        expenses = db_module.get_all_expenses(user_id)
        assert expenses[0].account == "NewAcct"
