#!/usr/bin/env python3
"""Exact authored/generated parity outside issue 213's explicit reskin mapping.

This checks authored fields, not derived NPC mechanics or runtime dispatch.
Those require the loaded-world comparison and gameplay journeys as well.
"""
import re

from _paths import ROOT

AREAS = ROOT / "areas"
COPIES = {
    "newbie2": ("chaos_intro", 22800, 91200),
    "newbie": ("wutvr", 29200, 91400),
}
KINDS = ("wld", "mob", "obj", "zon", "qst", "shp")
COUNTS = {"newbie2": {"wld": 7, "mob": 3, "obj": 10, "zon": 1},
          "newbie": {"wld": 117, "mob": 105, "obj": 133, "zon": 1, "qst": 32, "shp": 8}}
# Shared general supplies, crafting/training materials, and the two outside
# quest items remain canonical. The stream's authored room value is retained;
# its compiled procedure supplies the actual next-stage destination.
SHARED = {
    "wld": {132575},
    "obj": {52, 53, 54, 100, 105, 106, 107, 203, 204, 214, 227, 239, 246, 256,
            293, 294, 295, 318, 319, 330, 332, 333, 334, 335, 336, 338, 355, 356,
            363, 368, 369, 377, 393, 412, 447, 450, 452, 500, 676, 706, 731, 735,
            822, 824, 825, 826, 835, 1101, 1102, 1103, 1104, 1105, 1106, 1107,
            1108, 1109, 1110, 1112, 1113, 1114, 1115, 1116, 1117, 1118, 1119,
            1120, 1121, 1122, 1124, 1126, 1127, 1128, 1129, 1130, 1131, 1132,
            1134, 1135, 1136, 1137, 1138, 1139, 1140, 1141, 1142, 1143, 1144,
            1145, 1146, 1147, 1148, 1149, 1150, 1151, 3097, 87700, 88502, 98621},
}
NAMES = {
    "Burbul": "Grubruk", "Fleurita": "Vexira", "Janella": "Zarneth", "Laurel": "Zereth",
    "Chyron": "Zyrrak", "Mier": "Zhar", "Sadev": "Kuleth", "Maerg": "Grash",
    "Gandharvas": "Nethravas", "Brodi": "Ghoruk", "Saelryn": "Vhaezra",
    "Drinnan": "Krizzik", "Llerrad": "Vargesh", "Creyset": "Kresht", "Lapney": "Mordrak",
    "Roshenbly": "Skritch", "Nalk": "Skarrix", "Agare": "Zhaleth", "Grinda": "Khardra",
    "Eian": "Orvak", "Deline": "Velkris", "Tor": "Grath", "Vaugh": "Urzak",
    "Victa": "Vorka", "Burnarg": "Morzag", "Kord": "Krag", "Quek": "Zikk",
    "Risp": "Brusk", "Perr": "Xerr", "Foet": "Vaex", "Osule": "Ozuk",
    "Esera": "Kessra", "Taiz": "Zair", "Hellfax": "Kharzul", "Lardeus": "Vorrik",
    "Silva": "Varka", "Hizzy": "Skizz",
}
MOB_RACES = {"PH": "HO", "PB": "HO", "PF": "HG", "PG": "KB", "PE": "PL",
             "PM": "PD", "P2": "TF", "CT": "MT", "GZ": "GI"}
# Taiz's visible source identity is Half-Elf despite its PH mechanical header.
# Keep that identity mapping coherent while retaining the source PH profile.
MOB_RACE_OVERRIDES = {29264: "TF"}
RACE_LABELS = {
    "PH": {"human": "orc", "humans": "orcs"},
    "PB": {"barbarian": "orc", "barbarians": "orcs"},
    "PF": {"halfling": "goblin", "halflings": "goblins"},
    "PG": {"gnome": "kobold", "gnomes": "kobolds", "gnomish": "kobold"},
    "PE": {"grey elf": "drow elf", "grey elves": "drow elves", "grey-elf": "drow elf"},
    "PM": {"mountain dwarf": "duergar", "mountain dwarves": "duergar", "dwarf": "duergar",
           "dwarves": "duergar", "dwarven": "duergar"},
    "P2": {"half-elf": "tiefling", "half-elven": "tiefling", "half-elves": "tieflings", "half elf": "tiefling"},
    "CT": {"centaur": "minotaur", "centaurs": "minotaurs"},
    "GZ": {"githzerai": "githyanki"},
}


