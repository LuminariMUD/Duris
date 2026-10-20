"""Source contracts for class help files coverage across Duris help systems."""

from _paths import SRC
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMON_C = (SRC / "common.c").read_text()
DEFINES_H = (SRC / "defines.h").read_text()
PARSED_HELP = (ROOT / "help/duris_help_parsed.hlp").read_text()
HELP_INDEX = (ROOT / "lib/information/help_index").read_text()
MAX_CIRCLE = int(re.search(r"#define MAX_CIRCLE (\d+)", (SRC / "config.h").read_text())[1])

# 1. Extract all 30 classes from class_names_table in src/common.c
class_table_match = re.search(
    r"const struct class_names\s+class_names_table\[\]\s*=\s*\{(.*?)\n\};",
    COMMON_C,
    re.DOTALL,
)
assert class_table_match is not None, "class_names_table not found in src/common.c"

class_names = []
for line in class_table_match.group(1).split("\n"):
    m = re.search(r'\{\s*"([^"]+)"', line)
    if m and m.group(1) not in ("None", "NULL"):
        class_names.append(m.group(1))

class_count = int(re.search(r"#define CLASS_COUNT (\d+)", DEFINES_H).group(1))
assert len(class_names) == class_count, f"Expected {class_count} classes, found {len(class_names)}"

# 2. Parse help/duris_help_parsed.hlp
parsed_entries = PARSED_HELP.split("\n#0\n")
parsed_map = {}
for entry in parsed_entries:
    lines = entry.strip().split("\n")
    if len(lines) >= 2:
        title_line = lines[1].strip()
        title = title_line.split(" - Last Edited:")[0].strip()
        parsed_map[title.lower()] = (title, entry)

# 3. Parse lib/information/help_index
index_entries = re.split(r"(?m)^[ \t]*#[ \t]*$", HELP_INDEX)
index_map = {}
for entry in index_entries:
    lines = entry.strip().split("\n")
    if lines:
        title_line = lines[0].strip()
        match = re.match(r'^"([^"]+)"', title_line)
        if match:
            t = match.group(1).strip()
        else:
            t = title_line.split("(")[0].strip()
        if t:
            index_map[t.lower()] = (t, entry)

# 4. Verify contracts for every class
for cls in class_names:
    cls_lower = cls.lower()
    skills_title = f"{cls_lower} skills"
    index_skill_title = f"skill_{cls_lower}"

    # Main class helpfile in parsed help
    assert cls_lower in parsed_map, f"Missing main class helpfile for '{cls}' in duris_help_parsed.hlp"
    _, main_entry = parsed_map[cls_lower]
    main_lower = main_entry.lower()

    # Core sections check (allowing case flexibility on legacy files)
    assert "==see also==" in main_lower, f"Missing '==See also==' in help for '{cls}'"
    assert "==allowed races==" in main_lower or "==allowable races==" in main_lower, f"Missing '==Allowed races==' in help for '{cls}'"
    assert "==innate abilities==" in main_lower, f"Missing '==Innate abilities==' in help for '{cls}'"

    # Skills helpfile in parsed help
    assert skills_title in parsed_map, f"Missing skills helpfile for '{cls}' ('{cls} Skills') in duris_help_parsed.hlp"
    _, skill_entry = parsed_map[skills_title]
    skill_lower = skill_entry.lower()
    assert "==skills==" in skill_lower, f"Missing '==Skills==' in skills help for '{cls}'"
    assert "==spells==" in skill_lower, f"Missing '==Spells==' in skills help for '{cls}'"
    assert "==see also==" in skill_lower, f"Missing '==See also==' in skills help for '{cls}'"
    for circle in re.findall(r"(?m)^(\d+)(?:st|nd|rd|th) Circle:", skill_entry):
        assert 1 <= int(circle) <= MAX_CIRCLE, f"Unobtainable circle {circle} in {skills_title}"

    # Main class and skillset in help_index
    assert cls_lower in index_map or cls.upper() in [t.upper() for t in index_map], f"Missing '{cls}' in lib/information/help_index"
    assert index_skill_title in index_map or f"skill_{cls.upper()}".lower() in index_map, f"Missing 'SKILL_{cls.upper()}' in lib/information/help_index"

    # Both actual import sources must carry the same maintained class/skill body.
    main_body = "\n".join(main_entry.strip().splitlines()[3:]).strip()
    skill_body = "\n".join(skill_entry.strip().splitlines()[3:]).strip()
    for key, expected in ((cls_lower, main_body), (index_skill_title, skill_body)):
        index_body = "\n".join(index_map[key][1].strip().splitlines()[2:]).strip()
        assert index_body == expected, f"Divergent help source body for {key}"

