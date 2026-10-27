#!/usr/bin/env python3
"""Execute the battleprep command against eligibility, capacity and busy-state cases."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function

HARNESS = r'''
#include "cmd/battleprep.c"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>

Skill skills[MAX_SKILLS];
room_data rooms[1]{};
P_room world = rooms;
P_char character_list = nullptr;
static P_char target;
static std::string output;
static bool book_present = true, item_pending = false;
static int advances, epic_grants, stops;
static player_component_mask_t dirt;

void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[512]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args); output += text;
}
void logit(const char *, const char *, ...) {}
P_char get_char_vis(P_char, const char *) { return target; }
char *one_argument(const char *text, char *word) {
    while (*text == ' ') ++text;
    while (*text && *text != ' ') *word++ = *text++;
    *word = 0; return const_cast<char *>(text);
}
bool item_action_active(P_char) { return item_pending; }
bool chaos_kit_equipment_ready(P_char, P_char) { return false; }
void equip_chaos_kit(P_char) {}
void StopCasting(P_char ch) { REMOVE_BIT(ch->specials.affected_by2, AFF2_CASTING); }
void event_abort_spell(P_char, P_char, P_obj, void *) {}
void event_acidimmolate(P_char, P_char, P_obj, void *) {}
void event_magma_burst(P_char, P_char, P_obj, void *) {}
void event_poison(P_char, P_char, P_obj, void *) {}
static int cleared_effects;
void affect_from_char(P_char, int effect) { assert(effect == SPELL_MAGMA_BURST || effect == FIRST_POISON); ++cleared_effects; }
void gmcp_char_vitals(P_char) {}
nevent_handle nevent_handle_from_event(P_nevent event) { return {event, event->sequence}; }
nevent_cancel_result nevent_cancel(nevent_handle handle) {
    auto **cursor = &handle.event->ch->nevents;
    while (*cursor && *cursor != handle.event) cursor = &(*cursor)->next_char_nev;
    assert(*cursor == handle.event);
    *cursor = handle.event->next_char_nev;
    return nevent_cancel_result::canceled;
}
void disarm_char_nevents(P_char, event_func_type) {}
void stop_singing(P_char ch) { REMOVE_BIT(ch->specials.affected_by3, AFF3_SINGING); }
size_t item_actions_pending(P_char) { return item_pending ? 1 : 0; }
void item_actions_stop(P_char) { item_pending = false; }
void tranquilize(P_char, P_char victim) { victim->specials.fighting = nullptr; SET_POS(victim, STAT_SLEEPING + GET_POS(victim)); }
int get_from_q(txt_q *queue, char *) {
    if (!queue->head) return 0;
    queue->head = queue->tail = nullptr; return 1;
}
void flush_input_queue(P_desc d) {
    d->input.head = d->input.tail = nullptr;
    d->buflen = 0; d->buf[0] = 0;
}
char affect_total(P_char, int) { return 0; }
int panic_corruption_int(const char *, const char *, ...) { abort(); }
void advance_to_level(P_char ch, int level) {
    for (int stat = 0; stat < MAX_ATTRIBUTES; ++stat) assert(ch->base_stats[stat] == 100);
    assert(level == MAXLVLMORTAL); ++advances; ch->player.level = level;
}
int grant_epic_skills_without_specialization(P_char ch) {
    ++epic_grants;
    if (ch->player.m_class == CLASS_CLERIC) assert(ch->only.pc->skills[SKILL_KICK].learned == 40);
    return 0;
}
void mark_player_dirty_components(int, player_component_mask_t components) { dirt |= components; }
void stop_memorizing(P_char ch, memorization_stop_reason reason) {
    assert(reason == memorization_stop_reason::voluntary); ++stops;
    REMOVE_BIT(ch->specials.affected_by2, AFF2_MEMORIZING);
}
int max_spells_in_circle(P_char ch, int circle) { return circle <= get_max_circle(ch) ? 2 : 0; }
P_obj SpellInSpellBook(P_char, int, int) { static obj_data book{}; return book_present ? &book : nullptr; }
float get_property(const char *, double fallback) { return fallback; }

// UTILITY

static void command(P_char staff, const char *operation) {
    char text[256]; snprintf(text, sizeof(text), "%s", operation);
    output.clear(); do_battleprep(staff, text, 0);
}
int main() {
    char_data staff{}, victim{}, attacker{};
    pc_only_data staff_pc{}, pc{};
    descriptor_data connection{};
    staff.only.pc = &staff_pc; staff.player.level = OVERLORD;
    staff.player.name = const_cast<char *>("Operator");
    victim.only.pc = &pc; victim.player.name = const_cast<char *>("Battler");
    victim.player.m_class = CLASS_CLERIC; victim.player.race = RACE_HUMAN;
    victim.player.level = 1; victim.specials.position = STAT_NORMAL + POS_STANDING;
    victim.desc = &connection; connection.connected = CON_PLAYING;
    victim.points.max_hit = 300; victim.points.max_mana = 200; victim.points.max_vitality = 90;
    rooms[0].people = target = &victim;
    const int cls = flag2idx(CLASS_CLERIC) - 1;
    skills[SKILL_KICK].m_class[cls].rlevel[0] = 1;
    skills[SKILL_KICK].m_class[cls].maxlearn[0] = 40;
    skills[SKILL_BASH].m_class[cls].rlevel[0] = 57;
    skills[SKILL_BASH].m_class[cls].maxlearn[0] = 100;
    skills[SPELL_CURE_LIGHT].targets = TAR_SPELL;
    skills[SPELL_CURE_LIGHT].m_class[cls].rlevel[0] = 1;
    skills[SPELL_CURE_LIGHT].m_class[cls].maxlearn[0] = 85;
    skills[SPELL_HEAL].targets = TAR_SPELL;
    skills[SPELL_HEAL].m_class[cls].rlevel[0] = MAX_CIRCLE + 1;
    skills[SPELL_HEAL].m_class[cls].maxlearn[0] = 100;
    pc.skills[SKILL_BASH].learned = pc.skills[SKILL_BASH].taught = 100;
    command(&staff, "Battler baseline");
    assert(output.find("baseline ready at level 56") != std::string::npos);
    assert(advances == 1 && epic_grants == 1);
    assert(pc.skills[SKILL_KICK].learned == 40 && pc.skills[SKILL_KICK].taught == 40);
    assert(pc.skills[SKILL_BASH].learned == 0 && pc.skills[SPELL_HEAL].learned == 0);
    assert(pc.skills[SPELL_CURE_LIGHT].learned == 85);
    assert(GET_HIT(&victim) == 300 && GET_MANA(&victim) == 200 && GET_VITALITY(&victim) == 90);
    assert(dirt & PLAYER_COMPONENT_SKILLS);

    // An exact connected mortal is required; neither abbreviations nor staff,
    // dead, NPC, linkless, specialized or multiclass characters are modified.
    command(&staff, "Batt baseline"); assert(advances == 1);
    staff.player.level = OVERLORD - 1;
    command(&staff, "Battler baseline"); assert(advances == 1);
    staff.player.level = OVERLORD;
    victim.desc = nullptr; command(&staff, "Battler baseline"); assert(advances == 1);
    victim.desc = &connection;
    connection.connected = CON_MAIN_MENU;
    command(&staff, "Battler baseline"); assert(advances == 1);
    connection.connected = CON_PLAYING;
    victim.player.level = OVERLORD; command(&staff, "Battler baseline"); assert(advances == 1);
    victim.player.level = MAXLVLMORTAL;
    victim.specials.position = STAT_DEAD + POS_PRONE;
    command(&staff, "Battler baseline"); assert(advances == 1);
    victim.specials.position = STAT_NORMAL + POS_STANDING;
    victim.player.spec = 1; command(&staff, "Battler baseline"); assert(advances == 1);
    victim.player.spec = 0; victim.player.secondary_class = CLASS_WARRIOR;
    command(&staff, "Battler baseline"); assert(advances == 1);
    victim.player.secondary_class = 0;
    SET_BIT(victim.specials.act, ACT_ISNPC);
    command(&staff, "Battler baseline"); assert(advances == 1);
    REMOVE_BIT(victim.specials.act, ACT_ISNPC);

    // Incoming one-sided combat, casts and item windups also prevent preparation.
    victim.next_in_room = &attacker; attacker.specials.fighting = &victim;
    command(&staff, "Battler baseline"); assert(advances == 1);
    attacker.specials.fighting = nullptr;
    SET_BIT(victim.specials.affected_by2, AFF2_CASTING);
    command(&staff, "Battler baseline"); assert(advances == 1);
    REMOVE_BIT(victim.specials.affected_by2, AFF2_CASTING);
    item_pending = true; command(&staff, "Battler baseline"); assert(advances == 1);
    item_pending = false;
    SET_BIT(victim.specials.affected_by2, AFF2_MEMORIZING);
    command(&staff, "Battler baseline"); assert(advances == 1);

    affected_type first{}, second{}, third{};
    first.type = second.type = third.type = TAG_MEMORIZE;
    first.modifier = second.modifier = third.modifier = SPELL_CURE_LIGHT;
    first.next = &second; victim.affected = &first;
    command(&staff, "Battler spells");
    assert(output.find("2 newly prepared spells") != std::string::npos);
    assert((first.flags & MEMTYPE_FULL) && (second.flags & MEMTYPE_FULL) && stops == 1);
    assert(dirt & PLAYER_COMPONENT_AFFECTS);
    first.flags = 0; second.flags = MEMTYPE_FULL; second.next = &third;
    command(&staff, "Battler spells");
    assert(first.flags == 0 && third.flags == 0 && stops == 1); // no partial grant
    second.next = nullptr; second.modifier = SPELL_HEAL;
    command(&staff, "Battler spells"); assert(first.flags == 0 && stops == 1);
    second.modifier = MAX_SKILLS + 100;
    command(&staff, "Battler spells"); assert(first.flags == 0 && stops == 1);
    second.modifier = SPELL_CURE_LIGHT;
    victim.player.m_class = CLASS_SORCERER;
    skills[SPELL_CURE_LIGHT].m_class[flag2idx(CLASS_SORCERER) - 1] = skills[SPELL_CURE_LIGHT].m_class[cls];
    book_present = false;
    command(&staff, "Battler spells"); assert(first.flags == 0 && stops == 1);
    book_present = true;
    command(&staff, "Battler spells"); assert(first.flags & MEMTYPE_FULL); assert(stops == 2);

    // Slot and mana casters use their native resources, never prepared-copy grants.
    victim.player.m_class = CLASS_DRUID; first.flags = 0;
    command(&staff, "Battler spells"); assert(first.flags == 0 && stops == 2);
    victim.player.m_class = CLASS_PSIONICIST;
    command(&staff, "Battler spells"); assert(first.flags == 0 && stops == 2);
    victim.affected = nullptr;
    REMOVE_BIT(victim.specials.affected_by2, AFF2_MEMORIZING);
    victim.player.m_class = CLASS_DRUID;
    command(&staff, "Battler baseline");
    assert(victim.specials.undead_spell_slots[0] == 0);
    for (int circle = 1; circle <= MAX_CIRCLE; ++circle)
        assert(victim.specials.undead_spell_slots[circle] == 2);

    // Instrument and song IDs live outside the ordinary skill range.
    victim.player.m_class = CLASS_BARD;
    const int bard = flag2idx(CLASS_BARD) - 1;
    skills[INSTRUMENT_HARP].m_class[bard].rlevel[0] = 1;
    skills[INSTRUMENT_HARP].m_class[bard].maxlearn[0] = 90;
    skills[SONG_HEALING].m_class[bard].rlevel[0] = 15;
    skills[SONG_HEALING].m_class[bard].maxlearn[0] = 75;
    command(&staff, "Battler baseline");
    assert(pc.skills[INSTRUMENT_HARP].learned == 90 && pc.skills[SONG_HEALING].learned == 75);
    txt_block queued{};
    connection.input.head = connection.input.tail = &queued;
    connection.buflen = 4; strcpy(connection.buf,"cast");
    victim.specials.fighting = &attacker;
    attacker.specials.fighting = &staff; // unrelated fight must remain untouched
    SET_BIT(victim.specials.affected_by2, AFF2_CASTING | AFF2_MEMORIZING);
    SET_BIT(victim.specials.affected_by3, AFF3_SINGING);
    item_pending = true;
    command(&staff,"status Battler");
    assert(output.find("Battler pending") != std::string::npos && item_pending && connection.input.head);
    command(&staff,"stop Battler Missing");
    assert(output.find("Battler quiet") != std::string::npos && output.find("Missing missing") != std::string::npos);
    assert(!connection.input.head && !connection.buflen && !connection.buf[0]);
    assert(!IS_CASTING(&victim) && !SINGING(&victim) && !item_pending && !victim.specials.fighting);
    assert(attacker.specials.fighting == &staff);
    victim.desc = nullptr;
    command(&staff,"stop Battler");
    assert(output.find("Battler quiet") != std::string::npos); // linkdead actors can still be stopped
    nevent_data outgoing{}, incoming{}, poison{}, unrelated{};
    outgoing.ch = &victim; outgoing.victim = &attacker; outgoing.func = event_acidimmolate;
    incoming.ch = &attacker; incoming.victim = &victim; incoming.func = event_magma_burst;
    short poison_type = FIRST_POISON;
    poison.ch = &victim; poison.victim = &attacker; poison.func = event_poison; poison.data = &poison_type;
    unrelated.ch = &attacker; unrelated.victim = &staff; unrelated.func = event_acidimmolate;
    victim.nevents = &outgoing; outgoing.next_char_nev = &poison;
    attacker.nevents = &incoming; incoming.next_char_nev = &unrelated;
    character_list = &victim; victim.next = &attacker;
    SET_POS(&victim, STAT_NORMAL + POS_STANDING);
    command(&staff,"status Battler");
    assert(output.find("Battler pending") != std::string::npos);
    command(&staff,"stop Battler");
    assert(output.find("Battler quiet") != std::string::npos);
    assert(!victim.nevents && attacker.nevents == &unrelated);
    assert(cleared_effects == 2);
    assert(GET_STAT(&victim) == STAT_SLEEPING && GET_POS(&victim) == POS_SITTING);
    character_list = nullptr;
    puts("battleprep: native command guards, skill ceilings, resource baseline and atomic spell preparation passed");
}
'''

utility = "\n".join(extract_function(file, signature) for file, signature in (
    ("utility.c", "int BOUNDED(int a, int b, int c)"),
    ("utility.c", "int flag2idx(int flag)"),
    ("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "int GET_PRIME_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "int GET_SECONDARY_CLASS(P_char ch, uint m_class)"),
    ("utility.c", "ClassSkillInfo SKILL_DATA_ALL(P_char ch, int skill)"),
    ("memorize.c", "int get_max_circle(P_char ch)"),
    ("memorize.c", "int get_spell_circle(P_char ch, int spl)"),
    ("memorize.c", "bool book_class(P_char ch)"),
))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="battleprep-", dir=ROOT / "bin/tests") as directory:
    source, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    source.write_text(HARNESS.replace("// UTILITY", utility))
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-Isrc", str(source), "-o", str(binary)],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
