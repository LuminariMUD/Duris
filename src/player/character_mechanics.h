#ifndef CHARACTER_MECHANICS_H
#define CHARACTER_MECHANICS_H

#include "core/defines.h"

#include <span>
#include <string>
#include <vector>

struct char_data;
struct allowed_race_spec_struct;

namespace character_mechanics
{
using SpecializationNames = const char *[MAX_SPEC];
using ClassRow = int[CLASS_COUNT + 1];
using SecondaryClasses = int[5];

// Views of the production definitions, including None, unused spec slots and
// table sentinels. Keeping sentinels visible lets validation detect their removal.
// Class rows use table indices; allowance rows use CLASS_* bit masks. A spec's
// identity is (class, slot), where slot 0 is unspecialized and names[slot - 1]
// supplies slots 1..MAX_SPEC. Ordered multiclass pairs retain primary/secondary.
// These views describe definitions and predicates, never overall reachability.
struct IdentityConnections
{
	std::span<const race_names> races;
	std::span<const class_names> classes;
	std::span<const SpecializationNames> specializations;
	std::span<const playable_race_info> creation_roster;
	std::span<const restricted_race_info> restricted_roster;
	std::span<const ClassRow> race_classes;
	std::span<const restricted_class_row> restricted_classes;
	std::span<const SecondaryClasses> secondary_classes;
	std::span<const allowed_race_spec_struct> race_specializations;

	bool (*race_enabled)(int) = nullptr;
	bool (*class_enabled)(int) = nullptr;
	int (*class_alignment)(int, int) = nullptr;
	bool (*class_normally_available)(int, int) = nullptr;
	bool (*specialization_allowed)(int, unsigned int, int) = nullptr;
	bool (*secondary_allowed)(char_data *, int) = nullptr;
};

// Explicit providers live beside the tables/predicates they bind. No static
// constructors, gameplay dispatcher, copied eligibility rules or saved state.
void connect_identity_names(IdentityConnections &connections);
void connect_identity_tables(IdentityConnections &connections);
void connect_creation_predicates(IdentityConnections &connections);
void connect_specialization_predicate(IdentityConnections &connections);
void connect_multiclass_predicate(IdentityConnections &connections);
IdentityConnections identity_connections();

// Structural diagnostics only. Successful validation proves neither a command
// route nor its effect/lifecycle, and carries no editable "verified" flag.
std::vector<std::string> validate_identities(const IdentityConnections &connections);
} // namespace character_mechanics

#endif
