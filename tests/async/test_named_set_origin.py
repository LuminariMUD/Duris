#!/usr/bin/env python3
"""Execute durable origin, exact legacy resolution, and nested item wire storage."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

harness = r'''
#include "core/prototypes.h"
#include "persistence/persistence_log.h"
#include "core/utils.h"
#include "item/named_set_origin.h"
#include "item/random_equipment.h"
#include "sql/item_extra_descr_codec.h"
#include "player/player_snapshot_codec.h"
#include "world/db.h"
#include "world/vnum.obj.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <string>
#include <vector>

static zone_data zones[] = {
    {.number = 13, .name = const_cast<char *>("&+WBraddistock Mansion&n")},
    {.number = 1350, .name = const_cast<char *>("&+WBraddistock Mansion&n")},
    {.number = 44, .name = const_cast<char *>("&+LThe Underworld&n")},
    {.number = 300, .name = const_cast<char *>("&+LThe Underworld&n")},
    {.number = 808, .name = const_cast<char *>("&+gCeothia&n")},
    {.number = 811, .name = const_cast<char *>("&n&+gCeothia&n")},
    {.number = 814, .name = const_cast<char *>("&+gCeothia&n")},
    {.number = 196, .name = const_cast<char *>("&+RTiamat&n")},
    {.number = 199, .name = const_cast<char *>("&+RAstral Plane, Tiamat&n")},
    {.number = 204, .name = const_cast<char *>("Neverwind Valley")},
    {.number = 990, .name = const_cast<char *>("Neverwinter Woods")},
    {.number = 740, .name = const_cast<char *>("&+rBloodstone Keep&n")},
};
zone_data *zone_table = zones;
int top_of_zone_table = sizeof zones / sizeof zones[0] - 1;
static index_data indexes[2];
P_index obj_index = indexes;
char *str_dup(const char *text) { return strdup(text); }
void *__malloc(size_t size, const char *, const char *, int) { return calloc(1, size); }
bool isname(const char *word, const char *keywords) { return !strcmp(word, keywords); }
P_obj read_object(int nr, int mode) {
    assert(mode == REAL);
    auto *object = new obj_data{};
    object->R_num = nr;
    return object;
}

''' + extract_function("utility.c", "string strip_ansi(") + \
    extract_function("actwiz.c", "struct obj_data *clone_obj(") + \
    extract_function("actinf.c", "char *find_ex_description(") + r'''
static void clear_origin(obj_data &object) {
    while (object.ex_description) {
        auto *entry = object.ex_description;
        object.ex_description = entry->next;
        free(entry->keyword); free(entry->description); free(entry);
    }
}
int main() {
    indexes[0].virtual_number = VOBJ_RANDOM_ARMOR;
    indexes[1].virtual_number = VOBJ_RANDOM_WEAPON;
    for (int reverse : {0, 1}) {
        if (reverse) std::reverse(std::begin(zones), std::end(zones));
        for (int zone : {13, 1350, 44, 300, 808, 811, 814, 196, 199, 204, 990, 740, INT_MAX}) {
            obj_data object{};
            object.short_description = const_cast<char *>("an item &+rfrom &+gCeothia&n");
            assert(set_named_set_origin(&object, zone));
            assert(named_set_origin(&object).zone == zone);
            assert(object.str_mask & STRUNG_EDESC);
            object.short_description = const_cast<char *>("a completely renamed item");
            assert(named_set_origin(&object).zone == zone);
            assert(set_named_set_origin(&object, zone));
            assert(!set_named_set_origin(&object, zone == 13 ? 44 : 13));
            char key[] = "DURIS_NAMED_SET_ORIGIN_V1";
            assert(!find_ex_description(key, object.ex_description));
            auto *copy = clone_obj(&object);
            assert(copy && named_set_origin(copy).zone == zone);
            clear_origin(*copy); delete copy;
            clear_origin(object);
        }
        for (const char *title : {"Braddistock Mansion", "The Underworld", "Ceothia"}) {
            obj_data object{};
            std::string name = std::string("an item &+rfrom &+W") + title + "&n";
            object.short_description = name.data();
            auto identity = named_set_origin(&object);
            assert(identity.zone == 0 && identity.legacy_title == title);
            object.R_num = 1;
            object.value[5] = spells_data[0].spell;
            name += std::string(" of ") + spells_data[0].name + "&n";
            object.short_description = name.data();
            identity = named_set_origin(&object);
            assert(identity.zone == 0 && identity.legacy_title == title);
        }
        for (int zone : {196, 199, 204, 990, 740}) {
            auto found = std::find_if(std::begin(zones), std::end(zones),
                                      [zone](const auto &candidate) {return candidate.number == zone;});
            obj_data object{};
            std::string name = std::string("an item &+rfrom ") + found->name + "&n";
            object.short_description = name.data();
            assert(named_set_origin(&object).zone == zone);
            object.R_num = 1;
            object.value[5] = spells_data[0].spell;
            const std::string base = name;
            name += std::string(" of ") + spells_data[0].name + "&n";
            object.short_description = name.data();
            assert(named_set_origin(&object).zone == zone);
            name = base + " arbitrary text";
            object.short_description = name.data();
            assert(named_set_origin(&object).zone == 0);
            name = base + " of a forged effect";
            object.short_description = name.data();
            assert(named_set_origin(&object).zone == 0);
        }
    }
    obj_data object{};
    object.short_description = const_cast<char *>("an item &+rfrom Bloodstone Keep&n");
    extra_descr_data marker{const_cast<char *>(SQL_ITEM_NAMED_SET_ORIGIN_KEYWORD),
                            const_cast<char *>("invalid"), nullptr};
    object.ex_description = &marker;
    assert(named_set_origin(&object).zone == -1); // no legacy fallback
    assert(!clone_obj(&object));
    marker.description = const_cast<char *>("740");
    extra_descr_data duplicate = marker;
    marker.next = &duplicate;
    assert(named_set_origin(&object).zone == -1);
    duplicate.description = const_cast<char *>("13");
    assert(named_set_origin(&object).zone == -1);

    player_item_snapshot bag{};
    bag.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
    bag.equipment_slot = -1; bag.object_uid = 10; bag.vnum = 1;
    player_item_snapshot item{};
    item.parent_index = 0; item.equipment_slot = -1; item.object_uid = 11;
    item.vnum = VOBJ_RANDOM_ARMOR;
    item.extra_descriptions.push_back({SQL_ITEM_NAMED_SET_ORIGIN_KEYWORD, "808", false, {}});
    std::vector<player_item_snapshot> items{bag, item}, loaded;
    std::vector<uint8_t> bytes;
    assert(player_item_snapshot_list_encode(items, &bytes) == player_snapshot_codec_result::ok);
    const auto stored = bytes;
    assert(player_item_snapshot_list_decode(bytes.data(), bytes.size(), &loaded) == player_snapshot_codec_result::ok);
    assert(loaded[1].extra_descriptions[0].description == "808");
    std::vector<player_item_snapshot> selected, remaining;
    assert(player_item_snapshot_extract_subtree(loaded, 10, &selected, &remaining) == player_snapshot_codec_result::ok);
    assert(selected.size() == 2 && remaining.empty());
    assert(selected[1].extra_descriptions[0].description == "808");
    const std::string digits = "808";
    auto position = std::search(bytes.begin(), bytes.end(), digits.begin(), digits.end());
    assert(position != bytes.end());
    *position = 'x';
    assert(player_item_snapshot_list_decode(bytes.data(), bytes.size(), &loaded) != player_snapshot_codec_result::ok);
    items[1].extra_descriptions[0].description = std::string("808\0tail", 8);
    assert(player_item_snapshot_list_encode(items, &bytes) != player_snapshot_codec_result::ok);
    items[1].extra_descriptions[0].description = "808";
    items[1].extra_descriptions.push_back(items[1].extra_descriptions[0]);
    assert(player_item_snapshot_list_encode(items, &bytes) != player_snapshot_codec_result::ok);
    items[1].extra_descriptions.back().description = "811";
    assert(player_item_snapshot_list_encode(items, &bytes) != player_snapshot_codec_result::ok);
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="named-set-origin-", dir=build) as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
        "-fno-pie", "-no-pie", "-ffunction-sections", "-fdata-sections", "-Isrc",
        str(cpp), "src/item/named_set_origin.c", "src/item/random_equipment_tables.c",
        "src/player/player_snapshot_codec.c", str(HARNESS_STUBS), "-Wl,--gc-sections",
        "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
print("named origin, legacy collisions, hidden metadata, and nested item storage: passed")
