#!/usr/bin/env python3
"""A refused blackjack bet takes no money and leaves the table open.

Compiles the production src/economy/cardgames.c under ASan/UBSan and calls
blackjack_table() with `offer`. A player told they cannot afford the bet used to
lose it anyway: the refusal fell through to SUB_MONEY, past the table limit, and
an oversized platinum bet overflowed the copper total.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "economy/cardgames.h"
#include <cassert>
#include <cstdio>
#include <cstring>

int blackjack_table(P_obj obj, P_char ch, int cmd, char *argument);

static int taken;
int SUB_MONEY(P_char ch, int amount, int)
{
	taken += amount;
	ch->points.cash[0] -= amount;
	return 0;
}
int get_property(const char *, int fallback) { return fallback; }
int number(int low, int) { return low; }
int say(P_char, const char *) { return 0; }
void send_to_char_f(P_char, const char *, ...) {}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int)
{
	assert(false);
	return {};
}
// Argument splitting is not under test; the bet amount and coin parsing are.
char *one_argument(const char *argument, char *first)
{
	while (*argument == ' ')
		argument++;
	while (*argument && *argument != ' ')
		*first++ = *argument++;
	*first = '\0';
	return const_cast<char *>(argument);
}
// FUNCTIONS

static void offer(P_obj table, P_char ch, const char *what)
{
	char argument[64];
	std::snprintf(argument, sizeof(argument), "%s", what);
	blackjack_table(table, ch, CMD_OFFER, argument);
}

int main()
{
	char_data player{};
	player.player.name = const_cast<char *>("Gambler");
	player.specials.position = STAT_NORMAL | POS_STANDING;
	obj_data table{};
	table.value[0] = BJ_PREBID;

	// 10 platinum on hand, plenty of copper: a 50-platinum bet must be refused outright.
	player.points.cash[3] = 10;
	player.points.cash[0] = 100000;
	offer(&table, &player, "50 platinum");
	assert(taken == 0 && player.points.cash[0] == 100000 && player.points.cash[3] == 10);
	assert(table.value[0] == BJ_PREBID);

	// Far beyond the coins held and the table limit: no overflowed charge either.
	offer(&table, &player, "4294968 platinum");
	assert(taken == 0 && player.points.cash[0] == 100000);
	assert(table.value[0] == BJ_PREBID);

	std::puts("refused blackjack bets take nothing");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="blackjack-bet-", dir=ROOT / "bin/tests") as tmp:
    source = Path(tmp) / "blackjack.cpp"
    functions = "\n".join((extract_function("core/utility.c", "int coin_type(char *s)"),
                           extract_function("cmd/interp.c", "bool is_abbrev(const char *arg1, const char *arg2)")))
    source.write_text(HARNESS.replace("// FUNCTIONS", functions))
    binary = source.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=undefined", "-fno-omit-frame-pointer",
                    "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                    "-Isrc", "-I/usr/include/mysql", str(source), "src/economy/cardgames.c",
                    str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="detect_leaks=0:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
