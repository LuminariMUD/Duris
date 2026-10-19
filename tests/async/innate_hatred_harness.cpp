// The effect pool frees nodes immediately so invalid traversals fail under ASan.
#include "world/new_events.c"
#include "classes/necromancy.h"
#include "world/weather.h"
#include "net/gmcp.h"
#include <cassert>
#include <string>

int pulse = 0;
bool after_events_call = FALSE;
P_char character_list = nullptr;
P_obj object_list = nullptr;
static index_data mob_indexes[1]{};
P_index mob_index = mob_indexes;
P_index obj_index = nullptr;
static room_data rooms[2]{};
P_room world = rooms;
static zone_data zones[1]{};
zone_data *zone_table = zones;
extern const int top_of_world = 1;
Skill skills[MAX_AFFECT_TYPES + 1];
time_info_data time_info{};
extern const stat_data stat_factor[256]{};
hold_data TmpAffs{};
static mm_ds event_pool{}, affect_pool{};
mm_ds *dead_affect_pool = &affect_pool;
static int timer = WAIT_SEC;
static int activations, subsides;

bool nevent_periodic_begin(P_nevent)
{
	return false;
}
void nevent_periodic_complete(P_nevent) {}
void nevent_periodic_watchdog() {}
bool nevent_periodic_event_is_valid(P_nevent)
{
	return true;
}
long nevent_periodic_integrity_errors(bool)
{
	return 0;
}
const char *event_name_registry_lookup(const void *)
{
	return nullptr;
}
void release_mob_mem(P_char, P_char, P_obj, void *) {}
void event_hit_regen(P_char, P_char, P_obj, void *) {}
void event_mana_regen(P_char, P_char, P_obj, void *) {}
void event_ward_regen(P_char, P_char, P_obj, void *) {}
void event_wait(P_char, P_char, P_obj, void *) {}
void event_move_regen(P_char, P_char, P_obj, void *) {}
void event_spellcast(P_char, P_char, P_obj, void *) {}
void event_item_action_active(P_char, P_char, P_obj, void *) {}
void event_memorize(P_char, P_char, P_obj, void *) {}
void event_balance_affects(P_char, P_char, P_obj, void *) {}
void event_mob_mundane(P_char, P_char, P_obj, void *) {}
void event_reset_zone(P_char, P_char, P_obj, void *) {}
void event_autosave(P_char, P_char, P_obj, void *) {}
void event_short_affect(P_char, P_char, P_obj, void *) {}
void event_web_spray(P_char, P_char, P_obj, void *) {}
void unlink_char_affect(P_char, affected_type *)
{
	assert(false);
}
void unlink_char_obj_affect(P_char, affected_type *)
{
	assert(false);
}
void *__malloc(size_t size, const char *, const char *, int)
{
	return std::malloc(size);
}
void __free(void *memory, const char *, int)
{
	std::free(memory);
}
void *_mm_get(mm_ds *pool, const char *, int)
{
	++pool->objs_used;
	return std::calloc(1, pool == &event_pool ? sizeof(nevent_data) : sizeof(affected_type));
}
void mm_release(mm_ds *pool, void *memory)
{
	assert(pool->objs_used > 0);
	--pool->objs_used;
	std::free(memory);
}
int GET_CLASS(P_char ch, unsigned int cls)
{
	return (ch->player.m_class & cls) != 0;
}
int get_property(const char *key, int fallback)
{
	return !std::strcmp(key, "innate.timer.hatred") ? timer : fallback;
}
void act(const char *text, int, P_char, P_obj, void *, int)
{
	if (std::strstr(text, "BURN"))
		++activations;
}
void send_to_char(const char *text, P_char)
{
	if (std::strstr(text, "hatred in your heart subside"))
		++subsides;
}
void affect_modify(int, int, unsigned long *, int);
void balance_affects(P_char ch)
{
	TmpAffs = {};
	for (auto *af = ch->affected; af; af = af->next)
		affect_modify(af->location, af->modifier, &af->bitvector, FALSE);
	ch->points.combat_pulse = TmpAffs.combat_pulse;
	ch->points.spell_pulse = TmpAffs.spell_pulse;
}
void all_affects(P_char ch, int)
{
	balance_affects(ch);
}
int char_light(P_char)
{
	return 0;
}
int room_light(int, int)
{
	return 0;
}
bool IS_TWILIGHT_ROOM(int)
{
	return false;
}
bool IS_OUTDOORS(int)
{
	return false;
}
bool is_linked_to(P_char, P_char, ush_int)
{
	return false;
}
void gmcp_char_affects(P_char) {}
mm_ds *mm_create(const char *, size_t, size_t, unsigned int)
{
	assert(false);
	return nullptr;
}
char_link_data *link_char(P_char, P_char, ush_int)
{
	assert(false);
	return nullptr;
}
void remove_link(P_char, char_link_data *)
{
	assert(false);
}

