#!/usr/bin/env python3
"""Compile production CHAOS preparation/placement against deterministic objects.

Unit/runtime checks only: stub prototype loading and skill eligibility, no
server, database, Redis, networking, or durable state. Requires Linux g++ and
ASan/UBSan. Generated role/flag tables and actual preparation functions are used.
"""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, extract_function

NANNY = (SRC / "nanny.c").read_text()
BUILDER = NANNY[NANNY.index("struct chaos_kit_objects"):NANNY.index("static bool chaos_kit_skill_available")]
PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "account/chaos_eq_data.h"
#include "combat/chaos_config.h"
#include "item/item_movement_transaction.h"
#include "net/comm.h"
#include "sql/sql.h"
#include <array>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <string>

static index_data indexes[1]{};
P_index obj_index = indexes;
static obj_data loaded{};
static int required_level = 1;
static bool slot_available = true, usable = true, nesting = true, object_available = true;
static int extracts = 0, keywords = 0, book_additions = 0;
int equipment_pos_table[CUR_MAX_WEAR][3]{};
int flag2idx(int flags) { int i = 0; while (flags) { ++i; flags >>= 1; } return i; }
[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { abort(); }
int GET_CLASS(P_char actor, uint cls) { return actor->player.m_class & cls; }
int GET_LVL_FOR_SKILL(P_char, int) { return required_level; }
int get_spell_circle(P_char, int spell) { return spell == FIRST_SPELL ? 1 : 2; }
int AddSpellToSpellBook(P_char, P_obj, int) { ++book_additions; return 1; }
static void add_newbie_keyword(P_obj) { ++keywords; }
static int slot_check_level = -1;
bool has_eq_slot(P_char actor, int) { slot_check_level = actor->player.level; return slot_available; }
int can_char_use_item(P_char, P_obj) { return usable; }
P_obj read_object(int vnum, int) { indexes[0].virtual_number = vnum; return object_available ? &loaded : nullptr; }
void extract_obj(P_obj, int) { ++extracts; }
bool obj_can_nest(P_obj, P_obj) { return nesting; }
void obj_to_obj(P_obj object, P_obj bag) { object->loc_p = LOC_INSIDE; object->loc.inside = bag; bag->contains = object; }
void logit(const char *, const char *, ...) {}
static P_char restore_target = nullptr;
static bool chaos_enabled = true, restore_busy = false, restore_queued = false, restore_refused = false;
static int restore_calls = 0;
static std::string restore_message;
bool chaos_mud_enabled() { return chaos_enabled; }
P_char get_char_vis(P_char, const char *) { return restore_target; }
bool item_movement_transaction_player_busy(P_char) { return restore_busy; }
bool item_creation_grant_blocks_commands(P_char) { return restore_queued; }
static std::string sent;
void send_to_char(const char *message, P_char) { restore_message = message; sent += message; }
static void load_chaos_new_character_kit(P_char) {
    ++restore_calls;
    restore_busy = restore_queued = !restore_refused;
}
static bool enhanceable = false;
bool chaos_eq_use_enhanceable_profile() { return enhanceable; }
const char *where[MAX_WEAR];
struct name_row { const char *normal; };
static name_row race_names_table[LAST_RACE + 1], class_names_table[CLASS_COUNT + 1];
char *one_argument(const char *argument, char *first) {
    while (*argument == ' ') ++argument;
    size_t n = 0;
    for (; argument[n] && argument[n] != ' '; ++n) first[n] = argument[n];
    first[n] = 0;
    return const_cast<char *>(argument + n);
}
int training_dummy_parse_class(const char *token) { return !strcmp(token, "necromancer") ? CLASS_NECROMANCER : 0; }
int training_dummy_parse_race(const char *token) { return !strcmp(token, "githzerai") ? RACE_GITHZERAI : -1; }
static P_obj given = nullptr;
static P_char given_to = nullptr;
void obj_to_char(P_obj object, P_char recipient) { given = object; given_to = recipient; }
static room_data rooms[1]{};
P_room world = rooms;
static std::string wizlogged, sql_logged;
static int wizlog_level = -1;
static std::string format_line(const char *format, va_list args) {
    char line[256];
    vsnprintf(line, sizeof(line), format, args);
    return std::string(line) + "\n";
}
void wizlog(int level, const char *format, ...) {
    va_list args;
    va_start(args, format);
    wizlog_level = level;
    wizlogged += format_line(format, args);
    va_end(args);
}
void sql_log(P_char, const char *kind, const char *format, ...) {
    va_list args;
    va_start(args, format);
    sql_logged += std::string(kind) + ": " + format_line(format, args);
    va_end(args);
}
'''
KIT_STUB = r'''
// The staff kit bag's builder: records the stand-in it judged the kit against.
static obj_data kit_bag{}, kit_worn[2]{};
static bool build_succeeds = true, built_has_pc = false, built_npc = true;
static int build_calls = 0, built_level = -1;
static unsigned built_class = 0, built_race = 0;
static bool build_chaos_kit(P_char ch, chaos_kit_objects &kit) {
    ++build_calls;
    built_class = ch->player.m_class;
    built_race = ch->player.race;
    built_level = ch->player.level;
    built_has_pc = ch->only.pc != nullptr;
    built_npc = IS_NPC(ch);
    kit.append_root(&kit_bag);
    if (!build_succeeds)
        return false;
    kit.append_root(&kit_worn[0]);
    kit.append_root(&kit_worn[1]);
    return true;
}
'''
DRIVER = r'''
int main()
{
    pc_only_data pc{};
    pc.pid = 1;
    char_data actor{};
    actor.only.pc = &pc;
    actor.player.m_class = CLASS_WARRIOR;
    loaded.R_num = 0;
    loaded.type = ITEM_ARMOR;
    loaded.extra_flags = ITEM_TRANSIENT | ITEM_NODROP | ITEM_INVISIBLE | ITEM_SECRET |
                         ITEM_NOSHOW | ITEM_BURIED | ITEM_NORENT | ITEM_GLOW | ITEM_HUM;
    loaded.extra2_flags = ITEM2_CRUMBLELOOT | ITEM2_BLESS;
    loaded.affected[0] = {APPLY_CURSE, 10};
    loaded.affected[1] = {APPLY_STR, 3};
    loaded.affected[MAX_OBJ_AFFECT - 1] = {APPLY_CURSE, -7};
    loaded.bitvector2 = AFF2_GLOBE;
    prepare_chaos_kit_item(&actor, &loaded);
    assert(loaded.cost == 1 && keywords == 1);
    assert(loaded.extra_flags == (ITEM_GLOW | ITEM_HUM));
    assert(loaded.extra2_flags == ITEM2_BLESS);
    assert(loaded.affected[0].location == 0 && loaded.affected[0].modifier == 0);
    assert(loaded.affected[MAX_OBJ_AFFECT - 1].location == 0 && loaded.affected[MAX_OBJ_AFFECT - 1].modifier == 0);
    assert(loaded.affected[1].location == APPLY_STR && loaded.affected[1].modifier == 3);
    assert(loaded.bitvector2 == AFF2_GLOBE);
    prepare_chaos_kit_item(&actor, &loaded);
    assert(loaded.extra_flags == (ITEM_GLOW | ITEM_HUM) && loaded.bitvector2 == AFF2_GLOBE);
    loaded.type = ITEM_SPELLBOOK;
    indexes[0].virtual_number = MASTER_SPELLBOOK_VNUM;
    prepare_chaos_kit_item(&actor, &loaded);
    assert(book_additions == 0);
    indexes[0].virtual_number = 999;
    prepare_chaos_kit_item(&actor, &loaded);
    assert(book_additions == 1 && loaded.value[3] == 1);
    for (int level : {-1, 0, 1, 56, 57}) {
        required_level = level;
        assert(chaos_kit_skill_available(&actor, SKILL_TRAP) == (level > 0 && level <= 56));
    }
    required_level = 1;
    obj_data bag{};
    bag.type = ITEM_CONTAINER;
    loaded = {};
    loaded.R_num = 0;
    loaded.type = ITEM_ARMOR;
    loaded.wear_flags = ITEM_WEAR_NECK;
    equipment_pos_table[0][0] = ITEM_WEAR_NECK;
    equipment_pos_table[0][2] = WEAR_NECK_1;
    const chaos_kit_item wearable = {WEAR_NECK_1, 999};
    const chaos_kit_item support = {WEAR_NONE, 999};
    for (int cls : {CLASS_WARRIOR, CLASS_MONK, CLASS_THIEF, CLASS_SORCERER}) {
        actor.player.m_class = cls;
        loaded.bitvector2 = 0;
        chaos_kit_objects kit;
        assert(append_chaos_kit_item(&actor, &bag, &wearable, kit));
        assert(kit.count == 1 && kit.roots[0] == &loaded && bag.contains == nullptr);
        assert(bool(loaded.bitvector2 & AFF2_GLOBE) == (cls != CLASS_SORCERER));
        kit.count = 0;
    }
    actor.player.m_class = CLASS_MONK;
    for (int type : {ITEM_WEAPON, ITEM_FIREWEAPON, ITEM_MISSILE}) {
        loaded.type = type;
        chaos_kit_objects kit;
        assert(append_chaos_kit_item(&actor, &bag, &support, kit));
        assert(kit.count == 0 && bag.contains == nullptr);
    }
    loaded.type = ITEM_ARMOR;
    for (int slot : {PRIMARY_WEAPON, SECONDARY_WEAPON, THIRD_WEAPON, FOURTH_WEAPON}) {
        chaos_kit_objects kit;
        const chaos_kit_item weapon_slot = {slot, 999};
        assert(append_chaos_kit_item(&actor, &bag, &weapon_slot, kit));
        assert(!kit.count && !bag.contains);
    }
    loaded.wear_flags |= ITEM_WIELD;
    { chaos_kit_objects kit; assert(append_chaos_kit_item(&actor, &bag, &support, kit)); assert(!kit.count && !bag.contains); }
    loaded.wear_flags = ITEM_WEAR_NECK;
    actor.player.m_class = CLASS_WARRIOR;
    for (int failure = 0; failure < 3; ++failure) {
        chaos_kit_objects kit;
        object_available = failure != 0;
        usable = failure != 1;
        loaded.wear_flags = failure == 2 ? ITEM_WEAR_FEET : ITEM_WEAR_NECK;
        assert(!append_chaos_kit_item(&actor, &bag, &wearable, kit));
        assert(!kit.count && !bag.contains);
    }
    object_available = usable = true;
    loaded.wear_flags = ITEM_WEAR_NECK;
    slot_available = false;
    { chaos_kit_objects kit; assert(append_chaos_kit_item(&actor, &bag, &wearable, kit)); assert(!kit.count); }
    // A new character has no level yet; slots are judged at the CHAOS level.
    assert(slot_check_level == 56 && actor.player.level == 0);
    // CUR_MAX_WEAR is the highest valid equipment index, not the array size.
    const chaos_kit_item last_slot = {CUR_MAX_WEAR, 999};
    const chaos_kit_item invalid_slot = {MAX_WEAR, 999};
    { chaos_kit_objects kit; assert(append_chaos_kit_item(&actor, &bag, &last_slot, kit)); assert(!kit.count); }
    slot_available = true;
    equipment_pos_table[1][0] = ITEM_SPIDER_BODY;
    equipment_pos_table[1][2] = WEAR_SPIDER_BODY;
    loaded.wear_flags = ITEM_SPIDER_BODY;
    { chaos_kit_objects kit; assert(append_chaos_kit_item(&actor, &bag, &last_slot, kit)); assert(kit.count == 1); kit.count = 0; }
    { chaos_kit_objects kit; assert(!append_chaos_kit_item(&actor, &bag, &invalid_slot, kit)); assert(!kit.count); }
    loaded.wear_flags = ITEM_WEAR_NECK;
    nesting = false;
    { chaos_kit_objects kit; assert(!append_chaos_kit_item(&actor, &bag, &support, kit)); assert(!kit.count); }
    nesting = true;
    { chaos_kit_objects kit; assert(append_chaos_kit_item(&actor, &bag, &support, kit)); assert(!kit.count && bag.contains == &loaded); }

    // Staff recovery must use the normal grant once, and leave occupied or
    // nonplaying characters alone. Mortal callers and Chaos-off also refuse.
    char_data staff{};
    staff.only.pc = &pc;
    staff.player.level = MAXLVLMORTAL + 1;
    descriptor_data descriptor{};
    descriptor.connected = CON_PLAYING;
    actor.player.level = MAXLVLMORTAL;
    actor.desc = &descriptor;
    restore_target = &actor;
    restore_chaos_character_kit(nullptr, "target");
    restore_chaos_character_kit(&actor, "target");
    chaos_enabled = false;
    restore_chaos_character_kit(&staff, "target");
    chaos_enabled = true;
    restore_chaos_character_kit(&staff, "");
    restore_target = nullptr;
    restore_chaos_character_kit(&staff, "missing");
    restore_target = &actor;
    actor.desc = nullptr;
    restore_chaos_character_kit(&staff, "target");
    actor.desc = &descriptor;
    descriptor.connected = CON_RMOTD;
    restore_chaos_character_kit(&staff, "target");
    descriptor.connected = CON_PLAYING;
    actor.carrying = &loaded;
    restore_chaos_character_kit(&staff, "target");
    actor.carrying = nullptr;
    actor.equipment[MAX_WEAR - 1] = &loaded;
    restore_chaos_character_kit(&staff, "target");
    actor.equipment[MAX_WEAR - 1] = nullptr;
    restore_busy = true;
    restore_chaos_character_kit(&staff, "target");
    assert(restore_calls == 0);
    restore_busy = false;
    restore_refused = true;
    restore_chaos_character_kit(&staff, "target");
    assert(restore_calls == 1 && restore_message.find("could not be restored") != std::string::npos);
    restore_refused = false;
    restore_chaos_character_kit(&staff, "target");
    assert(restore_calls == 2 && restore_queued && restore_message.find("queued") != std::string::npos);
    restore_chaos_character_kit(&staff, "target");
    assert(restore_calls == 2);
    // The skip rules that creation and the staff kit bag share.
    actor.player.m_class = CLASS_MONK;
    assert(!strcmp(chaos_kit_skip_reason(&actor, PRIMARY_WEAPON), "monks fight unarmed"));
    actor.player.m_class = CLASS_WARRIOR;
    required_level = 0;
    assert(!strcmp(chaos_kit_skip_reason(&actor, SECONDARY_WEAPON), "no dual wield"));
    required_level = 1;
    assert(!chaos_kit_skip_reason(&actor, SECONDARY_WEAPON));
    slot_available = false;
    assert(!strcmp(chaos_kit_skip_reason(&actor, WEAR_LEGS), "no such slot"));
    assert(!chaos_kit_skip_reason(&actor, WEAR_NONE));
    slot_available = true;
    assert(!chaos_kit_skip_reason(&actor, WEAR_LEGS));

    // The staff kit bag takes the load command's level, a known class and race,
    // and judges the kit against a new character of exactly that class and race.
    char slot_names[MAX_WEAR][16];
    for (int slot = 0; slot < MAX_WEAR; ++slot) {
        snprintf(slot_names[slot], sizeof(slot_names[slot]), "slot%d", slot);
        where[slot] = slot_names[slot];
    }
    race_names_table[RACE_GITHZERAI].normal = "Githzerai";
    class_names_table[flag2idx(CLASS_NECROMANCER)].normal = "Necromancer";
    char staff_name[] = "Zusuk";
    staff.player.name = staff_name;
    char args[64] = "necromancer githzerai";
    staff.player.level = LESSER_G - 1;
    load_chaos_kit_bag(&staff, args);
    assert(!build_calls && restore_message.find("level of the load command") != std::string::npos);
    staff.player.level = OVERLORD;
    for (const char *bad : {"", "necromancer", "necromancer martian", "baker githzerai"}) {
        snprintf(args, sizeof(args), "%s", bad);
        load_chaos_kit_bag(&staff, args);
        assert(!build_calls && restore_message.find("Usage: chaos kitbag") != std::string::npos);
    }
    snprintf(args, sizeof(args), "necromancer githzerai");
    chaos_enabled = false;
    load_chaos_kit_bag(&staff, args);
    assert(!build_calls);
    chaos_enabled = true;
    const int extracts_before = extracts;
    build_succeeds = false;
    load_chaos_kit_bag(&staff, args);
    assert(build_calls == 1 && !given && extracts == extracts_before + 1);
    assert(restore_message.find("cannot be made") != std::string::npos);
    build_succeeds = true;
    required_level = 0; // no dual wield, so the necromancer's off-hand item is left out
    sent.clear();
    load_chaos_kit_bag(&staff, args);
    assert(build_calls == 2 && built_class == CLASS_NECROMANCER && built_race == RACE_GITHZERAI);
    assert(built_level == 0 && built_has_pc && !built_npc);
    assert(given == &kit_bag && given_to == &staff && extracts == extracts_before + 1);
    assert(kit_worn[0].loc.inside == &kit_bag && kit_worn[1].loc.inside == &kit_bag);
    assert(sent.find("standard CHAOS kit of a new Githzerai Necromancer: 2 worn items") != std::string::npos);
    int offhand = 0;
    for (const chaos_kit_item *item = chaos_eq_standard_necromancer; item->vnum; ++item)
        if (item->slot == SECONDARY_WEAPON)
            offhand = item->vnum;
    char left_out[96];
    snprintf(left_out, sizeof(left_out), "Left out: slot%d %6d  no dual wield\r\n", SECONDARY_WEAPON, offhand);
    assert(offhand && sent.find(left_out) != std::string::npos);
    assert(sent.find("Left out") == sent.rfind("Left out"));
    // Each bag is audited as a load is: the refusals above recorded nothing, an
    // OVERLORD's bag is in the wiz log only, a lower god's also on WIZLOG.
    assert(wizlogged.empty());
    assert(sql_logged == "wiz: Loaded the CHAOS kit of a Githzerai Necromancer\n");
    rooms[0].number = 22800;
    staff.player.level = LESSER_G;
    sql_logged.clear();
    load_chaos_kit_bag(&staff, args);
    assert(build_calls == 3 && wizlog_level == LESSER_G);
    assert(wizlogged == "Zusuk loaded the CHAOS kit of a Githzerai Necromancer in [22800]\n");
    assert(sql_logged == "wiz: Loaded the CHAOS kit of a Githzerai Necromancer\n");
    puts("CHAOS preparation/role/placement runtime passed");
}
'''


def main():
    functions = ["static void prepare_chaos_kit_item", "static bool chaos_kit_skill_available",
                 "static bool chaos_kit_has_eq_slot",
                 "static bool chaos_kit_weapon_slot", "static bool chaos_kit_fits_slot",
                 "static const char *chaos_kit_skip_reason",
                 "static bool append_chaos_kit_item", "void restore_chaos_character_kit",
                 "void load_chaos_kit_bag"]
    harness = "\n".join([PRELUDE, BUILDER, KIT_STUB, *[extract_function("nanny.c", sig) for sig in functions], DRIVER])
    with tempfile.TemporaryDirectory(prefix="chaos-kit-unit-") as directory:
        source, binary = Path(directory) / "kit.cpp", Path(directory) / "kit"
        source.write_text(harness)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-Isrc", "-D__NO_MYSQL__", "-Isrc/no_mysql",
                        str(source), "-o", str(binary)],
                       cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)

if __name__ == "__main__":
    main()
