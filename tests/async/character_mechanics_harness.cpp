#include "core/prototypes.h"
#include "core/utils.h"
#include "account/creation_availability_config.h"
#include "classes/specializations.h"
#include "classes/skills.h"
#include "player/character_mechanics.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "cmd/interp.h"
#include "guild/assocs.h"
#include "item/trophy.h"

#include <algorithm>
#include <cassert>
#include <tuple>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <set>
#include <type_traits>

using namespace character_mechanics;

void load_character_properties();
void set_character_property(const char *key, float value);
void clear_character_properties();
void update_dam_factors();
double bulwark_melee(P_char attacker, P_char victim, bool bypass = false);
extern Skill skills[MAX_AFFECT_TYPES + 1];
extern command_info cmd_info[MAX_CMD_LIST];
extern P_room world;
extern std::string mechanic_output;
void initialize_mechanic_commands();
void initialize_mechanic_objects();
void initialize_mechanic_rooms();
extern P_index obj_index;
extern int mechanic_removed_affects, mechanic_stop_memorizing, mechanic_ledger_calls;
extern int mechanic_kit_requests, mechanic_restores, mechanic_coin_refund, mechanic_saves;
extern bool mechanic_stage_coin_refund;
void update_stat_data();
void update_damage_data();
int calculate_hitpoints2(P_char);
int multiclass_proc(int, P_char, int, char *);
extern P_nevent current_nevent;
extern int mechanic_crown_events, mechanic_object_events, mechanic_wait;

static void revenant_transition()
{
	const auto mechanics = mechanic_connections();
	const auto transitions = transition_connections();
	assert(transitions.back().kind == TransitionKind::temporary);
	const int slot = real_object(22070);
	assert(slot > 0);
	const auto crown_proc = obj_index[slot].func.obj;
	assert(crown_proc);
	obj_index[slot].func.obj = nullptr;
	assert(!validate_mechanics(mechanics).empty());
	assert(!validate_transitions(transitions, mechanics).empty());
	obj_index[slot].func.obj = crown_proc;
	auto missing = mechanics;
	for (auto &connection : missing)
		if (connection.id == MechanicId::race_status_load)
			connection.binding = player_status_field::level;
	assert(!validate_transitions(transitions, missing).empty());
	missing = mechanics;
	for (auto &connection : missing)
		if (connection.id == MechanicId::equipment_load)
			connection.binding = PLAYER_COMPONENT_SKILLS;
	assert(!validate_transitions(transitions, missing).empty());
	event_func_type periodic = nullptr, lifecycle = nullptr;
	for (const auto &connection : mechanics)
	{
		if (connection.id == MechanicId::object_periodic)
			periodic = std::get<event_func_type>(connection.binding);
		if (connection.id == MechanicId::revenant_lifecycle)
			lifecycle = std::get<event_func_type>(connection.binding);
		if (connection.id == MechanicId::revenant_value)
			assert(std::get<ObjectProcValue>(connection.binding)(crown_proc) == 225);
	}
	assert(periodic && lifecycle);
	char_data wearer{};
	pc_only_data pc{};
	wearer.only.pc = &pc;
	wearer.player.race = RACE_ORC;
	wearer.player.m_class = CLASS_WARRIOR;
	wearer.player.secondary_class = CLASS_CLERIC;
	wearer.player.level = 41;
	SET_POS(&wearer, STAT_NORMAL + POS_STANDING);
	obj_data crown{}, gear{};
	crown.R_num = slot;
	assert(crown_proc(&crown, nullptr, CMD_SET_PERIODIC, nullptr));
	assert(!crown_proc(&crown, nullptr, CMD_PERIODIC, nullptr)); // Unworn.
	crown.loc_p = LOC_WORN;
	crown.loc.wearing = &wearer;
	wearer.equipment[WEAR_HEAD] = &crown;
	assert(!crown_proc(&crown, &wearer, CMD_WEAR, nullptr)); // Waits for periodic.
	SET_BIT(wearer.specials.act, ACT_ISNPC);
	assert(!crown_proc(&crown, nullptr, CMD_PERIODIC, nullptr));
	REMOVE_BIT(wearer.specials.act, ACT_ISNPC);
	SET_POS(&wearer, STAT_DEAD);
	assert(!crown_proc(&crown, nullptr, CMD_PERIODIC, nullptr));
	SET_POS(&wearer, STAT_NORMAL + POS_STANDING);
	affected_type existing{};
	existing.type = TAG_RACE_CHANGE;
	wearer.affected = &existing;
	assert(!crown_proc(&crown, nullptr, CMD_PERIODIC, nullptr));
	assert(wearer.player.race == RACE_ORC && wearer.affected == &existing);
	wearer.affected = nullptr;
	static int gear_removals;
	gear_removals = 0;
	obj_index[0].func.obj = [](P_obj, P_char, int cmd, char *) -> int
	{
		assert(cmd == CMD_REMOVE);
		++gear_removals;
		return TRUE;
	};
	gear.loc_p = LOC_WORN;
	gear.loc.wearing = &wearer;
	wearer.equipment[WEAR_BODY] = &gear;
	nevent_data active{};
	active.obj = &crown;
	current_nevent = &active;
	mechanic_crown_events = mechanic_object_events = mechanic_wait = 0;
	const auto before = time(nullptr);
	periodic(nullptr, nullptr, &crown, nullptr);
	assert(mechanic_crown_events == 1 && mechanic_object_events == 1);
	assert(mechanic_wait == 5 * WAIT_SEC);
	assert(wearer.player.race == RACE_REVENANT);
	assert(wearer.player.time.birth >= before - 100 * SECS_PER_MUD_YEAR);
	assert(wearer.player.time.birth <= time(nullptr) - 100 * SECS_PER_MUD_YEAR);
	assert(wearer.player.m_class == CLASS_WARRIOR &&
	       wearer.player.secondary_class == CLASS_CLERIC && wearer.player.level == 41);
	assert(wearer.equipment[WEAR_HEAD] == &crown && !wearer.equipment[WEAR_BODY]);
	assert(wearer.carrying == &gear && gear_removals == 1);
	assert(wearer.affected && wearer.affected->modifier == RACE_ORC &&
	       wearer.affected->duration == -1);
	assert(wearer.affected->flags == (AFFTYPE_NOSAVE | AFFTYPE_NODISPEL | AFFTYPE_NOAPPLY));
	periodic(nullptr, nullptr, &crown, nullptr); // Existing tag prevents reapplication.
	assert(mechanic_crown_events == 1 && mechanic_object_events == 2 && gear_removals == 1);
	lifecycle(&wearer, nullptr, nullptr, nullptr); // Worn crown retains/rearms.
	assert(mechanic_crown_events == 2 && wearer.player.race == RACE_REVENANT);
	wearer.player.race = RACE_HUMAN;
	GET_HIT(&wearer) = 200;
	lifecycle(&wearer, nullptr, nullptr, nullptr);
	assert(GET_HIT(&wearer) == 100 && mechanic_wait == 2 * WAIT_SEC);
	assert(mechanic_crown_events == 2 && wearer.affected);
	wearer.player.race = RACE_REVENANT;
	obj_to_char(unequip_char(&wearer, WEAR_HEAD), &wearer);
	lifecycle(&wearer, nullptr, nullptr, nullptr);
	assert(wearer.player.race == RACE_ORC && !wearer.affected);
	assert(wearer.player.time.birth >= before - 15 * SECS_PER_MUD_YEAR);
	assert(wearer.player.time.birth <= time(nullptr) - 15 * SECS_PER_MUD_YEAR);
	assert(mechanic_crown_events == 2);
	wearer.player.race = RACE_REVENANT;
	mechanic_output.clear();
	lifecycle(&wearer, nullptr, nullptr, nullptr);
	assert(mechanic_output.find("Possible serious screwup") != std::string::npos);
	assert(mechanic_crown_events == 2);
	current_nevent = nullptr; // An extracted/detached object must not rearm.
	periodic(nullptr, nullptr, &crown, nullptr);
	assert(mechanic_object_events == 2);
	obj_index[0].func.obj = nullptr;
	std::puts(
		"revenant.entry/lifecycle: PASS (registered periodic callback, guards, race/tag/birth, stripping, retention, removal and conflicts; scheduler, equipment transfer and derived-stat services are fixture boundaries)");
}

