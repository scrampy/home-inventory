import os
import sys
import threading
import time
import requests
import subprocess
import socket
import random
import string

# Set these before importing app for E2E/Playwright tests
os.environ['E2E_TEST'] = '1'
os.environ['TEST_DB_PATH'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '../test.db'))
import pytest
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from app import db, app

class FlaskServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.proc = None
        self.logfile = None
        self.port = self._find_free_port()
    def _find_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
    def run(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env = os.environ.copy()
        env['FLASK_TESTING'] = '1'
        env['PORT'] = str(self.port)
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.logfile = os.path.join(project_root, f'flask_server_{rand_suffix}.log')
        python_executable = sys.executable
        flask_app_script = os.path.join(project_root, "app.py")
        try:
            self.proc = subprocess.Popen(
                [python_executable, flask_app_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_root,
                env=env,
                text=True
            )
            time.sleep(1)
            self.proc.poll()
            if self.proc.returncode is not None:
                stdout, stderr = self.proc.communicate(timeout=5)
                raise AssertionError("Flask app did not start")
            for _ in range(20):
                try:
                    with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                        return
                except Exception:
                    time.sleep(0.5)
            stdout, stderr = self.proc.communicate(timeout=5)
            raise AssertionError("Flask app did not start")
        except Exception as e:
            raise
    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()

def wait_for_server(url, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

@pytest.fixture(scope="session", autouse=False)
def flask_server():
    server = FlaskServerThread()
    server.start()
    base_url = f"http://localhost:{server.port}"
    assert wait_for_server(f"{base_url}/auth"), "Flask app did not start"
    yield base_url
    server.stop()

@pytest.fixture(scope="session", autouse=True)
def ensure_db_created():
    with app.app_context():
        db.create_all()
    yield

@pytest.fixture(scope='session', autouse=True)
def setup_e2e_db():
    # Use persistent test DB for E2E
    with app.app_context():
        db.drop_all()
    yield
    # Clean up test DB after session
    try:
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../test.db'))
        os.remove(db_path)
        print('DEBUG: test.db deleted after session', flush=True)
    except Exception as e:
        print(f'DEBUG: Failed to delete test.db: {e}', flush=True)
