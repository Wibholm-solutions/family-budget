"""E2E tests for authentication flows."""

from playwright.sync_api import Page, expect


class TestLoginFlow:
    """Tests for login functionality."""

    def test_login_page_renders(self, page: Page, base_url: str):
        """Login page should display correctly."""
        page.goto(f"{base_url}/budget/login")

        # Check page title
        expect(page).to_have_title("Login - Budget")

        # Check form elements exist
        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()

    def test_login_with_invalid_credentials(self, page: Page, base_url: str):
        """Login with wrong credentials shows error."""
        page.goto(f"{base_url}/budget/login")

        page.fill('input[name="username"]', "wronguser")
        page.fill('input[name="password"]', "wrongpass")
        page.click('button[type="submit"]')

        # Should show error message
        expect(page.locator("text=Forkert")).to_be_visible()

    def test_demo_mode_link_works(self, page: Page, base_url: str):
        """Demo mode link should work and redirect to dashboard."""
        page.goto(f"{base_url}/budget/login")

        # Click demo link
        page.click("text=Prøv demo")

        # Should redirect to dashboard
        expect(page).to_have_url(f"{base_url}/budget/")

    def test_register_link_works(self, page: Page, base_url: str):
        """Register link should navigate to registration page."""
        page.goto(f"{base_url}/budget/login")

        page.click("text=Opret bruger")

        expect(page).to_have_url(f"{base_url}/budget/register")


class TestRegistrationFlow:
    """Tests for user registration."""

    def test_register_page_renders(self, page: Page, base_url: str):
        """Registration page should display correctly."""
        page.goto(f"{base_url}/budget/register")

        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()
        expect(page.locator('input[name="password_confirm"]')).to_be_visible()

    def test_register_success_redirects_to_dashboard(self, page: Page, base_url: str):
        """Successful registration should redirect to dashboard."""
        import uuid
        page.goto(f"{base_url}/budget/register")

        # Use unique username per test run
        unique_user = f"newuser_{uuid.uuid4().hex[:8]}"
        page.fill('input[name="username"]', unique_user)
        page.fill('input[name="password"]', "password123")
        page.fill('input[name="password_confirm"]', "password123")
        page.click('button[type="submit"]')

        # Should redirect to dashboard (wait for navigation)
        page.wait_for_url(f"{base_url}/budget/", timeout=10000)
        expect(page).to_have_url(f"{base_url}/budget/")

    def test_register_password_mismatch_shows_error(self, page: Page, base_url: str):
        """Mismatched passwords should show error."""
        page.goto(f"{base_url}/budget/register")

        page.fill('input[name="username"]', "testuser")
        page.fill('input[name="password"]', "password123")
        page.fill('input[name="password_confirm"]', "differentpass")
        page.click('button[type="submit"]')

        # Should show error
        expect(page.locator("text=matcher ikke")).to_be_visible()

    def test_register_short_password_blocked_by_validation(self, page: Page, base_url: str):
        """Short password should be blocked by HTML5 validation."""
        page.goto(f"{base_url}/budget/register")

        page.fill('input[name="username"]', "testuser")
        page.fill('input[name="password"]', "short")
        page.fill('input[name="password_confirm"]', "short")

        # Check that password field has minlength attribute
        password_input = page.locator('input[name="password"]')
        expect(password_input).to_have_attribute("minlength", "6")

        # Form should not submit due to HTML5 validation
        # After clicking submit, we should still be on register page
        page.click('button[type="submit"]')
        expect(page).to_have_url(f"{base_url}/budget/register")


class TestDemoMode:
    """Tests for demo mode functionality."""

    def test_demo_dashboard_shows_data(self, page: Page, base_url: str):
        """Demo mode should show demo data on dashboard."""
        page.goto(f"{base_url}/budget/demo")

        # Should redirect to dashboard
        page.wait_for_url(f"{base_url}/budget/")

        # Should show income/expense data (use .first for multiple matches)
        expect(page.get_by_text("Indkomst", exact=True).first).to_be_visible()
        expect(page.get_by_text("Udgifter", exact=True).first).to_be_visible()
        expect(page.get_by_text("Til fri brug")).to_be_visible()


class TestLogout:
    """Tests for logout functionality."""

    def test_logout_redirects_to_login(self, authenticated_page: Page, base_url: str):
        """Logout should redirect to login page."""
        # Click logout icon
        authenticated_page.click('[data-lucide="log-out"]')

        # Should redirect to login
        authenticated_page.wait_for_url(f"{base_url}/budget/login")
        expect(authenticated_page).to_have_url(f"{base_url}/budget/login")
