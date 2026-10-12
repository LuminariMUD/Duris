#!/usr/bin/env python3
"""Blood Tithe: anti-paladin group damage fed by damage taken, and every guardrail on it.

Runs the real spell, charge, decay and bonus functions from paladins.c (with the real
grouped, opposite_racewar, num_group_members_in_room and has_aura) against the shipped
spell.bloodTithe.* properties, and checks how the spell is wired into the server.
"""

import re
import subprocess

from _paths import HARNESS_STUBS, ROOT, extract_function, source

# Shipped switched on, with the tuning described in the help entry.
SHIPPED = {
    "spell.bloodTithe.maxBonus": 0.12,
    "spell.bloodTithe.refGroupSize": 3.0,
    "spell.bloodTithe.falloffExponent": 0.5,
    "spell.bloodTithe.fullChargePerRound": 0.15,
    "spell.bloodTithe.perHitCap": 0.05,
    "spell.bloodTithe.decayPerRound": 0.25,
    "spell.bloodTithe.pvpMod": 0.5,
}
properties = {}
for line in (ROOT / "lib/duris.properties").read_text(encoding="utf-8").splitlines():
    if line.startswith("spell.bloodTithe."):
        key, value = line.split("=", 1)
        properties[key] = float(value)
assert properties == SHIPPED, properties

# Dark Knight and Demonic Rider learn it at circle 10; Violator and the base class do not.
skills = source("skills.c").read_text(encoding="utf-8")
registration = skills[skills.index('SPELL_CREATE_MSG("blood tithe"') :]
registration = registration[: registration.index("SPELL_CREATE", 1)]
assert "SPELL_BLOOD_TITHE" in registration and "TAR_SELF_ONLY" in registration
assert re.findall(r"(?:SPEC_)?SPELL_ADD\([^)]*\)", registration) == [
    "SPEC_SPELL_ADD(CLASS_ANTIPALADIN, 10, SPEC_DARKKNIGHT)",
    "SPEC_SPELL_ADD(CLASS_ANTIPALADIN, 10, SPEC_DEMONIC)",
], registration

# Every landed hit charges the meter, ahead of check_vamp's early returns.
raw_damage = extract_function("fight.c", "int raw_damage(")
charge_at = raw_damage.index("blood_tithe_charge(ch, victim, dam);")
assert charge_at < raw_damage.index("check_vamp(ch, victim, dam, flags);", charge_at)
assert "if ((ch != victim))" in raw_damage[charge_at - 160 : charge_at]

# The bonus is a raw-damage modifier, so it covers weapons and spells alike.
dam_mods = source("dam_mods.c").read_text(encoding="utf-8")
raw_table = dam_mods[dam_mods.index("dam_mod_predicate raw_damage_modifiers[]") :]
bonus_at = raw_table.index("blood_tithe_damage_bonus(caster, victim)")
assert "!(flags & PHSDAM_NOREDUCE)" in raw_table[bonus_at - 120 : bonus_at]
assert "dam_mod_type::More" in raw_table[bonus_at : bonus_at + 120]

# A tithe that survives logout keeps decaying after login.
schedule = extract_function("nanny.c", "void schedule_pc_events(")
assert re.search(
    r"if \(affected_by_spell\(ch, SPELL_BLOOD_TITHE\)\)\s*"
    r"add_event\(event_blood_tithe, PULSE_VIOLENCE, ch",
    schedule,
)

# The score command shows the tithe, and the help explains it.
score = extract_function("actinf.c", "void do_score(")
assert "blood_tithe_bonus(ch)" in score and "silenced by Battle Lust" in score
for help_file in ("help/duris_help.hlp", "help/duris_help_parsed.hlp"):
    assert "\nBlood Tithe - Last Edited:" in (ROOT / help_file).read_text(encoding="utf-8")
assert '"BLOOD TITHE" (Spell)' in (ROOT / "lib/information/help_index").read_text(
    encoding="utf-8"
)

property_rows = ",\n".join(f'    {{"{key}", {value!r}}}' for key, value in SHIPPED.items())

