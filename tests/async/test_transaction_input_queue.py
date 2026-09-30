#!/usr/bin/env python3
"""While a transaction is in flight, the input that depends on it waits, in order.

Money applies at once now; the collector's transactions and item moves still hold the
commands that depend on them. This runs the real interpreter gates and queue readers.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC


def extract(source: Path, signature: str) -> str:
    """Return one complete C/C++ function beginning at ``signature``."""
    text = source.read_text(encoding="utf-8", errors="replace")
    start = text.index(signature)
    depth = 0
    for index in range(text.index("{", start), len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unbalanced braces reading {signature}")


COMM_PATH = SRC / "comm.c"
INTERP_PATH = SRC / "interp.c"
COMM = COMM_PATH.read_text(encoding="utf-8", errors="replace")
PROTOTYPES = (SRC / "prototypes.h").read_text(encoding="utf-8", errors="replace")
DEPENDS = extract(INTERP_PATH, "bool cmd_depends_on_currency_transaction(int cmd)")
for command in (
    "CMD_GET", "CMD_DROP", "CMD_PUT", "CMD_GIVE", "CMD_DEPOSIT", "CMD_WITHDRAW",
    "CMD_ASK", "CMD_BUY", "CMD_SELL", "CMD_OFFER", "CMD_RENT", "CMD_AUCTION",
):
    assert command in DEPENDS
# Money applies at once, so only the collector's transactions still hold such input.
assert "currency_transaction_player_busy" not in COMM
assert "collector_transaction_player_busy(character)" in COMM
assert "input_allowed_while_item_and_currency_pending" in COMM
assert "int get_pending_transaction_cmd_from_q(struct txt_q *, char *, bool, bool);" in PROTOTYPES

HARNESS = r'''
#include "core/structs.h"
#include "core/utils.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#define CMD_NONE 0
#define CMD_DROP 1
#define CMD_PUT 2
#define CMD_GIVE 3
#define CMD_DEPOSIT 4
#define CMD_WITHDRAW 5
#define CMD_INVENTORY 6
#define CMD_SCORE 7
#define CMD_LOOK 8
#define CMD_SAY 9
#define CMD_GET 10
#define CMD_COLLECTOR 11
#define CMD_ASK 12
#define CMD_BUY 13
#define CMD_SELL 14
#define CMD_OFFER 15
#define CMD_RENT 16
#define CMD_PRAY 17
#define CMD_EXCHANGE 18
#define CMD_SPLIT 19
#define CMD_RELOAD 20
#define CMD_REPAIR 21
#define CMD_SUMMON 22
#define CMD_MAIL 23
#define CMD_HOME 24
#define CMD_AUCTION 25
#define CMD_CONSTRUCT 26
#define CMD_ENTER 27
#define CMD_EQUIPMENT 28
#define CMD_STAT 29
#define CMD_HIRE 30
#define CMD_FORGE 31
#define CMD_REFINE 32
#define CMD_ENHANCE 33
#define CMD_SAY2 34
#define CMD_TELL 35
#define CMD_PRACTICE 36
#define CMD_PRACTISE 37
#define CMD_ENCHANT 38
static const char *command[] = {
	"drop", "put", "give", "deposit", "withdraw", "inventory", "score", "look",
	"say", "get", "collector", "ask", "buy", "sell", "offer", "rent", "pray",
	"exchange", "split", "reload", "repair", "summon", "mail", "home", "auction",
	"construct", "enter", "equipment", "stat", "hire", "forge", "refine", "enhance",
	"'", "tell", "practice", "practise", "enchant", "\n"
};
void logit(const char *, const char *, ...) {}
void __free(void *memory, const char *, int) { free(memory); }
bool input_allowed_while_item_moving(const char *input)
{
	return input && strcmp(input, "inventory") && strncmp(input, "get ", 4);
}
int get_item_movement_cmd_from_q(struct txt_q *queue, char *dest);
''' + "\n".join([
    extract(INTERP_PATH, "int old_search_block(const char *argument"),
    extract(INTERP_PATH, "static int input_command_number(const char *input)"),
    extract(INTERP_PATH, "bool cmd_depends_on_currency_transaction(int cmd)"),
    extract(INTERP_PATH, "static bool input_is_currency_dependent_speech(const char *input)"),
    extract(INTERP_PATH, "static bool input_is_currency_dependent_confirmation(const char *input)"),
    extract(INTERP_PATH, "bool input_allowed_while_currency_pending(const char *input)"),
    extract(INTERP_PATH, "bool input_allowed_while_item_and_currency_pending(const char *input)"),
    extract(COMM_PATH, "int get_from_q(struct txt_q *queue, char *dest)"),
    extract(COMM_PATH, "static int get_filtered_cmd_from_q(struct txt_q *queue, char *dest,"),
    extract(COMM_PATH, "int get_item_movement_cmd_from_q(struct txt_q *queue, char *dest)"),
    extract(COMM_PATH, "int get_pending_transaction_cmd_from_q(struct txt_q *queue, char *dest,"),
]) + r'''

static void push(struct txt_q *queue, const char *text)
{
	struct txt_block *block = (struct txt_block *)malloc(sizeof(struct txt_block));
	block->text = strdup(text);
	block->next = NULL;
	if (queue->head)
		queue->tail->next = block;
	else
		queue->head = block;
	queue->tail = block;
}

static void next(struct txt_q *queue, bool item, bool transaction, const char *want)
{
	char dest[MAX_INPUT_LENGTH] = "untouched";
	const int got = get_pending_transaction_cmd_from_q(queue, dest, item, transaction);
	if (!want)
	{
		assert(!got && !strcmp(dest, "untouched"));
		return;
	}
	if (!got || strcmp(dest, want))
	{
		fprintf(stderr, "got '%s', want '%s'\n", got ? dest : "(nothing)", want);
		abort();
	}
}

int main()
{
	assert(!input_allowed_while_currency_pending("get all corpse"));
	assert(!input_allowed_while_currency_pending("  DROP all.coins"));
	assert(!input_allowed_while_currency_pending("deposit all"));
	assert(!input_allowed_while_currency_pending("ask bartender abandon"));
	assert(!input_allowed_while_currency_pending("auction bid"));
	assert(!input_allowed_while_currency_pending("say deal"));
	assert(!input_allowed_while_currency_pending("yes"));
	assert(input_allowed_while_currency_pending("score"));
	assert(input_allowed_while_currency_pending("say waiting"));
	assert(input_allowed_while_currency_pending("no"));
	assert(!input_allowed_while_currency_pending(NULL));

	// A transaction in flight: what depends on it waits, in order; the rest passes.
	struct txt_q queue = {};
	push(&queue, "put all.coins satchel");
	push(&queue, "score");
	push(&queue, "give 1 platinum friend");
	push(&queue, "look");
	next(&queue, false, true, "score");
	next(&queue, false, true, "look");
	next(&queue, false, true, NULL);
	// Once it lands, the held input runs in the order it was typed.
	next(&queue, false, false, "put all.coins satchel");
	next(&queue, false, false, "give 1 platinum friend");
	next(&queue, false, false, NULL);

	// Both an item move and a transaction: only input safe under both gates passes.
	push(&queue, "inventory");
	push(&queue, "deposit all");
	push(&queue, "say waiting");
	next(&queue, true, true, "say waiting");
	next(&queue, true, true, NULL);
	next(&queue, true, false, "deposit all");
	next(&queue, false, false, "inventory");
	assert(!queue.head && !queue.tail);
	return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-transaction-input-") as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-Wno-unused-function", "-fsanitize=address,undefined", "-g", "-Isrc",
                    "-I/usr/include/mysql", str(source), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
print("[PASS] input that depends on a transaction in flight waits in order; the rest passes")
print("[PASS] an item move and a transaction together pass only input safe under both")
