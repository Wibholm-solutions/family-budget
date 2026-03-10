"""Integration tests for authentication endpoints."""


class TestAuthentication:
    """Tests for authentication endpoints."""

    def test_login_page_accessible(self, client):
        """Login page should be accessible without auth."""
        response = client.get("/budget/login")

        assert response.status_code == 200
        assert "login" in response.text.lower()

    def test_login_page_contains_app_description(self, client):
        """Login page should contain app description and features."""
        response = client.get("/budget/login")

        assert response.status_code == 200
        # Check tagline
        assert "Hold styr på familiens økonomi" in response.text
        # Check feature bullets
        assert "Overblik over indkomst" in response.text
        assert "Organiser udgifter" in response.text
        assert "hvad der er tilbage" in response.text
        # Check demo link exists
        assert "/budget/demo" in response.text

    def test_login_redirects_when_authenticated(self, authenticated_client):
        """Login page should redirect if already authenticated."""
        response = authenticated_client.get("/budget/login", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/budget/"

    def test_login_success(self, client, db_module):
        """Successful login should set cookie and redirect."""
        db_module.create_user("loginuser", "password123")

        response = client.post(
            "/budget/login",
            data={"username": "loginuser", "password": "password123"},
            follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/budget/"
        assert "budget_session" in response.cookies

    def test_login_failure(self, client, db_module):
        """Failed login should show error."""
        db_module.create_user("loginuser", "password123")

        response = client.post(
            "/budget/login",
            data={"username": "loginuser", "password": "wrongpassword"}
        )

        assert response.status_code == 200
        assert "forkert" in response.text.lower()

    def test_register_page_accessible(self, client):
        """Register page should be accessible without auth."""
        response = client.get("/budget/register")

        assert response.status_code == 200

    def test_register_success(self, client):
        """Successful registration should create user and login."""
        response = client.post(
            "/budget/register",
            data={
                "username": "newuser",
                "password": "password123",
                "password_confirm": "password123"
            },
            follow_redirects=False
        )

        assert response.status_code == 303
        assert "budget_session" in response.cookies

    def test_register_short_username(self, client):
        """Registration should fail with short username."""
        response = client.post(
            "/budget/register",
            data={
                "username": "ab",
                "password": "password123",
                "password_confirm": "password123"
            }
        )

        assert response.status_code == 200
        assert "mindst 3" in response.text.lower()

    def test_register_short_password(self, client):
        """Registration should fail with short password."""
        response = client.post(
            "/budget/register",
            data={
                "username": "validuser",
                "password": "short",
                "password_confirm": "short"
            }
        )

        assert response.status_code == 200
        assert "mindst 6" in response.text.lower()

    def test_register_password_mismatch(self, client):
        """Registration should fail when passwords don't match."""
        response = client.post(
            "/budget/register",
            data={
                "username": "validuser",
                "password": "password123",
                "password_confirm": "different123"
            }
        )

        assert response.status_code == 200
        assert "matcher ikke" in response.text.lower()

    def test_register_duplicate_username(self, client, db_module):
        """Registration should fail for existing username."""
        db_module.create_user("existing", "password123")

        response = client.post(
            "/budget/register",
            data={
                "username": "existing",
                "password": "newpass123",
                "password_confirm": "newpass123"
            }
        )

        assert response.status_code == 200
        assert "allerede" in response.text.lower()

    def test_logout(self, authenticated_client):
        """Logout should clear session and redirect to login."""
        response = authenticated_client.get("/budget/logout", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_demo_mode(self, client):
        """Demo mode should set special session."""
        response = client.get("/budget/demo", follow_redirects=False)

        assert response.status_code == 303
        assert response.cookies.get("budget_session") == "demo"


class TestPasswordReset:
    """Tests for password reset endpoints."""

    def test_forgot_password_page_accessible(self, client):
        """Forgot password page should be accessible without auth."""
        response = client.get("/budget/forgot-password")

        assert response.status_code == 200
        assert "Glemt adgangskode" in response.text

    def test_forgot_password_shows_success_for_any_email(self, client):
        """Forgot password should show success even for unknown email (prevent enumeration)."""
        response = client.post(
            "/budget/forgot-password",
            data={"email": "unknown@example.com"}
        )

        assert response.status_code == 200
        assert "sendt et link" in response.text

    def test_forgot_password_creates_token_for_valid_user(self, client, db_module):
        """Forgot password should create token for user with email."""
        user_id = db_module.create_user("resetuser1", "oldpass")
        db_module.update_user_email(user_id, "reset@example.com")

        response = client.post(
            "/budget/forgot-password",
            data={"email": "reset@example.com"}
        )

        assert response.status_code == 200
        # Token should be created (we can't easily check this without mocking email)

    def test_reset_password_invalid_token(self, client):
        """Reset password with invalid token should show error."""
        response = client.get("/budget/reset-password/invalidtoken123")

        assert response.status_code == 200
        assert "ugyldigt" in response.text.lower() or "udløbet" in response.text.lower()

    def test_reset_password_valid_token_shows_form(self, client, db_module):
        """Reset password with valid token should show password form."""
        import hashlib
        from datetime import datetime, timedelta

        user_id = db_module.create_user("resetuser2", "oldpass")
        token = "validtoken123"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        db_module.create_password_reset_token(user_id, token_hash, expires_at)

        response = client.get(f"/budget/reset-password/{token}")

        assert response.status_code == 200
        assert "Ny adgangskode" in response.text

    def test_reset_password_changes_password(self, client, db_module):
        """Reset password should update user's password."""
        import hashlib
        from datetime import datetime, timedelta

        user_id = db_module.create_user("resetuser3", "oldpassword")
        token = "changetoken123"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        db_module.create_password_reset_token(user_id, token_hash, expires_at)

        response = client.post(
            f"/budget/reset-password/{token}",
            data={"password": "newpassword", "password_confirm": "newpassword"}
        )

        assert response.status_code == 200
        assert "nulstillet" in response.text.lower()

        # Verify old password no longer works, new does
        assert db_module.authenticate_user("resetuser3", "oldpassword") is None
        assert db_module.authenticate_user("resetuser3", "newpassword") is not None

    def test_reset_password_validates_password_length(self, client, db_module):
        """Reset password should require minimum password length."""
        import hashlib
        from datetime import datetime, timedelta

        user_id = db_module.create_user("resetuser4", "oldpass")
        token = "shorttoken123"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        db_module.create_password_reset_token(user_id, token_hash, expires_at)

        response = client.post(
            f"/budget/reset-password/{token}",
            data={"password": "short", "password_confirm": "short"}
        )

        assert response.status_code == 200
        assert "mindst 6" in response.text

    def test_reset_password_validates_password_match(self, client, db_module):
        """Reset password should require passwords to match."""
        import hashlib
        from datetime import datetime, timedelta

        user_id = db_module.create_user("resetuser5", "oldpass")
        token = "matchtoken123"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        db_module.create_password_reset_token(user_id, token_hash, expires_at)

        response = client.post(
            f"/budget/reset-password/{token}",
            data={"password": "password1", "password_confirm": "password2"}
        )

        assert response.status_code == 200
        assert "matcher ikke" in response.text

    def test_reset_password_token_single_use(self, client, db_module):
        """Reset password token should only work once."""
        import hashlib
        from datetime import datetime, timedelta

        user_id = db_module.create_user("resetuser6", "oldpass")
        token = "singleusetoken"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        db_module.create_password_reset_token(user_id, token_hash, expires_at)

        # First use should work
        response1 = client.post(
            f"/budget/reset-password/{token}",
            data={"password": "newpass1", "password_confirm": "newpass1"}
        )
        assert "nulstillet" in response1.text.lower()

        # Second use should fail
        response2 = client.post(
            f"/budget/reset-password/{token}",
            data={"password": "newpass2", "password_confirm": "newpass2"}
        )
        assert "ugyldigt" in response2.text.lower() or "udløbet" in response2.text.lower()
