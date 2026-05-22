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
