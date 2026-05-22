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
            if isinstance(value, bool):
                new_value = value
            else:
                new_value = str(value).strip().lower() in ("true", "yes", "1")
        elif ftype == "int":
            new_value = str(value)
        else:
            new_value = "" if value is None else str(value)
        if configure.set_value(lines, section, key, new_value):
            applied.append(cid)
    if applied:
        configure.write_lines(lines)
    return applied


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
            result = f.readline().strip()
    except OSError:
        return None
    return result if result else None


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
