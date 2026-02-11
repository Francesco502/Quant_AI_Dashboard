import pytest
from playwright.sync_api import Page, expect

def test_dashboard_loads(page: Page):
    """Verify that the dashboard loads correctly."""
    page.goto("http://localhost:8686/")
    page.wait_for_load_state("networkidle")
    
    # Check for main heading
    expect(page.get_by_role("heading", name="Market Overview")).to_be_visible()
    
    # Check for key metrics cards
    expect(page.get_by_text("Total Balance")).to_be_visible()
    expect(page.get_by_text("Daily P&L")).to_be_visible()
    
    # Check chart is present
    expect(page.locator(".recharts-responsive-container")).to_be_visible()

def test_market_analysis_page(page: Page):
    """Verify Market Analysis page functionality."""
    page.goto("http://localhost:8686/market")
    page.wait_for_load_state("networkidle")
    
    expect(page.get_by_role("heading", name="Market Analysis")).to_be_visible()
    
    # Check Tabs - use role tab
    expect(page.get_by_role("tab", name="AI Forecast")).to_be_visible()
    expect(page.get_by_role("tab", name="Technical Indicators")).to_be_visible()
    
    # Check Forecast inputs
    expect(page.get_by_text("Asset", exact=True)).to_be_visible()
    expect(page.get_by_text("Horizon (Days)")).to_be_visible()
    
    # Check Run button
    run_btn = page.get_by_role("button", name="Run Forecast")
    expect(run_btn).to_be_visible()

def test_trading_page(page: Page):
    """Verify Trading page functionality."""
    page.goto("http://localhost:8686/trading")
    page.wait_for_load_state("networkidle")
    
    expect(page.get_by_role("heading", name="Quantitative Trading")).to_be_visible()
    expect(page.get_by_role("heading", name="Trading Signals")).to_be_visible()
    
    # Check table headers
    expect(page.get_by_role("columnheader", name="Signal")).to_be_visible()
    expect(page.get_by_role("columnheader", name="Confidence")).to_be_visible()
    expect(page.get_by_role("columnheader", name="Action")).to_be_visible()

def test_strategies_page(page: Page):
    """Verify Strategies page functionality."""
    page.goto("http://localhost:8686/strategies")
    page.wait_for_load_state("networkidle")
    
    expect(page.get_by_role("button", name="Create Strategy")).to_be_visible(timeout=20000)
    expect(page.get_by_text("Configure and monitor your trading algorithms.")).to_be_visible(timeout=20000)

def test_settings_page(page: Page):
    """Verify Settings page functionality."""
    page.goto("http://localhost:8686/settings")
    page.wait_for_load_state("networkidle")
    
    expect(page.get_by_role("heading", name="System Management")).to_be_visible()
    
    # Check tabs
    expect(page.get_by_role("tab", name="Asset Pool")).to_be_visible()
    expect(page.get_by_role("tab", name="Paper Account")).to_be_visible()
    expect(page.get_by_role("tab", name="Daemon Status")).to_be_visible()
