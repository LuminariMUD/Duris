#!/usr/bin/env python3
"""Fixed chances on info pages come from the roll their handler makes.

Every moved roll keeps its pre-conversion expression below as the oracle: under the same
seeds it must give the same result and leave the RNG at the same draw. Each page that prints
one is built from the real source, with the functions it reaches and the stubs below, and
its whole line is pinned. Source checks tie each handler branch to its roll function.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

# Source file: (original expression, expression over the shared functions).
ORACLES = {
    "cmd/actoff.c": [
        ("!number(0, 50)", "!combination_fumble_roll(rolls)"),
        ("!number(0, 30)", "!blade_barrage_fumble_roll(rolls)"),
        ("!number(0, 10)", "!kick_low_roll(rolls)"),
        ("!number(0, 24)", "!kick_stun_roll(rolls)"),
        ("number(0, 100) < 10", "dragon_roar_flee_roll(rolls) < dragon_roar_flee_threshold()"),
        ("number(0, 4)", "headbutt_weak_daze_roll(rolls)"),
        ("!number(0, 9)", "!garrote_stops_casting_roll(rolls)"),
        ("number(1, 20) < 7", "backstab_air_aura_roll(rolls) < backstab_air_aura_below()"),
        ("!number(0, 4)", "!tackle_carry_roll(rolls)"),
        ("!number(0, 3)", "!maul_clip_roll(rolls)"),
        ("number(0, 3) != 0", "springleap_plain_roll(rolls) != 0"),
        ("number(0, 1)", "springleap_super_stun_roll(rolls)"),
        ("number(0, 2)", "restrain_stops_casting_roll(rolls)"),
        ("number(1, 100) <= 15", "legsweep_prone_roll(rolls) <= legsweep_prone_up_to()"),
    ],
    "classes/new_skills.c": [("number(0, 1)", "appraise_wild_side_roll(rolls)")],
    "magic/magic.c": [
        ("number(0, 99) <= 60", "anti_magic_ray_noshrug_roll(rolls) <= anti_magic_ray_noshrug_chance()"),
        ("number(1, 100) <= 50", "cyclone_stun_roll(rolls) <= cyclone_stun_chance()"),
        ("number(1, 100) < 5", "entangle_bind_roll(rolls) < entangle_bind_chance()"),
        ("number(1, 100) < 20", "obtenebration_blind_roll(rolls) < obtenebration_blind_chance()"),
        ("10 < number(0, 101)", "chaos_shield_chance() < chaos_shield_roll(rolls)"),
        ("number(0, 99) < 10", "divine_blessing_parry_roll(rolls) < divine_blessing_parry_chance()"),
        ("!number(0, 1)", "!faerie_fire_disguise_roll(rolls)"),
        ("!number(0, 1)", "!faerie_fog_disguise_roll(rolls)"),
        ("!number(0, 1)", "!solar_flare_blind_roll(rolls)"),
        ("!number(0, 1)", "!solar_flare_immolate_roll(rolls)"),
        ("!number(0, 4)", "!dispel_magic_destroy_roll(rolls)"),
        ("!number(0, 99)", "!chaotic_ripple_big_surge_roll(rolls)"),
        ("number(2, 4)", "chaotic_ripple_big_surge_rays(rolls)"),
        ("!number(0, 19)", "!chaotic_ripple_small_surge_roll(rolls)"),
        ("number(1, 2)", "chaotic_ripple_small_surge_rays(rolls)"),
    ],
    "core/utility.c": [
        ("number(1, 100) <= 15", "quick_thinking_roll(rolls) <= quick_thinking_percent()"),
        ("41 > number(1, 100)", "41 > evasion_snake_roll(rolls)"),
        ("15 > number(1, 100)", "evasion_remove_chance() > evasion_dragon_roll(rolls)"),
    ],
    "classes/bard.c": [
        ("number(1, 100) > 75", "song_area_roll(rolls) > song_area_threshold()"),
        ("number(0, 100) < 10", "song_cowardice_flee_roll(rolls) < song_cowardice_flee_threshold()"),
        ("20 >= number(1, 100)", "echo_chance(SECT_INSIDE) >= echo_roll(rolls)"),
    ],
    "net/sparser.c": [
        ("number(1, 100) > 60", "spell_knowledge_name_roll(rolls) > spell_knowledge_name_threshold()"),
    ],
    "world/handler.c": [
        ("number(0, 101) <= 75", "calming_notarget_roll(rolls) <= calming_notarget_percent()"),
    ],
}

# Source file: (facts function, whole lines its page must hold).
PAGES = {
    "cmd/actoff.c": [
        ("combination_facts", ["  Chance it falls apart: 1 in 51"]),
        ("blade_barrage_facts", ["  Chance it falls apart, with no lag: 1 in 31"]),
        ("kick_facts", ["    Chance that also stuns it: 1 in 25, for 4 seconds to 9 seconds",
                        "    Chance that also stuns it: 1 in 25, for 4 seconds to 13 seconds",
                        "    (only a humanoid 2 or more sizes bigger than you, at most 1 in 11 kicks,"]),
        ("dragon_roar_facts", ["  Chance each other target also flees: 10 in 101, then 100 in 101"]),
        ("headbutt_facts", ["    Stunned and lagged, 4 in 5: 2 seconds each"]),
        ("garrote_facts", ["  Chance each round stops casting: 1 in 10, not elites or greater races"]),
        ("backstab_facts", ["  Chance a target's air aura foils it: 6 in 20"]),
        ("tackle_facts", ["  can carry you both out of the room, 1 in 5."]),
        ("maul_facts", ["  Chance the wrong size still takes half damage: 1 in 4"]),
        ("springleap_facts", ["  Chance of your dragon leap: 1 in 4",
                              "    Chance it also stuns, if the target fails a save: 1 in 2, for 4 seconds"]),
        ("restrain_facts", ["  A hit stops casting, 2 in 3."]),
        ("legsweep_facts", ["  Chance a hit leaves the target prone: 15 in 100"]),
    ],
    "classes/new_skills.c": [
        ("appraise_facts", ["    (1 in 2 high by up to 3 times the value, else low by up to 1/2)"]),
    ],
    "magic/magic.c": [
        ("anti_magic_ray_facts", ["  Cannot be shrugged: 61 in 100"]),
        ("cyclone_facts", ["  A flying target that fails a save: 50 in 100 to be stunned up to 2 seconds"]),
        ("entangle_facts", ["  In a forest, if it fails its save: 4 in 100 to bind it until freed instead"]),
        ("obtenebration_facts", ["  Blindness: 19 in 100, for 4 seconds to 12 seconds"]),
        ("chaos_shield_facts", ["  Chance to absorb part of a spell: 11 in 102"]),
        ("divine_blessing_facts", ["  Chance to parry an attack: 10 in 100 above alignment 990"]),
        ("faerie_fire_facts", ["  A visible, disguised target: 1 in 2 to lose its disguise"]),
        ("faerie_fog_facts", ["  A visible, disguised creature: 1 in 2 to lose its disguise"]),
        ("solar_flare_facts", ["  Blindness if it survives: 1 in 2, 4 seconds to 12 seconds",
                               "  Immolate if it survives: 1 in 2 to also cast it on the target"]),
        ("dispel_magic_facts", ["  A magic item: 1 in 5 to be destroyed"]),
        ("chaotic_ripple_facts", ["  Rays that follow: 2-4",
                                  "    (1 in 100 add 2-4 more, else 1 in 20 add 1-2 more)"]),
    ],
    "core/utility.c": [
        ("quick_thinking_innate_facts", ["  Chance an intelligence or power save passes at once: 15 in 100"]),
        ("evasion_innate_facts", ["  Way of the dragon: chance to avoid spell damage: 14 in 100"]),
    ],
    "classes/bard.c": [
        ("song_cowardice_facts", ["  Chance each verse reaches each target: 75 in 100",
                                  "  Chance a target flees each verse: 10 in 101, then 100 in 101"]),
        ("echo_innate_facts", ["  Chance of an echo each song beat: 20 in 100",
                               "  In the mountains: 30 in 100",
                               "  In the hills: 25 in 100",
                               "  In a forest: 15 in 100"]),
    ],
    "net/sparser.c": [
        ("spell_knowledge_magical_facts", ["  Then the chance to know its name: 60 in 100"]),
    ],
    "world/handler.c": [
        ("calming_innate_facts", ["  Chance a mob picking a target passes you over: 76 in 102"]),
    ],
}

# Handler, then the code each branch must run, in this order. Whitespace doesn't count.
BRANCHES = {
    "cmd/actoff.c": {
        "void event_combination(": ["if(!combination_fumble_roll(live_rolls))", "fallflatonyourface"],
        "void event_barrage(": ["if(!blade_barrage_fumble_roll(live_rolls))", "failtoexecutethedeadly"],
        "void kick(": ["if(!kick_stun_roll(live_rolls)&&!IS_STUNNED(victim))Stun(victim,ch,kick_wall_stun(live_rolls),TRUE);",
                       "csize<vsize&&!kick_low_roll(live_rolls))",
                       "if(!kick_stun_roll(live_rolls)){Stun(victim,ch,kick_groin_stun(live_rolls),TRUE);"],
        "void do_dragon_roar(": ["if((dragon_roar_flee_roll(live_rolls)<dragon_roar_flee_threshold())&&(number(0,100)<GET_CHAR_SKILL(ch,SKILL_DRAGON_ROAR))&&"],
        "void do_headbutt(": ["if(headbutt_weak_daze_roll(live_rolls)){CharWait(victim,headbutt_weak_daze());Stun(victim,ch,headbutt_weak_daze(),FALSE);"],
        "void event_garroteproc(": ["if(!garrote_stops_casting_roll(live_rolls)&&!IS_GREATER_RACE(ch)&&!IS_ELITE(ch)){StopCasting(ch);",
                                    "if(!garrote_stops_casting_roll(live_rolls)&&!IS_GREATER_RACE(ch)&&!IS_ELITE(ch)){StopCasting(ch);"],
        "bool backstab(": ["if(IS_AFFECTED2(victim,AFF2_AIR_AURA)){if(backstab_air_aura_roll(live_rolls)<backstab_air_aura_below())"],
        "void do_tackle(": ["if(!IS_FIGHTING(ch)&&!tackle_carry_roll(live_rolls)&&GET_POS(vict)==POS_STANDING&&!IS_ROOM(ch->in_room,ROOM_GUILD))"],
        "void maul(": ["if(!maul_clip_roll(live_rolls)){act(\"$n&+ygrowls&n", "melee_damage(ch,victim,(int)(dam/2),PHSDAM_TOUCH,0);",
                       "if(!maul_clip_roll(live_rolls)){act(\"As$nfalls"],
        "void do_springleap(": ["if(!SUPER_SPRINGLEAP||(springleap_plain_roll(live_rolls)&&SUPER_SPRINGLEAP))",
                                "if(springleap_super_stun_roll(live_rolls))Stun(vict,ch,springleap_super_stun(),TRUE);"],
        "void restrain(": ["if(restrain_stops_casting_roll(live_rolls)){StopCasting(victim);"],
        "void do_legsweep(": ["if(legsweep_prone_roll(live_rolls)<=legsweep_prone_up_to()){act(\"Youquicklymaneuver"],
    },
    "classes/new_skills.c": {
        "void do_appraise(": ["if(percent==101){if((appraise_wild_side_roll(live_rolls)))estimate_value+=(estimate_value*(appraise_wild_multiple(live_rolls)));"],
    },
    "magic/magic.c": {
        "void spell_anti_magic_ray(": ["if(anti_magic_ray_noshrug_roll(live_rolls)<=anti_magic_ray_noshrug_chance())noshrug=SPLDAM_NOSHRUG;"],
        "void spell_cyclone(": ["affchance=cyclone_stun_roll(live_rolls);if(affchance<=cyclone_stun_chance())"],
        "void spell_entangle(": ["chance=entangle_bind_chance();", "SECT_FOREST&&entangle_bind_roll(live_rolls)<chance&&!IS_AFFECTED(victim,AFF_BOUND))"],
        "void spell_single_obtenebration(": ["if(IS_ALIVE(ch)&&obtenebration_blind_roll(live_rolls)<obtenebration_blind_chance())"],
        "parse_chaos_shield(": ["chance=chaos_shield_chance();if(chance<chaos_shield_roll(live_rolls))returnFALSE;"],
        "bool divine_blessing_parry(": ["divine_blessing_parry_roll(live_rolls)<divine_blessing_parry_chance())"],
        "void spell_faerie_fire(": ["elseif(!faerie_fire_disguise_roll(live_rolls)&&IS_DISGUISE(victim))"],
        "void spell_faerie_fog(": ["if(!faerie_fog_disguise_roll(live_rolls)){remove_disguise(tmp_victim,TRUE);"],
        "void spell_solar_flare(": ["if(!solar_flare_blind_roll(live_rolls)&&!NewSaves(victim,SAVING_SPELL,mod))",
                                    "if(!solar_flare_immolate_roll(live_rolls))spell_immolate("],
        "void spell_dispel_magic(": ["if(!dispel_magic_destroy_roll(live_rolls)&&!IS_TRUSTED(ch))"],
        "void spell_chaotic_ripple(": ["rays=chaotic_ripple_rays(live_rolls);if(!chaotic_ripple_big_surge_roll(live_rolls))",
                                       "{rays+=chaotic_ripple_big_surge_rays(live_rolls);}elseif(!chaotic_ripple_small_surge_roll(live_rolls)){rays+=chaotic_ripple_small_surge_rays(live_rolls);}"],
    },
    "core/utility.c": {
        "StatSave(": ["caseAPPLY_INT:", "has_innate(ch,INNATE_QUICK_THINKING)&&quick_thinking_roll(live_rolls)<=quick_thinking_percent())returnTRUE;",
                      "caseAPPLY_POW:", "has_innate(ch,INNATE_QUICK_THINKING)&&quick_thinking_roll(live_rolls)<=quick_thinking_percent())returnTRUE;"],
    },
    "combat/fight.c": {
        "spell_damage(": ["if(evasion_remove_chance()>evasion_dragon_roll(live_rolls))"],
    },
    "classes/bard.c": {
        "void bard_cowardice(": ["if((song_cowardice_flee_roll(live_rolls)<song_cowardice_flee_threshold())&&(number(0,100)<GET_CHAR_SKILL(ch,SONG_COWARDICE))&&"],
        "event_bardsong(": ["aggr_chance=song_area_threshold();",
                            "(!should_area_hit(ch,tch)||(song_area_roll(live_rolls)>aggr_chance)))",
                            "echoChance=echo_chance(terrainType);if(echoChance>=echo_roll(live_rolls))"],
    },
    "net/sparser.c": {
        "void SpellCastShow(": ["if(spell_knowledge_name_roll(live_rolls)>spell_knowledge_name_threshold())idok=0;"],
    },
    "mob/mobact.c": {
        None: ["calming_notarget_roll(live_rolls)<=calming_notarget_percent()&&"],
    },
}

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <functional>
#include <map>
#include <sstream>
#include <string>

void randomize(uint64_t seed);
STUBS

FUNCTIONS

static int fingerprint() { return number(0, INT_MAX); }

// The original expression and the shared one give the same result and leave the RNG alike.
static void same(const char *name, const std::function<int()> &original,
                 const std::function<int(const Rolls &)> &shared) {
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(live_rolls), actual_next = fingerprint();
        if (actual != expected || actual_next != expected_next) {
            std::fprintf(stderr, "%s: seed %d gave %d then %d, expected %d then %d\n", name, (int)seed,
                         actual, actual_next, expected, expected_next);
            std::abort();
        }
    }
}

// The page holds each line whole, has no line over 79 columns, and builds without rolling.
static void page(const char *name, const std::function<std::string()> &build,
                 const std::vector<std::string> &lines) {
    randomize(7);
    const int expected_next = fingerprint();
    randomize(7);
    const std::string text = build();
    if (fingerprint() != expected_next) {
        std::fprintf(stderr, "%s: building the page rolled\n", name);
        std::abort();
    }
    std::vector<std::string> found;
    std::istringstream stream(text);
    for (std::string line; std::getline(stream, line);) {
        if (line.size() > 79) {
            std::fprintf(stderr, "%s: too wide: %s\n", name, line.c_str());
            std::abort();
        }
        found.push_back(line);
    }
    for (const std::string &line : lines)
        if (std::find(found.begin(), found.end(), line) == found.end()) {
            std::fprintf(stderr, "%s: no line [%s] in:\n%s", name, line.c_str(), text.c_str());
            std::abort();
        }
}

int main() {
    ORACLE_CALLS
    PAGE_CALLS
    return 0;
}
'''

STUBS = r'''
static std::map<int, int> ratings;
int GET_CHAR_SKILL_P(P_char, int skill) { auto it = ratings.find(skill); return it == ratings.end() ? 100 : it->second; }
bool has_innate(P_char, int) { return true; }
float get_property(const char *, double fallback) { return (float)fallback; }
int get_property(const char *, int fallback) { return fallback; }
int STAT_INDEX(int v) { return std::min(51, std::max(0, v / 3)); }
struct str_app_type str_app[52];
struct agi_app_type agi_app[52];
__attribute__((weak)) int flag2idx(int) { return 0; }
int combat_mind_quaff_chance(int chance) { return chance; }
__attribute__((weak)) int get_song_level(int, int, int) { return 1; }
bool spell_book_recognizes(int rating, int roll) { return rating >= roll; }
static pc_only_data pc_data;
static char_data viewer(uint m_class, int spec) {
    char_data ch{};
    ch.player.m_class = m_class;
    ch.player.spec = spec;
    ch.player.race = RACE_HUMAN;
    ch.player.level = 50;
    ch.points.max_hit = 500;
    ch.points.damroll = 20;
    ch.only.pc = &pc_data;
    ch.curr_stats.Str = ch.curr_stats.Dex = ch.curr_stats.Agi = ch.curr_stats.Int = 100;
    ch.curr_stats.Pow = ch.curr_stats.Luk = 100;
    ch.base_stats.Str = ch.base_stats.Con = ch.base_stats.Int = 100;
    ch.base_stats.Wis = ch.base_stats.Agi = ch.base_stats.Dex = ch.base_stats.Pow = 100;
    return ch;
}
'''


# The viewer a page's line needs, where a warrior doesn't see it.
VIEWERS = {"dragon_roar_facts": ("CLASS_DRAGOON", "SPEC_DRAGON_HUNTER"),
           "springleap_facts": ("CLASS_MONK", "SPEC_WAYOFDRAGON")}


def definitions(text):
    """Every top-level function in a source file: its name, and its text in file order."""
    lines = text.split("\n")
    found = {}
    for index, line in enumerate(lines):
        if line != "{":
            continue
        first = index
        while first > 0 and lines[first - 1] and lines[first - 1][0] not in "}#/" \
                and not lines[first - 1].rstrip().endswith((";", "*/")):
            first -= 1
        head = "\n".join(lines[first:index])
        match = re.search(r"(\w+)\s*\(", head)
        if not match or "=" in head.split("(")[0]:
            continue
        end = index
        while not lines[end].startswith("}"):
            end += 1
        found.setdefault(match.group(1), (first, "\n".join(lines[first:end + 1])))
    return found


def file_scope(text):
    """A source file's own #define lines and externs, which the functions it holds rely on."""
    lines = text.split("\n")
    kept = []
    index = 0
    while index < len(lines):
        if lines[index].startswith("#define") or lines[index].startswith("extern "):
            while lines[index].endswith("\\"):
                kept.append(lines[index])
                index += 1
            kept.append(lines[index])
        index += 1
    return "\n".join(kept)