static void race_and_death_cleanup()
{
	AffectRemoval remove = nullptr;
	CharacterAction death = nullptr;
	for (const auto &connection : mechanic_connections())
	{
		if (connection.id == MechanicId::race_affect_cleanup)
			remove = std::get<AffectRemoval>(connection.binding);
		if (connection.id == MechanicId::death_affect_cleanup)
			death = std::get<CharacterAction>(connection.binding);
	}
	assert(remove == affect_remove && death);
	char_data subject{};
	pc_only_data pc{};
	subject.only.pc = &pc;
	SET_POS(&subject, STAT_DEAD);
	// Exercise real head, middle and tail removal. The last case represents
	// raw_damage having already restored race before generic cleanup runs.
	for (int position = 0; position < 3; ++position)
	{
		affected_type *nodes[] = { new affected_type{}, new affected_type{},
					   new affected_type{} };
		for (int i = 0; i < 3; ++i)
		{
			nodes[i]->type = SPELL_BLESS;
			nodes[i]->next = i < 2 ? nodes[i + 1] : nullptr;
		}
		nodes[position]->type = TAG_RACE_CHANGE;
		nodes[position]->modifier = RACE_ORC;
		nodes[position]->flags = AFFTYPE_NOSAVE | AFFTYPE_NOAPPLY;
		subject.affected = nodes[0];
		subject.player.race = position == 2 ? RACE_ORC : RACE_REVENANT;
		const auto now = time(nullptr);
		subject.player.time.birth = now - 100 * SECS_PER_MUD_YEAR;
		remove(&subject, nodes[position]);
		assert(subject.player.race == RACE_ORC);
		assert(subject.player.time.birth >= now - 15 * SECS_PER_MUD_YEAR);
		assert(subject.player.time.birth <= time(nullptr) - 15 * SECS_PER_MUD_YEAR);
		int survivors = 0;
		for (auto *af = subject.affected; af; af = af->next)
		{
			assert(af->type == SPELL_BLESS);
			++survivors;
		}
		assert(survivors == 2);
		while (subject.affected)
			remove(&subject, subject.affected);
	}
	auto *memory = new affected_type{};
	auto *race = new affected_type{};
	auto *temporary = new affected_type{};
	auto *permanent = new affected_type{};
	auto *temporary_memory = new affected_type{};
	memory->type = temporary_memory->type = TAG_MEMORIZE;
	memory->flags = AFFTYPE_PERM | MEMTYPE_FULL;
	temporary_memory->flags = MEMTYPE_FULL;
	memory->modifier = SPELL_BLESS;
	permanent->type = SPELL_BLESS;
	permanent->flags = AFFTYPE_PERM;
	race->type = TAG_RACE_CHANGE;
	race->modifier = RACE_ORC;
	race->flags = AFFTYPE_NOSAVE | AFFTYPE_NOAPPLY;
	memory->next = race;
	race->next = temporary;
	temporary->next = permanent;
	permanent->next = temporary_memory;
	subject.affected = memory;
	subject.player.race = RACE_REVENANT;
	const auto now = time(nullptr);
	subject.player.time.birth = now - 100 * SECS_PER_MUD_YEAR;
	const int before_removed = mechanic_removed_affects;
	death(&subject);
	assert(mechanic_removed_affects == before_removed + 3);
	assert(subject.affected == memory && memory->next == permanent && !permanent->next);
	assert((memory->flags & AFFTYPE_PERM) && !(memory->flags & MEMTYPE_FULL));
	assert(memory->modifier == SPELL_BLESS && permanent->flags == AFFTYPE_PERM);
	assert(subject.player.race == RACE_ORC);
	assert(subject.player.time.birth >= now - 15 * SECS_PER_MUD_YEAR);
	assert(subject.player.time.birth <= time(nullptr) - 15 * SECS_PER_MUD_YEAR);
	while (subject.affected)
		remove(&subject, subject.affected);
	death(&subject);
	std::puts(
		"race/death.cleanup: PASS (real removal at head/middle/tail, original race/birth even after fatal race reset, permanent retention and memorized fullness; stat/light/event services remain fixture boundaries)");
}

static void multiclass_denials()
{
	load_character_properties();
	char_data student{};
	pc_only_data pc{};
	student.only.pc = &pc;
	student.player.m_class = CLASS_WARRIOR;
	student.player.level = 50;
	pc.epics = 17;
	auto command = [&](const char *choice)
	{
		char args[MAX_INPUT_LENGTH];
		strcpy(args, choice);
		mechanic_output.clear();
		if (!multiclass_proc(0, &student, CMD_MULTICLASS, args))
			do_multiclass(&student, args, CMD_MULTICLASS);
		assert(student.player.secondary_class == 0 && student.player.level == 50);
		assert(pc.epics == 17);
	};
	student.player.race = RACE_GNOME;
	command("cleric");
	assert(mechanic_output == "Your race is not versatile enough to learn that much.\n");
	set_character_property("multiclass.epic.req.min", 20);
	for (int race : { RACE_HUMAN, RACE_ORC })
	{
		student.player.race = race;
		command("cleric");
		assert(mechanic_output.find("need more") != std::string::npos);
		assert(mechanic_output.find("proper location") == std::string::npos);
	}
	set_character_property("multiclass.epic.req.min", 0);
	command("nonsense");
	assert(mechanic_output.find("no class, bubba") != std::string::npos);
	command("sorcerer");
	assert(mechanic_output.find("cannot multiclass to that particular class") !=
	       std::string::npos);
	assert(!multiclass_proc(0, nullptr, CMD_SET_PERIODIC, nullptr));
	clear_character_properties();
	std::puts(
		"multiclass.denials: PASS (room owns race/funds denials; no duplicate or incorrect location fallback; no state changes)");
}

