#!/usr/bin/env python3
"""Execute Chaos access/dispatch for staff, mortals, and local test accounts."""

from pathlib import Path
import subprocess
import tempfile

from _paths import HARNESS_STUBS, ROOT, SRC, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include <cassert>
#include <string>

#include "combat/chaos.c"

long new_exp_table[TOTALLVLS]{};
const int top_of_world = 1000;
static bool chaos_enabled = false, tests_enabled = false, ship_owned = true;
static std::string output;
static int kit_calls = 0, bag_calls = 0, money = 0, seeded = 0, generated = 0, funds = 0;
static ShipData ship{};
static obj_data material{};

bool chaos_mud_enabled() { return chaos_enabled; }
bool chaos_test_commands_enabled() { return tests_enabled; }
void send_to_char(const char *message, P_char) { output += message; }
void act(const char *message, int, P_char, P_obj, void *, int) { output += message; }
void restore_chaos_character_kit(P_char, const char *) { ++kit_calls; }
void load_chaos_kit_bag(P_char, char *) { ++bag_calls; }
void ADD_MONEY(P_char, int amount) { money += amount; }
void advance_to_level(P_char ch, int level) { ch->player.level = level; }
void lose_level(P_char ch) { --ch->player.level; }
P_ship get_ship_from_owner(char *) { return ship_owned ? &ship : nullptr; }
int char_in_list(const P_char ch) { return ch != nullptr; }
int real_room(int vnum) { return vnum == 16633 ? 43 : 42; }
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ch->in_room = room; return true; }
bool isname(const char *arg, const char *names) { return !strcmp(arg, names); }
P_obj read_object(int, int) { return &material; }
void extract_obj(P_obj, int) { assert(false); }
bool item_creation_grant_submit_to_player(P_char, P_obj, P_char, P_obj) { ++seeded; return true; }
bool item_creation_grant_mark_blocking(P_char) { return true; }
bool enhancement_system_is_ready() { return true; }
void boot_enhancement_system() {}
bool chaos_material_pouch_record_generated(P_char, const chaos_material_pouch_usage *usage, size_t count) {
    assert(count == 1);
    generated += usage[0].count;
    return true;
}
bool currency_transaction_submit_wallet_value(P_char ch, int64_t value,
    currency_reason_type, int64_t, critical_source_site, critical_deadline_class,
    currency_completion_fn completion, const void *, size_t) {
    assert(value == 100000);
    ++funds;
    completion(ch, true, {}, 0, nullptr, 0);
    return true;
}

static void run(P_char ch, const char *command) {
    char argument[MAX_INPUT_LENGTH];
    snprintf(argument, sizeof(argument), "%s", command);
    output.clear();
    do_chaos(ch, argument, 0);
}
static void explains(const char *reason) {
    if (output.find(reason) == std::string::npos)
        fprintf(stderr, "Expected reason: %s\nActual response: %s\n", reason, output.c_str());
    assert(output.find('(') != std::string::npos);
    assert(output.find(reason) != std::string::npos);
}

