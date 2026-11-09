#!/usr/bin/env python3
"""Run the smith command with real wallet refusal and exact input/output UIDs."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, rel, source


prelude = r'''
#include "currency_test_support.h"
#include "core/prototypes.h"
#include "core/utility.h"
#include "cmd/interp.h"
#include "economy/tradeskill.h"
#include "net/comm.h"
#include <algorithm>
#include <cstdio>
#include <cstring>

constexpr int SMITH_MAX_ITEMS = 20;
index_data mob_indices[1]{}, object_indices[3]{};
P_index mob_index = mob_indices, obj_index = object_indices;
forge_item forge_item_list[134]{};
static obj_data output{};
static bool refuse_creation, refuse_delivery;
static std::vector<uint64_t> extracted;

int number(int, int high) { return high; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *, P_char) {}
void ADD_MONEY(P_char, int) { std::abort(); }
void currency_adjustment_committed(P_char, bool, const currency_command_result &,
                                    unsigned int, const uint8_t *, size_t) {}
char *coin_stringv(int, int) { static char coins[] = "coins"; return coins; }
void forge_describe(int, P_char) {}
P_obj forge_create(int, P_char, int material)
{
    if (refuse_creation) return nullptr;
    output = {}; output.loc_p=LOC_NOWHERE;
    output.R_num = 2; output.obj_uid = 3003; output.material = material;
    return &output;
}
void obj_from_char(P_obj object)
{
    assert(OBJ_CARRIED(object));
    P_obj *link = &object->loc.carrying->carrying;
    while (*link != object) { assert(*link); link = &(*link)->next_content; }
    *link = object->next_content;
    object->next_content = nullptr; object->loc_p = LOC_NOWHERE;
}
void extract_obj(P_obj object, int)
{
    if (OBJ_CARRIED(object)) obj_from_char(object);
    extracted.push_back(object->obj_uid);
}
bool obj_to_char(P_obj object, P_char actor)
{
    if (object == &output && refuse_delivery) { extract_obj(object, 0); return false; }
    assert(OBJ_NOWHERE(object));
    object->next_content = actor->carrying; actor->carrying = object;
    object->loc_p = LOC_CARRIED; object->loc.carrying = actor;
    return true;
}
'''

tradeskill = source("tradeskill.c").read_text()
tables = tradeskill[tradeskill.index("int forge_prices[]"):
                    tradeskill.index("P_obj get_hammer(")]
functions = "\n".join(extract_function(name, signature) for name, signature in (
    ("utility.c", "int SUB_MONEY("),
    ("tradeskill.c", "int smith("),
))

driver = r'''
int main()
{
    player buyer(44);
    char_data smith_actor{}; npc_only_data smith_npc{};
    smith_actor.specials.act = ACT_ISNPC; smith_actor.only.npc = &smith_npc;
    mob_indices[0].virtual_number = smith_array[0].vnum;
    object_indices[0].virtual_number = 234;
    object_indices[1].virtual_number = 235;
    object_indices[2].virtual_number = 1255;
    forge_item_list[131].ore_needed[0] = 234;
    forge_item_list[131].ore_needed[1] = 235;
    forge_item_list[132].ore_needed[0] = 234;
    online[0] = &buyer.ch;

    for (int failure = 0; failure < 5; ++failure)
    {
        currency_transaction_reset_for_tests();
        buyer.ch.carrying = nullptr; smith_actor.carrying = nullptr;
        obj_data ore1{}, ore2{}, smith_ore{};
        ore1.loc_p=ore2.loc_p=smith_ore.loc_p=LOC_NOWHERE;
        ore1.R_num=0; ore1.obj_uid=1001; ore1.material=7;
        ore2.R_num=1; ore2.obj_uid=1002;
        smith_ore.R_num=0; smith_ore.obj_uid=2002;
        obj_to_char(&ore1, &buyer.ch); obj_to_char(&ore2, &buyer.ch);
        obj_to_char(&smith_ore, &smith_actor);
        GET_COPPER(&buyer.ch)=0; GET_SILVER(&buyer.ch)=0;
        GET_GOLD(&buyer.ch)=0; GET_PLATINUM(&buyer.ch)=10;
        refuse_creation = failure == 1; refuse_delivery = failure == 2;
        if (failure == 3) assert(currency_transaction_reserve_chest(&buyer.ch));
        if (failure == 4) assert(currency_transaction_reserve_trade(&buyer.ch, -8000));
        order.clear(); extracted.clear();
        auto revision = buyer.pc.wallet_revision;
        char choice[]="1";
        assert(smith(&smith_actor, &buyer.ch, CMD_FORGE, choice));
        assert(OBJ_CARRIED_BY(&smith_ore, &smith_actor) && smith_actor.carrying == &smith_ore);
        if (failure)
        {
            assert(GET_MONEY(&buyer.ch) == 10000 && buyer.pc.wallet_revision == revision);
            assert(OBJ_CARRIED_BY(&ore1, &buyer.ch) && OBJ_CARRIED_BY(&ore2, &buyer.ch));
            assert(std::find(extracted.begin(), extracted.end(), 1001) == extracted.end());
            assert(std::find(extracted.begin(), extracted.end(), 1002) == extracted.end());
            assert(order.empty());
            if (failure != 1) assert((extracted == std::vector<uint64_t>{3003}));
        }
        else
        {
            assert(GET_MONEY(&buyer.ch) == 5000 && buyer.pc.wallet_revision == revision+1);
            assert(buyer.ch.carrying == &output && OBJ_CARRIED_BY(&output, &buyer.ch));
            assert(output.obj_uid == 3003 && output.material == 7);
            std::sort(extracted.begin(), extracted.end());
            assert((extracted == std::vector<uint64_t>{1001, 1002}));
            assert((order == std::vector<std::string>{"save:44"}));
        }
        currency_transaction_reset_for_tests();
        refuse_creation = refuse_delivery = false;
    }
    // Choices outside this smith's actual menu leave its customer untouched.
    char invalid[]="7";
    assert(!smith(&smith_actor, &buyer.ch, CMD_FORGE, invalid));
    assert(GET_MONEY(&buyer.ch) == 10000);
    (void)last_committed; (void)last_error; (void)completion; (void)wallet;
    puts("smith: customer ore UIDs, menu bounds, delivery/payment refusals and one checkpoint pass");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="smith-payment-", dir=ROOT / "bin/tests") as temporary:
    cpp = Path(temporary) / "smith.cpp"
    binary = Path(temporary) / "smith"
    cpp.write_text(prelude + tables + functions + driver)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
        "-Wno-unused-parameter", "-Wno-missing-field-initializers",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
        "-ffunction-sections", "-fdata-sections", "-Isrc", "-Itests/async",
        "-I/usr/include/mysql", str(cpp), rel("currency_transaction.c"),
        rel("currency_command.c"), rel("critical_command.c"),
        "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
