# Web 控制面板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 ICBC 自动预约工具加一个本地网页控制面板,让用户不碰命令行即可编辑配置、启停监控、查看实时状态和日志。

**Architecture:** `webui.py` 用 Python 标准库 `http.server` 起一个只绑定 `127.0.0.1` 的本地服务,提供 `webui/` 下的静态前端和 `/api/*` JSON 接口。后端拆成三个模块:`webui_state.py`(配置读写 + 状态文件读取)、`webui_monitor.py`(`road.py` 子进程管理)、`webui.py`(HTTP 服务器 + 路由 + 入口)。复用现有 `configure.py` 的行级 YAML 读写函数,不重写 `configure.py` 或 `road.py`。

**Tech Stack:** Python 3.7+ 标准库(`http.server`、`subprocess`、`threading`、`webbrowser`、`socket`、`json`);测试用标准库 `unittest`;前端为原生 HTML/CSS/JS。**全程零新依赖。**

**完整设计见:** `docs/superpowers/specs/2026-05-21-web-control-panel-design.md`

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `webui_state.py` (新建) | 配置字段清单 `CONFIG_FIELDS`;`read_config()` / `write_config()` 桥接 `configure.py`;`read_status()` 读状态文件 |
| `webui_monitor.py` (新建) | `Monitor` 类:启停 `road.py` 子进程、捕获 stdout 到环形缓冲 |
| `webui.py` (新建) | `ThreadingHTTPServer` + `Handler` 路由 + `find_free_port` + `main()` 入口 |
| `webui/index.html` (新建) | 前端单页面板 HTML |
| `webui/style.css` (新建) | 前端样式 |
| `webui/app.js` (新建) | 前端逻辑:fetch、标签切换、轮询、配置表单 |
| `test_webui_state.py` (新建) | `webui_state` 单元测试 |
| `test_webui_monitor.py` (新建) | `webui_monitor` 单元测试 |
| `test_webui_server.py` (新建) | `webui` HTTP 接口测试 |
| `start.sh` (修改) | 新增菜单项 5「打开控制面板」 |
| `README.md` / `README.zh.md` (修改) | 记录控制面板用法 |

测试用标准库 `unittest`,放在项目根目录,与已移除的 `test_road.py` 旧约定一致。运行命令形如 `python3 -m unittest test_webui_state -v`。

---

## Task 1: webui_state.py — 配置字段清单与 read_config

**Files:**
- Create: `webui_state.py`
- Test: `test_webui_state.py`

- [ ] **Step 1: 写失败的测试**

创建 `test_webui_state.py`:

```python
import shutil
import tempfile
import unittest
from pathlib import Path

import configure
import webui_state


class ReadConfigTest(unittest.TestCase):
    def setUp(self):
        self._orig = configure.CONFIG_PATH
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "config.yml"
        shutil.copy("config.example.yml", self.cfg)
        configure.CONFIG_PATH = self.cfg

    def tearDown(self):
        configure.CONFIG_PATH = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_read_config_returns_fields_and_readiness(self):
        result = webui_state.read_config()
        self.assertIn("fields", result)
        self.assertIn("readiness", result)
        by_id = {f["id"]: f for f in result["fields"]}
        # 嵌套字段
        self.assertEqual(by_id["icbc.drvrLastName"]["value"], "YOUR_LAST_NAME")
        self.assertEqual(by_id["icbc.drvrLastName"]["type"], "text")
        self.assertEqual(by_id["icbc.drvrLastName"]["group"], "ICBC 账户")
        # 布尔字段被转成 Python bool
        self.assertIs(by_id["gmail.enable"]["value"], True)
        # 顶层字段用 _root 前缀,int 转成数字
        self.assertEqual(by_id["_root.pauseTimeMin"]["value"], 5)
        self.assertIsInstance(by_id["_root.pauseTimeMin"]["value"], int)

    def test_read_config_readiness_flags_placeholders(self):
        result = webui_state.read_config()
        self.assertTrue(any("last name" in r.lower() for r in result["readiness"]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m unittest test_webui_state -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'webui_state'`

- [ ] **Step 3: 写最小实现**

创建 `webui_state.py`:

