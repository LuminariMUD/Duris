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
    if (section.empty()) return name + " authored focus.\n\nStale creation claims.";
    return "Distinctive authored mechanics.";
}
static char_data ch;
static pc_only_data pc;
static std::string run(std::string args) {
    output.clear(); do_class(&ch, args.data(), 0);
    auto text = strip_ansi(output.c_str());
    std::istringstream lines(text);
    for (std::string line; std::getline(lines, line);) {
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
            std::string label = std::string("  ") + strip_ansi(class_names_table[cls].ansi);
            label += (cls == flag2idx(CLASS_ASSASSIN) || cls == flag2idx(CLASS_THIEF)) ?
                " (standalone legacy ID " + std::to_string(cls) + ")\n" : "\n";
            if ((text.find(label) != std::string::npos) != expected)
                fprintf(stderr, "Missing/mislabelled race %d class %d: %s\n%s\n", race, cls, label.c_str(), text.c_str());
            assert((text.find(label) != std::string::npos) == expected);
        }
    }
}
int main() {
    ch.only.pc = &pc; ch.player.race = RACE_GOBLIN; ch.player.level = 1;
    ch.player.m_class = CLASS_CLERIC;
    std::filesystem::create_directories("lib");
    std::ofstream("lib/creation_availability.cfg") << "creation.class.dragoon.enabled=false\n";
    boot_creation_availability_config();
    auto roster = run("");
    assert(roster == run("list"));
    assert(roster.find("THE CLASS ROSTER") != std::string::npos);
    assert(roster.find("Disabled in character creation") != std::string::npos);
    assert(roster.find("Special / legacy") != std::string::npos);
    assert(roster.find("standalone legacy ID 14") != std::string::npos);
    assert(roster.find("Warrior authored focus") != std::string::npos);
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
    assert(specs.find("not allowed") != std::string::npos);
    assert(specs.find("readiness to specialize") != std::string::npos);
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
    help_available = false;
    assert(run("info guardian").find("Description unavailable") != std::string::npos);
    assert(run("info guardian").find("Lost skill: lost access") != std::string::npos);
    assert(run("").find("THE CLASS ROSTER") != std::string::npos);
    setenv("CREATION_ALL_RACES", "TRUE", 1); check_filters();
    assert(run("list lich").find("normally restricted") != std::string::npos);
    setenv("CREATION_ALL_CLASSES", "TRUE", 1); check_filters();
    assert(run("list human").find("normally restricted (override enabled)") != std::string::npos);
    assert(run("info swashbuckler").find("Race permission override enabled") != std::string::npos);
    unsetenv("CREATION_ALL_RACES"); check_filters();
    unsetenv("CREATION_ALL_CLASSES");
    std::ofstream("lib/creation_availability.cfg") << "creation.class.warrior.enabled=false\n"
        "creation.race.gnome.enabled=false\n";
    boot_creation_availability_config(); check_filters();
    assert(run("list gnome").find("Disabled") != std::string::npos);
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
        ("wikihelp.c", "string trim("),
    )]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="class-command-", dir=build) as temporary:
        directory = Path(temporary)
        source = directory / "class.cpp"
        source.write_text(HARNESS.replace("#include <fstream>", "#include <fstream>\n#include <filesystem>")
                          .replace("int main() {", "\n".join(functions) + "\nint main() {"))
        for backend in ("mariadb", "flatfile"):
            binary = directory / backend
            flags = ["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else []
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            "-ffunction-sections", "-fdata-sections",
                            "-Wl,--gc-sections", "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                            "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2", *flags,
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
    assert(text.find("Description unavailable") != std::string::npos);
    assert(text.find("Added skill: rescue") != std::string::npos);
    assert(text.find("Parent class: Warrior") != std::string::npos);
    puts("PASS: real unavailable flat-file help preserves the class profile and grant differences");
}
''')
        binary = directory / "help-unavailable"
        subprocess.run(["g++", "-std=c++20", "-D__NO_MYSQL__", "-Isrc/no_mysql", "-Isrc",
                        "-I/usr/include/libxml2", "-ffunction-sections", "-fdata-sections",
                        "-Wl,--gc-sections", str(source), "src/cmd/class.c", "src/cmd/race.c",
                        "src/core/common.c", "src/core/constant.c", "src/account/creation_availability_config.c",
                        "src/classes/specializations.c", "src/cmd/wikihelp.c", "src/flatfile/flatfile_help_catalog.c",
                        str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True)
        with tempfile.TemporaryDirectory(prefix="missing-help-", dir=directory) as empty:
            subprocess.run([str(binary)], cwd=empty, check=True)


if __name__ == "__main__":
    main()
