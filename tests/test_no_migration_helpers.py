"""Ensure dead migration helper functions have been removed (issue #144)."""


class TestNoMigrationHelpers:
    """Ensure migration helper functions have been removed (issue #144)."""

    def test_migrate_categories_add_user_id_removed(self, db_module):
        assert not hasattr(db_module, "_migrate_categories_add_user_id"), \
            "_migrate_categories_add_user_id should have been removed"

    def test_migrate_expenses_add_columns_removed(self, db_module):
        assert not hasattr(db_module, "_migrate_expenses_add_columns"), \
            "_migrate_expenses_add_columns should have been removed"

    def test_run_migrations_removed(self, db_module):
        assert not hasattr(db_module, "_run_migrations"), \
            "_run_migrations should have been removed"
