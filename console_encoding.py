"""Helpers for keeping console output readable on Windows and Unix."""

import sys


def configure_utf8_output() -> None:
    """Make stdout/stderr emit UTF-8 when Python supports reconfiguration.

    A subprocess whose stdout is redirected to a pipe can fall back to the
    Windows locale (usually GBK), even when the parent console displays UTF-8
    correctly.  The application prints emoji and Chinese status messages, so
    use UTF-8 for both streams before any output is written.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
            )
        except (AttributeError, OSError, ValueError):
            # Python 3.7+ has reconfigure(), but keep startup compatible with
            # unusual stream wrappers and older embedded runtimes.
            continue
