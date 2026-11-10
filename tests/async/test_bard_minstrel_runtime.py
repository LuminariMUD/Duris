#!/usr/bin/env python3
"""Run Minstrel songs, real healing/Salvation and defense hooks using server objects."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT

fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "combat/damage.h"
#include "abilities/abilities.h"
#include <cassert>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>
extern P_room world;
extern P_index mob_index;
extern void initialize_skills();
extern int dodgeSucceed(P_char, P_char, P_obj);
extern void bard_healing(int, P_char, P_char, int);
extern void bard_charm(int, P_char, P_char, int);
extern void bard_drifting(int, P_char, P_char, int);
extern void bard_nimbleness(int, P_char, P_char, int);
static std::vector<std::unique_ptr<affected_type>> stored;
static int roll = 1, save_mod, save_calls, pet_duration, pets, teleports, spell_rolls;
static std::string captured;
// Boundaries deliberately outside the feature: output, pet ownership and affect allocation.
void send_to_char(const char *text, P_char) { captured += text; }
void act(const char *text, int, P_char, P_obj, void *, int) { captured += text; }
int attack_back(P_char, P_char, int) { return 0; }
int number(int low, int high) {
    if (low == 1 && high == 1000) ++spell_rolls;
    return MAX(low, MIN(high, roll));
}
bool NewSaves(P_char, int, int mod) { ++save_calls; save_mod = mod; return false; }
void add_follower(P_char target, P_char leader) { target->following = leader; }
int setup_pet(P_char, P_char, int duration, int) { ++pets; pet_duration = duration; return 0; }
void spell_group_teleport(int, P_char, char *, int, P_char, P_obj) { ++teleports; }
affected_type *affect_to_char(P_char ch, affected_type *af) {
    stored.emplace_back(new affected_type(*af));
    auto *copy = stored.back().get(); copy->next = ch->affected; ch->affected = copy;
    return copy;
}
void linked_affect_to_char(P_char ch, affected_type *af, P_char, int) {
    af->flags |= AFFTYPE_LINKED_CH | AFFTYPE_NOSAVE; affect_to_char(ch, af);
}
static char_data player(pc_only_data &pc) {
    char_data ch{}; ch.only.pc = &pc; ch.in_room = 1;
    ch.player.level = 56; ch.player.m_class = CLASS_BARD; ch.player.spec = SPEC_MINSTREL;
    ch.player.race = RACE_HUMAN; ch.player.name = const_cast<char *>("Fixture");
    ch.specials.position = POS_STANDING | STAT_NORMAL;
    ch.curr_stats.Cha = 150; ch.curr_stats.Int = ch.curr_stats.Wis = 100;
    ch.curr_stats.Agi = ch.curr_stats.Dex = 100;
    ch.points.hit = 100; ch.points.max_hit = 10000;
    pc.skills[SONG_HEALING].learned = pc.skills[SONG_CHARMING].learned = 100;
    pc.skills[SONG_DRIFTING].learned = 100;
    return ch;
}
static void clear_song(P_char ch) { ch->affected = nullptr; stored.clear(); }
int main() {
    initialize_skills();
    world = new room_data[2]{}; world[1].sector_type = SECT_FIELD;
    mob_index = new index_data[1]{};
    pc_only_data bard_pc{}, ally_pc{};
    char_data bard = player(bard_pc), ally = player(ally_pc);
    ally.player.m_class = CLASS_WARRIOR; ally.player.spec = 0;
    affected_type level_achievement{}; level_achievement.type = AIP_LEVELACHIEVEMENT; level_achievement.modifier = MAXLVL;
    affected_type salvation{}; salvation.type = AIP_MAYIHEALSYOU; salvation.next = &level_achievement; bard.affected = &salvation;
    bard_healing(56, &bard, &bard, SONG_HEALING);
    assert(bard.points.hit == 145 && salvation.modifier == 0);
    bard.affected = &salvation; stored.clear();
    bard_healing(56, &bard, &ally, SONG_HEALING);
    assert(ally.points.hit == 133 && salvation.modifier == 33);
    clear_song(&ally);
    ally.points.hit = 10000;
    bard_healing(56, &bard, &ally, SONG_HEALING);
    assert(salvation.modifier == 33); // Overhealing gives no credit.
    clear_song(&ally);
    npc_only_data mob_data{};
    char_data mob = ally; mob.specials.act = ACT_ISNPC; mob.only.npc = &mob_data;
    mob.player.level = 50; mob.player.race = RACE_HUMAN; mob.curr_stats.Int = 100;
    mob.points.hit = 100;
    bard_healing(56, &bard, &mob, SONG_HEALING);
    assert(mob.points.hit == 133 && salvation.modifier == 33);
    clear_song(&mob);
    // Raising any of the three Minstrel inputs helps; the cap applies after sharing.
    bard.affected = nullptr;
    for (int spec : {0, SPEC_MINSTREL, SPEC_SCOUNDREL})
      for (int level : {31,36,56}) for (int rating : {50,60,100}) for (int cha : {72,100,150,300}) {
        bard.player.spec = spec; bard.player.level = level; bard.curr_stats.Cha = cha;
        bard_pc.skills[SONG_HEALING].learned = rating;
        int base = cha/8 + level/4 + level/14;
        int bonus = (level-31)/5 + MAX(0,(rating-50)/10) + MAX(0,(cha-100)/10);
        for (bool self : {false,true}) {
            P_char target = self ? &bard : &ally;
            target->affected = nullptr; bard.affected = &level_achievement; target->points.hit = 100;
            int expected = base + (spec == SPEC_MINSTREL ? bonus : 0);
            if (!self) expected = expected*13/20;
            if (spec == SPEC_MINSTREL) expected = MIN(45,expected);
            bard_healing(level, &bard, target, SONG_HEALING);
            assert(target->points.hit == 100 + expected);
            clear_song(target);
        }
    }
    char_data mob_bard = player(bard_pc); mob_bard.specials.act = ACT_ISNPC; mob_bard.only.npc = &mob_data;
    mob_bard.affected = nullptr; mob_bard.points.hit = 100;
    bard_healing(56, &mob_bard, &mob_bard, SONG_HEALING);
    assert(mob_bard.points.hit == 136); // NPC Minstrels get the unchanged base amount.
    clear_song(&mob_bard);
    bard = player(bard_pc); mob.affected = nullptr; mob.following = nullptr;
    bard.player.spec = SPEC_SCOUNDREL; save_calls = pets = 0;
    bard_charm(56, &bard, &mob, SONG_CHARMING);
    assert(pets == 1 && pet_duration == 12 && save_calls == 1);
    int ordinary_save = save_mod;
    mob.following = nullptr; bard.player.spec = SPEC_MINSTREL;
    for (int duration : {40,48}) {
        mob.following = nullptr; roll = duration;
        bard_charm(56, &bard, &mob, SONG_CHARMING);
        assert(pet_duration == duration && save_mod == ordinary_save + 10);
    }
    mob.following = nullptr; mob.curr_stats.Int = 14;
    bard_charm(56, &bard, &mob, SONG_CHARMING);
    assert(pet_duration == 1240/14); // Existing long durations survive the floor.
    mob.following = nullptr; mob.player.level = 51; pets = save_calls = 0;
    bard_charm(56, &bard, &mob, SONG_CHARMING);
    assert(!pets && !save_calls); // The owner declined level-51 charm.
    bard = player(bard_pc); roll = 1; teleports = 0;
    bard_drifting(56, &bard, &bard, SONG_DRIFTING); assert(teleports == 1);
    bard.specials.act = ACT_ISNPC; bard.only.npc = &mob_data;
    bard_drifting(56, &bard, &bard, SONG_DRIFTING); assert(teleports == 1);
    bard = player(bard_pc); ally = player(ally_pc); ally.player.m_class = CLASS_WARRIOR; ally.player.spec = 0;
    bard_nimbleness(56, &bard, &ally, SONG_NIMBLENESS);
    assert(affected_by_spell(&ally, SONG_NIMBLENESS));
    char_data attacker = player(bard_pc); attacker.player.m_class = CLASS_WARRIOR; attacker.player.spec = 0;
    int normal = 0, nimble = 0;
    for (roll = 1; roll <= 101; ++roll) {
        auto *af = ally.affected; ally.affected = nullptr;
        normal += dodgeSucceed(&ally, &attacker, nullptr);
        ally.affected = af;
        nimble += dodgeSucceed(&ally, &attacker, nullptr);
    }
    assert(nimble - normal == 5);
    ally.specials.affected_by2 = AFF2_GLOBE;
    int avoided = 0; spell_rolls = 0;
    for (roll = 1; roll <= 1000; ++roll) {
        captured.clear();
        spell_damage(&attacker, &ally, 100, SPLDAM_GENERIC, SPLDAM_GLOBE, nullptr);
        avoided += captured.find("Minstrel's tune") != std::string::npos;
    }
    assert(avoided == 35 && spell_rolls == 1000);
    spell_rolls = 0;
    spell_damage(&attacker, &ally, 0, SPLDAM_GENERIC, SPLDAM_GLOBE, nullptr);
    assert(spell_rolls == 0);
    clear_song(&ally); spell_rolls = 0;
    spell_damage(&attacker, &ally, 100, SPLDAM_GENERIC, SPLDAM_GLOBE, nullptr);
    assert(!spell_rolls); // No extra roll without the song.
    stored.clear(); delete[] world; delete[] mob_index;
    std::puts("PASS Minstrel healing/cap/Salvation, charm saves/duration/level limit, pet Drifting, +5 melee and 35/1000 spell avoidance through real server paths");
}
'''
subprocess.run(["make", "-C", "src", "-j8"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
link = subprocess.check_output(["make", "-s", "--no-print-directory", "-C", "src",
    "--eval=print-link:;@echo $(DMS_OBJS) $(LIBS)", "print-link"], cwd=ROOT, text=True).split()
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="bard-minstrel-", dir=build) as temporary:
    cpp, binary = Path(temporary) / "test.cpp", Path(temporary) / "test"
    cpp.write_text(fixture)
    subprocess.run(["g++", "-std=c++20", "-g", "-Isrc", "-I/usr/include/libxml2", "-I/usr/include/mysql",
                    str(cpp), "-o", str(binary), "-rdynamic", "-Wl,--allow-multiple-definition", *link],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
