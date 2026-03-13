import subprocess
import time
import sys
import os
import requests
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
API_DIR = PROJECT_ROOT / "api"
WEB_DIR = PROJECT_ROOT / "web"
PYTHON_EXE = sys.executable

def is_port_open(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def wait_for_service(url, timeout=60):
    start_time = time.time()
    print(f"Waiting for {url}...")
    while time.time() - start_time < timeout:
        try:
            requests.get(url)
            print(f"Service {url} is ready!")
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(1)
        except Exception as e:
            print(f"Error checking service: {e}")
            time.sleep(1)
    return False

def main():
    print("Starting E2E Test Environment...")
    
    # Start Backend
    print("Launching Backend (FastAPI)...")
    backend_process = subprocess.Popen(
        [PYTHON_EXE, "-m", "uvicorn", "api.main:app", "--port", "8685", "--host", "127.0.0.1"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL, # Mute output to keep console clean
        stderr=subprocess.DEVNULL
    )
    
    # Start Frontend
    print("Launching Frontend (Next.js)...")
    # Use shell=True for npm on Windows
    frontend_process = subprocess.Popen(
        "npm run dev", 
        cwd=WEB_DIR, 
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        print("Waiting for services to be ready...")
        if not wait_for_service("http://127.0.0.1:8685/docs", timeout=60):
            print("Backend failed to start.")
            return 1
            
        if not wait_for_service("http://localhost:8686", timeout=120):
            print("Frontend failed to start.")
            return 1
            
        print("Services are up. Running Playwright tests...")
        
        # Run Tests
        result = subprocess.run(
            [PYTHON_EXE, "-m", "pytest", "tests/e2e/test_ui.py"],
            cwd=PROJECT_ROOT
        )
        
        return result.returncode
        
    finally:
        print("Cleaning up...")
        backend_process.terminate()
        # Frontend is tricky on Windows with shell=True, often leaves node running.
        # We try to kill by port to be sure.
        subprocess.run("taskkill /F /IM node.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("taskkill /F /IM uvicorn.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    sys.exit(main())
