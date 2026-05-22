"""Local web control panel for the ICBC auto-booking tool.

Stdlib-only HTTP server bound to 127.0.0.1. Serves the static frontend
from webui/ and a small JSON API under /api/*.
"""

import http.server
import json
import os
import socket
from urllib.parse import urlparse

import webui_state

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webui")

# 路径 -> (webui/ 下的文件名, Content-Type)。白名单,杜绝路径穿越。
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}


def find_free_port(start=8787, attempts=20):
    """从 start 起找一个能绑定的端口。"""
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("找不到可用端口")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # 静默,不污染终端

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path):
        filename, ctype = STATIC_FILES[path]
        try:
            with open(os.path.join(WEB_DIR, filename), "rb") as f:
                body = f.read()
        except OSError:
            self._send_json({"error": "static file missing"}, 500)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path in STATIC_FILES:
            self._send_static(path)
        elif path == "/api/config":
            self._send_json(webui_state.read_config())
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            applied = webui_state.write_config(self._read_json_body())
            self._send_json({"applied": applied})
        else:
            self._send_json({"error": "not found"}, 404)


def main():
    pass  # Task 8 实现


if __name__ == "__main__":
    main()
