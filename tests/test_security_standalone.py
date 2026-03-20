"""Standalone security tests — no DB setup needed."""


class TestHashPassword:
    def test_returns_hash_and_salt(self):
        from src.db.security import hash_password
        h, s = hash_password("testpassword")
        assert len(h) == 64  # SHA-256 hex
        assert len(s) == 64  # 32 bytes hex

    def test_same_salt_same_hash(self):
        from src.db.security import hash_password
        _, salt = hash_password("test")
        h1, _ = hash_password("test", bytes.fromhex(salt))
        h2, _ = hash_password("test", bytes.fromhex(salt))
        assert h1 == h2

    def test_different_passwords_differ(self):
        from src.db.security import hash_password
        _, salt = hash_password("a")
        h1, _ = hash_password("a", bytes.fromhex(salt))
        h2, _ = hash_password("b", bytes.fromhex(salt))
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password(self):
        from src.db.security import hash_password, verify_password
        h, s = hash_password("mypass")
        assert verify_password("mypass", h, s) is True

    def test_wrong_password(self):
        from src.db.security import hash_password, verify_password
        h, s = hash_password("mypass")
        assert verify_password("wrong", h, s) is False


class TestHashEmail:
    def test_deterministic(self):
        from src.db.security import hash_email
        assert hash_email("Test@Example.com") == hash_email("test@example.com")

    def test_strips_whitespace(self):
        from src.db.security import hash_email
        assert hash_email("  test@example.com  ") == hash_email("test@example.com")