```python
"""Config + status data layer for the web control panel.

Stdlib-only. Bridges to configure.py for config.yml read/write so the
config form works even before runtime dependencies are installed.
"""

import json
import os

import configure

# (section, key, label, type, group) — section None 表示顶层 key
# type: text | bool | date | int
CONFIG_FIELDS = [
    ("icbc", "drvrLastName", "姓氏", "text", "ICBC 账户"),
    ("icbc", "licenceNumber", "驾照号", "text", "ICBC 账户"),
    ("icbc", "keyword", "ICBC 关键字/密码", "text", "ICBC 账户"),
    ("icbc", "examClass", "考试类别", "text", "ICBC 账户"),
    ("icbc", "posID", "考点 ID", "text", "ICBC 账户"),
    ("icbc", "expactAfterDate", "最早日期 (YYYY-MM-DD)", "date", "日期 / 时间"),
    ("icbc", "expactBeforeDate", "最晚日期 (YYYY-MM-DD)", "date", "日期 / 时间"),
    ("icbc", "expactTimeRange", "时间范围", "text", "日期 / 时间"),
    ("icbc", "prfDaysOfWeek", "偏好星期 (0=周日)", "text", "日期 / 时间"),
    ("icbc", "prfPartsOfDay", "偏好时段 (0=上午,1=下午)", "text", "日期 / 时间"),
    ("gmail", "enable", "启用 Gmail", "bool", "Gmail"),
    ("gmail", "email", "Gmail 地址", "text", "Gmail"),
    ("gmail", "password", "Gmail 应用密码", "text", "Gmail"),
    ("autoBooking", "enable", "启用自动预约", "bool", "自动预约"),
    ("autoBooking", "timeSelectionStrategy", "时间选择策略", "text", "自动预约"),
    ("autoBooking", "exitAfterSuccess", "成功后退出", "bool", "自动预约"),
    ("autoBooking", "bookingTimeWindow", "预约时间窗口", "text", "自动预约"),
    ("pushdeer", "enable", "启用 PushDeer", "bool", "通知"),
    ("pushdeer", "key", "PushDeer key", "text", "通知"),
    ("ntfy", "enable", "启用 ntfy", "bool", "通知"),
    ("ntfy", "topic", "ntfy 主题", "text", "通知"),
    ("pushsms", "enable", "启用短信 (Twilio)", "bool", "通知"),
    ("pushsms", "accountSid", "Twilio Account SID", "text", "通知"),
    ("pushsms", "authToken", "Twilio Auth Token", "text", "通知"),
    ("pushsms", "fromNumber", "发件号码", "text", "通知"),
    ("pushsms", "toNumber", "收件号码", "text", "通知"),
    ("pushsound", "enable", "启用声音提示", "bool", "通知"),
    ("pushlocal", "enable", "启用桌面通知", "bool", "通知"),
    (None, "pauseTimeMin", "找到名额后暂停分钟数", "int", "高级"),
    (None, "skip0Clock", "跳过 23:55-00:05", "bool", "高级"),
    (None, "data_directory", "数据目录", "text", "高级"),
    ("requestLimit", "enable", "启用请求限流", "bool", "高级"),
    ("requestLimit", "period", "限流时段", "text", "高级"),
    ("requestLimit", "interval", "限流间隔(秒)", "int", "高级"),
]


def _dotted(section, key):
    return f"{section}.{key}" if section else f"_root.{key}"


def _coerce_out(raw, ftype):
    """把 configure.get_value 返回的字符串转成带类型的 JSON 值。"""
    if raw is None:
        return None
    if ftype == "bool":
        return str(raw).strip().lower() in ("true", "yes", "1")
    if ftype == "int":
        try:
            return int(str(raw).strip())
        except ValueError:
            return raw
    return raw


def read_config():
    """返回 {'fields': [...], 'readiness': [...]}。"""
    configure.ensure_config_exists()
    lines = configure.read_lines()
    fields = []
    for section, key, label, ftype, group in CONFIG_FIELDS:
        raw = configure.get_value(lines, section, key)
        fields.append({
            "id": _dotted(section, key),
            "section": section or "_root",
            "key": key,
            "label": label,
            "type": ftype,
            "group": group,
            "value": _coerce_out(raw, ftype),
        })
    return {"fields": fields, "readiness": configure.readiness_issues(lines)}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m unittest test_webui_state -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: 提交**

```bash
git add webui_state.py test_webui_state.py
git commit -m "Add webui_state config field manifest and read_config"
```

---

## Task 2: webui_state.py — write_config

**Files:**
- Modify: `webui_state.py`
- Test: `test_webui_state.py`

- [ ] **Step 1: 写失败的测试**

在 `test_webui_state.py` 的 `import` 之后追加新测试类:

```python
class WriteConfigTest(unittest.TestCase):
    def setUp(self):
        self._orig = configure.CONFIG_PATH
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "config.yml"
        shutil.copy("config.example.yml", self.cfg)
        configure.CONFIG_PATH = self.cfg

    def tearDown(self):
        configure.CONFIG_PATH = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_config_applies_text_bool_int(self):
        applied = webui_state.write_config({
            "icbc.drvrLastName": "Gao",
            "gmail.enable": False,
            "_root.pauseTimeMin": 9,
        })
        self.assertCountEqual(
            applied, ["icbc.drvrLastName", "gmail.enable", "_root.pauseTimeMin"])
        result = {f["id"]: f["value"] for f in webui_state.read_config()["fields"]}
        self.assertEqual(result["icbc.drvrLastName"], "Gao")
        self.assertIs(result["gmail.enable"], False)
        self.assertEqual(result["_root.pauseTimeMin"], 9)

    def test_write_config_ignores_unknown_ids(self):
        applied = webui_state.write_config({"bogus.field": "x"})
        self.assertEqual(applied, [])

    def test_write_config_output_still_valid_yaml(self):
        webui_state.write_config({"icbc.keyword": "newkey"})
        import yaml
        with open(self.cfg, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["icbc"]["keyword"], "newkey")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m unittest test_webui_state.WriteConfigTest -v`
Expected: FAIL，`AttributeError: module 'webui_state' has no attribute 'write_config'`

- [ ] **Step 3: 写最小实现**

在 `webui_state.py` 末尾(`read_config` 之后)追加:

```python
def write_config(changes):
    """changes: {dotted_id: value}。按 CONFIG_FIELDS 应用,返回成功写入的 id 列表。"""
    by_id = {
        _dotted(section, key): (section, key, ftype)
        for section, key, _label, ftype, _group in CONFIG_FIELDS
    }
    lines = configure.read_lines()
    applied = []
    for cid, value in changes.items():
        if cid not in by_id:
            continue
        section, key, ftype = by_id[cid]
        if ftype == "bool":
            new_value = bool(value)
        elif ftype == "int":
            new_value = str(value)
        else:
            new_value = "" if value is None else str(value)
        if configure.set_value(lines, section, key, new_value):
            applied.append(cid)
    configure.write_lines(lines)
    return applied
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m unittest test_webui_state -v`
Expected: PASS（全部测试,含 Task 1 的）

- [ ] **Step 5: 提交**

```bash
git add webui_state.py test_webui_state.py
git commit -m "Add webui_state.write_config"
```

---

## Task 3: webui_state.py — read_status

**Files:**
- Modify: `webui_state.py`
- Test: `test_webui_state.py`

- [ ] **Step 1: 写失败的测试**

在 `test_webui_state.py` 末尾追加新测试类:

```python
class ReadStatusTest(unittest.TestCase):
    def setUp(self):
        self._orig = configure.CONFIG_PATH
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "config.yml"
        shutil.copy("config.example.yml", self.cfg)
        configure.CONFIG_PATH = self.cfg
        # data_directory 指向临时目录里的 datadir
        self.datadir = self.tmp / "datadir"
        self.datadir.mkdir()
        lines = configure.read_lines()
        configure.set_value(lines, None, "data_directory", str(self.datadir))
        configure.write_lines(lines)

    def tearDown(self):
        configure.CONFIG_PATH = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_read_status_empty_when_no_files(self):
        status = webui_state.read_status()
        self.assertIsNone(status["booking"])
        self.assertIsNone(status["last_run"])
        self.assertIsNone(status["log_summary"])

    def test_read_status_reads_booking_and_log(self):
        (self.datadir / "booking_status.json").write_text(
            json.dumps({"status": "booked"}), encoding="utf-8")
        (self.datadir / "last_run.txt").write_text(
            "2026-05-21 10:00:00\n", encoding="utf-8")
        (self.datadir / "log_icbc_roadtest_checker.log").write_text(
            "x - ERROR - boom\nx - INFO - No appointments available\n",
            encoding="utf-8")
        status = webui_state.read_status()
        self.assertEqual(status["booking"]["status"], "booked")
        self.assertEqual(status["last_run"], "2026-05-21 10:00:00")
        self.assertEqual(status["log_summary"]["errors"], 1)
        self.assertEqual(status["log_summary"]["no_appointments"], 1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m unittest test_webui_state.ReadStatusTest -v`
Expected: FAIL，`AttributeError: module 'webui_state' has no attribute 'read_status'`

- [ ] **Step 3: 写最小实现**

在 `webui_state.py` 末尾追加:

```python
def _data_dir():
    lines = configure.read_lines()
    return configure.get_value(lines, None, "data_directory") or "./data"


def _read_booking(data_dir):
    path = os.path.join(data_dir, "booking_status.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _read_last_run(data_dir):
    path = os.path.join(data_dir, "last_run.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return f.readline().strip()
    except OSError:
        return None


def _read_log_summary(data_dir):
    path = os.path.join(data_dir, "log_icbc_roadtest_checker.log")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            recent = f.readlines()[-20:]
    except OSError:
        return None
    return {
        "recent_entries": len(recent),
        "errors": sum("ERROR" in line for line in recent),
        "warnings": sum("WARNING" in line for line in recent),
        "no_appointments": sum("No appointments available" in line for line in recent),
    }


def read_status():
    """返回 {'booking': ..., 'last_run': ..., 'log_summary': ...}。"""
    data_dir = _data_dir()
    return {
        "booking": _read_booking(data_dir),
        "last_run": _read_last_run(data_dir),
        "log_summary": _read_log_summary(data_dir),
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m unittest test_webui_state -v`
Expected: PASS（全部测试）

- [ ] **Step 5: 提交**

```bash
git add webui_state.py test_webui_state.py
git commit -m "Add webui_state.read_status"
```

---

## Task 4: webui_monitor.py — Monitor 类

**Files:**
- Create: `webui_monitor.py`
- Test: `test_webui_monitor.py`

- [ ] **Step 1: 写失败的测试**

创建 `test_webui_monitor.py`:

```python
import sys
import time
import unittest

from webui_monitor import Monitor

# 一个长命子进程:打印一行后睡 30 秒
LONG_CMD = [sys.executable, "-c",
            "import time,sys; print('hello-from-fake'); sys.stdout.flush(); time.sleep(30)"]
# 一个短命子进程:打印一行后立即退出
SHORT_CMD = [sys.executable, "-c", "print('done-fast')"]


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class MonitorTest(unittest.TestCase):
    def tearDown(self):
        # 防止测试残留子进程
        try:
            self.mon.stop()
        except AttributeError:
            pass

    def test_start_sets_running_and_pid(self):
        self.mon = Monitor(command=LONG_CMD)
        self.assertTrue(self.mon.start())
        self.assertTrue(self.mon.is_running())
        self.assertIsInstance(self.mon.pid(), int)

    def test_start_twice_returns_false(self):
        self.mon = Monitor(command=LONG_CMD)
        self.assertTrue(self.mon.start())
        self.assertFalse(self.mon.start())

    def test_console_captures_output(self):
        self.mon = Monitor(command=LONG_CMD)
        self.mon.start()
        self.assertTrue(
            _wait_for(lambda: any("hello-from-fake" in l for l in self.mon.console())))

    def test_stop_terminates_process(self):
        self.mon = Monitor(command=LONG_CMD)
        self.mon.start()
        self.assertTrue(self.mon.stop())
        self.assertFalse(self.mon.is_running())

    def test_stop_when_not_running_returns_false(self):
        self.mon = Monitor(command=LONG_CMD)
        self.assertFalse(self.mon.stop())

    def test_short_process_exits_on_its_own(self):
        self.mon = Monitor(command=SHORT_CMD)
        self.mon.start()
        self.assertTrue(_wait_for(lambda: not self.mon.is_running()))
        self.assertTrue(any("done-fast" in l for l in self.mon.console()))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m unittest test_webui_monitor -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'webui_monitor'`

- [ ] **Step 3: 写最小实现**

创建 `webui_monitor.py`:

```python
"""Manages a single road.py subprocess for the web control panel."""

import collections
import subprocess
import sys
import threading


class Monitor:
    """启停 road.py 子进程,并把它的 stdout 收进环形缓冲。"""

    def __init__(self, command=None):
        # 用 sys.executable 而非硬编码 python3,保证 Windows 也能调用
        self._command = command or [sys.executable, "road.py", "config.yml"]
        self._proc = None
        self._lines = collections.deque(maxlen=500)
        self._lock = threading.Lock()
        self._reader = None

    def is_running(self):
        return self._proc is not None and self._proc.poll() is None

    def pid(self):
        return self._proc.pid if self.is_running() else None

    def start(self):
        """启动子进程。已在运行则返回 False。"""
        if self.is_running():
            return False
        with self._lock:
            self._lines.clear()
        self._proc = subprocess.Popen(
            self._command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()
        return True

    def stop(self):
        """终止子进程。未运行则返回 False。"""
        if not self.is_running():
            return False
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=5)
        return True

    def console(self):
        """返回缓冲里的输出行列表。"""
        with self._lock:
            return list(self._lines)

    def _read_output(self):
        proc = self._proc
        for line in proc.stdout:
            with self._lock:
                self._lines.append(line.rstrip("\n"))
        proc.stdout.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m unittest test_webui_monitor -v`
Expected: PASS（6 个测试）

- [ ] **Step 5: 提交**

```bash
git add webui_monitor.py test_webui_monitor.py
git commit -m "Add webui_monitor Monitor for road.py subprocess"
```

---

## Task 5: webui.py — HTTP 服务器骨架与静态文件服务

**Files:**
- Create: `webui.py`
- Create: `webui/index.html`, `webui/style.css`, `webui/app.js`（本任务先建占位桩文件,Task 9/10 替换为正式内容）
- Test: `test_webui_server.py`

- [ ] **Step 1: 建占位前端文件**

创建 `webui/index.html`:

```html
<!DOCTYPE html>
<title>stub</title>
<p>webui stub</p>
```

创建 `webui/style.css`:

```css
/* stub */
```

创建 `webui/app.js`:

```javascript
/* stub */
```

- [ ] **Step 2: 写失败的测试**

创建 `test_webui_server.py`:

```python
import json
import threading
import unittest
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
        # 端口应可被实际绑定
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python3 -m unittest test_webui_server -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'webui'`

- [ ] **Step 4: 写最小实现**

创建 `webui.py`:

```python
"""Local web control panel for the ICBC auto-booking tool.

Stdlib-only HTTP server bound to 127.0.0.1. Serves the static frontend
from webui/ and a small JSON API under /api/*.
"""

import http.server
import json
import os
import socket

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

    def do_GET(self):
        if self.path in STATIC_FILES:
            self._send_static(self.path)
        else:
            self._send_json({"error": "not found"}, 404)


def main():
    pass  # Task 8 实现


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python3 -m unittest test_webui_server -v`
Expected: PASS（4 个测试）

- [ ] **Step 6: 提交**

```bash
git add webui.py webui/index.html webui/style.css webui/app.js test_webui_server.py
git commit -m "Add webui HTTP server skeleton and static serving"
```

---

## Task 6: webui.py — 配置接口 /api/config

**Files:**
- Modify: `webui.py`
- Test: `test_webui_server.py`

- [ ] **Step 1: 写失败的测试**

在 `test_webui_server.py` 顶部 import 区追加:

```python
import shutil
import tempfile
from pathlib import Path

import configure
```

并在文件末尾(`if __name__` 之前)追加新测试类:

```python
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
        # 重新读应得到新值
        _, _, body = _get(self.port, "/api/config")
        by_id = {f["id"]: f["value"] for f in json.loads(body)["fields"]}
        self.assertEqual(by_id["icbc.drvrLastName"], "Gao")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m unittest test_webui_server.ConfigApiTest -v`
Expected: FAIL，`/api/config` 返回 404 → 断言失败

- [ ] **Step 3: 写最小实现**

在 `webui.py` 顶部 import 区追加:

```python
import webui_state
```

在 `Handler` 类里追加 `_read_json_body` 方法,并扩展 `do_GET`、新增 `do_POST`:

```python
    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except ValueError:
            return {}
```

把 `do_GET` 改成:

```python
    def do_GET(self):
        if self.path in STATIC_FILES:
            self._send_static(self.path)
        elif self.path == "/api/config":
            self._send_json(webui_state.read_config())
        else:
            self._send_json({"error": "not found"}, 404)
```

新增 `do_POST`:

```python
    def do_POST(self):
        if self.path == "/api/config":
            applied = webui_state.write_config(self._read_json_body())
            self._send_json({"applied": applied})
        else:
            self._send_json({"error": "not found"}, 404)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m unittest test_webui_server -v`
Expected: PASS（含 Task 5 的全部测试）

- [ ] **Step 5: 提交**

```bash
git add webui.py test_webui_server.py
git commit -m "Add /api/config GET and POST endpoints"
```

---

## Task 7: webui.py — 状态、控制台、监控启停接口

**Files:**
- Modify: `webui.py`
- Test: `test_webui_server.py`

- [ ] **Step 1: 写失败的测试**

在 `test_webui_server.py` 顶部 import 区追加:

```python
import sys
import time

from webui_monitor import Monitor
```

在文件末尾追加新测试类:

```python
class MonitorApiTest(unittest.TestCase):
    def setUp(self):
        self._orig = configure.CONFIG_PATH
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "config.yml"
        shutil.copy("config.example.yml", self.cfg)
        configure.CONFIG_PATH = self.cfg
        # 把全局 monitor 换成跑假命令的 Monitor
        self._orig_monitor = webui.monitor
        webui.monitor = Monitor(command=[
            sys.executable, "-c",
            "import time; print('fake-monitor'); time.sleep(30)"])
        self.server, self.port = _serve()

    def tearDown(self):
        self.server.shutdown()
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
        # 控制台应能拿到假进程输出
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m unittest test_webui_server.MonitorApiTest -v`
Expected: FAIL，`AttributeError: module 'webui' has no attribute 'monitor'`

- [ ] **Step 3: 写最小实现**

在 `webui.py` 顶部 import 区追加:

```python
from webui_monitor import Monitor
```

在 `STATIC_FILES` 字典之后、`find_free_port` 之前追加模块级全局:

```python
# 全局唯一的 road.py 子进程管理器
monitor = Monitor()
```

把 `do_GET` 改成(追加 `/api/status` 和 `/api/console` 分支):

```python
    def do_GET(self):
        if self.path in STATIC_FILES:
            self._send_static(self.path)
        elif self.path == "/api/config":
            self._send_json(webui_state.read_config())
        elif self.path == "/api/status":
            status = webui_state.read_status()
            status["monitor_running"] = monitor.is_running()
            status["monitor_pid"] = monitor.pid()
            self._send_json(status)
        elif self.path == "/api/console":
            self._send_json({"lines": monitor.console()})
        else:
            self._send_json({"error": "not found"}, 404)
```

把 `do_POST` 改成(追加监控启停分支):

```python
    def do_POST(self):
        if self.path == "/api/config":
            applied = webui_state.write_config(self._read_json_body())
            self._send_json({"applied": applied})
        elif self.path == "/api/monitor/start":
            started = monitor.start()
            self._send_json({"running": monitor.is_running(), "started": started})
        elif self.path == "/api/monitor/stop":
            stopped = monitor.stop()
            self._send_json({"running": monitor.is_running(), "stopped": stopped})
        else:
            self._send_json({"error": "not found"}, 404)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m unittest test_webui_server -v`
Expected: PASS（全部测试）

- [ ] **Step 5: 提交**

```bash
git add webui.py test_webui_server.py
git commit -m "Add status, console, and monitor start/stop endpoints"
```

---

## Task 8: webui.py — main() 入口与退出清理

**Files:**
- Modify: `webui.py`

本任务实现入口逻辑。它会阻塞、开浏览器,不做单元测试,改为运行观察验证。

- [ ] **Step 1: 实现 main() 与依赖检查**

在 `webui.py` 顶部 import 区追加:

```python
import sys
import threading
import webbrowser

import configure
```

把文件末尾占位的 `def main(): pass` 整段替换为:

```python
def _check_dependencies():
    """检查 road.py 运行所需依赖。缺失只警告,不阻止配置编辑。"""
    missing = []
    for mod in ("requests", "yaml", "faker", "twilio", "pypushdeer"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print("⚠️  缺少依赖,监控功能不可用(配置仍可编辑):")
        print("   pip3 install -r requirements.txt")


def main():
    configure.ensure_config_exists()
    _check_dependencies()

    port = find_free_port()
    url = f"http://localhost:{port}"
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)

    print("🖥️  ICBC 自动预约控制面板")
    print(f"   {url}")
    print("ℹ️  注意:停止此面板程序(Ctrl+C)会一并停止正在运行的监控")
    print("   (仅关闭浏览器标签页不影响,服务仍在后台运行)")

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if monitor.is_running():
            print("\n⏹  正在停止监控...")
            monitor.stop()
        server.shutdown()
        print("✅ 已退出")
```

- [ ] **Step 2: 运行确认服务器能起、能停**

Run: `python3 webui.py`
Expected:
- 终端打印面板标题、`http://localhost:8787`(或递增端口)、以及关闭提示两行。
- 浏览器自动打开该地址(此时还是 Task 5 的桩页面,显示 "webui stub" 属正常)。
- 按 Ctrl+C 后终端打印 `✅ 已退出` 并干净退出(无 traceback)。

- [ ] **Step 3: 确认 import 不受运行期依赖影响**

Run: `python3 -c "import webui; print('import ok')"`
Expected: 打印 `import ok`,无报错(证明 `webui` 仅靠标准库即可导入)。

- [ ] **Step 4: 回归测试**

Run: `python3 -m unittest test_webui_server test_webui_state test_webui_monitor -v`
Expected: PASS（全部测试)

- [ ] **Step 5: 提交**

```bash
git add webui.py
git commit -m "Add webui main() entrypoint with browser launch and shutdown cleanup"
```

---

## Task 9: 前端 — index.html 与 style.css 正式内容

**Files:**
- Modify: `webui/index.html`
- Modify: `webui/style.css`

本任务替换 Task 5 的桩文件。前端无单元测试,以浏览器观察验证。

- [ ] **Step 1: 写 index.html**

把 `webui/index.html` 整个替换为:

```html
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ICBC 自动预约控制面板</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <header>
    <h1>🚗 ICBC 自动预约控制面板</h1>
    <span id="monitor-indicator" class="indicator off">● 已停止</span>
  </header>

  <nav class="tabs">
    <button class="tab active" data-tab="monitor">监控</button>
    <button class="tab" data-tab="config">配置</button>
  </nav>

  <section id="tab-monitor" class="panel">
    <div class="card">
      <h2>状态</h2>
      <div id="status-body">加载中…</div>
      <div class="controls">
        <button id="btn-start">启动监控</button>
        <button id="btn-stop">停止监控</button>
      </div>
      <p class="hint">关闭面板程序会同时停止监控(仅关闭浏览器标签页不影响,服务仍在后台运行)。</p>
    </div>
    <div class="card">
      <h2>实时输出</h2>
      <pre id="console">—</pre>
    </div>
  </section>

  <section id="tab-config" class="panel hidden">
    <div class="card">
      <h2>配置</h2>
      <div id="readiness"></div>
      <form id="config-form"></form>
      <div class="controls">
        <button id="btn-save">保存配置</button>
        <span id="save-msg"></span>
      </div>
    </div>
  </section>

  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 写 style.css**

把 `webui/style.css` 整个替换为:

```css
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: ui-sans-serif, system-ui, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f4f5f7;
  color: #1f2430;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: #1f2430;
  color: #fff;
}
header h1 { font-size: 17px; margin: 0; }
.indicator { font-size: 13px; }
.indicator.on { color: #3ad07a; }
.indicator.off { color: #9aa0ad; }
.tabs { display: flex; gap: 2px; padding: 10px 20px 0; background: #e9ebef; }
.tab {
  padding: 8px 20px; border: none; cursor: pointer;
  background: #d7dae1; color: #6b7280;
  border-radius: 6px 6px 0 0; font-size: 14px;
}
.tab.active { background: #f4f5f7; color: #1f2430; font-weight: 700; }
.panel { padding: 20px; }
.panel.hidden { display: none; }
.card {
  background: #fff; border: 1px solid #e0e2e8; border-radius: 8px;
  padding: 16px 18px; margin-bottom: 16px;
}
.card h2 { font-size: 15px; margin: 0 0 12px; }
.controls { margin-top: 12px; display: flex; align-items: center; gap: 10px; }
button {
  padding: 7px 16px; border: none; border-radius: 5px; cursor: pointer;
  font-size: 13px; background: #2f7be2; color: #fff;
}
button#btn-stop { background: #e2492f; }
.hint { font-size: 12px; color: #8a8f9a; margin: 10px 0 0; }
#console {
  background: #11141b; color: #9fe6b8; font-size: 12px;
  font-family: ui-monospace, monospace; padding: 12px;
  border-radius: 6px; height: 280px; overflow-y: auto; white-space: pre-wrap;
}
#status-body { font-size: 14px; line-height: 1.9; }
#readiness { font-size: 13px; margin-bottom: 12px; }
fieldset {
  border: 1px solid #e0e2e8; border-radius: 6px;
  margin: 0 0 14px; padding: 10px 14px;
}
legend { font-weight: 700; font-size: 13px; padding: 0 6px; }
.field {
  display: flex; align-items: center; gap: 10px; margin: 7px 0;
}
.field span { width: 200px; flex: none; font-size: 13px; color: #3a3f4a; }
.field input[type=text] {
  flex: 1; padding: 5px 8px; border: 1px solid #cfd2d9; border-radius: 4px;
  font-size: 13px;
}
#save-msg { font-size: 13px; color: #3ad07a; }
```

- [ ] **Step 3: 运行观察**

Run: `python3 webui.py`
Expected: 浏览器打开后看到面板:深色顶栏 + 标题 + 「已停止」指示;两个标签「监控」「配置」;监控页有状态卡、启停按钮、关闭提示、深色实时输出框。点标签暂时不会切换(逻辑在 Task 10)。看完按 Ctrl+C 退出。

- [ ] **Step 4: 提交**

```bash
git add webui/index.html webui/style.css
git commit -m "Add control panel HTML and CSS"
```

---

## Task 10: 前端 — app.js 正式内容

**Files:**
- Modify: `webui/app.js`

- [ ] **Step 1: 写 app.js**

把 `webui/app.js` 整个替换为:

```javascript
const $ = (sel) => document.querySelector(sel);

async function getJSON(url) {
  const resp = await fetch(url);
  return resp.json();
}
async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return resp.json();
}

// ── 标签切换 ──
let pollTimer = null;
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name));
  $("#tab-monitor").classList.toggle("hidden", name !== "monitor");
  $("#tab-config").classList.toggle("hidden", name !== "config");
  if (name === "monitor") startPolling();
  else stopPolling();
}

// ── 监控页轮询 ──
function startPolling() {
  if (pollTimer) return;
  refreshStatus();
  pollTimer = setInterval(refreshStatus, 2500);
}
function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}
async function refreshStatus() {
  const s = await getJSON("/api/status");
  const ind = $("#monitor-indicator");
  ind.textContent = s.monitor_running ? "● 监控中" : "● 已停止";
  ind.className = "indicator " + (s.monitor_running ? "on" : "off");
  $("#status-body").innerHTML = renderStatus(s);
  const c = await getJSON("/api/console");
  const pre = $("#console");
  pre.textContent = c.lines.length ? c.lines.join("\n") : "—";
  pre.scrollTop = pre.scrollHeight;
}
function renderStatus(s) {
  const booking = s.booking ? (s.booking.status || "unknown") : "未预约";
  const ls = s.log_summary;
  const log = ls
    ? `${ls.errors} 错误 / ${ls.warnings} 警告 / ${ls.no_appointments} 次无名额`
    : "无日志";
  return `预约状态:${booking}<br>上次运行:${s.last_run || "从未"}<br>最近日志:${log}`;
}

// ── 启动 / 停止 ──
$("#btn-start").addEventListener("click", async () => {
  await postJSON("/api/monitor/start");
  refreshStatus();
});
$("#btn-stop").addEventListener("click", async () => {
  await postJSON("/api/monitor/stop");
  refreshStatus();
});

// ── 配置表单 ──
async function loadConfig() {
  const cfg = await getJSON("/api/config");
  const form = $("#config-form");
  form.innerHTML = "";
  const groups = {};
  cfg.fields.forEach((f) => {
    (groups[f.group] = groups[f.group] || []).push(f);
  });
  Object.keys(groups).forEach((g) => {
    const fs = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.textContent = g;
    fs.appendChild(legend);
    groups[g].forEach((f) => fs.appendChild(renderField(f)));
    form.appendChild(fs);
  });
  const r = $("#readiness");
  r.textContent = cfg.readiness.length
    ? "⚠️ 还需填写:" + cfg.readiness.join("、")
    : "✅ 必填项已完成";
}
function renderField(f) {
  const row = document.createElement("label");
  row.className = "field";
  const span = document.createElement("span");
  span.textContent = f.label;
  const input = document.createElement("input");
  if (f.type === "bool") {
    input.type = "checkbox";
    input.checked = !!f.value;
  } else {
    input.type = "text";
    input.value = f.value == null ? "" : f.value;
  }
  input.dataset.id = f.id;
  input.dataset.type = f.type;
  row.appendChild(span);
  row.appendChild(input);
  return row;
}
$("#btn-save").addEventListener("click", async () => {
  const changes = {};
  document.querySelectorAll("#config-form input").forEach((i) => {
    changes[i.dataset.id] =
      i.dataset.type === "bool" ? i.checked : i.value;
  });
  const res = await postJSON("/api/config", changes);
  $("#save-msg").textContent = `已保存 ${res.applied.length} 项`;
  loadConfig();
});

// ── 初始化 ──
switchTab("monitor");
loadConfig();
```

- [ ] **Step 2: 运行并在浏览器里手动验证**

Run: `python3 webui.py`
Expected,在浏览器里逐项确认:
- 点「配置」标签 → 表单按分组(ICBC 账户 / 日期·时间 / Gmail / 自动预约 / 通知 / 高级)显示,顶部有就绪提示。
- 改一个字段(如姓氏)→ 点「保存配置」→ 出现「已保存 N 项」。
- 点「监控」标签 → 状态卡显示预约状态/上次运行/日志摘要;指示灯为「已停止」。
- 点「启动监控」→ 指示灯转「监控中」,实时输出框出现 `road.py` 的输出(若依赖齐全)。
- 点「停止监控」→ 指示灯转回「已停止」。
- 终端 Ctrl+C → 若监控还在跑,打印 `⏹ 正在停止监控...` 后退出。

- [ ] **Step 3: 回归测试**

Run: `python3 -m unittest test_webui_server test_webui_state test_webui_monitor -v`
Expected: PASS（全部测试)

- [ ] **Step 4: 提交**

```bash
git add webui/app.js
git commit -m "Add control panel frontend logic"
```

---

## Task 11: start.sh — 新增「打开控制面板」菜单项

**Files:**
- Modify: `start.sh`

- [ ] **Step 1: 改菜单文案**

把 `start.sh` 里这段:

```bash
echo "1. 🚀 Live Mode (connect to real ICBC system)"
echo "2. 📊 Check Status"
echo "3. 📋 View Recent Logs"
echo "4. ⚙️  Configure (edit config.yml interactively)"
echo ""
read -p "Enter choice (1-4): " choice
```

替换为:

```bash
echo "1. 🚀 Live Mode (connect to real ICBC system)"
echo "2. 📊 Check Status"
echo "3. 📋 View Recent Logs"
echo "4. ⚙️  Configure (edit config.yml interactively)"
echo "5. 🖥️  Open control panel (web UI)"
echo ""
read -p "Enter choice (1-5): " choice
```

- [ ] **Step 2: 加 case 分支**

把 `start.sh` 里 `case` 中的 `4)` 分支:

```bash
    4)
        echo ""
        python3 configure.py
        ;;
