#!/usr/bin/env python3
"""Execute the skills browser and real character calculations over bounded fixtures.

The companion gameplay journey checks the production skill/help catalogs and dispatcher.
"""
import subprocess
import tempfile

from _paths import ROOT, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "cmd/wikihelp.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <string>
extern const struct class_names class_names_table[];
extern const char *specdata[][MAX_SPEC];
Skill skills[MAX_AFFECT_TYPES + 1];
int SortedSkills[MAX_AFFECT_TYPES + 1];
static std::string output, help_name, help_result = "Syntax: bash <victim>";
static char_data *visible;
static int lookups;
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[8192]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args); output += text;
}
void debug(const char *, ...) {}
void logit(const char *, const char *, ...) {}
P_char get_linked_char(P_char, unsigned short) { return nullptr; }
int BOUNDED(int low, int value, int high) { return MAX(low, MIN(value, high)); }
int fill_word(char *) { return 0; }
bool has_innate(P_char, int) { return false; }
float get_property(const char *, double fallback) { return fallback; }
bool affected_by_spell(P_char, int) { return false; }
P_char get_char_vis(P_char, const char *) { ++lookups; return visible; }
std::string wiki_help_single(std::string name) { help_name = name; return help_result; }
static std::string bash_mechanics(P_char) { return "  Damage on a hit: 1-2\n"; }
AbilityFacts ability_facts(int skill) { return skill == SKILL_BASH ? bash_mechanics : nullptr; }
static std::string run(P_char ch, std::string args) {
    output.clear(); help_name.clear(); lookups = 0;
    do_skills(ch, args.data(), 0);
    return strip_ansi(output.c_str());
}
static void add(int id, const char *name, int cls, int level, int cap) {
    skills[id].name = name;
    for (int spec = 0; spec <= MAX_SPEC; ++spec) {
        skills[id].m_class[flag2idx(cls)-1].rlevel[spec] = level;
        skills[id].m_class[flag2idx(cls)-1].maxlearn[spec] = cap;
    }
}
int main() {
    for (int i = 0; i <= MAX_AFFECT_TYPES; ++i) SortedSkills[i] = i;
    add(SKILL_BASH, "bash", CLASS_WARRIOR, 1, 100);
    add(SKILL_GUARD, "guard", CLASS_WARRIOR, 41, 70);
    add(SKILL_PARRY, "parry", CLASS_WARRIOR, 1, 90);
    add(SKILL_RESCUE, "rescue", CLASS_RANGER, 10, 80);
    add(SKILL_BACKSTAB, "backstab", CLASS_ROGUE, 1, 80);
    add(INSTRUMENT_DRUMS, "drums", CLASS_BARD, 5, 100);
    add(SONG_HEROISM, "song of heroism", CLASS_BARD, 41, 100);
    skills[SKILL_BASH].m_class[0].maxlearn[SPEC_SWORDSMAN] = 70;
    skills[SKILL_BASH].m_class[0].rlevel[SPEC_SWASHBUCKLER] = -1;
    skills[SKILL_GUARD].m_class[0].rlevel[SPEC_GUARDIAN] = 30;
    skills[SKILL_GUARD].m_class[0].maxlearn[SPEC_GUARDIAN] = 100;
    skills[SKILL_BLADE_BARRAGE].name = "blade barrage";
    skills[SKILL_BLADE_BARRAGE].m_class[0].rlevel[SPEC_SWASHBUCKLER] = 30;
    skills[SKILL_BLADE_BARRAGE].m_class[0].maxlearn[SPEC_SWASHBUCKLER] = 100;
    skills[SKILL_ANATOMY].name = "anatomy";
    skills[SKILL_ANATOMY].targets = TAR_EPIC;
    skills[SKILL_CHARGE].name = "charge cooldown."; // no public class assignment
    char_data ch{}, other{}, npc{};
    pc_only_data pc{}, other_pc{};
    ch.only.pc = &pc; other.only.pc = &other_pc;
    ch.player.name = const_cast<char *>("Scholar");
    other.player.name = const_cast<char *>("Warrior");
    npc.player.name = const_cast<char *>("Trainer");
    ch.player.m_class = other.player.m_class = npc.player.m_class = CLASS_WARRIOR;
    ch.player.level = 10; other.player.level = 30; npc.player.level = 50;
    npc.specials.act = ACT_ISNPC;
    pc.skills[SKILL_BASH].learned = 60; pc.skills[SKILL_BASH].taught = 70;
    pc.skills[SKILL_ANATOMY].learned = 80;
    auto text = run(&ch, "");
    assert(text.find("Scholar : SKILLS") != std::string::npos && lookups == 0);
    assert(text.find("obtained at level 41") != std::string::npos);
    assert(text.find("anatomy") != std::string::npos);
    assert(text.find("charge cooldown") == std::string::npos);
    assert(run(&ch, "levels").find("staff only") != std::string::npos);
    visible = &other;
    assert(run(&ch, "Warrior").find("BASE CLASS") != std::string::npos && lookups == 0);
    run(&ch, "target Warrior"); assert(lookups == 0);
    assert(run(&ch, "stranger").find("staff-only") != std::string::npos && lookups == 0);
    assert(run(&ch, "GuArDiAn").find("30  100  guard") != std::string::npos);
    assert(run(&ch, "Swashbuckler").find("Skills lost from base class: bash") != std::string::npos);
    assert(run(&ch, "swashbuckler").find("30  100  blade barrage") != std::string::npos);
    assert(run(&ch, "warrior").find("blade barrage") == std::string::npos);
    assert(run(&ch, "Swordsman").find("1   70  bash") != std::string::npos);
    assert(run(&ch, "assassin").find("(Rogue)") != std::string::npos);
    assert(run(&ch, "thief").find("(Rogue)") != std::string::npos);
    assert(run(&ch, "dark knight").find("(Anti-Paladin)") != std::string::npos);
    assert(run(&ch, "s").find("Matching names:") != std::string::npos);
    assert(run(&ch, "guar").find("(Warrior)") != std::string::npos);
    assert(run(&ch, "info ba").find("Matching names:") != std::string::npos);
    assert(run(&ch, "info bas").find("bash : SKILL INFO") != std::string::npos);
    for (int cls = 1; cls <= CLASS_COUNT; ++cls) {
        assert(run(&ch, class_names_table[cls].normal).find("No such") == std::string::npos);
        for (int spec = 0; spec < MAX_SPEC; ++spec)
            if (*specdata[cls][spec] && std::string(specdata[cls][spec]) != "Not Used")
                assert(run(&ch, strip_ansi(specdata[cls][spec])).find("No such") == std::string::npos);
    }
    assert(run(&ch, "bard").find("song of heroism") != std::string::npos);
    assert(run(&ch, "bard").find("drums") != std::string::npos);
    assert(run(&ch, "info").find("Provide a known skill name") != std::string::npos);
    assert(run(&ch, "info charge cooldown.").find("Provide a known") != std::string::npos);
    text = run(&ch, " info   BAsH  ");
    assert(help_name == "bash" && text.find("Syntax: bash <victim>") != std::string::npos);
    assert(text.find("\n\n  Mechanics\n  Damage on a hit: 1-2\n\n  Helpfile details") != std::string::npos);
    assert(run(&ch, "info guard").find("Mechanics") == std::string::npos);
    assert(text.find("Current rating: 60  Learned: 60  Taught: 70") != std::string::npos);
    assert(text.find("Swordsman") != std::string::npos && text.find("70") != std::string::npos);
    assert(text.find("Swashbuckler") != std::string::npos && text.find("Unavailable") != std::string::npos);
    ch.player.secondary_class = CLASS_RANGER;
    text = run(&ch, "info rescue");
    assert(text.find("Your unlock level: 15  Your cap: 76") != std::string::npos);
    ch.player.secondary_class = 0;
    ch.player.spec = SPEC_GUARDIAN;
    assert(run(&ch, "info guard").find("Your unlock level: 30  Your cap: 100") != std::string::npos);
    ch.player.spec = 0;
    ch.specials.affected_by5 |= AFF5_MENTAL_ANGUISH;
    assert(run(&ch, "info bash").find("Current rating: 10  Learned: 60") != std::string::npos);
    ch.specials.affected_by5 = 0;
    help_result = "Help topic not found.";
    assert(run(&ch, "info bash").find("Your cap: 100") != std::string::npos);
    help_result = "Help is temporarily unavailable.";
    assert(run(&ch, "info bash").find("Current rating: 60") != std::string::npos);
    assert(run(&ch, "info anatomy").find("separate epic skill rules") != std::string::npos);
    affected_type effect{};
    effect.loc2 = SKILL_BASH;
    effect.location = APPLY_SKILL_ADD;
    effect.modifier = 20;
    ch.affected = &effect;
    assert(GET_CHAR_SKILL_P(&ch, SKILL_BASH) == 80);
    assert(run(&ch, "info bash").find("Current rating: 80  Learned: 60") != std::string::npos);
    effect.loc2 = SKILL_PARRY;
    assert(GET_CHAR_SKILL_P(&ch, SKILL_BASH) == 60); // an unrelated selector must not apply
    effect.loc2 = SKILL_BASH;
    effect.modifier = -80;
    assert(GET_CHAR_SKILL_P(&ch, SKILL_BASH) == 0);
    effect.modifier = 20;
    pc.skills[SKILL_BASH].learned = 0;
    assert(GET_CHAR_SKILL_P(&ch, SKILL_BASH) == 0); // additive effects do not teach a skill
    effect.location = APPLY_SKILL_GRANT;
    effect.modifier = 40;
    assert(GET_CHAR_SKILL_P(&ch, SKILL_BASH) == 40);
    assert(pc.skills[SKILL_BASH].learned == 0);
    effect.loc2 = SKILL_ANATOMY;
    pc.skills[SKILL_ANATOMY].learned = 0;
    assert(GET_CHAR_SKILL_P(&ch, SKILL_ANATOMY) == 40);
    assert(run(&ch, "info anatomy").find("Current rating: 40  Learned: 0") != std::string::npos);
    ch.affected = nullptr;
    assert(GET_CHAR_SKILL_P(&ch, SKILL_ANATOMY) == 0);
    assert(GET_CHAR_SKILL_P(&ch, SKILL_BASH) == 0);
    pc.skills[SKILL_BASH].learned = 60;
    ch.player.level = 62;
    text = run(&ch, "");
    assert(text.find("Scholar : SKILLS") != std::string::npos && text.find("taught 70") != std::string::npos);
    assert(run(&ch, "target Warrior").find("Warrior : SKILLS") != std::string::npos && lookups == 1);
    assert(run(&ch, "someone").find("Warrior : SKILLS") != std::string::npos);
    visible = &npc;
    assert(run(&ch, "target trainer").find("Trainer : SKILLS") != std::string::npos);
    visible = nullptr;
    assert(run(&ch, "reset Scholar").find("nothing to reset") == std::string::npos);
    text = run(&ch, "levels");
    for (int cls = 1; cls <= CLASS_COUNT; ++cls)
        assert(text.find(std::string(" = ") + class_names_table[cls].normal) != std::string::npos);
    ch.specials.act |= PLR_MORTAL;
    assert(run(&ch, "levels").find("staff only") != std::string::npos);
    puts("PASS: skills routes, all class/spec names, progress/multiclass, NPC safety, permissions and help fallback");
}
'''


def main():
    functions = [extract_function("interp.c", "char *one_argument("),
                 extract_function("interp.c", "bool is_abbrev("),
                 extract_function("utility.c", "string strip_ansi("),
                 extract_function("utility.c", "string pad_ansi("),
                 extract_function("utility.c", "int flag2idx("),
                 extract_function("utility.c", "ClassSkillInfo SKILL_DATA_ALL("),
                 extract_function("utility.c", "int GET_LVL_FOR_SKILL("),
                 extract_function("utility.c", "int GET_CHAR_SKILL_P("),
                 extract_function("wikihelp.c", "string trim(")]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="skills-command-", dir=build) as temporary:
        from pathlib import Path
        directory = Path(temporary)
        source = directory / "skills.cpp"
        source.write_text(HARNESS.replace("int main() {", "\n".join(functions) + "\nint main() {"))
        for backend in ("mariadb", "flatfile"):
            binary = directory / backend
            flags = ["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else []
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                            "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined", "-Isrc",
                            "-I/usr/include/mysql", "-I/usr/include/libxml2", *flags,
                            str(source), "src/cmd/skills.c", "src/core/common.c", "-o", str(binary)],
                           cwd=ROOT, check=True)
            subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
