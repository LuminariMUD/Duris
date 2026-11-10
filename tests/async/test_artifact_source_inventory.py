#!/usr/bin/env python3
"""Keep the reviewed artifact corpus and effective source bindings reproducible."""
from pathlib import Path
import runpy
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
subprocess.run([sys.executable, str(root/'scripts/artifact_source_inventory.py'), '--check'],
               cwd=root, check=True)

# Consume the actual catalog, including later object and room-stage overrides.
bindings = runpy.run_path(str(root/'scripts/artifact_source_inventory.py'))['bindings']()
assert bindings[30] == 'staff_of_power'
assert bindings[424] == 'lucrot_mindstone'
assert bindings[67242] == 'lich_spine'
