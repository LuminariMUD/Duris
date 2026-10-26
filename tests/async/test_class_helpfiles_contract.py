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
    for circle in re.findall(r"(?m)^&\+W(\d+)(?:st|nd|rd|th) Circle:", skill_entry):
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


# All base-class help pages and class skillsets follow the same ANSI style as
# specialization pages. Check progression ordering, line wrapping, and innates.
def ansi_visible_length(line):
    return len(re.sub(r"&(?:\+[A-Za-z]|[nN])", "", line))


def assert_progression(section, unit, topic):
    if section.strip() == "None.":
        return
    groups = []
    for line in section.splitlines():
        header = re.fullmatch(
            rf"&\+W(\d+)(?:st|nd|rd|th) {unit}: &\+c(.+)&n", line
        )
        continuation = re.fullmatch(r"    &\+c(.+)&n", line)
        assert ansi_visible_length(line) <= 79, f"Overflow in {topic}: {line}"
        if header:
            groups.append([int(header[1]), header[2]])
        elif continuation:
            assert groups, f"Orphan continuation in {topic}: {line}"
            assert groups[-1][1].endswith(","), (
                f"Missing separator before continuation in {topic}: {line}"
            )
            groups[-1][1] += " " + continuation[1]
        else:
            raise AssertionError(f"Unexpected {unit} progression in {topic}: {line}")
    assert groups, f"Empty {unit} progression in {topic}"
    positions = [level for level, _ in groups]
    assert positions == sorted(set(positions)), f"Unsorted {unit} labels in {topic}"
    for level, names in groups:
        abilities = names.split(", ")
        assert abilities == sorted(abilities, key=str.casefold), (
            f"Unsorted abilities at {unit} {level} in {topic}"
        )
        assert len(abilities) == len(set(abilities)), f"Duplicate ability in {topic}"


def assert_innates(section, topic):
    if section.strip() == "None.":
        return
    seen = []
    for line in section.splitlines():
        if line == "'*' Designates passive ability.":
            continue
        match = re.fullmatch(
            r"([ *])&\+c([^&\n]+)&n"
            r"(?: \(obtained at level &\+c(\d+)&n\))?", line
        )
        assert match, f"Invalid innate ANSI in {topic}: {line}"
        seen.append((int(match[3] or 1), match[2]))
    assert seen == sorted(seen, key=lambda x: (x[0], x[1].casefold())), (
        f"Unsorted innate list in {topic}"
    )


for class_name in class_names:
    key = class_name.lower()
    main_help = parsed_map[key][1]
    skill_help = parsed_map[f"{key} skills"][1]
    for topic, entry in ((key, main_help), (f"{key} skills", skill_help)):
        innates = re.search(
            r"==Innate abilities==\n(.*?)(?=\n==|\Z)", entry, re.S
        )
        assert innates, f"Missing innate section: {topic}"
        assert_innates(innates[1].strip("\n"), topic)
    for section, unit in (("Skills", "Level"), ("Spells", "Circle")):
        match = re.search(
            rf"=={section}==\n(.*?)(?=\n==|\Z)", skill_help, re.S
        )
        assert match, f"Missing section {section} in {key}"
        assert_progression(match[1].strip(), unit, key)
    allowed = re.search(
        r"==Allowed races==\n(.*?)(?=\nThese are normal-roster)", main_help, re.S
    )
    assert allowed, f"Missing allowed races in {key}"
    listing = allowed[1].strip().splitlines()
    if listing[0].startswith("None in the normal creation roster."):
        continue
    assert listing[0].startswith("&+W*&n "), f"Missing race bullet in {key}"
    assert all(ansi_visible_length(line) <= 79 for line in listing), key
    assert all(line.startswith("  ") for line in listing[1:]), key
    from_lines = " ".join(
        [listing[0][len("&+W*&n "):]] + [line.strip() for line in listing[1:]]
    )
    canonical = set(re.findall(
        r'\{\s*"[^"]+",\s*"[^"]+",\s*"([^"]+)",\s*"[^"]+"\s*\}',
        COMMON_C
    ))
    assert all(race in canonical for race in from_lines.split(", ")), (
        f"Noncanonical race coloring for {key}"
    )

# Bard's base songs and instruments also have level-based progression.
bard_base = parsed_map["bard skills"][1]
for part in ("Songs", "Instruments"):
    match = re.search(rf"=={part}==\n(.*?)(?=\n==|\Z)", bard_base, re.S)
    assert match, f"Missing {part} in Bard help"
    assert_progression(match[1].strip(), "Level", f"Bard {part}")


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
    plain_body = re.sub(r"&(?:\+[A-Za-z]|[nN])", "", body[1])
    for level, names in re.findall(r"(?m)^(\d+)(?:st|nd|rd|th) Level:([^\n]*(?:\n +[^\n]+)*)", plain_body):
        for name in names.replace("\n", " ").split(","):
            name = name.strip()
            assert name not in listed, f"Duplicate Bard {section} entry: {name}"
            listed[name] = int(level)
    assert musical_grants[kind], f"No source {kind} grants found"
    assert listed == musical_grants[kind], f"Bard {section} differs from skills.c"

