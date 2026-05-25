"""Locate bundled resources whether running from source or a PyInstaller exe.

When frozen, PyInstaller extracts data files to sys._MEIPASS at runtime.
From source, resources sit next to this file.
"""

import os
import sys


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)
