import pytest
import subprocess
import time
import requests
from playwright.sync_api import Page

@pytest.fixture(scope="session")
def run_server():
    # Start the server
    process = subprocess.Popen(
        ["./venv/bin/uvicorn", "backend.app.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
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

@pytest.fixture(autouse=True)
def ensure_server(run_server):
    pass
