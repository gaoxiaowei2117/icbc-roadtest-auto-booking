#!/usr/bin/env python3
"""Interactive configuration wizard for ICBC auto-booking.

Edits config.yml in-place using line-targeted regex updates so existing
comments, indentation, and quoting style are preserved. Falls back to
copying config.example.yml when config.yml is missing.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from resources import resource_path

CONFIG_PATH = Path("config.yml")
EXAMPLE_PATH = Path("config.example.yml")


def _example_source() -> Path:
    """Locate config.example.yml — CWD first, then bundled copy."""
    if EXAMPLE_PATH.exists():
        return EXAMPLE_PATH
    return Path(resource_path("config.example.yml"))

SECTION_HEADER_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(#.*)?$")


# ── file helpers ────────────────────────────────────────────────────────────

def ensure_config_exists() -> bool:
    """Return True if config.yml was just created from the template."""
    if CONFIG_PATH.exists():
        return False
    src = _example_source()
    if not src.exists():
        print(f"❌ Neither {CONFIG_PATH} nor {EXAMPLE_PATH} found.")
        sys.exit(1)
    print(f"📋 {CONFIG_PATH} not found. Creating from {src}...")
    shutil.copy(src, CONFIG_PATH)
    print(f"✅ Created {CONFIG_PATH}\n")
    return True


def read_lines() -> list[str]:
    return CONFIG_PATH.read_text(encoding="utf-8").splitlines(keepends=True)


def write_lines(lines: list[str]) -> None:
    CONFIG_PATH.write_text("".join(lines), encoding="utf-8")


# ── YAML line-targeted read / write ─────────────────────────────────────────

def _unquote(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("\"", "'"):
        return val[1:-1]
    return val


def _is_quoted(val: str) -> bool:
    val = val.strip()
    return len(val) >= 2 and val[0] == val[-1] and val[0] in ("\"", "'")


def _find(lines: list[str], section, key: str):
    """Locate section.key (section=None for a top-level key).

    Returns (index, indent, raw_value, comment) or (None, None, None, None).
    """
    if section is None:
        for i, line in enumerate(lines):
            if line.startswith((" ", "\t")):
                continue
            m = re.match(rf"^{re.escape(key)}:[ \t]*(.*?)([ \t]*#.*)?\s*$", line.rstrip("\n"))
            if m and m.group(1).strip() != "":
                return i, "", m.group(1).strip(), m.group(2) or ""
        return None, None, None, None

    in_section = False
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if not line.startswith((" ", "\t")):
            content = stripped.strip()
            if content and not content.startswith("#"):
                hm = SECTION_HEADER_RE.match(stripped)
                in_section = bool(hm) and hm.group(1) == section
            continue
        if in_section:
            km = re.match(rf"^([ \t]+){re.escape(key)}:[ \t]*(.*?)([ \t]*#.*)?\s*$", stripped)
            if km:
                return i, km.group(1), km.group(2).strip(), km.group(3) or ""
    return None, None, None, None


def get_value(lines: list[str], section, key: str):
    idx, _indent, raw, _comment = _find(lines, section, key)
    if idx is None:
        return None
    return _unquote(raw)


def ensure_key(lines: list[str], section, key: str, default: str = '""') -> bool:
    """If section.key is missing, insert a stub line with `default`.

    Returns True if a line was added, False if the key already existed.
    Used to migrate older config.yml files that pre-date a new field.
    """
    idx, _, _, _ = _find(lines, section, key)
    if idx is not None:
        return False

    if section is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key}: {default}\n")
        return True

    section_idx = None
    for i, line in enumerate(lines):
        m = SECTION_HEADER_RE.match(line.rstrip("\n"))
        if m and m.group(1) == section:
            section_idx = i
            break

    if section_idx is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append(f"{section}:\n")
        lines.append(f"  {key}: {default}\n")
        return True

    lines.insert(section_idx + 1, f"  {key}: {default}\n")
    return True


def set_value(lines: list[str], section, key: str, new_value, quote=None) -> bool:
    """Update section.key. quote=None preserves the existing quoting style."""
    idx, indent, raw, comment = _find(lines, section, key)
    if idx is None:
        return False

    if isinstance(new_value, bool):
        val_str = "true" if new_value else "false"
    else:
        text = "" if new_value is None else str(new_value)
        if text == "":
            val_str = '""'
        else:
            do_quote = _is_quoted(raw) if quote is None else quote
            if do_quote:
                esc = text.replace("\\", "\\\\").replace("\"", "\\\"")
                val_str = f'"{esc}"'
            else:
                val_str = text

    lines[idx] = f"{indent}{key}: {val_str}{comment}\n"
    return True


# ── prompts ─────────────────────────────────────────────────────────────────

def prompt(label: str, current, validator=None) -> str:
    cur_display = current if current is not None else ""
    suffix = f" [{cur_display}]" if cur_display else ""
    while True:
        raw = input(f"  {label}{suffix}: ").strip()
        if not raw:
            return cur_display
        if validator:
            ok, msg = validator(raw)
            if not ok:
                print(f"  ⚠️  {msg}")
                continue
        return raw


def prompt_secret(label: str, current) -> str:
    cur = current or ""
    has_value = bool(cur) and "xxxx" not in cur and "YOUR_" not in cur
    cur_display = "***set***" if has_value else "(not set)"
    raw = input(f"  {label} [{cur_display}] (Enter to keep): ").strip()
    return raw if raw else cur


def prompt_bool(label: str, current) -> bool:
    cur_str = "yes" if str(current).lower() in ("true", "yes", "1") else "no"
    while True:
        raw = input(f"  {label} (yes/no) [{cur_str}]: ").strip().lower()
        if not raw:
            return cur_str == "yes"
        if raw in ("y", "yes", "true", "1"):
            return True
        if raw in ("n", "no", "false", "0"):
            return False
        print("  ⚠️  Please enter yes or no.")


def validate_date(s: str):
    return (True, "") if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else (False, "Date must be YYYY-MM-DD")


def validate_time_range(s: str):
    pattern = re.compile(r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$")
    for p in (x.strip() for x in s.split(",")):
        if not pattern.match(p):
            return False, f"Bad time range '{p}'. Expected e.g. 9:40-14:15 or 10:00-11:30,13:00-14:10"
    return True, ""


def validate_int(s: str):
    return (True, "") if s.strip().lstrip("-").isdigit() else (False, "Must be a whole number")


# ── per-section editors ─────────────────────────────────────────────────────

def edit_icbc(lines: list[str]) -> None:
    print("\n  ICBC account")
    for key, label in [
        ("drvrLastName", "Last name"),
        ("licenceNumber", "Driver licence number"),
        ("keyword", "ICBC keyword / password"),
        ("examClass", "Exam class (e.g., 5, 7)"),
        ("posID", "Test centre ID (e.g., 274)"),
    ]:
        set_value(lines, "icbc", key, prompt(label, get_value(lines, "icbc", key)))


def edit_schedule(lines: list[str]) -> None:
    print("\n  Date / time preferences")
    for key, label, validator in [
        ("expactAfterDate", "Earliest date (YYYY-MM-DD)", validate_date),
        ("expactBeforeDate", "Latest date (YYYY-MM-DD)", validate_date),
        ("expactTimeRange", "Time range (e.g., 9:40-14:15)", validate_time_range),
    ]:
        set_value(lines, "icbc", key, prompt(label, get_value(lines, "icbc", key), validator))
    for key, label in [
        ("prfDaysOfWeek", "Preferred days of week (0=Sun, e.g., [0,1,2,3,4,5,6])"),
        ("prfPartsOfDay", "Preferred parts of day (0=AM, 1=PM, e.g., [0,1])"),
    ]:
        set_value(lines, "icbc", key, prompt(label, get_value(lines, "icbc", key)))


def edit_gmail(lines: list[str]) -> None:
    print("\n  Gmail (used to read the ICBC verification code)")
    print("  ⚠️  Use a Gmail App Password (16 chars), not your normal account password.")
    enable = prompt_bool("Enable Gmail", get_value(lines, "gmail", "enable"))
    set_value(lines, "gmail", "enable", enable)
    if not enable:
        return
    set_value(lines, "gmail", "email", prompt("Gmail address", get_value(lines, "gmail", "email")))
    set_value(lines, "gmail", "password", prompt_secret("App password (16 chars)", get_value(lines, "gmail", "password")))


def edit_auto_booking(lines: list[str]) -> None:
    print("\n  Auto-booking behaviour")
    enable = prompt_bool("Enable auto-booking", get_value(lines, "autoBooking", "enable"))
    set_value(lines, "autoBooking", "enable", enable)
    if not enable:
        return
    set_value(
        lines, "autoBooking", "timeSelectionStrategy",
        prompt("Time selection strategy (earliest / best_time_slot)", get_value(lines, "autoBooking", "timeSelectionStrategy")),
    )
    set_value(lines, "autoBooking", "exitAfterSuccess", prompt_bool("Exit after successful booking", get_value(lines, "autoBooking", "exitAfterSuccess")))
    if get_value(lines, "autoBooking", "bookingTimeWindow") is not None:
        set_value(lines, "autoBooking", "bookingTimeWindow", prompt("Booking time window (e.g., 00:00-23:59)", get_value(lines, "autoBooking", "bookingTimeWindow")))


def edit_notifications(lines: list[str]) -> None:
    print("\n  Notifications (all optional)")

    print("\n  ntfy.sh:")
    en = prompt_bool("    Enable ntfy", get_value(lines, "ntfy", "enable"))
    set_value(lines, "ntfy", "enable", en)
    if en:
        set_value(lines, "ntfy", "topic", prompt("    ntfy topic", get_value(lines, "ntfy", "topic")))

    print("\n  Local sound:")
    set_value(lines, "pushsound", "enable", prompt_bool("    Enable sound notification", get_value(lines, "pushsound", "enable")))

    print("\n  Local desktop notification:")
    set_value(lines, "pushlocal", "enable", prompt_bool("    Enable pushlocal", get_value(lines, "pushlocal", "enable")))


def edit_advanced(lines: list[str]) -> None:
    print("\n  Advanced (polling & request limits)")
    set_value(lines, None, "pauseTimeMin", prompt("Pause minutes after a slot is found", get_value(lines, None, "pauseTimeMin"), validate_int))
    set_value(lines, None, "skip0Clock", prompt_bool("Skip the 23:55-00:05 window", get_value(lines, None, "skip0Clock")))
    if get_value(lines, None, "data_directory") is not None:
        set_value(lines, None, "data_directory", prompt("Data directory", get_value(lines, None, "data_directory")))

    print("\n  Request rate limit:")
    en = prompt_bool("    Enable request limit", get_value(lines, "requestLimit", "enable"))
    set_value(lines, "requestLimit", "enable", en)
    if en:
        set_value(lines, "requestLimit", "period", prompt("    Limit period (e.g., 20:15-23:15)", get_value(lines, "requestLimit", "period")))
        set_value(lines, "requestLimit", "interval", prompt("    Interval seconds", get_value(lines, "requestLimit", "interval"), validate_int))


SECTIONS = [
    ("ICBC account info", edit_icbc),
    ("Date / time preferences", edit_schedule),
    ("Gmail (verification code)", edit_gmail),
    ("Auto-booking behaviour", edit_auto_booking),
    ("Notifications", edit_notifications),
    ("Advanced settings", edit_advanced),
]


# ── walkthrough / status ────────────────────────────────────────────────────

def full_walkthrough(lines: list[str]) -> None:
    print("\n" + "=" * 48)
    print("🧭 Full setup walkthrough")
    print("=" * 48)
    print("Goes through every section in order.")
    print("Press Enter at any prompt to keep the shown [current] value.")
    total = len(SECTIONS)
    for n, (name, fn) in enumerate(SECTIONS, 1):
        print(f"\n── Step {n}/{total}: {name} " + "─" * max(0, 30 - len(name)))
        fn(lines)
    print("\n✅ Walkthrough complete.")


def readiness_issues(lines: list[str]) -> list[str]:
    issues = []
    for key, label in [
        ("drvrLastName", "ICBC last name"),
        ("licenceNumber", "ICBC licence number"),
        ("keyword", "ICBC keyword"),
    ]:
        v = get_value(lines, "icbc", key) or ""
        if not v or v.startswith("YOUR_"):
            issues.append(label)
    if str(get_value(lines, "gmail", "enable")).lower() == "true":
        email = get_value(lines, "gmail", "email") or ""
        if not email or "your-email" in email:
            issues.append("Gmail address")
        pw = get_value(lines, "gmail", "password") or ""
        if not pw or "xxxx" in pw:
            issues.append("Gmail app password")
    return issues


def show_current(lines: list[str]) -> None:
    print("\n── Current configuration ──")
    fields = [
        ("icbc", "drvrLastName", "Last name", False),
        ("icbc", "licenceNumber", "Licence #", False),
        ("icbc", "keyword", "Keyword", True),
        ("icbc", "examClass", "Exam class", False),
        ("icbc", "posID", "Test centre ID", False),
        ("icbc", "expactAfterDate", "After date", False),
        ("icbc", "expactBeforeDate", "Before date", False),
        ("icbc", "expactTimeRange", "Time range", False),
        ("icbc", "prfDaysOfWeek", "Days of week", False),
        ("icbc", "prfPartsOfDay", "Parts of day", False),
        ("gmail", "enable", "Gmail enabled", False),
        ("gmail", "email", "Gmail address", False),
        ("gmail", "password", "Gmail app password", True),
        ("autoBooking", "enable", "Auto-booking enabled", False),
        ("autoBooking", "timeSelectionStrategy", "Strategy", False),
        ("autoBooking", "exitAfterSuccess", "Exit on success", False),
        ("ntfy", "enable", "ntfy", False),
        ("pushsound", "enable", "Sound", False),
        ("pushlocal", "enable", "Local desktop", False),
        (None, "pauseTimeMin", "Pause minutes", False),
        (None, "skip0Clock", "Skip 0 o'clock", False),
        (None, "data_directory", "Data directory", False),
    ]
    for sec, key, label, secret in fields:
        cur = get_value(lines, sec, key)
        if cur is None:
            display = "(not in file)"
        elif secret:
            looks_unset = (not cur) or "xxxx" in cur or "YOUR_" in cur
            display = "(not set)" if looks_unset else "***set***"
        else:
            display = cur if cur else "(empty)"
        print(f"  {label:.<32} {display}")

    issues = readiness_issues(lines)
    if issues:
        print("\n  ⚠️  Still needs attention before running:")
        for it in issues:
            print(f"     - {it}")
    else:
        print("\n  ✅ Required fields look complete.")


# ── menu ────────────────────────────────────────────────────────────────────

def main_menu() -> None:
    while True:
        print("\n" + "=" * 48)
        print("⚙️  ICBC Auto-Booking — Configuration (config.yml)")
        print("=" * 48)
        print("  Guided setup")
        print("    1. 🧭 Full setup walkthrough (every section, in order)")
        print()
        print("  Edit a single section")
        print("    2. 👤 ICBC account info")
        print("    3. 📅 Date / time preferences")
        print("    4. 📧 Gmail (verification code)")
        print("    5. 🤖 Auto-booking behaviour")
        print("    6. 🔔 Notifications")
        print("    7. ⏱  Advanced (polling & request limits)")
        print()
        print("  Other")
        print("    8. 👁️  Show current configuration")
        print("    0. ↩  Save and exit")
        choice = input("\nChoose: ").strip()

        if choice in ("0", ""):
            print("✅ Done.")
            return

        lines = read_lines()
        if choice == "1":
            full_walkthrough(lines)
        elif choice == "2":
            edit_icbc(lines)
        elif choice == "3":
            edit_schedule(lines)
        elif choice == "4":
            edit_gmail(lines)
        elif choice == "5":
            edit_auto_booking(lines)
        elif choice == "6":
            edit_notifications(lines)
        elif choice == "7":
            edit_advanced(lines)
        elif choice == "8":
            show_current(lines)
            continue
        else:
            print("⚠️  Invalid choice.")
            continue

        write_lines(lines)
        print("✅ Saved to config.yml")


def main() -> None:
    first_run = ensure_config_exists()
    try:
        if first_run:
            print("First-time setup — let's walk through the configuration.")
            lines = read_lines()
            full_walkthrough(lines)
            write_lines(lines)
            print("✅ Saved to config.yml")
            show_current(lines)
        main_menu()
    except (KeyboardInterrupt, EOFError):
        print("\n⏹  Aborted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
