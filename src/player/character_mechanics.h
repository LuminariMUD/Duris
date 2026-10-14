#ifndef CHARACTER_MECHANICS_H
#define CHARACTER_MECHANICS_H

#include "core/defines.h"
#include "player/player_snapshot.h"
#include "world/epic_transaction.h"
#include "economy/currency_transaction.h"
#include "account/racewar_admission.h"

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
struct cJSON;

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
	race_affect_cleanup,
	death_affect_cleanup,
	skill_table,
	skill_registration,
	racial_innate_grants,
	class_innate_grants,
	innate_registration,
	innate_callbacks,
	creation_rules,
	telnet_race_entry,
	telnet_race_select,
	telnet_class_entry,
	telnet_class_select,
	telnet_alignment_entry,
	telnet_alignment_select,
	websocket_options_entry,
	websocket_options,
	websocket_creation_entry,
	websocket_creation,
	account_admission_policy,
	account_admission,
	account_admission_commit,
	character_initialize,
	command_table,
	command_registration,
	ascend_entry,
	ascend_attempt,
	ascend_theurgist,
	ascend_commit,
	descend_entry,
	descend_attempt,
	old_descend_attempt,
	corpseform_entry,
	corpseform_attempt,
	corpseform_expiry,
	innate_cooldown,
	innate_readiness,
	innate_property,
	phantasmal_form,
	affect_apply,
	short_affect_expiry,
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
using SpellHandler = decltype(s_skill::spell_pointer);
using SpellSlot = SpellHandler const *;
using RaceSpecPredicate = bool (*)(int, unsigned int, int);
using CharacterAction = void (*)(char_data *);
using AffectRemoval = void (*)(char_data *, affected_type *);
using AffectInsertion = affected_type *(*)(char_data *, affected_type *);
using InnateCooldown = bool (*)(char_data *, int, int);
using InnateProperty = int (*)(int, const char *, int);
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

// Startup write provenance. Values are observed at the existing registration
// sites so an overwritten grant remains visible alongside the final native table.
struct GrantWrite
{
	int ability;
	Option owner;
	int level;
	int cap;
	std::source_location declared_at;
	// SPEC_*_ADD overrides a class-wide *_ADD default, never another specific grant.
	bool replaces = false;
};
using SkillTable = std::span<const s_skill>;
using GrantWrites = std::span<const GrantWrite>;
using InnateCallbacks = std::span<const innate_data>;
using RacialInnates = const char (*)[LAST_INNATE + 1][LAST_RACE + 1];
using ClassInnates = const char (*)[LAST_INNATE + 2][CLASS_COUNT][MAX_SPEC + 1];
struct CommandWrite
{
	int command;
	command_info value;
	std::string_view handler_symbol;
	std::source_location declared_at;
};
struct CommandTable
{
	std::span<const command_info> slots;
	// The existing command vocabulary is one-based; names[command - 1].
	std::span<const char *const> names;
};
using CommandWrites = std::span<const CommandWrite>;
struct IdentityConnections;
using CreationRules = const IdentityConnections *;
using DescriptorSelection = void (*)(descriptor_data *, char *);
using JsonCommand = void (*)(descriptor_data *, cJSON *);
using AdmissionPolicy = decltype(&account_racewar_evaluate);
using AdmissionCheck = account_racewar_admission (*)(descriptor_data *, int, bool, bool);
using AdmissionCommit = bool (*)(descriptor_data *, char_data *, bool, account_racewar_admission *);
struct LoginRegistration
{
	int state;
	DescriptorSelection dispatcher;
	DescriptorSelection selection;
};
struct JsonHandler
{
	const char *name;
	JsonCommand handler;
};
struct JsonRegistration
{
	const char *command;
	JsonCommand (*lookup)(const char *);
	void (*dispatcher)(descriptor_data *, const char *, cJSON *);
	std::span<const JsonHandler> handlers;
};
using MechanicBinding = std::variant<
	const char *, const float *, CharacterIntPredicate, CharacterIntFunction, CharacterQuery,
	MeleeDamage, CommandHandler, CommandSlot, RaceSpecPredicate, CharacterAction,
	player_status_field, const innate_data *, ObjectRegistration, obj_proc_type, ObjectAction,
	epic_completion_fn, EpicSubmit, ObjectProcValue, RoomRegistration, RoomProcedure,
	CharacterReset, SkillReset, SkillDataQuery, WalletSubmit, ClassHitpointFactors,
	RacialStatFactors, StatusFields, player_checkpoint_component, event_func_type,
	RacialAgeData, AffectRemoval, SkillTable, GrantWrites, InnateCallbacks, RacialInnates,
	ClassInnates, CreationRules, DescriptorSelection, JsonCommand, LoginRegistration,
	JsonRegistration, AdmissionPolicy, AdmissionCheck, AdmissionCommit, CommandTable,
	CommandWrites, SpellHandler, SpellSlot, AffectInsertion, InnateCooldown, InnateProperty>;

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
std::span<const MechanicConnection> affect_cleanup_connections();
std::span<const MechanicConnection> death_connections();
std::span<const MechanicConnection> skill_registration_connections();
std::span<const MechanicConnection> innate_registration_connections();
std::span<const MechanicConnection> creation_rule_connections();
std::span<const MechanicConnection> telnet_creation_connections();
std::span<const MechanicConnection> websocket_creation_connections();
std::span<const MechanicConnection> admission_connections();
std::span<const MechanicConnection> ascension_connections();
std::span<const MechanicConnection> corpseform_connections();
std::span<const TransitionConnection> phantasmal_transitions();
std::span<const TransitionConnection> revenant_transitions();
std::span<const TransitionConnection> multiclass_transitions();
std::span<const TransitionConnection> specialization_transitions();
std::vector<TransitionConnection> transition_connections();
std::vector<MechanicConnection> mechanic_connections();
std::vector<std::string> validate_mechanics(std::span<const MechanicConnection> connections);
std::vector<std::string> validate_grants(std::span<const MechanicConnection> connections);
std::vector<std::string> validate_commands(std::span<const MechanicConnection> connections);
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
