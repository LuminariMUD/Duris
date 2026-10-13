#include "core/prototypes.h"
#include "player/character_mechanics.h"
#include "classes/specializations.h"

#include <algorithm>
#include <bit>
#include <cstring>

namespace character_mechanics
{
IdentityConnections identity_connections()
{
	IdentityConnections connections;
	connect_identity_names(connections);
	connect_identity_tables(connections);
	connect_creation_predicates(connections);
	connect_specialization_predicate(connections);
	connect_multiclass_predicate(connections);
	return connections;
}

std::vector<std::string> validate_identities(const IdentityConnections &c)
{
	std::vector<std::string> errors;
	auto require = [&](bool condition, const std::string &message)
	{
		if (!condition)
			errors.push_back(message);
	};
	require(c.races.size() == LAST_RACE + 2, "race definitions disagree with LAST_RACE");
	require(c.classes.size() == CLASS_COUNT + 2, "class definitions disagree with CLASS_COUNT");
	require(c.specializations.size() == CLASS_COUNT + 1, "specialization class rows missing");
	require(c.race_classes.size() == LAST_RACE + 1, "race/class rows missing");
	require(c.secondary_classes.size() == CLASS_COUNT + 1, "secondary-class rows missing");
	require(!c.creation_roster.empty() && c.creation_roster.back().race_id == -1,
		"creation roster sentinel missing");
	require(!c.restricted_roster.empty() && c.restricted_roster.back().race_id == -1,
		"restricted roster sentinel missing");
	require(!c.restricted_classes.empty() && c.restricted_classes.back().race_id == -1,
		"restricted class sentinel missing");
	require(!c.race_specializations.empty(), "specialization allowance table missing");
	require(c.race_enabled && c.class_enabled && c.class_alignment &&
			c.class_normally_available && c.specialization_allowed &&
			c.secondary_allowed,
		"eligibility predicate binding missing");
	if (!errors.empty())
		return errors;
	require(c.races.back().normal == nullptr, "race name sentinel missing");
	require(c.classes.back().normal == nullptr, "class name sentinel missing");

	for (size_t race = 0; race <= LAST_RACE; ++race)
		require(c.races[race].normal && *c.races[race].normal,
			"unnamed race " + std::to_string(race));
	for (size_t cls = 0; cls <= CLASS_COUNT; ++cls)
		require(c.classes[cls].normal && *c.classes[cls].normal,
			"unnamed class " + std::to_string(cls));
	for (size_t cls = 0; cls < c.specializations.size(); ++cls)
		for (int slot = 0; slot < MAX_SPEC; ++slot)
			require(c.specializations[cls][slot] != nullptr,
				"unclassified specialization " + std::to_string(cls) + "/" +
					std::to_string(slot + 1));

	std::vector<int> roster_memberships(c.races.size());
	for (const auto &race : c.creation_roster.first(c.creation_roster.size() - 1))
	{
		bool valid = race.race_id > RACE_NONE && race.race_id <= RACE_PLAYER_MAX &&
			     size_t(race.race_id) < c.races.size();
		require(valid, "invalid creation race " + std::to_string(race.race_id));
		if (valid)
			++roster_memberships[race.race_id];
		require(race.select_key != 0 && race.faction &&
				(!strcmp(race.faction, "good") || !strcmp(race.faction, "evil") ||
				 !strcmp(race.faction, "neutral")),
			"creation race lacks key/faction " + std::to_string(race.race_id));
	}
	for (const auto &race : c.restricted_roster.first(c.restricted_roster.size() - 1))
	{
		bool valid = race.race_id > RACE_NONE && race.race_id <= RACE_PLAYER_MAX &&
			     size_t(race.race_id) < c.races.size();
		require(valid, "invalid restricted race " + std::to_string(race.race_id));
		if (valid)
			++roster_memberships[race.race_id];
		require(race.note && *race.note,
			"restricted race lacks reason " + std::to_string(race.race_id));
	}
	for (size_t race = 1; race < c.races.size() && race <= RACE_PLAYER_MAX; ++race)
		require(roster_memberships[race] == 1,
			"missing/conflicting creation classification for race " +
				std::to_string(race));
	for (size_t race = 0; race < c.race_classes.size(); ++race)
		for (int align : c.race_classes[race])
			require(align >= -1 && align <= 5,
				"invalid alignment code for race " + std::to_string(race));
	std::vector<int> restricted_rows(c.races.size());
	for (const auto &row : c.restricted_classes.first(c.restricted_classes.size() - 1))
	{
		bool valid = row.race_id > RACE_NONE && row.race_id <= RACE_PLAYER_MAX;
		require(valid, "invalid restricted class race " + std::to_string(row.race_id));
		if (valid)
			require(++restricted_rows[row.race_id] == 1,
				"duplicate restricted class race " + std::to_string(row.race_id));
		for (int align : row.align)
			require(align >= -1 && align <= 5, "invalid restricted alignment code");
	}

	auto valid_class = [&](unsigned int mask)
	{ return std::has_single_bit(mask) && std::countr_zero(mask) < CLASS_COUNT; };
	for (size_t cls = 0; cls < c.secondary_classes.size(); ++cls)
	{
		const auto &row = c.secondary_classes[cls];
		auto end = std::find(std::begin(row), std::end(row), -1);
		require(end != std::end(row),
			"unterminated secondary-class row " + std::to_string(cls));
		for (auto entry = std::begin(row); entry != end; ++entry)
		{
			require(valid_class(*entry),
				"invalid secondary class in row " + std::to_string(cls));
			require(std::find(std::begin(row), entry, *entry) == entry,
				"duplicate secondary class in row " + std::to_string(cls));
		}
	}
	for (const auto &row : c.race_specializations)
	{
		require(row.race > RACE_NONE && row.race <= LAST_RACE,
			"invalid specialization race " + std::to_string(row.race));
		require(valid_class(row.m_class), "invalid specialization class mask");
		// Slot zero is the production table's wildcard, not a named spec.
		require(row.spec >= 0 && row.spec <= MAX_SPEC, "invalid specialization slot");
	}
	return errors;
}
} // namespace character_mechanics