def reach(text, roots):
    """The functions the roots call, directly or not, in file order, so each is declared first."""
    known = definitions(text)
    seen = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen or name not in known or name.isupper() or name == "dice":
            continue
        seen.add(name)
        stack.extend(re.findall(r"\b(\w+)\s*\(", known[name][1]))
        stack.extend(re.findall(r"\b(\w+_roll)\b", known[name][1]))
    return "\n\n".join(known[name][1] for name in sorted(seen, key=lambda n: known[n][0]))


def check_sources():
    """Each roll is called in its own branch, in order, and is not left as a bare number()."""
    for file, handlers in BRANCHES.items():
        code = strip_comments(source(file).read_text(encoding="utf-8", errors="replace"))
        for signature, wanted in handlers.items():
            if signature is None:
                bodies = [code]
            else:
                bodies = function_bodies(code, rf"\b{re.escape(signature)}") or \
                    function_bodies(code, rf"\b{re.escape(signature.rstrip('('))}\s*\(")
            assert bodies, f"{file}: no definition of {signature}"
            joined = ["".join(body.split()) for body in bodies]
            assert any(_in_order(body, wanted) for body in joined), f"{file} {signature}: {wanted}"


def _in_order(body, wanted):
    position = 0
    for text in wanted:
        position = body.find("".join(text.split()), position)
        if position < 0:
            print("missing:", text)
            return False
        position += 1
    return True


