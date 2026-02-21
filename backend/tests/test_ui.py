import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"

def test_dashboard_loads(page: Page):
    page.goto(BASE_URL) # Should redirect or show dashboard
    expect(page).to_have_title("Dashboard - Logbook Scanner Pro")
    
    # Check Stats Panel
    expect(page.locator("#stats-panel")).to_be_visible()
    expect(page.locator("#stat-total-time")).to_be_visible()

def test_logbook_page(page: Page):
    page.goto(f"{BASE_URL}/logbook")
    expect(page).to_have_title("My Logbook - Logbook Scanner Pro")
    
    # Check for specific headers to ensure table rendered
    expect(page.locator("th").filter(has_text="Date")).to_be_visible()
    expect(page.locator("th").filter(has_text="Aircraft")).to_be_visible()

def test_map_page(page: Page):
    page.goto(f"{BASE_URL}/map")
    expect(page).to_have_title("Flight Map - Logbook Scanner Pro")
    
    # Check Map is present
    expect(page.locator("#map-card")).to_be_visible()
    expect(page.locator(".leaflet-container")).to_be_visible()

def test_tools_page(page: Page):
    page.goto(f"{BASE_URL}/tools")
    expect(page).to_have_title("Tools - Logbook Scanner Pro")
    
    # Check Import Options
    expect(page.get_by_text("Scan New Logbook Page")).to_be_visible()
    expect(page.get_by_text("Import from ForeFlight")).to_be_visible()

def test_manual_entry_creation_and_edit(page: Page):
    page.goto(f"{BASE_URL}/logbook")
    
    # 1. Click "Add Entry"
    expect(page.locator("table")).to_be_visible()
    page.get_by_text("Add Entry").click()
    
    # 2. Wait for new row
    page.wait_for_timeout(1000) 
    page.wait_for_timeout(1000) 
    # Use locator to find the input since it enters edit mode automatically
    new_entry_input = page.locator('input[value="New Entry"]').first
    expect(new_entry_input).to_be_visible(timeout=5000)
    
    # Verify persists
    page.reload()
    expect(page.get_by_text("New Entry").first).to_be_visible()

def test_delete_entry(page: Page):
    # Ensure isolation by creating a unique entry via API
    page.request.post(f"{BASE_URL}/entries/create", data={"date": "2023-01-01", "remarks": "Delete Me"})
    
    page.goto(f"{BASE_URL}/logbook")
    
    # Locate the row
    row = page.locator("tr").filter(has_text="Delete Me").first
    expect(row).to_be_visible()
    
    # Delete
    page.on("dialog", lambda dialog: dialog.accept()) 
    row.locator("button.delete").click()
    
    # Verify gone
    expect(page.get_by_text("Delete Me")).not_to_be_visible()

def test_navigation_sidebar(page: Page):
    page.goto(BASE_URL)
    
    # Click Map Link
    page.locator(".sidebar-nav a[href='/map']").click()
    expect(page).to_have_url(f"{BASE_URL}/map")
    expect(page.locator("#map-card")).to_be_visible()
    
    # Click Logbook Link
    page.locator(".sidebar-nav a[href='/logbook']").click()
    expect(page).to_have_url(f"{BASE_URL}/logbook")
    expect(page.locator("#master-table")).to_be_visible()
