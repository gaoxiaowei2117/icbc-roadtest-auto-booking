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
