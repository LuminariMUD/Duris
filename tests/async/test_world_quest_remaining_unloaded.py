#!/usr/bin/env python3
"""The remaining bartender quests are not shown while the quest history is loading.

sql_world_quest_can_do_another() answers below zero until a character's history has been
read. `score` and the Quest.Status message printed that value as "-1" (work item #13).
Both now leave the count out until it is known. This runs score's own lines and the
production json_build_quest_status() against a history that has not loaded, then against
one that has.
"""
from _paths import ROOT, SRC, HARNESS_STUBS, extract_function
import subprocess
import tempfile
from pathlib import Path

score = (SRC / "actinf.c").read_text()
count = score.index("int RemainingBartenderQuests")
start = score.rindex("if (IS_PC(ch))", 0, count)
score_lines = score[start:score.index("\n\t}\n", count) + len("\n\t}\n")]

SCORE_HARNESS = r'''
#include <cassert>
#include <cstdio>
#include <string>
constexpr int MAX_STRING_LENGTH = 4096;
struct character {};
using P_char = character *;
#define IS_PC(ch) true
int remaining;
int sql_world_quest_can_do_another(P_char) { return remaining; }
std::string shown;
void send_to_char(const char *text, P_char) { shown += text; }
void score(P_char ch)
{
	char buf[MAX_STRING_LENGTH];
''' + score_lines + r'''
}
int main()
{
	character ch;
	remaining = -1; // the history has not loaded
	score(&ch);
	assert(shown.empty());
	for (int known : { 0, 3 })
	{
		shown.clear();
		remaining = known;
		score(&ch);
		assert(shown == "&+yBartender Quests Remaining:&n " + std::to_string(known) + "\n");
	}
}
'''

