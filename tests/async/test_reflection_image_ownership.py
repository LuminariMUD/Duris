#!/usr/bin/env python3
"""Exercise Reflection ownership and Shambler admission with real spell bodies.

This checks repeated image ownership transitions, not a booted game or scheduler.
"""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function


prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "classes/necromancy.h"
#include "combat/training_dummy.h"
#include "economy/collector_presence.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/achievements.h"

#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <set>
#include <map>
#include <string>
#include <vector>

room_data rooms[1]{};
P_room world = rooms;
index_data indexes[4]{};
P_index mob_index = indexes;
const race_names race_names_table[LAST_RACE + 2] = {
    {"None", "None", "None", "NO"},
};

static char prototype_keys[] = "reflection image";
static char prototype_long[] = "A reflection image stands here.\r\n";
static char prototype_short[] = "a reflection image";
static std::set<const char *> owned_strings;
static std::vector<P_char> images;
static int random_call;
static int extracted_images;
static bool high_dice;
static std::string output;
static std::map<P_char, int> death_events;
static std::set<P_char> conjured;

void send_to_char(const char *text, P_char) { output += text; }
int dice(int count, int sides) { return count * (high_dice ? sides : 1); }
void event_pet_death(P_char, P_char, P_obj, void *) { abort(); }
nevent_schedule_result add_event(event_func callback, int delay, P_char mob,
                                P_char victim, P_obj obj, int, const void *data, int) {
    assert(callback == event_pet_death && !victim && !obj && !data);
    assert(death_events.emplace(mob, delay).second);
    return {nevent_schedule_status::scheduled, {}};
}
affected_type *apply_achievement(P_char mob, int tag) {
    assert(tag == TAG_CONJURED_PET && conjured.insert(mob).second);
    return nullptr;
}

