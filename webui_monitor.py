"""Manages a single road.py subprocess for the web control panel."""

import collections
import subprocess
import sys
import threading


class Monitor:
    """启停 road.py 子进程,并把它的 stdout 收进环形缓冲。"""

    def __init__(self, command=None):
        # 用 sys.executable 而非硬编码 python3,保证 Windows 也能调用
        # -u: 让 road.py 的 stdout 不缓冲,实时输出才能及时显示
        self._command = command or [sys.executable, "-u", "road.py", "config.yml"]
        self._proc = None
        self._lines = collections.deque(maxlen=500)
        self._lock = threading.Lock()
        self._reader = None
        self._generation = 0

    def is_running(self):
        return self._proc is not None and self._proc.poll() is None

    def pid(self):
        return self._proc.pid if self.is_running() else None

    def start(self):
        """启动子进程。已在运行则返回 False。"""
        with self._lock:
            if self.is_running():
                return False
            self._lines.clear()
            self._generation += 1
            gen = self._generation
            self._proc = subprocess.Popen(
                self._command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        self._reader = threading.Thread(
            target=self._read_output, args=(gen,), daemon=True)
        self._reader.start()
        return True

    def stop(self):
        """终止子进程。未运行则返回 False。"""
        with self._lock:
            if not self.is_running():
                return False
            proc = self._proc
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        return True

    def console(self):
        """返回缓冲里的输出行列表。"""
        with self._lock:
            return list(self._lines)

    def _read_output(self, gen):
        proc = self._proc
        for line in proc.stdout:
            with self._lock:
                if self._generation == gen:
                    self._lines.append(line.rstrip("\n"))
        proc.stdout.close()