JSON_HARNESS = r'''
#include "core/structs.h"
#include "core/json_utils.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/world_quest.h"
#include "world/world_quest_policy.h"
#include "player/player_save_pipeline.h"
#include "world/zone_story_quest_runtime.h"
#include "persistence/persistence_checkpoint.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <string>

int remaining;
int sql_world_quest_can_do_another(P_char) { return remaining; }
// Rendering may neither create/extract an actor nor discard a quest.
P_char read_mobile(int, int) { std::abort(); }
void extract_char(P_char) { std::abort(); }
void resetQuest(P_char) { std::abort(); }
int real_mobile(const int vnum) { return vnum == 100 ? 0 : vnum == 101 ? 1 : -1; }
int real_zone(const int vnum) { return vnum == 123 ? 0 : -1; }
int real_zone0(const int) { return 0; }
int real_room0(const int) { return 0; }
int real_room(const int) { return 0; }
static index_data profiles[2]{};
P_index mob_index = profiles;
static zone_data zones[1]{};
zone_data *zone_table = zones;
static room_data rooms[1]{};
P_room world = rooms;
int top_of_world = 0;
time_info_data time_info{};
const char *month_name[] = { "Moon" };
std::string shown;
void send_to_char(const char *text, P_char) { shown += text; }
void half_chop(char *, char *name, char *who) { *name = *who = 0; }
P_char ParseTarget(P_char, char *) { std::abort(); }
bool is_linked_to(P_char, P_char, ush_int) { std::abort(); }
float get_property(const char *, double fallback) { return fallback; }
int get_property(const char *, int fallback) { return fallback; }
int BOUNDED(int lo, int x, int hi) { return x < lo ? lo : x > hi ? hi : x; }
int sql_world_quest_done_already(P_char, int) { std::abort(); }
void mark_player_dirty_components(int, player_component_mask_t) { std::abort(); }
void gmcp_quest_status(P_char) { std::abort(); }
void gmcp_quest_status(P_char, world_quest_target_status) {}
world_quest_target_status world_quest_refresh(P_char, int) { return world_quest_target_status::valid; }
world_quest_target_check world_quest_policy_check_target(P_char, int, int, int, int, int, int) { std::abort(); }
void show_map_at(P_char, int) { std::abort(); }
namespace zone_story_quest_runtime {
zone_story_quest_feature::service *service() { return nullptr; }
std::string render_daily(P_char, bool, std::string *) { std::abort(); }
}
''' + extract_function("world_quest.c", "static int world_quest_share_limit(") + "\n" + extract_function("world_quest.c", "void do_quest(") + "\n" + extract_function("world_quest.c", "void world_quest_describe(") + r'''
static cJSON *quest_status(P_char ch)
{
    char *text = json_build_quest_status(ch, world_quest_target_status::valid);
    assert(text);
    cJSON *status = cJSON_Parse(text);
    json_free_string(text);
    assert(status && cJSON_GetObjectItem(status, "active"));
    return status;
}
int main()
{
    static char_data ch{};
    static pc_only_data pc{};
    ch.only.pc = &pc;
    remaining = -1;
    cJSON *status = quest_status(&ch);
    assert(cJSON_IsFalse(cJSON_GetObjectItem(status, "active")));
    assert(!cJSON_HasObjectItem(status, "remaining"));
    cJSON_Delete(status);
    for (int known : {0, 3}) {
        remaining = known;
        status = quest_status(&ch);
        assert(cJSON_GetObjectItem(status, "remaining")->valueint == known);
        cJSON_Delete(status);
    }
    profiles[0].desc2 = const_cast<char *>("a bartender");
    profiles[1].desc2 = const_cast<char *>("a bronze guardian");
    zones[0].name = const_cast<char *>("Local Wood");
    pc.pid = pc.quest_receiver = 7;
    pc.quest_active = 1; pc.quest_giver = 100; pc.quest_mob_vnum = 101;
    pc.quest_zone_number = 123; pc.quest_kill_original = 3; pc.quest_kill_how_many = 1;
    for (int type : {FIND_AND_ASK, FIND_AND_KILL}) {
        pc.quest_type = type;
        const auto before = pc;
        shown.clear(); do_quest(&ch, const_cast<char *>(""), 0);
        assert(shown.find("a bronze guardian") != std::string::npos);
        assert(shown.find("Local Wood") != std::string::npos);
        assert(shown.find(type == FIND_AND_ASK ? "Go ask " : "Go kill 3 ") != std::string::npos);
        if (type == FIND_AND_KILL) assert(shown.find("(2 left)") != std::string::npos);
        assert(!memcmp(&before, &pc, sizeof(pc)));
        status = quest_status(&ch);
        const std::string target = cJSON_GetObjectItem(status, "target")->valuestring;
        assert(target.find("a bronze guardian") != std::string::npos);
        assert(target.find("Local Wood") != std::string::npos);
        cJSON_Delete(status);
        assert(!memcmp(&before, &pc, sizeof(pc)));
    }
    // Missing details cannot erase paid or completed work.
    for (int missing = 0; missing < 4; ++missing) {
        pc.quest_giver = missing == 0 ? 999 : 100;
        pc.quest_mob_vnum = missing == 1 ? 999 : 101;
        profiles[1].desc2 = missing == 2 ? nullptr : const_cast<char *>("a bronze guardian");
        pc.quest_zone_number = missing == 3 ? 999 : 123;
        pc.quest_accomplished = 0;
        const auto before = pc;
        shown.clear(); do_quest(&ch, const_cast<char *>(""), 0);
        assert(shown.find("gave you the following quest") != std::string::npos);
        status = quest_status(&ch);
        if (missing != 0) {
            assert(shown.find("details are unavailable") != std::string::npos);
            assert(std::string(cJSON_GetObjectItem(status, "target")->valuestring) ==
                   "Ask a bartender to check your task.");
        }
        cJSON_Delete(status);
        assert(!memcmp(&before, &pc, sizeof(pc)));

        pc.quest_accomplished = 1;
        const auto completed = pc;
        shown.clear(); do_quest(&ch, const_cast<char *>(""), 0);
        assert(shown.find("already finished") != std::string::npos);
        status = quest_status(&ch);
        assert(std::string(cJSON_GetObjectItem(status, "target")->valuestring) ==
               "Task complete. Return to your quest giver.");
        assert(!cJSON_HasObjectItem(status, "zoneNumber"));
        cJSON_Delete(status);
        assert(!memcmp(&completed, &pc, sizeof(pc)));
    }

}
'''

with tempfile.TemporaryDirectory(prefix="duris-quest-remaining-") as directory:
    temp = Path(directory)
    (temp / "score.cpp").write_text(SCORE_HARNESS)
    (temp / "json.cpp").write_text(JSON_HARNESS)
    flags = ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g",
             "-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
    subprocess.run(flags + [str(temp / "score.cpp"), "-o", str(temp / "score")], check=True)
    subprocess.run([str(temp / "score")], check=True)
    subprocess.run(
        flags + ["-ffunction-sections", "-fdata-sections", f"-I{SRC}", str(temp / "json.cpp"),
                 str(SRC / "json_utils.c"), str(SRC / "core/safe_format.c"), str(HARNESS_STUBS),
                 "-Wl,--gc-sections", "-lcjson", "-o",
                 str(temp / "json")],
        check=True,
    )
    subprocess.run([str(temp / "json")], check=True)

print("world quest remaining count and read-only text/JSON presentation regressions passed")
