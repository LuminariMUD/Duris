#!/usr/bin/env python3
"""Exercise the real shop dispatcher and room lookups with ambiguous targets."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


production = "\n".join(
    extract_function(file, signature)
    for file, signatures in (
        ("handler.c", (
            "bool isname(const char *str, const char *namelist)",
            "P_char get_char_room(",
            "static bool room_target_matches(",
            "P_char get_char_room_vis(",
        )),
        ("shop.c", ("int shop_keeper(",)),
    )
    for signature in signatures
)

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "economy/shop.h"
#include "net/comm.h"
#include "world/handler.h"
#include <cassert>
#include <cstdio>
#include <cstring>

#undef CAN_DAYPEOPLE_SEE
#define CAN_DAYPEOPLE_SEE(room) true
static room_data rooms[2]{};
P_room world = rooms;
const int top_of_world = 1;
static struct { const char *normal; } race_names_table[LAST_RACE+1]{};
static shop_data shops[1]{};
shop_data *shop_index = shops;
int number_of_shops = 1;
time_info_data time_info{};
static P_char unseen;
static int attacks, shouts, refusals;

bool ac_can_see(P_char, P_char target, bool) { return target != unseen; }
int is_introd(P_char, P_char) { return 0; }
bool has_innate(P_char, int) { return false; }
bool racewar(P_char, P_char) { return false; }
void logit(const char *, const char *, ...) {}
int singleton_shop_id(P_char) { return 0; }
void shopping_kill(char *, P_char, P_char, int) { ++attacks; }
void command_interpreter(P_char, char *text) {
    assert(strstr(text, "shout Guards!")); ++shouts;
}
void act(const char *message, int, P_char, P_obj, P_char, int) {
    assert(!strcmp(message, MSG_NO_STEAL_HERE) || strstr(message, "No magic in here!"));
    ++refusals;
}
int smith(P_char, P_char, int, char *) { abort(); }
int real_room(int room) { return room; }
int fill_word(char *) { return false; }
void obj_from_char(P_obj) { abort(); }
void obj_to_room(P_obj, int) { abort(); }
void extract_obj(P_obj, bool) { abort(); }
void shopping_buy(char *, P_char, P_char, int) { abort(); }
void shopping_sell(char *, P_char, P_char, int) { abort(); }
void shopping_value(char *, P_char, P_char, int) { abort(); }
void shopping_peruse(char *, P_char, P_char, int) { abort(); }
void shopping_list(char *, P_char, P_char, int) { abort(); }
void shopping_repair(char *, P_char, P_char, int) { abort(); }

// PRODUCTION

static void check(P_char keeper, P_char player, const char *target, bool blocked) {
    char argument[128];
    snprintf(argument, sizeof(argument), "%s", target);
    const int old_attacks = attacks, old_shouts = shouts, old_refusals = refusals;
    assert(bool(shop_keeper(keeper, player, CMD_KILL, argument)) == blocked);
    assert(attacks == old_attacks + blocked);
    snprintf(argument, sizeof(argument), "coin %s", target);
    assert(bool(shop_keeper(keeper, player, CMD_STEAL, argument)) == blocked);
    assert(shouts == old_shouts + blocked && refusals == old_refusals + blocked);
}

int main() {
    char_data player{}, hidden{}, guard{}, keeper{};
    player.player.name = const_cast<char *>("Customer");
    for (P_char npc : {&hidden, &guard, &keeper}) {
        SET_BIT(npc->specials.act, ACT_ISNPC);
        npc->player.name = const_cast<char *>("shopkeeper dwarf guard");
    }
    player.next_in_room = &hidden; hidden.next_in_room = &guard;
    guard.next_in_room = &keeper; rooms[0].people = &player;
    race_names_table[0].normal = "Human";
    unseen = &hidden;
    SET_BIT(hidden.specials.affected_by, AFF_HIDE);
    assert(get_char_room("dwarf", 0) == nullptr); // hidden is still counted here
    assert(get_char_room("2.dwarf", 0) == &guard);
    assert(get_char_room("3.dwarf", 0) == &keeper);
    // Remote pet shops must still search the explicitly supplied room.
    rooms[1].people = &keeper;
    assert(get_char_room("dwarf", 1) == &keeper);

    check(&keeper, &player, "2.dwarf", true);
    check(&keeper, &player, "dwarf", false);
    check(&keeper, &player, "3.dwarf", false);
    guard.specials.z_cord = 1;
    check(&keeper, &player, "dwarf", true);
    check(&keeper, &player, "2.dwarf", false);
    guard.specials.z_cord = 0;
    hidden.next_in_room = &keeper; keeper.next_in_room = &guard;
    guard.next_in_room = nullptr;
    check(&keeper, &player, "shopkeeper", true);
    check(&keeper, &player, "dwarf", true);
    check(&keeper, &player, "guard", true);
    check(&keeper, &player, "2.dwarf", false);
    shops[0].shop_killable = true;
    char argument[] = "dwarf";
    assert(!shop_keeper(&keeper, &player, CMD_KILL, argument));
    for (int command : {CMD_CAST, CMD_USE, CMD_RECITE, CMD_WILL}) {
        shops[0].magic_allowed = false;
        shops[0].shop_is_roaming = false;
        keeper.in_room = 0;
        assert(shop_keeper(&keeper, &player, command, argument));
        keeper.in_room = 1;
        assert(!shop_keeper(&keeper, &player, command, argument));
        shops[0].shop_is_roaming = true;
        assert(shop_keeper(&keeper, &player, command, argument));
        shops[0].magic_allowed = true;
        assert(!shop_keeper(&keeper, &player, command, argument));
    }
    puts("shop guards: secondary keywords, visibility, ordinals, height and killable shops passed");
}
'''

production = "\n".join((
    extract_function("handler.c", "int get_number("),
    extract_function("interp.c", "char *one_argument("),
    production,
))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="shop-targets-", dir=ROOT / "bin/tests") as directory:
    path, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    path.write_text(harness.replace("// PRODUCTION", production))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-Isrc", str(path), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
