#!/usr/bin/env python3
"""Execute race browsing against the real race tables and creation policy."""
from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "cmd/race.h"
#include "abilities/abilities.h"
#include "account/creation_availability_config.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
extern const struct race_names race_names_table[];
extern const struct class_names class_names_table[];
static std::string output;
static int innate_race;
float combat_by_race[LAST_RACE + 1][3];
float combat_by_class[CLASS_COUNT + 1][2];
char racial_innates[LAST_INNATE + 1][LAST_RACE + 1];
char class_innates[LAST_INNATE + 2][CLASS_COUNT][5];
void active(P_char, char *, int) {}
extern const innate_data innates_data[LAST_INNATE + 1] = {
    {"passive ability", nullptr}, {"active ability", active}
};
// PRODUCTION_LIST_INNATES
float spell_pulse_data[LAST_RACE + 1];
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[8192]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args); output += text;
}
void logit(const char *, const char *, ...) {}
void debug(const char *, ...) {}
int fill_word(char *) { return 0; }
const char *stat_to_string_damage_pulse(float) { return "average"; }
const char *stat_to_string_spell_pulse(float) { return "average"; }
std::string wiki_race_description(std::string) { return "Authored racial lore."; }
std::string list_innates(int race, int cls, int spec) {
    assert(race > 0 && race <= RACE_PLAYER_MAX && cls == 0 && spec == 0);
    innate_race = race;
    return production_list_innates(race, cls, spec);
}
static std::string plain(std::string text) {
    for (size_t i = 0; i < text.size();) {
        if (text[i] == '&' && i + 1 < text.size())
            text.erase(i, text[i+1] == '+' ? 3 : 2);
        else ++i;
    }
    return text;
}
static std::string run(std::string arguments) {
    char_data ch{}; output.clear(); innate_race = 0;
    do_race(&ch, arguments.data(), 0);
    return plain(output);
}
static void check_classes(int race) {
    combat_by_race[race][0] = 18.25f;
    spell_pulse_data[race] = 0.875f;
    auto text = run("info " + std::string(race_names_table[race].normal));
    assert(text.find("[ " + std::string(race_names_table[race].normal) + " ]") != std::string::npos);
    assert(text.find("    Combat speed : 18.250 pulses\n") != std::string::npos);
    assert(text.find("    Spell speed  : 0.875x casting time\n") != std::string::npos);
    const auto start = text.find("Valid classes (current character creation rules)\n");
    const auto end = text.find("Racial stat factors", start);
    assert(start != std::string::npos && end != std::string::npos);
    const auto classes = text.substr(start, end - start);
    int expected = 0;
    for (int cls = 1; cls <= CLASS_COUNT; ++cls) {
        bool allowed = creation_class_enabled(cls) && creation_class_align(race, cls) != 5;
        assert((classes.find("    " + plain(class_names_table[cls].ansi)) !=
                std::string::npos) == allowed);
        expected += allowed;
    }
    assert((classes.find("None.") != std::string::npos) == (expected == 0));
}
int main() {
    for (int race = 1; race <= RACE_PLAYER_MAX; ++race) {
        combat_by_race[race][1] = 1.0f;
        racial_innates[0][race] = 1;
        racial_innates[1][race] = 31;
    }
    unsetenv("CREATION_ALL_CLASSES"); unsetenv("CREATION_ALL_RACES");
    std::filesystem::create_directory("lib");
    std::ofstream("lib/creation_availability.cfg") << "creation.class.dragoon.enabled=false\n";
    boot_creation_availability_config();
    auto roster = run("");
    assert(roster == run("list"));
    const auto good = roster.find("GOOD RACES"), evil = roster.find("EVIL RACES");
    const auto neutral = roster.find("NEUTRAL RACES"), special = roster.find("DISABLED RACES");
    assert(good < evil && evil < neutral && neutral < special);
    assert(roster.find("Human", good) < evil);
    assert(roster.find("Drow Elf", evil) < neutral);
    assert(roster.find("Thri-Kreen", neutral) < special);
    assert(roster.find("Lich", special) != std::string::npos);
    assert(roster.find("Mountain Dwarf", good) < evil);
    assert(roster.find("Duergar Dwarf", evil) < neutral);
    assert(roster.find("Planetbound Illithid", special) != std::string::npos);
    assert(output.find("&+C") != std::string::npos && output.find("&+R") != std::string::npos &&
           output.find("&+Y") != std::string::npos);
    for (int race = 1; race <= RACE_PLAYER_MAX; ++race) {
        // Preserve every embedded race-name color, including multicolor names.
        if (plain(race_names_table[race].ansi) == race_names_table[race].normal)
            assert(output.find(race_names_table[race].ansi) != std::string::npos);
    }
    for (const auto *name : {"&+YMountain Dwarf&n", "&+rDuergar Dwarf&n",
                             "&+MPlanetbound Illithid&n"})
        assert(output.find(name) != std::string::npos);
    for (const auto *heading : {"&+R       D U R I S", "&+W             >====[",
                                "&+C  +", "&+R  +", "&+Y  +", "&+M  +",
                                "&+WRace info <race name>&n",
                                "&+WRace innates <race name>&n"})
        assert(output.find(heading) != std::string::npos);
    const std::string expected_roster = R"ROSTER(
  /====================================================================\
  |        D U R I S  :  L A N D  O F  B L O O D L U S T               |
  |              >====[  THE RACEWAR ROSTER  ]====<                    |
  \====================================================================/
  +--------------------------------------------------------------------+
  |                        /\   GOOD RACES   /\                        |
  +--------------------------------------------------------------------+
  |   Human                 Barbarian             Grey Elf             |
  |   Mountain Dwarf        Halfling              Gnome                |
  |   Centaur               Githzerai             Firbolg              |
  +--------------------------------------------------------------------+
  |                        \/   EVIL RACES   \/                        |
  +--------------------------------------------------------------------+
  |   Drow Elf              Duergar Dwarf         Ogre                 |
  |   Troll                 Orc                   Githyanki            |
  |   Goblin                Kobold                Drider               |
  +--------------------------------------------------------------------+
  |                      <>   NEUTRAL RACES   <>                       |
  |              Choose their racewar side during creation             |
  +--------------------------------------------------------------------+
  |   Thri-Kreen            Minotaur              Tiefling             |
  +--------------------------------------------------------------------+
  |                           DISABLED RACES                           |
  +--------------------------------------------------------------------+
  |   Lich                  Vampire               Death Knight         |
  |   Wight                 Revenant              Shadow Beast         |
  |   Phantom               Shade                                      |
  |   Half-Elf              Wood Elf              Kuo Toa              |
  |   Orog                  Harpy                                      |
  |   Illithid              Planetbound Illithid  Storm Giant          |
  +--------------------------------------------------------------------+

  Race info <race name>     Profile and valid classes
  Race innates <race name>  Racial abilities and unlock levels
)ROSTER";
    assert(roster == expected_roster);
    std::istringstream lines(roster);
    for (std::string line; std::getline(lines, line);) {
        if (line.rfind("  |", 0) == 0 || line.rfind("  +", 0) == 0) {
            if (line.size() != 72) fprintf(stderr, "Panel width %zu: %s\n", line.size(), line.c_str());
            assert(line.size() == 72);
        }
    }
    assert(run("info").find("provide a race name") != std::string::npos);
    assert(run("innates").find("provide a race name") != std::string::npos);
    assert(run("feats human").find("Usage:") != std::string::npos && innate_race == 0);
    assert(run("list human").find("Usage:") != std::string::npos);
    assert(run("info missing").find("No such player race") != std::string::npos);
    assert(run("info fire elemental").find("No such player race") != std::string::npos);
    assert(run("info gith").find("Matching races: Githyanki, Githzerai") != std::string::npos);
    assert(run("info    GrEy ElF   ").find("Authored racial lore.") != std::string::npos);
    assert(run("info GreyElf").find("Grey Elf") != std::string::npos);
    assert(run("info mountain").find("Mountain Dwarf") != std::string::npos);
    assert(run("innates planetbound illithid").find("obtained at level 31") != std::string::npos);
    assert(innate_race == RACE_PILLITHID);
    for (int race = 1; race <= RACE_PLAYER_MAX; ++race) {
        check_classes(race);
        run("innates " + std::string(race_names_table[race].normal));
        assert(innate_race == race);
    }
    // Runtime table changes are displayed without changing innate grants.
    assert(run("innates barbarian").find("Melee and archery damage") == std::string::npos);
    combat_by_race[RACE_BARBARIAN][1] = 1.15f;
    assert(run("innate barbarian").find("Melee and archery damage: +15% (passive)") != std::string::npos);
    combat_by_race[RACE_BARBARIAN][1] = .825f;
    assert(run("innates barbarian").find("Melee and archery damage: -17.5% (passive)") != std::string::npos);
    for (auto entry : {std::pair{1.001f, "+0.1%"}, std::pair{.999f, "-0.1%"}}) {
        combat_by_race[RACE_BARBARIAN][1] = entry.first;
        assert(run("innates barbarian").find(entry.second) != std::string::npos);
    }
    combat_by_race[RACE_BARBARIAN][1] = 1.0f;
    assert(run("innates barbarian").find("Melee and archery damage") == std::string::npos);
    racial_innates[0][RACE_SGIANT] = racial_innates[1][RACE_SGIANT] = 0;
    combat_by_race[RACE_SGIANT][1] = 1.2f;
    auto modifier_only = run("innates storm giant");
    assert(modifier_only.find("+20%") != std::string::npos && modifier_only.find("None.") == std::string::npos);
    assert(modifier_only.find("help attack damage modifiers") != std::string::npos);
    combat_by_race[RACE_SGIANT][1] = 1.0f;
    assert(run("innates storm giant").find("None.") != std::string::npos);
    spell_pulse_data[RACE_BARBARIAN] = 1.22f;
    assert(run("info barbarian").find("    Spell speed  : 1.220x casting time\n") != std::string::npos);
    spell_pulse_data[RACE_ILLITHID] = 0.025f;
    assert(run("info illithid").find("    Spell speed  : 0.025x casting time\n") !=
           std::string::npos);
    auto goblin = run("info goblin");
    assert(goblin.find("    Warrior     : Swordsman, Guardian\n") != std::string::npos);
    assert(goblin.find("    Rogue       : Assassin, Thief\n") != std::string::npos);
    assert(goblin.find("    Summoner    : Controller, Mentalist, Naturalist\n") != std::string::npos);
    assert(goblin.find("Swashbuckler") == std::string::npos);
    assert(goblin.find("Shadow Archer") == std::string::npos);
    assert(goblin.find("Not Used") == std::string::npos);
    assert(run("info human").find("    Warrior     : Swordsman, Guardian, Swashbuckler\n") !=
           std::string::npos);
    assert(run("info thri-kreen").find("    Warrior     : Swordsman\n") != std::string::npos);
    assert(run("info revenant").find("    Warrior\n") != std::string::npos);
    assert(run("info human").find("    Paladin") != std::string::npos);
    assert(run("info human").find("    Anti-Paladin") == std::string::npos);
    assert(run("info human").find("    Dragoon") == std::string::npos);
    setenv("CREATION_ALL_CLASSES", "TRUE", 1);
    for (int race = 1; race <= RACE_PLAYER_MAX; ++race) check_classes(race);
    assert(run("info human").find("    Dragoon") != std::string::npos);
    goblin = run("info goblin");
    assert(goblin.find("    Warrior     : Swordsman, Guardian, Swashbuckler\n") !=
           std::string::npos);
    assert(goblin.find("    Rogue       : Assassin, Thief, Shadow Archer\n") != std::string::npos);
    setenv("CREATION_ALL_RACES", "TRUE", 1);
    auto open_roster = run("list");
    assert(open_roster.find("SPECIAL / LEGACY RACES") != std::string::npos);
    assert(open_roster.find("DISABLED RACES") == std::string::npos);
    std::istringstream open_lines(open_roster);
    for (std::string line; std::getline(open_lines, line);)
        if (line.rfind("  |", 0) == 0 || line.rfind("  +", 0) == 0)
            assert(line.size() == 72);
    for (int race = 1; race <= RACE_PLAYER_MAX; ++race) check_classes(race);
    unsetenv("CREATION_ALL_CLASSES");
    assert(run("info lich").find("    Necromancer") != std::string::npos);
    assert(run("info lich").find("normally restricted") != std::string::npos);
    unsetenv("CREATION_ALL_RACES");
    assert(run("info lich").find("descend: necromancer") != std::string::npos);
    std::ofstream("lib/creation_availability.cfg") << "creation.class.warrior.enabled=false\n"
        "creation.race.gnome.enabled=false\ncreation.race.lich.enabled=false\n";
    boot_creation_availability_config();
    assert(run("info human").find("    Warrior") == std::string::npos);
    assert(run("info gnome").find("Disabled in character creation") != std::string::npos);
    assert(run("list").find("*Gnome") != std::string::npos);
    assert(output.find("&+L*&+RGnome&n") != std::string::npos);
    assert(plain(output).find("* Disabled in character creation.") != std::string::npos);
    setenv("CREATION_ALL_RACES", "TRUE", 1);
    assert(run("list").find("*Lich") != std::string::npos);
    assert(output.find("&+L*" + race_display_name(RACE_LICH)) != std::string::npos);
    puts("PASS: all 37 race profiles/innate routes, numeric racial timing, race-specific specializations, "
         "creation restrictions and overrides, faction colors, ASCII panels and name resolution");
}
'''


def main():
    interp = (ROOT / "src/cmd/interp.c").read_text()
    names = re.findall(r'"([^"\n]+)"', interp.split('const char *command[MAX_CMD] = {', 1)[1].split('};', 1)[0])
    command_id = int(re.search(r"#define CMD_RACE (\d+)", (ROOT / "src/cmd/interp.h").read_text())[1])
    maximum = int(re.search(r"#define MAX_CMD (\d+)", (ROOT / "src/core/config.h").read_text())[1])
    assert names[command_id - 1] == "race" and maximum == len(names)
    assert "CMD_Y(CMD_RACE, STAT_DEAD + POS_PRONE, do_race, 0, FALSE)" in interp
    parser = extract_function("interp.c", "char *one_argument(")
    parser += "\n" + extract_function("interp.c", "bool is_abbrev(")
    parser += "\n" + extract_function("sparser.c", "char *skip_spaces(")
    parser += "\n" + extract_function("utility.c", "string strip_ansi(")
    parser += "\n" + extract_function("utility.c", "string pad_ansi(")
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="race-command-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "race.cpp"
        listing = extract_function("abilities.c", "std::string damage_modifier_innate(") + "\n"
        listing += extract_function("innates.c", "string list_innates(").replace("string list_innates(", "string production_list_innates(", 1)
        harness.write_text(HARNESS.replace("// PRODUCTION_LIST_INNATES", listing)
                           .replace("int main() {", parser + "\nint main() {", 1))
        for backend in ("mariadb", "flatfile"):
            binary = directory / backend
            flags = ["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else []
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                            "-fsanitize=undefined", "-fno-sanitize-recover=undefined", "-Isrc",
                            "-I/usr/include/mysql", "-I/usr/include/libxml2", *flags,
                            str(harness), "src/cmd/race.c", "src/core/common.c", "src/core/constant.c",
                            "src/account/creation_availability_config.c", "src/classes/specializations.c",
                            "-o", str(binary)], cwd=ROOT, check=True)
            subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