int BOUNDED(int low, int value, int high) { return std::max(low, std::min(value, high)); }
int number(int low, int high) {
    assert(low <= high);
    return low + random_call++ % (high - low + 1);
}
bool collector_presence_is_npc(P_char) { return false; }
bool training_dummy_capture_target_allowed(P_char) { return true; }
bool has_innate(P_char, int) { return false; }
P_obj get_globe(P_char) { return nullptr; }
void linked_affect_to_char(P_char mob, affected_type *af, P_char ch, int type) {
    assert(type == LNK_PET && !mob->linking);
    auto *copy = new affected_type(*af);
    copy->next = mob->affected;
    mob->affected = copy;
    auto *link = new char_link_data{};
    link->type = type;
    link->linking = mob;
    link->linked = ch;
    link->affect = copy;
    link->next_linked = ch->linked;
    ch->linked = mob->linking = link;
}
void remove_plushit_bits(P_char) {}
void clearMemory(P_char) {}
void remember(P_char, P_char) {}
void balance_affects(P_char) {}
void affect_remove(P_char ch, affected_type *af) {
    assert(ch->affected == af);
    ch->affected = af->next;
    delete af;
}
void stop_fighting(P_char ch) { ch->specials.fighting = nullptr; }
void StopAllAttackers(P_char ch) {
    for (P_char other = world[0].people; other; other = other->next_in_room)
        if (GET_OPPONENT(other) == ch)
            stop_fighting(other);
}
void set_fighting(P_char ch, P_char victim) { ch->specials.fighting = victim; }
void char_from_room(P_char ch) {
    assert(ch->in_room == 0);
    P_char *entry = &world[0].people;
    while (*entry && *entry != ch)
        entry = &(*entry)->next_in_room;
    assert(*entry == ch);
    *entry = ch->next_in_room;
    ch->next_in_room = nullptr;
    ch->in_room = NOWHERE;
}
bool char_to_room(P_char ch, int room, int) {
    assert(room == 0 && ch->in_room == NOWHERE);
    ch->in_room = room;
    ch->next_in_room = world[room].people;
    world[room].people = ch;
    return true;
}
void add_follower(P_char mob, P_char ch) {
    auto *follow = new follow_type{};
    follow->follower = mob;
    follow->next = ch->followers;
    ch->followers = follow;
    mob->following = ch;
}
int real_mobile(int vnum) {
    for (int i = 0; i < 4; ++i)
        if (indexes[i].virtual_number == vnum)
            return i;
    return -1;
}
P_char read_mobile(int nr, int type) {
    if (type == VIRTUAL)
        nr = real_mobile(nr);
    assert(nr >= 0 && nr < 4);
    auto *mob = new char_data{};
    mob->only.npc = new npc_only_data{};
    mob->only.npc->R_num = nr;
    mob->specials.act = ACT_ISNPC;
    mob->in_room = NOWHERE;
    SET_POS(mob, STAT_NORMAL + POS_STANDING);
    mob->player.name = indexes[nr].keys;
    mob->player.long_descr = indexes[nr].desc1;
    mob->player.short_descr = indexes[nr].desc2;
    if (nr == 0)
        images.push_back(mob);
    return mob;
}
char *str_dup(const char *text) {
    char *copy = strdup(text);
    assert(copy && owned_strings.insert(copy).second);
    return copy;
}
void str_free(const char *text) {
    assert(text && owned_strings.erase(text) == 1);
    free(const_cast<char *>(text));
}
void extract_char(P_char mob) {
    assert(IS_NPC(mob) && mob->following && mob->linking);
    P_char owner = mob->following;
    follow_type **follow = &owner->followers;
    while (*follow && (*follow)->follower != mob)
        follow = &(*follow)->next;
    assert(*follow);
    auto *old_follow = *follow;
    *follow = old_follow->next;
    delete old_follow;
    char_link_data **link = &owner->linked;
    while (*link && (*link)->linking != mob)
        link = &(*link)->next_linked;
    assert(*link == mob->linking);
    auto *old_link = *link;
    *link = old_link->next_linked;
    delete old_link;
    char_from_room(mob);
    if (IS_SET(mob->only.npc->str_mask, STRUNG_KEYS))
        str_free(mob->player.name);
    if (IS_SET(mob->only.npc->str_mask, STRUNG_DESC1))
        str_free(mob->player.long_descr);
    if (IS_SET(mob->only.npc->str_mask, STRUNG_DESC2))
        str_free(mob->player.short_descr);
    if (GET_TITLE(mob))
        str_free(GET_TITLE(mob));
    while (mob->affected)
        affect_remove(mob, mob->affected);
    if (GET_VNUM(mob) == 250) {
        auto entry = std::find(images.begin(), images.end(), mob);
        assert(entry != images.end());
        images.erase(entry);
        ++extracted_images;
    }
    death_events.erase(mob);
    conjured.erase(mob);
    delete mob->only.npc;
    delete mob;
}
'''

production = "\n".join([
    extract_function("affects.c", "P_char get_linked_char("),
    extract_function("necromancy.c", "int setup_pet("),
    extract_function("necromancy.c", "int count_pets("),
    extract_function("sillusionist.c", "void spell_reflection("),
    extract_function("blispells.c", "void spell_shambler("),
])

driver = r'''
static void assert_prototype_unchanged() {
    assert(indexes[0].keys == prototype_keys);
    assert(indexes[0].desc1 == prototype_long);
    assert(indexes[0].desc2 == prototype_short);
    assert(!strcmp(indexes[0].keys, "reflection image"));
    assert(!strcmp(indexes[0].desc1, "A reflection image stands here.\r\n"));
    assert(!strcmp(indexes[0].desc2, "a reflection image"));
}

static void assert_images(P_char caster, P_char victim, int expected) {
    assert(images.size() == static_cast<size_t>(expected));
    assert_prototype_unchanged();
    std::string expected_name = "image " + std::string(victim->player.name) + " None";
    std::string expected_long = std::string(victim->player.name) + " stands here.\r\n";

    for (P_char image : images) {
        assert(image->only.npc->str_mask ==
               (STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2));
        assert(image->player.name != indexes[0].keys);
        assert(image->player.long_descr != indexes[0].desc1);
        assert(image->player.short_descr != indexes[0].desc2);
        assert(!strcmp(image->player.name, expected_name.c_str()));
        assert(!strcmp(image->player.long_descr, expected_long.c_str()));
        assert(!strcmp(image->player.short_descr, victim->player.name));
        if (GET_TITLE(victim)) {
            assert(GET_TITLE(image) != GET_TITLE(victim));
            assert(!strcmp(GET_TITLE(image), GET_TITLE(victim)));
        } else {
            assert(!GET_TITLE(image));
        }
        assert(image->following == caster && get_linked_char(image, LNK_PET) == caster);
        assert(image->affected && image->affected->type == SPELL_CHARM_PERSON);
        assert(image->affected->duration == (IS_PC(caster) ? 3 : -1));
        assert(GET_C_CHA(image) == 1);
    }
}

