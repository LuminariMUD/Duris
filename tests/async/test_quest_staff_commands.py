#!/usr/bin/env python3
"""Execute the production quest inspection handlers under ASan/UBSan.

The real quest lookup and prototype lookups run against inert indexed fixtures.
Entity loaders abort; no server, database, or existing player state is used.
"""
from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "core/utility.h"
#include "world/db.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include <cassert>
#include <charconv>
#include <climits>
#include <cstring>
#include <sstream>
#include <vector>
P_index mob_index, obj_index;
P_room world;
zone_data *zone_table;
int top_of_mobt, top_of_objt, top_of_world, top_of_zone_table;
int number_of_quests;
quest_data quest_index[MAX_QUESTS];
Skill skills[MAX_SKILLS];
const char *item_types[] = {"UNDEFINED", "LIGHT", "\n"};
static std::string output;
void send_to_char(const char *text, P_char) { output += text; }
char *coin_stringv(int amount, int) {
    static std::string text;
    text = std::to_string(amount) + " copper coins";
    return text.data();
}
P_char read_mobile(int, int, bool) { abort(); }
P_obj read_object(int, int) { abort(); }
void extract_char(P_char) { abort(); }
void extract_obj(P_obj) { abort(); }
'''

DRIVER = r'''
static char_data staff;
static index_data mobiles[4], objects[3];
static room_data room;
static zone_data zones[2];
static char *text(const char *value) { return const_cast<char *>(value); }
static std::string run(int command, const std::string &argument) {
    output.clear(); std::string writable = argument;
    if(command == CMD_QVIEW) do_qview(&staff, writable.data(), command);
    else if(command == CMD_QREF || command == CMD_QINFO) do_qref(&staff, writable.data(), command);
    else do_qlist(&staff, writable.data(), command);
    return output;
}
static bool has(const std::string &value, const std::string &part) {
    return value.find(part) != std::string::npos;
}
static size_t count(const std::string &value, const std::string &part) {
    size_t found=0;
    for(size_t at=0; (at=value.find(part,at))!=std::string::npos; at+=part.size()) ++found;
    return found;
}
int main() {
    const int vnums[] = {0,100,200,201};
    for(int i=0;i<4;++i) {
        mobiles[i].virtual_number=vnums[i]; mobiles[i].desc2=text("the quest giver");
        mobiles[i].number=7; mobiles[i].limit=12;
    }
    for(int i=0;i<3;++i) {
        objects[i].virtual_number=i; objects[i].desc2=text("a quest token");
        objects[i].number=3; objects[i].limit=8;
    }
    mob_index=mobiles; obj_index=objects; top_of_mobt=3; top_of_objt=2;
    world=&room; top_of_world=0; zone_table=zones; top_of_zone_table=1;
    zones[0].number=17; zones[0].top=100;
    zones[1].number=83; zones[1].top=INT_MAX;
    room.zone=1; staff.in_room=0;
    SET_BIT(staff.specials.act,PLR_PAGING_ON);
    skills[3].name=text("quest skill");
    quest_msg_data message{text("help quest"), text("RAW $n response"), true, nullptr};
    goal_data wrong_type{QUEST_GOAL_ITEM_TYPE,0,nullptr};
    goal_data reward_exp{QUEST_GOAL_EXP,-1,nullptr};
    goal_data reward_skill{QUEST_GOAL_SKILL,3,&reward_exp};
    goal_data reward_item{QUEST_GOAL_ITEM,0,&reward_skill};
    goal_data coins{QUEST_GOAL_COINS,123,nullptr};
    goal_data duplicate{QUEST_GOAL_ITEM,0,&coins};
    goal_data give{QUEST_GOAL_ITEM,0,&duplicate};
    quest_complete_data last{text("LAST_COMPLETION"), &reward_item, nullptr,
                             false, nullptr, false, nullptr};
    quest_complete_data both{text("BOTH_COMPLETION"), &reward_item, &give,
                             true, text("RAW $n disappears"), true, &last};
    quest_complete_data unrelated{text("UNRELATED_COMPLETION"), nullptr, &wrong_type,
                                  false, nullptr, false, &both};
    // The boot loader can retain an unresolved giver at -1.
    quest_index[0]={-1,nullptr,&both};
    quest_index[1]={0,&message,nullptr};
    quest_index[2]={1,nullptr,nullptr};
    quest_index[3]={2,&message,&unrelated};
    number_of_quests=4;
    auto saved_mobiles=std::vector<index_data>(mobiles,mobiles+4);
    auto saved_objects=std::vector<index_data>(objects,objects+3);
    auto saved_quests=std::vector<quest_data>(quest_index,quest_index+4);

    for(int command : {CMD_QVIEW,CMD_QREF,CMD_QINFO,CMD_QLIST,CMD_HLQLIST}) {
        for(const char *bad : {"-1", "+1", "1x", "2147483648", "99999999999999999999",
                               "0 extra", "0 1 2", "?"})
            assert(has(run(command,bad),"Usage:"));
        if(command==CMD_QVIEW || command==CMD_QREF || command==CMD_QINFO) {
            assert(has(run(command,""),"Usage:"));
            assert(has(run(command,"0 1"),"Usage:"));
        }
    }
    assert(has(run(CMD_QVIEW,"99"),"No such mobile"));
    assert(has(run(CMD_QVIEW,"201"),"has no quests"));
    assert(has(run(CMD_QVIEW,"0"),"No completion rules"));
    std::string view=run(CMD_QVIEW," 200 \t");
    for(const char *part : {"Quest giver [200]", "Key: help quest (room)", "RAW $n response",
                            "Completion 3:", "BOTH_COMPLETION", "UNRELATED_COMPLETION",
                            "123 copper coins", "Skill [3] quest skill",
                            "Experience: -1 (dynamic reward)", "RAW $n disappears",
                            "Completion message (player)", "Completion message (room)"})
        assert(has(view,part));
    assert(count(view,"Item [0]")==4); // Two required copies and two reward occurrences.
    std::string refs=run(CMD_QREF,"0");
    assert(has(refs,"completion 2: GIVE, RECEIVE"));
    assert(has(refs,"completion 3: RECEIVE"));
    assert(!has(refs,"completion 1:") && !has(refs,"BOTH_COMPLETION"));
    std::string info=run(CMD_QINFO,"0");
    assert(has(info,"BOTH_COMPLETION") && has(info,"LAST_COMPLETION"));
    assert(!has(info,"UNRELATED_COMPLETION"));
    assert(count(info,"Give:")==2 && count(info,"Item [0]")==4);
    assert(has(run(CMD_QREF,"1"),"not used in any quests"));
    assert(has(run(CMD_QINFO,"99"),"No such object"));
    assert(has(run(CMD_QLIST,""),"[200]") && !has(run(CMD_QLIST,""),"[100]"));
    assert(run(CMD_HLQLIST,"")==run(CMD_QLIST,""));
    assert(has(run(CMD_QLIST,"0"),"0 completion rule(s)"));
    assert(has(run(CMD_QLIST,"0 100"),"[100]"));
    assert(run(CMD_QLIST,"0 200")==run(CMD_QLIST,"200 0"));
    assert(has(run(CMD_QLIST,"201"),"No quest givers found"));
    room.zone=0;
    assert(has(run(CMD_QLIST,""),"[0]") && has(run(CMD_QLIST,""),"[100]"));
    staff.in_room=-1;
    assert(has(run(CMD_QLIST,""),"no valid current zone"));
    assert(has(run(CMD_QLIST,"200"),"[200]"));
    staff.in_room=1;
    assert(has(run(CMD_QLIST,""),"no valid current zone"));
    staff.in_room=0; room.zone=USHRT_MAX;
    assert(has(run(CMD_QLIST,""),"no valid current zone"));
    room.zone=1;

    // Broken references must be printable, never indexed out of bounds.
    goal_data broken_skill{QUEST_GOAL_SKILL,MAX_SKILLS,nullptr};
    goal_data broken_type{QUEST_GOAL_ITEM_TYPE,-1,&broken_skill};
    goal_data broken_item{QUEST_GOAL_ITEM,999,&broken_type};
    last.receive=&broken_item;
    view=run(CMD_QVIEW,"200");
    assert(has(view,"Item [999] <missing object>"));
    assert(has(view,"Item type [-1] UNDEFINED"));
    assert(has(view,"<missing skill>"));
    broken_skill.number=-1;
    assert(has(run(CMD_QVIEW,"200"),"<missing skill>"));
    last.receive=&reward_item;

    for(int command : {CMD_QVIEW,CMD_QREF,CMD_QINFO,CMD_QLIST,CMD_HLQLIST}) {
        SET_BIT(staff.specials.act,ACT_ISNPC);
        assert(run(command,"0").empty());
        REMOVE_BIT(staff.specials.act,ACT_ISNPC);
    }
    assert(!memcmp(mobiles,saved_mobiles.data(),sizeof(mobiles)));
    assert(!memcmp(objects,saved_objects.data(),sizeof(objects)));
    assert(!memcmp(quest_index,saved_quests.data(),4*sizeof(quest_data)));

    // Full reports exceed the old fixed string buffer without silently losing rows.
    std::string long_name(150,'x'); mobiles[2].desc2=long_name.data();
    std::vector<quest_complete_data> many(700,both);
    for(size_t i=0;i<many.size();++i) many[i].next=i+1<many.size()?&many[i+1]:nullptr;
    quest_index[3].quest_complete=many.data();
    assert(count(run(CMD_QINFO,"0"),"BOTH_COMPLETION")==700);
    assert(has(run(CMD_QVIEW,"200"),"Completion 700:"));
    REMOVE_BIT(staff.specials.act,PLR_PAGING_ON);
    assert(has(run(CMD_QINFO,"0"),"requires paging"));
    assert(has(run(CMD_QVIEW,"0"),"No completion rules"));
    SET_BIT(staff.specials.act,PLR_PAGING_ON);
    number_of_quests=MAX_QUESTS;
    for(int i=0;i<number_of_quests;++i) quest_index[i]={2,nullptr,nullptr};
    assert(count(run(CMD_QLIST,"200"),"[200]")==MAX_QUESTS);
    REMOVE_BIT(staff.specials.act,PLR_PAGING_ON);
    assert(has(run(CMD_QLIST,"200"),"requires paging"));
    number_of_quests=0;
    assert(has(run(CMD_QLIST,"0 2147483647"),"No quest givers found"));
    mob_index=obj_index=nullptr; top_of_mobt=top_of_objt=-1;
    assert(has(run(CMD_QVIEW,"0"),"No such mobile"));
    assert(has(run(CMD_QREF,"0"),"No such object"));
    puts("quest staff command behavior: OK");
}
'''


def main():
    source = (ROOT / "src/world/quest.c").read_text()
    start = source.index("namespace\n{\nvoid quest_staff_output")
    handlers = source[start:source.index("int quester(", start)]
    interp = (ROOT / "src/cmd/interp.c").read_text()
    header = (ROOT / "src/cmd/interp.h").read_text()
    names = re.findall(r'"([^\"]+)"', interp.split("const char *command[MAX_CMD] = {")[1].split("};")[0])
    for name in ("qview", "qref", "qinfo", "qlist", "hlqlist"):
        number = int(re.search(rf"#define CMD_{name.upper()} (\d+)", header)[1])
        assert names[number - 1] == name
        assert re.search(rf"CMD_Y\(CMD_{name.upper()}, STAT_DEAD \+ POS_PRONE, do_\w+, IMMORTAL, FALSE\)", interp)
    parts = [PRELUDE,
             extract_function("db.c", "int real_mobile(const int virt)"),
             extract_function("db.c", "int real_object(const int virt)"),
             extract_function("utility.c", "void sprinttype(int type, const char *names[], char *result)"),
             extract_function("quest.c", "int binary_search(int num, int min, int max)"),
             extract_function("quest.c", "int find_quester_id(int num)"),
             handlers, DRIVER]
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quest-staff-", dir=ROOT / "bin/tests") as temporary:
        test, binary = Path(temporary) / "test.cpp", Path(temporary) / "test"
        test.write_text("\n".join(parts))
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
                        "-fsanitize=address,undefined", "-Isrc", str(test), str(HARNESS_STUBS),
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
