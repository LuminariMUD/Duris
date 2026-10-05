#!/usr/bin/env python3
"""The remaining bartender quests are not shown while the quest history is loading.

sql_world_quest_can_do_another() answers below zero until a character's history has been
read. `score` and the Quest.Status message printed that value as "-1" (work item #13).
Both now leave the count out until it is known. This runs score's own lines and the
production json_build_quest_status() against a history that has not loaded, then against
one that has.
"""
from _paths import SRC
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

#include <cassert>

int remaining;
int sql_world_quest_can_do_another(struct char_data *) { return remaining; }
// An inactive quest names no target, so none of these is called.
P_char read_mobile(int, int) { return nullptr; }
int real_mobile(const int) { return -1; }
int real_zone0(const int) { return 0; }
void extract_char(P_char) {}
struct zone_data *zone_table;
struct time_info_data time_info;
const char *month_name[] = { "" };

static cJSON *quest_status(struct char_data *ch)
{
	char *text = json_build_quest_status(ch);
	assert(text);
	cJSON *status = cJSON_Parse(text);
	json_free_string(text);
	assert(status && cJSON_IsFalse(cJSON_GetObjectItem(status, "active")));
	return status;
}

int main()
{
	static struct char_data ch;
	static struct pc_only_data pc;
	ch.only.pc = &pc;

	remaining = -1; // the history has not loaded
	cJSON *status = quest_status(&ch);
	assert(!cJSON_HasObjectItem(status, "remaining"));
	cJSON_Delete(status);

	for (int known : { 0, 3 })
	{
		remaining = known;
		status = quest_status(&ch);
		assert(cJSON_GetObjectItem(status, "remaining")->valueint == known);
		cJSON_Delete(status);
	}
}
'''

with tempfile.TemporaryDirectory(prefix="duris-quest-remaining-") as directory:
    temp = Path(directory)
    (temp / "score.cpp").write_text(SCORE_HARNESS)
    (temp / "json.cpp").write_text(JSON_HARNESS)
    flags = ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror"]
    subprocess.run(flags + [str(temp / "score.cpp"), "-o", str(temp / "score")], check=True)
    subprocess.run([str(temp / "score")], check=True)
    subprocess.run(
        flags + ["-ffunction-sections", "-fdata-sections", f"-I{SRC}", str(temp / "json.cpp"),
                 str(SRC / "json_utils.c"), "-Wl,--gc-sections", "-lcjson", "-o",
                 str(temp / "json")],
        check=True,
    )
    subprocess.run([str(temp / "json")], check=True)

print("world quest remaining count regressions passed")