```

替换为:

```bash
    4)
        echo ""
        python3 configure.py
        ;;
    5)
        echo ""
        echo "🖥️  Opening control panel..."
        python3 webui.py
        ;;
```

- [ ] **Step 3: 语法检查并运行验证**

Run: `bash -n start.sh && echo "syntax ok"`
Expected: 打印 `syntax ok`

Run: `./start.sh`,在菜单输入 `5`
Expected: 启动控制面板,浏览器打开;Ctrl+C 干净退出。

- [ ] **Step 4: 提交**

```bash
git add start.sh
git commit -m "Add control panel option to start.sh menu"
```

---

## Task 12: 文档 — README 记录控制面板

**Files:**
- Modify: `README.md`
- Modify: `README.zh.md`

- [ ] **Step 1: 改 README.md 的 Usage 段**

在 `README.md` 的 `## 📖 Usage` 段、`### Launcher` 小节之后,新增一个小节:

```markdown
### Control panel (web UI)

```bash
python3 webui.py
```

Starts a local control panel and opens it in your browser. From there you
can edit the configuration, start and stop the monitor, and watch live
status and console output — no command line needed. Uses only the Python
standard library (no extra dependencies). The server binds to
`127.0.0.1` only.

Note: stopping `webui.py` (Ctrl+C) also stops a running monitor. Closing
just the browser tab does not — the server keeps running in the background.
```

