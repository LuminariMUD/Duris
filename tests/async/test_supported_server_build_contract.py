#!/usr/bin/env python3
"""Keep the documented server build aligned with the maintained target."""

from _paths import SRC
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
makefile = (SRC / "Makefile").read_text(encoding="ascii")
building = (ROOT / "docs" / "guides" / "BUILDING.md").read_text(encoding="ascii")
help_system = (ROOT / "docs" / "content" / "HELP_SYSTEM.md").read_text(encoding="ascii")
building_words = " ".join(building.split())

assert "__NO_MYSQL__" not in makefile
assert "make -C src BUILD_PROFILE=development" in building
assert "make -C src BUILD_PROFILE=production" in building
assert "PERSISTENCE_BACKEND=flatfile" not in building
assert "MariaDB is the only server persistence backend" in building_words
assert "Hiredis and OpenSSL remain build dependencies" in building_words
assert "__NO_MYSQL__" not in help_system

print("supported MariaDB server build contract passed")
