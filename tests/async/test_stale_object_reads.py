#!/usr/bin/env python3
"""Refine, object affects and scribing do not read released objects.

Object memory goes back to a pool at once, so these reads used to "work" until
the slot was reused:
- do_refine() read the vnum of a material or ore it had just extracted, and
  its failure message showed the extracted material.
- event_obj_affect() read the affect type after obj_affect_remove() released it.
- event_scribe() kept raw scroll and teacher pointers across the page delay;
  a scroll that left the game was read and extracted again, and a teacher who
  left was written to.

Compiles the production functions under ASan/UBSan. Object and character
storage is freed when the fixture extracts it, so a stale read fails at once.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function, source


def includes(name):
    return "\n".join(line for line in source(name).read_text().splitlines()
                     if line.startswith("#include"))


REFINE = r'''
// INCLUDES
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>

// Materials 400001/400002, the worst ore (194) and the best ore (233).
static index_data index_fixture[4]{};
P_index obj_index = index_fixture;
static std::vector<P_obj> granted;
static int roll, coins;

static P_obj make_obj(int rnum)
{
	P_obj obj = new obj_data{};
	obj->R_num = rnum;
	obj->name = const_cast<char *>(rnum < 2 ? "iron" : "ore");
	obj->short_description = obj->name;
	return obj;
}
static int rnum_of(int vnum)
{
	for (int rnum = 0; rnum < 4; rnum++)
		if (index_fixture[rnum].virtual_number == vnum)
			return rnum;
	__builtin_trap();
}

P_obj read_object(int nr, int type)
{
	assert(type == VIRTUAL);
	return make_obj(rnum_of(nr));
}
void extract_obj(P_obj obj, int) { delete obj; }
void obj_from_char(P_obj obj)
{
	P_char ch = obj->loc.carrying;
	P_obj *link = &ch->carrying;
	while (*link != obj)
		link = &(*link)->next_content;
	*link = obj->next_content;
	obj->next_content = nullptr;
}
P_obj get_obj_in_list(char *name, P_obj list)
{
	for (; list; list = list->next_content)
		if (!std::strcmp(list->name, name))
			return list;
	return nullptr;
}
void argument_interpreter(char *arg, char *first, char *second)
{
	std::strcpy(first, arg);
	*second = '\0';
}
// Messages name the object they show.
void act(const char *, int, P_char, P_obj obj, void *, int)
{
	volatile char c = *obj->short_description;
	(void)c;
}
void send_to_char(const char *, P_char) {}
int get_matstart(P_obj) { return 400000; }
int SUB_MONEY(P_char, int amount, int)
{
	coins += amount;
	return 0;
}
int number(int, int) { return roll; }
bool grant_tradeskill_item(P_char, P_obj obj)
{
	granted.push_back(obj);
	return true;
}
int panic_corruption_int(const char *, const char *, ...) { __builtin_trap(); }

// FUNCTIONS

static void refine(const std::vector<int> &carried)
{
	char_data ch{};
	for (auto rnum = carried.rbegin(); rnum != carried.rend(); ++rnum)
	{
		P_obj obj = make_obj(*rnum);
		obj->loc.carrying = &ch;
		obj->next_content = ch.carrying;
		ch.carrying = obj;
	}
	for (P_obj obj : granted)
		delete obj;
	granted.clear();
	coins = 0;
	char arg[] = "iron";
	do_refine(&ch, arg, 0);
	// Both materials and the one ore are used up.
	assert(!ch.carrying);
}

int main()
{
	index_fixture[0].virtual_number = 400001;
	index_fixture[1].virtual_number = 400002;
	index_fixture[2].virtual_number = 194;
	index_fixture[3].virtual_number = 233;
	roll = 100;

	// The best ore lifts the chance to 100, so the roll cannot fail.
	refine({ 0, 0, 3 });
	assert(granted.size() == 1 && granted[0]->R_num == 1 && !coins);
	refine({ 3, 0, 0 });
	assert(granted.size() == 1 && granted[0]->R_num == 1 && !coins);
	// The worst ore fails the same roll and shows the material that was used.
	refine({ 0, 0, 2 });
	assert(granted.empty() && !coins);
	// So does paying in coins.
	refine({ 0, 0 });
	assert(granted.empty() && coins == 50000);

	for (P_obj obj : granted)
		delete obj;
	std::puts("do_refine reads nothing it extracted");
}
'''

OBJ_AFFECT = r'''
// INCLUDES
#include <cassert>
#include <cstdio>
#include <cstdlib>

mm_ds *dead_obj_affect_pool;
P_index obj_index;
static int decays;

// The pool hands the slot to the next caller; freeing makes a later read fail at once.
void mm_release(mm_ds *, void *slot) { std::free(slot); }
void Decay(P_obj) { decays++; }
int set_obj_condition(P_obj, int condition) { return condition; }
void recalculate_obj_extra(P_obj) {}
obj_affect *get_obj_affect(P_obj, int) { return nullptr; }
// The fixture objects carry no events.
nevent_handle nevent_handle_from_event(P_nevent) { __builtin_trap(); }
nevent_cancel_result nevent_cancel(nevent_handle) { __builtin_trap(); }

// FUNCTIONS

static void expire(int type)
{
	obj_data obj{};
	auto af = static_cast<obj_affect *>(std::calloc(1, sizeof(obj_affect)));
	af->type = type;
	obj.affects = af;
	event_obj_affect(nullptr, nullptr, &obj, &af);
	assert(!obj.affects);
}

int main()
{
	expire(TAG_OBJ_DECAY);
	assert(decays == 1);
	expire(TAG_ALTERED_EXTRA2);
	assert(decays == 1);
	std::puts("event_obj_affect reads no released affect");
}
'''

SCRIBE = r'''
// INCLUDES
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <set>

char Gbuf1[MAX_STRING_LENGTH];
Skill skills[MAX_SKILLS];
static scribing_data_type payload;
static std::set<P_obj> live_objects;
static std::map<uint64_t, P_char> live_characters;
static int extracted, aborted, page_events;
void event_scribe(P_char, P_char, P_obj, void *);

nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *data,
				 int size)
{
	assert(size == sizeof(payload));
	std::memmove(&payload, data, sizeof(payload)); // the next page reuses the payload
	page_events++;
	return {};
}
void AddScribingAffect(P_char ch) { SET_BIT(ch->specials.affected_by2, AFF2_SCRIBING); }
static int scribe_first_page_wait(P_char) { return 1; }
static int scribe_page_wait(P_char) { return 1; }
int GetSpellPages(P_char, int) { return 2; }
int AddSpellToSpellBook(P_char, P_obj, int) { return TRUE; }
void mark_player_dirty_components(int, player_component_mask_t) {}
bool notch_skill(P_char, int, float) { return false; }
void disarm_char_nevents(P_char, event_func_type) { aborted++; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *, P_char ch)
{
	volatile int stat = ch->specials.position;
	(void)stat;
}
P_obj find_live_object(P_obj expected, uint64_t uid)
{
	return live_objects.count(expected) && expected->obj_uid == uid ? expected : nullptr;
}
P_char find_character_by_runtime_id(uint64_t id)
{
	return live_characters.count(id) ? live_characters[id] : nullptr;
}
// Extraction frees the storage, as the pool would hand it out again.
void extract_obj(P_obj obj, int)
{
	live_objects.erase(obj);
	extracted++;
	delete obj;
}
int panic_corruption_int(const char *, const char *, ...) { __builtin_trap(); }

// FUNCTIONS

static char_data scriber{};
static obj_data book{}, pen{};

// Starts copying a spell and writes every page but the last.
static void start(P_obj scroll, P_char teacher)
{
	add_scribe_data(1, &scriber, &book, scroll ? 1 : 0, scroll, teacher);
	event_scribe(&scriber, nullptr, nullptr, &payload);
	assert(page_events == 2 && !aborted);
}
static void last_page() { event_scribe(&scriber, nullptr, nullptr, &payload); }
static P_obj carried_scroll()
{
	P_obj scroll = new obj_data{};
	scroll->type = ITEM_SCROLL;
	scroll->obj_uid = 7;
	scroll->value[1] = 1;
	scroll->loc_p = LOC_CARRIED;
	scroll->loc.carrying = &scriber;
	live_objects.insert(scroll);
	return scroll;
}
static void reset()
{
	extracted = aborted = page_events = 0;
	book.value[3] = 0;
}

int main()
{
	static pc_only_data pc{};
	scriber.only.pc = &pc;
	scriber.specials.position = STAT_RESTING + POS_SITTING;
	book.type = ITEM_SPELLBOOK;
	pen.type = ITEM_PEN;
	scriber.equipment[HOLD] = &book;
	scriber.equipment[WIELD] = &pen;
	skills[1].name = const_cast<char *>("armor");

	// A scroll the scriber still carries is used up on the last page.
	P_obj scroll = carried_scroll();
	start(scroll, nullptr);
	last_page();
	assert(extracted == 1 && !aborted);

	// A scroll that left the game is not read or extracted again.
	reset();
	scroll = carried_scroll();
	start(scroll, nullptr);
	extract_obj(scroll, TRUE);
	last_page();
	assert(extracted == 1 && aborted == 1);

	// A scroll put down mid-scribe stops the copy.
	reset();
	scroll = carried_scroll();
	start(scroll, nullptr);
	scroll->loc_p = LOC_ROOM;
	last_page();
	assert(!extracted && aborted == 1);
	extract_obj(scroll, TRUE);

	// A teacher still in the game is told and freed from teaching.
	reset();
	char_data teacher{};
	teacher.runtime_id = 11;
	live_characters[11] = &teacher;
	start(nullptr, &teacher);
	last_page();
	assert(!aborted && !IS_SET(teacher.specials.affected_by2, AFF2_SCRIBING));

	// A teacher who left the game is not touched.
	reset();
	P_char gone = new char_data{};
	gone->runtime_id = 12;
	live_characters[12] = gone;
	start(nullptr, gone);
	live_characters.erase(12);
	delete gone;
	last_page();
	assert(!aborted);
	std::puts("event_scribe re-finds its scroll and teacher");
}
'''

HARNESSES = {
    "refine": (REFINE, "tradeskill.c", [
        ("tradeskill.c", "void do_refine(P_char ch, char *arg, int /*cmd*/)")]),
    "obj-affect": (OBJ_AFFECT, "affects.c", [
        ("affects.c", "void obj_affect_remove(P_obj obj, struct obj_affect *af)"),
        ("affects.c", "void event_obj_affect(P_char, P_char, P_obj obj, void *data)")]),
    "scribe": (SCRIBE, "memorize.c", [
        ("memorize.c", "static P_obj scribing_implement("),
        ("memorize.c", "void add_scribe_data(int spl,"),
        ("memorize.c", "void event_scribe(P_char ch, P_char /*victim*/")]),
}

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="stale-object-reads-", dir=ROOT / "bin/tests") as tmp:
    for name, (harness, origin, functions) in HARNESSES.items():
        path = Path(tmp) / f"{name}.cpp"
        path.write_text(harness.replace("// INCLUDES", includes(origin)).replace(
            "// FUNCTIONS", "\n".join(extract_function(*f) for f in functions)))
        binary = path.with_suffix("")
        subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                        "-fno-sanitize-recover=undefined", "-fno-omit-frame-pointer",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-Isrc", "-I/usr/include/mysql", str(path), str(HARNESS_STUBS),
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env=dict(os.environ,
            ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