并把 `### Launcher` 小节里的菜单选项列表更新为包含第 5 项:

```markdown
It will prompt you to pick:
- `1` — 🚀 Live mode (connect to the real ICBC system)
- `2` — 📊 Show status
- `3` — 📋 Show recent logs
- `4` — ⚙️ Configure (edit config.yml interactively)
- `5` — 🖥️ Open control panel (web UI)
```

- [ ] **Step 2: 改 README.md 的 Project Files 段**

在 `## 📁 Project Files` 的文件表里追加这几行(放在 `start.sh` 行之后):

```markdown
| `webui.py` | Web control panel server (stdlib only) |
| `webui_state.py` | Config + status data layer for the panel |
| `webui_monitor.py` | Manages the road.py subprocess for the panel |
| `webui/` | Control panel frontend (HTML/CSS/JS) |
```

- [ ] **Step 3: 改 README.zh.md**

在 `README.zh.md` 中找到对应的「使用」/「启动器」段落,以同样结构加入中文版控制面板说明:

```markdown
### 控制面板(网页版)

```bash
python3 webui.py
```

启动一个本地控制面板并自动在浏览器中打开。在面板里可以编辑配置、启动/停止
监控、查看实时状态和输出,全程无需命令行。仅用 Python 标准库,不需要安装额外
依赖。服务只绑定 `127.0.0.1`。

注意:停止 `webui.py`(Ctrl+C)会一并停止正在运行的监控;仅关闭浏览器标签页
不会,服务仍在后台运行。
```

