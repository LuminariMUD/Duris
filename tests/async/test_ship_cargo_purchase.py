#!/usr/bin/env python3
"""Run the real purchase handlers and currency settlement with a controlled market."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function

functions = "\n".join(
    extract_function("ships/ship_utils.c", signature)
    for signature in ("int ShipSlot::get_weight(", "int ShipData::slot_weight(", "void ShipSlot::clear(")
)
functions += "\n" + extract_function(
    "ships/ship_variables.c", "const ShipTypeData ship_type_data[MAXSHIPCLASS] ="
) + ";\n"
functions += extract_function("ships/ship_shop.c", "struct ship_crate_purchase\n") + ";\n"
functions += "\n".join(
    extract_function("ships/ship_shop.c", signature)
    for signature in (
        "static bool ship_crate_order_cost(", "static void ship_crate_purchase_committed(",
        "int buy_cargo(", "int buy_contra(",
    )
)

harness = r'''
#include "currency_test_support.h"
#include "core/utility.h"
#include "economy/divine_trade_runtime.h"
#include "world/epic_bonus.h"
#include "net/comm.h"
#include <charconv>
#include <cmath>
#include <cstdarg>
#include <cstring>
#include <limits>

static room_data rooms[1]{};
const PortData ports[NUM_PORTS] = {{111, "Test port", 0}};
const WeaponData weapon_data[MAXWEAPON] = {};
const EquipmentData equipment_data[MAXEQUIPMENT] = {};
int eq_ram_weight(const ShipData *) { return 0; }
int eq_levistone_weight(const ShipData *) { return 0; }
float ShipCrew::get_maxcargo_mod() const { return 1.1f; }
int IS_MORPH(P_char) { return false; }
char buf[MAX_STRING_LENGTH];
static int price = 100, quotes = 0, market_changes = 0, updates = 0;
static int trade_calls = 0;
static bool trade_handled = false;
static float discount = 0;
static std::string purchase_messages;
int cargo_sell_price(int, bool) { ++quotes; return price; }
int contra_sell_price(int) { ++quotes; return price; }
float get_epic_bonus(P_char, int) { return discount; }
bool can_buy_contraband(P_ship, int) { return true; }
bool divine_trade_runtime_purchase(P_char, P_ship, int, int, int, int, divine_trade_goods) {
    ++trade_calls;
    return trade_handled;
}
void adjust_ship_market(int, int, int, int) { ++market_changes; }
void update_ship_status(P_ship, P_ship) { ++updates; }
void queue_ship_save(P_ship ship, const char *) {
    assert(!order.empty() && order.back() == "save:44");
    order.push_back("ship");
    ship->save_pending = true;
}
const char *cargo_type_name(int) { return "cargo"; }
const char *contra_type_name(int) { return "contraband"; }
char *coin_stringv(int, int) { static char text[] = "coins"; return text; }
std::string strip_ansi(const char *text) { return text; }
void statuslog(int, const char *, ...) {}
void send_to_char(const char *text, P_char) { purchase_messages += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[2048];
    va_list args;
    va_start(args, format);
    vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    purchase_messages += text;
}
// FUNCTIONS

int main() {
    (void)completion;
    world = rooms;
    rooms[0].number = 111;
    player captain(44);
    captain.ch.in_room = 0;
    captain.ch.player.name = const_cast<char *>("Soldon");
    GET_ALIGNMENT(&captain.ch) = -1000;

    for (int type : {SLOT_CARGO, SLOT_CONTRABAND}) {
        ShipSlot slot{};
        slot.clear();
        int cost = 0;
        assert(ship_crate_order_cost(slot, type, 1, INT_MAX, 0, &cost) && cost == INT_MAX);
        assert(ship_crate_order_cost(slot, type, INT_MAX, 1, 0, &cost) && cost == INT_MAX);
        assert(!ship_crate_order_cost(slot, type, 2, INT_MAX, 0, &cost));
        assert(!ship_crate_order_cost(slot, type, INT_MAX, INT_MAX, 0, &cost));
        assert(!ship_crate_order_cost(slot, type, 65536, 65536, 0, &cost));
        assert(ship_crate_order_cost(slot, type, 46340, 46340, 0, &cost) && cost == 2147395600);
        for (int invalid : {INT_MIN, -1, 0}) {
            assert(!ship_crate_order_cost(slot, type, invalid, 100, 0, &cost));
            assert(!ship_crate_order_cost(slot, type, 1, invalid, 0, &cost));
        }
        for (float invalid : {-1.f, 1.f, 2.f, std::numeric_limits<float>::infinity(),
                              std::numeric_limits<float>::quiet_NaN()})
            assert(!ship_crate_order_cost(slot, type, 1, INT_MAX, invalid, &cost));
        // A total float rounds down must not turn a full discount into a nominal price.
        assert(!ship_crate_order_cost(slot, type, 16777217, 1, 1.f, &cost));
        assert(ship_crate_order_cost(slot, type, 7, 1, .4f, &cost) && cost == 5);
        slot.type = type;
        slot.val0 = slot.val1 = INT_MAX - 2;
        assert(ship_crate_order_cost(slot, type, 2, 1, 0, &cost));
        assert(!ship_crate_order_cost(slot, type, 3, 1, 0, &cost));
        slot.val0 = 1;
        assert(!ship_crate_order_cost(slot, type, 1, 3, 0, &cost));
        slot.val0 = -1;
        assert(!ship_crate_order_cost(slot, type, 1, 1, 0, &cost));
        slot.val0 = 1;
        slot.val1 = -1;
        assert(!ship_crate_order_cost(slot, type, 1, 1, 0, &cost));

        int (*buy)(P_char, P_ship, char *) = buy_cargo;
        if (type == SLOT_CONTRABAND) buy = buy_contra;
        ShipData ship{};
        ship.m_class = SH_GALLEON;
        for (auto &entry : ship.slot) entry.clear();
        auto reset_observers = [&] {
            order.clear(); purchase_messages.clear();
            market_changes = updates = quotes = trade_calls = 0;
            ship.save_pending = false;
        };
        auto refused = [&](const char *input) {
            reset_observers();
            const auto purse = wallet(&captain.ch);
            const ShipSlot before = ship.slot[0];
            char argument[80]; strcpy(argument, input);
            assert(buy(&captain.ch, &ship, argument) == TRUE);
            assert(wallet(&captain.ch) == purse);
            assert(!memcmp(&before, &ship.slot[0], sizeof(before)));
            assert(!ship.save_pending && !market_changes && !updates && order.empty());
            assert(purchase_messages.find("You buy") == std::string::npos);
        };
        GET_COPPER(&captain.ch) = 1000;
        for (const char *input : {"", "0", "-1000", "-", "2x", "1 2", "2147483648",
                                  "999999999999999999999999999999999999"}) {
            refused(input);
            assert(quotes == 0 && trade_calls == 0);
        }
        for (int invalid_price : {0, -1, INT_MAX}) {
            price = invalid_price;
            refused("2");
            assert(quotes == 1 && trade_calls == 0);
        }
        price = 100;
        discount = type == SLOT_CARGO ? .25f : 0;
        const int per_crate = type == SLOT_CARGO ? 75 : 100;
        char two[] = "2", one[] = "1";
        reset_observers();
        assert(buy(&captain.ch, &ship, two) == TRUE);
        assert(GET_MONEY(&captain.ch) == 1000 - 2 * per_crate);
        assert(ship.slot[0].type == type && ship.slot[0].index == 0 &&
               ship.slot[0].position == SLOT_HOLD && ship.slot[0].val0 == 2 &&
               ship.slot[0].val1 == 2 * per_crate);
        assert(market_changes == 1 && updates == 1 && ship.save_pending);
        assert((order == std::vector<std::string>{"save:44", "ship"}));
        reset_observers();
        assert(buy(&captain.ch, &ship, one) == TRUE);
        assert(ship.slot[0].val0 == 3 && ship.slot[0].val1 == 3 * per_crate &&
               ship.slot[1].type == SLOT_EMPTY && GET_MONEY(&captain.ch) == 1000 - 3 * per_crate);

        // Both refusal modes must leave new loads and existing stacks untouched.
        for (bool stacked : {true, false}) {
            if (!stacked) ship.slot[0].clear();
            GET_COPPER(&captain.ch) = 1000;
            GET_SILVER(&captain.ch) = GET_GOLD(&captain.ch) = GET_PLATINUM(&captain.ch) = 0;
            assert(currency_transaction_reserve_trade(&captain.ch, -950));
            const auto rejected = currency_transaction_health_copy().rejected;
            refused("2");
            assert(currency_transaction_health_copy().rejected == rejected + 1);
            currency_transaction_release_trade(44);
            assert(currency_transaction_reserve_world_quest(&captain.ch, 950));
            refused("2");
            currency_transaction_release_world_quest(44);
            GET_COPPER(&captain.ch) = 0;
            refused("2");
        }
        GET_COPPER(&captain.ch) = 1000;
        trade_handled = true;
        refused("2");
        assert(trade_calls == 1);
        trade_handled = false;
        discount = 0;
        price = INT_MAX;
        GET_COPPER(&captain.ch) = INT_MAX;
        reset_observers();
        assert(buy(&captain.ch, &ship, one) == TRUE);
        assert(GET_MONEY(&captain.ch) == 0 && ship.slot[0].val1 == INT_MAX);
        price = 1;
        GET_COPPER(&captain.ch) = 1000;
        refused("1"); // Invoice basis addition would overflow.

        // With every stock hull, capacity refuses the old oversized example first,
        // including ships ordered by Soldon. No synthetic capacity bypass is used.
        for (int hull = 0; hull < MAXSHIPCLASS; ++hull) {
            for (auto &entry : ship.slot) entry.clear();
            ship.m_class = hull;
            price = 65536;
            refused("65536");
            assert(quotes == 0 && trade_calls == 0);
        }
    }
}
'''

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ship-cargo-purchase-", dir=output) as temporary:
    source = Path(temporary) / "purchase.cpp"
    binary = Path(temporary) / "purchase"
    source.write_text(harness.replace("// FUNCTIONS", functions))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        "-Wno-missing-field-initializers", "-g", "-O1",
        "-fsanitize=address,undefined,float-cast-overflow", "-fno-sanitize-recover=all",
        "-fno-pie", "-no-pie", "-ffunction-sections", "-fdata-sections", "-Isrc", "-Itests/async",
        "-I/usr/include/mysql", str(source), "src/economy/currency_transaction.c",
        "src/economy/currency_command.c", "src/persistence/critical_command.c",
        "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=60)
print("PASS: checked cargo/contraband invoices, stock hull limits, stacked loads, and real payment refusals preserve inventory")