def records(text, wanted=None):
    result = {}
    matches = list(re.finditer(r"(?m)^#(\d+)(?:~)?$", text))
    for index, match in enumerate(matches):
        ident = int(match[1])
        if wanted is not None and ident not in wanted:
            continue
        assert ident not in result, f"duplicate ID {ident}"
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[ident] = text[match.start():end]
    return result


MAPS = {}
for source, (_, old_base, new_base) in COPIES.items():
    MAPS[source] = {}
    for kind in COUNTS[source]:
        ids = records((AREAS / kind / f"{source}.{kind}").read_text())
        delta = (new_base - old_base) // 100 if kind == "zon" else new_base - old_base
        MAPS[source][kind] = {ident: ident + delta for ident in ids}


def remap(kind, ident):
    # Both tutorials form one route: a portal referencing the other stage must
    # follow its copy too. Shared supplies/services outside both maps stay shared.
    for namespaces in MAPS.values():
        if ident in namespaces.get(kind, {}):
            return namespaces[kind][ident]
    assert ident <= 0 or ident in SHARED.get(kind, set()), f"unreviewed external {kind} reference {ident}"
    return ident


def numbers(line, replacements):
    """Replace selected numeric fields, preserving all spacing and comments."""
    fields = list(re.finditer(r"-?\d+", line.split("*", 1)[0]))
    for index, value in sorted(replacements.items(), reverse=True):
        field = fields[index]
        line = line[:field.start()] + str(value) + line[field.end():]
    return line


def after_strings(lines, index, count):
    for _ in range(count):
        while "~" not in lines[index]:
            index += 1
        index += 1
    return index


def room_exit_fields(lines):
    """Typed exits for the parity fixture and authored-world walking journey."""
    index = after_strings(lines, 1, 2) + 1
    while index < len(lines) and lines[index].strip() != "S":
        marker = lines[index].strip()
        if re.fullmatch(r"D[0-9]", marker):
            direction = int(marker[1])
            index = after_strings(lines, index + 1, 2)
            values = [int(value) for value in lines[index].split()]
            assert len(values) == 3
            yield direction, index, values
            index += 1
        elif marker == "E":
            index = after_strings(lines, index + 1, 2)
        else:
            raise AssertionError(f"unexpected room field: {marker}")


def replace_visible(text, replacements, flags=re.I):
    """Replace whole visible names/phrases without consuming ANSI or other words."""
    colour = r"&(?:[+-].|=..|[nN])"
    visible, offsets = [], []
    for token in re.finditer(colour + r"|.", text, re.S):
        if not token[0].startswith("&"):
            visible.append(token[0])
            offsets.append(token.start())
    plain = "".join(visible)
    pattern = r"(?<![A-Za-z])(?:" + "|".join(re.escape(key) for key in sorted(replacements, key=len, reverse=True)) + r")(?![A-Za-z])"
    lookup = {key.lower(): value for key, value in replacements.items()}
    for match in reversed(list(re.finditer(pattern, plain, flags))):
        start, end = offsets[match.start()], offsets[match.end() - 1] + 1
        new = lookup[match[0].lower()]
        new = new.lower() if match[0].islower() else new.upper() if match[0].isupper() else new
        result, index = [], 0
        for token in re.findall(colour + r"|.", text[start:end], re.S):
            if token.startswith("&"):
                result.append(token)
            else:
                if index < len(new):
                    result.append(new[index])
                index += 1
        text = text[:start] + "".join(result) + new[index:] + text[end:]
    return text