并把启动器菜单选项列表更新为包含第 5 项「🖥️ 打开控制面板(网页版)」。

- [ ] **Step 4: 提交**

```bash
git add README.md README.zh.md
git commit -m "Document the web control panel in README"
```

---

## Task 13: 端到端手动验证

**Files:** 无(纯验证)

- [ ] **Step 1: 全量测试**

Run: `python3 -m unittest test_webui_state test_webui_monitor test_webui_server -v`
Expected: PASS（全部测试)

- [ ] **Step 2: 干净环境走一遍首次运行**

```bash
# 在一个临时副本里验证,不动真实 config.yml
mkdir -p /tmp/icbc-e2e && cp -r . /tmp/icbc-e2e/src && cd /tmp/icbc-e2e/src
rm -f config.yml
python3 webui.py
```

Expected:
- 终端提示从 `config.example.yml` 创建了 `config.yml`。
- 浏览器打开面板。
- 「配置」标签可填写并保存;`config.yml` 被正确写入。
- 「监控」标签的启停按钮可用。
- Ctrl+C 干净退出。
验证完 `cd` 回项目目录,删除 `/tmp/icbc-e2e`。

- [ ] **Step 3: 验证「关面板即停监控」连锁反应**

在项目目录运行 `python3 webui.py`,浏览器里点「启动监控」,确认监控在跑,然后在终端按 Ctrl+C。
Expected: 终端先打印 `⏹ 正在停止监控...` 再打印 `✅ 已退出`;用 `ps` 确认没有遗留的 `road.py` 进程。