static void multiclass_reset_and_consumers()
{
	const auto mechanics = mechanic_connections();
	const auto transitions = transition_connections();
	for (int vnum : { 17, 52904 })
	{
		const int room = real_room(vnum);
		assert(room > 0);
		const auto handler = world[room].funct;
		world[room].funct = nullptr;
		assert(!validate_transitions(transitions, mechanics).empty());
		world[room].funct = handler;
	}
	auto missing_fields = mechanics;
	for (auto &connection : missing_fields)
		if (connection.id == MechanicId::multiclass_status_capture)
			connection.binding = std::get<StatusFields>(connection.binding).subspan(1);
	assert(!validate_transitions(transitions, missing_fields).empty());
	auto missing_skills = mechanics;
	for (auto &connection : missing_skills)
		if (connection.id == MechanicId::skills_load)
			connection.binding = PLAYER_COMPONENT_AFFECTS;
	assert(!validate_transitions(transitions, missing_skills).empty());
	load_character_properties();
	update_stat_data();
	update_damage_data();
	for (auto &skill : skills)
		skill = Skill{};
	auto grant = [](int skill, unsigned int cls, int level, int cap)
	{
		auto &row = skills[skill].m_class[flag2idx(cls) - 1];
		row.rlevel[0] = level;
		row.maxlearn[0] = cap;
	};
	// Explicit skill cells isolate consumer branches; the world journey uses
	// the real initialized skill table at the same 5/6 boundary.
	grant(SKILL_KICK, CLASS_WARRIOR, 1, 100);
	grant(SKILL_MEDITATE, CLASS_CLERIC, 1, 100);
	grant(SKILL_BANDAGE, CLASS_WARRIOR, 1, 90);
	grant(SKILL_BANDAGE, CLASS_CLERIC, 1, 100);
	grant(SKILL_GUARD, CLASS_WARRIOR, 41, 70);
	skills[SKILL_EPIC_STRENGTH].name = "epic strength";
	skills[SKILL_EPIC_STRENGTH].targets = TAR_MENTAL | TAR_EPIC;
	skills[SKILL_FORGE].name = "forge";
	skills[SKILL_FORGE].targets = TAR_MENTAL | TAR_EPIC;
	struct RefundCase
	{
		int race;
		bool staged;
		int platinum;
		int expected_platinum;
		int revision;
	};
	for (const auto scenario :
	     { RefundCase{ RACE_HUMAN, true, 3, 3, 0 }, RefundCase{ RACE_ORC, false, 3, 2003, 1 },
	       RefundCase{ RACE_ORC, false, INT_MAX, INT_MAX, 0 } })
	{
		const int race = scenario.race;
		char_data student{};
		pc_only_data pc{};
		Guild guild;
		std::vector<zone_trophy_data> trophies{ { 12, 300 } };
		student.only.pc = &pc;
		student.player.name = const_cast<char *>("Multifixture");
		student.player.title = strdup("old title");
		student.player.race = race;
		student.player.racewar = race == RACE_HUMAN ? RACEWAR_GOOD : RACEWAR_EVIL;
		student.player.m_class = CLASS_WARRIOR;
		student.player.spec = SPEC_GUARDIAN;
		student.player.level = 50;
		student.player.time.played = 12345;
		const time_t logon = time(nullptr) - 600;
		student.player.time.logon = logon;
		student.specials.guild = &guild;
		SET_MEMBER(student.specials.guild_status);
		SET_NORMAL(student.specials.guild_status);
		student.specials.act = PLR_ECHO | PLR_VICIOUS;
		SET_POS(&student, STAT_NORMAL + POS_STANDING);
		GET_EXP(&student) = 999999;
		GET_PLATINUM(&student) = scenario.platinum;
		student.points.max_mana = 200;
		student.points.base_vitality = 80;
		pc.pid = 42;
		pc.epics = 17;
		pc.prestige = 9;
		pc.zone_trophy = &trophies;
		pc.skills[SKILL_EPIC_STRENGTH] = { 20, 20 };
		pc.skills[SKILL_FORGE] = { 70, 70 };
		pc.skills[SKILL_GUARD] = { 80, 100 };
		auto *full = new affected_type{};
		full->type = TAG_MEMORIZE;
		full->flags = MEMTYPE_FULL;
		auto *pending = new affected_type{};
		pending->type = TAG_MEMORIZE;
		pending->next = full;
		student.affected = pending;
		mechanic_kit_requests = mechanic_restores = mechanic_coin_refund = mechanic_saves =
			0;
		mechanic_removed_affects = mechanic_stop_memorizing = mechanic_ledger_calls = 0;
		mechanic_stage_coin_refund = scenario.staged;
		mechanic_output.clear();
		char choice[] = "cleric";
		const int room = real_room(race == RACE_HUMAN ? 52904 : 17);
		assert(world[room].funct(room, &student, CMD_MULTICLASS, choice));
		assert(student.player.m_class == CLASS_WARRIOR &&
		       student.player.secondary_class == CLASS_CLERIC);
		assert(student.player.race == race && student.player.spec == 0);
		assert(student.player.level == 1 && GET_EXP(&student) == 1);
		assert(student.player.time.played == 12345 && student.player.time.logon == logon);
		assert(student.points.base_hit == 1 && student.points.base_mana == 1 &&
		       student.points.base_vitality == 0);
		assert(student.player.title == nullptr && pc.prestige == 0 && trophies.empty());
		assert(student.specials.guild == &guild &&
		       IS_MEMBER(student.specials.guild_status) &&
		       IS_PAROLE(student.specials.guild_status));
		assert(student.specials.act == (PLR_ECHO | PLR_VICIOUS));
		assert(GET_PLATINUM(&student) == scenario.expected_platinum);
		assert(pc.wallet_revision == unsigned(scenario.revision));
		if (!scenario.staged && scenario.revision == 0)
			assert(mechanic_output.find("Your coin refund could not be credited") !=
			       std::string::npos);
		assert(mechanic_kit_requests == 1 && mechanic_restores == 1);
		assert(pc.skills[SKILL_KICK].learned == 20 && pc.skills[SKILL_KICK].taught == 90);
		assert(pc.skills[SKILL_GUARD].learned == 0 && pc.skills[SKILL_GUARD].taught == 100);
		assert(pc.skills[SKILL_FORGE].learned == 70 && pc.skills[SKILL_FORGE].taught == 70);
		assert(pc.skills[SKILL_EPIC_STRENGTH].learned == 0 &&
		       pc.skills[SKILL_EPIC_STRENGTH].taught == 0);
		assert(pc.epics == 317 && mechanic_coin_refund == 2000000 &&
		       mechanic_ledger_calls == 1 && mechanic_saves == 1);
		assert(student.affected == nullptr && mechanic_removed_affects == 2 &&
		       mechanic_stop_memorizing == 1);

		assert(SKILL_DATA_ALL(&student, SKILL_KICK).rlevel[0] == 1);
		assert(SKILL_DATA_ALL(&student, SKILL_KICK).maxlearn[0] == 100);
		assert(SKILL_DATA_ALL(&student, SKILL_MEDITATE).rlevel[0] == 6);
		assert(SKILL_DATA_ALL(&student, SKILL_MEDITATE).maxlearn[0] == 95);
		assert(SKILL_DATA_ALL(&student, SKILL_BANDAGE).rlevel[0] == 1);
		assert(SKILL_DATA_ALL(&student, SKILL_BANDAGE).maxlearn[0] == 95);
		student.player.level = 5;
		update_skills(&student);
		assert(pc.skills[SKILL_MEDITATE].learned == 0);
		student.player.level = 6;
		update_skills(&student);
		assert(pc.skills[SKILL_MEDITATE].learned == 9 &&
		       pc.skills[SKILL_MEDITATE].taught == 95);
		set_character_property("skill.cap.multi.mod.secondarySkill", 80);
		assert(SKILL_DATA_ALL(&student, SKILL_MEDITATE).maxlearn[0] == 80);
		assert(SKILL_DATA_ALL(&student, SKILL_BANDAGE).maxlearn[0] == 90);
		set_character_property("skill.cap.multi.mod.secondarySkill", 95);
		set_character_property("skill.cap.multi.mod.primarySkill", 75);
		assert(SKILL_DATA_ALL(&student, SKILL_KICK).maxlearn[0] == 75);
		set_character_property("skill.cap.multi.mod.primarySkill", 100);

		student.player.level = 40;
		student.curr_stats.Con = 100;
		student.points.base_hit = student.points.max_hit = 1;
		student.player.secondary_class = 0;
		const int warrior_hp = calculate_hitpoints2(&student);
		student.player.m_class = CLASS_CLERIC;
		const int cleric_hp = calculate_hitpoints2(&student);
		assert(warrior_hp > cleric_hp);
		student.player.secondary_class = CLASS_WARRIOR;
		assert(calculate_hitpoints2(&student) == warrior_hp);
		student.player.m_class = CLASS_WARRIOR;
		student.player.secondary_class = CLASS_CLERIC;
		assert(calculate_hitpoints2(&student) == warrior_hp);
	}
	clear_character_properties();
	std::puts(
		"multiclass.reset/consumers: PASS (native reset/refund/forget, guild rank bits, retained state, secondary skills/caps and larger class HP modifier for Human/Orc; delivery/persistence/affect cleanup remain fixture boundaries)");
}