minstrel_help = parsed_map["minstrel"][1]
song_changes = re.search(r"==Song changes==\n(.*?)(?=\n==|\Z)", minstrel_help, re.S)
assert song_changes, "Missing Minstrel song progression"
listed = {name: (int(level), int(cap)) for level, name, cap in re.findall(
    r"(?m)^&\+W(\d+)(?:st|nd|rd|th) Level: &\+c(.+?) \(cap (\d+)%\)&n$",
    song_changes[1])}
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

# Fire Magus gains the existing active Fireshield innate at specialization level 30.
# Keep its registered level/spec and both published help entries in sync.
fire_fireshield = re.findall(
    r"ADD_CLASS_INNATE\(\s*INNATE_FIRESHIELD,\s*CLASS_CONJURER,\s*(\d+),\s*(SPEC_\w+)\s*\)",
    (SRC / "innates.c").read_text(),
)
assert fire_fireshield == [("30", "SPEC_FIRE")], (
    f"Incorrect Fire Magus innate fireshield registration: {fire_fireshield}"
)
for entries in (parsed_map, index_map):
    fire_help = entries["fire magus"][1]
    fire_innates = re.search(r"==Innate additions==\n(.*?)(?=\n==|\Z)", fire_help, re.S)
    assert fire_innates and (
        "\n &+cfireshield&n (obtained at level &+c30&n)\n" in fire_innates[1]
    ), "Fire Magus help must show active level-30 innate fireshield"
    assert "innate fireshield" in fire_help.lower(), (
        "Fire Magus help must document the activation command"
    )


# The removed Holy Intercession grant must not linger in either imported
# Holyman specialization entry; they should describe only available spells.
for entries in (parsed_map, index_map):
    assert "holy intercession" not in entries["holyman"][1].lower(), (
        "Retired Holy Intercession still advertised for Holyman"
    )

# Cleric spec help must reflect the currently registered defensive auras.
spell_aura = re.search(r'\{\s*"([^"]+)",\s*do_aura_spell_protection\s*\}',
                       (SRC / "innates.c").read_text())
protection_aura = re.search(r'\{\s*"([^"]+)",\s*do_aura_protection\s*\}',
                            (SRC / "innates.c").read_text())
assert spell_aura and protection_aura, "Defensive aura command registration missing"
for entries in (parsed_map, index_map):
    assert f"&+c{spell_aura[1]}&n" in entries["healer"][1], \
        "Healer help must use the registered Spell Protection aura command"
    assert f"&+c{protection_aura[1]}&n" in entries["zealot"][1], \
        "Zealot help must use the registered Protection aura command"
    assert "&+cwarding faith&n" not in entries["healer"][1].lower()
    assert "&+caura_of_improved_healing&n" not in entries["healer"][1]


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
        lines = match[1].strip().splitlines()
        numbers = []
        for line in lines:
            if re.match(r"^[^:\n]+: (?:circle|level) \d+", line):
                raise AssertionError(f"Old progression format in {title}: {line}")
            row = re.match(rf"^&\+W(\d+)(?:st|nd|rd|th) {unit}: &\+c.*&n$", line)
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


# Static specialization race-permission rows must use the canonical in-game
# race ANSI strings and keep the two imported help sources synchronized.
race_ansi = dict(re.findall(
    r'\{\s*"([^"]+)",\s*"[^"]+",\s*"([^"]+)",\s*"[^"]+"\s*\}',
    COMMON_C,
))
canonical_race_tokens = set(race_ansi.values())
for title, (_, entry) in parsed_map.items():
    if ("==Allowed races==" not in entry or
            "These permissions apply to an existing character" not in entry):
        continue
    assert "==Race permission rows==" not in entry, title
    section = re.search(r"==Allowed races==\n(.*?)(?=\n==|\Z)", entry, re.S)
    assert section, title
    list_lines = []
    for line in section[1].strip().splitlines():
        if line.startswith("These permissions apply"):
            break
        list_lines.append(line)
    if list_lines[0].startswith("None."):
        continue
    assert list_lines[0].startswith("&+W*&n "), f"Missing bullet in {title}"
    assert all(len(re.sub(r"&(?:\+[A-Za-z]|[nN])", "", line)) <= 79 for line in list_lines), title
    assert all(line.startswith("  ") for line in list_lines[1:]), title
    rendered = " ".join([list_lines[0][len("&+W*&n "):]] +
                        [line.strip() for line in list_lines[1:]])
    for race in rendered.split(", "):
        assert race in canonical_race_tokens, f"Noncanonical race ANSI in {title}: {race}"
    if title in index_map:
        body = "\n".join(entry.strip().splitlines()[3:]).strip()
        mirror = "\n".join(index_map[title][1].strip().splitlines()[2:]).strip()
        assert body == mirror, f"Divergent race help source: {title}"

assert race_ansi["Goblin"] == "&+GGoblin&n"
assert race_ansi["Githzerai"] == "&+WGith&+Gzerai&n"
assert race_ansi["Githyanki"] == "&+GGith&+Wyanki&n"

print("All 30 class help files, Bard progression, and specialization help contracts passed!")
