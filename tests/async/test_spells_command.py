#!/usr/bin/env python3
"""Execute the spell browser with real circle/eligibility rules under sanitizers."""
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function

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
static std::string output, help_name, help_result = "Syntax: cast 'fireball' <victim>";
static P_char visible, book_target;
static int lookups, book_checks;
static bool wearing_necroplasm;
int is_wearing_necroplasm(P_char) { return wearing_necroplasm; }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[8192]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args); output += text;
}
void debug(const char *, ...) {}
void logit(const char *, const char *, ...) {}
float get_property(const char *, double fallback) { return fallback; }
int fill_word(char *) { return 0; }
P_char get_char_vis(P_char, const char *) { ++lookups; return visible; }
P_obj SpellInSpellBook(P_char target, int spell, int mode) {
    ++book_checks; book_target = target;
    assert(mode == (SBOOK_MODE_IN_INV | SBOOK_MODE_AT_HAND | SBOOK_MODE_ON_BELT));
    return spell == SPELL_FIREBALL ? reinterpret_cast<P_obj>(1) : nullptr;
}
std::string wiki_help_single(std::string name) { help_name = name; return help_result; }
static std::string fireball_mechanics(P_char) { return "  Fire damage: 1-2\n"; }
AbilityFacts ability_facts(int spell) { return spell == SPELL_FIREBALL ? fireball_mechanics : nullptr; }
static std::string run(P_char ch, std::string args) {
    output.clear(); help_name.clear(); lookups = book_checks = 0;
    do_spells(ch, args.data(), 0);
    return strip_ansi(output.c_str());
}
static void add(int id, const char *name, int cls, int circle) {
    skills[id].name = name; skills[id].targets = TAR_SPELL;
    for (int spec = 0; spec <= MAX_SPEC; ++spec) {
        skills[id].m_class[flag2idx(cls)-1].rlevel[spec] = circle;
        skills[id].m_class[flag2idx(cls)-1].maxlearn[spec] = 100;
    }
}
int main() {
    add(SPELL_FIREBALL, "fireball", CLASS_CONJURER, 3);
    add(SPELL_ACID_BLAST, "Zeta spell", CLASS_CONJURER, 3);
    skills[SPELL_FIREBALL].targets |= TAR_AGGRO;
    add(SPELL_BURNING_HANDS, "burning hands", CLASS_CONJURER, 1);
    add(SPELL_HEAL, "heal", CLASS_CLERIC, 6);
    add(SPELL_MAGIC_MISSILE, "magic missile", CLASS_BARD, 3);
    add(SPELL_MIRROR_IMAGE, "mirror image", CLASS_CONJURER, MAX_CIRCLE);
    add(SPELL_FIRE_FORM, "fire form", CLASS_CONJURER, 0);
    auto &fire = skills[SPELL_FIRE_FORM].m_class[flag2idx(CLASS_CONJURER)-1];
    fire.rlevel[SPEC_FIRE] = 10;
    auto &ball = skills[SPELL_FIREBALL].m_class[flag2idx(CLASS_CONJURER)-1];
    ball.rlevel[SPEC_FIRE] = 2; ball.rlevel[SPEC_WATER] = -1;
    // Defined internal, undefined placeholder, invalid and capless grants.
    add(SPELL_BLINDNESS, "internal spell", CLASS_WARRIOR, 0);
    add(SPELL_ENLARGE, "Undefined", CLASS_CONJURER, 1);
    add(SPELL_DETECT_MAGIC, "invalid circle", CLASS_CONJURER, MAX_CIRCLE+1);
    add(SPELL_INVISIBILITY, "capless spell", CLASS_CONJURER, 2);
    for (int sp = 0; sp <= MAX_SPEC; ++sp)
        skills[SPELL_INVISIBILITY].m_class[flag2idx(CLASS_CONJURER)-1].maxlearn[sp] = 0;
    char_data ch{}, other{}, npc{};
    pc_only_data pc{}, other_pc{};
    ch.only.pc = &pc; other.only.pc = &other_pc;
    ch.player.name = const_cast<char *>("Scholar");
    other.player.name = const_cast<char *>("Cleric");
    npc.player.name = const_cast<char *>("Trainer");
    ch.player.m_class = CLASS_CONJURER; ch.player.level = 1;
    ch.player.race = RACE_HUMAN;
    other.player.m_class = CLASS_CLERIC; other.player.level = 30;
    npc.player.m_class = CLASS_CONJURER | CLASS_CLERIC;
    npc.player.level = 50; npc.specials.act = ACT_ISNPC;
    auto text = run(&ch, "");
    assert(text == ">====[ Scholar | Conjurer | Max Circle 1 ]====<\n"
                   "\n1st CIRCLE:\nburning hands\n"
                   "\n3rd CIRCLE:\nfireball [in spellbook]\nZeta spell\n"
                   "\n12th CIRCLE:\nmirror image\n"
                   "\nmemorize is your spell interface\n"
                   "See: spells <class or specialization> | spells info <spell name>\n");
    assert(lookups == 0 && book_target == &ch);
    assert(output.find("&+B1st CIRCLE:&n\nburning hands\n") != std::string::npos);
    assert(output.find("&+B3rd CIRCLE:&n\n&+Lfireball [in spellbook]&n\n") != std::string::npos);
    assert(output.ends_with("&+Wmemorize&n is your spell interface\n"
                            "See: &+Wspells <class or specialization>&n | "
                            "&+Wspells info <spell name>&n\n"));
    assert(run(&ch, "all").find("staff only") != std::string::npos);
    assert(run(&ch, "a").find("staff only") != std::string::npos);
    visible = &other;
    assert(run(&ch, "Cleric").find("BASE CLASS") != std::string::npos && lookups == 0);
    assert(run(&ch, "target Cleric").find("staff-only") != std::string::npos && lookups == 0);
    assert(run(&ch, "stranger").find("staff-only") != std::string::npos && lookups == 0);
    text = run(&ch, "fire magus");
    assert(text.find("Circle 10\n  * fire form\n") != std::string::npos);
    assert(text.find("Circle 1\n  burning hands\n") != std::string::npos);
    assert(text.find("Circle 2\n  fireball\n") != std::string::npos);
    assert(text.find("\n  * indicates spells gained from spec.\n") != std::string::npos);
    assert(text.find("memorize is the default spell interface") != std::string::npos);
    text = run(&ch, "conjurer");
    assert(text.find("fire form") == std::string::npos && text.find('*') == std::string::npos);
    assert(text.find("fireball") < text.find("Zeta spell"));
    text = run(&ch, "WaTeR-MaGuS");
    assert(text.find("\n  Spells lost from base class:\n  fireball") != std::string::npos);
    assert(text.find('*') == std::string::npos);
    fire.rlevel[SPEC_WATER] = 1;
    text = run(&ch, "water magus");
    assert(text.find("Circle 1\n  burning hands\n  * fire form\n") != std::string::npos);
    assert(text.find("\n  * indicates spells gained from spec. Spells lost from base class:\n  fireball") != std::string::npos);
    assert(run(&ch, "assassin").find("(Rogue)") != std::string::npos);
    assert(run(&ch, "thief").find("(Rogue)") != std::string::npos);
    assert(run(&ch, "dark knight").find("(Anti-Paladin)") != std::string::npos);
    assert(run(&ch, "s").find("Matching names:") != std::string::npos);
    assert(run(&ch, "fire mag").find("SPECIALIZATION") != std::string::npos);
    for (int cls = 1; cls <= CLASS_COUNT; ++cls) {
        assert(run(&ch, class_names_table[cls].normal).find("No such") == std::string::npos);
        for (int sp = 0; sp < MAX_SPEC; ++sp)
            if (*specdata[cls][sp] && std::string(specdata[cls][sp]) != "Not Used")
                assert(run(&ch, strip_ansi(specdata[cls][sp])).find("No such") == std::string::npos);
    }
    assert(run(&ch, "info").find("Provide a known spell") != std::string::npos);
    assert(run(&ch, "info fire").find("Matching names:") != std::string::npos);
    assert(run(&ch, "info internal spell").find("Provide a known") != std::string::npos);
    assert(run(&ch, "info Undefined").find("Provide a known") != std::string::npos);
    text = run(&ch, " info   FiReBaLl  ");
    assert(help_name == "fireball" && text.find("cast 'fireball'") != std::string::npos);
    assert(text.find("readiness to cast.\n\n  Mechanics\n  Fire damage: 1-2\n\n  Helpfile details") != std::string::npos);
    assert(text.find("Registered aggression: Yes") != std::string::npos);
    assert(text.find("Circle 2 (changed)") != std::string::npos);
    assert(text.find("Unavailable (lost from base class)") != std::string::npos);
    assert(text.find("Your required Circle: 3") != std::string::npos);
    assert(text.find("Circle requirement: not yet met") != std::string::npos);
    ch.player.level = 11;
    assert(run(&ch, "info fireball").find("Circle requirement: met") != std::string::npos);
    ch.player.spec = SPEC_WATER;
    assert(run(&ch, "info fireball").find("Not available through") != std::string::npos);
    ch.player.spec = SPEC_FIRE;
    assert(run(&ch, "info fire form").find("Circle 10 (added)") != std::string::npos);
    assert(run(&ch, "info fireball").find("Your required Circle: 2") != std::string::npos);
    ch.player.secondary_class = CLASS_CLERIC;
    assert(run(&ch, "").starts_with(">====[ Scholar | Conjurer / Fire Magus + Cleric | Max Circle 3 ]====<\n"));
    ch.player.spec = 0;
    assert(run(&ch, "info heal").find("Your required Circle: 7") != std::string::npos);
    assert(run(&ch, "info heal").find("readiness to cast.\n\n  Helpfile details") != std::string::npos);
    // A primary grant takes precedence even if a secondary grant is earlier.
    skills[SPELL_FIREBALL].m_class[flag2idx(CLASS_CLERIC)-1].rlevel[0] = 1;
    assert(run(&ch, "info fireball").find("Your required Circle: 3") != std::string::npos);
    ch.player.m_class = CLASS_WARRIOR; ch.player.secondary_class = CLASS_CONJURER;
    assert(run(&ch, "info mirror image").find("Not available through") != std::string::npos);
    ch.player.m_class = CLASS_CONJURER; ch.player.secondary_class = 0;
    ch.player.level = 56;
    assert(run(&ch, "info mirror image").find("Circle requirement: met") != std::string::npos);
    help_result = "Help topic not found.";
    assert(run(&ch, "info fireball").find("Your required Circle: 3") != std::string::npos);
    help_result = "Help is temporarily unavailable.";
    assert(run(&ch, "info fireball").find("Your required Circle: 3") != std::string::npos);
    ch.player.m_class = CLASS_SHAMAN;
    run(&ch, "info fireball"); assert(book_checks == 0);
    ch.player.m_class = CLASS_CLERIC;
    assert(run(&ch, "").find("heal") != std::string::npos && book_checks == 0);
    ch.player.m_class = CLASS_CONJURER; ch.player.race = RACE_ILLITHID;
    run(&ch, ""); assert(book_checks == 0);
    ch.player.race = RACE_HUMAN; ch.player.m_class = CLASS_WARRIOR;
    text = run(&ch, "");
    assert(text.find("No eligible spells") != std::string::npos);
    assert(text.find("is your spell interface") == std::string::npos);
    assert(run(&ch, "warrior").find("default spell interface") == std::string::npos);
    ch.player.level = 62;
    assert(run(&ch, "").starts_with(">====[ Scholar | Warrior | Max Circle 12 ]====<\n"));
    text = run(&ch, "target Cleric");
    assert(text.starts_with(">====[ Cleric | Cleric | Max Circle 6 ]====<\n") && lookups == 1);
    assert(text.find("is your spell interface") == std::string::npos);
    assert(run(&ch, "someone").starts_with(">====[ Cleric | Cleric | Max Circle 6 ]====<\n"));
    assert(run(&ch, "Cleric").find("BASE CLASS") != std::string::npos && lookups == 0);
    assert(run(&ch, "target").find("Provide one visible") != std::string::npos && lookups == 0);
    assert(run(&ch, "target Cleric extra").find("Provide one visible") != std::string::npos && lookups == 0);
    assert(run(&ch, "all extra").find("Usage:") != std::string::npos);
    assert(run(&ch, "info fireball extra").find("Provide a known") != std::string::npos);
    assert(run(&ch, "info internal spell").find("No ordinary class/specialization grants") != std::string::npos);
    visible = &npc;
    text = run(&ch, "target Trainer");
    assert(text.starts_with(">====[ Trainer | Cleric Conjurer | Max Circle 10 ]====<\n") && book_checks == 0);
    assert(text.find("heal") != std::string::npos && text.find("fireball") != std::string::npos);
    visible = nullptr;
    assert(run(&ch, "target absent").find("No such visible") != std::string::npos);
    text = run(&ch, "all");
    assert(text.find("BASE-CLASS CIRCLE REFERENCE") != std::string::npos);
    assert(text.find("internal spell") != std::string::npos && text.find("AGGR") != std::string::npos);
    assert(text.find("No base-class grant; see info") != std::string::npos);
    assert(text.find("Undefined") == std::string::npos);
    assert(text.find("fireball") < text.find("Zeta spell"));
    for (int cls = 1; cls <= CLASS_COUNT; ++cls)
        assert(text.find(std::string(" = ") + class_names_table[cls].normal) != std::string::npos);
    ch.specials.act |= PLR_MORTAL;
    assert(run(&ch, "all").find("staff only") != std::string::npos);
    assert(run(&ch, "al").find("staff only") != std::string::npos);
    assert(run(&ch, "info internal spell").find("Provide a known") != std::string::npos);
    run(&ch, "target Trainer"); assert(lookups == 0);

    for (int cls : {CLASS_SHAMAN, CLASS_DRUID, CLASS_RANGER, CLASS_DRAGOON, CLASS_BLIGHTER,
                    CLASS_CLERIC, CLASS_PSIONICIST, CLASS_WARLOCK, CLASS_ETHERMANCER})
        add(SPELL_MAGIC_MISSILE, "magic missile", cls, 1);
    ch.player.level = 6;
    const struct {
        int primary, secondary, race;
        const char *command;
    } interfaces[] = {
        {CLASS_SHAMAN, 0, RACE_HUMAN, "memorize"},
        {CLASS_DRUID, 0, RACE_HUMAN, "commune"},
        {CLASS_RANGER, 0, RACE_HUMAN, "commune"},
        {CLASS_DRAGOON, 0, RACE_HUMAN, "commune"},
        {CLASS_BLIGHTER, 0, RACE_HUMAN, "deforest"},
        {CLASS_CLERIC, 0, RACE_HUMAN, "pray"},
        {CLASS_PSIONICIST, 0, RACE_HUMAN, "will"},
        {CLASS_WARLOCK, 0, RACE_HUMAN, "assimilate"},
        {CLASS_ETHERMANCER, 0, RACE_HUMAN, "tupor"},
        {CLASS_CONJURER, 0, RACE_HARPY, "tupor"},
        {CLASS_CONJURER, 0, RACE_PSBEAST, "focus"},
        {CLASS_CONJURER, 0, RACE_LICH, "assimilate"},
        {CLASS_CLERIC, 0, RACE_ANGEL, "assimilate"},
        {CLASS_WARRIOR, CLASS_BLIGHTER, RACE_HUMAN, "deforest"},
        {CLASS_WARRIOR, CLASS_SHAMAN, RACE_HUMAN, "memorize"},
        {CLASS_CLERIC, CLASS_BLIGHTER, RACE_HUMAN, "pray"},
        {CLASS_DRUID, 0, RACE_ILLITHID, "will"},
    };
    for (const auto &[primary, secondary, race, command] : interfaces) {
        ch.player.m_class = primary; ch.player.secondary_class = secondary; ch.player.race = race;
        run(&ch, "");
        assert(output.find(std::string("\n&+W") + command + "&n is your spell interface\nSee:") != std::string::npos);
        if (!secondary && race == RACE_HUMAN) {
            run(&ch, class_names_table[flag2idx(primary)].normal);
            assert(output.find(std::string("\n  &+W") + command + "&n is the default spell interface\n") != std::string::npos);
        }
    }
    ch.player.m_class = CLASS_CONJURER; ch.player.race = RACE_HUMAN;
    wearing_necroplasm = true;
    assert(run(&ch, "").find("assimilate is your spell interface") != std::string::npos);
    puts("PASS: spells routes, grants, spell interfaces, circle rules, book paths, NPCs and permissions");
}
'''


def main():
    functions = [extract_function(file, signature) for file, signature in (
        ("interp.c", "char *one_argument("), ("interp.c", "bool is_abbrev("),
        ("utility.c", "string strip_ansi("), ("utility.c", "string pad_ansi("),
        ("utility.c", "int flag2idx("), ("utility.c", "int BOUNDED(int a, int b, int c)"),
        ("utility.c", "int GET_CLASS("), ("utility.c", "int GET_PRIME_CLASS("),
        ("utility.c", "int GET_SECONDARY_CLASS("),
        ("utility.c", "ClassSkillInfo SKILL_DATA_ALL("),
        ("memorize.c", "int get_spell_circle(P_char ch, int spl)"),
        ("memorize.c", "int get_max_circle("), ("memorize.c", "bool book_class("),
        ("memorize.c", "bool praying_class("), ("memorize.c", "bool meming_class("),
        ("memorize.c", "static bool can_assimilate("),
        ("memorize.c", "const char *spell_interface_command("),
        ("memorize.c", "const char *default_spell_interface_command("),
        ("wikihelp.c", "string trim("),
    )]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="spells-command-", dir=build) as temporary:
        directory = Path(temporary)
        source = directory / "spells.cpp"
        source.write_text(HARNESS.replace("int main() {", "\n".join(functions) + "\nint main() {"))
        for backend in ("mariadb", "flatfile"):
            binary = directory / backend
            flags = ["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else []
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                            "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined", "-Isrc",
                            "-I/usr/include/mysql", "-I/usr/include/libxml2", *flags,
                            str(source), "src/cmd/spells.c", "src/core/common.c", "-o", str(binary)],
                           cwd=ROOT, check=True)
            subprocess.run([str(binary)], cwd=directory, check=True)

        # A cold flat-file help failure must leave the real browser facts usable.
        driver = r'''