static void cleanup_followers(P_char caster) {
    while (caster->followers) {
        P_char follower = caster->followers->follower;
        stop_fighting(follower);
        StopAllAttackers(follower);
        extract_char(follower);
    }
    assert(!caster->linked);
}

static void scenario(int level, int expected, int pets, bool combat,
                     bool npc = false, bool other_target = false) {
    char_data caster{}, target{}, attacker{};
    pc_only_data player{};
    npc_only_data caster_npc{};
    if (npc) {
        caster.specials.act = ACT_ISNPC;
        caster.only.npc = &caster_npc;
    } else {
        caster.only.pc = &player;
    }
    caster.player.name = const_cast<char *>("Mirror");
    caster.player.level = level;
    caster.in_room = target.in_room = attacker.in_room = NOWHERE;
    SET_POS(&caster, STAT_NORMAL + POS_STANDING);
    char_to_room(&caster, 0, 0);
    P_char victim = other_target ? &target : &caster;
    if (other_target) {
        target.player.name = const_cast<char *>("Target");
        target.player.level = level;
        SET_POS(&target, STAT_NORMAL + POS_STANDING);
        char_to_room(&target, 0, 0);
    }
    victim->player.title = combat ? const_cast<char *>("the Magnificent") : nullptr;
    if (combat) {
        attacker.player.name = const_cast<char *>("Enemy");
        SET_POS(&attacker, STAT_NORMAL + POS_STANDING);
        char_to_room(&attacker, 0, 0);
    }
    random_call = extracted_images = 0;
    std::vector<P_char> existing_pets;
    std::vector<const char *> pet_names;
    for (int i = 0; i < pets; ++i) {
        P_char pet = read_mobile(1, REAL);
        char_to_room(pet, 0, 0);
        setup_pet(pet, &caster, 10, PET_NOCASH);
        add_follower(pet, &caster);
        existing_pets.push_back(pet);
        pet_names.push_back(pet->player.name);
    }
    if (other_target) {
        // Casting on another player must replace their existing images too.
        spell_reflection(level, victim, nullptr, 0, victim, nullptr);
        assert_images(victim, victim, expected);
    }
    for (int round = 0; round < 8; ++round) {
        if (combat) {
            set_fighting(&attacker, victim);
            set_fighting(victim, &attacker);
        }
        spell_reflection(level, &caster, nullptr, 0, victim, nullptr);
        assert_images(&caster, victim, expected);
        assert(extracted_images == (round + (other_target ? 1 : 0)) * expected);
        int followers = 0, links = 0;
        for (auto *follow = caster.followers; follow; follow = follow->next)
            ++followers;
        for (auto *link = caster.linked; link; link = link->next_linked)
            ++links;
        assert(followers == expected + pets && links == expected + pets);
        for (int i = 0; i < pets; ++i) {
            P_char pet = existing_pets[i];
            assert(GET_VNUM(pet) == 3 && pet->following == &caster);
            assert(get_linked_char(pet, LNK_PET) == &caster);
            assert(pet->player.name == pet_names[i]);
            assert(pet->affected && pet->affected->duration == 10);
        }
        if (combat) {
            P_char redirected = attacker.specials.fighting;
            assert(std::find(images.begin(), images.end(), redirected) != images.end());
            assert(GET_OPPONENT(redirected) == &attacker && !IS_FIGHTING(victim));
        }
        if (other_target)
            assert(!victim->followers && !victim->linked);
    }
    cleanup_followers(&caster);
    assert(images.empty());
    if (combat)
        char_from_room(&attacker);
    if (other_target)
        char_from_room(&target);
    char_from_room(&caster);
    assert(!world[0].people);
    assert(owned_strings.empty());
    assert_prototype_unchanged();
}

