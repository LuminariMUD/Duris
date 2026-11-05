#!/usr/bin/env python3
"""Shared ability numbers, batch 10: the last pending spells.

Flame blade, doom and holy blade, the dragoon weapons, essence of the wolf and banish. Builds
src/abilities/abilities.c and the real RNG with their shared and facts functions under
sanitizers. Each roll keeps its pre-conversion expression below as the oracle. Every page is
built at every level for several casters: it must never roll, and every line must fit 79
columns.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

MAGIC = "magic/magic.c"
SPELLS = {
    "SPELL_FLAME_BLADE": "flame_blade",
    "SPELL_DOOM_BLADE": "doom_blade",
    "SPELL_HOLY_BLADE": "doom_blade",
    "SPELL_ENSIS_UNGUIS": "dragoon_weapon",
    "SPELL_LANCEA_CINERALAE": "dragoon_weapon",
    "SPELL_SIMULACRUM_ANGUIS": "dragoon_weapon",
    "SPELL_ESSENCE_OF_WOLF": "essence_of_wolf",
    "SPELL_BANISH": "banish",
}
# In source order within each file, so that each function sees what it calls.
FUNCTIONS = [("specs.object.c", "int doom_blade_proc_roll("), ("specs.object.c", "int doom_blade_proc_level("),
             ("specs.object.c", "int doom_blade_effect_roll("), ("fight.c", "int essence_of_wolf_attacks("),
             ("fight.c", "int essence_of_wolf_attack_cap("), ("fight.c", "int essence_of_wolf_offhand_roll("),
             ("smagic.c", "std::string essence_of_wolf_facts(")]
FUNCTIONS += [(MAGIC, f"static int {name}(") for name in """
    conjured_blade_sunray_level conjured_blade_sunray_chance conjured_blade_fast_fireball_level
    conjured_blade_fast_fireball_chance conjured_blade_fireball_level conjured_blade_fireball_chance
    conjured_blade_flameburst_level conjured_blade_flameburst_chance""".split()]
FUNCTIONS += [(MAGIC, "static std::string conjured_blade_spell_facts(")]
FUNCTIONS += [(MAGIC, f"static int {name}(") for name in
              "flame_blade_fire_aura_level flame_blade_fireshield_level flame_blade_prot_fire_level".split()]
FUNCTIONS += [(MAGIC, "std::string flame_blade_facts(")]
FUNCTIONS += [(MAGIC, f"static int {name}(") for name in """
    banish_base_chance banish_outlevel_margin banish_outlevel_chance banish_zealot_chance
    banish_greater_chance banish_bounded_chance banish_roll""".split()]
FUNCTIONS += [(MAGIC, "std::string banish_facts("), (MAGIC, "std::string doom_blade_facts("),
              (MAGIC, "static float dragoon_spell_cost(P_char ch)\n{"), (MAGIC, "static std::string dragoon_cost_fact("),
              (MAGIC, "std::string dragoon_weapon_facts(")]

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "combat/damage.h"
#include <cassert>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <string>

void randomize(uint64_t seed);

static int devotion;
int GET_CHAR_SKILL_P(P_char, int) { return devotion; }
float dam_factor[LAST_DF + 1];

FUNCTIONS

// The ids the handlers store in value[5], for the spells the pages name.
static_assert(SPELL_SUNRAY == 124 && SPELL_FIREBALL == 26 && SPELL_FLAMEBURST == 195);

static int fingerprint() { return number(0, INT_MAX); }

static void same(const char *name, const std::function<int()> &original,
                 const std::function<int(const Rolls &)> &shared) {
    const int a = shared(lowest_rolls), b = shared(highest_rolls);
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(live_rolls), actual_next = fingerprint();
        if (actual != expected || actual_next != expected_next || actual < a || actual > b) {
            std::fprintf(stderr, "%s: seed %d gave %d, expected %d in %d..%d\n", name, (int)seed,
                         actual, expected, a, b);
            std::abort();
        }
    }
}

static char_data viewer(uint m_class, int spec, int level) {
    char_data ch{};
    ch.player.m_class = m_class;
    ch.player.spec = spec;
    ch.player.level = level;
    ch.points.hit = 200;
    return ch;
}

// The text is exactly these lines.
static void exactly(const std::string &text, const char *lines) {
    if (text != lines) {
        std::fprintf(stderr, "expected:\n%sgot:\n%s", lines, text.c_str());
        std::abort();
    }
}

struct Viewer { uint m_class; int spec; };
static const Viewer viewers[] = {
    { CLASS_DRUID, 0 }, { CLASS_DRAGOON, 0 }, { CLASS_CLERIC, 0 }, { CLASS_CLERIC, SPEC_ZEALOT },
    { CLASS_NECROMANCER, 0 }, { CLASS_NECROMANCER, SPEC_REAPER }, { CLASS_BLIGHTER, SPEC_RUINER },
    { CLASS_THEURGIST, SPEC_THAUMATURGE }, { CLASS_SHAMAN, SPEC_ANIMALIST }, { CLASS_WARRIOR, 0 },
};
static const AbilityFacts pages[] = { flame_blade_facts, doom_blade_facts, dragoon_weapon_facts,
                                      essence_of_wolf_facts, banish_facts };

int main() {
    dam_factor[DF_ELSHIELDRED] = 0.75f;
    dam_factor[DF_PROTECTION] = 0.85f;
    dam_factor[DF_ELSHIELDINC] = 1.5f;
    dam_factor[DF_VULNCOLD] = 1.35f;

    // Rolls, and the old expressions as oracles.
    same("essence attacks", [] { return number(2, 4); }, essence_of_wolf_attacks);
    same("essence off hand", [] { return number(0, 1); }, essence_of_wolf_offhand_roll);
    same("doom effect", [] { return number(0, 4); }, doom_blade_effect_roll);
    same("banish", [] { return number(1, 100); }, banish_roll);
    for (int level : { 1, 8, 10, 30, 47, 48, 49, 50, 56, 60 }) {
        char_data ch = viewer(CLASS_NECROMANCER, SPEC_REAPER, level);
        same("doom proc", [&] { return number(0, MAX(8, 56 - level)); },
             [&](const Rolls &rolls) { return doom_blade_proc_roll(rolls, &ch); });
        assert(doom_blade_proc_level(&ch) == MIN(40, level));
        assert(essence_of_wolf_attack_cap(level) == level / 10);
        for (int skill : { 0, 50, 100 })
            for (int target : { 0, 1, 25, 60 }) {
                devotion = skill;
                assert(banish_base_chance(level, &ch, target) ==
                       (int)(((40 * level) + (10 * skill)) / (target + 1)));
            }
    }
    devotion = 0;
    for (int chance : { -5, 0, 1, 2, 3, 33, 94, 95, 96, 118, 1000 }) {
        assert(banish_zealot_chance(chance) == (int)(chance * 1.25));
        assert(banish_greater_chance(chance) == (int)(chance * 1 / 3));
        assert(banish_bounded_chance(chance) == BOUNDED(1, chance, 95));
    }

    // Each spell tier, against the thresholds and chances the handlers held as literals.
    assert(conjured_blade_sunray_level() == 51 && conjured_blade_sunray_chance() == 30);
    assert(conjured_blade_fast_fireball_level() == 41 && conjured_blade_fast_fireball_chance() == 25);
    assert(conjured_blade_fireball_level() == 36 && conjured_blade_fireball_chance() == 40);
    assert(conjured_blade_flameburst_level() == 21 && conjured_blade_flameburst_chance() == 40);
    assert(flame_blade_fire_aura_level() == 56 && flame_blade_fireshield_level() == 31 &&
           flame_blade_prot_fire_level() == 26);
    assert(banish_outlevel_margin() == 10 && banish_outlevel_chance() == 95);

    // Every page at every level for every kind of caster: no rolls, short lines.
    randomize(9);
    const int untouched = fingerprint();
    for (const Viewer &v : viewers)
        for (int level = 1; level <= 62; ++level)
            for (AbilityFacts page : pages) {
                char_data ch = viewer(v.m_class, v.spec, level);
                randomize(9);
                const std::string text = page(&ch);
                assert(fingerprint() == untouched);
                assert(!text.empty() && text.back() == '\n');
                for (size_t start = 0, end; start < text.size(); start = end + 1) {
                    end = text.find('\n', start);
                    if (end - start > 79 || text.compare(start, 2, "  ") != 0) {
                        std::fprintf(stderr, "level %d: \"%s\"\n", level,
                                     text.substr(start, end - start).c_str());
                        std::abort();
                    }
                }
                assert(text.find("--") == std::string::npos);
            }

    const std::string holds = "  If another player holds it, it loses its spell and protections.\n";
    const std::string other = "  Other effects on fire damage add to that.\n";
    const std::string vulnerable = "  A wielder vulnerable to fire uses other factors.\n";
    const auto flame = [](int level) {
        char_data ch = viewer(CLASS_DRUID, 0, level);
        return flame_blade_facts(&ch);
    };
    exactly(flame(1), ("  Below level 21 the blade casts no spell.\n" + holds).c_str());
    exactly(flame(20), ("  Below level 21 the blade casts no spell.\n" + holds).c_str());
    exactly(flame(21), ("  Blade's spell: flameburst at your level, 1 in 40 hits\n" + holds).c_str());
    exactly(flame(25), ("  Blade's spell: flameburst at your level, 1 in 40 hits\n" + holds).c_str());
    exactly(flame(26), ("  Blade's spell: flameburst at your level, 1 in 40 hits\n"
                        "  Fire spell damage to you, wielded: 85% of normal\n" + other + vulnerable + holds).c_str());
    const std::string shield = "  Fire spell damage to you, wielded: 75% of normal\n" + other +
                               "  Cold spell damage to you, wielded: 150% of normal\n" + vulnerable + holds;
    exactly(flame(31), ("  Blade's spell: flameburst at your level, 1 in 40 hits\n" + shield).c_str());
    exactly(flame(35), ("  Blade's spell: flameburst at your level, 1 in 40 hits\n" + shield).c_str());
    exactly(flame(36), ("  Blade's spell: fireball at your level, 1 in 40 hits\n" + shield).c_str());
    exactly(flame(40), ("  Blade's spell: fireball at your level, 1 in 40 hits\n" + shield).c_str());
    exactly(flame(41), ("  Blade's spell: fireball at your level, 1 in 25 hits\n" + shield).c_str());
    exactly(flame(50), ("  Blade's spell: fireball at your level, 1 in 25 hits\n" + shield).c_str());
    exactly(flame(51), ("  Blade's spell: sunray at your level, 1 in 30 hits\n" + shield).c_str());
    exactly(flame(55), ("  Blade's spell: sunray at your level, 1 in 30 hits\n" + shield).c_str());
    exactly(flame(56), ("  Blade's spell: sunray at your level, 1 in 30 hits\n"
                        "  Fire spell damage to you, wielded: 75% of normal\n" + other +
                        "  Cold spell damage to you, wielded: 185% of normal\n"
                        "  Fire spells from others heal you a quarter of their damage instead.\n" + vulnerable + holds).c_str());

    {
        char_data ch = viewer(CLASS_DRAGOON, 0, 1);
        exactly(dragoon_weapon_facts(&ch),
                "  Below level 21 the blade casts no spell.\n"
                "  Spirit damage to yourself: 20 at your current health, before defenses\n"
                "  You pay only if the weapon is delivered.\n");
        ch = viewer(CLASS_DRAGOON, 0, 50);
        exactly(dragoon_weapon_facts(&ch),
                "  Blade's spell: fireball at your level, 1 in 25 hits\n"
                "  Spirit damage to yourself: 20 at your current health, before defenses\n"
                "  You pay only if the weapon is delivered.\n");
    }

    const std::string poisons = "  Cloud's spell: 1 in 5 each: wither, blindness, disease, curse, poison\n";
    const auto doom = [](uint m_class, int spec, int level) {
        char_data ch = viewer(m_class, spec, level);
        return doom_blade_facts(&ch);
    };
    const std::string undead = "  An undead target always takes undead to death instead.\n";
    exactly(doom(CLASS_NECROMANCER, SPEC_REAPER, 1),
            ("  Death cloud: 1 in 56 hits at your level\n  Cloud's spell level: 1\n" + poisons + undead).c_str());
    exactly(doom(CLASS_NECROMANCER, SPEC_REAPER, 47),
            ("  Death cloud: 1 in 10 hits at your level\n  Cloud's spell level: 40\n" + poisons + undead).c_str());
    exactly(doom(CLASS_THEURGIST, SPEC_THAUMATURGE, 48),
            ("  Death cloud: 1 in 9 hits at your level\n  Cloud's spell level: 40\n" + poisons + undead).c_str());
    exactly(doom(CLASS_THEURGIST, SPEC_THAUMATURGE, 60),
            ("  Death cloud: 1 in 9 hits at your level\n  Cloud's spell level: 40\n" + poisons + undead).c_str());
    // A ruiner has the spell, but not the undead branch.
    exactly(doom(CLASS_BLIGHTER, SPEC_RUINER, 39),
            ("  Death cloud: 1 in 18 hits at your level\n  Cloud's spell level: 39\n" + poisons).c_str());

    {
        char_data ch = viewer(CLASS_SHAMAN, SPEC_ANIMALIST, 50);
        exactly(essence_of_wolf_facts(&ch),
                "  Target's extra attacks each round: 2-4\n"
                "  Most at target's level 10, 20, 30: 1, 2, 3; none below 10\n"
                "  With an off-hand weapon: 1 off-hand attack more; 1 in 2 rounds another\n"
                "  That other one uses up an extra attack if any are left.\n"
                "  An NPC target is refused.\n"
                "  Nothing happens if you already share it or the target already has it.\n"
                "  It ends when you use a command, or when the target walks 2 rooms away.\n");
        assert(essence_of_wolf_attack_cap(9) == 0 && essence_of_wolf_attack_cap(39) == 3 &&
               essence_of_wolf_attack_cap(40) == 4);
    }

    const std::string limits =
        "  Greater dracolich or avatar: 33% of that chance\n"
        "  Final chance: 1-95, and a roll of 1-100 must be below it\n"
        "  It affects pets only: elementals, efreet, undead, angels, conjured pets.\n"
        "  No save. It does not spare your own pets or your allies' pets.\n"
        "  Earth, fire, air and water elementals and efreet are safe on their own\n"
        "  plane, undead on the negative plane and angels on the ethereal plane.\n";
    {
        char_data ch = viewer(CLASS_CLERIC, SPEC_ZEALOT, 50);
        devotion = 100;
        exactly(banish_facts(&ch),
                ("  Chance: 3000 / (target's level + 1) at your level and devotion\n"
                 "  Target over 10 levels below you: chance is 95\n"
                 "  As a zealot: 125% of that chance\n" + limits).c_str());
        devotion = 0;
        ch = viewer(CLASS_CLERIC, 0, 1);
        exactly(banish_facts(&ch),
                ("  Chance: 40 / (target's level + 1) at your level and devotion\n"
                 "  Target over 10 levels below you: chance is 95\n" + limits).c_str());
    }
    return 0;
}
'''

# Each handler's chain, in order, tying each level to its own spell and chance.
TIERS = ("if (GET_LEVEL(ch) >= conjured_blade_sunray_level()) { blade->value[5] = 124; "
         "blade->value[7] = conjured_blade_sunray_chance(); } "
         "else if (GET_LEVEL(ch) >= conjured_blade_fast_fireball_level()) { blade->value[5] = 26; "
         "blade->value[7] = conjured_blade_fast_fireball_chance(); } "
         "else if (GET_LEVEL(ch) >= conjured_blade_fireball_level()) { blade->value[5] = 26; "
         "blade->value[7] = conjured_blade_fireball_chance(); } "
         "else if (GET_LEVEL(ch) >= conjured_blade_flameburst_level()) { blade->value[5] = 195; "
         "blade->value[7] = conjured_blade_flameburst_chance(); }")


def squeeze(text):
    return re.sub(r"\s+", " ", text)


def check_sources():
    magic = strip_comments(source(MAGIC).read_text(encoding="utf-8", errors="replace"))
    for handler in ("spell_flame_blade", "spell_ensis_unguis", "spell_lancea_cineralae", "spell_simulacrum_anguis"):
        body = squeeze(function_bodies(magic, rf"\bvoid\s+{handler}\s*\(")[0])
        assert TIERS in body, handler
        assert "blade->value[6] = GET_LEVEL(ch);" in body, handler
    flame = squeeze(function_bodies(magic, r"\bvoid\s+spell_flame_blade\s*\(")[0])
    for level, flag in (("flame_blade_fire_aura_level", "SET_BIT(blade->bitvector2, AFF2_FIRE_AURA)"),
                        ("flame_blade_fireshield_level", "SET_BIT(blade->bitvector2, AFF2_FIRESHIELD)"),
                        ("flame_blade_prot_fire_level", "SET_BIT(blade->bitvector, AFF_PROT_FIRE)")):
        assert f"if (GET_LEVEL(ch) >= {level}()) {{ {flag}; }}" in flame, level

    # The dragoon weapons take the shared cost on both paths, then pay it through spell_damage.
    submit = squeeze(function_bodies(magic, r"\bbool\s+submit_conjured_weapon\s*\(")[0])
    assert "conjured_weapon_publish_effect(actor, blade, kind, dragoon_spell_cost(actor));" in submit
    assert "static_cast<uint32_t>(GET_PID(actor)), dragoon_spell_cost(actor)," in submit
    assert "0.10f" not in submit
    effect = squeeze(function_bodies(magic, r"\bvoid\s+conjured_weapon_publish_effect\s*\(")[0])
    assert "spell_damage(actor, actor, self_damage, SPLDAM_SPIRIT, SPLDAM_GRSPIRIT | SPLDAM_NOSHRUG, NULL);" in effect
    done = function_bodies(magic, r"\bvoid\s+conjured_weapon_grant_completed\s*\(")[0]
    assert done.index("if (!committed)") < done.index("conjured_weapon_publish_effect(")
    assert "no health was spent" in done

    # Banish keeps its order, and has no save.
    single = squeeze(function_bodies(magic, r"\bvoid\s+spell_single_banish\s*\(")[0])
    order = ["chance = banish_base_chance(level, ch, GET_LEVEL(victim));",
             "if (GET_LEVEL(ch) > (banish_outlevel_margin() + GET_LEVEL(victim))) { chance = banish_outlevel_chance(); }",
             "if (GET_SPEC(ch, CLASS_CLERIC, SPEC_ZEALOT)) { chance = banish_zealot_chance(chance); }",
             "if (IS_GREATER_DRACO(victim) || IS_GREATER_AVATAR(victim)) { chance = banish_greater_chance(chance); }",
             "chance = banish_bounded_chance(chance);", "if (chance > banish_roll(live_rolls))", "extract_char(victim);"]
    places = [single.index(step) for step in order]
    assert places == sorted(places)
    assert "NewSaves" not in single
    banish = squeeze(function_bodies(magic, r"\bvoid\s+spell_banish\s*\(")[0])
    assert banish.count("get_linked_char(tch, LNK_PET) && can_banish(ch, tch)") == 2
    assert "spell_single_banish(level, ch, arg, type, tch, 0);" in banish
    can = squeeze(function_bodies(magic, r"\bbool\s+can_banish\s*\(")[0])
    for rule in ("SECT_EARTH_PLANE", "SECT_FIREPLANE", "SECT_AIR_PLANE", "SECT_WATER_PLANE", "SECT_ETHEREAL",
                 "SECT_NEG_PLANE", "TAG_CONJURED_PET", "RACE_I_ELEMENTAL", "RACE_EFREET"):
        assert rule in can, rule

    # The doom blade's proc reads what its page shows, in its own branches.
    procs = strip_comments(source("specs.object.c").read_text(encoding="utf-8", errors="replace"))
    proc = squeeze(function_bodies(procs, r"\bint\s+doom_blade_Proc\s*\(")[0])
    order = ["lvl = doom_blade_proc_level(ch);", "if (doom_blade_proc_roll(live_rolls, ch))",
             "IS_UNDEADRACE(vict) && (GET_SPEC(ch, CLASS_NECROMANCER, SPEC_REAPER) || "
             "GET_SPEC(ch, CLASS_THEURGIST, SPEC_THAUMATURGE))",
             "spell_undead_to_death(lvl, ch", "rand = doom_blade_effect_roll(live_rolls);"]
    places = [proc.index(step) for step in order]
    assert places == sorted(places)
    for spell in ("wither", "blindness", "disease", "curse", "poison"):
        assert f"spell_{spell}(lvl, ch" in proc, spell
    # The proc runs from weapon_proc on a melee hit, and only with no spell in value[5].
    fight = strip_comments(source("fight.c").read_text(encoding="utf-8", errors="replace"))
    weapon = squeeze(function_bodies(fight, r"\bbool\s+weapon_proc\s*\(")[0])
    assert "if (!obj->value[5] || obj->value[7] <= 0)" in weapon and "CMD_MELEE_HIT" in weapon
    assert "if (number(0, obj->value[7] - 1)) return FALSE;" in weapon
    lamify = squeeze(function_bodies(procs, r"\bint\s+flame_blade\s*\(")[0])
    assert ("if (GET_PID(tch) != obj->timer[1])" in lamify and "IS_NPC(tch)" in lamify and
            "obj->value[5] = 0;" in lamify and "obj->bitvector2 = 0;" in lamify)

    # Essence of the wolf gives its target the attacks, ends with the caster's command or a move.
    attacks = squeeze(function_bodies(fight, r"\bint\s+calculate_attacks\s*\(")[0])
    wolf = attacks[attacks.index("if (get_linking_char(ch, LNK_ESSENCE_OF_WOLF))"):]
    order = ["int extra = essence_of_wolf_attacks(live_rolls);",
             "extra = MIN(extra, essence_of_wolf_attack_cap(GET_LEVEL(ch)));",
             "if (ch->equipment[SECONDARY_WEAPON]) { ADD_ATTACK(SECONDARY_WEAPON); "
             "if (essence_of_wolf_offhand_roll(live_rolls)) { extra--; ADD_ATTACK(SECONDARY_WEAPON); } }",
             "while (extra-- > 0) ADD_ATTACK(PRIMARY_WEAPON);"]
    places = [wolf.index(step) for step in order]
    assert places == sorted(places)
    handler = squeeze(function_bodies(strip_comments(source("smagic.c").read_text(encoding="utf-8", errors="replace")),
                                      r"\bvoid\s+spell_essence_of_the_wolf\s*\(")[0])
    assert "IS_NPC(victim)" in handler and "link_char(ch, victim, LNK_ESSENCE_OF_WOLF);" in handler
    assert ("get_linked_char(ch, LNK_ESSENCE_OF_WOLF) || get_linking_char(victim, LNK_ESSENCE_OF_WOLF)" in handler)
    interp = source("interp.c").read_text(encoding="utf-8", errors="replace")
    assert "clear_links(ch, LNK_ESSENCE_OF_WOLF);" in interp
    affects = source("affects.c").read_text(encoding="utf-8", errors="replace")
    assert 'define_link(LNK_ESSENCE_OF_WOLF, "ESSENCE", essence_broken, LNKFLG_ROOM | LNKFLG_EXCLUSIVE);' in affects
    # A walk breaks it only when the other is in neither room, so the second room away.
    links = squeeze(function_bodies(affects, r"\bvoid\s+check_room_links\s*\(")[0])
    assert "if (cld->linking->in_room != old_room && cld->linking->in_room != new_room) " in links
    assert "check_room_links(ch, was_in, new_room);" in source("actmove.c").read_text(errors="replace")
    # Nothing else reads the link, so no damage modifier or skin rule touches this spell.
    assert "ESSENCE_OF_WOLF" not in source("dam_mods.c").read_text(encoding="utf-8", errors="replace")
    assert fight.count("LNK_ESSENCE_OF_WOLF") == 1

    # The factors flame blade's page reads: the keys, the live values and the branches.
    properties = dict(line.split("=", 1) for line in
                      (ROOT / "lib/duris.properties").read_text(errors="replace").splitlines() if "=" in line)
    for factor, key, value in (("DF_ELSHIELDRED", "damage.reduction.fireColdShield", 0.75),
                               ("DF_PROTECTION", "damage.reduction.protElement", 0.85),
                               ("DF_ELSHIELDINC", "damage.increase.fireColdShield", 1.5),
                               ("DF_VULNCOLD", "damage.increase.vulnCold", 1.35)):
        assert re.search(rf'dam_factor\[{factor}\] =\s*get_property\("{key}"', fight), factor
        assert float(properties[key]) == value, key
    mods = squeeze(source("dam_mods.c").read_text(encoding="utf-8", errors="replace"))
    assert ("else if (IS_AFFECTED2(victim, AFF2_FIRESHIELD)) { dam_mod->mod += dam_factor[DF_ELSHIELDRED] - 1.0;") in mods
    assert ("else if (IS_AFFECTED(victim, AFF_PROT_FIRE)) { dam_mod->mod += dam_factor[DF_PROTECTION] - 1.0;") in mods
    assert ("else if (IS_AFFECTED2(victim, AFF2_FIRE_AURA)) { dam_mod->type = dam_mod_type::More; "
            "dam_mod->mod += dam_factor[DF_VULNCOLD] - 1.0;") in mods
    assert "dam_mod->mod += dam_factor[DF_ELSHIELDINC] - 1.0;" in mods
    spell_damage = squeeze(fight)
    assert ("type == SPLDAM_FIRE && ch != victim && ((IS_AFFECTED2(victim, AFF2_FIRE_AURA) && "
            "IS_AFFECTED2(victim, AFF2_FIRESHIELD))") in spell_damage

    # Registration: each id its own case, and the list no longer names them.
    registered = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    pending = (ROOT / "tests/fixtures/ability_coverage_pending.txt").read_text().split()
    for constant, name in SPELLS.items():
        assert re.search(rf"case {constant}:\s*return {name}_facts;", registered), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name
        assert constant not in pending, constant
    # Holy blade and doom blade share a handler.
    skills = source("classes/skills.c").read_text(encoding="utf-8", errors="replace")
    assert re.search(r'"holy blade", SPELL_HOLY_BLADE,[^;]*spell_doom_blade\)', skills)
    assert not [name for name in pending if name.startswith("SPELL_")]


def main():
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)")]
    functions += [extract_function(file, signature) for file, signature in FUNCTIONS]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-10-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch10.cpp"
        harness.write_text(HARNESS.replace("FUNCTIONS", "\n".join(functions)))
        binary = directory / "batch10"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)
    print("PASS: ability batch 10")


if __name__ == "__main__":
    main()
