#!/usr/bin/env python3
"""Encrusting guild-store gear keeps its buyer binding (#677).

Compiles the production do_encrust() under ASan/UBSan with object and
character services controlled by the fixture, and checks the replacement with
the production binding predicate. Ordinary gear stays unbound. Store gear
creation, wear and persistence are covered by their own tests.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function, source

HARNESS = r'''
// INCLUDES
#include "kingdom/kingdom_store_piece.h"
#include "combat/chaos_materials.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>

static index_data index_fixture[3]{};
P_index obj_index = index_fixture;
static std::vector<P_obj> extracted;
static std::vector<P_obj> objects;
static P_obj given;
static P_obj carried[2];

static P_obj make_obj(int rnum, const char *name)
{
	P_obj obj = new obj_data{};
	obj->R_num = rnum;
	obj->name = const_cast<char *>(name);
	obj->short_description = const_cast<char *>(name);
	obj->description = const_cast<char *>(name);
	objects.push_back(obj);
	return obj;
}

P_obj read_object(int nr, int type)
{
	assert(nr == 1251 && type == VIRTUAL);
	return make_obj(2, "encrusted");
}
P_obj get_obj_in_list_vis(P_char, const char *name, P_obj, bool)
{
	for (P_obj obj : carried)
		if (!std::strcmp(obj->name, name))
			return obj;
	return nullptr;
}
void extract_obj(P_obj obj, int) { extracted.push_back(obj); }
bool obj_to_char(P_obj obj, P_char)
{
	given = obj;
	return true;
}
int number(int low, int) { return low; }
char *str_dup(const char *text) { return strdup(text); }
void CharWait(P_char, int) {}
int GET_CHAR_SKILL_P(P_char, int skill) { return skill == SKILL_ENCRUST ? 100 : 0; }
char *one_argument(const char *argument, char *first)
{
	while (*argument == ' ')
		argument++;
	while (*argument && *argument != ' ')
		*first++ = *argument++;
	*first = '\0';
	return const_cast<char *>(argument);
}
bool isname(const char *word, const char *list) { return std::strstr(list, word) != nullptr; }
void set_keywords(P_obj obj, const char *text) { obj->name = str_dup(text); obj->str_mask |= STRUNG_KEYS; }
void set_short_description(P_obj obj, const char *text) { obj->short_description = str_dup(text); obj->str_mask |= STRUNG_DESC2; }
void set_long_description(P_obj obj, const char *text) { obj->description = str_dup(text); obj->str_mask |= STRUNG_DESC1; }
bool chaos_material_pouch_available(P_char) { return false; }
bool chaos_material_pouch_record_generated(P_char, const chaos_material_pouch_usage *, int) { return false; }
void chaos_material_pouch_report_generated_failure(P_char, const char *) {}
void set_encrust_affect(P_obj, int) {}
void describe_encrusted_enhanced(P_obj) {}
bool account_bound_reward_owner(P_char, P_obj) { return false; }

// FUNCTIONS

static P_obj encrust(P_char ch, const char *binding, bool rejected = false)
{
	carried[0] = make_obj(0, "sword");
	carried[0]->type = ITEM_WEAPON;
	carried[0]->action_description = const_cast<char *>(binding);
	carried[1] = make_obj(1, "jewel");
	carried[1]->value[6] = 1;
	given = nullptr;
	extracted.clear();
	char argument[] = "sword jewel";
	do_encrust(ch, argument, 0);
	if (rejected)
		assert(!given && extracted.empty());
	else
		assert(given && extracted.size() == 2);
	return given;
}

int main()
{
	index_fixture[0].virtual_number = 1000;
	index_fixture[1].virtual_number = ENCRUST_VNUM_BEGIN;
	index_fixture[2].virtual_number = 1251;

	char_data maker{};
	maker.player.name = const_cast<char *>("Maker");

	char token[KINGDOM_CRAFT_BIND_TOKEN_LEN];
	assert(kingdom_craft_bind_token(1042, token, sizeof(token)));
	char_data buyer{}, other{};
	pc_only_data buyer_pc{}, other_pc{};
	buyer.only.pc = &buyer_pc;
	other.only.pc = &other_pc;
	buyer.only.pc->pid = 1042;
	other.only.pc->pid = 77;

	P_obj bound = encrust(&maker, token);
	assert(kingdom_store_bound(bound));
	assert(kingdom_store_piece_owner(&buyer, bound));
	assert(!kingdom_store_piece_owner(&other, bound));
	assert(can_equip_soulbound_item(&buyer, bound, false));
	assert(!can_equip_soulbound_item(&other, bound, false));
	assert(IS_SET(bound->str_mask, STRUNG_DESC3));
	assert(bound->action_description != token);

	P_obj ordinary = encrust(&maker, nullptr);
	assert(!kingdom_store_bound(ordinary));
	assert(!IS_SET(ordinary->str_mask, STRUNG_DESC3));
	assert(can_equip_soulbound_item(&other, ordinary, false));
	P_obj malformed = encrust(&maker, "kingdom-bound-invalid");
	assert(kingdom_store_bound(malformed));
	assert(!can_equip_soulbound_item(&buyer, malformed, false));
	assert(!can_equip_soulbound_item(&other, malformed, false));
	index_fixture[0].virtual_number = VOBJ_KINGDOM_CRAFT_BLANK;
	assert(!encrust(&maker, nullptr, true));
	assert(!encrust(&maker, "legacy description without a buyer", true));
	for (P_obj obj : objects)
	{
		if (obj->str_mask & STRUNG_KEYS) free(obj->name);
		if (obj->str_mask & STRUNG_DESC1) free(obj->description);
		if (obj->str_mask & STRUNG_DESC2) free(obj->short_description);
		if (obj->str_mask & STRUNG_DESC3) free(obj->action_description);
		delete obj;
	}
	std::puts("encrust keeps the guild-store buyer binding");
}
'''

salchemist = "classes/salchemist.c"
includes = "\n".join(line for line in source(salchemist).read_text().splitlines()
                     if line.startswith("#include"))
functions = "\n".join(
    extract_function(salchemist, signature)
    for signature in ("static int encrust_lag()",
                      "void do_encrust(P_char ch, char *argument, int /*cmd*/)")
)
functions = extract_function("cmd/actobj.c", "static bool can_equip_soulbound_item(") + "\n" + functions
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="encrust-binding-", dir=ROOT / "bin/tests") as tmp:
    source = Path(tmp) / "encrust.cpp"
    source.write_text(HARNESS.replace("// INCLUDES", includes).replace("// FUNCTIONS", functions))
    binary = source.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-ffunction-sections", "-fdata-sections",
                    "-Wl,--gc-sections", "-Isrc", "-I/usr/include/mysql", str(source), str(HARNESS_STUBS),
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