PRELUDE = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "magic/spells.h"
#include "classes/paladins.h"
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

affected_type *get_spell_from_char(P_char ch, int spell, void *, int) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == spell) return af;
    return nullptr;
}
bool affected_by_spell(P_char ch, int spell) { return get_spell_from_char(ch, spell, nullptr, 0); }
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af);
    copy->next = ch->affected;
    ch->affected = copy;
    return copy;
}
static void clear(P_char ch) {
    while (auto *af = ch->affected) {
        ch->affected = af->next;
        delete af;
    }
}

static int devotion = 0;
int GET_CHAR_SKILL_P(P_char, int skill) { return skill == SKILL_DEVOTION ? devotion : 0; }

static std::map<P_char, P_char> masters;
P_char get_linked_char(P_char ch, ush_int type) {
    auto it = masters.find(ch);
    return type == LNK_PET && it != masters.end() ? it->second : nullptr;
}

static int scheduled = 0, disarmed = 0, sends = 0, last_delay = 0;
static event_func last_event = nullptr;
nevent_schedule_result add_event(event_func func, int delay, P_char, P_char, P_obj, int,
                                 const void *, int) {
    ++scheduled;
    last_event = func;
    last_delay = delay;
    return {};
}
void disarm_char_nevents(P_char, event_func_type) { ++disarmed; }
void send_to_char(const char *, P_char) { ++sends; }
"""

DRIVER = r"""
static void init(char_data &ch, bool pc, int room, int racewar) {
    ch.specials.position = STAT_NORMAL;
    if (!pc) ch.specials.act |= ACT_ISNPC;
    ch.in_room = room;
    ch.player.racewar = racewar;
    ch.points.max_hit = 1000;
}
static void aura(P_char ch, int type) {
    affected_type af{};
    af.type = type;
    affect_to_char(ch, &af);
}
static int malice(P_char ch) { return get_spell_from_char(ch, SPELL_BLOOD_TITHE)->modifier; }
static void set_malice(P_char ch, int value) {
    get_spell_from_char(ch, SPELL_BLOOD_TITHE)->modifier = value;
}
static bool about(double actual, double expected) { return std::fabs(actual - expected) < 1e-5; }

// Group head shared by every member, as group.c builds it.
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

// One round of combat: hits of the given size land, then the round's decay runs.
static void combat_round(P_char ap, P_char enemy, int hits, double each) {
    for (int i = 0; i < hits; ++i) blood_tithe_charge(enemy, ap, each);
    event_blood_tithe(ap, nullptr, nullptr, nullptr);
}

static char_data ap, ap2, mate, far_mate, stranger, pet, enemy, enemy_pc, ally_pc, other_pet,
    hireling;
static char_data crowd[14];