- [ ] **Step 4: 最终提交(若有验证中发现的小修)**

```bash
git add -A
git commit -m "Finalize web control panel"
```

若 Step 1-3 全部通过且无需改动,跳过本步。

---

## Self-Review

**Spec coverage** — 逐条对照 `docs/superpowers/specs/2026-05-21-web-control-panel-design.md`:

- 跨平台 / 零新依赖 → Task 1-13 全程仅用标准库 + `unittest`;`Monitor` 用 `sys.executable`。✓
- 三模块拆分(`webui.py` / `webui_state.py` / `webui_monitor.py`)→ Task 1-8。✓
- 复用 `configure.py` 函数 → Task 1-3 通过 `webui_state` 调用。✓
- 静态前端 `webui/index.html|style.css|app.js` → Task 5 建桩,Task 9-10 正式内容。✓
- 七个接口(static / config GET+POST / monitor start+stop / status / console)→ Task 5-7。✓
- 进程管理 + 环形缓冲 → Task 4。✓
- 分标签页布局 → Task 9-10。✓
- 关面板即停监控 + 三处提示 → Task 8(终端启动提示、退出提示)+ Task 9(浏览器内 `.hint`)。✓
- 端口占用自动 +1 → Task 5 `find_free_port`。✓
- 状态文件按 `data_directory` 解析 → Task 3 `_data_dir`。✓
- `ensure_config_exists` 首次运行 → Task 8 `main()`。✓
- 依赖检查 → Task 8 `_check_dependencies`。✓
- start.sh 菜单项 → Task 11。✓
- 测试方式(config 往返 / 进程管理 / 接口 / 手动)→ Task 1-13。✓

**Placeholder scan** — Task 5 的 `def main(): pass` 是有意的占位,Task 8 Step 1 明确「整段替换」,非遗漏。其余步骤均含完整代码或确切命令。✓

**Type consistency** — 跨任务核对:
- `configure` 函数名 `read_lines` / `write_lines` / `get_value` / `set_value` / `ensure_config_exists` / `readiness_issues` 与现有 `configure.py` 一致。✓
- `webui_state` 对外:`read_config()` / `write_config(changes)` / `read_status()` / `CONFIG_FIELDS`,Task 1-3 定义、Task 6-7 调用一致。✓
- `Monitor` 方法 `start` / `stop` / `is_running` / `pid` / `console`,Task 4 定义、Task 7 与测试调用一致。✓
- 接口 JSON 形状:`/api/config` → `{fields, readiness}`;`/api/config` POST → `{applied}`;`/api/status` → `{booking, last_run, log_summary, monitor_running, monitor_pid}`;`/api/console` → `{lines}`;monitor 启停 → `{running, started/stopped}`。前端 `app.js`(Task 10)消费的字段与之逐一对应。✓
- 字段 `id` 格式 `section.key` / `_root.key`,`webui_state._dotted` 产出与 `write_config` 的 `by_id` 解析一致。✓
