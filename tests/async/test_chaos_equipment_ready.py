#!/usr/bin/env python3
"""Native readiness counts actual worn kit items, including duplicate requirements."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <map>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <string>
#include <vector>
struct chaos_kit_item { int slot, vnum; };
struct chaos_eq_profile { const chaos_kit_item *items; };
static const chaos_kit_item standard[] = {{1,100},{2,100},{PRIMARY_WEAPON,200},{SECONDARY_WEAPON,201},{WEAR_SHIELD,202},{HOLD,300},{0,0}};
static const chaos_kit_item monk_armor[] = {{1,100},{2,100},{0,0}};
static const chaos_kit_item enhanced[] = {{1,400},{0,0}};
static const chaos_kit_item chaos_eq_standard_optional_slots[] = {{WEAR_HORSE_BODY,500},{0,0}};
static const chaos_kit_item chaos_eq_enhanceable_optional_slots[] = {{WEAR_HORSE_BODY,600},{0,0}};
static chaos_eq_profile chaos_eq_profiles[CLASS_COUNT+1][2]{};
static index_data prototypes[9]{};
P_index obj_index = prototypes;
static bool enhanced_profile = false;
static std::string output;
int panic_corruption_int(const char *, const char *, ...) { abort(); }
int GET_CLASS(P_char ch, uint cls) { return ch->player.m_class & cls; }
static int free_hands = 0;
int equipment_pos_table[CUR_MAX_WEAR][3] = {{0,1,WEAR_FINGER_R},{0,1,WEAR_FINGER_L},
    {0,12,PRIMARY_WEAPON},{0,12,SECONDARY_WEAPON},{0,14,WEAR_SHIELD},{0,13,HOLD},{0,22,WEAR_HORSE_BODY}};
static std::vector<int> wear_categories;
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
int wear(P_char ch, P_obj object, int category, bool) {
    wear_categories.push_back(category);
    int slot = category==1 ? (ch->equipment[WEAR_FINGER_L] ? WEAR_FINGER_R : WEAR_FINGER_L) :
        category==12 ? (ch->equipment[PRIMARY_WEAPON] ? SECONDARY_WEAPON : PRIMARY_WEAPON) :
        category==14 ? WEAR_SHIELD : WEAR_HORSE_BODY;
    assert(!ch->equipment[slot]);
    if (category==12 || category==14) { assert(free_hands>0); --free_hands; }
    P_obj *link=&ch->carrying;
    while (*link!=object) link=&(*link)->next_content;
    *link=object->next_content; object->next_content=nullptr;
    ch->equipment[slot]=object; return 1;
}
int get_numb_free_hands(P_char) { return free_hands; }
int wield_item_size(P_char, P_obj) { return 1; }
static bool chaos_kit_weapon_slot(int slot) {
    return slot==PRIMARY_WEAPON || slot==SECONDARY_WEAPON || slot==THIRD_WEAPON || slot==FOURTH_WEAPON;
}
static chaos_kit_item chaos_kit_item_for_character(P_char, const chaos_kit_item &item) { return item; }
bool chaos_eq_use_enhanceable_profile() { return enhanced_profile; }
int flag2idx(int flags) { int index = 0; while (flags) { ++index; flags >>= 1; } return index; }
static const char *chaos_kit_skip_reason(P_char ch, int slot) {
    if (slot == WEAR_HORSE_BODY && ch->player.race != RACE_CENTAUR) return "no such slot";
    if (slot == PRIMARY_WEAPON && ch->player.m_class == CLASS_MONK) return "unarmed";
    return nullptr;
}
void send_to_char_f(P_char, const char *format, ...) {
    char text[512]; va_list args; va_start(args,format); vsnprintf(text,sizeof(text),format,args); va_end(args);
    output += text;
}
// NATIVE
int main() {
    char_data ch{}; pc_only_data pc{}; ch.only.pc=&pc;
    ch.player.name=const_cast<char *>("Battler"); ch.player.m_class=CLASS_WARRIOR;
    ch.player.race=RACE_HUMAN; ch.player.level=MAXLVLMORTAL;
    for (int cls : {flag2idx(CLASS_WARRIOR), flag2idx(CLASS_MONK)}) {
        chaos_eq_profiles[cls][0].items=standard; chaos_eq_profiles[cls][1].items=enhanced;
    }
    chaos_eq_profiles[flag2idx(CLASS_MONK)][0].items=monk_armor;
    obj_data ring{}, duplicate{}, weapon{}, horse{}, newring{}, newhorse{}, alternate{}, shield{}, book{};
    P_obj objects[] = {&ring,&duplicate,&weapon,&horse,&newring,&newhorse,&alternate,&shield,&book};
    int vnums[] = {100,100,200,500,400,600,201,202,300};
    for (int i=0;i<9;++i) { objects[i]->R_num=i; prototypes[i].virtual_number=vnums[i]; }
    weapon.type=alternate.type=ITEM_WEAPON; book.type=ITEM_SPELLBOOK;
    ch.equipment[WEAR_FINGER_L]=&ring; ch.equipment[PRIMARY_WEAPON]=&weapon; ch.equipment[WEAR_SHIELD]=&shield;
    ch.carrying=&alternate; alternate.next_content=&book;
    assert(!chaos_kit_equipment_ready(&ch,&ch)); // a missing second copy cannot pass
    assert(output.find("100 worn 1/2") != std::string::npos);
    book.next_content=&duplicate;
    assert(!chaos_kit_equipment_ready(&ch,&ch)); // carried is not worn
    ch.equipment[WEAR_FINGER_R]=&duplicate;
    book.next_content=nullptr;
    assert(chaos_kit_equipment_ready(&ch,&ch)); // slot permutation is legal
    ch.carrying=&book;
    assert(!chaos_kit_equipment_ready(&ch,&ch)); // unused alternatives must still exist
    ch.carrying=&alternate; free_hands=1;
    assert(!chaos_kit_equipment_ready(&ch,&ch)); // a usable free hand cannot be left empty
    free_hands=0;
    ch.player.race=RACE_CENTAUR;
    assert(!chaos_kit_equipment_ready(&ch,&ch));
    ch.equipment[WEAR_HORSE_BODY]=&horse;
    assert(chaos_kit_equipment_ready(&ch,&ch));
    ch.player.m_class=CLASS_MONK; ch.equipment[PRIMARY_WEAPON]=nullptr;
    assert(!chaos_kit_equipment_ready(&ch,&ch)); // shield would penalize unarmed skills
    ch.equipment[WEAR_SHIELD]=nullptr;
    assert(chaos_kit_equipment_ready(&ch,&ch));
    enhanced_profile=true;
    assert(!chaos_kit_equipment_ready(&ch,&ch)); // current server profile is authoritative
    ch.equipment[6]=&newring; ch.equipment[WEAR_HORSE_BODY]=&newhorse;
    assert(chaos_kit_equipment_ready(&ch,&ch));
    ch.player.level=1; assert(!chaos_kit_equipment_ready(&ch,&ch));
    assert(!chaos_kit_equipment_ready(nullptr,&ch));
    char_data outfitted{}; pc_only_data otherpc{}; outfitted.only.pc=&otherpc;
    outfitted.player.name=const_cast<char *>("Outfitted"); outfitted.player.level=MAXLVLMORTAL;
    outfitted.player.race=RACE_HUMAN; outfitted.player.m_class=CLASS_WARRIOR;
    obj_data inventory[6]{};
    int identities[] = {8,7,6,2,1,0}; // deliberately opposite the desired wear order
    for (int i=0;i<6;++i) {
        inventory[i].R_num=identities[i];
        inventory[i].type=i==0 ? ITEM_SPELLBOOK : (i==2 || i==3) ? ITEM_WEAPON : ITEM_ARMOR;
        inventory[i].next_content=i<5 ? &inventory[i+1] : nullptr;
    }
    outfitted.carrying=inventory; enhanced_profile=false; free_hands=2;
    equip_chaos_kit(&outfitted);
    assert((wear_categories==std::vector<int>{1,1,12,12}));
    assert(free_hands==0 && outfitted.carrying==&inventory[0] && inventory[0].next_content==&inventory[1]);
    assert(chaos_kit_equipment_ready(&outfitted,&outfitted));
    puts("CHAOS readiness: multiplicities, actual wear, anatomy, monk and selected profile passed");
}
'''
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="chaos-ready-", dir=ROOT / "bin/tests") as directory:
    source, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    native = extract_function("nanny.c", "void equip_chaos_kit(") + "\n" + extract_function("nanny.c", "bool chaos_kit_equipment_ready(")
    source.write_text(harness.replace("// NATIVE", native))
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    "-Isrc", str(source), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
