import sys

# Windows consoles often default to cp1252, which can't print the ✓/★/— used in our output.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
