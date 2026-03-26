"""E2E tests for export buttons on the Konto (settings) page."""

from playwright.sync_api import Page, expect


class TestExportButtons:
    """Tests for the export section on /budget/settings."""

    def test_export_section_heading_visible(self, authenticated_page: Page, base_url: str):
        """The 'Eksporter' section heading should be visible on the settings page."""
        authenticated_page.goto(f"{base_url}/budget/settings")

        expect(authenticated_page.get_by_text("Eksporter", exact=True)).to_be_visible()

    def test_export_summary_button_exists(self, authenticated_page: Page, base_url: str):
        """The export summary button should exist with the correct ID."""
        authenticated_page.goto(f"{base_url}/budget/settings")

        expect(authenticated_page.locator("#export-summary-btn")).to_be_visible()

    def test_export_detailed_button_exists(self, authenticated_page: Page, base_url: str):
        """The export detailed button should exist with the correct ID."""
        authenticated_page.goto(f"{base_url}/budget/settings")

        expect(authenticated_page.locator("#export-detailed-btn")).to_be_visible()

    def test_export_summary_button_text(self, authenticated_page: Page, base_url: str):
        """The export summary button should display the correct text."""
        authenticated_page.goto(f"{base_url}/budget/settings")

        btn = authenticated_page.locator("#export-summary-btn")
        expect(btn.get_by_text("Oversigt som billede")).to_be_visible()

    def test_export_detailed_button_text(self, authenticated_page: Page, base_url: str):
        """The export detailed button should display the correct text."""
        authenticated_page.goto(f"{base_url}/budget/settings")

        btn = authenticated_page.locator("#export-detailed-btn")
        expect(btn.get_by_text("Detaljeret som billede")).to_be_visible()
