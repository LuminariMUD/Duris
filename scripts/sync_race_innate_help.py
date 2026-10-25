#!/usr/bin/env python3
"""Rewrite each player race's ==Innate abilities== list in help/duris_help_parsed.hlp.

The list is generated from the ADD_RACIAL_INNATE calls in src/classes/innates.c, in the
same order and format list_innates() uses in game. Run it after adding or changing a racial
innate; --check only reports races whose help is out of date.

Usage: scripts/sync_race_innate_help.py [--check]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
HELP = ROOT / "help" / "duris_help_parsed.hlp"
PASSIVE_NOTE = "'*' Designates passive ability."


def read(path):
	return path.read_text(encoding="utf-8", errors="ignore")


def without_comments(text):
	return re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)


def expected_lists():
	"""Map each player race's help title to the innate list lines it should show."""
	structs = without_comments(read(SRC / "core" / "structs.h"))
	defines = read(SRC / "core" / "defines.h")
	innates = without_comments(read(SRC / "classes" / "innates.c"))
	common = read(SRC / "core" / "common.c")

	innate_defines = structs[structs.index("#define INNATE_HORSE_BODY"):structs.index("#define LAST_INNATE")]
	innate_ids = {name: int(value) for name, value in
		      re.findall(r"^#define\s+(\w+)\s+(\d+)\b", innate_defines, re.M)}
	race_ids = {name: int(value) for name, value in
		    re.findall(r"^#define (RACE_\w+) (\d+)\b", defines, re.M)}

	table = re.search(r"innates_data\[LAST_INNATE \+ 1\] = \{(.*?)\n\};", innates, re.S)
	entries = re.findall(r'\{\s*"([^"]*)"\s*,\s*(\w+)\s*\}', table.group(1))
	last_innate = innate_ids[re.search(r"#define LAST_INNATE (\w+)", structs).group(1)]
	if len(entries) != last_innate + 1:
		sys.exit(f"innates_data has {len(entries)} entries, expected {last_innate + 1}")

	levels = {}
	# Inspect every call, excluding the macro definition: unsupported arguments must
	# stop the generator before it can publish a silently incomplete list.
	calls = re.sub(r"^#define ADD_RACIAL_INNATE[^\n]*", "", innates, flags=re.M)
	for call in re.finditer(r"\bADD_RACIAL_INNATE\b", calls):
		match = re.match(r"ADD_RACIAL_INNATE\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\d+)\s*\)\s*;",
				 calls[call.start():])
		if not match:
			sys.exit("Cannot parse racial innate call: " + calls[call.start():].splitlines()[0])
		innate, race, level = match.groups()
		if innate not in innate_ids or race not in race_ids or not 0 <= innate_ids[innate] <= last_innate:
			sys.exit("Unresolved racial innate call: " + match.group(0))
		levels.setdefault(race_ids[race], {})[innate_ids[innate]] = int(level)

	names = re.search(r"race_names_table\[.*?\]\s*=\s*\{(.*?)\n\};", common, re.S).group(1)
	races = re.findall(r'\{\s*"([^"]+)"\s*,\s*"[^"]*"\s*,\s*"[^"]*"\s*,\s*"[^"]*"\s*\}', names)
	player_max = race_ids[re.search(r"#define RACE_PLAYER_MAX (RACE_\w+)", defines).group(1)]

	lists = {}
	for race in range(1, player_max + 1):
		lines = []
		for innate, (name, func) in enumerate(entries):
			level = levels.get(race, {}).get(innate)
			if not level:
				continue
			line = (" " if func != "NULL" else "*") + name
			if level > 1:
				line += f" (obtained at level {level})"
			lines.append(line)
		lists[races[race].lower()] = lines + [PASSIVE_NOTE] if lines else ["None."]
	return lists


def sync(check):
	lists = expected_lists()
	blocks = read(HELP).split("\n#0\n")
	stale = []
	for index, block in enumerate(blocks):
		lines = block.split("\n")
		# Each entry starts with a short title line, then "<Title> - Last Edited: ...".
		title = lines[1].split(" - Last Edited:")[0].strip().lower() if len(lines) > 1 else ""
		if title not in lists or "==Innate abilities==" not in lines:
			continue
		start = lines.index("==Innate abilities==") + 1
		# The help layout keeps a blank line after the section heading.
		if start < len(lines) and not lines[start]:
			start += 1
		end = start
		while end < len(lines) and lines[end] not in (PASSIVE_NOTE, "None."):
			end += 1
		if lines[start:end + 1] != lists[title]:
			stale.append(title)
			blocks[index] = "\n".join(lines[:start] + lists[title] + lines[end + 1:])

	if check:
		if stale:
			print("Race help innate lists are out of date: " + ", ".join(stale))
			print("Run scripts/sync_race_innate_help.py to update help/duris_help_parsed.hlp.")
			return 1
		print("Race help innate lists match innates.c.")
		return 0
	if stale:
		HELP.write_text("\n#0\n".join(blocks), encoding="utf-8")
		print("Updated: " + ", ".join(stale))
	else:
		print("Already up to date.")
	return 0


if __name__ == "__main__":
	sys.exit(sync("--check" in sys.argv[1:]))
