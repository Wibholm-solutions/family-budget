"""E2E tests for chart visualizations."""

from playwright.sync_api import Page, expect


class TestChartRendering:
    """Tests for chart rendering on dashboard."""

    def test_chart_section_renders_for_new_user(self, authenticated_page: Page, base_url: str):
        """Chart section should render empty state placeholder for users without data."""
        authenticated_page.goto(f"{base_url}/budget/")

        # Empty state shows icon + descriptive text (scoped to chart empty state)
        expect(authenticated_page.locator("#chart-empty-state")).to_be_visible()

    def test_chart_label_visible(self, authenticated_page: Page, base_url: str):
        """Chart label should be visible."""
        authenticated_page.goto(f"{base_url}/budget/")

        expect(authenticated_page.locator("text=Udgiftsfordeling")).to_be_visible()


class TestChartResponsive:
    """Tests for responsive chart behavior."""

    def test_chart_renders_on_mobile(self, page: Page, base_url: str):
        """Chart should render properly on mobile viewport."""
        # Use demo mode to have actual chart data
        page.goto(f"{base_url}/budget/demo")
        page.wait_for_url(f"{base_url}/budget/")

        page.set_viewport_size({"width": 375, "height": 667})
        page.reload()

        # Pie chart should be visible with demo data
        expect(page.locator("#chart-categories")).to_be_visible()

    def test_chart_renders_on_small_viewport(self, page: Page, base_url: str):
        """Chart should render properly on smallest mobile viewport."""
        # Use demo mode to have actual chart data
        page.goto(f"{base_url}/budget/demo")
        page.wait_for_url(f"{base_url}/budget/")

        page.set_viewport_size({"width": 320, "height": 568})
        page.reload()

        # Chart should still be visible
        expect(page.locator("#chart-categories")).to_be_visible()


class TestDemoCharts:
    """Tests for charts in demo mode."""

    def test_demo_chart_shows_data(self, page: Page, base_url: str):
        """Demo mode should display pie chart with demo data."""
        page.goto(f"{base_url}/budget/demo")
        page.wait_for_url(f"{base_url}/budget/")

        # Pie chart should be visible
        expect(page.locator("#chart-categories")).to_be_visible()

    def test_demo_chart_has_content(self, page: Page, base_url: str):
        """Demo mode chart should have actual rendered content."""
        page.goto(f"{base_url}/budget/demo")
        page.wait_for_url(f"{base_url}/budget/")

        # Wait for chart to render (Chart.js needs a moment)
        page.wait_for_timeout(1000)

        # Canvas should have non-zero dimensions (indicating content)
        canvas = page.locator("#chart-categories")
        box = canvas.bounding_box()
        assert box is not None
        assert box["width"] > 0
        assert box["height"] > 0

    def test_demo_chart_has_custom_legend(self, page: Page, base_url: str):
        """Doughnut chart should have a custom legend div below the canvas."""
        page.goto(f"{base_url}/budget/demo")
        page.wait_for_url(f"{base_url}/budget/")
        page.wait_for_timeout(1000)

        legend = page.locator("#chart-legend")
        expect(legend).to_be_visible()

    def test_demo_chart_legend_has_percentage(self, page: Page, base_url: str):
        """Custom legend should show percentage values."""
        page.goto(f"{base_url}/budget/demo")
        page.wait_for_url(f"{base_url}/budget/")
        page.wait_for_timeout(1500)

        legend_text = page.locator("#chart-legend").text_content()
        assert legend_text is not None
        assert "%" in legend_text


class TestChartPosition:
    """Tests for chart position on dashboard."""

    def test_chart_at_bottom_of_page(self, page: Page, base_url: str):
        """Chart should be positioned at the bottom of the dashboard."""
        page.goto(f"{base_url}/budget/demo")
        page.wait_for_url(f"{base_url}/budget/")

        # Income breakdown should appear before chart
        income_breakdown = page.locator("text=Indkomst fordeling")
        chart = page.locator("#chart-categories")

        income_box = income_breakdown.bounding_box()
        chart_box = chart.bounding_box()

        assert income_box is not None
        assert chart_box is not None
        # Chart should be below income breakdown
        assert chart_box["y"] > income_box["y"]
