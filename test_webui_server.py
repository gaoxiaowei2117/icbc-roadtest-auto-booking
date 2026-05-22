import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import webui


def _serve():
    server = ThreadingHTTPServer(("127.0.0.1", 0), webui.Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as resp:
        return resp.status, resp.headers.get("Content-Type"), resp.read()


class StaticServingTest(unittest.TestCase):
    def setUp(self):
        self.server, self.port = _serve()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_root_serves_index_html(self):
        status, ctype, body = _get(self.port, "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"webui stub", body)

    def test_style_and_app_served(self):
        status, ctype, _ = _get(self.port, "/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", ctype)
        status, ctype, _ = _get(self.port, "/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)

    def test_unknown_path_returns_404(self):
        try:
            _get(self.port, "/api/nope")
            self.fail("expected HTTPError")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


class FindFreePortTest(unittest.TestCase):
    def test_find_free_port_returns_bindable_port(self):
        port = webui.find_free_port()
        self.assertGreaterEqual(port, 8787)
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))


if __name__ == "__main__":
    unittest.main()
