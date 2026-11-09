#!/usr/bin/env python3
"""Write the source revision header used by offline valuation provenance."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

target, root = map(Path, sys.argv[1:])
git = ["git", "-C", str(root), "-c", "core.fileMode=false"]
try:
    revision = subprocess.check_output(git + ["rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
                                       text=True, timeout=30).strip()
    dirty = subprocess.check_output(
        git + ["status", "--porcelain", "--untracked-files=normal", "--", "src", "areas/src"],
        stderr=subprocess.DEVNULL, text=True, timeout=30)
    if dirty:
        revision += "-dirty"
except (OSError, subprocess.SubprocessError):
    # Exported source trees remain buildable; the binary hash still identifies
    # their exact executable. Do not invent a source commit for them.
    revision = "unavailable"

content = "#define DURIS_SOURCE_REVISION " + json.dumps(revision) + "\n"
if not target.exists() or target.read_text() != content:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as temporary:
        temporary.write(content)
    Path(temporary.name).replace(target)
