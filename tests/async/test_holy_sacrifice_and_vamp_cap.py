#!/usr/bin/env python3
"""Holy Sacrifice shares one bounded healing budget, and the vamp ceiling stops at 2.5x.

Runs the real holy_sacrifice_heal and vamp from fight.c (with IS_MORPH and healing auras)
against the shipped
vamping.holySacrifice.* properties: each injured groupmate heals up to 30% of a blow, but a
blow heals the group by at most 90% of its damage and 60% of the owner's max hp, a combat
round by at most 120% of the owner's max hp, and against players both limits are halved.
Then evaluates the real VAMPPERCENT macro (with the real BOUNDEDF and GET_PRIME_CLASS):
prime anti-paladins get +0.25 on top of the Power multiplier, never past 2.5x.
"""

import re
import subprocess

from _paths import HARNESS_STUBS, ROOT, extract_function, source

SHIPPED = {
    "vamping.holySacrifice": 0.3,
    "vamping.holySacrifice.hitDamageCap": 0.9,
    "vamping.holySacrifice.hitMaxHpCap": 0.6,
    "vamping.holySacrifice.roundMaxHpCap": 1.2,
    "vamping.holySacrifice.pvpMod": 0.5,
    "vamping.maxHP.bonus.antipaladin": 0.25,
    "vamping.maxHP.bonus.all": 0.0,
    "innate.paladin_aura.healing_mod": 0.2,
}
properties = {}
for line in (ROOT / "lib/duris.properties").read_text(encoding="utf-8").splitlines():
    key, _, value = line.partition("=")
    if key in SHIPPED:
        properties[key] = float(value)
assert properties == SHIPPED, properties

# check_vamp keeps every existing gate and hands the healing to the budgeted helper.
check_vamp = extract_function("fight.c", "void check_vamp(")
gate = check_vamp[check_vamp.index("IS_AFFECTED4(victim, AFF4_HOLY_SACRIFICE)") - 120 :]
gate = gate[: gate.index("holy_sacrifice_heal(victim, dam);")]
for condition in (
    "dam >= 2",
    "!IS_AFFECTED4(ch, AFF4_BATTLE_ECSTASY)",
    "(flags & RAWDAM_HOLYSAC)",
    "!affected_by_spell(victim, SPELL_BMANTLE)",
    "!affected_by_spell(victim, SPELL_PLAGUE)",
    "!affected_by_spell(victim, SPELL_FLAMESTRIKE)",
):
    assert condition in gate, condition
assert "vamping.holySacrifice" not in check_vamp
raw_damage = extract_function("fight.c", "int raw_damage(")
note_at = raw_damage.index("holy_sacrifice_note_hit(ch, victim);")
assert "dam > 0 && IS_AFFECTED4(victim, AFF4_HOLY_SACRIFICE)" in raw_damage[note_at - 100:note_at]
assert note_at < raw_damage.index("check_vamp(ch, victim, dam, flags);", note_at)

# The round state is runtime-only character state, so a recast cannot refresh it.
structs = source("structs.h").read_text(encoding="utf-8")
assert re.search(r"unsigned long long holy_sacrifice_round;\s*int holy_sacrifice_healed;", structs)

# Every help source describes the shared limits and the 2.5x ceiling.
for help_file in ("help/duris_help_parsed.hlp", "lib/information/help_index"):
    text = " ".join((ROOT / help_file).read_text(encoding="utf-8").split())
    for phrase in ("no more than 90% of its damage", "60% of the Paladin's own maximum hit points",
                   "at most 120% of the Paladin's maximum hit points", "halves these limits for the rest of the combat round",
                   "two and a half times their normal maximum"):
        assert phrase in text, (help_file, phrase)

property_rows = ",\n".join(f'    {{"{key}", {value!r}}}' for key, value in SHIPPED.items())

PRELUDE = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "classes/paladins.h"
#include "net/comm.h"
#include <deque>
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <map>
#include <set>
#include <string>
#include <vector>