static void specialization_transition()
{
	initialize_mechanic_commands();
	initialize_mechanic_objects();
	initialize_mechanic_rooms();
	const auto mechanics = mechanic_connections();
	const auto transitions = transition_connections();
	const auto errors = validate_transitions(transitions, mechanics);
	for (const auto &error : errors)
		std::fprintf(stderr, "%s\n", error.c_str());
	assert(errors.empty());
	assert(transitions.size() == 4);
	assert(transitions.front().kind == TransitionKind::permanent);

	const auto handler = cmd_info[CMD_SPECIALIZE].command_pointer;
	assert(handler == do_specialize);
	cmd_info[CMD_SPECIALIZE].command_pointer = nullptr;
	assert(!validate_transitions(transitions, mechanics).empty());
	cmd_info[CMD_SPECIALIZE].command_pointer = handler;
	auto wrong_field = mechanics;
	for (auto &connection : wrong_field)
		if (connection.id == MechanicId::specialization_load)
			connection.binding = player_status_field::class_primary;
	assert(!validate_transitions(transitions, wrong_field).empty());
	assert(!validate_transitions({}, mechanics).empty());
	std::vector<TransitionConnection> duplicate{ transitions.front(), transitions.front() };
	assert(!validate_transitions(duplicate, mechanics).empty());

	// Explicit room, NPC teacher and skill cells exercise the real registered
	// handler/refresh. The separate world journey proves loaded teacher/grants,
	// interpreter guards and persistent skill rows.
	room_data room{};
	char_data student{}, teacher{};
	pc_only_data pc{};
	student.only.pc = &pc;
	student.player.name = const_cast<char *>("NativeStudent");
	student.player.race = RACE_HUMAN;
	student.player.m_class = CLASS_WARRIOR;
	student.player.level = 30;
	GET_EXP(&student) = 12345;
	pc.epics = 17;
	GET_COPPER(&student) = 2;
	GET_SILVER(&student) = 3;
	GET_GOLD(&student) = 4;
	GET_PLATINUM(&student) = 5;
	student.in_room = 0;
	teacher.specials.act = ACT_ISNPC | ACT_SPEC_TEACHER;
	teacher.player.m_class = CLASS_WARRIOR;
	room.people = &teacher;
	P_room saved_world = world;
	world = &room;
	auto &grant = skills[SKILL_GUARD].m_class[flag2idx(CLASS_WARRIOR) - 1];
	grant.rlevel[SPEC_GUARDIAN] = 30;
	grant.maxlearn[SPEC_GUARDIAN] = 100;
	char argument[] = "guardian";
	pc.time_unspecced = time(nullptr) + 3600;
	handler(&student, argument, CMD_SPECIALIZE);
	assert(student.player.spec == 0 && pc.skills[SKILL_GUARD].learned == 0);
	pc.time_unspecced = time(nullptr) - 1;
	handler(&student, argument, CMD_SPECIALIZE);
	assert(student.player.spec == SPEC_GUARDIAN);
	assert(pc.skills[SKILL_GUARD].learned == 40 && pc.skills[SKILL_GUARD].taught == 100);
	assert(student.player.m_class == CLASS_WARRIOR && student.player.secondary_class == 0);
	assert(student.player.race == RACE_HUMAN && student.player.level == 30);
	assert(GET_EXP(&student) == 12345 && pc.epics == 17);
	assert(GET_COPPER(&student) == 2 && GET_SILVER(&student) == 3 && GET_GOLD(&student) == 4 &&
	       GET_PLATINUM(&student) == 5);
	world = saved_world;
	std::puts(
		"specialization.transition: PASS (native command registration, timer denial, assignment and skill refresh; missing registration/load/transition rejected)");
}

