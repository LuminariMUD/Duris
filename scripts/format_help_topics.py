#!/usr/bin/env python3
"""Normalize section spacing and progression label contrast in authored help.

Run without --write to check the maintained sources without modifying them.
Only standalone ==Section== headings and dark-blue level/circle labels change.
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "help" / "duris_help_parsed.hlp",
    ROOT / "lib" / "information" / "help_index",
)
HEADING = re.compile(r"^==[^=\n]{2,70}==$")
PROGRESSION = re.compile(
    r"^([ \t]*)&\+b(?=\d+(?:st|nd|rd|th) (?:Level|Circle):)"
)


def format_text(text):
    lines = text.split("\n")
    result = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if HEADING.fullmatch(line.strip()):
            while result and not result[-1].strip():
                result.pop()
            if result:
                result.append("")
            result.append(line)
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            if index < len(lines):
                result.append("")
            continue
        result.append(PROGRESSION.sub(r"\1&+W", line))
        index += 1
    return "\n".join(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="update both maintained help sources")
    args = parser.parse_args()
    changed = []
    for path in SOURCES:
        original = path.read_bytes()
        # Preserve any old non-UTF8 help bytes instead of dropping content.
        text = original.decode("utf-8", errors="surrogateescape")
        updated = format_text(text).encode("utf-8", errors="surrogateescape")
        if updated == original:
            continue
        changed.append(str(path.relative_to(ROOT)))
        if args.write:
            path.write_bytes(updated)
    if changed:
        print(("Formatted: " if args.write else "Needs formatting: ") +
              ", ".join(changed))
    else:
        print("Help formatting is up to date.")
    return int(bool(changed) and not args.write)


if __name__ == "__main__":
    raise SystemExit(main())
