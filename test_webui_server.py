import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import configure
import webui
from webui_monitor import Monitor


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
        self.assertIn(b"monitor-indicator", body)

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


def _post(port, path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


class ConfigApiTest(unittest.TestCase):
    def setUp(self):
        self._orig = configure.CONFIG_PATH
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "config.yml"
        shutil.copy("config.example.yml", self.cfg)
        configure.CONFIG_PATH = self.cfg
        self.server, self.port = _serve()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        configure.CONFIG_PATH = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_get_config_returns_fields(self):
        status, _, body = _get(self.port, "/api/config")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("fields", data)
        self.assertIn("readiness", data)

    def test_post_config_writes_changes(self):
        status, data = _post(self.port, "/api/config",
                             {"icbc.drvrLastName": "Gao"})
        self.assertEqual(status, 200)
        self.assertIn("icbc.drvrLastName", data["applied"])
        _, _, body = _get(self.port, "/api/config")
        by_id = {f["id"]: f["value"] for f in json.loads(body)["fields"]}
        self.assertEqual(by_id["icbc.drvrLastName"], "Gao")


class MonitorApiTest(unittest.TestCase):
    def setUp(self):
        self._orig = configure.CONFIG_PATH
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "config.yml"
        shutil.copy("config.example.yml", self.cfg)
        configure.CONFIG_PATH = self.cfg
        self._orig_monitor = webui.monitor
        # -u: unbuffered stdout, else block-buffering hides output past the poll window
        webui.monitor = Monitor(command=[
            sys.executable, "-u", "-c",
            "import time; print('fake-monitor'); time.sleep(30)"])
        self.server, self.port = _serve()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        webui.monitor.stop()
        webui.monitor = self._orig_monitor
        configure.CONFIG_PATH = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_status_endpoint_reports_monitor_state(self):
        status, _, body = _get(self.port, "/api/status")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertFalse(data["monitor_running"])
        self.assertIn("booking", data)
        self.assertIn("log_summary", data)

    def test_start_then_stop_monitor(self):
        _, started = _post(self.port, "/api/monitor/start", {})
        self.assertTrue(started["running"])
        ok = False
        for _ in range(100):
            _, _, body = _get(self.port, "/api/console")
            if any("fake-monitor" in l for l in json.loads(body)["lines"]):
                ok = True
                break
            time.sleep(0.05)
        self.assertTrue(ok)
        _, stopped = _post(self.port, "/api/monitor/stop", {})
        self.assertFalse(stopped["running"])


if __name__ == "__main__":
    unittest.main()
