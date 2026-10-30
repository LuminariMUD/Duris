#!/usr/bin/env python3
"""Execute production pile pickup and currency transactions with four-count wallets."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC, extract_function, rel

ACTOBJ = (SRC / "actobj.c").read_text()
start = ACTOBJ.index("static bool take_coins(", ACTOBJ.index("// Take the selected coins"))
take = ACTOBJ[start:ACTOBJ.index("P_obj find_live_item_uid(", start)]

HARNESS = r'''
#include "currency_test_support.h"
#include "net/comm.h"
#include "classes/necromancy.h"
#include <algorithm>
#include <cstdio>
#include <cstring>

struct bulk_get_state { std::vector<std::string> haul; };
static std::string actor_text, room_text;
static P_obj room_container = nullptr, extracted = nullptr;
static int room_acts = 0, corpse_writes = 0, relabels = 0;
static bulk_get_state *haul = nullptr;
void send_to_char(const char *text, P_char) { actor_text += text; }
void act(const char *text, int, P_char, P_obj, void *container, int type)
{
    if (type == TO_ROOM) {
        room_text += text;
        room_container = static_cast<P_obj>(container);
        ++room_acts;
    }
}
void extract_obj(P_obj pile, int) { extracted = pile; }
void add_coins(P_obj, int, int, int, int) { ++relabels; }
void writeCorpse(P_obj) { ++corpse_writes; }
static bulk_get_state *corpse_bulk_get(P_char, uint64_t) { return haul; }
void debug(const char *, ...) {}
''' + extract_function("utility.c", "char *coins_to_string(") + "\n" + \
    extract_function("actobj.c", "struct coin_get_submission_options") + ";\n" + \
    extract_function("actobj.c", "static bool change_nonpersistent_coins(") + "\n" + \
    extract_function("actobj.c", "static bool credit_coins(") + "\n" + take + r'''

static void reset()
{
    actor_text.clear(); room_text.clear();
    room_container = extracted = nullptr;
    room_acts = corpse_writes = relabels = 0;
    haul = nullptr;
}
static coin_get_submission_options all_of(const obj_data &pile)
{
    coin_get_submission_options options = {};
    options.has_amount_limit = true;
    for (size_t i = 0; i < 4; ++i) options.amount_limit[i] = pile.value[i];
    return options;
}

int main()
{
    player actor(44);
    obj_data floor = {};
    floor.type = ITEM_MONEY; floor.value[2] = 40;
    assert(take_coins(&actor.ch, &floor, nullptr, TRUE, all_of(floor)));
    assert((wallet(&actor.ch) == std::array<int64_t,4>{0,0,40,0}));
    assert(extracted == &floor && actor.pc.wallet_revision == 1);
    assert(actor_text == std::string("You get ") + coins_to_string(0,40,0,0,"&+y") + ".\r\n");
    assert(room_acts == 1 && room_text == "$n gets some coins." && !room_container);

    reset();
    obj_data corpse = {}; corpse.obj_uid = 50;
    corpse.type = ITEM_CORPSE; corpse.value[CORPSE_FLAGS] = PC_CORPSE;
    obj_data pile = {}; pile.type = ITEM_MONEY;
    pile.value[0] = 3; pile.value[1] = 12; pile.value[2] = 17;
    coin_get_submission_options partial = {}; partial.has_amount_limit = true;
    partial.amount_limit = {1,10,10,0};
    assert(take_coins(&actor.ch,&pile,&corpse,TRUE,partial));
    assert((wallet(&actor.ch) == std::array<int64_t,4>{1,10,50,0}));
    assert(pile.value[0] == 2 && pile.value[1] == 2 && pile.value[2] == 7);
    assert(!extracted && relabels == 1 && corpse_writes == 1);
    assert(room_text == "$n gets some coins from $P." && room_container == &corpse);

    reset();
    bulk_get_state state; haul = &state;
    assert(take_coins(&actor.ch,&pile,&corpse,TRUE,all_of(pile)));
    assert((wallet(&actor.ch) == std::array<int64_t,4>{3,12,57,0}));
    assert(extracted == &pile && state.haul.size() == 1);
    assert(state.haul[0] == coins_to_string(0,7,2,2,"&+y"));
    assert(actor_text.empty() && room_acts == 0);

    // Refusal on the last nonzero component must not partially credit the others.
    reset();
    player full(46); GET_GOLD(&full.ch) = INT_MAX;
    obj_data refused = {}; refused.type = ITEM_MONEY;
    refused.value[0] = 3; refused.value[2] = 1;
    assert(!take_coins(&full.ch,&refused,&corpse,TRUE,all_of(refused)));
    assert((wallet(&full.ch) == std::array<int64_t,4>{0,0,INT_MAX,0}));
    assert(full.pc.wallet_revision == 0 && refused.value[0] == 3 && refused.value[2] == 1);
    assert(!extracted && !relabels && !corpse_writes && actor_text.empty());
    coin_get_submission_options none = {};
    assert(!take_coins(&actor.ch,&refused,nullptr,TRUE,none));

    // Existing noncanonical coins, mixed piles, NPC and no-PID wallets all retain
    // their individual counts. No fallback may reinterpret them as a value.
    for (int kind=0; kind<3; ++kind) {
        reset(); player holder(kind==2 ? 0 : 44);
        if(kind==1) holder.ch.specials.act |= ACT_ISNPC;
        GET_GOLD(&holder.ch)=35;
        obj_data five={};five.type=ITEM_MONEY;five.value[2]=5;
        assert(take_coins(&holder.ch,&five,nullptr,TRUE,all_of(five)));
        assert((wallet(&holder.ch)==std::array<int64_t,4>{0,0,40,0}));
        obj_data mixed={};mixed.type=ITEM_MONEY;
        mixed.value[0]=3;mixed.value[1]=12;mixed.value[2]=17;
        assert(take_coins(&holder.ch,&mixed,nullptr,TRUE,all_of(mixed)));
        assert((wallet(&holder.ch)==std::array<int64_t,4>{3,12,57,0}));
        reset();GET_GOLD(&holder.ch)=INT_MAX;
        obj_data overflow={};overflow.type=ITEM_MONEY;
        overflow.value[0]=1;overflow.value[2]=1;
        const auto revision=holder.pc.wallet_revision;
        assert(!take_coins(&holder.ch,&overflow,&corpse,TRUE,all_of(overflow)));
        assert((wallet(&holder.ch)==std::array<int64_t,4>{3,12,INT_MAX,0}));
        assert(holder.pc.wallet_revision==revision && !extracted && !corpse_writes);
    }
    return 0;
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="take-coins-", dir=ROOT / "bin/tests") as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(HARNESS)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        "-Wno-unused-function", "-Wno-missing-field-initializers", "-g", "-O1",
        "-fsanitize=address,undefined", "-ffunction-sections", "-fdata-sections",
        "-Isrc", "-Itests/async", "-I/usr/include/mysql", str(source),
        rel("currency_transaction.c"), rel("currency_command.c"), rel("critical_command.c"),
        "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
print("[PASS] production pickup preserves exact coins, partial piles, feedback and refusal")
