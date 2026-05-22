import json
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
        self.assertEqual(status["log_summary"]["warnings"], 0)
        self.assertEqual(status["log_summary"]["recent_entries"], 2)


class PickerFieldTypesTest(unittest.TestCase):
    """新的字段类型:date / time_range / multi_select 的读写往返。"""

    def setUp(self):
        self._orig = configure.CONFIG_PATH
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "config.yml"
        shutil.copy("config.example.yml", self.cfg)
        configure.CONFIG_PATH = self.cfg

    def tearDown(self):
        configure.CONFIG_PATH = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_field_types_are_date_time_range_and_multi_select(self):
        by_id = {f["id"]: f for f in webui_state.read_config()["fields"]}
        self.assertEqual(by_id["icbc.expactAfterDate"]["type"], "date")
        self.assertEqual(by_id["icbc.expactBeforeDate"]["type"], "date")
        self.assertEqual(by_id["icbc.expactTimeRange"]["type"], "time_range")
        self.assertEqual(by_id["icbc.prfDaysOfWeek"]["type"], "multi_select")
        self.assertEqual(by_id["icbc.prfPartsOfDay"]["type"], "multi_select")

    def test_multi_select_field_exposes_options_and_parsed_value(self):
        by_id = {f["id"]: f for f in webui_state.read_config()["fields"]}
        days = by_id["icbc.prfDaysOfWeek"]
        # 模板里是 "[0,1,2,3,4,5,6]" — 应解析成 7 个字符串
        self.assertEqual(days["value"], ["0", "1", "2", "3", "4", "5", "6"])
        # options 与 FIELD_OPTIONS 对应,7 个 (value, label)
        self.assertEqual(len(days["options"]), 7)
        self.assertEqual(days["options"][0], ["0", "日"])
        parts = by_id["icbc.prfPartsOfDay"]
        self.assertEqual(parts["value"], ["0", "1"])
        self.assertEqual(len(parts["options"]), 2)

    def test_write_multi_select_serializes_to_bracket_string(self):
        applied = webui_state.write_config({
            "icbc.prfDaysOfWeek": ["1", "3", "5"],
            "icbc.prfPartsOfDay": ["0"],
        })
        self.assertIn("icbc.prfDaysOfWeek", applied)
        self.assertIn("icbc.prfPartsOfDay", applied)
        import yaml
        with open(self.cfg, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["icbc"]["prfDaysOfWeek"], "[1,3,5]")
        self.assertEqual(data["icbc"]["prfPartsOfDay"], "[0]")
        # 再读回来应是列表
        by_id = {f["id"]: f for f in webui_state.read_config()["fields"]}
        self.assertEqual(by_id["icbc.prfDaysOfWeek"]["value"], ["1", "3", "5"])

    def test_write_multi_select_accepts_legacy_string_value(self):
        # 防御性:即便有调用方仍然传字符串,也应能正确解析。
        applied = webui_state.write_config({
            "icbc.prfDaysOfWeek": "[2,4]",
        })
        self.assertEqual(applied, ["icbc.prfDaysOfWeek"])
        by_id = {f["id"]: f for f in webui_state.read_config()["fields"]}
        self.assertEqual(by_id["icbc.prfDaysOfWeek"]["value"], ["2", "4"])

    def test_write_multi_select_empty_list(self):
        applied = webui_state.write_config({"icbc.prfPartsOfDay": []})
        self.assertEqual(applied, ["icbc.prfPartsOfDay"])
        by_id = {f["id"]: f for f in webui_state.read_config()["fields"]}
        self.assertEqual(by_id["icbc.prfPartsOfDay"]["value"], [])

    def test_write_time_range_and_date_are_stored_as_string(self):
        applied = webui_state.write_config({
            "icbc.expactAfterDate": "2026-08-01",
            "icbc.expactTimeRange": "10:00-12:30",
        })
        self.assertCountEqual(applied,
                              ["icbc.expactAfterDate", "icbc.expactTimeRange"])
        by_id = {f["id"]: f for f in webui_state.read_config()["fields"]}
        self.assertEqual(by_id["icbc.expactAfterDate"]["value"], "2026-08-01")
        self.assertEqual(by_id["icbc.expactTimeRange"]["value"], "10:00-12:30")


if __name__ == "__main__":
    unittest.main()