#include "production.inc"

struct scene
{
	char_data dwarf{}, target{};
	pc_only_data player{}, other_player{};
	scene()
	{
		dwarf.only.pc = &player;
		target.only.pc = &other_player;
		SET_POS(&dwarf, STAT_NORMAL + POS_STANDING);
		SET_POS(&target, STAT_NORMAL + POS_STANDING);
		dwarf.player.race = RACE_MOUNTAIN;
		dwarf.player.level = 21;
		dwarf.in_room = target.in_room = 0;
		dwarf.next_in_room = &target;
		rooms[0].people = &dwarf;
		target.player.race = RACE_HUMAN;
		activations = subsides = 0;
	}
	~scene()
	{
		disarm_char_nevents(&dwarf, nullptr);
		while (dwarf.affected)
			affect_remove(&dwarf, dwarf.affected);
		assert(event_pool.objs_used == 0 && affect_pool.objs_used == 0);
		rooms[0].people = nullptr;
	}
	void check()
	{
		disarm_char_nevents(&dwarf, event_hatred_check);
		event_hatred_check(&dwarf, nullptr, nullptr, nullptr);
	}
	void add(int location, int modifier = -1, int type = TAG_HATRED)
	{
		affected_type af{};
		af.type = type;
		af.flags = AFFTYPE_NOSAVE | AFFTYPE_NODISPEL;
		af.location = location;
		af.modifier = modifier;
		af.duration = -1;
		affect_to_char(&dwarf, &af);
	}
	int count()
	{
		int n = 0;
		for (auto *af = dwarf.affected; af; af = af->next)
			n += af->type == TAG_HATRED;
		return n;
	}
	void pair()
	{
		assert(count() == 2);
		assert(dwarf.points.combat_pulse == -1 && dwarf.points.spell_pulse == -1);
	}
};

