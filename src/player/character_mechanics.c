#include "core/prototypes.h"
#include "player/character_mechanics.h"
#include "classes/specializations.h"

#include <algorithm>
#include <array>
#include <bit>
#include <cstring>
#include <type_traits>

namespace character_mechanics
{
namespace
{
bool entry_registered(const MechanicConnection &entry,
		      std::span<const MechanicConnection> connections)
{
	for (auto id : entry.dependencies)
		for (const auto &target : connections)
		{
			if (target.id != id)
				continue;
			if (const auto *slot = std::get_if<CommandSlot>(&entry.binding))
			{
				const auto *handler = std::get_if<CommandHandler>(&target.binding);
				if (*slot && **slot && handler && **slot == *handler)
					return true;
			}
			if (const auto *room = std::get_if<RoomRegistration>(&entry.binding))
			{
				const auto *handler = std::get_if<RoomProcedure>(&target.binding);
				if (!room->world || !*room->world || !room->lookup || !handler ||
				    !*handler)
					continue;
				const int slot = room->lookup(room->vnum);
				if (slot >= 0 && (*room->world)[slot].number == room->vnum &&
				    (*room->world)[slot].funct == *handler)
					return true;
			}
			if (const auto *object = std::get_if<ObjectRegistration>(&entry.binding))
			{
				const auto *handler = std::get_if<obj_proc_type>(&target.binding);
				if (!object->index || !*object->index || !object->lookup ||
				    !handler || !*handler)
					continue;
				const int slot = object->lookup(object->vnum);
				if (slot >= 0 &&
				    (*object->index)[slot].virtual_number == object->vnum &&
				    (*object->index)[slot].func.obj == *handler)
					return true;
			}
		}
	return false;
}
} // namespace

std::string_view mechanic_name(MechanicId id)
{
	switch (id)
	{
	case MechanicId::innate_identity:
		return "innate.identity";
	case MechanicId::innate_unlock:
		return "innate.unlock";
	case MechanicId::innate_eligibility:
		return "innate.eligibility";
	case MechanicId::innate_entry:
		return "innate.entry";
	case MechanicId::innate_dispatch:
		return "innate.dispatch";
	case MechanicId::guardian_bulwark_grant:
		return "guardian.bulwark.grant";
	case MechanicId::guardian_bulwark_callback:
		return "guardian.bulwark.callback";
	case MechanicId::guardian_bulwark_factor:
		return "guardian.bulwark.factor";
	case MechanicId::guardian_bulwark_effect:
		return "guardian.bulwark.effect";
	case MechanicId::specialization_entry:
		return "specialization.entry";
	case MechanicId::specialization_eligibility:
		return "specialization.eligibility";
	case MechanicId::specialization_select:
		return "specialization.select";
	case MechanicId::specialization_refresh:
		return "specialization.refresh";
	case MechanicId::specialization_capture:
		return "specialization.capture";
	case MechanicId::specialization_load:
		return "specialization.load";
	case MechanicId::unspecialization_entry_coral:
		return "unspecialization.entry.coral";
	case MechanicId::unspecialization_entry_blood:
		return "unspecialization.entry.blood";
	case MechanicId::unspecialization_altar:
		return "unspecialization.altar";
	case MechanicId::unspecialization_value:
		return "unspecialization.value";
	case MechanicId::unspecialization_purchase:
		return "unspecialization.purchase";
	case MechanicId::unspecialization_commit:
		return "unspecialization.commit";
	case MechanicId::unspecialization_refresh:
		return "unspecialization.refresh";
	case MechanicId::unspecialization_forget:
		return "unspecialization.forget";
	case MechanicId::epics_capture:
		return "epics.capture";
	case MechanicId::epics_load:
		return "epics.load";
	case MechanicId::epics_transaction:
		return "epics.transaction";
	case MechanicId::multiclass_command:
		return "multiclass.command";
	case MechanicId::multiclass_list:
		return "multiclass.list";
	case MechanicId::multiclass_room_test:
		return "multiclass.room.test";
	case MechanicId::multiclass_room_temple:
		return "multiclass.room.temple";
	case MechanicId::multiclass_select:
		return "multiclass.select";
	case MechanicId::multiclass_allowed:
		return "multiclass.allowed";
	case MechanicId::multiclass_reset:
		return "multiclass.reset";
	case MechanicId::multiclass_newbie_skills:
		return "multiclass.newbie.skills";
	case MechanicId::multiclass_restore:
		return "multiclass.restore";
	case MechanicId::multiclass_forget:
		return "multiclass.forget";
	case MechanicId::multiclass_refund:
		return "multiclass.refund";
	case MechanicId::multiclass_refund_commit:
		return "multiclass.refund.commit";
	case MechanicId::multiclass_wallet_refund:
		return "multiclass.wallet.refund";
	case MechanicId::multiclass_trophies:
		return "multiclass.trophies";
	case MechanicId::multiclass_skill_data:
		return "multiclass.skill.data";
	case MechanicId::multiclass_primary_cap:
		return "multiclass.primary.cap";
	case MechanicId::multiclass_secondary_cap:
		return "multiclass.secondary.cap";
	case MechanicId::multiclass_hitpoints:
		return "multiclass.hitpoints";
	case MechanicId::class_hitpoint_factors:
		return "class.hitpoint.factors";
	case MechanicId::racial_constitution:
		return "racial.constitution";
	case MechanicId::multiclass_status_capture:
		return "multiclass.status.capture";
	case MechanicId::multiclass_status_load:
		return "multiclass.status.load";
	case MechanicId::status_capture:
		return "status.capture";
	case MechanicId::status_load:
		return "status.load";
	case MechanicId::skills_capture:
		return "skills.capture";
	case MechanicId::skills_load:
		return "skills.load";
	case MechanicId::affects_capture:
		return "affects.capture";
	case MechanicId::affects_load:
		return "affects.load";
	case MechanicId::trophies_capture:
		return "trophies.capture";
	case MechanicId::trophies_load:
		return "trophies.load";
	case MechanicId::revenant_entry:
		return "revenant.entry";
	case MechanicId::object_periodic:
		return "object.periodic";
	case MechanicId::revenant_apply:
		return "revenant.apply";
	case MechanicId::revenant_lifecycle:
		return "revenant.lifecycle";
	case MechanicId::revenant_value:
		return "revenant.value";
	case MechanicId::race_status_capture:
		return "race.status.capture";
	case MechanicId::transient_race_capture:
		return "transient.race.capture";
	case MechanicId::race_status_load:
		return "race.status.load";
	case MechanicId::equipment_capture:
		return "equipment.capture";
	case MechanicId::inventory_capture:
		return "inventory.capture";
	case MechanicId::equipment_load:
		return "equipment.load";
	case MechanicId::inventory_load:
		return "inventory.load";
	case MechanicId::racial_age_data:
		return "racial.age.data";
	case MechanicId::race_affect_cleanup:
		return "race.affect.cleanup";
	case MechanicId::death_affect_cleanup:
		return "death.affect.cleanup";
	case MechanicId::count:
		break;
	}
	return {};
}

std::vector<MechanicConnection> mechanic_connections()
{
	std::vector<MechanicConnection> result;
	for (auto connections : { innate_connections(),
				  melee_connections(),
				  command_connections(),
				  specialization_connections(),
				  training_connections(),
				  status_capture_connections(),
				  status_load_connections(),
				  unspecialization_connections(),
				  object_registration_connections(),
				  object_action_connections(),
				  memorization_connections(),
				  epic_connections(),
				  object_value_connections(),
				  room_registration_connections(),
				  multiclass_command_connections(),
				  multiclass_connections(),
				  reset_connections(),
				  skill_data_connections(),
				  hitpoint_connections(),
				  racial_stat_connections(),
				  epic_refund_connections(),
				  trophy_connections(),
				  currency_connections(),
				  revenant_connections(),
				  object_periodic_connections(),
				  item_load_connections(),
				  racial_age_connections(),
				  affect_cleanup_connections(),
				  death_connections() })
		result.insert(result.end(), connections.begin(), connections.end());
	return result;
}

std::vector<TransitionConnection> transition_connections()
{
	std::vector<TransitionConnection> result;
	for (auto connections :
	     { specialization_transitions(), multiclass_transitions(), revenant_transitions() })
		result.insert(result.end(), connections.begin(), connections.end());
	return result;
}

std::vector<std::string> validate_mechanics(std::span<const MechanicConnection> connections)
{
	std::vector<std::string> errors;
	std::array<bool, size_t(MechanicId::count)> seen{};
	auto valid_class = [](unsigned int mask)
	{ return std::has_single_bit(mask) && std::countr_zero(mask) < CLASS_COUNT; };
	for (const auto &connection : connections)
	{
		const std::string name(mechanic_name(connection.id));
		auto require = [&](bool valid, const char *problem)
		{
			if (!valid)
				errors.push_back(name + ": " + problem);
		};
		if (name.empty())
		{
			errors.push_back("unknown mechanic ID");
			continue;
		}
		require(!seen[size_t(connection.id)], "duplicate connection");
		seen[size_t(connection.id)] = true;
		require(std::visit(
				[](auto binding)
				{
					if constexpr (std::is_same_v<decltype(binding),
								     player_status_field> ||
						      std::is_same_v<decltype(binding),
								     player_checkpoint_component>)
						return true; // A typed field ID, not a nullable pointer.
					else if constexpr (std::is_same_v<decltype(binding),
									  StatusFields>)
						return !binding.empty();
					else if constexpr (std::is_same_v<decltype(binding),
									  RoomRegistration>)
						return binding.world && *binding.world &&
						       binding.lookup;
					else if constexpr (std::is_same_v<decltype(binding),
									  ObjectRegistration>)
						return binding.index && *binding.index &&
						       binding.lookup;
					else
						return binding != nullptr;
				},
				connection.binding),
			"missing native binding");
		require(!connection.symbol.empty(), "missing native symbol");
		require(!connection.context.empty(), "missing context");
		bool compatible = false;
		switch (connection.relation)
		{
		case Relation::identity:
			compatible = std::holds_alternative<CharacterQuery>(connection.binding);
			break;
		case Relation::eligibility:
			compatible =
				std::holds_alternative<CharacterIntPredicate>(connection.binding) ||
				std::holds_alternative<CharacterIntFunction>(connection.binding) ||
				std::holds_alternative<RaceSpecPredicate>(connection.binding);
			break;
		case Relation::grant:
			compatible = std::holds_alternative<const char *>(connection.binding);
			break;
		case Relation::passive:
			compatible =
				std::holds_alternative<const innate_data *>(connection.binding);
			if (const auto *row = std::get_if<const innate_data *>(&connection.binding);
			    row && *row)
			{
				require((*row)->name && *(*row)->name, "passive has no name");
				require((*row)->func == nullptr, "passive has an active callback");
			}
			break;
		case Relation::configuration:
			compatible =
				std::holds_alternative<const float *>(connection.binding) ||
				std::holds_alternative<ObjectProcValue>(connection.binding) ||
				std::holds_alternative<SkillDataQuery>(connection.binding) ||
				std::holds_alternative<ClassHitpointFactors>(connection.binding) ||
				std::holds_alternative<RacialStatFactors>(connection.binding) ||
				std::holds_alternative<RacialAgeData>(connection.binding);
			break;
		case Relation::effect:
			compatible =
				std::holds_alternative<AffectRemoval>(connection.binding) ||
				std::holds_alternative<event_func_type>(connection.binding) ||
				std::holds_alternative<MeleeDamage>(connection.binding) ||
				std::holds_alternative<CharacterAction>(connection.binding) ||
				std::holds_alternative<CommandHandler>(connection.binding) ||
				std::holds_alternative<obj_proc_type>(connection.binding) ||
				std::holds_alternative<ObjectAction>(connection.binding) ||
				std::holds_alternative<CharacterIntFunction>(connection.binding) ||
				std::holds_alternative<EpicSubmit>(connection.binding) ||
				std::holds_alternative<WalletSubmit>(connection.binding) ||
				std::holds_alternative<CharacterReset>(connection.binding) ||
				std::holds_alternative<SkillReset>(connection.binding) ||
				std::holds_alternative<SkillDataQuery>(connection.binding) ||
				std::holds_alternative<CharacterQuery>(connection.binding) ||
				std::holds_alternative<epic_completion_fn>(connection.binding);
			break;
		case Relation::entry:
			compatible =
				std::holds_alternative<CommandSlot>(connection.binding) ||
				std::holds_alternative<ObjectRegistration>(connection.binding) ||
				std::holds_alternative<RoomRegistration>(connection.binding);
			break;
		case Relation::mutation:
			compatible =
				std::holds_alternative<obj_proc_type>(connection.binding) ||
				std::holds_alternative<CommandHandler>(connection.binding) ||
				std::holds_alternative<epic_completion_fn>(connection.binding) ||
				std::holds_alternative<RoomProcedure>(connection.binding);
			break;
		case Relation::capture:
		case Relation::load:
			compatible =
				std::holds_alternative<player_status_field>(connection.binding) ||
				std::holds_alternative<StatusFields>(connection.binding) ||
				std::holds_alternative<player_checkpoint_component>(
					connection.binding);
			break;
		}
		require(compatible, "relation/native binding disagree");
		if (const auto *component =
			    std::get_if<player_checkpoint_component>(&connection.binding))
			require(std::has_single_bit(player_component_mask_t(*component)) &&
					!(player_component_mask_t(*component) &
					  ~PLAYER_CHECKPOINT_COMPONENT_ALL),
				"invalid snapshot component");
		require(connection.implementation == Implementation::connected ?
				connection.gap.empty() :
				!connection.gap.empty(),
			"implementation/gap disagree");
		require(connection.innate >= 0 && connection.innate <= LAST_INNATE,
			"invalid innate");
		const auto &owner = connection.owner;
		switch (owner.kind)
		{
		case OptionKind::shared:
			require(owner.primary == 0 && owner.secondary == 0, "invalid shared owner");
			break;
		case OptionKind::race:
			require(owner.primary <= LAST_RACE && owner.secondary == 0,
				"invalid race owner");
			break;
		case OptionKind::character_class:
			require(valid_class(owner.primary) && owner.secondary == 0,
				"invalid class owner");
			break;
		case OptionKind::specialization:
			require(valid_class(owner.primary) && owner.secondary > 0 &&
					owner.secondary <= MAX_SPEC,
				"invalid specialization owner");
			break;
		case OptionKind::multiclass:
			require(valid_class(owner.primary) && valid_class(owner.secondary),
				"invalid multiclass owner");
			break;
		}
		for (auto dependency : connection.dependencies)
			require(std::any_of(connections.begin(), connections.end(),
					    [&](const auto &candidate)
					    { return candidate.id == dependency; }),
				"missing dependency");
		if (connection.relation == Relation::entry)
			require(entry_registered(connection, connections),
				std::holds_alternative<RoomRegistration>(connection.binding) ?
					"room registration missing or different handler" :
				std::holds_alternative<ObjectRegistration>(connection.binding) ?
					"object registration missing or different handler" :
					"command registration missing or different handler");
		if (connection.relation == Relation::passive)
		{
			bool consumer = false;
			for (auto id : connection.dependencies)
				for (const auto &target : connections)
					consumer |= target.id == id &&
						    target.relation == Relation::effect &&
						    connection.innate > 0 &&
						    target.innate == connection.innate;
			require(consumer, "passive lacks a matching effect connection");
		}
	}
	for (size_t id = 0; id < seen.size(); ++id)
		if (!seen[id])
			errors.push_back(std::string(mechanic_name(MechanicId(id))) +
					 ": missing connection");
	return errors;
}

std::vector<std::string> validate_transitions(std::span<const TransitionConnection> transitions,
					      std::span<const MechanicConnection> connections)
{
	std::vector<std::string> errors;
	auto find = [&](MechanicId id) -> const MechanicConnection *
	{
		for (const auto &connection : connections)
			if (connection.id == id)
				return &connection;
		return nullptr;
	};
	auto reaches = [&](MechanicId start, MechanicId target)
	{
		std::vector<MechanicId> pending{ start };
		for (size_t i = 0; i < pending.size(); ++i)
		{
			if (pending[i] == target)
				return true;
			if (const auto *part = find(pending[i]))
				for (auto id : part->dependencies)
					if (std::find(pending.begin(), pending.end(), id) ==
					    pending.end())
						pending.push_back(id);
		}
		return false;
	};
	for (const auto &transition : transitions)
	{
		const std::string name(mechanic_name(transition.mutation));
		auto require = [&](bool valid, const char *message)
		{
			if (!valid)
				errors.push_back(name + ": " + message);
		};
		const auto *mutation = find(transition.mutation);
		require(mutation && mutation->relation == Relation::mutation, "missing mutation");
		if (!mutation)
			continue;
		require(!transition.entries.empty(), "missing entry");
		for (auto id : transition.entries)
		{
			const auto *entry = find(id);
			require(entry && entry->relation == Relation::entry, "missing entry");
			if (!entry)
				continue;
			require(entry_registered(*entry, connections),
				std::holds_alternative<RoomRegistration>(entry->binding) ?
					"room registration missing or different handler" :
				std::holds_alternative<ObjectRegistration>(entry->binding) ?
					"object registration missing or different handler" :
					"command registration missing or different handler");
			require(reaches(id, transition.mutation), "entry does not reach mutation");
		}
		require(!transition.changed_status.empty() && !transition.context.empty(),
			"missing state description");
		for (auto field : transition.changed_status)
		{
			require(std::find(transition.retained_status.begin(),
					  transition.retained_status.end(),
					  field) == transition.retained_status.end(),
				"state both changed and retained");
			for (auto role : { Relation::capture, Relation::load })
			{
				bool found = false;
				for (auto id : transition.lifecycle)
					if (const auto *part = find(id);
					    part && part->relation == role)
					{
						if (const auto *bound =
							    std::get_if<player_status_field>(
								    &part->binding))
							found |= *bound == field;
						if (const auto *fields = std::get_if<StatusFields>(
							    &part->binding))
							found |= std::find(fields->begin(),
									   fields->end(),
									   field) != fields->end();
					}
				require(found, "changed field lacks capture/load connection");
			}
		}
		require(!(transition.changed_components & ~PLAYER_CHECKPOINT_COMPONENT_ALL),
			"invalid changed components");
		for (auto role : { Relation::capture, Relation::load })
		{
			player_component_mask_t covered = 0;
			for (auto id : transition.lifecycle)
				if (const auto *part = find(id); part && part->relation == role)
					if (const auto *component =
						    std::get_if<player_checkpoint_component>(
							    &part->binding))
						covered |= *component;
			require((covered & transition.changed_components) ==
					transition.changed_components,
				"changed component lacks capture/load connection");
		}
		for (auto id : transition.lifecycle)
			require(find(id) != nullptr, "missing lifecycle connection");
	}
	for (const auto &connection : connections)
		if (connection.relation == Relation::mutation)
			if (std::count_if(transitions.begin(), transitions.end(),
					  [&](const auto &transition)
					  { return transition.mutation == connection.id; }) != 1)
				errors.push_back(std::string(mechanic_name(connection.id)) +
						 ": missing/duplicate transition");
	return errors;
}

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
