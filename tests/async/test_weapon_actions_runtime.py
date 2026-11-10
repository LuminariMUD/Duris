#!/usr/bin/env python3
"""Selected weapon procs against the real item runtime and scheduler, ASan/UBSan.

Compile the actual Avernus/packed/random/wind callbacks, not copies of their routing.
Only world presentation, permission, RNG and effect endpoints are doubled here.
Artifact persistence has its own game/worker/repository tests; this fixture uses
the real resource arithmetic at the debit boundary and checks its call ordering.
"""
import ast
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import HARNESS_STUBS

ROOT = Path(__file__).resolve().parents[2]


def literal(path, name):
    tree = ast.parse(path.read_text())
    return next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


def function(path, signature):
    text = path.read_text()
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


platform = literal(ROOT / "tests/async/test_nevent_scheduler_runtime.py", "HARNESS")
platform = platform.split("struct record_payload\n", 1)[0]
platform = platform.replace("DEFINE_LABEL_CALLBACK(event_item_action_active)", "")
platform = platform.replace("test_world[1]", "test_world[2]").replace("top_of_world = 0", "top_of_world = 1")
platform = platform.replace("int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }",
                            function(ROOT / "src/core/utility.c", "int GET_CLASS(P_char ch, uint m_class)"))
fixture = literal(ROOT / "tests/async/test_item_actions_runtime.py", "HARNESS")
fixture = fixture.replace("int main() {", "void foundation_regression_main() {")
fixture = fixture.replace("// INSERT_PRODUCTION_ABORT",
                          function(ROOT / "src/net/sparser.c", "void do_abort(P_char ch,"))
callbacks = "\n".join([
    function(ROOT / "src/combat/fight.c", "static attack_continuation capture_monk_glove_proc("),
    function(ROOT / "src/combat/fight.c", "static void dispatch_monk_glove_proc("),
    function(ROOT / "src/combat/fight.c", "bool monk_superhit(P_char ch, P_char victim, int *damAccumulator)\n"),
    function(ROOT / "src/combat/training_dummy.c", "bool training_dummy_is(P_char ch)"),
    function(ROOT / "src/world/handler.c", "bool isname(const char *str, const char *namelist)"),
    function(ROOT / "src/cmd/interp.c", "bool special(P_char ch, int cmd, char *arg)"),
    function(ROOT / "src/net/comm.c", "void act_trio("),
    function(ROOT / "src/specs/specs.object.c", "P_char melee_proc_target("),
    function(ROOT / "src/specs/specs.underworld.c", "void resolve_avernus_drain("),
    function(ROOT / "src/specs/specs.underworld.c", "int avernus("),
    function(ROOT / "src/combat/fight.c", "static void cast_packed_weapon_spell("),
    function(ROOT / "src/combat/fight.c", "bool weapon_proc("),
    function(ROOT / "src/item/random_equipment.c", "int random_eq_proc("),
    function(ROOT / "src/cmd/actoff.c", "bool is_in_safe("),
    function(ROOT / "src/item/native_artifact_actions.c", "bool native_artifact_hostile("),
    function(ROOT / "src/specs/specs.underworld.c", "int lightning("),
    function(ROOT / "src/specs/specs.underworld.c", "int dagger_of_wind("),
    function(ROOT / "src/mob/mobact.c", "int empty_slot_for_weapon(P_char ch)\n"),
    function(ROOT / "src/mob/mobact.c", "void try_wield_weapon(P_char ch)\n"),
])

