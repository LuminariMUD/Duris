#ifndef CHARACTER_MECHANICS_H
#define CHARACTER_MECHANICS_H

#include "core/defines.h"
#include "player/player_snapshot.h"
#include "world/epic_transaction.h"
#include "economy/currency_transaction.h"

#include <span>
#include <source_location>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

struct char_data;
struct allowed_race_spec_struct;
struct damage_messages;
struct innate_data;

namespace character_mechanics
{
// IDs belong to mechanics, not saved character data. Connections are supplied
// beside their owners; exact branch markers below carry the same compiled ID.
enum class MechanicId
{
	innate_identity,
	innate_unlock,
	innate_eligibility,
	innate_entry,
	innate_dispatch,
	guardian_bulwark_grant,
	guardian_bulwark_callback,
	guardian_bulwark_factor,
	guardian_bulwark_effect,
	specialization_entry,
	specialization_eligibility,
	specialization_select,
	specialization_refresh,
	specialization_capture,
	specialization_load,
	unspecialization_entry_coral,
	unspecialization_entry_blood,
	unspecialization_altar,
	unspecialization_value,
	unspecialization_purchase,
	unspecialization_commit,
	unspecialization_refresh,
	unspecialization_forget,
	epics_capture,
	epics_load,
	epics_transaction,
	multiclass_command,
	multiclass_list,
	multiclass_room_test,
	multiclass_room_temple,
	multiclass_select,
	multiclass_allowed,
	multiclass_reset,
	multiclass_newbie_skills,
	multiclass_restore,
	multiclass_forget,
	multiclass_refund,
	multiclass_refund_commit,
	multiclass_wallet_refund,
	multiclass_trophies,
	multiclass_skill_data,
	multiclass_primary_cap,
	multiclass_secondary_cap,
	multiclass_hitpoints,
	class_hitpoint_factors,
	racial_constitution,
	multiclass_status_capture,
	multiclass_status_load,
	status_capture,
	status_load,
	skills_capture,
	skills_load,
	affects_capture,
	affects_load,
	trophies_capture,
	trophies_load,
	revenant_entry,
	object_periodic,
	revenant_apply,
	revenant_lifecycle,
	revenant_value,
	race_status_capture,
	transient_race_capture,
	race_status_load,
	equipment_capture,
	inventory_capture,
	equipment_load,
	inventory_load,
	racial_age_data,
	count
};

enum class Relation
{
	identity,
	eligibility,
	grant,
	passive,
	configuration,
	effect,
	entry,
	mutation,
	capture,
	load
};
enum class Access
{
	available,
	conditional,
	disabled,
	unresolved
};
enum class Implementation
{
	connected,
	incomplete,
	legacy
};
enum class OptionKind
{
	shared,
	race,
	character_class,
	specialization,
	multiclass
};

struct Option
{
	OptionKind kind;
	// Native race ID or CLASS_* mask. Specializations use (class mask, slot);
	// multiclass uses ordered (primary mask, secondary mask). Shared is (0, 0).
	unsigned int primary;
	unsigned int secondary;
};

using CharacterIntPredicate = bool (*)(char_data *, int);
using CharacterIntFunction = int (*)(char_data *, int);
using CharacterQuery = int (*)(char_data *);
using MeleeDamage = int (*)(char_data *, char_data *, double, int, damage_messages *, int *);
using CommandHandler = void (*)(char_data *, char *, int);
using CommandSlot = CommandHandler const *;
using RaceSpecPredicate = bool (*)(int, unsigned int, int);
using CharacterAction = void (*)(char_data *);
using ObjectAction = void (*)(char_data *, obj_data *);
using EpicSubmit = decltype(&epic_transaction_submit);
using WalletSubmit = decltype(&currency_transaction_submit_wallet_value);
using ObjectProcValue = int (*)(obj_proc_type);
using RoomProcedure = decltype(room_data::funct);
using CharacterReset = void (*)(char_data *, int);
using SkillReset = void (*)(char_data *, bool);
using SkillDataQuery = ClassSkillInfo (*)(char_data *, int);
using ClassHitpointFactors = const float (*)[CLASS_COUNT + 1];
using RacialStatFactors = const stat_data (*)[LAST_RACE + 1];
using RacialAgeData = const racial_data_type (*)[LAST_RACE + 1];
using StatusFields = std::span<const player_status_field>;

// Bind the vnum to the loaded native prototype table and its lookup. Missing
// vnums are invalid registrations, even when the legacy real_object0 assignment
// fell back to slot zero.
struct ObjectRegistration
{
	int vnum;
	index_data *const *index;
	int (*lookup)(int);
};
struct RoomRegistration
{
	int vnum;
	room_data *const *world;
	int (*lookup)(int);
};
using MechanicBinding =
	std::variant<const char *, const float *, CharacterIntPredicate, CharacterIntFunction,
		     CharacterQuery, MeleeDamage, CommandHandler, CommandSlot, RaceSpecPredicate,
		     CharacterAction, player_status_field, const innate_data *, ObjectRegistration,
		     obj_proc_type, ObjectAction, epic_completion_fn, EpicSubmit, ObjectProcValue,
		     RoomRegistration, RoomProcedure, CharacterReset, SkillReset, SkillDataQuery,
		     WalletSubmit, ClassHitpointFactors, RacialStatFactors, StatusFields,
		     player_checkpoint_component, event_func_type, RacialAgeData>;

struct MechanicConnection
{
	MechanicId id;
	Relation relation;
	Option owner;
	// Zero when not specific to one innate; nonzero is the existing INNATE_* ID.
	int innate;
	MechanicBinding binding;
	std::string_view symbol;
	std::span<const MechanicId> dependencies;
	Access access;
	Implementation implementation;
	std::string_view context;
	std::string_view gap;
	std::source_location declared_at = std::source_location::current();
};

enum class TransitionKind
{
	permanent,
	temporary,
	disguise,
	control_transfer
};

// State/lifecycle attributes of a mutation connection. The IDs refer to the
// same native connections above instead of repeating handlers or execution.
struct TransitionConnection
{
	MechanicId mutation;
	std::span<const MechanicId> entries;
	TransitionKind kind;
	std::span<const player_status_field> changed_status;
	std::span<const player_status_field> retained_status;
	std::span<const MechanicId> lifecycle;
	std::string_view context;
	player_component_mask_t changed_components = 0;
};

// Bindings retain native pointer types or existing status-field IDs. Their
// spelling is for source checks, never a second evaluator or a dispatcher.
#define CHARACTER_MECHANIC_BIND(symbol) (symbol), #symbol
#define CHARACTER_MECHANIC_SITE(id)                           \
	static_assert(::character_mechanics::MechanicId::id < \
		      ::character_mechanics::MechanicId::count)

std::string_view mechanic_name(MechanicId id);
std::span<const MechanicConnection> innate_connections();
std::span<const MechanicConnection> melee_connections();
std::span<const MechanicConnection> command_connections();
std::span<const MechanicConnection> specialization_connections();
std::span<const MechanicConnection> unspecialization_connections();
std::span<const MechanicConnection> object_registration_connections();
std::span<const MechanicConnection> object_action_connections();
std::span<const MechanicConnection> memorization_connections();
std::span<const MechanicConnection> epic_connections();
std::span<const MechanicConnection> object_value_connections();
std::span<const MechanicConnection> training_connections();
std::span<const MechanicConnection> status_capture_connections();
std::span<const MechanicConnection> status_load_connections();
std::span<const MechanicConnection> room_registration_connections();
std::span<const MechanicConnection> multiclass_command_connections();
std::span<const MechanicConnection> multiclass_connections();
std::span<const MechanicConnection> reset_connections();
std::span<const MechanicConnection> skill_data_connections();
std::span<const MechanicConnection> hitpoint_connections();
std::span<const MechanicConnection> racial_stat_connections();
std::span<const MechanicConnection> epic_refund_connections();
std::span<const MechanicConnection> trophy_connections();
std::span<const MechanicConnection> currency_connections();
std::span<const MechanicConnection> revenant_connections();
std::span<const MechanicConnection> object_periodic_connections();
std::span<const MechanicConnection> item_load_connections();
std::span<const MechanicConnection> racial_age_connections();
std::span<const TransitionConnection> revenant_transitions();
std::span<const TransitionConnection> multiclass_transitions();
std::span<const TransitionConnection> specialization_transitions();
std::vector<TransitionConnection> transition_connections();
std::vector<MechanicConnection> mechanic_connections();
std::vector<std::string> validate_mechanics(std::span<const MechanicConnection> connections);
std::vector<std::string> validate_transitions(std::span<const TransitionConnection> transitions,
					      std::span<const MechanicConnection> connections);

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
