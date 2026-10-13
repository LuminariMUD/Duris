#include "core/prototypes.h"
#include "core/utils.h"
#include "account/creation_availability_config.h"
#include "classes/specializations.h"
#include "player/character_mechanics.h"
#include "combat/damage.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

using namespace character_mechanics;

void load_character_properties();
void set_bulwark_property(float value);
void clear_character_properties();
void update_dam_factors();
double bulwark_melee(P_char attacker, P_char victim, bool bypass = false);

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
		std::printf("CONNECTION\t%.*s\t%.*s\t%s\t%u\n", int(name.size()), name.data(),
			    int(connection.symbol.size()), connection.symbol.data(),
			    connection.declared_at.file_name(), connection.declared_at.line());
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
	assert(bulwark_melee(&attacker, &victim) == 850);
	assert(bulwark_melee(&attacker, &victim, true) == 1000);
	victim.player.level = 40;
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
	set_bulwark_property(0.5f);
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

int main()
{
	guardian_bulwark();
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
		"UNVERIFIED: entry commands, raw HP/death, other effects, transitions, persistence and remaining reverse coverage");
}