def build(file, directory):
    text = source(file).read_text(encoding="utf-8", errors="replace")
    oracles = ORACLES.get(file, [])
    pages = PAGES.get(file, [])
    roots = [name for name, _ in pages]
    roots += re.findall(r"\b([a-z_]+)\(", " ".join(shared for _, shared in oracles))
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 file_scope(text), reach(text, roots)]
    oracle_calls = "\n    ".join(
        f'same({shared!r}, [&] {{ return (int)({old}); }}, [&](const Rolls &rolls) {{ return (int)({shared}); }});'
        .replace(repr(shared), '"' + shared + '"') for old, shared in oracles)
    page_calls = "\n    ".join(
        'page("%s", [&] { char_data ch = viewer(%s, %s); return %s(&ch); }, { %s });'
        % (name, *VIEWERS.get(name, ("CLASS_WARRIOR", "0")), name,
           ", ".join('"' + line + '"' for line in lines)) for name, lines in pages)
    harness = directory / (re.sub(r"\W", "_", file) + ".cpp")
    harness.write_text(PRELUDE.replace("STUBS", STUBS).replace("FUNCTIONS", "\n\n".join(functions))
                       .replace("ORACLE_CALLS", oracle_calls).replace("PAGE_CALLS", page_calls))
    binary = harness.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                    "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                    "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                    str(harness), "src/abilities/abilities.c", "src/core/random.c",
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)


def main():
    check_sources()
    directory = ROOT / "bin/tests"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-page-chances-", dir=directory) as temporary:
        for file in sorted(set(ORACLES) | set(PAGES)):
            build(file, Path(temporary))


if __name__ == "__main__":
    main()