int main(int argc, char **argv)
{
	assert(argc == 2);
	nevent_bind_game_thread();
	ne_dead_event_pool = &event_pool;
	assign_innates();
	skills[TAG_HATRED].wear_off_char[0] = "You feel the hatred in your heart subside.";
	if (!std::strcmp(argv[1], "bounds"))
	{
		scene s;
		s.check();
		assert(!s.count() && !activations && !subsides);
	}
	else if (!std::strcmp(argv[1], "cleanup"))
	{
		scene s;
		s.dwarf.next_in_room = nullptr;
		s.add(APPLY_COMBAT_PULSE);
		s.add(APPLY_SPELL_PULSE);
		s.check();
		assert(!s.count() && subsides == 1);
		s.check();
		assert(subsides == 1);
	}
	else if (!std::strcmp(argv[1], "partial"))
	{
		scene s;
		s.target.player.race = RACE_ORC;
		s.add(APPLY_COMBAT_PULSE);
		s.check();
		s.pair();
		assert(!activations);
	}
	else if (!std::strcmp(argv[1], "matching"))
	{
		for (int race = 0; race <= LAST_RACE + 1; ++race)
		{
			scene s;
			s.target.player.race = race;
			s.check();
			bool hated = race == RACE_ORC || race == RACE_DUERGAR || race == RACE_DROW;
			assert(s.count() == (hated ? 2 : 0) && activations == hated);
		}
		{
			scene s;
			s.target.player.race = static_cast<ubyte>(-1);
			s.check();
			assert(!s.count());
		}
		for (int race : { RACE_ORC, RACE_DUERGAR, RACE_DROW })
		{
			scene s;
			s.target.player.race = race;
			s.check();
			s.pair();
			assert(activations == 1);
			s.check();
			s.pair();
			assert(activations == 1);
			s.dwarf.next_in_room = nullptr;
			s.check();
			assert(!s.count() && subsides == 1);
			s.dwarf.next_in_room = &s.target;
			s.check();
			s.pair();
			assert(activations == 2);
		}
		scene s;
		npc_only_data npc{};
		s.target.only.npc = &npc;
		s.target.specials.act = ACT_ISNPC;
		s.target.player.race = RACE_ORC;
		s.check();
		s.pair();
		s.dwarf.next_in_room = nullptr;
		s.target.in_room = 1;
		rooms[1].people = &s.target;
		s.check();
		assert(!s.count() && subsides == 1);
		rooms[1].people = nullptr;
	}
	else if (!std::strcmp(argv[1], "visibility"))
	{
		scene s;
		s.target.player.race = RACE_ORC;
		s.target.specials.affected_by = AFF_INVISIBLE;
		s.check();
		assert(!s.count());
		s.dwarf.specials.affected_by = AFF_DETECT_INVISIBLE;
		s.check();
		s.pair();
		s.target.specials.affected_by = AFF_HIDE;
		s.check();
		assert(!s.count() && subsides == 1);
		s.target.specials.affected_by = 0;
		s.dwarf.specials.affected_by = AFF_BLIND;
		s.check();
		assert(!s.count());
		s.dwarf.specials.affected_by = 0;
		SET_POS(&s.dwarf, STAT_SLEEPING + POS_PRONE);
		s.check();
		assert(!s.count());
		SET_POS(&s.dwarf, STAT_NORMAL + POS_STANDING);
		s.check();
		s.pair();
		assert(activations == 2);
	}
	else if (!std::strcmp(argv[1], "eligibility"))
	{
		for (int race = 0; race <= LAST_RACE; ++race)
		{
			scene s;
			s.target.player.race = RACE_ORC;
			s.dwarf.player.race = race;
			s.check();
			assert(s.count() == (race == RACE_MOUNTAIN ? 2 : 0));
		}
		scene s;
		s.target.player.race = RACE_ORC;
		s.dwarf.player.level = 20;
		s.check();
		assert(!s.count());
		s.dwarf.player.level = 21;
		s.check();
		s.pair();
		s.dwarf.disguise.active_shapechange = true;
		s.dwarf.disguise.race = RACE_HUMAN;
		s.check();
		assert(!s.count() && subsides == 1);
		s.dwarf.disguise.active_shapechange = false;
		s.check();
		s.pair();
		// A human borrowing mountain-dwarf innates still has no actual-race rule.
		s.dwarf.player.race = RACE_HUMAN;
		s.dwarf.disguise.active_shapechange = true;
		s.dwarf.disguise.race = RACE_MOUNTAIN;
		s.check();
		assert(!s.count());
		s.dwarf.disguise.active_shapechange = false;
		s.add(APPLY_NONE, RACE_MOUNTAIN, TAG_RACE_CHANGE);
		s.add(APPLY_NONE, CORPSEFORM_REG, SPELL_CORPSEFORM);
		assert(has_innate(&s.dwarf, INNATE_HATRED));
		s.check();
		assert(!s.count());
		affect_from_char(&s.dwarf, TAG_RACE_CHANGE);
		affect_from_char(&s.dwarf, SPELL_CORPSEFORM);
		s.check();
		s.pair();
		s.dwarf.in_room = NOWHERE;
		s.check();
		assert(!s.count());
		event_hatred_check(nullptr, nullptr, nullptr, nullptr);
	}
	else if (!std::strcmp(argv[1], "normalization"))
	{
		for (int location : { APPLY_COMBAT_PULSE, APPLY_SPELL_PULSE, APPLY_HITROLL })
		{
			scene s;
			s.target.player.race = RACE_ORC;
			s.add(location, -7);
			s.add(APPLY_NONE, 0, SPELL_BLESS);
			s.add(APPLY_COMBAT_PULSE);
			s.add(APPLY_COMBAT_PULSE);
			s.add(APPLY_SPELL_PULSE);
			s.check();
			s.pair();
			assert(!activations && !subsides);
			assert(get_spell_from_char(&s.dwarf, SPELL_BLESS));
			s.dwarf.next_in_room = nullptr;
			s.check();
			assert(!s.count() && subsides == 1);
			assert(get_spell_from_char(&s.dwarf, SPELL_BLESS));
			assert(s.dwarf.points.combat_pulse == 0 && s.dwarf.points.spell_pulse == 0);
		}
	}
	else
		assert(false);
	std::printf("Hatred production case passed: %s\n", argv[1]);
}