DOUBLES = r'''
#include "item/random_equipment.h"
#include "combat/attack_continuation.c"
#include "item/weapon_actions.c"
#include "item/native_artifact_actions.h"
#include "item/item_value.h"
#include "world/buildings.h"
bool native_artifact_owns(int) { return false; }
#include "item/artifact_mana_model.c"
#include "combat/damage.h"
#include <deque>
Skill skills[MAX_SKILLS] = {};
random_spells spells_data[61] = {};
struct message { std::string text; int audience; };
static std::vector<message> messages;
static std::vector<std::pair<int, int>> rolls;
static std::deque<int> choices;
struct effect_call {
    int id, power, type; uint64_t target; uint flags;
    bool operator==(const effect_call &) const = default;
};
static std::vector<effect_call> effects;
static bool can_fight = true, storage_ready = true;
static int stone_calls = 0, hum_calls = 0, debit_calls = 0, mutation = 0;
static int affected_spell = 0;
static int base_result = DAM_NONEDEAD, base_mutation = 0, native_calls = 0;
static P_obj proc_source;
bool SanityCheck(P_char, const char *) { return true; }
bool can_hit_target(P_char, P_char) { return true; }
int on_front_line(P_char) { return true; }
int MonkDamage(P_char) { return 10; }
int melee_damage(P_char actor, P_char target, double, uint, damage_messages *, int *) {
    if (base_mutation == 1) remove_source(proc_source, actor);
    if (base_mutation == 2) depart(target);
    if (base_mutation == 3) actor->equipment[WEAR_HANDS] = nullptr;
    return base_result;
}
int glove_native(P_obj obj, P_char actor, int cmd, char *arg) {
    assert(cmd == CMD_MELEE_HIT && melee_proc_target(obj, actor, cmd, arg));
    ++native_calls;
    return FALSE; // Callback status must not change hit success.
}
static P_char protected_player = nullptr;
static zone_data test_zones[1]{};
zone_data *zone_table = test_zones;
static artifact_mana_profile mana_profile;
static std::map<uint64_t, artifact_mana_record> reserves;
static std::map<uint64_t, uint64_t> tokens;
static time_t wall_time = 1000;
time_t selected_test_time(time_t *) { return wall_time; }
void send_to_char(const char *text, P_char) { messages.push_back({text, -1}); }
void send_to_room(const char *text, int) { messages.push_back({text, -2}); }
void act(const char *text, int, P_char, P_obj, void *, int audience) {
    messages.push_back({text, audience});
}
int number(int low, int high) {
    rolls.emplace_back(low, high);
    assert(!choices.empty());
    const int result = choices.front(); choices.pop_front();
    assert(result >= low && result <= high); return result;
}
int CanDoFightMove(P_char, P_char) { return can_fight; }
int BOUNDED(int low, int value, int high) { return std::clamp(value, low, high); }
float BOUNDEDF(float low, float value, float high) { return std::clamp(value, low, high); }
float get_property(const char *key, double fallback) { return get_property(key, fallback, false); }
int GET_PRIME_CLASS(P_char, uint) { return 0; }
bool affected_by_spell(P_char, int spell) { return spell == affected_spell; }
int is_char_in_room(const P_char ch, int room) { return ch && ch->in_room == room; }
void hummer(P_obj) { ++hum_calls; }
bool should_not_kill(P_char, P_char target) { return target == protected_player; }
int GET_ALT_SIZE(P_char target) { return target->player.size; }
void stop_fighting(P_char target) { GET_OPPONENT(target) = nullptr; }
int wear(P_char actor, P_obj source, int slot, bool) {
    assert(slot == 12 && !actor->equipment[WIELD]);
    actor->carrying = source->next_content; source->next_content = nullptr;
    actor->equipment[WIELD] = source; source->loc_p = LOC_WORN; source->loc.wearing = actor;
    return 1;
}
void spell_stone_skin(int, P_char, char *, int, P_char, P_obj) { ++stone_calls; }
int vamp(P_char ch, double amount, double cap, bool) {
    effects.push_back({-1, static_cast<int>(amount), static_cast<int>(cap), ch->runtime_id, 0});
    return 0;
}
int spell_damage(P_char, P_char victim, double damage, int type, uint flags,
                 damage_messages *, int *) {
    effects.push_back({-2, static_cast<int>(damage), type, victim->runtime_id, flags}); return 0;
}
void spell_endpoint(int id, int power, int type, P_char target) {
    effects.push_back({id, power, type, target->runtime_id, 0});
    if (mutation == 1) depart(target);
    if (mutation == 2) remove_character(target);
    if (mutation == 3) SET_POS(target, STAT_DEAD);
    if (mutation == 4) remove_source(proc_source, proc_source->loc.wearing);
    if (mutation == 5) remove_character(character_list);
    if (mutation == 6) ++target->specials.z_cord;
}
void spell_cyclone(int power, P_char, char *, int type, P_char target, P_obj) {
    spell_endpoint(SPELL_CYCLONE, power, type, target);
}
void spell_lightning_bolt(int power, P_char, char *, int type, P_char target, P_obj) {
    spell_endpoint(SPELL_LIGHTNING_BOLT, power, type, target);
}
void spell_deflect(int power, P_char, char *, int type, P_char target, P_obj) {
    spell_endpoint(SPELL_DEFLECT, power, type, target);
}
void spell_one(int power, P_char, char *, int type, P_char target, P_obj) {
    spell_endpoint(1, power, type, target);
}
void spell_two(int power, P_char, char *, int type, P_char target, P_obj) {
    spell_endpoint(2, power, type, target);
}
void spell_three(int power, P_char, char *, int type, P_char target, P_obj) {
    spell_endpoint(3, power, type, target);
}
bool artifact_mana_publish(int, const artifact_mana_profile &profile) {
    mana_profile = profile; return artifact_mana_valid(profile);
}
bool artifact_mana_debit(P_obj source, uint64_t cost, bool passive, uint64_t token) {
    ++debit_calls;
    assert(item_actions_pending() > 0); // Scheduler owns the action before payment.
    if (!storage_ready || token <= tokens[source->obj_uid]) return false;
    auto found = reserves.find(source->obj_uid);
    if (found == reserves.end()) return false;
    if (!artifact_mana_spend(found->second, mana_profile, wall_time, cost, passive)) return false;
    tokens[source->obj_uid] = token; return true;
}
#define time selected_test_time
// INSERT_CALLBACKS
#undef time

struct weapon_scene : scene {
    explicit weapon_scene(const char *category = "avernus", bool enabled = true) {
        bindings.clear(); messages.clear(); effects.clear(); rolls.clear(); choices.clear();
        reserves.clear(); tokens.clear(); can_fight = storage_ready = true;
        debit_calls = mutation = affected_spell = stone_calls = hum_calls = 0;
        obj_index[0].virtual_number = 19730;
        obj_index[0].func.obj = avernus;
        GET_HIT(target) = 170; GET_MAX_HIT(actor) = 1000;
        properties[std::string("itemActions.") + category + ".enabled"] = enabled;
        skills[1].spell_pointer = spell_one; skills[1].targets = TAR_AGGRO;
        skills[2].spell_pointer = spell_two; skills[2].targets = 0;
        skills[3].spell_pointer = spell_three; skills[3].targets = TAR_AGGRO;
        spells_data[1].spell = 1; spells_data[1].self_only = false;
        spells_data[2].spell = 2; spells_data[2].self_only = true;
    }
    void paid(int reserve = 60) {
        properties["itemActions.weapon.19730.manaCost"] = 30;
        properties["itemActions.weapon.19730.manaCapacity"] = 100;
        mana_profile = {19730, 1, 100, 0, 0};
        auto row = artifact_mana_empty(source->obj_uid, mana_profile, wall_time);
        row.reserve = reserve; reserves[source->obj_uid] = row;
    }
    bool hit(int roll = 0) { choices.push_back(roll); return weapon_proc(source, actor, target); }
    void packed(bool random = false) {
        source->type=ITEM_WEAPON; source->wear_flags=ITEM_TAKE|ITEM_WIELD;
        obj_index[0].func.obj = nullptr;
        source->value[5] = 3002001 + (random ? 1000000000 : 0);
        source->value[6] = 57; source->value[7] = 25;
    }
    void named() {
        obj_index[0].func.obj = random_eq_proc;
        source->value[6] = 999; source->value[7] = 1;
        source->wear_flags = ITEM_WIELD; GET_OPPONENT(actor) = target;
    }
};
static void audience_count(const char *part, size_t expected) {
    for (int audience : {TO_CHAR, TO_VICT, TO_NOTVICT}) {
        size_t count = 0;
        for (auto &m : messages)
            if (m.audience == audience && m.text.find(part) != std::string::npos) ++count;
        assert(count == expected);
    }
}

static void avernus_parity() {
    for (int hitpoints : {170, 500, -8, -9}) {
        for (bool enabled : {false, true}) {
            weapon_scene s("avernus", enabled);
            GET_HIT(s.target) = hitpoints;
            assert(s.hit());
            assert((rolls == std::vector<std::pair<int,int>>{{0,24}}));
            if (enabled) {
                assert(effects.empty()); audience_count("begins", 1);
                advance(20, false); assert(effects.empty()); audience_count("intensifies", 0);
                advance(5); assert(effects.empty()); audience_count("intensifies", 1);
                GET_HIT(s.target) = 1000; GET_MAX_HIT(s.actor) = 2;
                GET_OPPONENT(s.actor) = s.actor; // Completion cannot retarget/recompute.
                advance(8);
            }
            const int damage = std::clamp(hitpoints + 9, 0, 200);
            assert(effects.size() == 2);
            assert((effects[0] == effect_call{-1, damage / 2, 1100, s.actor->runtime_id, 0}));
            assert((effects[1] == effect_call{-2, damage, SPLDAM_NEGATIVE, s.target->runtime_id,
                SPLDAM_NODEFLECT | SPLDAM_NOSHRUG | PHSDAM_NOREDUCE}));
            assert(choices.empty() && rolls.size() == 1);
        }
    }
    weapon_scene s;
    assert(!s.hit(24) && effects.empty() && !item_actions_pending());
    assert(avernus(s.source, nullptr, CMD_SET_PERIODIC, nullptr));
    assert(avernus(s.source, nullptr, CMD_PERIODIC, nullptr));
    assert(hum_calls == 1);
    char stone[] = "stone";
    assert(avernus(s.source, s.actor, CMD_SAY, stone));
    assert(stone_calls == 1 && s.source->timer[0] == wall_time);
    choices.push_back(0);
    // Same direct callback invocation used by do_backstab, bypassing weapon_proc.
    assert(obj_index[0].func.obj(s.source, s.actor, CMD_MELEE_HIT, reinterpret_cast<char *>(s.target)));
    assert(effects.empty()); advance(); assert(effects.size() == 2);
}

static void cancellation_and_payment() {
    for (int transition = 0; transition < 8; ++transition) {
        weapon_scene s; s.paid();
        assert(s.hit() && effects.empty());
        assert(debit_calls == 1 && reserves[100].reserve == 30);
        assert(s.hit()); assert(debit_calls == 1); // Busy selection never falls back.
        switch (transition) {
        case 0: depart(s.target); s.target->in_room = 0; break;
        case 1: depart(s.actor); s.actor->in_room = 0; break;
        case 2: SET_POS(s.target, STAT_DEAD); break;
        case 3: remove_character(s.target); break;
        case 4: remove_source(s.source, s.actor); break;
        case 5: can_fight = false; break;
        case 6: properties["itemActions.weapon.19730.enabled"] = 0; update_weapon_action_properties(); break;
        case 7: properties["itemActions.enabled"] = 0; update_item_action_properties(); break;
        }
        advance();
        assert(effects.empty() && !item_actions_pending() && reserves[100].reserve == 30);
        assert(!messages.empty());
        bool fizzle = false;
        for (const auto &m : messages) fizzle |= m.text.find("fades") != std::string::npos;
        assert(fizzle);
    }
    {
        weapon_scene s; s.paid(30);
        const auto sequence = ne_event_sequence; ne_event_sequence = ULLONG_MAX;
        assert(s.hit()); ne_event_sequence = sequence;
        assert(debit_calls == 0 && reserves[100].reserve == 30 && effects.empty());
        assert(s.hit()); advance(); assert(effects.size() == 2 && reserves[100].reserve == 0);
        assert(s.hit()); advance(); assert(effects.size() == 2 && debit_calls == 2);
        properties["itemActions.avernus.enabled"] = 0; update_weapon_action_properties();
        assert(s.hit() && effects.size() == 4); // Explicit rollback restores legacy.
    }
    {
        weapon_scene s; s.paid(); storage_ready = false;
        assert(s.hit()); advance();
        assert(effects.empty() && messages.empty() && reserves[100].reserve == 60);
    }
    {
        weapon_scene s;
        SET_BIT(s.actor->specials.affected_by2, AFF2_CASTING);
        const auto wait_changes = unrelated_wait_changes;
        assert(s.hit());
        auto other = new obj_data{};
        other->R_num = s.source->R_num; other->loc_p = LOC_WORN; other->loc.wearing = s.actor;
        other->obj_uid = 101; other->next = object_list;
        object_list = other; s.actor->equipment[WIELD2] = other;
        choices.push_back(0); assert(weapon_proc(other, s.actor, s.target));
        assert(item_actions_pending() == 2 && !item_action_active(s.actor));
        advance();
        assert(effects.size() == 4 && IS_AFFECTED2(s.actor, AFF2_CASTING));
        assert(wait_changes == unrelated_wait_changes);
    }
}

static void monk_gloves() {
    // Exercise the actual capture/terminal dispatch and actual PvP superhit.
    for (bool enabled : {false, true}) {
        for (int change = 0; change < 7; ++change) {
            weapon_scene s("weapons", enabled); s.packed();
            s.actor->player.m_class = CLASS_MONK;
            s.actor->equipment[WIELD] = nullptr;
            s.actor->equipment[WEAR_HANDS] = s.source;
            s.source->type = ITEM_ARMOR; s.source->wear_flags = ITEM_WEAR_HANDS;
            s.source->extra2_flags = ITEM2_MONK_PROC; proc_source = s.source;
            choices = {0};
            const auto opportunity = capture_monk_glove_proc(s.actor, s.target, nullptr);
            dispatch_monk_glove_proc(opportunity);
            if (enabled) {
                assert(effects.empty() && item_actions_pending() == 1);
                choices = {0}; dispatch_monk_glove_proc(opportunity);
                assert(effects.empty() && item_actions_pending() == 1);
                switch (change) {
                case 1: s.actor->player.m_class = CLASS_WARRIOR; break;
                case 2: s.source->extra2_flags = 0; break;
                case 3: s.actor->equipment[WEAR_HANDS] = nullptr;
                        s.actor->equipment[WEAR_HANDS_2] = s.source; break;
                case 4: remove_source(s.source, s.actor); break;
                case 5: depart(s.target); break;
                case 6: {
                    auto *weapon = new obj_data{}; weapon->obj_uid = 101;
                    weapon->loc_p = LOC_WORN; weapon->loc.wearing = s.actor;
                    weapon->next = object_list; object_list = weapon;
                    s.actor->equipment[WIELD] = weapon; break;
                }
                }
                advance();
                assert(effects.size() == (change == 0 || change == 6 ? 3 : 0));
            } else assert(effects.size() == 3);
        }
    }
    for (int admission = 0; admission < 9; ++admission) {
        weapon_scene s("weapons", false); s.packed();
        s.actor->player.m_class = CLASS_MONK;
        s.actor->equipment[WIELD] = nullptr; s.actor->equipment[WEAR_HANDS] = s.source;
        s.source->type = ITEM_WORN; s.source->wear_flags = ITEM_WEAR_HANDS;
        s.source->extra2_flags = ITEM2_MONK_PROC;
        switch (admission) {
        case 1: s.actor->player.m_class = CLASS_WARRIOR; break;
        case 2: s.actor->specials.act = ACT_ISNPC; break;
        case 3: s.source->extra2_flags = 0; break;
        case 4: s.actor->equipment[WEAR_HANDS] = nullptr; break;
        case 5: s.source->type = ITEM_LIGHT; break;
        case 6: s.source->wear_flags = ITEM_WEAR_BODY; break;
        case 7: s.actor->player.m_class = CLASS_WARRIOR;
                s.actor->player.secondary_class = CLASS_MONK; break;
        case 8: s.actor->equipment[WEAR_HANDS_2] = s.source; break;
        }
        choices = {0};
        dispatch_monk_glove_proc(capture_monk_glove_proc(s.actor, s.target, nullptr));
        assert(effects.size() == (admission == 0 || admission >= 7 ? 3 : 0));
        effects.clear();
        dispatch_monk_glove_proc(capture_monk_glove_proc(s.actor, s.target, s.source));
        assert(effects.empty());
    }
    for (int spec = 0; spec <= 4; ++spec) for (int change = 0; change < 5; ++change) {
        weapon_scene s("weapons", false);
        s.actor->player.m_class = CLASS_MONK;
        s.actor->equipment[WIELD] = nullptr; s.actor->equipment[WEAR_HANDS] = s.source;
        s.source->type = ITEM_ARMOR; s.source->wear_flags = ITEM_WEAR_HANDS;
        s.source->extra2_flags = ITEM2_MONK_PROC;
        s.actor->player.spec = spec < 4 ? spec : 0;
        if (spec == 4) {
            s.actor->player.m_class = CLASS_WARRIOR;
            s.actor->player.secondary_class = CLASS_MONK;
        }
        obj_index[0].func.obj = glove_native; native_calls = 0; proc_source = s.source;
        base_mutation = change < 4 ? change : 0;
        base_result = change == 4 ? DAM_VICTDEAD : DAM_NONEDEAD;
        assert(monk_superhit(s.actor, s.target, nullptr));
        assert(native_calls == (change == 0 ? 1 : 0));
    }
    base_mutation = 0; base_result = DAM_NONEDEAD;
    for (int packed : {-1, 1000, 1000000000, 999, 3000001}) {
        weapon_scene s("weapons", false); s.packed();
        s.source->type = ITEM_ARMOR; s.source->wear_flags = ITEM_WEAR_HANDS;
        s.source->extra2_flags = ITEM2_MONK_PROC; s.source->value[5] = packed;
        assert(!weapon_proc(s.source, s.actor, s.target) && rolls.empty());
    }
    for (int bad = 0; bad < 2; ++bad) {
        weapon_scene s("weapons", false); s.packed();
        s.source->type = ITEM_ARMOR; s.source->wear_flags = ITEM_WEAR_HANDS;
        s.source->extra2_flags = ITEM2_MONK_PROC; s.source->value[6 + bad] = 0;
        obj_index[0].func.obj = glove_native; native_calls = 0;
        assert(!weapon_proc(s.source, s.actor, s.target) && native_calls == 0 && rolls.empty());
    }
    for (bool enabled : {false, true}) for (int change = 1; change <= 6; ++change) {
        weapon_scene s("weapons", enabled); s.packed(); mutation = change;
        proc_source = s.source;
        assert(s.hit()); if (enabled) advance();
        // Scheduled magic keeps existing weapon-action reach rules; immediate
        // bundles additionally enforce the captured melee height between spells.
        assert(effects.size() == (enabled && change == 6 ? 3 : 1));
    }
}

static unsigned int valued_packed_mask(P_obj object) {
    item_value_input input; input.type=object->type; input.wear_flags=object->wear_flags;
    input.extra2_flags=object->extra2_flags;
    for(int i=0;i<NUMB_OBJ_VALS;++i) input.value[i]=object->value[i];
    unsigned int callable=0;
    for(int packed=object->value[5]%1000000000,i=0;i<3;++i,packed/=1000) {
        int spell=packed%1000;
        if(spell>0 && spell<MAX_SKILLS && skills[spell].spell_pointer) callable |= 1u<<i;
    }
    return item_value_packed_cast_mask(input,callable);
}

static void packed_parity() {
    for (bool enabled : {false, true}) {
        weapon_scene s("weapons", enabled); s.packed();
        assert(s.hit());
        if (enabled) { assert(effects.empty()); advance(); }
        assert((effects == std::vector<effect_call>{
            {3,57,SPELL_TYPE_SPELL,s.target->runtime_id,0},
            {2,57,SPELL_TYPE_SPELL,s.actor->runtime_id,0},
            {1,57,SPELL_TYPE_SPELL,s.target->runtime_id,0}}));
        assert(rolls.size() == 1 && choices.empty());
    }
    for (bool enabled : {false, true}) for (int count : {2, 3})
    for (int choice = 0; choice < count; ++choice) {
        weapon_scene s("weapons", enabled); s.packed(true);
        if (count == 2) s.source->value[5] = 1000002001;
        choices = {0, choice}; assert(weapon_proc(s.source, s.actor, s.target));
        s.source->value[5] = 3; s.source->value[6] = 999;
        if (enabled) { assert(effects.empty()); advance(); }
        assert(effects.size() == 1 && effects[0].id == choice + 1 && effects[0].power == 57);
        assert(effects[0].target == (choice == 1 ? s.actor : s.target)->runtime_id);
        assert((rolls == std::vector<std::pair<int,int>>{{0,24},{0,count-1}}));
    }
    for (bool enabled : {false, true}) for (int choice = 0; choice < 3; ++choice) {
        weapon_scene s("weapons", enabled); s.packed(true);
        skills[1].spell_pointer = nullptr;
        assert(valued_packed_mask(s.source)==6);
        choices = {0, choice}; assert(weapon_proc(s.source, s.actor, s.target));
        if (enabled) advance();
        assert(effects.size() == (choice ? 1u : 0u));
        if (choice) assert(effects[0].id == choice + 1 && effects[0].power == 57);
        assert((rolls == std::vector<std::pair<int,int>>{{0,24},{0,2}}));
    }
    {
        weapon_scene s("weapons"); s.packed(); s.source->value[5] = 2002;
        assert(s.hit() && effects.size() == 2 && !item_actions_pending()); // Pure buffs stay instant.
    }
    for (bool enabled : {false, true}) {
        weapon_scene s("weapons", enabled); s.packed(); s.source->value[5] = 3000001;
        assert(valued_packed_mask(s.source)==1);
        assert(s.hit()); advance();
        assert(effects.size() == 1 && effects[0].id == 1); // Preserve legacy sparse-slot/count quirk.
    }
    {
        weapon_scene s("weapons"); s.packed(); affected_spell = 2;
        assert(s.hit()); advance(); assert(effects.size() == 2 && effects[0].id == 3 && effects[1].id == 1);
    }
    for (int change : {1,2}) {
        weapon_scene s("weapons"); s.packed(); mutation = change;
        assert(s.hit()); advance(); assert(effects.size() == 1 && !item_actions_pending());
    }
}

static void random_parity() {
    for (bool enabled : {false, true}) {
        weapon_scene s("randomWeapons", enabled); s.named();
        assert(!s.hit());
        assert(s.source->timer[0] == wall_time);
        if (enabled) {
            assert(effects.empty()); GET_OPPONENT(s.actor) = s.actor;
            advance();
        }
        assert((effects == std::vector<effect_call>{{1,50,SPELL_TYPE_SPELL,s.target->runtime_id,0}}));
        assert((rolls == std::vector<std::pair<int,int>>{{0,10}}));
        assert(!weapon_proc(s.source, s.actor, s.target)); assert(rolls.size() == 1);
    }
    {
        weapon_scene s("randomWeapons"); s.named(); s.paid(0);
        assert(!s.hit()); assert(!s.source->timer[0] && effects.empty());
    }
    {
        weapon_scene s("randomWeapons"); s.named();
        assert(!s.hit()); depart(s.target); advance();
        assert(effects.empty() && s.source->timer[0] == wall_time);
    }
    {
        weapon_scene s("randomWeapons"); s.named(); s.source->value[7] = 2;
        assert(!s.hit());
        assert(effects.size() == 1 && effects[0].id == 2 && effects[0].target == s.actor->runtime_id);
    }
    for (int command : {CMD_GOTHIT, CMD_GOTNUKED}) {
        weapon_scene s("randomWeapons"); s.named();
        // Three matching pieces satisfy the unchanged defensive selection path.
        s.actor->equipment[6] = s.actor->equipment[19] = s.actor->equipment[21] = s.source;
        choices.push_back(0);
        assert(!random_eq_proc(s.source,s.actor,command,reinterpret_cast<char *>(s.target)));
        assert(effects.size() == 1 && !item_actions_pending());
        assert(rolls.size() == 1 && rolls[0].second == (command == CMD_GOTHIT ? 100 : 50));
    }
}

static void suppression_measurement() {
    for (bool enabled : {false, true}) {
        weapon_scene s("avernus", enabled);
        for (int i = 0; i < 200; ++i) { assert(s.hit()); advance(1); }
        advance();
        const size_t completed = effects.size() / 2;
        assert(rolls.size() == 200 && (enabled ? completed > 0 && completed < 200 : completed == 200));
        std::printf("Deterministic Avernus: enabled=%d, selected=200 at 4/sec, completed=%zu, suppressed=%zu\n",
                    enabled, completed, 200 - completed);
    }
    weapon_scene s;
    properties["itemActions.avernus.windupPulses"] = 600;
    properties["itemActions.maxPulses"] = 8; update_item_action_properties();
    assert(s.hit()); advance(5); audience_count("intensifies", 1);
    advance(8); assert(effects.size() == 2);
}

struct wind_scene : weapon_scene {
    explicit wind_scene(bool dagger = false) {
        obj_index[0].virtual_number = dagger ? 131616 : 24406;
        obj_index[0].func.obj = dagger ? dagger_of_wind : lightning;
        source->type = ITEM_WEAPON; source->extra_flags = ITEM_ARTIFACT;
        source->name = const_cast<char *>("sphere wind");
        actor->in_room = target->in_room = 1;
        world[1] = {}; world[1].people = actor; actor->next_in_room = target;
        GET_OPPONENT(actor) = target; GET_OPPONENT(target) = actor;
        protected_player = nullptr; test_zones[0] = {}; unrelated_wait_changes = 0;
        wall_time = 1000; target->player.size = SIZE_MEDIUM;
    }
    ~wind_scene() { world[1].people = nullptr; }
    int rub() { char argument[] = "sphere"; return lightning(source, actor, CMD_RUB, argument); }
};

static int carried_rubs = 0;
static int carried_rub(P_obj source, P_char, int command, char *argument) {
    if (command != CMD_RUB || !isname(argument, source->name)) return false;
    ++carried_rubs;
    return true;
}

// A proc that extracts its own object, as huntsman_ward and generic_drow_eq do.
static int self_extract(P_obj source, P_char ch, int, char *) {
    ch->carrying = source->next_content;
    delete source;
    return false;
}

static void self_extracting_dispatch() {
    wind_scene s;
    P_index saved = obj_index;
    index_data index[3]{};
    index[0] = obj_index[0]; index[1].func.obj = self_extract; index[2].func.obj = carried_rub;
    obj_index = index;
    obj_data carried{}; carried.R_num = 2;
    carried.name = const_cast<char *>("amethyst orb");
    auto *doomed = new obj_data{}; doomed->R_num = 1; doomed->next_content = &carried;
    s.actor->carrying = doomed; carried_rubs = 0;
    char argument[] = "amethyst";
    // The next object is read before the proc frees the current one.
    assert(special(s.actor, CMD_RUB, argument) && carried_rubs == 1);
    s.actor->carrying = nullptr;
    obj_index = saved;
}

static void wind_rub_dispatch() {
    for (bool safe : {false, true}) {
        wind_scene s;
        index_data index[2]{};
        index[0] = obj_index[0]; index[1].func.obj = carried_rub; obj_index = index;
        obj_data carried{}; carried.R_num = 1;
        carried.name = const_cast<char *>("amethyst orb"); s.actor->carrying = &carried;
        world[1].room_flags = safe ? ROOM_SAFE : 0; carried_rubs = 0;
        choices = {SIZE_GARGANTUAN + 2};
        char argument[] = "amethyst";
        assert(special(s.actor, CMD_RUB, argument) && carried_rubs == 1);
        assert(!s.source->timer[0] && messages.empty() && rolls.empty() && !unrelated_wait_changes);
        assert(GET_POS(s.target) == POS_STANDING && GET_OPPONENT(s.target) == s.actor);
        s.actor->carrying = nullptr;
    }
    for (const char *name : {"", "   ", "amethyst", "sphereish", "amethyst sphere"}) {
        wind_scene s; std::string argument(name);
        assert(!special(s.actor, CMD_RUB, argument.data()));
        assert(!s.source->timer[0] && messages.empty() && rolls.empty());
    }
    { wind_scene s;
      assert(!lightning(s.source, s.actor, CMD_RUB, nullptr));
      assert(!s.source->timer[0] && messages.empty() && rolls.empty()); }
    for (const char *name : {"sphere", "wind", "sphere wind", "  SpHeRe"}) {
        wind_scene s; std::string argument(name); choices = {SIZE_GARGANTUAN + 2};
        assert(special(s.actor, CMD_RUB, argument.data()));
        assert(s.source->timer[0] == wall_time && GET_POS(s.target) == POS_PRONE);
        assert(choices.empty() && unrelated_wait_changes == 1);
    }
}

static void wind_artifact_cases() {
    // Real weapon dispatch reaches the sphere callback on exactly one of 16 rolls.
    for (int roll = 0; roll < 16; ++roll) {
        wind_scene s;
        assert(s.hit(roll) == (roll == 0));
        assert((rolls == std::vector<std::pair<int,int>>{{0,15}}));
        assert(effects.size() == (roll ? 0 : 4));
        for (size_t i = 0; i < effects.size(); ++i)
            assert((effects[i] == effect_call{i ? SPELL_LIGHTNING_BOLT : SPELL_CYCLONE,
                60, SPELL_TYPE_SPELL, s.target->runtime_id, 0}));
        assert(choices.empty());
    }
    { wind_scene s; mutation = 3; assert(s.hit()); assert(effects.size() == 1); }
    for (int invalid = 0; invalid < 4; ++invalid) {
        wind_scene s;
        if (invalid == 0) { s.actor->equipment[WIELD] = nullptr; s.actor->equipment[HOLD] = s.source; }
        if (invalid == 1) s.source->loc.wearing = s.target;
        if (invalid == 2) SET_POS(s.actor, STAT_DEAD);
        if (invalid == 3) SET_POS(s.target, STAT_DEAD);
        assert(!weapon_proc(s.source, s.actor, s.target) && rolls.empty() && effects.empty());
    }
    { wind_scene s;
      assert(lightning(s.source, nullptr, CMD_SET_PERIODIC, nullptr));
      assert(lightning(s.source, nullptr, CMD_PERIODIC, nullptr)); assert(hum_calls == 1);
      assert(!lightning(s.source, s.actor, CMD_LOOK, nullptr)); assert(rolls.empty()); }

    // Both room and zone safety reject the rub before cooldown, messages or effects.
    for (bool zone : {false, true}) {
        wind_scene s;
        if (zone) test_zones[0].flags = ZONE_SAFE; else world[1].room_flags = ROOM_SAFE;
        assert(s.rub());
        assert(!s.source->timer[0] && rolls.empty() && !unrelated_wait_changes);
        assert(GET_POS(s.target) == POS_STANDING && GET_OPPONENT(s.target) == s.actor);
        assert(messages.size() == 1 && messages[0].audience == -1); // Safety explanation only.
    }
    // The existing hostile-target policy excludes protected players and ineligible attacks.
    for (int denied = 0; denied < 7; ++denied) {
        wind_scene s; group_list group{};
        if (denied == 0) s.actor->group = s.target->group = &group;
        if (denied == 1) protected_player = s.target;
        if (denied == 2) can_fight = false;
        if (denied == 3) s.actor->specials.affected_by5 = AFF5_NOT_OFFENSIVE;
        if (denied == 4) affected_spell = SONG_PEACE;
        if (denied == 5) affected_spell = SKILL_GAZE;
        if (denied == 6) SET_POS(s.target, STAT_DEAD);
        const auto position = s.target->specials.position;
        assert(s.rub());
        assert(rolls.empty() && !unrelated_wait_changes && effects.empty());
        assert(s.target->specials.position == position && GET_OPPONENT(s.target) == s.actor);
        assert(GET_POS(s.actor) == POS_STANDING && GET_OPPONENT(s.actor) == s.target);
        s.actor->group = s.target->group = nullptr;
    }
    { wind_scene s; choices = {SIZE_GARGANTUAN + 2};
      assert(s.rub() && s.source->timer[0] == wall_time);
      assert(GET_POS(s.target) == POS_PRONE && !GET_OPPONENT(s.target) && unrelated_wait_changes == 1);
      assert(GET_OPPONENT(s.actor) == s.target && GET_POS(s.actor) == POS_STANDING);
      assert(choices.empty()); const auto calls = rolls.size();
      wall_time += 499; assert(!s.rub() && rolls.size() == calls);
      wall_time += 1; choices = {0}; assert(s.rub() && choices.empty()); }
    { wind_scene s; s.source->loc.wearing = s.target;
      assert(!s.rub() && !s.source->timer[0] && rolls.empty()); }

    // Reproduce the reset carrier's inventory -> auto-wield -> melee callback path.
    { wind_scene s(true); SET_BIT(s.actor->specials.act, ACT_ISNPC);
      s.actor->equipment[WIELD] = nullptr; s.actor->carrying = s.source;
      s.source->loc_p = LOC_CARRIED; s.source->loc.carrying = s.actor;
      try_wield_weapon(s.actor); assert(OBJ_WORN_POS(s.source, WIELD));
      for (int hit = 0; hit < 30; ++hit) assert(!weapon_proc(s.source, s.actor, s.target));
      assert(GET_OPPONENT(s.actor) == s.target && GET_OPPONENT(s.target) == s.actor);
      assert(rolls.empty() && effects.empty() && messages.empty()); }
    // Players retain the 1/15 escape and its optional 1/4 self-deflection.
    for (int roll = 0; roll < 15; ++roll) {
        wind_scene s(true); choices = {roll}; if (!roll) choices.push_back(0);
        assert(weapon_proc(s.source, s.actor, s.target) == (roll == 0));
        assert(choices.empty() && rolls[0] == std::make_pair(0, 14));
        assert((GET_OPPONENT(s.actor) == nullptr) == (roll == 0));
        assert((GET_OPPONENT(s.target) == nullptr) == (roll == 0));
        assert(effects.size() == (roll ? 0 : 1));
        if (!roll) assert((effects[0] == effect_call{SPELL_DEFLECT, 60, SPELL_TYPE_SPELL, s.actor->runtime_id, 0}));
    }
    { wind_scene s(true); choices = {0, 3}; assert(weapon_proc(s.source, s.actor, s.target));
      assert(effects.empty() && choices.empty()); }
}

int main() {
    nevent_bind_game_thread(); ne_dead_event_pool = &test_pool;
    fake_clock_ns = 1000000000ULL; ne_events();
    monk_gloves(); avernus_parity(); cancellation_and_payment(); packed_parity(); random_parity(); suppression_measurement();
    wind_artifact_cases(); wind_rub_dispatch(); self_extracting_dispatch();
    std::puts("Weapon actions: real selection callbacks, parity, payment, targets, cancellation and timing passed");
    std::puts("Wind artifacts: sphere melee/whirlwind policy and cooldown, NPC auto-wield and player escape passed");
    std::puts("Wind rub dispatch: real command routing and name matching preserve other carried-item procs");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="weapon-actions-", dir=ROOT / "bin/tests") as directory:
    source = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    doubles = DOUBLES.replace("messages", "captured_messages").replace("damage_captured_messages", "damage_messages")
    source.write_text(platform + fixture + doubles.replace("// INSERT_CALLBACKS", callbacks))
    subprocess.run([
        "g++", "-std=c++20", "-O1", "-g", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-pthread",
        "-I" + str(ROOT / "src"), str(source), str(ROOT / "src/persistence/latency_trace.c"), str(ROOT / "src/item/item_value.c"),
        "-Wl,--gc-sections", str(HARNESS_STUBS), "-o", str(binary),
    ], check=True)
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1",
               DURIS_NEVENT_ANALYTICS="0", DURIS_NEVENT_BUDGET_USEC="0",
               DURIS_NEVENT_MAX_CALLBACKS="0", DURIS_NEVENT_PLAYER_PRIORITY="1")
    subprocess.run([str(binary)], check=True, env=env)

backstab = function(ROOT / "src/cmd/actoff.c", "bool single_stab(")
assert "obj_index[weapon->R_num].func.obj" in backstab and "CMD_MELEE_HIT" in backstab
assert "weapon_proc(" not in "\n".join(line.split("//", 1)[0] for line in backstab.splitlines())
print("Backstab retains the direct callback route covered by the Avernus pilot")

for area, boss, room, reward, previous in (
    ("plane_air_one", 24440, 24450, 131616, 24406),
    ("airp", 131648, 131792, 24406, 131616),
):
    holder = None
    rewards = []
    for line in (ROOT / f"areas/zon/{area}.zon").read_text().splitlines():
        fields = line.split("*", 1)[0].split()
        if fields and fields[0] == "M":
            holder = (int(fields[2]), int(fields[4]))
        elif fields and fields[0] == "G" and int(fields[2]) in (reward, previous):
            rewards.append((holder, fields))
    assert rewards == [((boss, room), ["G", "1", str(reward), "1", "0", "100", "0", "0", "0"])]
print("Wind artifact resets: dagger on Yan-C-Bin, sphere on Akadi, limits/chances preserved")
