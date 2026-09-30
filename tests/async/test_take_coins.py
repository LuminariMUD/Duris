#!/usr/bin/env python3
"""Coins taken from a pile in memory: colored amounts, the room told, the rest left in the pile."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC, extract_function


ACTOBJ = (SRC / "actobj.c").read_text(encoding="utf-8", errors="replace")
_start = ACTOBJ.index("static bool take_coins(", ACTOBJ.index("// Take the selected coins"))
TAKE = ACTOBJ[_start:ACTOBJ.index("P_obj find_live_item_uid(", _start)]
assert "coins_to_string(" in TAKE and "if (!credit_coins(actor, value))" in TAKE
# The purse takes the coins before the pile gives them up, on both paths.
assert TAKE.index("credit_coins(actor, value)") < TAKE.index("money->value[index] -= got[index]")
GET = extract_function("actobj.c", "void get(P_char ch, P_obj o_obj, P_obj s_obj, int showit)")
assert "const int64_t total_value = got_p * 1000LL + got_g * 100LL + got_s * 10LL + got_c;" in GET
assert GET.index("if (!credit_coins(ch, total_value))") < GET.index(
    "o_obj->value[3] = o_obj->value[2] = o_obj->value[1] = o_obj->value[0] = 0;")
assert "int total_value" not in GET and "ADD_MONEY(ch, total_value)" not in GET

HARNESS = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#define MAX_STRING_LENGTH 65536
#define CURRENCY_DENOMINATION_COUNT 4
#define TRUE 1
#define FALSE 0
#define TO_ROOM 0
#define ITEM_CORPSE 24
#define CORPSE_FLAGS 1
#define PC_CORPSE 1
#define IS_SET(flag, bit) ((flag) & (bit))
#define BIT_1 1U
#define BIT_2 2U
#define BIT_3 4U
#define BIT_4 8U

struct obj_data
{
	uint64_t obj_uid = 0;
	int type = 0;
	int value[8] = {};
	bool extracted = false;
};
using P_obj = obj_data *;
struct char_data
{
	int wallet = 0;
};
using P_char = char_data *;
struct item_owner_identity
{
	int type = 0;
	uint64_t id = 0, extra = 0;
};
struct bulk_get_state
{
	std::vector<std::string> haul;
};

static std::string actor_text, room_text;
static P_obj room_container = nullptr;
static int room_acts = 0, corpse_writes = 0, relabels = 0;
static bulk_get_state *haul = nullptr;

void send_to_char(const char *text, P_char) { actor_text += text; }
void act(const char *text, int, P_char, P_obj, void *container, int type)
{
	if (type == TO_ROOM)
	{
		room_text += text;
		room_container = static_cast<P_obj>(container);
		++room_acts;
	}
}
// The purse: it refuses coins it cannot hold, the way a player's wallet refuses a
// denomination that would overflow.
static bool credit_coins(P_char ch, int64_t value)
{
	if (value <= 0 || value > INT_MAX - ch->wallet)
		return false;
	ch->wallet += static_cast<int>(value);
	return true;
}
void extract_obj(P_obj pile, int) { pile->extracted = true; }
void add_coins(P_obj, int, int, int, int) { ++relabels; }
void writeCorpse(P_obj) { ++corpse_writes; }
static bulk_get_state *corpse_bulk_get(P_char, uint64_t) { return haul; }
void debug(const char *, ...) {}
''' + extract_function("utility.c", "char *coins_to_string(int platinum, int gold, int silver, int copper, const char *color_string)") + "\n" + extract_function("actobj.c", "struct coin_get_submission_options") + ";\n" + TAKE + r'''

static void reset()
{
	actor_text.clear();
	room_text.clear();
	room_container = nullptr;
	room_acts = corpse_writes = relabels = 0;
	haul = nullptr;
}

static coin_get_submission_options all_of(const obj_data &pile)
{
	coin_get_submission_options options = {};
	options.has_amount_limit = true;
	for (size_t index = 0; index < 4; ++index)
		options.amount_limit[index] = pile.value[index];
	return options;
}

int main()
{
	// Everything in a pile on the floor: the colored amount without its zero
	// denominations, the room told, the pile gone.
	reset();
	char_data actor;
	obj_data floor = {};
	floor.type = 1;
	floor.value[0] = 3;
	floor.value[2] = 2;
	assert(take_coins(&actor, &floor, nullptr, TRUE, all_of(floor)));
	assert(actor.wallet == 203 && floor.extracted);
	assert(actor_text == std::string("You get ") + coins_to_string(0, 2, 0, 3, "&+y") + ".\r\n");
	assert(actor_text.find("0 ") == std::string::npos && actor_text.find("&+Y") != std::string::npos);
	assert(room_acts == 1 && room_text == "$n gets some coins." && !room_container);

	// Part of a pile in a player's corpse: the rest stays and is relabelled, the room
	// hears where the coins came from, and the corpse is saved.
	reset();
	obj_data corpse = {};
	corpse.obj_uid = 50;
	corpse.type = ITEM_CORPSE;
	corpse.value[CORPSE_FLAGS] = PC_CORPSE;
	obj_data pile = {};
	pile.type = 1;
	pile.value[2] = 5;
	coin_get_submission_options one_gold = {};
	one_gold.has_amount_limit = true;
	one_gold.amount_limit[2] = 1;
	assert(take_coins(&actor, &pile, &corpse, TRUE, one_gold));
	assert(actor.wallet == 303 && pile.value[2] == 4 && !pile.extracted && relabels == 1);
	assert(room_text == "$n gets some coins from $P." && room_container == &corpse);
	assert(corpse_writes == 1);

	// A haul lists the coins in its summary and tells nobody yet.
	reset();
	bulk_get_state state;
	haul = &state;
	obj_data hauled = {};
	hauled.type = 1;
	hauled.value[3] = 1;
	assert(take_coins(&actor, &hauled, &corpse, TRUE, all_of(hauled)));
	assert(actor.wallet == 1303 && hauled.extracted);
	assert(state.haul.size() == 1 && state.haul[0] == coins_to_string(1, 0, 0, 0, "&+y"));
	assert(actor_text.empty() && room_acts == 0);

	// Coins the purse cannot hold are refused, and the pile keeps them.
	reset();
	char_data full;
	full.wallet = INT_MAX - 5;
	obj_data heavy = {};
	heavy.type = 1;
	heavy.value[3] = 1;
	assert(!take_coins(&full, &heavy, nullptr, TRUE, all_of(heavy)));
	assert(full.wallet == INT_MAX - 5 && heavy.value[3] == 1 && !heavy.extracted);
	assert(actor_text.empty() && room_acts == 0);

	// Nothing to take is refused and changes nothing.
	reset();
	obj_data empty = {};
	empty.type = 1;
	empty.value[1] = 4;
	coin_get_submission_options none = {};
	none.has_amount_limit = true;
	assert(!take_coins(&actor, &empty, nullptr, TRUE, none));
	assert(actor.wallet == 1303 && empty.value[1] == 4 && actor_text.empty());
	return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-take-coins-") as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-Wno-unused-function", "-fsanitize=address,undefined", "-g", str(source),
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
print("[PASS] coins taken in memory show their colored amount and tell the room")
print("[PASS] a partial take leaves the rest in the pile; a player corpse is saved")
print("[PASS] a haul lists the coins in its summary; nothing to take changes nothing")
