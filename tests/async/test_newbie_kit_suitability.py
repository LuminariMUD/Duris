#!/usr/bin/env python3
"""Execute starter admission with production rules and active area data.

Selection, preparation, item-use predicates, weapon classification and slots
are production code. Skills and first-circle spells are controlled fixtures.
No live game, item identities, persistence or player data participate.
"""
from pathlib import Path
import re
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function
from test_newbie_kit_plan import tables, extra
from test_flatfile_chaos_new_character_kit import world_object_text

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "magic/spells.h"
#include "item/objmisc.h"
#include "account/newbie_kit_plan.h"
#include "world/object_template.h"
#include "world/vnum.room.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <map>
static std::map<int, object_template> prototypes;
const object_template *find_object_template(int vnum) {
    const auto found = prototypes.find(vnum);
    return found == prototypes.end() ? nullptr : &found->second;
}
int real_mobile(const int) { return -1; }
int GET_CLASS(P_char ch, uint cls) { return ch->player.m_class & cls; }
int GET_PRIME_CLASS(P_char ch, uint cls) { return GET_CLASS(ch, cls); }
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
bool has_innate(P_char ch, int innate) {
    return (IS_CENTAUR(ch) && innate == INNATE_HORSE_BODY) ||
           (IS_DRIDER(ch) && innate == INNATE_SPIDER_BODY);
}
static int skill_level = 1;
int GET_LVL_FOR_SKILL(P_char, int skill) { return skill ? skill_level : 0; }
int get_spell_circle(P_char, int) { return 0; }
bool creation_all_classes_enabled() { return false; }
P_room world = nullptr;
extern const int top_of_world = -1;
P_index obj_index = nullptr;
static int direct_grants;
void load_obj_to_newbies(P_char) { ++direct_grants; }
static void start_grant_boundary(P_char ch, bool grant_newbie_kit) {
    START_GRANT
}
static void add_prototype(int vnum, int type, unsigned long flags,
                          unsigned long wear, unsigned long classes,
                          unsigned long races, int weapon) {
    auto &obj = prototypes[vnum];
    obj.type = type;
    obj.extra_flags = flags;
    obj.wear_flags = wear;
    obj.anti_flags = classes;
    obj.anti2_flags = races;
    obj.value[0] = weapon;
}
'''

DRIVER = r'''
static int count(const std::vector<prepared_newbie_item> &kit, int vnum) {
    return std::count_if(kit.begin(), kit.end(), [vnum](const auto &item) {
        return item.item.vnum == vnum;
    });
}
int main() {
    LOAD_PROTOTYPES
    for (int vnum : newbie_kit_template_vnums()) assert(find_object_template(vnum));
    pc_only_data pc{};
    char_data ch{};
    ch.only.pc = &pc;
    ch.player.level = 1;
    ch.in_room = NOWHERE;
    for (int race : {RACE_GITHZERAI, RACE_GITHYANKI}) {
        ch.player.race = race;
        ch.player.m_class = CLASS_PSIONICIST;
        const auto kit = prepare_legacy_newbie_plan(&ch);
        assert(count(kit, 706) == 1 && count(kit, 1131) == 1);
    }
    for (int race : {RACE_DROW, RACE_DRIDER, RACE_GOBLIN}) {
        ch.player.race = race;
        ch.player.m_class = CLASS_BLIGHTER;
        const auto kit = prepare_legacy_newbie_plan(&ch);
        assert(count(kit, race == RACE_GOBLIN ? 612 : 604) == 1);
        assert(count(kit, 618) == 0 && count(kit, 390) == 0);
    }
    ch.player.race = RACE_ORC;
    assert(count(prepare_legacy_newbie_plan(&ch), 618) == 1);
    for (int race : {RACE_MOUNTAIN, RACE_DUERGAR}) {
        ch.player.race = race;
        ch.player.m_class = CLASS_BERSERKER;
        direct_grants = 0;
        start_grant_boundary(&ch, true);
        assert(direct_grants == 1);
        start_grant_boundary(&ch, false);
        assert(direct_grants == 1); // deferred start leaves the grant to nanny
        assert(count(prepare_legacy_newbie_plan(&ch), 1107) == 1);
    }
    for (int alignment : {-1000, 0, 1000}) {
        ch.player.race = RACE_MINOTAUR;
        ch.specials.alignment = alignment;
        for (int cls : {CLASS_SHAMAN, CLASS_WARRIOR}) {
            ch.player.m_class = cls;
            const auto kit = prepare_legacy_newbie_plan(&ch);
            for (int vnum : {108, 109, 111})
                assert(count(kit, vnum) == (cls == CLASS_SHAMAN ? 1 : 0));
        }
    }
    unsigned combinations = 0;
    for (const auto &race : playable_races) {
        if (race.race_id == -1) break;
        ch.player.race = race.race_id;
        for (const auto &cls : class_bits) {
            if (class_table[race.race_id][cls[0]] == 5) continue;
            ch.player.m_class = cls[1];
            for (int alignment : {-1000, 0, 1000}) {
                ch.specials.alignment = alignment;
                const auto kit = prepare_legacy_newbie_plan(&ch);
                int containers = 0;
                for (const auto &item : kit) {
                    const auto *obj = find_object_template(item.item.vnum);
                    assert(obj);
                    containers += obj->type == ITEM_CONTAINER;
                    const auto facts = capture_newbie_item_facts(&ch, item.item);
                    assert(facts.available && facts.weapon_admitted);
                }
                assert(containers == 1);
                ++combinations;
            }
        }
    }
    ch.player.race = RACE_HUMAN;
    for (int cls : {CLASS_PALADIN, CLASS_ANTIPALADIN}) {
        ch.player.m_class = cls;
        const auto kit = prepare_legacy_newbie_plan(&ch);
        assert(count(kit, 1104) == 1 && count(kit, 1105) == 2);
    }
    ch.player.m_class = CLASS_WARRIOR;
    assert(!capture_newbie_item_facts(&ch, {108, true}).available);
    ch.player.race = RACE_MINOTAUR;
    assert(!capture_newbie_item_facts(&ch, {1106, true}).available); // helmet
    assert(!capture_newbie_item_facts(&ch, {1103, true}).available); // boots
    prototypes[1106].wear_flags = ITEM_WEAR_HEAD | ITEM_WEAR_NECK;
    assert(capture_newbie_item_facts(&ch, {1106, true}).available);
    prototypes[1106].wear_flags = ITEM_HOLD;
    assert(capture_newbie_item_facts(&ch, {1106, true}).available); // held-only item
    ch.player.race = RACE_HUMAN;
    for (int level : {0, 2}) {
        skill_level = level;
        assert(!capture_newbie_item_facts(&ch, {1112, true}).weapon_admitted);
    }
    skill_level = 1;
    assert(capture_newbie_item_facts(&ch, {1112, true}).weapon_admitted);
    prototypes[1104].anti2_flags = 1U << (RACE_HUMAN - 1);
    assert(!capture_newbie_item_facts(&ch, {1104, true}).available);
    // Only the requested bits changed on these shared objects.
    assert(prototypes[1104].anti_flags == (87572483 | CLASS_PALADIN | CLASS_ANTIPALADIN));
    assert(prototypes[1105].anti_flags == (87556099 | CLASS_PALADIN | CLASS_ANTIPALADIN));
    assert(prototypes[1131].anti_flags == (146913792 | CLASS_PSIONICIST));
    printf("starter suitability: %u normal race/class/alignment cases and all four review regressions passed\n", combinations);
}
'''


def main():
    nanny = (ROOT / "src/account/nanny.c").read_text()
    start = extract_function("actwiz.c", "static void do_start_impl(")
    start_grant = re.search(r"if \(grant_newbie_kit\b.*?\n\t\}", start, re.S).group(0)
    deferred = nanny.split("do_start_deferred_newbie_kit(ch, 0);", 1)[1]
    assert "load_obj_to_newbies(ch);" in deferred.split("else", 1)[0]
    constants = (ROOT / "src/core/constant.c").read_text()
    arrays = [re.search(r"^const (?:int|struct playable_race_info) " + name +
                        r"\[.*?\n\};", constants, re.S | re.M).group(0)
              for name in ("class_table", "playable_races")]
    classes = (ROOT / "src/account/creation_availability_config.c").read_text()
    names = classes.split("static const struct named_id class_names[] = {", 1)[1].split("};", 1)[0]
    class_bits = "const int class_bits[][2] = {" + ",".join(
        "{" + number + ", CLASS_" + name.upper().replace("-", "") + "}"
        for name, number in re.findall(r'\{ "([a-z-]+)", (\d+) \}', names)) + "};"
    vnums = {390, 393, 458, 29319, 91519}
    for items in list(tables.values()) + list(extra.values()):
        vnums.update(items)
    world = world_object_text()
    loads = []
    for vnum in sorted(vnums):
        record = re.search(rf"(?ms)^#{vnum}\s*\n(.*?)(?=^#\d+\s*$|^\$~|\Z)", world)
        assert record, vnum
        payload = record[1].split("~", 4)[4].strip().splitlines()
        flags = [int(value) for value in payload[0].split()]
        assert len(flags) == 11, (vnum, flags)
        weapon = int(payload[1].split()[0])
        loads.append(f"add_prototype({vnum}, {flags[0]}, {flags[6]}UL, {flags[7]}UL, "
                     f"{flags[9]}UL, {flags[10]}UL, {weapon});")
    equipment = (ROOT / "src/cmd/actobj.c").read_text()
    positions = re.search(r"int equipment_pos_table\[.*?\n\};", equipment, re.S).group(0)
    functions = [extract_function(file, signature) for file, signature in [
        ("handler.c", "static bool obj_race_bit_set"),
        ("handler.c", "int can_char_use_item(P_char ch, P_obj obj)"),
        ("actinf.c", "bool has_eq_slot(P_char ch, int wear_slot)"),
        ("fight.c", "int required_weapon_skill(P_obj wpn)"),
        ("nanny.c", "static newbie_item_facts capture_newbie_item_facts("),
        ("nanny.c", "static std::vector<prepared_newbie_item> prepare_legacy_newbie_plan("),
    ]]
    harness = "\n".join([PRELUDE.replace("START_GRANT", start_grant), *arrays,
                         class_bits, positions, *functions,
                         DRIVER.replace("LOAD_PROTOTYPES", "\n".join(loads))])
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="starter-suitability-", dir=build_root) as tmp:
        source, binary = Path(tmp) / "suitability.cpp", Path(tmp) / "suitability"
        source.write_text(harness)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                        "-fno-omit-frame-pointer", "-no-pie", "-Isrc", str(source),
                        "src/account/newbie_kit_plan.c", str(HARNESS_STUBS),
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