static void titan_rejection() {
    char_data caster{};
    caster.player.name = const_cast<char *>("Mirror");
    caster.in_room = NOWHERE;
    SET_POS(&caster, STAT_NORMAL + POS_STANDING);
    char_to_room(&caster, 0, 0);
    P_char titan = read_mobile(2, REAL);
    char_to_room(titan, 0, 0);
    setup_pet(titan, &caster, 10, PET_NOCASH);
    add_follower(titan, &caster);
    spell_reflection(46, &caster, nullptr, 0, &caster, nullptr);
    assert(images.empty());
    assert(caster.followers->follower == titan && !caster.followers->next);
    assert(get_linked_char(titan, LNK_PET) == &caster);
    cleanup_followers(&caster);
    char_from_room(&caster);
    assert(!world[0].people && owned_strings.empty());
    assert_prototype_unchanged();
}

static void shambler_admission(int image_count, int pets, bool summoned,
                              int sector, int expected_mounds, bool existing_mound) {
    char_data caster{}, nonpet{};
    pc_only_data pc{};
    caster.only.pc = &pc;
    caster.player.name = const_cast<char *>("Mirror");
    caster.in_room = NOWHERE;
    SET_POS(&caster, STAT_NORMAL + POS_STANDING);
    char_to_room(&caster, 0, 0);
    world[0].sector_type = sector;
    random_call = 0;
    std::vector<P_char> ordinary;
    std::vector<const char *> names;
    for (int i = 0; i < pets; ++i) {
        P_char pet = read_mobile(1, REAL);
        char_to_room(pet, 0, 0);
        setup_pet(pet, &caster, 10, PET_NOCASH);
        add_follower(pet, &caster);
        pet->only.npc->summoned_instance = summoned;
        if (summoned)
            apply_achievement(pet, TAG_CONJURED_PET);
        ordinary.push_back(pet);
        names.push_back(pet->player.name);
    }
    if (existing_mound) {
        P_char mound = read_mobile(100, VIRTUAL);
        char_to_room(mound, 0, 0);
        setup_pet(mound, &caster, 15, PET_NOCASH | PET_NOAGGRO);
        add_follower(mound, &caster);
    }
    if (image_count) {
        spell_reflection(26 + image_count * 5, &caster, nullptr, 0, &caster, nullptr);
        assert_images(&caster, &caster, image_count);
    }
    // Unrelated links must not be interpreted as pets or dereferenced as NPCs.
    char_link_data other{};
    other.type = LNK_RIDING;
    other.linking = &nonpet;
    other.next_linked = caster.linked;
    caster.linked = &other;
    const auto original_images = images;
    std::vector<const char *> image_names;
    for (P_char image : images)
        image_names.push_back(image->player.name);
    assert(count_pets(&caster) == pets + image_count + existing_mound);

    output.clear();
    spell_shambler(50, &caster, nullptr, 0, &caster, nullptr);
    const bool admitted = pets <= 1 && !existing_mound && expected_mounds > 0;
    int created = 0;
    std::vector<P_char> new_mounds;
    for (auto *follow = caster.followers; follow; follow = follow->next) {
        P_char mob = follow->follower;
        if (GET_VNUM(mob) != 100 || existing_mound)
            continue;
        ++created;
        new_mounds.push_back(mob);
        assert(mob->following == &caster && get_linked_char(mob, LNK_PET) == &caster);
        assert(mob->affected && mob->affected->duration == 15);
        assert(conjured.count(mob) == 1);
        assert(death_events.at(mob) == (high_dice ? 12 : 2) * 60 * WAIT_SEC);
    }
    assert(created == (admitted ? expected_mounds : 0));
    if (existing_mound)
        assert(output == "You already have a mound.\n");
    else if (pets > 1)
        assert(output == "You already have enough pets.");
    else if (!expected_mounds)
        assert(output.find("vegetation") != std::string::npos);
    else
        assert(output.empty());
    assert(images == original_images);
    for (size_t i = 0; i < images.size(); ++i)
        assert(images[i]->player.name == image_names[i]);
    assert_images(&caster, &caster, image_count);
    assert(count_pets(&caster) == pets + image_count + existing_mound + created);
    if (admitted) {
        output.clear();
        spell_shambler(50, &caster, nullptr, 0, &caster, nullptr);
        assert(output == "You already have a mound.\n");
        assert(count_pets(&caster) == pets + image_count + created);
    }
    for (int i = 0; i < pets; ++i) {
        assert(ordinary[i]->player.name == names[i]);
        assert(ordinary[i]->following == &caster);
        assert(get_linked_char(ordinary[i], LNK_PET) == &caster);
        assert(ordinary[i]->affected->duration == 10);
    }
    if (image_count) {
        for (P_char mound : new_mounds)
            extract_char(mound);
        while (!images.empty())
            extract_char(images.back());
        assert(count_pets(&caster) == pets + existing_mound);
        output.clear();
        spell_shambler(50, &caster, nullptr, 0, &caster, nullptr);
        assert(count_pets(&caster) == pets + existing_mound +
               (admitted ? expected_mounds : 0));
        for (int i = 0; i < pets; ++i) {
            assert(ordinary[i]->player.name == names[i]);
            assert(get_linked_char(ordinary[i], LNK_PET) == &caster);
        }
    }
    // Remove the stack-owned non-pet link before normal fixture teardown.
    auto **link = &caster.linked;
    while (*link != &other)
        link = &(*link)->next_linked;
    *link = other.next_linked;
    cleanup_followers(&caster);
    char_from_room(&caster);
    assert(images.empty() && owned_strings.empty() && death_events.empty() && conjured.empty());
    assert(!world[0].people);
    assert_prototype_unchanged();
}

