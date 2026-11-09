#!/usr/bin/env python3
"""Exercise class browsing with real names, creation/spec policies and grant deltas."""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "account/creation_availability_config.h"
#include "classes/specializations.h"
#include "cmd/class.h"
#include "cmd/wikihelp.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdarg>
#include <fstream>
#include <sstream>
extern const struct class_names class_names_table[];
extern const struct race_names race_names_table[];
extern const char *specdata[][MAX_SPEC];
Skill skills[MAX_AFFECT_TYPES + 1];
char class_innates[LAST_INNATE + 2][CLASS_COUNT][5];
float combat_by_class[CLASS_COUNT + 1][2];
void active(P_char, char *, int) {}
extern const innate_data innates_data[LAST_INNATE + 1] = {
    {"inherited", active}, {"passive gift", nullptr}, {"changed gift", nullptr}
};
static std::string output, topic;
static bool help_available = true;
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[8192]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof text, format, args); va_end(args); output += text;
}
void logit(const char *, const char *, ...) {}
int fill_word(char *) { return 0; }
std::string wiki_help_prose(std::string name, std::string section) {
    topic = name;
    if (!help_available) return "";
    if (name == "Theurgist" && section.empty())
        return "Celestial invocations and\ndivine/arcane magic.\n\nStale creation claims.";
    if (name == "Medium" || name == "Templar" || name == "Thaumaturge")
        return section.empty() ? name + " is a Theurgist specialization. Selection requires level 30." : "";
    if (section.empty()) return name + " authored focus.\n\nStale creation claims.";
    return "Distinctive authored mechanics.";
}
static char_data ch;
static pc_only_data pc;
static std::string run(std::string args) {
    output.clear(); do_class(&ch, args.data(), 0);
    auto text = strip_ansi(output.c_str());
    bool roster = text.find("THE CLASS ROSTER") != std::string::npos ||
                  text.find(" : CLASS CHOICES") != std::string::npos ||
                  text.find("\n  Specializations\n") != std::string::npos;
    for (auto removed : {"Transport alignment", "account admission", "readiness",
                         "does not establish", "effective definitions", "Authored mechanics"})
        assert(text.find(removed) == std::string::npos);
    std::istringstream lines(text);
    for (std::string line; std::getline(lines, line);) {
        if (roster && line.rfind("  ", 0) == 0 && line.find(" - ") != std::string::npos)
            continue;
        if (line.size() > 79) fprintf(stderr, "Overflow: %s\n", line.c_str());
        assert(line.size() <= 79);
    }
    return text;
}
static void add(int id, const char *name, int level, int cap, int speclevel, int speccap) {
    skills[id].name = name;
    if (id >= FIRST_SPELL && id <= LAST_SPELL) skills[id].targets = TAR_SPELL;
    auto &data = skills[id].m_class[flag2idx(CLASS_WARRIOR)-1];
    data.rlevel[0] = level; data.maxlearn[0] = cap;
    data.rlevel[SPEC_GUARDIAN] = speclevel; data.maxlearn[SPEC_GUARDIAN] = speccap;
}
static bool ordinary(int race) {
    for (auto entry = playable_races; entry->race_id >= 0; ++entry)
        if (entry->race_id == race) return true;
    return false;
}
static void check_filters() {
    for (int race = 1; race <= RACE_PLAYER_MAX; ++race) {
        auto text = run(std::string("list ") + race_names_table[race].normal);
        bool available = creation_race_enabled(race) && (ordinary(race) || creation_all_races_enabled());
        if (!available) {
            assert(text.find("No new character can currently select this race") != std::string::npos);
            continue;
        }
        for (int cls = 1; cls <= CLASS_COUNT; ++cls) {
            bool expected = creation_class_enabled(cls) && creation_class_align(race, cls) != 5;
            std::string label = std::string("\n  ") + strip_ansi(class_names_table[cls].ansi) + " (";
            if ((text.find(label) != std::string::npos) != expected)
                fprintf(stderr, "Missing/mislabelled race %d class %d: %s\n%s\n", race, cls, label.c_str(), text.c_str());
            assert((text.find(label) != std::string::npos) == expected);
        }
    }
}
int main() {
    for (auto &row : combat_by_class) row[1] = 1.0f;
    ch.only.pc = &pc; ch.player.race = RACE_GOBLIN; ch.player.level = 1;
    ch.player.m_class = CLASS_CLERIC;
    std::filesystem::create_directories("lib");
    std::ofstream("lib/creation_availability.cfg") << "creation.class.dragoon.enabled=false\n";
    boot_creation_availability_config();
    auto roster = run("");
    assert(roster == run("list"));
    assert(roster.find("THE CLASS ROSTER") != std::string::npos);
    for (auto row : {"  Warrior - Warrior authored focus.\n",
                     "  Assassin (Retired ID 14: Special/Legacy) - Assassin authored focus.\n",
                     "  Thief (Retired ID 17: Special/Legacy) - Thief authored focus.\n",
                     "  Theurgist (Disabled: Special/Legacy) - Celestial invocations and divine/arcane magic.\n",
                     "  Summoner - Summoner authored focus.\n",
                     "  Dragoon (Disabled) - Dragoon authored focus.\n"})
        assert(roster.find(row) != std::string::npos);
    assert(roster.find("Available") == std::string::npos);
    std::istringstream rows(roster);
    int row_count = 0;
    for (std::string row; std::getline(rows, row);)
        if (row.find(" - ") != std::string::npos) ++row_count;
    assert(row_count == CLASS_COUNT);
    assert(roster.find("\n  Alignment is separate from racewar side.\n") != std::string::npos);
    for (auto removed : {"creation-policy choices", "transport alignment",
                         "Assassin and Thief lookups", "legacy IDs above"})
        assert(roster.find(removed) == std::string::npos);
    assert(output.find("&+") != std::string::npos);
    check_filters();
    assert(run("list GrEy-ElF") == run("list greyelf"));
    assert(run("list pillithid") == run("list planetbound illithid"));
    assert(run("list gith").find("Matching names") != std::string::npos);
    assert(run("list missing").find("No such player race") != std::string::npos);
    assert(run("info dark   knight") == run("INFO DaRk-KnIgHt"));
    assert(run("info warrior").find("Stale creation") == std::string::npos);
    assert(run("info assas").find("Parent class: Rogue") != std::string::npos);
    assert(run("info assassin").find("Rogue Assassin authored focus") != std::string::npos);
    assert(run("info thief").find("Rogue Thief authored focus") != std::string::npos);
    assert(run("info s").find("Matching names") != std::string::npos);
    assert(run("i warrior").find("Matching names:\n  info\n  innates") != std::string::npos);
    for (auto args : {"info", "innates", "specs", "bad", "info missing", "info warrior extra"})
        assert(run(args).find("Usage:") != std::string::npos);
    assert(run("specs assassin").find("Provide a base class") != std::string::npos);
    auto specs = run("specs warrior");
    assert(specs.find("Swashbuckler") != std::string::npos);
    assert(specs.find("Not available to Goblin") != std::string::npos);
    assert(specs.find("class info <specialization>") != std::string::npos);
    assert(specs.find("Use specialize at level 30.") != std::string::npos);
    auto theurgist = run("info theurgist");
    assert(theurgist.find(" is a Theurgist specialization") == std::string::npos);
    assert(theurgist.find("Selection requires") == std::string::npos);
    assert(theurgist.find("Description unavailable") == std::string::npos);
    for (auto name : {"Medium", "Templar", "Thaumaturge"}) {
        assert(theurgist.find(std::string("  ") + name + " (Not available to Goblin)\n") != std::string::npos);
        assert(run(std::string("info ") + name).find(" is a Theurgist specialization") == std::string::npos);
    }
    assert(run("info swashbuckler").find("Parent class: Warrior") != std::string::npos);
    assert(run("specs warlock").find("No named specializations") != std::string::npos);
    assert(run("specs rogue").find("Not Used") == std::string::npos);
    for (int cls = 1; cls <= CLASS_COUNT; ++cls) {
        assert(run(std::string("info ") + class_names_table[cls].normal).find("No such") == std::string::npos);
        for (int sp = 0; sp < MAX_SPEC; ++sp)
            if (*specdata[cls][sp] && std::string(specdata[cls][sp]) != "Not Used")
                assert(run("info " + strip_ansi(specdata[cls][sp])).find("SPECIALIZATION") != std::string::npos);
    }
    add(SKILL_BASH, "unchanged", 1, 90, 1, 90);
    add(SKILL_PARRY, "cap only", 1, 60, 1, 90);
    add(SKILL_DUAL_WIELD, "lost access", 1, 90, -1, 90);
    add(SKILL_RESCUE, "added skill", 0, 0, 30, 100);
    add(SKILL_KICK, "changed level", 10, 90, 20, 90);
    add(SPELL_FIREBALL, "changed circle", 3, 100, 2, 100);
    add(SPELL_HEAL, "lost spell", 6, 100, 6, 0);
    add(SPELL_HASTE, "added spell", 0, 0, 5, 100);
    const int warrior = flag2idx(CLASS_WARRIOR)-1;
    class_innates[0][warrior][0] = 5;
    class_innates[1][warrior][SPEC_GUARDIAN] = 41;
    class_innates[2][warrior][0] = 30;
    class_innates[2][warrior][SPEC_GUARDIAN] = 20;
    auto text = run("info guardian");
    assert(text.find("cap only (level 1 -> 1, cap 60% -> 90%)") != std::string::npos);
    for (auto part : {"Lost skill: lost access", "Added skill: added skill", "Changed skill: changed level",
                     "Changed spell: changed circle (Circle 3 -> 2)", "Lost spell: lost spell",
                     "Added spell: added spell (Circle 5)", "Added innate: passive gift",
                     "Changed innate: changed gift (level 30 -> 20", "skills Guardian", "spells Guardian"})
        { if (text.find(part) == std::string::npos) fprintf(stderr, "Missing %s\n%s\n", part, text.c_str());
          assert(text.find(part) != std::string::npos); }
    assert(text.find("unchanged") == std::string::npos);
    assert(text.find("Changed innate: inherited") == std::string::npos);
    text = run("innates guardian");
    for (auto part : {"inherited (level 5, active)", "*passive gift (level 41, passive)",
                     "changed gift (level 20, passive)", "race innates <race>"})
        assert(text.find(part) != std::string::npos);
    assert(run("innates conjurer").find("None. No class innates") != std::string::npos);
    combat_by_class[flag2idx(CLASS_WARRIOR)][1] = 1.15f;
    combat_by_class[flag2idx(CLASS_MONK)][1] = .825f;
    combat_by_class[flag2idx(CLASS_BERSERKER)][1] = .9f;
    combat_by_class[flag2idx(CLASS_ROGUE)][1] = 1.1f;
    for (auto name : {"warrior", "guardian", "swordsman"})
        assert(run(std::string("innates ") + name).find("Melee and archery damage: +15% (passive)") != std::string::npos);
    assert(run("innates monk").find("Melee and archery damage: -17.5% (passive)") != std::string::npos);
    assert(run("innates berserker").find("Melee and archery damage: -10% (passive)") != std::string::npos);
    for (auto name : {"rogue", "thief", "assassin"})
        assert(run(std::string("innates ") + name).find("Melee and archery damage: +10% (passive)") != std::string::npos);
    // The display describes the selected class, not the viewer's current kit.
    ch.player.m_class = CLASS_MONK;
    assert(run("innates warrior").find("+15%") != std::string::npos);
    combat_by_class[flag2idx(CLASS_CONJURER)][1] = .8f;
    auto modifier_only = run("innates conjurer");
    assert(modifier_only.find("-20%") != std::string::npos && modifier_only.find("None. No class innates") == std::string::npos);
    combat_by_class[flag2idx(CLASS_CONJURER)][1] = 1.0f;
    assert(run("innates conjurer").find("Melee and archery damage") == std::string::npos);
    assert(run("innates conjurer").find("None. No class innates") != std::string::npos);
    help_available = false;
    assert(run("info guardian").find("Lost skill: lost access") != std::string::npos);
    assert(run("").find("THE CLASS ROSTER") != std::string::npos);
    setenv("CREATION_ALL_RACES", "TRUE", 1); check_filters();
    assert(run("list lich").find("normally restricted") != std::string::npos);
    setenv("CREATION_ALL_CLASSES", "TRUE", 1); check_filters();
    assert(run("list human").find("normally restricted") != std::string::npos);
    assert(run("").find("Theurgist (Special/Legacy; Override)") != std::string::npos);
    assert(run("info swashbuckler").find("Race permission override enabled") != std::string::npos);
    unsetenv("CREATION_ALL_RACES"); check_filters();
    unsetenv("CREATION_ALL_CLASSES");
    std::ofstream("lib/creation_availability.cfg") << "creation.class.warrior.enabled=false\n"
        "creation.race.gnome.enabled=false\n";
    boot_creation_availability_config(); check_filters();
    assert(run("list gnome").find("Disabled") != std::string::npos);
    assert(run("").find("Warrior (Disabled) - ") != std::string::npos);
    std::ofstream config("lib/creation_availability.cfg");
    for (int cls = 1; cls <= CLASS_COUNT; ++cls) {
        std::string name = class_names_table[cls].normal;
        for (char &c : name) c = std::tolower(static_cast<unsigned char>(c));
        config << "creation.class." << name << ".enabled=false\n";
    }
    config.close(); boot_creation_availability_config();
    assert(run("list human").find("None under current creation policy") != std::string::npos);
    ch.player.level = 62;
    assert(run("info guardian").find("Lost skill: lost access") != std::string::npos);
    puts("PASS: class routes, every class/spec, creation overrides, race permission, deltas, inheritance and width");
}
'''


def main():
    interp = (ROOT / "src/cmd/interp.c").read_text()
    command_id = int(re.search(r"#define CMD_CLASS (\d+)", (ROOT / "src/cmd/interp.h").read_text())[1])
    names = re.findall(r'"([^"\n]+)"', interp.split('const char *command[MAX_CMD] = {', 1)[1].split('};', 1)[0])
    assert names[command_id - 1] == "class"
    assert "CMD_Y(CMD_CLASS, STAT_DEAD + POS_PRONE, do_class, 0, FALSE)" in interp
    functions = [extract_function(file, signature) for file, signature in (
        ("interp.c", "char *one_argument("), ("utility.c", "string strip_ansi("),
        ("utility.c", "int ansi_strlen("), ("utility.c", "int flag2idx("),
        ("abilities.c", "std::string damage_modifier_innate("),
        ("wikihelp.c", "string trim("),
    )]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="class-command-", dir=build) as temporary:
        directory = Path(temporary)
        source = directory / "class.cpp"
        source.write_text(HARNESS.replace("#include <fstream>", "#include <fstream>\n#include <filesystem>")
                          .replace("int main() {", "\n".join(functions) + "\nint main() {"))
        binary = directory / "class"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections",
                        "-Wl,--gc-sections", "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(source), "src/cmd/class.c", "src/cmd/race.c", "src/core/common.c", "src/core/constant.c",
                        "src/account/creation_availability_config.c", "src/classes/specializations.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)

        # A cold real help-catalog failure must preserve the command's facts.
        prelude = HARNESS.split("int main() {", 1)[0]
        start = prelude.index("std::string wiki_help_prose(")
        end = prelude.index("static char_data ch;", start)
        prelude = prelude[:start] + prelude[end:]
        source.write_text(prelude + "\n".join(functions[:-1]) + r'''
int main() {
    ch.only.pc = &pc; ch.player.race = RACE_HUMAN; ch.player.level = 1;
    add(SKILL_RESCUE, "rescue", 0, 0, 30, 100);
    auto text = run("info guardian");
    assert(text.find("Added skill: rescue") != std::string::npos);
    assert(text.find("Parent class: Warrior") != std::string::npos);
    puts("PASS: real unavailable help preserves the class profile and grant differences");
}
''')
        binary = directory / "help-unavailable"
        subprocess.run(["g++", "-std=c++20", '-I/usr/include/mysql', "-Isrc",
                        "-I/usr/include/libxml2", "-ffunction-sections", "-fdata-sections",
                        "-Wl,--gc-sections", str(source), "src/cmd/class.c", "src/cmd/race.c",
                        "src/core/common.c", "src/core/constant.c", "src/account/creation_availability_config.c",
                        "src/classes/specializations.c", "src/cmd/wikihelp.c", "src/cmd/help_cache.c",
                        str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True)
        with tempfile.TemporaryDirectory(prefix="missing-help-", dir=directory) as empty:
            subprocess.run([str(binary)], cwd=empty, check=True)


if __name__ == "__main__":
    main()