static void unspecialization_transition()
{
	const auto mechanics = mechanic_connections();
	const auto transitions = transition_connections();
	assert(transitions[1].entries.size() == 2);
	for (int slot : { 1, 2 })
	{
		for (const auto &connection : mechanics)
			if (connection.id == MechanicId::unspecialization_value)
			{
				const auto value = std::get<ObjectProcValue>(connection.binding);
				assert(value(obj_index[slot].func.obj) == -100000);
			}
		const auto handler = obj_index[slot].func.obj;
		obj_index[slot].func.obj = nullptr;
		assert(!validate_mechanics(mechanics).empty());
		assert(!validate_transitions(transitions, mechanics).empty());
		obj_index[slot].func.obj = handler;
	}
	// A legacy missing-vnum assignment can land at prototype zero. Even with
	// the right handler there, it must not validate as the requested altar.
	obj_index[0].func.obj = obj_index[1].func.obj;
	obj_index[1].virtual_number = 2202;
	assert(!validate_transitions(transitions, mechanics).empty());
	obj_index[1].virtual_number = 2203;
	auto disconnected = mechanics;
	for (auto &connection : disconnected)
		if (connection.id == MechanicId::unspecialization_purchase)
			connection.dependencies = {};
	assert(!validate_transitions(transitions, disconnected).empty());

	char_data student{};
	pc_only_data pc{};
	obj_data altar{};
	student.only.pc = &pc;
	student.player.m_class = CLASS_WARRIOR;
	student.player.race = RACE_HUMAN;
	student.player.level = 30;
	SET_POS(&student, STAT_NORMAL + POS_STANDING);
	GET_EXP(&student) = 23456;
	GET_COPPER(&student) = 7;
	GET_SILVER(&student) = 8;
	GET_GOLD(&student) = 9;
	GET_PLATINUM(&student) = 10;
	pc.pid = 42;
	char prayer[] = "altar";
	for (int slot : { 1, 2 })
	{
		student.player.spec = SPEC_GUARDIAN;
		pc.epics = 12;
		pc.skills[SKILL_GUARD] = { 40, 100 };
		affected_type unrelated{};
		unrelated.type = SPELL_BLESS;
		auto *full = new affected_type{};
		full->type = TAG_MEMORIZE;
		full->flags = MEMTYPE_FULL;
		full->next = &unrelated;
		auto *pending = new affected_type{};
		pending->type = TAG_MEMORIZE;
		pending->next = full;
		student.affected = pending;
		mechanic_removed_affects = mechanic_stop_memorizing = mechanic_ledger_calls = 0;
		const auto handler = obj_index[slot].func.obj;
		assert(handler(&altar, &student, CMD_LOOK, prayer) == FALSE);
		assert(student.player.spec == SPEC_GUARDIAN && pc.epics == 12);
		assert(handler(&altar, &student, CMD_PRAY, prayer) == TRUE);
		assert(student.player.spec == 0 && pc.epics == 2);
		assert(student.player.m_class == CLASS_WARRIOR &&
		       student.player.secondary_class == 0);
		assert(student.player.race == RACE_HUMAN && student.player.level == 30);
		assert(GET_EXP(&student) == 23456 && GET_COPPER(&student) == 7 &&
		       GET_SILVER(&student) == 8 && GET_GOLD(&student) == 9 &&
		       GET_PLATINUM(&student) == 10);
		assert(pc.skills[SKILL_GUARD].learned == 0 && pc.skills[SKILL_GUARD].taught == 0);
		assert(mechanic_removed_affects == 2 && mechanic_stop_memorizing == 1);
		assert(student.affected == &unrelated && mechanic_ledger_calls == 1);
		assert(handler(&altar, &student, CMD_PRAY, prayer) == TRUE);
		assert(pc.epics == 2 && mechanic_ledger_calls == 1);
		student.affected = nullptr;
	}
	std::puts(
		"unspecialization.transition: PASS (both actual object assignments, native prayer/purchase/completion/refresh/forget selection; missing slots/vnum/path rejected; affect removal and ledger are fixture boundaries)");
}

static void skill_class_mask_bounds()
{
	// Explicit skill fixture; this checks class-index safety, not registration
	// completeness or the ordinary acquisition of this fixture skill.
	char_data ch{};
	ch.player.name = const_cast<char *>("Maskfixture");
	ch.player.m_class = CLASS_WARRIOR;
	auto &primary = skills[SKILL_GUARD].m_class[flag2idx(CLASS_WARRIOR) - 1];
	auto &secondary = skills[SKILL_GUARD].m_class[flag2idx(CLASS_CLERIC) - 1];
	primary.rlevel[0] = 20;
	primary.maxlearn[0] = 80;
	secondary.rlevel[0] = 30;
	secondary.maxlearn[0] = 70;
	auto check = [&](int level, int cap)
	{
		const auto data = SKILL_DATA_ALL(&ch, SKILL_GUARD);
		assert(data.rlevel[0] == level && data.maxlearn[0] == cap);
	};
	check(20, 80);
	ch.player.secondary_class = BIT_32; // Existing non-multiclass sentinel.
	check(20, 80);
	ch.player.secondary_class = CLASS_CLERIC;
	check(20, 80);
	ch.player.m_class = CLASS_NONE;
	check(20, 80);
	assert(ch.player.m_class == CLASS_WARRIOR);
	ch.player.m_class = BIT_32;
	check(20, 80);
	assert(ch.player.m_class == CLASS_WARRIOR);
	ch.specials.act = ACT_ISNPC;
	ch.specials.affected_by4 = AFF4_MULTI_CLASS;
	ch.player.secondary_class = 0;
	ch.player.m_class = CLASS_WARRIOR | CLASS_CLERIC;
	check(20, 80);
	ch.player.m_class = BIT_32 | CLASS_CLERIC;
	check(30, 70);
	assert(ch.player.m_class == (BIT_32 | CLASS_CLERIC));
	std::puts(
		"skill.class-mask: PASS (legacy secondary sentinel, primary normalization and NPC class masks)");
}

