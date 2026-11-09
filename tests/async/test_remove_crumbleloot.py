#!/usr/bin/env python3
"""ASan/UBSan: public give/removal of equipment that crumbles on transfer."""
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, HARNESS_STUBS, extract_function

actobj = (SRC / 'actobj.c').read_text()
production = '\n'.join([
    extract_function('handler.c', 'bool obj_to_char('),
    extract_function('handler.c', 'P_obj find_live_object(').replace('live_objects', 'live'),
    extract_function('handler.c', 'void Decay('),
    extract_function('actobj.c', 'int wearing_invis('),
    actobj[actobj.index('#define REMOVE_SUCCESS'):actobj.index('int remove_item(')],
    extract_function('actobj.c', 'int remove_item('),
    extract_function('actobj.c', 'int remove_and_wear('),
    extract_function('actobj.c', 'void do_remove('),
    extract_function('actobj.c', 'void do_give('),
    extract_function('rogues.c', 'static int slip_fighting_penalty('),
    extract_function('rogues.c', 'void do_slip('),
    extract_function('magic.c', 'static bool give_soulbind_item('),
])
harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "magic/spells.h"
#include "item/encumbrance_policy.h"
#include "economy/currency_transaction.h"
#include "world/transport.h"
#include "classes/rogues.h"
#include "sql/sql.h"
#include "persistence/persistence_checkpoint.h"
#include "world/vnum.obj.h"
#include "cmd/interp.h"
#include <cassert>
#include <cstring>
#include <set>
#include <string>

