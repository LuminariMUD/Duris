#!/usr/bin/env python3
"""Calls that break a directional character link must name its linking side first.

Compiles the production buck(), event_bearhug(), charm_broken() and stop_follower()
under ASan/UBSan with the real link code and link registrations from affects.c.
Affect storage, output and combat services are fixtures. Each case runs on its own:
- buck: the thrown rider no longer rides the mount (riding links run rider to mount).
- bearhug: releasing a bearhug frees the victim, whose hold links it to the grappler.
- dragoon: losing a dragoon mount leaves the dragoon following its group leader.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/mm.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "combat/damage.h"
#include "combat/grapple.h"
#include "abilities/abilities.h"
#include "classes/necromancy.h"
#include "persistence/persistence_checkpoint.h"
#include "redis/redis_floor_runtime.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static room_data rooms[1]{};
P_room world = rooms;
static index_data mob_indexes[1]{};
P_index mob_index = mob_indexes;
link_description link_types[LNK_MAX + 1]{};
static mm_ds link_pool{};
mm_ds *dead_link_pool = &link_pool;
static int melee_calls, dirty_calls;

void *_mm_get(mm_ds *, const char *, int) { return new char_link_data{}; }
void mm_release(mm_ds *, void *value) { delete static_cast<char_link_data *>(value); }
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { return &link_pool; }
void __free(void *pointer, const char *, int) { std::free(pointer); }
void logit(const char *, const char *, ...) {}
void wear_off_message(P_char, affected_type *) {}
void unlink_char_affect(P_char, affected_type *);
void charm_broken(char_link_data *);
void send_to_char(const char *, P_char) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int number(int, int high) { return high; }
void appear(P_char, bool) {}
void CharWait(P_char, int) {}
void Stun(P_char, P_char, int, bool) {}
int melee_damage(P_char, P_char, double, int, struct damage_messages *, int *)
{
	++melee_calls;
	return DAM_NONEDEAD;
}
int CanDoFightMove(P_char, P_char) { return TRUE; }
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
bool notch_skill(P_char, int, float) { return false; }
int GET_CHAR_SKILL_P(P_char, int) { return 100; }
int BOUNDED(int low, int value, int high) { return value < low ? low : value > high ? high : value; }
const Rolls live_rolls{};
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int)
{
	std::abort();
}
void obj_from_char(P_obj) { std::abort(); }
void obj_to_room(P_obj, int) { std::abort(); }
void redis_log_floor_drop(P_obj, int) { std::abort(); }
void hold_durable_pet_items(P_char) {}
void unequip_all(P_char) {}
void mark_player_dirty_components(int, player_component_mask_t) { ++dirty_calls; }
int CheckFor_remember(P_char, P_char) { return FALSE; }
void MobStartFight(P_char, P_char) { std::abort(); }
void schedule_pet_death(P_char, int) { std::abort(); }
bool group_remove_member(P_char) { std::abort(); }

affected_type *affect_to_char(P_char ch, affected_type *af)
{
	affected_type *copy = new affected_type(*af);
	copy->next = ch->affected;
	ch->affected = copy;
	return copy;
}
void affect_remove(P_char ch, affected_type *af)
{
	affected_type **at = &ch->affected;
	while (*at != af)
		at = &(*at)->next;
	*at = af->next;
	if (IS_SET(af->flags, AFFTYPE_LINKED_CH))
		unlink_char_affect(ch, af);
	delete af;
}
'''

DRIVER = r'''
static void standing(P_char ch)
{
	SET_POS(ch, POS_STANDING + STAT_NORMAL);
	ch->in_room = 0;
}

static void follow(P_char follower, P_char leader)
{
	follower->following = leader;
	auto *entry = static_cast<follow_type *>(std::calloc(1, sizeof(follow_type)));
	entry->follower = follower;
	entry->next = leader->followers;
	leader->followers = entry;
}

static void buck_throws_rider()
{
	char_data mount{}, rider{};
	npc_only_data npc{};
	pc_only_data pc{};
	mount.only.npc = &npc;
	mount.specials.act = ACT_ISNPC | ACT_MOUNT;
	rider.only.pc = &pc;
	standing(&mount);
	standing(&rider);
	link_char(&rider, &mount, LNK_RIDING);
	assert(GET_RIDER(&mount) == &rider && GET_MOUNT(&rider) == &mount);

	buck(&mount);

	assert(melee_calls == 1 && GET_POS(&rider) == POS_PRONE);
	assert(!GET_RIDER(&mount) && !GET_MOUNT(&rider));
	assert(!mount.linked && !rider.linking);
}

static void bearhug_release_frees_victim()
{
	for (int hold : { SKILL_BEARHUG, TAG_BEARHUG })
	{
		char_data grappler{}, victim{};
		standing(&grappler);
		standing(&victim);
		affected_type af{};
		af.type = hold;
		af.duration = 48;
		linked_affect_to_char(&victim, &af, &grappler, LNK_GRAPPLED);
		af = {};
		af.type = TAG_GRAPPLE;
		af.duration = 45;
		affect_to_char(&grappler, &af);
		assert(IS_BEARHUG(&victim) && grapple_attack_check(&victim) == &grappler);

		// The victim is knocked down, so the next squeeze lets go.
		SET_POS(&victim, POS_PRONE + STAT_NORMAL);
		event_bearhug(&grappler, &victim, nullptr, nullptr);

		assert(!IS_TGRAPPLE(&grappler) && GRAPPLE_TIMER(&grappler));
		assert(!IS_GRAPPLED(&victim) && !grapple_attack_check(&victim));
		assert(!victim.linking && !grappler.linked && !melee_calls);
		affect_from_char(&grappler, SKILL_GRAPPLER_COMBAT);
	}
}

static void dragoon_keeps_following_when_mount_dies()
{
	char_data leader{}, dragoon{}, mount{};
	pc_only_data leader_pc{}, dragoon_pc{};
	npc_only_data npc{};
	leader.only.pc = &leader_pc;
	dragoon.only.pc = &dragoon_pc;
	mount.only.npc = &npc;
	mount.specials.act = ACT_ISNPC | ACT_MOUNT;
	for (P_char ch : { &leader, &dragoon, &mount })
		standing(ch);
	follow(&dragoon, &leader);

	// As the dragoon's mount summon sets them up.
	affected_type charm{};
	charm.type = SPELL_CHARM_PERSON;
	charm.duration = -1;
	linked_affect_to_char(&mount, &charm, &dragoon, LNK_PET);
	follow(&mount, &dragoon);
	link_char(&dragoon, &mount, LNK_DRAGOON_MOUNT);
	assert(GET_MASTER(&mount) == &dragoon);
	assert(get_linked_char(&dragoon, LNK_DRAGOON_MOUNT) == &mount);

	clear_all_links(&mount);

	assert(!mount.following && !mount.affected && dirty_calls == 1);
	assert(dragoon.following == &leader && leader.followers->follower == &dragoon);
	assert(!dragoon.followers && !dragoon.linking && !dragoon.linked);
	std::free(leader.followers);
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	initialize_test_links();
	if (!std::strcmp(argv[1], "buck"))
		buck_throws_rider();
	else if (!std::strcmp(argv[1], "bearhug"))
		bearhug_release_frees_victim();
	else if (!std::strcmp(argv[1], "dragoon"))
		dragoon_keeps_following_when_mount_dies();
	else
		return 2;
	std::printf("%s passed\n", argv[1]);
}
'''

AFFECTS = "magic/affects.c"
functions = [extract_function(AFFECTS, signature) for signature in (
    "void define_link(", "struct char_link_data *link_char_with_affect(",
    "struct char_link_data *link_char(", "P_char get_linked_char(", "P_char get_linking_char(",
    "void dispose_link(", "void internal_unlink_char(", "void unlink_char(P_char ch,",
    "void unlink_char_affect(P_char ch, struct affected_type *af)",
    "void clear_links(P_char ch, ush_int type)", "void clear_all_links(",
    "void linked_affect_to_char(", "void affect_from_char(",
    "struct affected_type *get_spell_from_char(", "bool affected_by_spell(P_char ch, int skill)",
)]
links = extract_function(AFFECTS, "void initialize_links()")
registrations = [re.search(rf"define_link\({name},.*?;", links, re.S)[0]
                 for name in ("LNK_RIDING", "LNK_PET", "LNK_GRAPPLED", "LNK_DRAGOON_MOUNT")]
functions.append("void initialize_test_links() {\n" + "\n".join(registrations) + "\n}")
functions += [extract_function("combat/grapple.c", signature) for signature in (
    "P_char grapple_attack_check(", "static int bearhug_interval(",
    "static int bearhug_base_damage(", "static int bearhug_damage_roll(",
    "static int bearhug_rest(", "void event_bearhug(",
)]
functions += [
    extract_function("cmd/actoff.c", "void buck(P_char ch)"),
    extract_function("sparser.c", "void stop_follower(P_char ch)"),
    extract_function("classes/necromancy.c", "void charm_broken(struct char_link_data *cld)"),
]

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="reversed-links-", dir=ROOT / "bin/tests") as tmp:
    harness = Path(tmp) / "harness.cpp"
    binary = harness.with_suffix("")
    harness.write_text("\n".join((PRELUDE, *functions, DRIVER)), encoding="utf-8")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                    "-Isrc", "-I/usr/include/mysql", str(harness), str(HARNESS_STUBS),
                    "-o", str(binary)], cwd=ROOT, check=True)
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1")
    failed = [case for case in ("buck", "bearhug", "dragoon")
              if subprocess.run([str(binary), case], env=env).returncode]
    assert not failed, f"failed: {', '.join(failed)}"