static void guardian_bulwark()
{
	load_character_properties();
	assign_innates();
	const auto mechanics = mechanic_connections();
	const auto errors = validate_mechanics(mechanics);
	for (const auto &error : errors)
		std::fprintf(stderr, "%s\n", error.c_str());
	assert(errors.empty());
	for (const auto &connection : mechanics)
	{
		const auto name = mechanic_name(connection.id);
		const bool callable = std::visit(
			[](auto binding)
			{
				return std::is_pointer_v<decltype(binding)> &&
				       std::is_function_v<std::remove_pointer_t<decltype(binding)>>;
			},
			connection.binding);
		std::printf("CONNECTION\t%.*s\t%.*s\t%s\t%s\t%u\n", int(name.size()), name.data(),
			    int(connection.symbol.size()), connection.symbol.data(),
			    callable ? "callable" : "value", connection.declared_at.file_name(),
			    connection.declared_at.line());
		for (auto dependency : connection.dependencies)
		{
			const auto target = mechanic_name(dependency);
			std::printf("DEPENDENCY\t%.*s\t%.*s\n", int(name.size()), name.data(),
				    int(target.size()), target.data());
		}
		if (connection.id == MechanicId::guardian_bulwark_grant)
			assert(*std::get<const char *>(connection.binding) == 41);
		if (connection.id == MechanicId::guardian_bulwark_factor)
			assert(*std::get<const float *>(connection.binding) == 0.85f);
		if (connection.id == MechanicId::guardian_bulwark_callback)
		{
			const auto *row = std::get<const innate_data *>(connection.binding);
			assert(!strcmp(row->name, "bulwark") && row->func == nullptr);
		}
	}
	auto missing_effect = mechanics;
	missing_effect.pop_back();
	assert(!validate_mechanics(missing_effect).empty());
	auto conflicting = mechanics;
	conflicting.push_back(mechanics.front());
	assert(!validate_mechanics(conflicting).empty());
	auto wrong_type = mechanics;
	wrong_type.front().binding = static_cast<const char *>(nullptr);
	assert(!validate_mechanics(wrong_type).empty());
	auto no_passive_consumer = mechanics;
	for (auto &connection : no_passive_consumer)
		if (connection.id == MechanicId::guardian_bulwark_callback)
			connection.dependencies = {};
	assert(!validate_mechanics(no_passive_consumer).empty());
	char_data attacker{}, victim{};
	obj_data shield{};
	SET_POS(&attacker, STAT_NORMAL + POS_STANDING);
	SET_POS(&victim, STAT_NORMAL + POS_STANDING);
	attacker.player.race = victim.player.race = RACE_HUMAN;
	attacker.player.m_class = victim.player.m_class = CLASS_WARRIOR;
	attacker.player.level = victim.player.level = 41;
	victim.player.spec = SPEC_GUARDIAN;
	victim.equipment[WEAR_SHIELD] = &shield;
	assert(has_innate(&victim, INNATE_GUARDIANS_BULWARK));
	char innate_args[] = "bulwark";
	const auto innate_command = cmd_info[CMD_INNATE].command_pointer;
	assert(innate_command == do_innate);
	mechanic_output.clear();
	innate_command(&victim, innate_args, CMD_INNATE);
	assert(mechanic_output == "This innate is always active.\n");
	assert(!victim.affected);
	assert(bulwark_melee(&attacker, &victim) == 850);
	assert(bulwark_melee(&attacker, &victim, true) == 1000);
	victim.player.level = 40;
	mechanic_output.clear();
	innate_command(&victim, innate_args, CMD_INNATE);
	assert(mechanic_output == "You know no such ability!\n");
	char list_args[] = "";
	mechanic_output.clear();
	innate_command(&victim, list_args, CMD_INNATE);
	assert(mechanic_output.find("*bulwark (unlocks at level 41)") != std::string::npos);
	assert(!has_innate(&victim, INNATE_GUARDIANS_BULWARK));
	assert(bulwark_melee(&attacker, &victim) == 1000);
	victim.player.level = 41;
	victim.equipment[WEAR_SHIELD] = nullptr;
	assert(has_innate(&victim, INNATE_GUARDIANS_BULWARK));
	assert(bulwark_melee(&attacker, &victim) == 1000);
	victim.equipment[WEAR_SHIELD] = &shield;
	victim.player.spec = SPEC_SWORDSMAN;
	assert(!has_innate(&victim, INNATE_GUARDIANS_BULWARK));
	assert(bulwark_melee(&attacker, &victim) == 1000);
	victim.player.spec = 0;
	victim.player.secondary_class = CLASS_CLERIC;
	assert(!has_innate(&victim, INNATE_GUARDIANS_BULWARK));
	assert(bulwark_melee(&attacker, &victim) == 1000);
	// The shared slot number on another class is not Guardian ownership.
	victim.player.m_class = CLASS_CLERIC;
	victim.player.secondary_class = CLASS_WARRIOR;
	victim.player.spec = SPEC_GUARDIAN;
	assert(!has_innate(&victim, INNATE_GUARDIANS_BULWARK));
	assert(bulwark_melee(&attacker, &victim) == 1000);
	victim.player.m_class = CLASS_WARRIOR;
	victim.player.secondary_class = 0;
	set_character_property("damage.reduction.guardians.bulwark", 0.5f);
	assert(bulwark_melee(&attacker, &victim) == 500);
	clear_character_properties();
	update_dam_factors();
	assert(bulwark_melee(&attacker, &victim) == 850);
	std::puts(
		"guardian.bulwark: PASS (real grants, eligibility, property loading and melee reduction; raw damage is a fixture boundary)");
}

static void expect_diagnostic(const IdentityConnections &connections, const char *expected)
{
	for (const auto &error : validate_identities(connections))
		if (error.find(expected) != std::string::npos)
			return;
	std::fprintf(stderr, "Missing diagnostic: %s\n", expected);
	std::abort();
}

extern int mechanic_login_selection, mechanic_json_selection, mechanic_json_fallback;

static void creation_bindings()
{
	auto mechanics = mechanic_connections();
	descriptor_data descriptor{};
	char argument[] = "";
	int login_entries = 0, json_entries = 0;
	for (const auto &connection : mechanics)
	{
		if (const auto *rules = std::get_if<CreationRules>(&connection.binding))
		{
			assert((*rules)->race_enabled == creation_race_enabled);
			assert((*rules)->class_alignment(RACE_HUMAN, flag2idx(CLASS_NECROMANCER)) ==
			       -1);
		}
		if (const auto *login = std::get_if<LoginRegistration>(&connection.binding))
		{
			++login_entries;
			mechanic_login_selection = 0;
			login->selection(&descriptor, argument);
			const auto expected = mechanic_login_selection;
			assert(expected);
			mechanic_login_selection = 0;
			descriptor.connected = login->state;
			login->dispatcher(&descriptor, argument);
			assert(mechanic_login_selection == expected);
			auto missing = mechanics;
			for (auto &changed : missing)
				if (changed.id == connection.id)
					std::get<LoginRegistration>(changed.binding).selection =
						nullptr;
			assert(!validate_mechanics(missing).empty());
		}
		if (const auto *json = std::get_if<JsonRegistration>(&connection.binding))
		{
			++json_entries;
			assert(!json->lookup("__not_registered__") && !json->lookup(nullptr));
			mechanic_json_selection = 0;
			descriptor.writer_wait_id = 1;
			json->dispatcher(&descriptor, json->command, nullptr);
			assert(!mechanic_json_selection);
			descriptor.writer_wait_id = 0;
			json->dispatcher(&descriptor, json->command, nullptr);
			assert(mechanic_json_selection);
			const auto expected = mechanic_json_selection;
			mechanic_json_selection = 0;
			json->lookup(json->command)(&descriptor, nullptr);
			assert(mechanic_json_selection == expected);
			auto missing = mechanics;
			for (auto &changed : missing)
				if (changed.id == connection.id)
					std::get<JsonRegistration>(changed.binding).command =
						"__not_registered__";
			assert(!validate_mechanics(missing).empty());
			std::vector<JsonHandler> aliases(json->handlers.begin(),
							 json->handlers.end());
			aliases.push_back(
				{ "__new_creation_alias__", json->lookup(json->command) });
			auto aliased = mechanics;
			for (auto &changed : aliased)
				if (auto *entry = std::get_if<JsonRegistration>(&changed.binding))
					entry->handlers = aliases;
			const auto alias_errors = validate_mechanics(aliased);
			assert(std::any_of(
				alias_errors.begin(), alias_errors.end(),
				[](const auto &error) {
					return error.find(
						       "unregistered JSON alias __new_creation_alias__") !=
					       std::string::npos;
				}));
			descriptor.connected = CON_PLAYING;
			const int before = mechanic_json_fallback;
			json->dispatcher(&descriptor, nullptr, nullptr);
			assert(mechanic_json_fallback == before);
			json->dispatcher(&descriptor, "__not_registered__", nullptr);
			assert(mechanic_json_fallback == before + 1);
		}
	}
	assert(login_entries == 3 && json_entries == 2);
	std::puts(
		"creation.bindings: PASS (actual login case excerpts, JSON table/dispatcher, missing slots and writer fence; selection/creation bodies and earlier login guards are separate world evidence)");
}

