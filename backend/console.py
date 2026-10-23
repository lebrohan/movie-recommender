"""Explicit console setup for CLI entry points.

Windows consoles often default to cp1252, which cannot encode the glyphs used in CLI output
(check, cross, star, em dash, ellipsis). Call use_utf8_console() as the first statement of an
entry point's main(); never call it at import time.
"""

import sys


def use_utf8_console() -> None:
    """Switch stdout and stderr to UTF-8 (undecodable output is replaced). Idempotent."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