int main() {
    pc_only_data pc{};
    char_data staff{};
    staff.only.pc = &pc;
    char name[] = "Staff";
    staff.player.name = name;
    staff.specials.position = STAT_NORMAL + POS_STANDING;
    staff.in_room = 10;
    assert(!chaos_command_allowed(nullptr));

    // Trusted lower staff retain their existing gate in both game modes.
    for (bool mode : {false, true}) {
        chaos_enabled = mode;
        for (int level : {MAXLVLMORTAL, AVATAR, LESSER_G, GREATER_G, FORGER, OVERLORD}) {
            for (bool mortal : {false, true}) {
                staff.player.level = level;
                staff.specials.act = mortal ? PLR_MORTAL : 0;
                int before = money;
                run(&staff, "plat");
                bool allowed = level >= FORGER || (mode && level > MAXLVLMORTAL && !mortal);
                assert(money == before + (allowed ? 10000000 : 0));
                if (!allowed)
                    explains(level <= MAXLVLMORTAL || mortal ? "Trusted staff required" :
                             "Chaos mode is disabled; level 61 staff can override it.");
            }
        }
    }
    // NPCs cannot inherit player staff access from their level.
    staff.specials.act = ACT_ISNPC;
    staff.player.level = OVERLORD;
    int before = money;
    run(&staff, "plat");
    assert(money == before && !chaos_command_allowed(&staff));

    // Exercise EVERY subcommand with both mode switches off and mortal mode on.
    chaos_enabled = tests_enabled = false;
    staff.specials.act = PLR_MORTAL;
    run(&staff, "kit target");
    assert(kit_calls == 1);
    run(&staff, "kitbag necromancer githzerai");
    assert(bag_calls == 1);
    run(&staff, "shipfrags 123");
    assert(ship.frags == 123);
    run(&staff, "sfrags 234");
    assert(ship.frags == 234);
    run(&staff, "crewexp 12 34 56");
    assert(ship.crew.sail_skill == 12 && ship.crew.guns_skill == 34 && ship.crew.rpar_skill == 56);
    run(&staff, "portal flann");
    assert(staff.in_room == 42);
    run(&staff, "side evil");
    assert(staff.player.racewar == RACEWAR_EVIL);
    run(&staff, "pouchseed");
    assert(seeded == 5);
    run(&staff, "pouchgenerate 7");
    assert(generated == 7);
    // No descriptor, account, or localhost is needed for level 62's helper.
    run(&staff, "questroom 16633");
    assert(staff.in_room == 43 && funds == 1);
    assert(output.find("funds committed") != std::string::npos);
    // A real-size exp table plus ASan catches the former level-63 index.
    new_exp_table[MAXLVLMORTAL + 1] = 200;
    run(&staff, "level 56");
    assert(staff.player.level == 56 && GET_EXP(&staff) == 100);
    staff.player.level = OVERLORD;

    run(&staff, "");
    explains("Missing or unknown Chaos subcommand");
    run(&staff, "notacommand");
    explains("Missing or unknown Chaos subcommand");
    run(&staff, "portal nowhere");
    explains("Unknown Chaos portal destination");
    run(&staff, "side nonsense");
    explains("Choose good, evil, undead, or neutral");
    run(&staff, "shipfrags potato");
    explains("Usage: chaos shipfrags");
    run(&staff, "shipfrags 10001");
    explains("between 0 and 10000");
    run(&staff, "crewexp 10001");
    explains("between 0 and 10000");
    ship_owned = false;
    run(&staff, "shipfrags 1");
    explains("No ship is registered");
    run(&staff, "crewexp 1");
    explains("No ship is registered");
    run(&staff, "level 63");
    explains("Usage: chaos level");
    assert(staff.player.level == OVERLORD);
    run(&staff, "questroom 123");
    explains("Usage: chaos questroom 16633");
    assert(funds == 1);

    chaos_enabled = true;
    staff.player.level = LESSER_G;
    staff.specials.act = 0;
    run(&staff, "level 56");
    explains("Only level 62 staff");
    assert(staff.player.level == LESSER_G);
    run(&staff, "pouchseed");
    explains("Chaos test commands");
    run(&staff, "pouchgenerate 1");
    explains("Chaos test commands");
    assert(seeded == 5 && generated == 7);
    run(&staff, "questroom 16633");
    explains("configured test account");
    assert(funds == 1);
    tests_enabled = true;
    run(&staff, "pouchseed");
    assert(seeded == 10);
    run(&staff, "pouchgenerate 1");
    assert(generated == 8);

    // Preserve the existing tightly scoped local mortal quest-test exception.
    descriptor_data descriptor{};
    acct_entry account{};
    char account_name[] = "chaostest";
    account.acct_name = account_name;
    descriptor.account = &account;
    staff.desc = &descriptor;
    staff.player.level = MAXLVLMORTAL;
    setenv("CHAOS_TEST_ACCOUNT", account_name, 1);
    snprintf(descriptor.host, sizeof(descriptor.host), "remote.example");
    run(&staff, "questroom 16633");
    explains("localhost");
    assert(funds == 1);
    snprintf(descriptor.host, sizeof(descriptor.host), "127.0.0.1");
    run(&staff, "questroom 16633");
    assert(funds == 2);
    run(&staff, "kit target");
    explains("Trusted staff required");
    assert(kit_calls == 1);
    chaos_enabled = false;
    run(&staff, "questroom 16633");
    explains("Chaos test mode");
    assert(funds == 2);
    puts("Chaos staff override, all subcommands, denials, and local test exception passed");
}
'''

# Keep the real argument/abbreviation behavior in the dispatcher harness.
helpers = "\n".join([
    extract_function("utility.c", "int strn_cmp("),
    extract_function("interp.c", "const char *fill_words[]") + ";",
    extract_function("interp.c", "int search_block("),
    extract_function("interp.c", "int fill_word("),
    extract_function("interp.c", "char *one_argument("),
    extract_function("interp.c", "bool is_abbrev("),
])
with tempfile.TemporaryDirectory(prefix="duris-chaos-auth-") as directory:
    source = Path(directory) / "authorization.cpp"
    binary = Path(directory) / "authorization"
    source.write_text(HARNESS + helpers)
    for defines in ([], ["-DTEST_MUD"]):
        subprocess.run([
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-ffunction-sections", "-fdata-sections",
            "-Isrc", *defines, str(source), str(HARNESS_STUBS),
            "-Wl,--gc-sections", "-o", str(binary),
        ], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=ROOT, check=True)

interp = (SRC / "cmd/interp.c").read_text()
assert "CMD_Y(CMD_CHAOS, STAT_DEAD + POS_PRONE, do_chaos, 0, FALSE);" in interp
