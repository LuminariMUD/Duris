#!/usr/bin/env python3
"""#769: execute ship geometry, tactical map, text contacts, lock and GMCP JSON.

World lookup, crew contact_bonus and output are controlled; the production functions
are compiled unchanged under ASan/UBSan. Movement samples use the same physical
positions on either side of room transitions, not a booted-world sailing trip.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

FUNCTIONS = "\n\n".join(
    extract_function(file, signature)
    for file, signatures in (
        ("ship_utils.c", (
            "ShipObjHash::ShipObjHash()", "P_ship ShipObjHash::find(P_obj key)",
            "bool ShipObjHash::add(P_ship ship)",
            "bool ShipObjHash::get_first(visitor &vs)", "bool ShipObjHash::get_next(visitor &vs)",
            "float range(float x1, float y1, float z1, float x2,",
            "static float ship_range(P_ship ship, P_ship target, int x, int y)\n",
            "static bool ship_contact_coords(P_ship ship, P_ship target, int &x, int &y)",
            "void normalize_direction(float &dir)", "int get_arc(float heading, float bearing)",
            "const char *get_arc_indicator(int arc_no)",
            "float bearing(float x1, float y1, float x2, float y2)",
            "void setcontact(int i, P_ship target, P_ship ship, int x, int y)",
            "bool ship_target_in_contact(P_ship ship)", "int getcontacts(P_ship ship, bool limit_range)",
            "bool getmap(P_ship ship, bool limit_range)",
            "bool has_no_weapons(const ShipData *ship)", "bool ocean_pvp_state()",
        )),
        ("map.c", ("unsigned int calculate_relative_room(",)),
        ("ship_control.c", ("int look_contacts(P_char ch, P_ship ship)",
                            "int do_lock_target(P_char ch, P_ship ship, char *arg)")),
        ("gmcp.c", ("static cJSON *json_build_ship_contacts(",)),
    )
    for signature in signatures
)

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "core/utility.h"
#include "world/db.h"
#include "world/map.h"
#include "ships/ships.h"
#include "ships/ship_npc_ai.h"
#include <cjson/cJSON.h>
#include <cassert>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>

static room_data rooms[32005]{};
P_room world = rooms;
int top_of_world = 32004, top_of_zone_table = 1;
static zone_data zones[2]{};
zone_data *zone_table = zones;
ShipObjHash shipObjHash;
ShipMap tactical_map[101][101]{};
ContactData contacts[MAXSHIPS]{};
const char *ship_symbol[NUM_SECT_TYPES]{};
static ShipData observer{}, target{};
static obj_data hulls[2]{};
static int contact_bonus;
static std::string output;
int ShipCrew::get_contact_range_mod() const { return contact_bonus; }
int real_room0(const int vnum) {
    const int r = vnum - 1000 + 1;
    return r > 0 && r <= zones[0].mapx * zones[0].mapy ? r : 0;
}
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[4096]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof text, format, args); va_end(args); output += text;
}
std::string strip_ansi(const char *text) { return text; }
bool isname(const char *word, const char *names) { return !strcasecmp(word, names); }
P_char get_char2(char *) { return nullptr; }
int ShipData::get_maxspeed(P_char) const { return 10; }
void act_to_all_in_ship(P_ship, const char *) {}
void act_to_all_in_ship_f(P_ship, const char *, ...) {}
NPCShipAI::NPCShipAI(P_ship, P_char) { abort(); }
''' + FUNCTIONS + r'''

static void setup(int width = 200, int height = 160) {
    memset(rooms, 0, sizeof rooms);
    zones[0].flags = ZONE_MAP;
    zones[0].mapx = width; zones[0].mapy = height; zones[0].real_bottom = 1;
    for (int i = 1; i <= top_of_world; ++i) world[i].number = 999 + i;
    observer.x = observer.y = target.x = target.y = 50;
    observer.z = target.z = 0;
    observer.flags = target.flags = LOADED;
    observer.target = &target;
    observer.heading = target.heading = 0;
    target.race = EVILSHIP;
    contact_bonus = 0;
}

static void place(P_ship ship, int x, int y) {
    if (ship->location > 0) world[ship->location].contents = nullptr;
    ship->location = 1 + x + y * zones[0].mapx;
    world[ship->location].contents = ship->shipobj;
}

static void near(double actual, double expected) { assert(fabs(actual - expected) < 0.0001); }

static void presentation(bool visible, double distance = 0) {
    output.clear(); look_contacts(nullptr, &observer);
    assert((output.find("Enemy") != std::string::npos) == visible);
    cJSON *root = json_build_ship_contacts(&observer);
    cJSON *items = cJSON_GetObjectItemCaseSensitive(root, "contacts");
    assert(cJSON_GetArraySize(items) == (visible ? 1 : 0));
    if (visible) {
        cJSON *item = cJSON_GetArrayItem(items, 0);
        near(cJSON_GetObjectItemCaseSensitive(item, "range")->valuedouble, distance);
        assert(cJSON_GetObjectItemCaseSensitive(item, "x")->valueint == contacts[0].x);
        assert(cJSON_GetObjectItemCaseSensitive(item, "y")->valueint == contacts[0].y);
        assert(cJSON_GetObjectItemCaseSensitive(item, "bearing")->valueint == int(contacts[0].bearing));
        assert(!strcmp(cJSON_GetObjectItemCaseSensitive(item, "arc")->valuestring, contacts[0].arc));
    }
    cJSON_Delete(root);
}

static void check_contact(int x, int y, double distance, double direction, const char *arc) {
    assert(getcontacts(&observer) == 1);
    assert(contacts[0].ship == &target && contacts[0].x == x && contacts[0].y == y);
    near(contacts[0].range, distance); near(contacts[0].bearing, direction);
    assert(!strcmp(contacts[0].arc, arc));
    const ContactData saved = contacts[0];
    assert(ship_target_in_contact(&observer));
    assert(!memcmp(&saved, &contacts[0], sizeof saved));
    presentation(true, distance);
    assert(getmap(&observer, true));
    assert(tactical_map[x][100-y].rroom == target.location);
    if (x != 50 || y != 50) assert(strstr(tactical_map[x][100-y].map, "AB"));
    int markers = 0;
    for (int i = 0; i < 100; ++i)
        for (int j = 0; j < 100; ++j)
            if (strstr(tactical_map[i][j].map, "AB")) ++markers;
    assert(markers == ((x == 50 && y == 50) ? 0 : 1));
}

static void edges() {
    setup(); place(&observer, 1, 20); place(&target, 199, 20);
    check_contact(48, 50, 2, 270, "PS");
    target.target = &observer;
    assert(ship_target_in_contact(&target) && getcontacts(&target) == 1);
    near(contacts[0].range, 2); near(contacts[0].bearing, 90);
    char_data captain{}; captain.player.name = const_cast<char *>("Captain");
    observer.ownername = captain.player.name; observer.target = nullptr;
    assert(do_lock_target(&captain, &observer, target.id));
    assert(observer.target == &target && observer.timer[T_TARGET_IDLE] == 300);
    place(&observer, 20, 1); place(&target, 20, 159);
    check_contact(50, 52, 2, 0, "FR");
    place(&observer, 1, 1); place(&target, 199, 159);
    check_contact(48, 52, sqrt(8), 315, "PS");
    puts("PASS horizontal/vertical/diagonal seams, reciprocal detection, bearing, arcs, text/JSON/map and lock command");
}

static void thresholds() {
    setup(); place(&observer, 190, 20);
    for (contact_bonus = 0; contact_bonus <= 2; ++contact_bonus) {
        place(&target, 25 + contact_bonus, 20);
        for (float offset : {-0.01f, 0.0f, 0.01f}) {
            target.x = 50 + offset;
            const bool visible = offset <= 0;
            assert(getcontacts(&observer) == (visible ? 1 : 0));
            assert(ship_target_in_contact(&observer) == visible);
            presentation(visible, 35 + contact_bonus + target.x - 50);
        }
        target.x = 50; target.z = 1;
        assert(!ship_target_in_contact(&observer) && getcontacts(&observer) == 0);
        target.z = 0;
    }
    contact_bonus = 0; place(&target, 195, 20); target.flags |= DOCKED;
    assert(!ship_target_in_contact(&observer)); presentation(true, 5);
    target.x = 50.01f; presentation(false);
    target.x = 50;
    for (auto flags : {0u, LOADED | SINKING, LOADED | DOCKED}) {
        target.flags = flags;
        assert(!ship_target_in_contact(&observer));
        // Presentation has always included these states; lock availability differs.
        presentation(true, 5);
    }
    target.flags = LOADED | FLYING; target.z = 10;
    assert(ship_target_in_contact(&observer)); presentation(true, sqrt(125));
    puts("PASS 35/36/37 boundaries, fractions, altitude, docked 5-room presentation and unavailable locks");
}

static void movement() {
    setup();
    for (int axis = 0; axis < 2; ++axis)
    for (int together = 0; together < 2; ++together)
    for (int tick = 0; tick <= 40; ++tick) {
        const int size = axis == 0 ? 200 : 160;
        const double pos = size - 2 + tick * 0.125;
        const double other = together ? pos - 2.25 : size - 4.25;
        // y increases north in ShipData but south in room numbering.
        const int room = int(floor(pos)) % size;
        const int observer_room = int(floor(other)) % size;
        if (!axis) {
            place(&target, room, 20); place(&observer, observer_room, 20);
            target.x = 50 + pos - floor(pos); observer.x = 50 + other - floor(other);
        } else {
            place(&target, 20, (size - room) % size);
            place(&observer, 20, (size - observer_room) % size);
            target.x = observer.x = 50;
            target.y = 50 + pos - floor(pos); observer.y = 50 + other - floor(other);
        }
        assert(getcontacts(&observer) == 1 && ship_target_in_contact(&observer));
        near(contacts[0].range, pos - other);
        presentation(true, pos - other);
        assert(getmap(&observer, true));
        assert(tactical_map[contacts[0].x][100-contacts[0].y].rroom == target.location);
    }
    puts("PASS fractional samples before/after both seams, one moving ship and ships moving together");
}

static void dimensions() {
    setup(10, 6); place(&observer, 1, 1); place(&target, 9, 5);
    check_contact(48, 52, sqrt(8), 315, "PS");
    place(&observer, 0, 0); place(&target, 5, 0);
    check_contact(55, 50, 5, 90, "SP"); // Equal-distance tie retains raw sign.
    target.x = 50.25f;
    check_contact(45, 50, 4.75, 270, "PS"); // Fraction decides the shorter image.
    target.x = 50; place(&target, 0, 3);
    check_contact(50, 47, 3, 180, "RF");
    target.y = 49.75f;
    check_contact(50, 53, 2.75, 0, "FR");
    setup(1, 1); place(&observer, 0, 0); place(&target, 0, 0);
    target.x = 50.25f;
    check_contact(50, 50, 0.25, 90, "SP");
    setup(); place(&observer, 0, 0); place(&target, 2, 0);
    const int valid = target.location;
    for (int invalid : {-1, top_of_world + 1, 32001}) {
        target.location = invalid;
        assert(!ship_target_in_contact(&observer) && getcontacts(&observer, false) == 0);
    }
    target.location = valid;
    for (int zone : {1, 2}) {
        world[valid].zone = zone;
        assert(!ship_target_in_contact(&observer) && getcontacts(&observer, false) == 0);
    }
    world[valid].zone = 0;
    for (int dimension : {0, -1}) {
        zones[0].mapx = dimension;
        assert(!ship_target_in_contact(&observer) && !getmap(&observer, true));
        presentation(false);
        zones[0].mapx = 200; zones[0].mapy = dimension;
        assert(!ship_target_in_contact(&observer) && !getmap(&observer, true));
        presentation(false);
        zones[0].mapy = 160;
    }
    observer.location = 32001;
    cJSON *root = json_build_ship_contacts(&observer);
    assert(!cJSON_GetObjectItemCaseSensitive(root, "worldX"));
    assert(!cJSON_GetObjectItemCaseSensitive(root, "worldY"));
    assert(cJSON_GetArraySize(cJSON_GetObjectItemCaseSensitive(root, "contacts")) == 0);
    cJSON_Delete(root);
    observer.location = 1;
    zones[0].flags = 0;
    assert(!ship_target_in_contact(&observer) && getcontacts(&observer, false) == 0);
    puts("PASS small/non-square grids, fractional half-map ties, invalid/tail rooms, zones and dimensions");
}

static void pvp() {
    setup(); place(&observer, 10, 10); place(&target, 90, 10);
    observer.race = GOODIESHIP;
    observer.m_class = target.m_class = SH_FRIGATE;
    assert(!ocean_pvp_state());
    place(&observer, 1, 10); place(&target, 199, 10);
    assert(ocean_pvp_state());
    target.flags |= DOCKED;
    assert(!ocean_pvp_state());
    target.flags = LOADED;
    target.race = GOODIESHIP;
    assert(!ocean_pvp_state());
    target.race = EVILSHIP;
    for (P_ship small : {&observer, &target}) {
        small->m_class = SH_SLOOP;
        assert(!ocean_pvp_state());
        small->m_class = SH_YACHT;
        assert(!ocean_pvp_state());
        small->slot[0].type = SLOT_WEAPON;
        assert(ocean_pvp_state());
        small->slot[0].type = 0;
        small->m_class = SH_FRIGATE;
    }
    puts("PASS ocean PvP requires opposing ships in actual contact, including across seams");
}

static void last_room() {
    setup();
    // top_of_world is the last valid index, not the room count.
    const int saved_top = top_of_world;
    top_of_world = zones[0].mapx * zones[0].mapy;
    place(&observer, 199, 159); place(&target, 198, 159);
    cJSON *root = json_build_ship_contacts(&observer);
    assert(cJSON_GetObjectItemCaseSensitive(root, "worldX"));
    assert(cJSON_GetObjectItemCaseSensitive(root, "worldY"));
    assert(cJSON_GetObjectItemCaseSensitive(root, "worldX")->valueint == 199);
    assert(cJSON_GetObjectItemCaseSensitive(root, "worldY")->valueint == 159);
    cJSON_Delete(root);
    top_of_world = saved_top;
    puts("PASS GMCP includes coordinates for the last valid world room");
}

int main() {
    for (auto &symbol : ship_symbol) symbol = "~~";
    observer.shipobj = &hulls[0]; target.shipobj = &hulls[1];
    for (auto &hull : hulls) { hull.type = ITEM_SHIP; hull.value[6] = 1; }
    observer.id = const_cast<char *>("CD"); target.id = const_cast<char *>("AB");
    target.name = const_cast<char *>("Enemy");
    assert(shipObjHash.add(&observer) && shipObjHash.add(&target));
    edges(); thresholds(); movement(); dimensions(); last_room(); pvp();
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ship-contacts-", dir=build) as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(HARNESS)
    binary = path / "test"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Isrc", "-I/usr/include/mysql",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
        "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        str(path / "test.cpp"), str(HARNESS_STUBS), "-lcjson", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
