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
    expect(page.get_by_text("Extract via API")).to_be_visible()
    expect(page.get_by_text("ForeFlight Import")).to_be_visible()

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
    row.locator("button.delete").click()
    page.locator("#custom-dialog-confirm").click()
    
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

def test_bulk_delete(page: Page):
    # Setup: Create two entries
    page.request.post(f"{BASE_URL}/entries/create", data={"date": "2023-01-01", "remarks": "Bulk Delete 1"})
    page.request.post(f"{BASE_URL}/entries/create", data={"date": "2023-01-02", "remarks": "Bulk Delete 2"})
    
    page.goto(f"{BASE_URL}/logbook")
    page.wait_for_selector("text=Synthesizing flight data...", state="hidden")
    
    # Verify entries exist
    expect(page.get_by_text("Bulk Delete 1").first).to_be_visible()
    expect(page.get_by_text("Bulk Delete 2").first).to_be_visible()
    
    # Button initially disabled
    delete_btn = page.locator("#btn-delete-selected")
    expect(delete_btn).to_be_disabled()
    
    # Click Select All
    page.locator("#selectAllCheckbox").check()
    
    # Wait for JS to update UI (just in case)
    page.wait_for_timeout(500)
    
    # Button should be enabled and show count >= 2
    expect(delete_btn).to_be_enabled()
    
    # Execute delete
    delete_btn.click()
    
    # Confirm warning modal
    page.locator("#custom-dialog-confirm").click()
    
    # Confirm success modal
    page.locator("#custom-dialog-confirm").click()
    
    # Wait for tables to refresh
    page.wait_for_timeout(1000)
    
    # Verify entries are gone
    expect(page.get_by_text("Bulk Delete 1")).not_to_be_visible()
    expect(page.get_by_text("Bulk Delete 2")).not_to_be_visible()
    
    # Verify button reset
    expect(delete_btn).to_be_disabled()
