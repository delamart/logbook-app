import pytest
import subprocess
import time
import requests
import os
from playwright.sync_api import Page

@pytest.fixture(scope="session")
def run_server():
    # Start the server with overidden isolated DB URL
    env = os.environ.copy()
    test_db_path = "backend/data/test_ui.db"
    env["DATABASE_URL"] = f"sqlite:///{test_db_path}"

    process = subprocess.Popen(
        ["./venv/bin/uvicorn", "backend.app.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    # Wait for server to be ready
    url = "http://localhost:8000"
    for _ in range(10):
        try:
            requests.get(url)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    else:
        process.terminate()
        raise RuntimeError("Server did not start in time")
    
    yield
    
    # Teardown
    process.terminate()
    process.wait()
    
    # Cleanup UI Test Database
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

@pytest.fixture(autouse=True)
def ensure_server(run_server):
    pass