# Songs and instruments have their own ID ranges, but belong in Bard progression.
skills_source = re.sub(r"/\*.*?\*/|//[^\n]*", "", (SRC / "skills.c").read_text(), flags=re.S)
musical_grants = {"SONG": {}, "INSTRUMENT": {}}
minstrel_grants = {}
for block in re.split(r"\bSKILL_CREATE(?:_WITH_MESSAGES)?\(", skills_source)[1:]:
    name = re.match(r'"([^"]+)",\s*(SONG|INSTRUMENT)_\w+', block)
    if not name:
        continue
    base = re.search(r"\bSKILL_ADD\(CLASS_BARD,\s*(\d+),\s*(\d+)\)", block)
    spec = re.search(r"\bSPEC_SKILL_ADD\(CLASS_BARD,\s*(\d+),\s*(\d+),\s*SPEC_MINSTREL\)", block)
    if base:
        musical_grants[name[2]][name[1]] = int(base[1])
    if spec:
        minstrel_grants[name[1]] = (int(spec[1]), int(spec[2]))

bard_help = parsed_map["bard skills"][1]
for kind, section in (("SONG", "Songs"), ("INSTRUMENT", "Instruments")):
    body = re.search(r"==" + section + r"==\n(.*?)(?=\n==|\Z)", bard_help, re.S)
    assert body, f"Missing Bard {section} progression"
    listed = {}
    for level, names in re.findall(r"(?m)^(\d+)(?:st|nd|rd|th) Level:([^\n]*(?:\n +[^\n]+)*)", body[1]):
        for name in names.replace("\n", " ").split(","):
            name = name.strip()
            assert name not in listed, f"Duplicate Bard {section} entry: {name}"
            listed[name] = int(level)
    assert musical_grants[kind], f"No source {kind} grants found"
    assert listed == musical_grants[kind], f"Bard {section} differs from skills.c"

minstrel_help = parsed_map["minstrel"][1]
song_changes = re.search(r"==Song changes==\n(.*?)(?=\n==|\Z)", minstrel_help, re.S)
assert song_changes, "Missing Minstrel song progression"
listed = {name: (int(level), int(cap)) for name, level, cap in re.findall(
    r"(?m)^([^\n:]+): level (\d+), skill cap (\d+)%$", song_changes[1])}
assert minstrel_grants and listed == minstrel_grants, "Minstrel songs differ from skills.c"

# These specialization bonuses are implemented in fight.c, outside grant tables.
for title in ("blademaster", "swashbuckler"):
    entry = parsed_map[title][1]
    mechanics = re.search(r"==Class mechanics==\n(.*?)(?=\n==|\Z)", entry, re.S)
    assert mechanics and all(word in mechanics[1].lower() for word in ("parry", "riposte")), title
assert "harder to parry" in " ".join(parsed_map["swashbuckler"][1].lower().split())
for title in ("minstrel", "blademaster", "swashbuckler"):
    parsed_body = "\n".join(parsed_map[title][1].strip().splitlines()[3:]).strip()
    index_body = "\n".join(index_map[title][1].strip().splitlines()[2:]).strip()
    assert index_body == parsed_body, f"Divergent specialization help source body for {title}"

# Healer instructions must name the command registered by the innate dispatcher.
healing_aura = re.search(r'\{\s*"([^"]+)",\s*do_aura_healing\s*\}',
                         (SRC / "innates.c").read_text())
assert healing_aura, "Healing aura command registration is missing"
for entries in (parsed_map, index_map):
    assert f"&+c{healing_aura[1]}&n" in entries["healer"][1], \
        "Healer help must use the registered healing aura command"


# Specialization deltas use the same ANSI progression layout as class skillsets:
# ascending spell circles / skill levels and colored spell and skill names.
for title, (_, entry) in parsed_map.items():
    if "==Spell changes==" not in entry:
        continue
    for section_name, unit in (("Skill changes", "Level"), ("Spell changes", "Circle")):
        match = re.search(
            rf"=={section_name}==\n(.*?)(?=\n==|\Z)", entry, re.S
        )
        assert match, f"Missing {section_name} section in {title}"
        lines = match[1].splitlines()
        numbers = []
        for line in lines:
            if re.match(r"^[^:\n]+: (?:circle|level) \d+", line):
                raise AssertionError(f"Old progression format in {title}: {line}")
            row = re.match(rf"^&\+b(\d+)(?:st|nd|rd|th) {unit}: &\+c.*&n$", line)
            if row:
                numbers.append(int(row[1]))
            if line.startswith("    &+c"):
                assert line.endswith("&n"), f"Unterminated color in {title}: {line}"
        assert numbers == sorted(set(numbers)), f"Unsorted {unit} progression in {title}"

    innates = re.search(r"==Innate additions==\n(.*?)(?=\n==|\Z)", entry, re.S)
    assert innates, f"Missing Innate additions in {title}"
    innate_levels = []
    for line in innates[1].splitlines():
        if re.match(r"^[^:\n]+: level \d+", line):
            raise AssertionError(f"Old innate format in {title}: {line}")
        match = re.match(
            r"^[ *]&\+c[^&\n]+&n(?: \(obtained at level &\+c(\d+)&n\))?$", line
        )
        if match:
            innate_levels.append(int(match[1] or 1))
    assert innate_levels == sorted(innate_levels), f"Unsorted innates in {title}"

    if title in index_map:
        parsed_body = "\n".join(entry.strip().splitlines()[3:]).strip()
        index_body = "\n".join(index_map[title][1].strip().splitlines()[2:]).strip()
        assert parsed_body == index_body, f"Divergent specialization help source: {title}"

print("All 30 class help files, Bard progression, and specialization help contracts passed!")
