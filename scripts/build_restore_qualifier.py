#!/usr/bin/env python3
"""Build the native restore-receipt verifier."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = """
flatfile_store locker_receipt combat_outcome_intent starter_kit_intent critical_command
item_transfer_command currency_command combat_outcome_command artifact_guild_command
""".split()


def build(destination=None):
    destination = destination or ROOT / "bin/tools/qualify_flatfile_restore"
    destination.parent.mkdir(parents=True, exist_ok=True)
    sources = []
    for name in SOURCES:
        matches = list((ROOT / "src").rglob(name + ".c"))
        if len(matches) != 1:
            raise RuntimeError("ambiguous native verifier source")
        sources.append(str(matches[0]))
    subprocess.run(["g++", "-std=c++20", "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                    "-Isrc",
                    "scripts/qualify_flatfile_restore.cpp", *sources, "-lcrypto", "-lz", "-pthread",
                    "-o", str(destination)], cwd=ROOT, check=True)
    return destination


if __name__ == "__main__":
    build()
