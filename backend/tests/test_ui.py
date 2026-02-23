import pytest
import uuid
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"

@pytest.fixture
def auth_page(page: Page) -> Page:
    """Fixture that registers a new user and returns an authenticated page."""
    email = f"test_{uuid.uuid4()}@example.com"
    password = "password123"
    
    page.goto(f"{BASE_URL}/register")
    page.locator("#email").fill(email)
    page.locator("#password").fill(password)
    page.locator("#confirmPassword").fill(password)
    page.locator("button[type='submit']").click()
    
    # Registration redirects to /login after success
    expect(page).to_have_url(f"{BASE_URL}/login", timeout=10000)
    
    # Now log in with the new credentials
    page.locator("#email").fill(email)
    page.locator("#password").fill(password)
    page.locator("button[type='submit']").click()
    
    # Wait for login to complete and redirect to dashboard
    expect(page).to_have_url(f"{BASE_URL}/dashboard", timeout=10000)
    
    # Return the authenticated page for the test to use
    return page

def test_login_redirect(page: Page):
    page.goto(BASE_URL)
    expect(page).to_have_url(f"{BASE_URL}/login")
    expect(page).to_have_title("Logbook Scanner Pro - Login")

def test_register_page(page: Page):
    page.goto(f"{BASE_URL}/register")
    expect(page).to_have_title("Logbook Scanner Pro - Register")
    expect(page.locator("h2").filter(has_text="Join the Fleet")).to_be_visible()

def test_dashboard_loads(auth_page: Page):
    auth_page.goto(BASE_URL)
    
    # Check Stats Panel
    expect(auth_page.locator("#stats-panel")).to_be_visible()
    expect(auth_page.locator("#stat-total-time")).to_be_visible()

def test_logbook_page(auth_page: Page):
    auth_page.goto(f"{BASE_URL}/logbook")
    expect(auth_page).to_have_title("My Logbook - Logbook Scanner Pro")
    
    # Check for specific headers to ensure table rendered
    expect(auth_page.locator("th").filter(has_text="Date")).to_be_visible()
    expect(auth_page.locator("th").filter(has_text="Aircraft")).to_be_visible()

def test_map_page(auth_page: Page):
    auth_page.goto(f"{BASE_URL}/map")
    expect(auth_page).to_have_title("Flight Map - Logbook Scanner Pro")
    
    # Check Map is present
    expect(auth_page.locator("#map-card")).to_be_visible()
    expect(auth_page.locator(".leaflet-container")).to_be_visible()

def test_tools_page(auth_page: Page):
    auth_page.goto(f"{BASE_URL}/tools")
    expect(auth_page).to_have_title("Tools - Logbook Scanner Pro")
    
    # Check Import Options
    expect(auth_page.get_by_text("Extract via API")).to_be_visible()
    expect(auth_page.get_by_text("ForeFlight Import")).to_be_visible()

def test_manual_entry_creation_and_edit(auth_page: Page):
    auth_page.goto(f"{BASE_URL}/logbook")
    
    # 1. Click "Add Entry"
    expect(auth_page.locator("table")).to_be_visible()
    auth_page.get_by_text("Add Entry").click()
    
    # 2. Wait for new row
    auth_page.wait_for_timeout(1000) 
    auth_page.wait_for_timeout(1000) 
    # Use locator to find the input since it enters edit mode automatically
    new_entry_input = auth_page.locator('input[value="New Entry"]').first
    expect(new_entry_input).to_be_visible(timeout=5000)
    
    # Verify persists
    auth_page.reload()
    expect(auth_page.get_by_text("New Entry").first).to_be_visible()

def test_delete_entry(auth_page: Page):
    # Ensure isolation by creating a unique entry via API
    auth_page.request.post(f"{BASE_URL}/entries/create", data={"date": "2023-01-01", "remarks": "Delete Me"})
    
    auth_page.goto(f"{BASE_URL}/logbook")
    
    # Locate the row
    row = auth_page.locator("tr").filter(has_text="Delete Me").first
    expect(row).to_be_visible()
    
    # Delete
    row.locator("button.delete").click()
    auth_page.locator("#custom-dialog-confirm").click()
    
    # Verify gone
    expect(auth_page.get_by_text("Delete Me")).not_to_be_visible()

def test_navigation_sidebar(auth_page: Page):
    auth_page.goto(BASE_URL)
    
    # Click Map Link
    auth_page.locator(".sidebar-nav a[href='/map']").click()
    expect(auth_page).to_have_url(f"{BASE_URL}/map")
    expect(auth_page.locator("#map-card")).to_be_visible()
    
    # Click Logbook Link
    auth_page.locator(".sidebar-nav a[href='/logbook']").click()
    expect(auth_page).to_have_url(f"{BASE_URL}/logbook")
    expect(auth_page.locator("#master-table")).to_be_visible()

def test_bulk_delete(auth_page: Page):
    # Setup: Create two entries
    auth_page.request.post(f"{BASE_URL}/entries/create", data={"date": "2023-01-01", "remarks": "Bulk Delete 1"})
    auth_page.request.post(f"{BASE_URL}/entries/create", data={"date": "2023-01-02", "remarks": "Bulk Delete 2"})
    
    auth_page.goto(f"{BASE_URL}/logbook")
    auth_page.wait_for_selector("text=Synthesizing flight data...", state="hidden")
    
    # Verify entries exist
    expect(auth_page.get_by_text("Bulk Delete 1").first).to_be_visible()
    expect(auth_page.get_by_text("Bulk Delete 2").first).to_be_visible()
    
    # Button initially disabled
    delete_btn = auth_page.locator("#btn-delete-selected")
    expect(delete_btn).to_be_disabled()
    
    # Click Select All
    auth_page.locator("#selectAllCheckbox").check()
    
    # Wait for JS to update UI (just in case)
    auth_page.wait_for_timeout(500)
    
    # Button should be enabled and show count >= 2
    expect(delete_btn).to_be_enabled()
    
    # Execute delete
    delete_btn.click()
    
    # Confirm warning modal
    auth_page.locator("#custom-dialog-confirm").click()
    
    # Confirm success modal
    auth_page.locator("#custom-dialog-confirm").click()
    
    # Wait for tables to refresh
    auth_page.wait_for_timeout(1000)
    
    # Verify entries are gone
    expect(auth_page.get_by_text("Bulk Delete 1")).not_to_be_visible()
    expect(auth_page.get_by_text("Bulk Delete 2")).not_to_be_visible()
    
    # Verify button reset
    expect(delete_btn).to_be_disabled()
