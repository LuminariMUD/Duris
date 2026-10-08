#!/usr/bin/env python3
"""The shop listing: it reads the next item before it extracts invalid stock, and a
listing longer than its buffer reaches the player whole and in order.

For the second, the production shopping_list() is compiled under ASan and UBSan against
stubs for the world, the keeper's stock and the output queue: a keeper carrying 700
listable items writes about 70 KB, more than the 64 KB buffer the listing is built in.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import SRC, extract_function


source = (SRC / "economy" / "shop.c").read_text()

listing = source[source.index("void shopping_list(") :]
listing = listing[: listing.index("\n}\n")]
loop = listing[listing.index("for (obj1 = keeper->carrying;") :]

assert loop.startswith("for (obj1 = keeper->carrying; obj1; obj1 = next_obj)")
assert loop.index("next_obj = obj1->next_content;") < loop.index("extract_obj(obj1, TRUE);")
assert "obj1 = obj1->next_content" not in listing

print("[PASS] the shop listing reads the next item before it extracts invalid stock")

PRELUDE = r'''
#include <cassert>
#include <cctype>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#define TRUE 1
#define FALSE 0
#define MAX_STRING_LENGTH 65536
#define ITEM_DRINKCON 17
#define EPIC_BONUS_SHOP 1
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define STAT_INDEX(v) 0
#define GET_C_CHA(ch) 100
#define GET_RACE(ch) 1
#define GET_NAME(ch) "keeper"
#define IS_ARTIFACT(obj) false
#define CAN_SEE_OBJ(ch, obj) true
#define OBJ_VNUM(obj) 0
#define CAP(s) ((s)[0] = toupper((unsigned char)(s)[0]))
struct obj_data {
    obj_data *next_content = nullptr;
    const char *short_description = "";
    const char *name = "";
    int cost = 0, type = 0;
    int value[4] = {};
};
struct char_data { obj_data *carrying = nullptr; };
typedef char_data *P_char;
typedef obj_data *P_obj;
struct { int modifier; } cha_app[1] = {{0}};
struct { float sell_percent; } shop_index[1] = {{1.0f}};
const char *drinks[] = {"water"};
std::vector<std::string> sent;
void send_to_char(const char *text, P_char) { sent.emplace_back(text); }
bool is_ok(P_char, P_char, int) { return true; }
bool isname(const char *, const char *) { return false; }
bool shop_trade_route_invalid_cleanup(P_char, P_char, P_obj, uint32_t) { return false; }
void wizlog(int, const char *, ...) {}
void extract_obj(P_obj, int) {}
const char *item_condition(P_obj) { return ""; }
float get_epic_bonus(P_char, int) { return 0; }
const char *coin_stringv(int amount) {
    static char buffer[64];
    snprintf(buffer, sizeof buffer, "%d copper", amount);
    return buffer;
}
std::string pad_ansi(const char *text, int width) {
    std::string padded(text);
    padded.resize(MAX(padded.size(), static_cast<size_t>(width)), ' ');
    return padded;
}
int checked_snprintf(char *buffer, size_t size, const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    const int written = vsnprintf(buffer, size, format, arguments);
    va_end(arguments);
    return written;
}
'''

DRIVER = r'''
int main() {
    char_data player, keeper;
    std::vector<std::string> names;
    std::vector<obj_data> stock(700);
    names.reserve(stock.size());
    for (size_t index = 0; index < stock.size(); ++index) {
        names.push_back("a long and carefully described trade good from a distant harbour, crate number " + std::to_string(index + 1));
        stock[index].short_description = names.back().c_str();
        stock[index].cost = 10;
        if (index + 1 < stock.size())
            stock[index].next_content = &stock[index + 1];
    }
    keeper.carrying = stock.data();
    shopping_list(nullptr, &player, &keeper, 0);

    std::string listing;
    for (const auto &message : sent) {
        assert(message.size() < MAX_STRING_LENGTH);
        listing += message;
    }
    assert(sent.size() > 1 && listing.size() > MAX_STRING_LENGTH);
    std::string expected = "You can buy:\r\n";
    for (size_t index = 0; index < stock.size(); ++index) {
        char line[256];
        std::string text = names[index];
        text[0] = toupper((unsigned char)text[0]);
        snprintf(line, sizeof line, "%2zu) %s for 10 copper.\r\n", index + 1,
                 pad_ansi(text.c_str(), 45).c_str());
        expected += line;
    }
    assert(listing == expected);
    puts("long shop listing arrives whole and in order");
}
'''

harness = "\n".join([PRELUDE, extract_function("economy/shop.c", "void shopping_list("), DRIVER])
with tempfile.TemporaryDirectory(prefix="shop-list-") as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-g", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
