#!/usr/bin/env python3
"""Execute instrument selection and Rope Trick against equipment/room fixtures."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#define INSTRUMENT_OFFSET (FIRST_INSTRUMENT - 184)
#include <cassert>
#include <cstdio>
#include <cstring>
struct song_description { const char *name; int instrument, song; };
static song_description songs[] = {
    {"sleep", INSTRUMENT_FLUTE, SONG_SLEEP},
    {"heroism", INSTRUMENT_DRUMS, SONG_HEROISM}, {}
};
room_data rooms[2]{}; P_room world = rooms;
static bool visible = true, blind_singing = false, saved = false, resist = false;
static bool consent = false, in_group = false;
static int rating = 70, saves = 0, resists = 0, applied = 0;
void logit(const char *, const char *, ...) {}
bool ac_can_see_obj(P_char, P_obj, int) { return visible; }
bool has_innate(P_char, int) { return blind_singing; }
int GET_CHAR_SKILL_P(P_char, int) { return rating; }
bool grouped(P_char, P_char) { return in_group; }
bool is_linked_to(P_char, P_char, ush_int) { return consent; }
bool resists_spell(P_char, P_char) { ++resists; return resist; }
bool NewSaves(P_char, int, int) { ++saves; return saved; }
int get_default_save_mod(P_char, P_char, int, int) { return 0; }
bool affected_by_spell(P_char ch, int type) {
    return ch->affected && ch->affected->type == type;
}
affected_type *affect_to_char(P_char, affected_type *af) {
    ++applied; assert(af->type == SPELL_ROPE_TRICK && af->duration == 5); return nullptr;
}
void send_to_char(const char *, P_char) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
'''
functions = [("bard.c", sig) for sig in (
    "static int bard_blind_play_rating(", "int bard_get_type(", "P_obj has_instrument(",
)] + [("magic.c", sig) for sig in (
    "static int rope_trick_duration(", "static int rope_trick_limit(", "void spell_rope_trick(",
)]
driver = r'''
int main() {
    char_data bard{}; bard.player.level = 56; bard.specials.position = POS_STANDING | STAT_NORMAL;
    obj_data flute{}, drums{}, other{};
    flute.type = drums.type = ITEM_INSTRUMENT;
    flute.value[0] = INSTRUMENT_FLUTE - INSTRUMENT_OFFSET;
    drums.value[0] = INSTRUMENT_DRUMS - INSTRUMENT_OFFSET;
    bard.equipment[HOLD] = &flute;
    for (int slot : {WEAR_ATTACH_BELT_1, WEAR_ATTACH_BELT_2, WEAR_ATTACH_BELT_3}) {
        bard.equipment[slot] = &drums;
        assert(has_instrument(&bard, SONG_HEROISM) == &drums);
        assert(has_instrument(&bard, SONG_SLEEP) == &flute);
        bard.equipment[slot] = nullptr;
    }
    // Every equipment slot, even below WIELD, participates.
    for (int slot = 0; slot < MAX_WEAR; ++slot) {
        bard.equipment[slot] = &drums;
        assert(has_instrument(&bard, SONG_HEROISM) == &drums);
        bard.equipment[slot] = slot == HOLD ? &flute : nullptr;
    }
    assert(has_instrument(&bard, SONG_HEROISM) == &flute); // wrong-instrument feedback
    flute.extra_flags = ITEM_ARTIFACT;
    assert(has_instrument(&bard, SONG_HEROISM) == &flute);
    visible = false;
    assert(has_instrument(&bard, SONG_HEROISM) == &flute); // unseen artifact
    flute.extra_flags = 0;
    assert(!has_instrument(&bard, SONG_SLEEP));
    blind_singing = true; assert(has_instrument(&bard, SONG_SLEEP) == &flute);
    rating = 69; assert(!has_instrument(&bard, SONG_SLEEP));
    bard.equipment[HOLD] = &other; visible = true;
    assert(!has_instrument(&bard, SONG_HEROISM));
    bard.equipment[HOLD] = nullptr; assert(!has_instrument(&bard, SONG_SLEEP));

    char_data people[6]{}; affected_type ropes[6]{};
    bard.in_room = 1; world[1].sector_type = SECT_FIELD;
    world[1].people = &people[0];
    for (int i = 0; i < 6; ++i) {
        people[i].specials.position = POS_STANDING | STAT_NORMAL;
        people[i].in_room = 1; people[i].affected = &ropes[i];
        ropes[i].type = SPELL_ROPE_TRICK;
        if (i < 5) people[i].next_in_room = &people[i+1];
    }
    // Four hidden: grouped fifth bypasses both resistance and a certain save.
    for (int i = 0; i < 4; ++i) people[i].specials.affected_by = AFF_HIDE;
    in_group = saved = resist = true;
    spell_rope_trick(56, &bard, nullptr, 0, &people[4], nullptr);
    assert(applied == 1 && !saves && !resists && IS_AFFECTED(&people[4], AFF_HIDE));
    spell_rope_trick(56, &bard, nullptr, 0, &people[5], nullptr);
    assert(applied == 1 && !IS_AFFECTED(&people[5], AFF_HIDE)); // sixth refused
    // Revealing one frees a slot; consent and self still bypass saves.
    people[0].specials.affected_by = 0; in_group = false; consent = true;
    spell_rope_trick(56, &bard, nullptr, 0, &people[5], nullptr);
    assert(applied == 2 && !saves && !resists);
    people[1].specials.affected_by = 0; consent = false;
    spell_rope_trick(56, &bard, nullptr, 0, &bard, nullptr);
    assert(applied == 3 && !saves && !resists);
    bard.specials.affected_by = 0; people[5].specials.affected_by = 0;
    spell_rope_trick(56, &bard, nullptr, 0, &people[5], nullptr);
    assert(applied == 3 && resists == 1); // ungrouped hostile resistance
    resist = false;
    spell_rope_trick(56, &bard, nullptr, 0, &people[5], nullptr);
    assert(applied == 3 && saves == 1); // save still protects outsiders
    saved = false;
    spell_rope_trick(56, &bard, nullptr, 0, &people[5], nullptr);
    assert(applied == 4 && saves == 2);
    std::puts("PASS instrument choice/all slots/artifact/darkness/fallback; Rope Trick fifth/sixth/group/consent/resist/save");
}
'''
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="bard-utility-", dir=build) as directory:
    cpp, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    cpp.write_text(prelude + "\n".join(extract_function(f, s) for f, s in functions) + driver)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-Isrc",
                    str(cpp), str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