static index_data indexes[1]{};
str_app_type str_app[52]{};
P_index obj_index = indexes;
P_index mob_index = indexes;
static room_data rooms[1]{};
P_room world = rooms;
static std::set<P_obj> live;
static std::set<int> effects;
static std::string output;
static int extracted, attached_notices;
static int saves, dirty_components;
static bool dummy, redirect_extract;
P_obj object_list = nullptr;
static P_char give_recipient;
static int give_triggers;
// COIN_TYPES
bool begin_coin_give_credit(P_char, P_char, const coin_debit_context &, bool) { assert(false); return false; }
bool submit_coin_debit(P_char, const coin_debit_context &) { assert(false); return false; }
bool is_number(char *) { return false; }
int coin_type(char *) { return -1; }
bool racewar(P_char, P_char) { return false; }
int real_mobile(int) { return 0; }
int real_object(int) { return -1; }
int total_carried_weight(P_char) { return 0; }
bool is_linked_to(P_char, P_char, ush_int) { return false; }
void mark_player_dirty_components(int, player_component_mask_t) { ++dirty_components; }
void artifact_switch_check(P_char, P_obj object) { volatile auto flags = object->extra_flags; (void)flags; }
int nq_action_check(P_char, P_char, char *) { return 0; }
char *coin_names[] = {nullptr, nullptr, nullptr, nullptr};
bool collector_presence_is_npc(P_char) { return false; }
bool flying_transport_cmd_give(P_char, P_char, char *) { return false; }
int flying_transport(P_char, P_char, int, char *) { return 0; }
P_char get_char_room_vis(P_char, char *) { return give_recipient; }
P_obj get_obj_in_list_vis(P_char, char *name, P_obj object) { return !strcmp(name, "robe") ? object : nullptr; }
int generic_find(char *, int, P_char, P_char *, P_obj *) { return 0; }
int container_total_weight(P_obj) { return 0; }
bool put(P_char, P_obj, P_obj, int, bool *) { assert(false); return false; }
int number(int low, int) { return low; }
float get_property(const char *, double fallback) { return fallback; }
int get_property(const char *, int fallback) { return fallback; }
int GET_CHAR_SKILL_P(P_char ch, int skill) { return ch->only.pc->skills[skill].learned; }
void notch_skill(P_char, int, int) {}
int writeCharacter(P_char, int, int) { ++saves; return 1; }
void obj_from_char(P_obj object) {
    assert(live.count(object) && OBJ_CARRIED(object));
    object->loc.carrying->carrying = nullptr; object->loc_p = LOC_NOWHERE;
}
void studioproc_give(P_char, P_obj object, P_char) {
    assert(live.count(object)); ++give_triggers;
}
void gmcp_items_changed(P_char) { ++attached_notices; }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_room(const char *text, int) { output += text; }
void act(const char *text, int, P_char, P_obj obj, void *, int) {
    if (obj) { assert(live.count(obj)); output += obj->short_description; }
    output += text;
}
void extract_obj(P_obj obj, int) {
    assert(live.erase(obj) == 1 && OBJ_NOWHERE(obj));
    ++extracted;
    if (object_list == obj) object_list = obj->next;
    delete obj;
}
bool training_dummy_is(P_char) { return dummy; }
void obj_to_room(P_obj object, int room) {
    if (redirect_extract) extract_obj(object, TRUE);
    else { object->loc_p=LOC_ROOM; object->loc.room=room; }
}
void obj_from_obj(P_obj) { assert(false); }
void obj_to_obj(P_obj, P_obj) { assert(false); }
void artifact_update_location_sql(P_obj) {}
void mark_char_or_owner_dirty(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void balance_affects(P_char) {}
void strip_holy_sword(P_char) {}
void CharWait(P_char, int) {}
int STAT_INDEX(int) { return 30; }
char *one_argument(const char *arg, char *word) {
    while (*arg == ' ') ++arg;
    while (*arg && *arg != ' ') *word++ = *arg++;
    *word = 0; while (*arg == ' ') ++arg; return const_cast<char *>(arg);
}
bool affected_by_spell(P_char, int spell) { return effects.count(spell); }
void affect_from_char(P_char, int spell) { effects.erase(spell); }
affected_type *affect_to_char(P_char, affected_type *af) { effects.insert(af->type); return nullptr; }
obj_affect *get_obj_affect(P_obj obj, int type) { return obj->affects && obj->affects->type == type ? obj->affects : nullptr; }
void obj_affect_remove(P_obj obj, obj_affect *) { obj->affects = nullptr; }
P_obj unequip_char(P_char ch, int slot, bool) {
    P_obj obj = ch->equipment[slot]; ch->equipment[slot] = nullptr;
    obj->loc_p = LOC_NOWHERE; return obj;
}
P_obj get_object_in_equip(P_char ch, char *, int *slot) { *slot = WEAR_BODY; return ch->equipment[*slot]; }
void execute_wear(P_char ch, P_obj obj, int slot, int, bool) {
    assert(live.count(obj) && !ch->equipment[slot]);
    ch->equipment[slot] = obj; obj->loc_p = LOC_WORN; obj->loc.wearing = ch;
}
// PRODUCTION
int main() {
    // Refused placements preserve the body; a dummy redirect may consume it.
    {
        char_data receiver{}; receiver.player.level=62; receiver.in_room=0;
        assert(!obj_to_char(nullptr, &receiver));
        P_obj object=new obj_data{}; live.insert(object); object_list=object;
        object->short_description=const_cast<char *>("redirected item");
        assert(obj_to_char(object, nullptr) && live.count(object));
        object->loc_p=LOC_ROOM;
        assert(obj_to_char(object, &receiver) && live.count(object));
        object->loc_p=LOC_NOWHERE; dummy=true;
        assert(obj_to_char(object, &receiver) && OBJ_ROOM(object));
        object->loc_p=LOC_NOWHERE; redirect_extract=true;
        assert(!obj_to_char(object, &receiver) && live.empty());
        dummy=redirect_extract=false;
    }
    for (int mode = 0; mode < 3; ++mode) {
        for (bool crumble : {false, true}) {
            for (bool trusted : {false, true}) {
                pc_only_data pc{}; char_data ch{}; ch.only.pc = &pc;
                ch.player.level = trusted ? 62 : 1;
                ch.in_room = 1;
                P_obj obj = new obj_data{}; live.insert(obj);
                obj->R_num = 0; indexes[0].virtual_number = 400218;
                obj->short_description = const_cast<char *>("test robe");
                obj->extra2_flags = crumble ? ITEM2_CRUMBLELOOT : 0;
                obj->bitvector = AFF_INVISIBLE;
                obj_affect enchant{}; enchant.type = SKILL_ENCHANT; enchant.data = SPELL_ARMOR;
                obj->affects = &enchant;
                effects = {TAG_PERMINVIS, SPELL_ARMOR, SPELL_BATTLEMAGE};
                execute_wear(&ch, obj, WEAR_BODY, 0, false);
                output.clear(); extracted = 0; attached_notices = 0;
                P_obj replacement = nullptr;
                if (mode == 2) {
                    replacement = new obj_data{}; live.insert(replacement);
                    assert(remove_and_wear(&ch, replacement, WEAR_BODY, 0, true));
                    assert(ch.equipment[WEAR_BODY] == replacement);
                } else {
                    char arg[8]; strcpy(arg, mode == 0 ? "robe" : "all");
                    do_remove(&ch, arg, 0);
                    assert(!ch.equipment[WEAR_BODY]);
                }
                assert(!effects.count(TAG_PERMINVIS) && !effects.count(SPELL_ARMOR));
                if (mode != 2) assert(!effects.count(SPELL_BATTLEMAGE));
                if (crumble && !trusted) {
                    assert(extracted == 1 && ch.carrying == nullptr && attached_notices == 0);
                    assert(output.find("crumble to dust") != std::string::npos);
                    assert(output.find("You are quite naked") == std::string::npos);
                } else {
                    assert(extracted == 0 && ch.carrying == obj && obj->affects == nullptr && attached_notices == 1);
                    assert(output.find("You stop using") != std::string::npos);
                    live.erase(obj); delete obj;
                }
                if (replacement) { live.erase(replacement); delete replacement; }
                assert(live.empty());
            }
        }
    }
    // An equipped crumble-on-transfer item must be retired once by decay,
    // without continuing through the destroyed inventory pointer.
    {
        char_data owner{}; pc_only_data pc{}; owner.only.pc=&pc;
        owner.in_room=NOWHERE; owner.player.level=1;
        P_obj object=new obj_data{}; live.insert(object); object_list=object;
        object->obj_uid=124; object->R_num=0; object->short_description=const_cast<char *>("decaying robe");
        object->extra2_flags=ITEM2_CRUMBLELOOT;
        execute_wear(&owner,object,WEAR_BODY,0,false); extracted=0;
        Decay(object);
        assert(extracted==1 && !owner.equipment[WEAR_BODY] && !owner.carrying && live.empty());
    }
    for (int transfer : {0, 1, 2}) for (bool crumble : {false, true}) for (bool trusted_receiver : {false, true})
    for (bool trusted_sender : {false, true}) {
        char_data sender{}, recipient{}; pc_only_data sender_pc{}, recipient_pc{};
        sender.only.pc = &sender_pc; recipient.only.pc = &recipient_pc;
        sender.player.name = const_cast<char *>("Sender"); recipient.player.name = const_cast<char *>("Recipient");
        sender.player.level = trusted_sender ? 62 : 1;
        sender_pc.skills[SKILL_SLIP].learned = 100;
        recipient.player.level = trusted_receiver ? 62 : 1;
        sender.in_room = recipient.in_room = 0; give_recipient = &recipient;
        P_obj object = new obj_data{}; live.insert(object); object_list = object;
        object->obj_uid = 123; object->R_num = 0;
        object->short_description = const_cast<char *>("test robe");
        object->extra2_flags = crumble ? ITEM2_CRUMBLELOOT : 0;
        sender.carrying = object; object->loc_p = LOC_CARRIED; object->loc.carrying = &sender;
        extracted = give_triggers = 0;
        char command[] = "robe recipient";
        saves = dirty_components = 0;
        if (transfer == 2) assert(give_soulbind_item(&sender, &recipient, object) == (!crumble || trusted_receiver));
        else if (transfer == 1) do_slip(&sender, command, 0);
        else do_give(&sender, command, 0);
        assert(!sender.carrying);
        if (transfer == 0) assert(dirty_components == 2);
        if (crumble && !trusted_receiver) {
            assert(extracted == 1 && !recipient.carrying && !give_triggers && live.empty());
            if (transfer == 1) assert(saves == 2);
        } else {
            assert(!extracted && recipient.carrying == object && give_triggers == (transfer ? 0 : 1));
            live.erase(object); delete object; object_list = nullptr;
        }
    }
    puts("crumbleloot give, single/all removal and replacement passed");
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='remove-crumbleloot-', dir=build) as td:
    source, binary = Path(td) / 'test.cpp', Path(td) / 'test'
    coin_types = extract_function('actobj.c', 'enum class coin_debit_action') + ';\n' + extract_function('actobj.c', 'struct coin_debit_context') + ';\n'
    source.write_text(harness.replace('// COIN_TYPES', coin_types).replace('// PRODUCTION', production))
    subprocess.run(['g++', '-std=c++20', '-g', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-fno-pie', '-no-pie', '-I' + str(SRC), '-I/usr/include/mysql',
                    str(source), str(HARNESS_STUBS), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True,
                   env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1'})