static const std::map<std::string, double> shipped = {
""" + property_rows + r"""
};
static std::set<std::string> unknown_properties;
float get_property(const char *key, double fallback) {
    auto it = shipped.find(key);
    if (it == shipped.end()) {
        unknown_properties.insert(key);
        return fallback;
    }
    return it->second;
}

unsigned long long ne_event_tick = 0;

affected_type *get_spell_from_char(P_char ch, int spell, void *, int) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == spell) return af;
    return nullptr;
}
bool affected_by_spell(P_char ch, int spell) {
    return get_spell_from_char(ch, spell, nullptr, 0) != nullptr;
}
bool affected_by_skill(P_char ch, int skill) { return affected_by_spell(ch, skill); }
void wear_off_message(P_char, affected_type *) {}
void affect_remove(P_char ch, affected_type *af) {
    auto **current = &ch->affected;
    while (*current && *current != af) current = &(*current)->next;
    assert(*current == af);
    *current = af->next;
}
int number(int low, int) { return low; } // deterministic healing-reduction rolls
static int vamp_calls = 0;
void gmcp_char_vitals(P_char) { ++vamp_calls; }
static std::map<P_char, P_char> masters;
P_char get_linked_char(P_char ch, ush_int type) {
    auto it = masters.find(ch);
    return type == LNK_PET && it != masters.end() ? it->second : nullptr;
}

"""

DRIVER = r"""
static void qualifying_hit(P_char attacker, P_char owner, int damage) {
    holy_sacrifice_note_hit(attacker, owner);
    holy_sacrifice_heal(owner, damage);
}
static std::deque<pc_only_data> players;
static void init(char_data &ch, bool pc, int room, int max_hit) {
    ch.specials.position = STAT_NORMAL;
    if (!pc) ch.specials.act |= ACT_ISNPC;
    else ch.only.pc = &players.emplace_back();
    ch.in_room = room;
    ch.points.max_hit = max_hit;
    ch.points.hit = max_hit;
}

struct test_group {
    std::vector<group_list> nodes;
    explicit test_group(std::vector<P_char> members) : nodes(members.size()) {
        for (size_t i = 0; i < members.size(); ++i) {
            nodes[i].ch = members[i];
            nodes[i].next = i + 1 < members.size() ? &nodes[i + 1] : nullptr;
        }
        for (P_char ch : members) ch->group = &nodes[0];
    }
    ~test_group() {
        for (auto &node : nodes) node.ch->group = nullptr;
    }
};

static char_data paladin, paladin2, mount, monster, enemy_pc, far_mate, mates[10];
static affected_type plague{}, healing_aura{};
static void healing_aura_on(P_char ch) {
    healing_aura.type = AURA_HEALING;
    healing_aura.modifier = 56;
    ch->affected = &healing_aura;
    ch->specials.affected_by3 |= AFF3_PALADIN_AURA;
}
static void healing_aura_off(P_char ch) {
    ch->affected = nullptr;
    ch->specials.affected_by3 &= ~AFF3_PALADIN_AURA;
}

// Wound every groupmate to 1 hp; next_round starts a fresh combat round; healed totals it.
static void wound_all() {
    for (auto &mate : mates) mate.points.hit = 1;
    far_mate.points.hit = 1;
}
static void next_round() {
    ne_event_tick += PULSE_VIOLENCE;
}
static int healed(int count) {
    int total = 0;
    for (int i = 0; i < count; ++i) total += GET_HIT(&mates[i]) - 1;
    return total;
}