int main() {
    init(ap, true, 1, RACEWAR_EVIL);
    init(ap2, true, 1, RACEWAR_EVIL);
    init(mate, true, 1, RACEWAR_EVIL);
    init(far_mate, true, 2, RACEWAR_EVIL);
    init(stranger, true, 1, RACEWAR_EVIL);
    init(pet, false, 1, RACEWAR_EVIL);
    init(enemy, false, 1, 0);
    init(enemy_pc, true, 1, RACEWAR_GOOD);
    init(ally_pc, true, 1, RACEWAR_EVIL);
    init(other_pet, false, 1, 0);
    init(hireling, false, 1, 0);
    for (auto &ch : crowd) init(ch, true, 1, RACEWAR_EVIL);

    // Casting: 15 ticks plus 1 per 10 Devotion, an empty meter and one decay event.
    devotion = 50;
    spell_blood_tithe(56, &ap, nullptr, 0, &ap, nullptr);
    affected_type *tithe = get_spell_from_char(&ap, SPELL_BLOOD_TITHE);
    assert(tithe && tithe->duration == 20 && tithe->modifier == 0);
    assert(scheduled == 1 && disarmed == 1 && last_event == event_blood_tithe);
    assert(last_delay == PULSE_VIOLENCE);
    spell_blood_tithe(56, &ap, nullptr, 0, &ap, nullptr);
    assert(sends == 1 && scheduled == 1 && tithe->next == nullptr);

    // Enemy hits charge it, each counting for at most 5% of max hp.
    blood_tithe_charge(&enemy, &ap, 30);
    assert(malice(&ap) == 30);
    blood_tithe_charge(&enemy, &ap, 400);
    assert(malice(&ap) == 80);
    blood_tithe_charge(&enemy, &ap, 0);
    blood_tithe_charge(&enemy, &ap, -40);
    assert(malice(&ap) == 80);

    // Nothing friendly feeds it: self, groupmates (players or monsters), any pet of the
    // group, same-side players.
    {
        test_group party({&ap, &mate, &hireling});
        blood_tithe_charge(&ap, &ap, 50);
        blood_tithe_charge(&mate, &ap, 50);
        blood_tithe_charge(&hireling, &ap, 50);
        masters[&pet] = &ap;
        blood_tithe_charge(&pet, &ap, 50);
        masters[&pet] = &mate;
        blood_tithe_charge(&pet, &ap, 50);
        blood_tithe_charge(&ally_pc, &ap, 50);
        masters[&other_pet] = &ally_pc;
        blood_tithe_charge(&other_pet, &ap, 50);
        assert(malice(&ap) == 80);

        // Enemy players and their pets do feed it.
        blood_tithe_charge(&enemy_pc, &ap, 50);
        masters[&other_pet] = &enemy_pc;
        blood_tithe_charge(&other_pet, &ap, 50);
        assert(malice(&ap) == 180);
        masters.clear();
    }

    // Someone without the spell is untouched.
    blood_tithe_charge(&enemy, &mate, 50);
    assert(mate.affected == nullptr);

    // The meter caps at the malice that sustains full charge: 15% / 25% of max hp.
    for (int i = 0; i < 40; ++i) blood_tithe_charge(&enemy, &ap, 50);
    assert(malice(&ap) == 600);

    // Each round a quarter fades, and the event keeps itself going.
    scheduled = 0;
    event_blood_tithe(&ap, nullptr, nullptr, nullptr);
    assert(malice(&ap) == 450 && scheduled == 1 && last_event == event_blood_tithe);
    event_blood_tithe(&mate, nullptr, nullptr, nullptr);
    assert(scheduled == 1);

    // Charge follows how hard the caster is hit (measured just after the round's hits).
    // Solo, a lone groupmate gets the full 12% times the charge.
    {
        test_group party({&ap, &mate});
        const struct {
            int hits;
            double each, low, high;
        } intake[] = {
            {4, 50, 1.0, 1.0},       // 20% of max hp a round: full
            {3, 50, 0.99, 1.0},      // 15%: full, less integer rounding
            {2, 50, 0.64, 0.667},    // 10%: two thirds
            {1, 50, 0.31, 0.334},    // 5%: a third
            {10, 1, 0.05, 0.067},    // trash: 1% a round barely registers
            {1, 500, 0.31, 0.334},   // one huge hit a round counts as 5%
        };
        for (auto &row : intake) {
            set_malice(&ap, 0);
            for (int r = 0; r < 60; ++r) combat_round(&ap, &enemy, row.hits, row.each);
            for (int i = 0; i < row.hits; ++i) blood_tithe_charge(&enemy, &ap, row.each);
            double charge = blood_tithe_bonus(&ap) / 0.12;
            assert(charge >= row.low - 1e-4 && charge <= row.high + 1e-4);
        }

        // Once the hits stop it halves in under three rounds.
        set_malice(&ap, 600);
        for (int r = 0; r < 3; ++r) event_blood_tithe(&ap, nullptr, nullptr, nullptr);
        assert(blood_tithe_bonus(&ap) < 0.06 && blood_tithe_bonus(&ap) > 0.04);
    }

    // Group size: full 12% up to three groupmates, then 12% x sqrt(3 / groupmates).
    set_malice(&ap, 600);
    for (int size : {1, 2, 3, 5, 8, 14}) {
        std::vector<P_char> members{&ap};
        for (int i = 0; i < size; ++i) members.push_back(&crowd[i]);
        // Pets, NPCs and groupmates elsewhere neither count nor dilute it.
        members.push_back(&pet);
        members.push_back(&far_mate);
        test_group party(members);
        double expected = 0.12 * std::sqrt(3.0 / std::max(3, size));
        assert(about(blood_tithe_bonus(&ap), expected));
        assert(about(blood_tithe_damage_bonus(&crowd[0], &enemy), expected));
    }

    {
        test_group party({&ap, &mate, &far_mate, &pet});

        // A groupmate in the room hits harder; against players it is halved.
        assert(about(blood_tithe_damage_bonus(&mate, &enemy), 0.12));
        assert(about(blood_tithe_damage_bonus(&mate, &enemy_pc), 0.06));

        // The caster, groupmates elsewhere, pets and outsiders get nothing.
        assert(blood_tithe_damage_bonus(&ap, &enemy) == 0);
        assert(blood_tithe_damage_bonus(&far_mate, &enemy) == 0);
        assert(blood_tithe_damage_bonus(&pet, &enemy) == 0);
        assert(blood_tithe_damage_bonus(&stranger, &enemy) == 0);

        // Half the malice, half the bonus.
        set_malice(&ap, 300);
        assert(about(blood_tithe_damage_bonus(&mate, &enemy), 0.06));
        set_malice(&ap, 600);

        // Battle Lust silences it, so the two never stack.
        aura(&mate, AURA_BATTLELUST);
        assert(blood_tithe_damage_bonus(&mate, &enemy) == 0);
        clear(&mate);
        aura(&mate, AURA_PROTECTION);
        assert(about(blood_tithe_damage_bonus(&mate, &enemy), 0.12));
        clear(&mate);

        // A dead caster or a monster with the spell grants nothing.
        ap.specials.position = STAT_DEAD;
        assert(blood_tithe_damage_bonus(&mate, &enemy) == 0);
        ap.specials.position = STAT_NORMAL;
        ap.specials.act |= ACT_ISNPC;
        assert(blood_tithe_damage_bonus(&mate, &enemy) == 0);
        ap.specials.act &= ~ACT_ISNPC;
    }

    // Two tithes: groupmates take the stronger one, never the sum, and the two
    // anti-paladins gain nothing from each other.
    {
        test_group party({&ap, &ap2, &mate});
        spell_blood_tithe(56, &ap2, nullptr, 0, &ap2, nullptr);
        set_malice(&ap2, 300);
        assert(about(blood_tithe_damage_bonus(&mate, &enemy), 0.12));
        set_malice(&ap, 150);
        assert(about(blood_tithe_damage_bonus(&mate, &enemy), 0.06));
        assert(blood_tithe_damage_bonus(&ap, &enemy) == 0);
        assert(blood_tithe_damage_bonus(&ap2, &enemy) == 0);
    }

    // Without a group there is no one to empower.
    assert(blood_tithe_damage_bonus(&mate, &enemy) == 0);

    for (const auto &key : unknown_properties) std::printf("unknown property %s\n", key.c_str());
    assert(unknown_properties.empty());

    for (char_data *ch : {&ap, &ap2, &mate}) clear(ch);
    std::puts("Blood Tithe charge, decay, scaling and guardrails passed.");
}
"""

functions = [extract_function("paladins.c", signature) for signature in (
    "bool has_aura(",
    "static double blood_tithe_full_malice(",
    "void spell_blood_tithe(",
    "void event_blood_tithe(",
    "void blood_tithe_charge(",
    "double blood_tithe_bonus(",
    "double blood_tithe_damage_bonus(",
)]
functions += [
    extract_function("fight.c", "bool opposite_racewar("),
    extract_function("utility.c", "bool grouped("),
    extract_function("group.c", "int num_group_members_in_room("),
]

output = ROOT / "bin/tests/blood-tithe"
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