def renamed(text, source, kind, ident, race):
    text = replace_visible(text, {"Ail-v-io": "Wutvr", "Ailvio": "Wutvr"})
    if source == "newbie2":
        return replace_visible(text, {"Plane of Life": "Plane of Chaos", "Plains of Life": "Plane of Chaos",
                                      "Life Stream": "Chaos Stream", "paladin": "reaver", "holy": "chaotic", "angelic": "chaotic"})
    text = replace_visible(text, NAMES)
    # Red is a person's name here, but lowercase red elsewhere is an unchanged
    # colour/quest ingredient. Handle only the name and explicit command target.
    text = replace_visible(text, {"Red": "Vraz"}, flags=0)
    text = replace_visible(text, {"tell red": "tell vraz", "ask red": "ask vraz",
                                  "evil races": "good races"})
    if kind == "mob":
        labels = RACE_LABELS.get("P2" if ident == 29264 else race, {})
        if labels:
            text = replace_visible(text, labels)
        header, keywords, rest = text.split("\n", 2)
        if ident == 29233:
            keywords = replace_visible(keywords, {"red": "vraz"})
        if race == "PE":
            keywords = replace_visible(keywords, {"grey": "drow"})
        text = header + "\n" + keywords + "\n" + rest
    elif kind == "wld" and ident < 29312 or kind == "obj":
        # Resident/cultural references change; generic forest-width comparisons
        # and the existing geography descriptions are preserved.
        text = replace_visible(text, {**RACE_LABELS["CT"], **RACE_LABELS["PB"]})
    elif kind == "qst":
        # The ranger's statement about non-centaurs is a lesson, not NPC identity.
        text = replace_visible(text, {"the human bard": "the orc bard"})
        if ident == 29304:
            text = replace_visible(text, {**RACE_LABELS["P2"], "bandage human": "bandage orc"})
    if kind == "wld" and ident == 29312:
        text = replace_visible(text, {"All races can choose to enter here": "Only its existing residents return here"})
    return text


def copied_record(source, kind, record):
    lines = record.splitlines(keepends=True)
    ident = int(re.match(r"#(\d+)", lines[0])[1])
    record_id, old_race = ident, None
    header_kind = "mob" if kind == "qst" else kind
    lines[0] = lines[0].replace(str(ident), str(remap(header_kind, ident)), 1)
    if kind == "wld":
        index = after_strings(lines, 1, 2)
        zone = int(lines[index].split()[0])
        lines[index] = numbers(lines[index], {0: remap("zon", zone)})
        for _, field, values in room_exit_fields(lines):
            lines[field] = numbers(lines[field], {1: remap("obj", values[1]),
                                                 2: remap("wld", values[2])})
    elif kind == "mob":
        index = after_strings(lines, 1, 4)
        old_race = lines[index + 1].split()[0].upper()
        new_race = "HO" if source == "newbie2" and ident == 22801 else MOB_RACE_OVERRIDES.get(ident, MOB_RACES.get(old_race, old_race))
        if new_race != old_race:
            lines[index + 1] = re.sub(r"^(\s*)\S+", lambda match: match[1] + new_race, lines[index + 1], count=1)
    elif kind == "obj":
        index = after_strings(lines, 1, 4)
        object_type = int(lines[index].split()[0])
        values = [int(value) for value in lines[index + 1].split()]
        if object_type == 25:  # ITEM_TELEPORT: destination room
            lines[index + 1] = numbers(lines[index + 1], {0: remap("wld", values[0])})
        elif object_type == 15:  # ITEM_CONTAINER: key object
            lines[index + 1] = numbers(lines[index + 1], {2: remap("obj", values[2])})
        elif object_type == 29:  # ITEM_SWITCH: room containing the blocked exit
            lines[index + 1] = numbers(lines[index + 1], {1: remap("wld", values[1])})
    elif kind == "qst":
        index = 1
        while index < len(lines):
            value = lines[index].strip()
            if value in ("M", "MA"):
                index = after_strings(lines, index + 1, 2)
            elif value in ("Q", "QA", "D"):
                index = after_strings(lines, index + 1, 1)
            elif re.fullmatch(r"[GR]\s+I\s+\d+", value):
                ident = int(value.split()[2])
                lines[index] = numbers(lines[index], {0: remap("obj", ident)})
                index += 1
            else:
                assert re.fullmatch(r"[GR]\s+[TCSE]\s+\d+", value) or value == "S", value
                index += 1
    elif kind == "zon":
        index = after_strings(lines, 1, 1)
        top = int(lines[index].split()[0])
        lines[index] = numbers(lines[index], {0: remap("wld", top)})
        references = {"M": {1: "mob", 3: "wld"}, "O": {1: "obj", 3: "wld"},
                      "G": {1: "obj"}, "E": {1: "obj"}, "P": {1: "obj", 3: "obj"},
                      "D": {1: "wld"}}
        for index in range(index + 1, len(lines)):
            if not re.match(r"[A-Z] ", lines[index]):
                continue
            command = lines[index][0]
            assert command in references, f"unmapped reset opcode {command}"
            values = [int(value) for value in re.findall(r"-?\d+", lines[index].split("*", 1)[0])]
            lines[index] = numbers(lines[index], {field: remap(namespace, values[field])
                                                for field, namespace in references[command].items()})
    elif kind == "shp":
        assert lines[1].strip() == "N"
        index = 2
        while int(lines[index]) != 0:
            lines[index] = numbers(lines[index], {0: remap("obj", int(lines[index]))})
            index += 1
        index += 3  # inventory terminator and buy/sell percentages
        while int(lines[index]) != 0:  # traded item types are not object references
            index += 1
        index = after_strings(lines, index + 1, 7)
        lines[index + 2] = numbers(lines[index + 2], {0: remap("mob", int(lines[index + 2]))})
        lines[index + 4] = numbers(lines[index + 4], {0: remap("wld", int(lines[index + 4]))})
    return renamed("".join(lines), source, kind, record_id, old_race)


