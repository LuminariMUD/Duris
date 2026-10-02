#!/usr/bin/env python3
"""Run the production `empty` command: it moves what fits in memory and reports once.

The world is a stub; start_empty() and its checks are the real source, run under
ASan and UBSan.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import extract_function


def take(signature):
    return extract_function("actobj.c", signature)


PRELUDE = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <string>
#define FALSE 0
#define TO_CHAR 1
#define REAL 0
#define USE_SPACE 0
#define ITEM_CONTAINER 15
#define ITEM_STORAGE 16
#define ITEM_QUIVER 17
#define ITEM_MISSILE 18
#define ITEM_CORPSE 24
#define CORPSE_FLAGS 1
#define PC_CORPSE 1
#define ITEM_NODROP 1
#define ITEM_ARTIFACT 2
#define CONT_CLOSED 4
#define PLAYER_COMPONENT_STATUS 1
#define PLAYER_COMPONENT_EQUIPMENT 2
#define PLAYER_COMPONENT_INVENTORY 4
#define IS_SET(a, b) ((a) & (b))
#define IS_PC(ch) true
#define GET_PID(ch) 42
#define IS_TRUSTED(ch) false
#define GET_ITEM_TYPE(o) ((o)->type)
#define GET_OBJ_WEIGHT(o) ((o)->weight)
#define IS_ARTIFACT(o) ((o)->extra_flags & ITEM_ARTIFACT)
#define OBJ_CARRIED_BY(o, ch) ((o)->carrier == (ch))
#define OBJ_WORN_BY(o, ch) false
#define OBJ_ROOM(o) false
struct char_data { int in_room = 1; };
using P_char = char_data *;
struct obj_data {
    int type = ITEM_CONTAINER, weight = 1, extra_flags = 0;
    int value[8] = {};
    const char *short_description = "a bag";
    P_char carrier = nullptr;
    obj_data *contains = nullptr, *next_content = nullptr, *inside = nullptr;
    struct { int room = 0; } loc;
};
using P_obj = obj_data *;
static std::string output;
static int saves = 0;
static void send_to_char(const char *text, P_char) { output += text; }
static void send_to_char_f(P_char, const char *format, ...)
{
    char line[256];
    va_list args;
    va_start(args, format);
    vsnprintf(line, sizeof(line), format, args);
    va_end(args);
    output += line;
}
static void act(const char *text, int, P_char, P_obj, P_obj, int) { output += text; }
static P_char training_dummy_item_owner(P_obj) { return nullptr; }
static bool item_command_container_is_valid(P_obj o) { return o->type != 0; }
static bool item_movement_transaction_player_busy(P_char) { return false; }
static int64_t container_total_weight(P_obj container)
{
    int64_t total = 0;
    for (P_obj o = container->contains; o; o = o->next_content)
        total += o->weight;
    return total;
}
static void obj_from_obj(P_obj o)
{
    P_obj *link = &o->inside->contains;
    while (*link != o)
        link = &(*link)->next_content;
    *link = o->next_content;
    o->next_content = nullptr;
    o->inside = nullptr;
}
static void obj_to_obj(P_obj o, P_obj container)
{
    o->next_content = container->contains;
    container->contains = o;
    o->inside = container;
}
static void char_light(P_char) {}
static void room_light(int, int) {}
static void mark_player_dirty_components(int, int) { ++saves; }
static void writeSavedItem(P_obj) {}
static P_obj corpse_saved = nullptr;
static void writeCorpse(P_obj corpse) { corpse_saved = corpse; }
'''

DRIVER = r'''
static void fill(P_obj source, P_obj *items, int count)
{
    for (int i = count - 1; i >= 0; --i)
        obj_to_obj(items[i], source);
}
static int count(P_obj container)
{
    int n = 0;
    for (P_obj o = container->contains; o; o = o->next_content)
        ++n;
    return n;
}
int main()
{
    char_data actor;
    obj_data source, target, a, b, c;
    source.carrier = target.carrier = &actor;
    target.value[0] = 10;
    target.short_description = "a chest";
    P_obj items[] = { &a, &b, &c };

    // Everything that fits moves at once and the owner is marked for its next save.
    fill(&source, items, 3);
    start_empty(&actor, &source, &target);
    assert(count(&source) == 0 && count(&target) == 3 && saves == 1 && !corpse_saved);
    assert(output == "You moved 3 items from a bag to a chest.\n");

    // Capacity stops the move at the first item that does not fit.
    obj_data small_source, small_target, d, e;
    small_source.carrier = small_target.carrier = &actor;
    small_target.value[0] = 1;
    P_obj two[] = { &d, &e };
    fill(&small_source, two, 2);
    output.clear(); saves = 0;
    start_empty(&actor, &small_source, &small_target);
    assert(count(&small_source) == 1 && count(&small_target) == 1 && saves == 1);
    assert(output.find("will not fit") != std::string::npos);
    assert(output.find("You moved 1 item from") != std::string::npos);

    // One item that may not go refuses the whole empty; nothing moves.
    obj_data guarded_source, guarded_target, f, artifact;
    guarded_source.carrier = guarded_target.carrier = &actor;
    guarded_target.value[0] = 10;
    artifact.extra_flags = ITEM_ARTIFACT;
    P_obj guarded[] = { &f, &artifact };
    fill(&guarded_source, guarded, 2);
    output.clear(); saves = 0;
    start_empty(&actor, &guarded_source, &guarded_target);
    assert(count(&guarded_source) == 2 && count(&guarded_target) == 0 && saves == 0);
    assert(output == "Nothing was emptied; an item cannot be moved into that destination.\r\n");

    // A closed destination is refused before anything moves.
    obj_data closed_source, closed_target, g;
    closed_source.carrier = closed_target.carrier = &actor;
    closed_target.value[1] = CONT_CLOSED;
    P_obj one[] = { &g };
    fill(&closed_source, one, 1);
    output.clear();
    start_empty(&actor, &closed_source, &closed_target);
    assert(count(&closed_source) == 1 && output.find("could not start") != std::string::npos);

    // A player corpse an empty fills is saved; the putter's own save drops the items.
    obj_data corpse_source, corpse, h;
    corpse_source.carrier = corpse.carrier = &actor;
    corpse.type = ITEM_CORPSE;
    corpse.value[0] = 10;
    corpse.value[CORPSE_FLAGS] = PC_CORPSE;
    P_obj loot[] = { &h };
    fill(&corpse_source, loot, 1);
    start_empty(&actor, &corpse_source, &corpse);
    assert(count(&corpse) == 1 && corpse_saved == &corpse);
    puts("empty command: full move, capacity stop, refused item, closed target and player "
         "corpse passed");
}
'''

parts = [PRELUDE]
for signature in ("void save_filled_container(", "bool bulk_put_destination_available(",
                  "bool bulk_put_permitted(",
                  "bool empty_source_available(", "bool empty_target_available(",
                  "bool empty_item_restrictions_allow(", "void start_empty("):
    parts.append(take(signature))
parts.append(DRIVER)
with tempfile.TemporaryDirectory(prefix="empty-command-") as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text("\n".join(parts))
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-g", str(cpp), "-o", str(binary)],
                   check=True)
    subprocess.run([str(binary)], check=True)
