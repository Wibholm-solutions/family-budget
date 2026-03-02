#!/usr/bin/env python3
"""
One-time migration script to migrate all users to per-user categories.

This script should be run once after deploying the per-user categories feature.
It migrates all existing users' expenses to use category_id foreign keys.

Usage:
    python scripts/migrate_all_users_to_per_user_categories.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import database as db


def main():
    print("=" * 60)
    print("Per-User Categories Migration")
    print("=" * 60)
    print()

    # Get all users
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users ORDER BY id")
    users = cur.fetchall()
    conn.close()

    if not users:
        print("No users found in database.")
        return

    print(f"Found {len(users)} user(s) to migrate:\n")
    for user_id, username in users:
        print(f"  - {username} (ID: {user_id})")

    print()
    response = input("Proceed with migration? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Migration cancelled.")
        return

    print()
    print("Starting migration...")
    print("-" * 60)

    success_count = 0
    for user_id, username in users:
        try:
            print(f"Migrating {username} (ID: {user_id})...", end=" ")

            # Check if already migrated
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM categories WHERE user_id = ?", (user_id,))
            existing_cats = cur.fetchone()[0]
            conn.close()

            if existing_cats > 0:
                print(f"SKIP (already has {existing_cats} categories)")
                success_count += 1
                continue

            # Migrate user
            db.migrate_user_categories(user_id)

            # Verify
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM categories WHERE user_id = ?", (user_id,))
            new_cats = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ? AND category_id IS NOT NULL", (user_id,))
            migrated_expenses = cur.fetchone()[0]
            conn.close()

            print(f"OK ({new_cats} categories, {migrated_expenses} expenses linked)")
            success_count += 1

        except Exception as e:
            print(f"ERROR: {e}")

    print("-" * 60)
    print(f"\nMigration complete: {success_count}/{len(users)} users migrated successfully")

    if success_count == len(users):
        print("✅ All users migrated successfully!")
    else:
        print("⚠️  Some users failed to migrate. Check errors above.")


if __name__ == "__main__":
    main()