static void ability_registration()
{
	initialize_skills();
	assign_innates();
	auto mechanics = mechanic_connections();
	const auto errors = validate_grants(mechanics);
	// Preserve the existing last-write result while requiring its precise
	// diagnostic. Any additional conflict or loss of this gap fails the test.
	std::vector<GrantWrite> writes;
	for (const auto &connection : mechanics)
		if (connection.id == MechanicId::skill_registration)
		{
			const auto rows = std::get<GrantWrites>(connection.binding);
			writes.assign(rows.begin(), rows.end());
			assert(connection.implementation == Implementation::incomplete &&
			       !connection.gap.empty());
		}
	const GrantWrite *specific = nullptr, *last = nullptr;
	for (const auto &write : writes)
		if (write.ability == SKILL_BLINDFIGHTING && write.owner.primary == CLASS_ROGUE &&
		    write.owner.kind == OptionKind::specialization &&
		    write.owner.secondary == SPEC_ASSASSIN)
		{
			if (write.replaces)
				specific = &write;
			else
				last = &write;
		}
	assert(specific && last && specific->level == 1 && specific->cap == 100 &&
	       last->level == 1 && last->cap == 90 &&
	       last->declared_at.line() > specific->declared_at.line());
	const auto known = std::string(last->declared_at.file_name()) + ":" +
			   std::to_string(last->declared_at.line()) +
			   ": conflicting registration without explicit precedence ability " +
			   std::to_string(SKILL_BLINDFIGHTING);
	for (const auto &error : errors)
		std::fprintf(stderr, "%s\n", error.c_str());
	assert(errors == std::vector<std::string>{ known });
	size_t skill_writes = 0, innate_writes = 0;
	std::set<std::tuple<std::string, unsigned int, unsigned int>> sites;
	for (const auto &connection : mechanics)
		if (const auto *writes = std::get_if<GrantWrites>(&connection.binding))
		{
			if (connection.id == MechanicId::skill_registration)
				skill_writes = writes->size();
			else
				innate_writes = writes->size();
			for (const auto &write : *writes)
			{
				sites.emplace(write.declared_at.file_name(),
					      write.declared_at.line(), write.declared_at.column());
				assert(write.declared_at.line() > 0);
				assert(std::strstr(write.declared_at.file_name(), "src/classes/"));
			}
		}
	for (const auto &[file, line, column] : sites)
		std::printf("GRANT_SITE\t%s\t%u\t%u\n", file.c_str(), line, column);
	assert(skill_writes > 1000 && innate_writes > 100);
	assert(skills[SPELL_DRACONIC_APOTHEOSIS].spell_pointer != nullptr);
	assert(skills[SPELL_DRACONIC_APOTHEOSIS].m_class[flag2idx(CLASS_DRAGOON) - 1].rlevel[0] ==
	       12);
	const auto before =
		skills[SKILL_GUARD].m_class[flag2idx(CLASS_WARRIOR) - 1].rlevel[SPEC_GUARDIAN];
	++skills[SKILL_GUARD].m_class[flag2idx(CLASS_WARRIOR) - 1].rlevel[SPEC_GUARDIAN];
	assert(validate_grants(mechanics).size() > errors.size());
	skills[SKILL_GUARD].m_class[flag2idx(CLASS_WARRIOR) - 1].rlevel[SPEC_GUARDIAN] = before;
	auto missing = mechanics;
	for (auto &connection : missing)
		if (connection.id == MechanicId::skill_registration)
			connection.binding = GrantWrites{};
	assert(validate_grants(missing).size() > errors.size());
	assert(validate_grants({}).size() == 4);
	// An incompatible specific write must fail even when the final table agrees
	// with the overwrite: final-table inspection alone cannot detect this.
	const auto specific_write =
		std::find_if(writes.begin(), writes.end(),
			     [](const auto &write)
			     {
				     return write.ability == SKILL_GUARD &&
					    write.owner.primary == CLASS_WARRIOR &&
					    write.owner.secondary == SPEC_GUARDIAN &&
					    write.replaces;
			     });
	assert(specific_write != writes.end());
	auto conflicting = *specific_write;
	++conflicting.level;
	writes.push_back(conflicting);
	++skills[SKILL_GUARD].m_class[flag2idx(CLASS_WARRIOR) - 1].rlevel[SPEC_GUARDIAN];
	for (auto &connection : missing)
		if (connection.id == MechanicId::skill_registration)
			connection.binding = GrantWrites(writes);
	const auto conflicts = validate_grants(missing);
	assert(conflicts.size() == errors.size() + 1);
	assert(conflicts.back().find("conflicting registration") != std::string::npos);
	skills[SKILL_GUARD].m_class[flag2idx(CLASS_WARRIOR) - 1].rlevel[SPEC_GUARDIAN] = before;

	std::printf(
		"ability.registration: PASS (%zu skill/definition writes, %zu innate grants; native tables, changed/missing provenance and one exact existing conflict checked; callback execution is separate)\n",
		skill_writes, innate_writes);
}

