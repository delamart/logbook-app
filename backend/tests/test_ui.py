import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"

def test_home_page_loads(page: Page):
    page.goto(BASE_URL)
    expect(page).to_have_title("Logbook Scanner Pro")

def test_table_headers(page: Page):
    page.goto(BASE_URL)
    # Check for specific headers to ensure table rendered
    expect(page.locator("th").filter(has_text="Date")).to_be_visible()
    expect(page.locator("th").filter(has_text="Aircraft")).to_be_visible()
    expect(page.locator("th").filter(has_text="Remarks")).to_be_visible()

def test_manual_entry_creation_and_edit(page: Page):
    page.goto(BASE_URL)
    
    # 1. Click "Add Entry"
    # Wait for table to load first
    expect(page.locator("table")).to_be_visible()
    
    page.get_by_text("Add Entry").click()
    
    page.wait_for_timeout(1000) # Wait for fetch and render
    
    # 2. Wait for new row to appear
    # The row should contain "New Entry"
    new_entry_text = page.get_by_text("New Entry").first
    expect(new_entry_text).to_be_visible(timeout=5000)
    
    # Verify it persists (optional, but good check)
    page.reload()
    expect(page.get_by_text("New Entry").first).to_be_visible()

def test_delete_entry(page: Page):
    # Ensure isolation by creating a unique entry via API
    page.request.post(f"{BASE_URL}/entries/create", data={"date": "2023-01-01", "remarks": "Delete Me"})
    
    page.goto(BASE_URL)
    
    # Locate the row with our text
    row = page.locator("tr").filter(has_text="Delete Me").first
    expect(row).to_be_visible()
    
    # Delete
    page.on("dialog", lambda dialog: dialog.accept()) # Handle confirm alert
    row.locator("button.delete").click()
    
    # Verify gone
    expect(page.get_by_text("Delete Me")).not_to_be_visible()

def test_dashboard_stats(page: Page):
    page.goto(BASE_URL)
    
    # Check Stats Panel
    expect(page.locator("#stats-panel")).to_be_visible()
    
    # Check specific stats cards
    expect(page.locator("#stat-total-time")).to_be_visible()
    expect(page.locator("#stat-pic-time")).to_be_visible()
    expect(page.locator("#stat-landings")).to_be_visible()
    expect(page.locator("#stat-aircraft")).to_be_visible()

def test_map_component(page: Page):
    page.goto(BASE_URL)
    
    # Check Map is present
    expect(page.locator("#map-card")).to_be_visible()
    # Check Legend
    expect(page.locator(".legend")).to_be_visible()

def test_csv_import_button(page: Page):
    page.goto(BASE_URL)
    
    # Check Import Button
    expect(page.locator("#btn-import-csv")).to_be_visible()
    # Check hidden input exists
    expect(page.locator("#csv-input")).to_be_hidden()