int main() {
    init(paladin, true, 1, 1500);
    init(paladin2, true, 1, 1500);
    init(mount, false, 1, 1000);
    init(monster, false, 1, 1000);
    init(enemy_pc, true, 1, 1000);
    init(far_mate, true, 2, 1000);
    for (auto &mate : mates) init(mate, true, 1, 1000);
    ne_event_tick = 1000 * PULSE_VIOLENCE;

    // A 1,000-point blow on a 1,500 hp owner: each groupmate heals up to 300, but the
    // group as a whole gets at most 900. Small groups keep the full 30%.
    for (int size : {1, 3, 5, 10}) {
        std::vector<P_char> members{&paladin};
        for (int i = 0; i < size; ++i) members.push_back(&mates[i]);
        test_group party(members);
        wound_all();
        next_round();
        qualifying_hit(&monster, &paladin, 1000);
        const int expected = std::min(300 * size, 900);
        assert(healed(size) == expected);
        for (int i = 0; i < size; ++i) assert(GET_HIT(&mates[i]) - 1 == expected / size);
    }

    // A blow far beyond the owner's hp: 60% of the owner's max hp is the ceiling.
    {
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        wound_all();
        next_round();
        qualifying_hit(&monster, &paladin, 3000); // 90% would be 2,700
        assert(healed(5) == 900);
    }

    // Many blows in one round share the 120% round budget (1,800 hp), which resets on the
    // next round; a blow at the start of the next round gets the full allowance.
    {
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        wound_all();
        next_round();
        for (int i = 0; i < 20; ++i) qualifying_hit(&monster, &paladin, 200);
        assert(healed(5) == 1800);
        assert(paladin.specials.holy_sacrifice_healed == 1800);
        // Still the same round one pulse before it ends.
        ne_event_tick += PULSE_VIOLENCE - 1;
        qualifying_hit(&monster, &paladin, 1000);
        assert(healed(5) == 1800);
        ++ne_event_tick;
        qualifying_hit(&monster, &paladin, 1000);
        assert(healed(5) == 2700 && paladin.specials.holy_sacrifice_healed == 900);
    }

    // Only actual healing is counted: groupmates at full hp are skipped, and what a
    // nearly-healed groupmate cannot take passes to the others.
    {
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        wound_all();
        mates[0].points.hit = 1000;             // full: takes nothing
        mates[1].points.hit = 1000 - 50;        // needs 50
        next_round();
        vamp_calls = 0;
        qualifying_hit(&monster, &paladin, 1000);
        assert(vamp_calls == 4);
        assert(GET_HIT(&mates[0]) == 1000 && GET_HIT(&mates[1]) == 1000);
        // The 850 left is split between the other three, each under the 300 limit.
        int rest = 0;
        for (int i = 2; i < 5; ++i) {
            assert(GET_HIT(&mates[i]) - 1 >= 283 && GET_HIT(&mates[i]) - 1 <= 284);
            rest += GET_HIT(&mates[i]) - 1;
        }
        assert(rest == 850 && paladin.specials.holy_sacrifice_healed == 900);
    }

    // Healing modifiers cannot push past a groupmate's share or the shared budget.
    {
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        wound_all();
        next_round();
        for (auto &mate : mates) healing_aura_on(&mate);
        qualifying_hit(&monster, &paladin, 1000);
        assert(healed(5) == 900);
        for (auto &mate : mates) healing_aura_off(&mate);
    }
    {
        // Real level-56 healing aura: 30 HP plus floor(30 * 11.2%) = 33.
        test_group party({&paladin, &mates[0]});
        wound_all();
        next_round();
        healing_aura_on(&mates[0]);
        qualifying_hit(&monster, &paladin, 100);
        assert(healed(1) == 33);
        healing_aura_off(&mates[0]);
    }

    // Existing exclusions: the owner, plagued groupmates, other Holy Sacrifice holders
    // and groupmates in another room get nothing, and do not dilute the others.
    {
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &far_mate});
        plague.type = SPELL_PLAGUE;
        mates[1].affected = &plague;
        mates[2].specials.affected_by4 |= AFF4_HOLY_SACRIFICE;
        wound_all();
        paladin.points.hit = 1;
        next_round();
        qualifying_hit(&monster, &paladin, 1000);
        assert(GET_HIT(&mates[0]) == 301);
        assert(GET_HIT(&mates[1]) == 1 && GET_HIT(&mates[2]) == 1 && GET_HIT(&far_mate) == 1);
        assert(GET_HIT(&paladin) == 1);
        mates[1].affected = nullptr;
        mates[2].specials.affected_by4 &= ~AFF4_HOLY_SACRIFICE;
        paladin.points.hit = paladin.points.max_hit;
    }

    // Against players, and their morphs, both limits are halved: 450 a blow, 900 a round.
    {
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        wound_all();
        next_round();
        qualifying_hit(&enemy_pc, &paladin, 1000);
        assert(healed(5) == 450);
        for (int i = 0; i < 5; ++i) qualifying_hit(&enemy_pc, &paladin, 1000);
        assert(healed(5) == 900);

        char_data morph{};
        npc_only_data morph_npc{};
        init(morph, false, 1, 1000);
        morph.only.npc = &morph_npc;
        morph_npc.orig_char = &enemy_pc;
        wound_all();
        next_round();
        qualifying_hit(&morph, &paladin, 1000);
        assert(healed(5) == 450);

        // Healing already shared against monsters counts toward the smaller PvP round limit.
        wound_all();
        next_round();
        qualifying_hit(&monster, &paladin, 1000);
        qualifying_hit(&enemy_pc, &paladin, 1000);
        assert(healed(5) == 900);
    }

    // Pets, including pets whose master is morphed, are player-controlled sources.
    {
        char_data pet{}, master_form{};
        npc_only_data pet_data{}, master_data{};
        init(pet, false, 1, 1000);
        init(master_form, false, 1, 1000);
        pet.only.npc = &pet_data;
        master_form.only.npc = &master_data;
        master_data.orig_char = &enemy_pc;
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        for (P_char master : {&enemy_pc, &master_form}) {
            masters[&pet] = master;
            wound_all(); next_round();
            qualifying_hit(&pet, &paladin, 1000);
            assert(healed(5) == 450);
            qualifying_hit(&monster, &paladin, 1000);
            qualifying_hit(&pet, &paladin, 1000);
            assert(healed(5) == 900);
        }
        masters.clear();
        // A genuinely NPC-owned pet keeps the PvE limits.
        masters[&pet] = &monster;
        wound_all(); next_round();
        qualifying_hit(&pet, &paladin, 1000);
        assert(healed(5) == 900);
        masters.clear();
    }

    // Once PvP starts, NPC hits cannot reopen the larger allowance.
    {
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        for (bool player_first : {false, true}) {
            wound_all(); next_round();
            qualifying_hit(player_first ? &enemy_pc : &monster, &paladin, 1000);
            qualifying_hit(player_first ? &monster : &enemy_pc, &paladin, 1000);
            for (int i = 0; i < 5; ++i) qualifying_hit(&monster, &paladin, 1000);
            assert(healed(5) == 900 && paladin.specials.holy_sacrifice_pvp);
        }
        wound_all(); next_round();
        qualifying_hit(&monster, &paladin, 1000);
        qualifying_hit(&monster, &paladin, 1000);
        assert(healed(5) == 1800 && !paladin.specials.holy_sacrifice_pvp);
        // Late PvP stops further healing, but never claws back prior PvE healing.
        qualifying_hit(&enemy_pc, &paladin, 1000);
        qualifying_hit(&monster, &paladin, 1000);
        assert(healed(5) == 1800 && paladin.specials.holy_sacrifice_pvp);
    }

    // Positive player hits that cannot heal still mark PvP for the round:
    // the raw damage hook runs before the sub-2-HP and Battle Ecstasy gates.
    {
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        for (bool battle_ecstasy : {false, true}) {
            wound_all(); next_round();
            if (battle_ecstasy) enemy_pc.specials.affected_by4 |= AFF4_BATTLE_ECSTASY;
            holy_sacrifice_note_hit(&enemy_pc, &paladin);
            assert(healed(5) == 0);
            qualifying_hit(&monster, &paladin, 1000);
            assert(healed(5) == 450);
            enemy_pc.specials.affected_by4 &= ~AFF4_BATTLE_ECSTASY;
        }
    }

    // Group entries stay on the original player; all eligibility and healing use the body.
    {
        char_data original{}, body{};
        npc_only_data body_data{};
        init(original, true, 2, 1000);
        init(body, false, 1, 1000);
        body.only.npc = &body_data;
        body_data.orig_char = &original;
        original.only.pc->switched = &body;
        body.points.hit = 1;
        test_group party({&paladin, &original});
        next_round();
        qualifying_hit(&monster, &paladin, 1000);
        assert(body.points.hit == 301 && original.points.hit == 1000);
        body.in_room = 2;
        original.in_room = 1; // an original in the room must not make an absent body eligible
        next_round();
        qualifying_hit(&monster, &paladin, 1000);
        assert(body.points.hit == 301);
        body.in_room = 1;
        for (int excluded : {SPELL_PLAGUE, TAG_BUILDING}) {
            affected_type affect{};
            affect.type = excluded;
            body.affected = &affect;
            next_round();
            qualifying_hit(&monster, &paladin, 1000);
            assert(body.points.hit == 301);
            body.affected = nullptr;
        }
        body.specials.affected_by4 |= AFF4_HOLY_SACRIFICE;
        next_round();
        qualifying_hit(&monster, &paladin, 1000);
        assert(body.points.hit == 301);
    }

    // A switched group pet can also have its own group entry. Heal its body once.
    {
        char_data original{}, body{};
        npc_only_data body_data{};
        init(original, true, 2, 1000);
        init(body, false, 1, 1000);
        body.only.npc = &body_data;
        body_data.orig_char = &original;
        original.only.pc->switched = &body;
        body.points.hit = 1;
        test_group party({&paladin, &original, &body});
        next_round();
        qualifying_hit(&monster, &paladin, 1000);
        assert(body.points.hit == 301 && original.points.hit == 1000);
    }

    // A holder changing body keeps its original group, spent HP and PvP classification.
    {
        char_data body{};
        npc_only_data body_data{};
        init(body, false, 1, 1500);
        body.only.npc = &body_data;
        body_data.orig_char = &paladin;
        test_group party({&paladin, &mates[0], &mates[1], &mates[2], &mates[3], &mates[4]});
        wound_all(); next_round();
        qualifying_hit(&enemy_pc, &paladin, 1000);
        paladin.only.pc->switched = &body;
        paladin.in_room = 2;
        qualifying_hit(&monster, &body, 1000);
        qualifying_hit(&monster, &body, 1000);
        assert(healed(5) == 900 && paladin.specials.holy_sacrifice_healed == 900);
        paladin.only.pc->switched = nullptr;
        paladin.in_room = 1;
        qualifying_hit(&monster, &paladin, 1000);
        assert(healed(5) == 900);
    }

    // The real vamp path applies suppression, and the ledger counts actual awarded HP.
    {
        test_group party({&paladin, &mates[0]});
        wound_all(); next_round();
        mates[0].specials.affected_by4 |= AFF4_CARRY_PLAGUE;
        qualifying_hit(&monster, &paladin, 1000);
        assert(healed(1) == 150 && paladin.specials.holy_sacrifice_healed == 150);
        mates[0].specials.affected_by4 &= ~AFF4_CARRY_PLAGUE;
    }

    // Each owner keeps its own budget: two paladins, or a Cavalier's mount, never share or
    // drain one another's round allowance.
    {
        test_group party({&paladin, &paladin2, &mates[0], &mates[1], &mates[2], &mates[3]});
        wound_all();
        next_round();
        for (int i = 0; i < 4; ++i) qualifying_hit(&monster, &paladin, 1000);
        assert(paladin.specials.holy_sacrifice_healed == 1800);
        qualifying_hit(&monster, &paladin2, 1000);
        assert(paladin2.specials.holy_sacrifice_healed == 900);
    }
    {
        test_group party({&mount, &mates[0], &mates[1]});
        wound_all();
        next_round();
        qualifying_hit(&monster, &mount, 1000); // 60% of the mount's 1,000 hp
        assert(healed(2) == 600 && mount.specials.holy_sacrifice_healed == 600);
    }

    // A tiny blow heals nothing and spends nothing.
    {
        test_group party({&paladin, &mates[0]});
        wound_all();
        next_round();
        qualifying_hit(&monster, &paladin, 1);
        assert(GET_HIT(&mates[0]) == 1 && paladin.specials.holy_sacrifice_healed == 0);
    }

    // The vamp ceiling: prime anti-paladins get +0.25, never past 2.5x; others unchanged.
    char_data ap{}, multi{}, warrior{}, npc_ap{};
    init(ap, true, 1, 1500);
    init(multi, true, 1, 1500);
    init(warrior, true, 1, 1500);
    init(npc_ap, false, 1, 1500);
    ap.player.m_class = CLASS_ANTIPALADIN;
    npc_ap.player.m_class = CLASS_ANTIPALADIN;
    multi.player.m_class = CLASS_WARRIOR;
    multi.player.secondary_class = CLASS_ANTIPALADIN;
    warrior.player.m_class = CLASS_WARRIOR;
    const struct {
        int power;
        double ap, other;
    } rows[] = {
        {50, 1.35, 1.10},   // below the floor: 1.10 + 0.25
        {135, 1.75, 1.50},  // 1.50 + 0.25
        {203, 2.50, 2.2556}, // 2.2556 + 0.25 just reaches the cap
        {300, 2.50, 2.50},  // was 3.50 for anti-paladins
    };
    for (const auto &row : rows) {
        for (char_data *ch : {&ap, &multi, &warrior, &npc_ap}) ch->curr_stats.Pow = row.power;
        assert(std::abs(VAMPPERCENT(&ap) - row.ap) < 0.01);
        assert(VAMPPERCENT(&ap) <= 2.50);
        assert(std::abs(VAMPPERCENT(&multi) - row.other) < 0.01);
        assert(std::abs(VAMPPERCENT(&warrior) - row.other) < 0.01);
        assert(std::abs(VAMPPERCENT(&npc_ap) - row.other) < 0.01);
    }
    // 1,500 hp at the Power cap: a 3,750 hp ceiling, down from 5,250.
    ap.curr_stats.Pow = 300;
    assert((int)(GET_MAX_HIT(&ap) * VAMPPERCENT(&ap)) == 3750);

    // Hit points already above a lowered ceiling are kept, not cut: vamp just adds nothing.
    ap.points.hit = 5000;
    assert(vamp(&ap, 500, GET_MAX_HIT(&ap) * VAMPPERCENT(&ap)) == 0 && GET_HIT(&ap) == 5000);

    for (const auto &key : unknown_properties) std::printf("unknown property %s\n", key.c_str());
    assert(unknown_properties.empty());
    std::puts("Holy Sacrifice budgets and anti-paladin vamp ceiling passed.");
}
"""

functions = [
    extract_function("paladins.c", "bool has_aura("),
    extract_function("paladins.c", "int aura_mod("),
    extract_function("fight.c", "int vamp("),
    extract_function("utility.c", "int IS_MORPH("),
    extract_function("utility.c", "float BOUNDEDF("),
    extract_function("utility.c", "int GET_PRIME_CLASS("),
    extract_function("fight.c", "static void holy_sacrifice_note_hit("),
    extract_function("fight.c", "static void holy_sacrifice_heal("),
]

output = ROOT / "bin/tests/holy-sacrifice"
output.mkdir(parents=True, exist_ok=True)
harness = output / "harness.cpp"
harness.write_text(PRELUDE + "\n".join(functions) + DRIVER, encoding="utf-8")
binary = output / "harness"
subprocess.run(
    ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
     "-I" + str(ROOT / "src"), str(harness), str(HARNESS_STUBS), "-o", str(binary)],
    check=True,
)
subprocess.run([str(binary)], check=True, timeout=30)