int main() {
    indexes[0].virtual_number = 250;
    indexes[1].virtual_number = 3;
    indexes[2].virtual_number = TITAN_NUMBER;
    indexes[3].virtual_number = 100;
    for (auto &index : indexes) {
        index.keys = prototype_keys;
        index.desc1 = prototype_long;
        index.desc2 = prototype_short;
    }
    const int levels[] = {31, 35, 36, 40, 41, 45, 46, 56};
    const int counts[] = {1, 1, 2, 2, 3, 3, 4, 4};
    for (int i = 0; i < 8; ++i)
        for (int pets : {0, 1, 4})
            for (bool combat : {false, true})
                scenario(levels[i], counts[i], pets, combat);
    scenario(46, 4, 0, false, true);
    scenario(46, 4, 0, true, true);
    scenario(46, 4, 1, true, false, true);
    titan_rejection();
    puts("Reflection: 409 casts and titan rejection preserved prototypes, pets, links, "
         "combat redirection and private-string cleanup.");
    int cases = 0;
    for (bool summoned : {false, true})
        for (bool high : {false, true}) {
            high_dice = high;
            const int sectors[] = {SECT_CITY, SECT_FIELD, SECT_FOREST, SECT_INSIDE};
            const int counts[] = {high ? 2 : 1, high ? 4 : 2, high ? 6 : 3, 0};
            for (int image_count = 0; image_count <= 4; ++image_count)
                for (int pets = 0; pets <= 3; ++pets)
                    for (int sector = 0; sector < 4; ++sector)
                        for (bool mound : {false, true}) {
                            shambler_admission(image_count, pets, summoned,
                                               sectors[sector], counts[sector], mound);
                            ++cases;
                        }
        }
    printf("Shambler: %d image/pet/terrain/mound cases preserved admission, "
           "ownership, yields, tagging and lifetime scheduling.\n", cases);
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="reflection-ownership-", dir=build) as directory:
    cpp = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    cpp.write_text(prelude + production + driver)
    subprocess.run([
        *shlex.split(os.environ.get("CXX", "g++")), "-std=c++20", "-g",
        "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-lbsd", "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True, timeout=30, env={
        **os.environ,
        "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
        "UBSAN_OPTIONS": "halt_on_error=1",
    })
