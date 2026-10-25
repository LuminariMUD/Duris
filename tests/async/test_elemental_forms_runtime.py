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
static int aff_vers, short_size = sizeof(short), int_size = sizeof(int), long_size = sizeof(long);
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
void send_to_char(const char *text, P_char) { output += text; }
void act(const char *, int, P_char, P_obj, void *, int) {}
bool NewSaves(P_char, int, int) { return false; }
bool has_innate(P_char, int) { return false; }
int number(int low, int) { return low; }
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
'''

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
    ('magic.c', 'const char *elemental_aura_failure_message('),
    ('magic.c', 'void spell_elemental_aura('),
    ('psionics.c', 'void spell_fire_aura('),
    ('magic.c', 'void spell_air_form('),
    ('magic.c', 'void spell_earth_form('),
    ('magic.c', 'void spell_fire_form('),
    ('magic.c', 'void spell_water_form('),
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
bool completion_allowed(P_char ch, int spell) {
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
            while (caster.affected) {
                wear_off_message(&caster, caster.affected);
                affect_remove(&caster, caster.affected);
            }
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
    puts("Elemental forms: spec/self registration, terrain, exact effects, conflict preflight, ownership, wear-off and persistence passed.");
}
'''.replace('REGISTER_FORMS', '\n'.join(registrations))

build = ROOT / 'bin/tests/elemental-forms'
build.mkdir(parents=True, exist_ok=True)
cpp, binary = build / 'harness.cpp', build / 'harness'
cpp.write_text(prelude + '\n'.join(extract_function(file, sig) for file, sig in functions) + gate + driver)
subprocess.run(['g++', '-std=c++20', '-g', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                '-I' + str(ROOT / 'src'), str(cpp), str(HARNESS_STUBS),
                '-Wl,--gc-sections', '-lbsd', '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True)