def expected_copy(source, kind):
    original = (AREAS / kind / f"{source}.{kind}").read_text()
    return "".join(copied_record(source, kind, record) for record in records(original).values())


def main():
    active = [line.split()[0] for line in (AREAS / "AREA").read_text().splitlines()
              if line.strip() and not line.startswith("*")]
    for kind, shared in SHARED.items():
        generated = (AREAS / f"world.{kind}").read_text()
        ids = {int(value) for value in re.findall(r"(?m)^#(\d+)", generated)}
        assert shared <= ids, f"missing shared {kind} references: {shared - ids}"
    for source, (copy, _, _) in COPIES.items():
        assert active.count(copy) == 1, f"{copy} must be active exactly once"
        for kind, count in COUNTS[source].items():
            original = (AREAS / kind / f"{source}.{kind}").read_text()
            if kind == "shp":
                # Shop IDs are durable load-order indices. Append copied records
                # in the existing end.shp tail, never ahead of established shops.
                contents = (AREAS / "shp/end.shp").read_text()
                actual = "".join(records(contents, MAPS[source][kind].values()).values()).split("$~", 1)[0]
                for ident in MAPS[source][kind].values():
                    assert len(re.findall(rf"(?m)^#{ident}(?:~|[^0-9])", contents)) == 1
            else:
                actual = (AREAS / kind / f"{copy}.{kind}").read_text()
            assert len(records(original)) == count
            assert len(records(actual)) == count
            assert actual == expected_copy(source, kind), f"{copy}.{kind} differs beyond the explicit copy mapping"
            allocated = set(MAPS[source][kind].values())
            for path in (AREAS / kind).glob(f"*.{kind}"):
                if path.stem == copy or kind == "shp" and path.name == "end.shp":
                    continue
                collision = allocated.intersection(int(ident) for ident in re.findall(r"(?m)^#(\d+)", path.read_text(errors="replace")))
                assert not collision, f"allocated {kind} IDs collide with {path}: {collision}"
            generated_path = AREAS / f"world.{kind}"
            assert generated_path.exists(), "run make world before generated-output parity"
            generated = records(generated_path.read_text(), allocated)
            if kind == "shp":
                headers = re.findall(r"(?m)^#.*$", generated_path.read_text())
                copied_headers = [record.splitlines()[0] for record in records(actual).values()]
                assert headers[-count:] == copied_headers, "copied shops must append after every existing durable shop ID"
            for old_id, old_record in records(original).items():
                new_id = remap("mob" if kind == "qst" else kind, old_id)
                expected = copied_record(source, kind, old_record)
                if kind == "zon":
                    index = expected.index("~") + 1
                    expected = expected[:index] + "\n" + copy + "~" + expected[index:]
                # Generated streams may have whitespace between source files and
                # an end marker; neither belongs to the final authored record.
                actual_record = generated[new_id].split("$~", 1)[0].rstrip()
                assert actual_record == expected.rstrip(), f"generated {kind} {new_id} differs"
    print("issue 213 authored/generated tutorial copy parity passed (124 rooms, 108 mobiles, 143 objects, 32 controllers, 8 shops)")


if __name__ == "__main__":
    main()
