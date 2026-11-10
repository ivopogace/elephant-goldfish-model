"""Start a private OpenCode server for one run and talk to its HTTP API."""

import base64
import json
import os
import secrets
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


class Server:
    def __init__(self, binary: str, cwd: str, env: dict, log_path: str):
        self.port = free_port()
        self.password = secrets.token_urlsafe(24)
        self.auth = 'Basic ' + base64.b64encode(f'opencode:{self.password}'.encode()).decode()
        self.log = open(log_path, 'w')
        self.process = subprocess.Popen(
            [binary, 'serve', '--hostname', '127.0.0.1', '--port', str(self.port)], cwd=cwd,
            env={**env, 'OPENCODE_PASSWORD': self.password}, stdout=self.log, stderr=self.log,
            start_new_session=True)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                if any(agent.get('id') == 'egm' for agent in self.get('/api/agent')['data']):
                    return
            except (urllib.error.URLError, ConnectionError, TimeoutError, KeyError):
                pass
            time.sleep(0.5)
        self.stop()
        raise TimeoutError('The egm agent never loaded on the started server')

    @property
    def url(self) -> str:
        return f'http://127.0.0.1:{self.port}'

    def call(self, method: str, path: str, body=None, timeout: float = 60):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.url + path, data=data, method=method, headers={
            'Authorization': self.auth, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw) if raw else None

    def get(self, path: str):
        return self.call('GET', path)

    def post(self, path: str, body=None):
        return self.call('POST', path, body if body is not None else {})

    def record_events(self, path: str) -> threading.Thread:
        """Append the server's event stream to a file until the server stops."""
        def pump():
            request = urllib.request.Request(self.url + '/api/event', headers={'Authorization': self.auth})
            try:
                with urllib.request.urlopen(request, timeout=86400) as stream, open(path, 'a') as out:
                    for line in stream:
                        if line.startswith(b'data:'):
                            out.write(line[5:].decode('utf-8', 'replace').strip() + '\n')
                            out.flush()
            except Exception:
                pass
        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        return thread

    def stop(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=20)
        self.log.close()
