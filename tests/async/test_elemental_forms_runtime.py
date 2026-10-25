#!/usr/bin/env python3
"""Run form registration, handlers, affect ownership and binary save/restore.

Production list/codec operations are used; the general stat total, scheduler and
UI are fixtures. Full server command/combat journeys are recorded in plan.md.
"""
import re
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function, source

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "core/mm.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/events.h"
#include "combat/damage.h"
#include "player/player_snapshot_codec.h"
#include <cassert>
#include <cstring>
#include <string>
#include <map>
room_data rooms[1]{};
P_room world = rooms;
const int top_of_world = 0;
Skill skills[MAX_SKILLS];
int numSkills, SortedSkills[MAX_SKILLS];
static mm_ds pool{};
mm_ds *dead_affect_pool = &pool;
static std::string output;
index_data indexes[1]{};
P_index obj_index = indexes;
static int die_roll = 1, aura_roll = 1, delivered_damage, delivered_type;
static bool save_roll;
static int aff_vers, short_size = sizeof(short), int_size = sizeof(int), long_size = sizeof(long);
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
void send_to_char(const char *text, P_char) { output += text; }
void act(const char *, int, P_char, P_obj, void *, int) {}
bool NewSaves(P_char, int, int) { return save_roll; }
bool has_innate(P_char ch, int id) { return id == INNATE_LIVING_STONE && GET_SPEC(ch, CLASS_CONJURER, SPEC_EARTH); }
int number(int low, int high) { return low == 1 && high == 4 ? die_roll : (low == 0 && high == 5 ? aura_roll : (low == 0 && high == 3 ? 2 : low)); }
int dice(int count, int) { return count * 5; }
bool IS_OUTDOORS(int room) { return !IS_ROOM(room, ROOM_INDOORS); }
int get_default_save_mod(P_char, P_char, int, int) { return 0; }
int spell_damage(P_char, P_char, double dam, int type, uint, damage_messages *, int *) {
    delivered_damage = dam; delivered_type = type; return DAM_NONEDEAD;
}
int gain_exp(P_char, P_char, int, int) { return 0; }
bool critical_disarm(P_char, P_char) { assert(false); return false; }
bool hit(P_char, P_char, P_obj, int *) { assert(false); return false; }
float get_property(const char *, double fallback) { return fallback; }
int get_property(const char *, int fallback) { return fallback; }
void *_mm_get(mm_ds *, const char *, int) { return new affected_type{}; }
void mm_release(mm_ds *, void *p) { delete static_cast<affected_type *>(p); }
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { return &pool; }
void all_affects(P_char, int) {}
void balance_affects(P_char ch) {
    ch->specials.affected_by = ch->specials.affected_by2 = ch->specials.affected_by4 = 0;
    for (auto *af = ch->affected; af; af = af->next) {
        ch->specials.affected_by |= af->bitvector;
        ch->specials.affected_by2 |= af->bitvector2;
        ch->specials.affected_by4 |= af->bitvector4;
    }
}
char affect_total(P_char ch, int) { balance_affects(ch); return 0; }
void gmcp_char_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void unlink_char_affect(P_char, affected_type *) { assert(false); }
void unlink_char_obj_affect(P_char, affected_type *) { assert(false); }
void event_poison(P_char, P_char, P_obj, void *) {}
void event_web_spray(P_char, P_char, P_obj, void *) {}
void event_short_affect(P_char, P_char, P_obj, void *) { assert(false); }
void disarm_char_nevents(P_char, event_func_type) {}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) { assert(false); return {}; }
nevent_handle nevent_handle_from_event(P_nevent) { assert(false); return {}; }
nevent_cancel_result nevent_cancel(nevent_handle) { assert(false); return nevent_cancel_result::canceled; }
char *getString(char **) { assert(false); return nullptr; }
void str_free(const char *) { assert(false); }
void affect_to_char_with_messages(P_char, affected_type *, const char *, const char *) { assert(false); }
void StopCasting(P_char) { output += "STOP"; }
int IS_MORPH(P_char) { return false; }
P_char un_morph(P_char) { assert(false); return nullptr; }
'''

prelude += re.search(r'(?m)^#define MACE_OF_EARTH_VNUM \d+', source('magic.c').read_text())[0] + '\n'
prelude += re.search(r'struct attack_hit_type attack_hit_text\[\] = .*?\n};', source('fight.c').read_text(), re.S)[0] + '\n'

functions = [
    ('utility.c', 'int flag2idx('),
    ('skills.c', 'void SPELL_CREATE_MSG('),
    ('skills.c', 'void SPEC_SPELL_ADD('),
    ('affects.c', 'struct affected_type *get_spell_from_char('),
    ('affects.c', 'bool affected_by_spell('),
    ('affects.c', 'struct affected_type *affect_to_char('),
    ('affects.c', 'void affect_remove('),
    ('affects.c', 'void affect_from_char('),
    ('affects.c', 'void wear_off_message('),
    ('files.c', 'ush_int getShort('), ('files.c', 'uint getInt('), ('files.c', 'long getLong('),
    ('files.c', 'int writeAffects('), ('files.c', 'int restoreAffects('),
    ('magic.c', 'const char *elemental_form_failure_message('),
    ('magic.c', 'const char *elemental_summon_failure_message('),
    ('magic.c', 'const char *elemental_aura_failure_message('),
    ('magic.c', 'void spell_elemental_aura('),
    ('psionics.c', 'void spell_fire_aura('),
    ('magic.c', 'void spell_air_form('),
    ('magic.c', 'void spell_earth_form('),
    ('magic.c', 'void spell_fire_form('),
    ('magic.c', 'void spell_water_form('),
    ('magic.c', 'static bool has_other_skin_spell('),
    ('magic.c', 'bool has_skin_spell('),
    ('magic.c', 'void spell_stone_skin('),
    ('magic.c', 'void spell_earthen_maul('),
    ('fight.c', 'bool decrease_skin_counter('),
    ('fight.c', 'bool critical_attack('),
]
skills = source('skills.c').read_text()
registrations = []
for name in ('air', 'earth', 'fire', 'water'):
    match = re.search(rf'SPELL_CREATE_MSG\("{name} form",.*?;\s*SPEC_SPELL_ADD\([^;]+;', skills, re.S)
    assert match
    registrations.append(match[0])

event = extract_function('sparser.c', 'void event_spellcast(P_char ch,')
start = event.index('\t/* Reject conflicting auras/forms')
end = event.index('\n\t/*', start + 3)
preflight = event[start:end]
assert start < event.index('use_spell(ch, arg->spell)')
# The exact production completion preflight is exercised with a resource sentinel;
# the whole parser and memorization path are covered separately and in gameplay.
gate = '''
bool completion_allowed(P_char ch, int spell, const char *args = "") {
    spellcast_datatype payload{}; auto *arg = &payload; arg->spell = spell;
    P_char tar_char = ch; bool weaving = false;
    auto finish = [&]() {
PRODUCTION_PREFLIGHT
        output += "SPENT";
    };
    output.clear(); finish();
    return output.find("SPENT") != std::string::npos;
}
'''.replace('PRODUCTION_PREFLIGHT', preflight)

materialize = source('player_load_materialize.c').read_text()
affect_start = materialize.index('\tfor (auto affect_entry = result.snapshot.affects.rbegin();')
affect_end = materialize.index('\n\tif (zone_trophies)', affect_start)
snapshot_restore = '''
void restore_snapshot_affects(P_char ch, const player_snapshot &snapshot) {
    struct { const player_snapshot &snapshot; } result{snapshot};
PRODUCTION_AFFECTS
}
'''.replace('PRODUCTION_AFFECTS', materialize[affect_start:affect_end])

updates = extract_function('affects.c', 'void affect_update(')
tick_start = updates.index('\t\t\tfor (af = i->affected;')
tick_end = updates.index('\n\t\t\tif (morphed)', tick_start)
tick = '''
void tick_forms(P_char i) {
    affected_type *af, *next_af_dude; P_char orig; int morphed = FALSE;
PRODUCTION_DURATION_LOOP
}
'''.replace('PRODUCTION_DURATION_LOOP', updates[tick_start:tick_end])

physical = extract_function('fight.c', 'int melee_damage(')
skin_start = physical.index('\t// Earth elementals ignore earth aura.')
skin_end = physical.index('\n\tif (affected_by_spell(ch, ACH_DRAGONSLAYER)', skin_start)
skin_path = '''
int physical_skin_path(P_char ch, P_char victim, double dam, unsigned int flags = 0) {
    double reduction = 0; unsigned int skin = 0; bool dragonfist = false;
PRODUCTION_SKIN
    return std::max(0, int(dam));
}
'''.replace('PRODUCTION_SKIN', physical[skin_start:skin_end])

driver = r'''
static void clear(P_char ch) { while (ch->affected) affect_remove(ch, ch->affected); }
static std::map<int, int> modifiers(P_char ch, int type) {
    std::map<int, int> result;
    for (auto *af = ch->affected; af; af = af->next) {
        if (af->type != type) continue;
        assert(af->duration == 8);
        result[af->location] += af->modifier;
    }
    return result;
}
int main() {
    REGISTER_FORMS
    assert(SPELL_BLOOD_TITHE == 683 && SPELL_EARTH_FORM == 684 && LAST_SPELL == 686);
    static_assert(LAST_SPELL < FIRST_SKILL && LAST_SPELL < MAX_SKILLS);
    char_data caster{}, other{};
    caster.player.m_class = CLASS_CONJURER;
    caster.player.level = 46;
    SET_POS(&caster, STAT_NORMAL + POS_STANDING);
    SET_POS(&other, STAT_NORMAL + POS_STANDING);
    struct Form { int type, spec; unsigned int bit; std::map<int, int> stats; };
    Form forms[] = {
        {SPELL_EARTH_FORM, SPEC_EARTH, AFF2_EARTH_AURA, {{0, 0}}},
        {SPELL_FIRE_FORM, SPEC_FIRE, AFF2_FIRE_AURA | AFF2_FIRESHIELD,
            {{APPLY_AC,-15}, {APPLY_STR_MAX,15}, {APPLY_DEX_MAX,-20}, {APPLY_AGI_MAX,-20}, {APPLY_CON_MAX,25}}},
        {SPELL_WATER_FORM, SPEC_WATER, AFF2_WATER_AURA,
            {{APPLY_STR_MAX,-20}, {APPLY_DEX_MAX,50}, {APPLY_AGI_MAX,25}, {APPLY_CON_MAX,-10}}},
    };
    for (const auto &form : forms) {
        assert(skills[form.type].targets == (TAR_SPELL | TAR_SELF_ONLY));
        assert(skills[form.type].beats == PULSE_SPELLCAST * 4);
        for (int cls = 0; cls < CLASS_COUNT; ++cls)
            for (int spec = 0; spec <= MAX_SPEC; ++spec)
                assert(skills[form.type].m_class[cls].rlevel[spec] ==
                    ((cls == flag2idx(CLASS_CONJURER)-1 && spec == form.spec) ? 10 : 0));
        for (int spec : {0, SPEC_AIR, SPEC_EARTH, SPEC_FIRE, SPEC_WATER}) {
            caster.player.spec = spec;
            skills[form.type].spell_pointer(46, &caster, nullptr, 0, &caster, nullptr);
            assert(bool(caster.affected) == (spec == form.spec));
            clear(&caster);
        }
        caster.player.spec = form.spec;
        skills[form.type].spell_pointer(46, &caster, nullptr, 0, &other, nullptr);
        assert(!other.affected && !caster.affected);
        caster.specials.act = ACT_ISNPC;
        skills[form.type].spell_pointer(46, &caster, nullptr, 0, &caster, nullptr);
        assert(!caster.affected); caster.specials.act = 0;
        for (int sector : {SECT_INSIDE, SECT_WATER_SWIM, SECT_OCEAN, SECT_NO_GROUND,
                           SECT_FIREPLANE, SECT_WATER_PLANE, SECT_AIR_PLANE, SECT_EARTH_PLANE}) {
            rooms[0].sector_type = sector;
            assert(completion_allowed(&caster, form.type));
            skills[form.type].spell_pointer(46, &caster, nullptr, 0, &caster, nullptr);
            assert(modifiers(&caster, form.type) == form.stats);
            assert(caster.specials.affected_by2 == form.bit);
            assert(!completion_allowed(&caster, form.type)); // no recast/refresh
            for (int aura : {SPELL_AIR_FORM, SPELL_FIRE_AURA, SPELL_ELEMENTAL_AURA}) {
                assert(!completion_allowed(&caster, aura));
                skills[form.type].spell_pointer(46, &caster, nullptr, 0, &caster, nullptr);
                assert(modifiers(&caster, form.type) == form.stats);
            }
            spell_air_form(46, &caster, nullptr, 0, &caster, nullptr);
            spell_fire_aura(46, &caster, nullptr, 0, &caster, nullptr);
            spell_elemental_aura(46, &caster, nullptr, 0, &caster, nullptr);
            assert(!affected_by_spell(&caster, SPELL_AIR_FORM));
            assert(!affected_by_spell(&caster, SPELL_FIRE_AURA));
            assert(!affected_by_spell(&caster, SPELL_ELEMENTAL_AURA));
            // Existing binary affect codec round-trips every component and its duration.
            char saved[4096]{};
            int bytes = writeAffects(saved, caster.affected);
            clear(&caster); assert(restoreAffects(saved, &caster) == bytes);
            assert(modifiers(&caster, form.type) == form.stats);
            assert(caster.specials.affected_by2 == form.bit);
            // Independent shield survives full form removal (normal dispel ownership).
            affected_type shield{}; shield.type = SPELL_FIRESHIELD; shield.bitvector2 = AFF2_FIRESHIELD;
            affect_to_char(&caster, &shield);
            affect_from_char(&caster, form.type);
            assert(!affected_by_spell(&caster, form.type));
            assert(caster.specials.affected_by2 == AFF2_FIRESHIELD);
            clear(&caster);
            // Equal-duration components expire with exactly one final message.
            skills[form.type].spell_pointer(46, &caster, nullptr, 0, &caster, nullptr);
            output.clear();
            for (int unit = 0; unit < 8; ++unit) tick_forms(&caster);
            assert(caster.affected && caster.affected->duration == 0);
            tick_forms(&caster); assert(!caster.affected);
            assert(output == std::string(skills[form.type].wear_off_char[0]) + "\n");
            assert(caster.specials.affected_by2 == 0);
        }
        // Partial aura effects (without their aura bit) must also block a form.
        for (int aura : {SPELL_ELEMENTAL_AURA, SPELL_FIRE_AURA, SPELL_AIR_FORM,
                         SPELL_EARTH_FORM, SPELL_FIRE_FORM, SPELL_WATER_FORM}) {
            affected_type partial{}; partial.type = aura; partial.location = APPLY_STR_MAX; partial.modifier = 3;
            affect_to_char(&caster, &partial);
            assert(!completion_allowed(&caster, form.type));
            skills[form.type].spell_pointer(46, &caster, nullptr, 0, &caster, nullptr);
            assert(caster.affected->next == nullptr && caster.affected->modifier == 3);
            clear(&caster);
        }
        for (unsigned int bit : {AFF2_EARTH_AURA, AFF2_WATER_AURA, AFF2_FIRE_AURA, AFF2_AIR_AURA}) {
            caster.specials.affected_by2 = bit;
            assert(!completion_allowed(&caster, form.type));
        }
        caster.specials.affected_by2 = 0;
        caster.specials.affected_by4 = AFF4_ICE_AURA;
        assert(!completion_allowed(&caster, form.type));
        caster.specials.affected_by4 = 0;
    }
    caster.player.spec = SPEC_FIRE;
    for (int spell : {SPELL_CONJURE_ELEMENTAL, SPELL_CONJURE_GREATER_ELEMENTAL}) {
        assert(completion_allowed(&caster, spell, "mephit"));
        assert(completion_allowed(&caster, spell, ""));
        assert(!completion_allowed(&caster, spell, "mephit 1112"));
        caster.player.spec = SPEC_AIR;
        assert(completion_allowed(&caster, spell, "other callers keep old arguments"));
        caster.player.spec = SPEC_FIRE;
    }
    // Stone Skin stacks on the recipient, retaining each caster's charge bonus.
    char_data earth{}, ordinary{}, pet{};
    earth.player.m_class = CLASS_CONJURER; earth.player.spec = SPEC_EARTH;
    earth.player.level = 56;
    SET_POS(&earth, STAT_NORMAL + POS_STANDING);
    SET_POS(&ordinary, STAT_NORMAL + POS_STANDING);
    pet.specials.act = ACT_ISNPC; pet.player = earth.player;
    for (P_char recipient : {&earth, &ordinary, &pet}) {
        for (P_char source : {&earth, &ordinary}) {
            for (int cast = 1; cast <= 4; ++cast) {
                die_roll = cast;
                spell_stone_skin(40, source, nullptr, 0, recipient, nullptr);
                int count = 0;
                for (auto *af = recipient->affected; af; af = af->next) ++count;
                assert(count == (recipient == &earth ? std::min(cast,3) : 1));
            }
            clear(recipient);
        }
    }
    die_roll = 1;
    spell_stone_skin(40, &ordinary, nullptr, 0, &earth, nullptr);
    auto *oldest = earth.affected; oldest->duration = 1;
    spell_stone_skin(44, &ordinary, nullptr, 0, &earth, nullptr);
    auto *middle = earth.affected; middle->duration = 2;
    spell_stone_skin(48, &earth, nullptr, 0, &earth, nullptr);
    auto *newest = earth.affected;
    assert(newest->modifier == 19 && middle->modifier == 9 && oldest->modifier == 8);
    assert(newest->duration == 4 && middle->duration == 2 && oldest->duration == 1);
    for (int recovery = 0; recovery < 2; ++recovery) {
        char saved[4096]{};
        int bytes = writeAffects(saved, earth.affected);
        clear(&earth); assert(restoreAffects(saved, &earth) == bytes);
        newest = earth.affected; middle = newest->next; oldest = middle->next;
        assert(newest->modifier == 19 && middle->modifier == 9 && oldest->modifier == 8);
        assert(newest->duration == 4 && middle->duration == 2 && oldest->duration == 1);
    }
    // The binary path must reverse only its restored prefix, retaining older affects.
    char preserved[4096]{}; int preserved_bytes = writeAffects(preserved, earth.affected);
    char_data extra{}; affected_type independent{}; independent.type = SPELL_FIRESHIELD;
    auto *previous = affect_to_char(&extra, &independent);
    assert(restoreAffects(preserved, &extra) == preserved_bytes);
    assert(extra.affected->modifier == 19 && extra.affected->next->next->next == previous);
    clear(&extra);
    for (int recovery = 0; recovery < 2; ++recovery) {
        player_snapshot snapshot{};
        snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
        snapshot.pid = 215; snapshot.revision = 1; snapshot.components = PLAYER_COMPONENT_STATUS;
        snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
        for (auto *af = earth.affected; af; af = af->next) {
            player_affect_snapshot row{};
            row.type = af->type; row.duration = af->duration; row.modifier = af->modifier;
            row.location = af->location; row.flags = af->flags; row.level = af->level;
            snapshot.affects.push_back(row);
        }
        std::vector<uint8_t> bytes; player_snapshot decoded{};
        assert(player_snapshot_encode(snapshot, &bytes) == player_snapshot_codec_result::ok);
        assert(player_snapshot_decode(bytes.data(), bytes.size(), &decoded) == player_snapshot_codec_result::ok);
        clear(&earth); restore_snapshot_affects(&earth, decoded);
        newest = earth.affected; middle = newest->next; oldest = middle->next;
        assert(newest->modifier == 19 && middle->modifier == 9 && oldest->modifier == 8);
        assert(newest->duration == 4 && middle->duration == 2 && oldest->duration == 1);
    }
    int damage_with_three = physical_skin_path(&ordinary, &earth, 200);
    assert(newest->modifier == 18 && middle->modifier == 9 && oldest->modifier == 8);
    while (earth.affected == newest) decrease_skin_counter(&earth, SPELL_STONE_SKIN);
    assert(earth.affected == middle && middle->modifier == 9 && oldest->modifier == 8);
    assert(physical_skin_path(&ordinary, &earth, 200) == damage_with_three);
    // Earth Form uses the same single mitigation roll regardless of layer count.
    spell_earth_form(56, &earth, nullptr, 0, &earth, nullptr);
    aura_roll = 0;
    assert(physical_skin_path(&ordinary, &earth, 200) == 0);
    ordinary.player.race = RACE_E_ELEMENTAL;
    assert(physical_skin_path(&ordinary, &earth, 200) == damage_with_three);
    ordinary.player.race = RACE_HUMAN;
    assert(physical_skin_path(&ordinary, &earth, 200, PHSDAM_NOREDUCE) == 200);
    aura_roll = 1;
    assert(critical_attack(&ordinary, &earth, 0));
    assert(!affected_by_spell(&earth, SPELL_STONE_SKIN));
    assert(affected_by_spell(&earth, SPELL_EARTH_FORM));
    clear(&earth);
    // A second layer must never bypass the other skin exclusions.
    for (int other_skin : {SPELL_BIOFEEDBACK, SPELL_SHADOW_SHIELD, SPELL_IRONWOOD,
                           SPELL_VINES, SPELL_ICE_ARMOR, SPELL_NEG_ARMOR, SPELL_DRAKESCALE_AEGIS}) {
        spell_stone_skin(40, &earth, nullptr, 0, &earth, nullptr);
        affected_type blocked{}; blocked.type = other_skin; affect_to_char(&earth, &blocked);
        auto *head = earth.affected;
        spell_stone_skin(40, &earth, nullptr, 0, &earth, nullptr);
        assert(earth.affected == head && head->next->next == nullptr);
        clear(&earth);
    }
    // Actual Maul handler: matched dice retain normal/indoor/mountain/lava tiers
    // for both Earth Magi and Druids; earthless/airborne fallback stays normal.
    for (int cls : {CLASS_CONJURER, CLASS_DRUID}) {
        caster.player.m_class = cls; caster.player.spec = cls == CLASS_CONJURER ? SPEC_EARTH : 0;
        for (int level : {46,56}) {
            for (bool saved : {false,true}) {
                save_roll = saved;
                int base = (level > 50 ? 600 : 500) / (saved ? 2 : 1);
                for (int sector : {SECT_FIELD, SECT_INSIDE, SECT_MOUNTAIN, SECT_LAVA,
                                   SECT_OCEAN, SECT_WATER_SWIM, SECT_WATER_NOSWIM,
                                   SECT_UNDERWATER, SECT_NO_GROUND, SECT_FIREPLANE,
                                   SECT_AIR_PLANE, SECT_WATER_PLANE, SECT_EARTH_PLANE}) {
                    for (bool indoor : {false,true}) {
                        rooms[0].sector_type = sector;
                        rooms[0].room_flags = indoor ? ROOM_INDOORS : 0;
                        for (int altitude : {0,1}) {
                            caster.specials.z_cord = altitude;
                            delivered_damage = 0;
                            spell_earthen_maul(level, &caster, nullptr, 0, &other, nullptr);
                            int tier = 1;
                            if (altitude == 0) {
                                if (sector == SECT_INSIDE || (sector == SECT_FIELD && indoor)) tier = 3;
                                if (sector == SECT_MOUNTAIN) tier = 2;
                                if (sector == SECT_LAVA) tier = 4;
                            }
                            assert(delivered_damage == int(base + 0.1 * base * tier));
                            assert(delivered_type == (tier == 4 ? SPLDAM_FIRE : SPLDAM_GENERIC));
                        }
                    }
                }
            }
        }
    }
    puts("Forms and Earth: ownership/persistence/conflicts, personal layers, single-layer mitigation and terrain-free Maul passed.");
}
'''.replace('REGISTER_FORMS', '\n'.join(registrations))

build = ROOT / 'bin/tests/elemental-forms'
build.mkdir(parents=True, exist_ok=True)
cpp, binary = build / 'harness.cpp', build / 'harness'
cpp.write_text(prelude + '\n'.join(extract_function(file, sig) for file, sig in functions) + gate + snapshot_restore + tick + skin_path + driver)
subprocess.run(['g++', '-std=c++20', '-g', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                '-I' + str(ROOT / 'src'), str(cpp), str(HARNESS_STUBS),
                str(ROOT / 'src/player/player_snapshot_codec.c'),
                '-Wl,--gc-sections', '-lbsd', '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True)