int main()
{
	ability_registration();
	specialization_transition();
	creation_bindings();
	guardian_bulwark();
	unspecialization_transition();
	skill_class_mask_bounds();
	multiclass_denials();
	multiclass_reset_and_consumers();
	revenant_transition();
	race_and_death_cleanup();
	assert(!creation_all_races_enabled() && !creation_all_classes_enabled());
	assert(!strcmp(getenv("CHAOS_MUD"), "FALSE"));
	const auto connections = identity_connections();
	const auto errors = validate_identities(connections);
	for (const auto &error : errors)
		std::fprintf(stderr, "%s\n", error.c_str());
	assert(errors.empty());
	assert(connections.race_enabled == creation_race_enabled);
	assert(connections.class_enabled == creation_class_enabled);
	assert(connections.class_alignment == creation_class_align);
	assert(connections.class_normally_available == creation_class_normally_available);
	assert(connections.specialization_allowed == is_allowed_race_spec);
	assert(connections.secondary_allowed == can_char_multi_to_class);

	// Identity is independent of acquisition: forms outside the player range,
	// empty legacy class slots, and Rogue Assassin are all retained.
	assert(!strcmp(connections.races[RACE_AGATHINON].normal, "Agathinon"));
	assert(!strcmp(connections.races[RACE_ELADRIN].normal, "Eladrin"));
	assert(!strcmp(connections.races[RACE_DRAGONKIN].normal, "Dragonkin"));
	assert(!strcmp(connections.classes[flag2idx(CLASS_ASSASSIN)].normal, "Assassin"));
	assert(!*connections.specializations[flag2idx(CLASS_ASSASSIN)][0]);
	assert(*connections.specializations[flag2idx(CLASS_ROGUE)][SPEC_ASSASSIN - 1]);
	assert(!strcmp(connections.specializations[flag2idx(CLASS_ROGUE)][2], "Not Used"));

	// Exhaustive table/predicate binding checks; these are not independent
	// behavioral oracles for all choices or transport-specific admission.
	for (int race = RACE_NONE; race <= LAST_RACE; ++race)
		for (int cls = 1; cls <= CLASS_COUNT; ++cls)
			assert(connections.class_alignment(race, cls) ==
			       connections.race_classes[race][cls]);
	for (const auto &row : connections.race_specializations)
		if (row.spec)
			assert(connections.specialization_allowed(row.race, row.m_class, row.spec));
		else
			for (int slot = 1; slot <= MAX_SPEC; ++slot)
				assert(connections.specialization_allowed(row.race, row.m_class,
									  slot));

	// Named policy assertions against checked-in normal configuration.
	assert(connections.class_enabled(flag2idx(CLASS_WARRIOR)));
	assert(!connections.class_enabled(flag2idx(CLASS_DRAGOON)));
	assert(connections.class_alignment(RACE_HUMAN, flag2idx(CLASS_WARRIOR)) == 2);
	assert(connections.class_alignment(RACE_HUMAN, flag2idx(CLASS_NECROMANCER)) == -1);
	assert(connections.class_alignment(RACE_LICH, flag2idx(CLASS_NECROMANCER)) == 5);
	assert(connections.specialization_allowed(RACE_HUMAN, CLASS_WARRIOR, SPEC_GUARDIAN));
	assert(!connections.specialization_allowed(RACE_THRIKREEN, CLASS_WARRIOR, SPEC_GUARDIAN));
	char_data ch{};
	for (int race : { RACE_HUMAN, RACE_ORC })
	{
		ch.player.race = race;
		ch.player.m_class = CLASS_WARRIOR;
		assert(connections.secondary_allowed(&ch, flag2idx(CLASS_CLERIC)));
		assert(connections.secondary_allowed(&ch, flag2idx(CLASS_MERCENARY)));
		assert(!connections.secondary_allowed(&ch, flag2idx(CLASS_SORCERER)));
	}
	ch.player.race = RACE_HUMAN;
	ch.player.m_class = CLASS_RANGER;
	assert(connections.secondary_allowed(&ch, flag2idx(CLASS_WARRIOR)));
	ch.player.m_class = CLASS_WARRIOR;
	assert(!connections.secondary_allowed(&ch, flag2idx(CLASS_RANGER)));

	setenv("CREATION_ALL_RACES", "TRUE", 1);
	assert(connections.class_alignment(RACE_LICH, flag2idx(CLASS_NECROMANCER)) == -1);
	setenv("CREATION_ALL_CLASSES", "TRUE", 1);
	assert(connections.class_enabled(flag2idx(CLASS_DRAGOON)));
	assert(connections.class_alignment(RACE_HUMAN, flag2idx(CLASS_ASSASSIN)) == 2);
	assert(connections.specialization_allowed(RACE_THRIKREEN, CLASS_WARRIOR, SPEC_GUARDIAN));
	setenv("CREATION_ALL_RACES", "FALSE", 1);
	setenv("CREATION_ALL_CLASSES", "FALSE", 1);

	// Mutate copies of the read-only views, never the production tables.
	auto broken = connections;
	broken.races = broken.races.first(broken.races.size() - 1);
	expect_diagnostic(broken, "race definitions disagree");
	broken = connections;
	broken.classes = broken.classes.first(broken.classes.size() - 1);
	expect_diagnostic(broken, "class definitions disagree");
	broken = connections;
	broken.specializations = broken.specializations.first(broken.specializations.size() - 1);
	expect_diagnostic(broken, "specialization class rows missing");
	broken = connections;
	broken.specialization_allowed = nullptr;
	expect_diagnostic(broken, "predicate binding missing");
	broken = connections;
	broken.creation_roster = broken.creation_roster.subspan(1);
	expect_diagnostic(broken, "creation classification for race 1");
	std::vector<playable_race_info> duplicate(connections.creation_roster.begin(),
						  connections.creation_roster.end());
	duplicate.insert(duplicate.begin(), duplicate.front());
	broken = connections;
	broken.creation_roster = duplicate;
	expect_diagnostic(broken, "creation classification for race 1");
	broken = connections;
	broken.creation_roster = broken.creation_roster.first(broken.creation_roster.size() - 1);
	expect_diagnostic(broken, "creation roster sentinel missing");
	broken = connections;
	broken.race_specializations = {};
	expect_diagnostic(broken, "specialization allowance table missing");
	allowed_race_spec_struct invalid_allowance{ RACE_HUMAN, CLASS_WARRIOR | CLASS_CLERIC, 1 };
	broken = connections;
	broken.race_specializations = { &invalid_allowance, 1 };
	expect_diagnostic(broken, "invalid specialization class mask");
	invalid_allowance.m_class = CLASS_WARRIOR;
	invalid_allowance.spec = MAX_SPEC + 1;
	expect_diagnostic(broken, "invalid specialization slot");
	SecondaryClasses unterminated{ CLASS_WARRIOR, CLASS_CLERIC, CLASS_BARD, CLASS_ROGUE,
				       CLASS_DRUID };
	// Replace a single real row while retaining the complete table dimensions.
	SecondaryClasses secondaries[CLASS_COUNT + 1];
	std::memcpy(secondaries, connections.secondary_classes.data(), sizeof(secondaries));
	std::memcpy(secondaries[1], unterminated, sizeof(unterminated));
	broken = connections;
	broken.secondary_classes = secondaries;
	expect_diagnostic(broken, "unterminated secondary-class row 1");

	std::printf("identity.tables: PASS (%zu races including None, %zu classes including None, "
		    "%zu specialization rows including unused slots)\n",
		    connections.races.size() - 1, connections.classes.size() - 1,
		    connections.specializations.size());
	std::puts(
		"identity.bindings: PASS (production table/predicate bindings and malformed-view diagnostics)");
	std::puts(
		"eligibility.examples: PASS (normal configuration, overrides, ordered pairs; predicate scope only)");
	std::puts(
		"UNVERIFIED HERE: full interpreter/world/persistence (separate journey), raw HP/death, other effects/transitions and remaining reverse coverage");
}