int main() {
    add(SPELL_FIREBALL, "fireball", CLASS_CONJURER, 3);
    char_data ch{}; pc_only_data pc{}; ch.only.pc = &pc;
    ch.player.name = const_cast<char *>("Scholar");
    ch.player.m_class = CLASS_CONJURER; ch.player.level = 1;
    auto text = run(&ch, "info fireball");
    assert(text.find("Your required Circle: 3") != std::string::npos);
    assert(text.find("error with the help system") != std::string::npos);
    puts("PASS: real flat-file help unavailability preserves browser facts and access");
}
'''
        prelude = HARNESS.split("int main() {", 1)[0]
        prelude = prelude.replace(
            'std::string wiki_help_single(std::string name) { help_name = name; return help_result; }', '')
        source.write_text(prelude + "\n".join(functions[:-1]) + driver)
        binary = directory / "help-unavailable"
        subprocess.run(["g++", "-std=c++20", "-D__NO_MYSQL__", "-Isrc/no_mysql", "-Isrc",
                        "-I/usr/include/libxml2", "-ffunction-sections", "-fdata-sections",
                        "-Wl,--gc-sections", str(source), "src/cmd/spells.c", "src/core/common.c",
                        "src/cmd/wikihelp.c", "src/flatfile/flatfile_help_catalog.c",
                        str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
