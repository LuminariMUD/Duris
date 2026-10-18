/****************************************************************************
 *
 *  File: player_load_items.c                                   Part of Duris
 *  Usage: materializes a player's saved items and equipment on load
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "player/player_load_items.h"

#include "net/comm.h"
#include "guild/artifact_admission.h"
#include <cerrno>
#include "item/item_ownership_runtime.h"
#include "item/encumbrance_policy.h"
#include "player/player_snapshot_codec.h"
#include "sql/item_extra_descr_codec.h"
#include "core/prototypes.h"
#include "magic/spells.h"
#include "core/structs.h"
#include "core/utils.h"

#include <algorithm>
#include <array>
#include <climits>
#include <cstring>
#include <limits>
#include <new>
#include <unordered_map>
#include <unordered_set>
#include <vector>

extern Skill skills[];

namespace
{
class staged_item_graph
{
    public:
	~staged_item_graph()
	{
		if (published)
			return;
		for (P_obj object : objects)
			if (object)
			{
				artifact_object_extracted(object, false);
				object->obj_uid = 0;
			}
		if (linked)
		{
			for (size_t index = 0; index < objects.size(); ++index)
				if (objects[index] && roots[index])
					extract_obj(objects[index], FALSE);
			return;
		}
		for (P_obj object : objects)
			if (object)
				extract_obj(object, FALSE);
	}

	std::vector<P_obj> objects;
	std::vector<bool> roots;
	bool linked = false;
	bool published = false;
};

bool fail(player_load_item_materialize_metrics *metrics,
	  player_load_item_materialize_outcome outcome)
{
	if (metrics)
		metrics->outcome = outcome;
	return false;
}

void clear_item_uids(P_obj object)
{
	if (!object)
		return;
	artifact_object_extracted(object, false);
	object->obj_uid = 0;
	for (P_obj child = object->contains; child; child = child->next_content)
		clear_item_uids(child);
}

bool count_operation(player_load_item_materialize_metrics *metrics, size_t item_count,
		     size_t amount = 1)
{
	if (!metrics ||
	    metrics->operation_count > PLAYER_LOAD_ITEM_OPERATIONS_PER_ITEM * item_count - amount)
		return false;
	metrics->operation_count += amount;
	return true;
}

bool parse_spellbook(const std::string &json, char *spell_bits = nullptr)
{
	std::array<bool, MAX_SKILLS> seen = {};
	size_t position = 0;
	auto skip_space = [&]()
	{
		while (position < json.size() && (json[position] == ' ' || json[position] == '\t' ||
						  json[position] == '\r' || json[position] == '\n'))
			++position;
	};
	skip_space();
	if (position >= json.size() || json[position++] != '[')
		return false;
	skip_space();
	if (position < json.size() && json[position] == ']')
	{
		++position;
		skip_space();
		return position == json.size();
	}
	for (;;)
	{
		skip_space();
		if (position >= json.size() || json[position] < '0' || json[position] > '9')
			return false;
		const size_t number_start = position;
		uint64_t value = 0;
		while (position < json.size() && json[position] >= '0' && json[position] <= '9')
		{
			const uint64_t digit = static_cast<unsigned int>(json[position++] - '0');
			if (value > (static_cast<uint64_t>(MAX_SKILLS) - 1 - digit) / 10)
				return false;
			value = value * 10 + digit;
		}
		if (json[number_start] == '0' && position != number_start + 1)
			return false;
		if (seen[value])
			return false;
		seen[value] = true;
		if (spell_bits)
			spell_bits[value / 8] = static_cast<char>(
				static_cast<unsigned char>(spell_bits[value / 8]) |
				static_cast<unsigned char>(1U << (value % 8)));
		skip_space();
		if (position >= json.size())
			return false;
		if (json[position] == ']')
		{
			++position;
			break;
		}
		if (json[position++] != ',')
			return false;
	}
	skip_space();
	return position == json.size();
}

// Captured/flatfile snapshots store typed spell IDs; SQL rows store JSON.
// Both representations feed the same validation and materialization path.
// When spell_bits is non-null, callers must provide a zero-initialized buffer
// of (MAX_SKILLS + 1) / 8 + 1 bytes because this helper ORs the selected bits
// into it rather than clearing it first.
bool decode_saved_spellbook(const player_item_extra_description_snapshot &description,
			    char *spell_bits = nullptr)
{
	if (!description.description.empty())
		return description.spell_ids.empty() &&
		       parse_spellbook(description.description, spell_bits);
	std::array<bool, MAX_SKILLS> seen = {};
	for (int32_t spell : description.spell_ids)
	{
		if (spell < 0 || spell >= MAX_SKILLS || seen[spell])
			return false;
		seen[spell] = true;
		if (spell_bits)
			spell_bits[spell / 8] = static_cast<char>(
				static_cast<unsigned char>(spell_bits[spell / 8]) |
				static_cast<unsigned char>(1U << (spell % 8)));
	}
	return true;
}

enum class metadata_validation_outcome
{
	valid,
	invalid,
	allocation_failure,
};

metadata_validation_outcome valid_item_metadata(const player_item_snapshot &item,
						const player_load_item_identity &identity,
						bool complete_snapshot_state)
{
	constexpr uint8_t allowed_string_mask = STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2 |
						STRUNG_DESC3 | STRUNG_EDESC;
	if ((item.string_mask & ~allowed_string_mask) ||
	    identity.database_id > static_cast<uint64_t>(INT_MAX) ||
	    identity.item_uid > static_cast<uint64_t>(ULONG_MAX) ||
	    item.timers[0] < std::numeric_limits<time_t>::min() ||
	    item.timers[0] > std::numeric_limits<time_t>::max())
		return metadata_validation_outcome::invalid;
	if (complete_snapshot_state)
		for (int64_t timer : item.timers)
			if (timer < std::numeric_limits<time_t>::min() ||
			    timer > std::numeric_limits<time_t>::max())
				return metadata_validation_outcome::invalid;
	if ((identity.override_mask & PLAYER_LOAD_ITEM_OVERRIDE_TYPE) &&
	    (item.type < ITEM_LOWEST || item.type > ITEM_LAST))
		return metadata_validation_outcome::invalid;
	if (complete_snapshot_state)
		for (const auto &affect : item.dynamic_affects)
			if (affect.extra2 > ULONG_MAX)
				return metadata_validation_outcome::invalid;
	for (const auto &affect : item.affects)
		if ((identity.override_mask & PLAYER_LOAD_ITEM_OVERRIDE_AFFECTS) &&
		    (affect[0] < 0 || affect[0] > APPLY_LAST || affect[1] < INT8_MIN ||
		     affect[1] > INT8_MAX))
			return metadata_validation_outcome::invalid;
	std::unordered_set<std::string> descriptions;
	bool trap_state_seen = false;
	try
	{
		descriptions.reserve(item.extra_descriptions.size());
		for (const player_item_extra_description_snapshot &description :
		     item.extra_descriptions)
		{
			if (description.keyword.size() > PLAYER_SNAPSHOT_MAX_STRING_BYTES ||
			    description.description.size() > PLAYER_SNAPSHOT_MAX_STRING_BYTES)
				return metadata_validation_outcome::invalid;
			int16_t effect = 0, damage = 0, charges = 0, level = 0;
			const auto trap = sql_decode_item_trap_state(
				description.keyword.c_str(), description.description.c_str(),
				&effect, &damage, &charges, &level);
			if (trap == sql_item_trap_state_decode_status::invalid ||
			    (trap == sql_item_trap_state_decode_status::decoded &&
			     (trap_state_seen || description.spellbook ||
			      !description.spell_ids.empty())) ||
			    (trap == sql_item_trap_state_decode_status::not_trap_state &&
			     description.spellbook != (description.keyword == "SPELLBOOK")))
				return metadata_validation_outcome::invalid;
			trap_state_seen = trap_state_seen ||
					  trap == sql_item_trap_state_decode_status::decoded;
			std::string key = description.keyword;
			key.push_back('\0');
			key += description.description;
			if (description.spellbook)
			{
				std::array<char, (MAX_SKILLS + 1) / 8 + 1> spell_bits = {};
				if (!decode_saved_spellbook(description, spell_bits.data()))
					return metadata_validation_outcome::invalid;
				if (description.description.empty())
					key.append(spell_bits.data(), spell_bits.size());
			}
			else if (!description.spell_ids.empty())
				return metadata_validation_outcome::invalid;
			if (!descriptions.insert(std::move(key)).second)
				return metadata_validation_outcome::invalid;
		}
	}
	catch (const std::bad_alloc &)
	{
		return metadata_validation_outcome::allocation_failure;
	}
	return metadata_validation_outcome::valid;
}

void apply_saved_strings(P_obj object, const player_item_snapshot &item)
{
	if (item.string_mask & STRUNG_KEYS)
	{
		object->name = str_dup(item.name.c_str());
		object->str_mask |= STRUNG_KEYS;
	}
	if (item.string_mask & STRUNG_DESC2)
	{
		object->short_description = str_dup(item.short_description.c_str());
		object->str_mask |= STRUNG_DESC2;
	}
	if (item.string_mask & STRUNG_DESC1)
	{
		object->description = str_dup(item.description.c_str());
		object->str_mask |= STRUNG_DESC1;
	}
	if (item.string_mask & STRUNG_DESC3)
	{
		object->action_description = str_dup(item.action_description.c_str());
		object->str_mask |= STRUNG_DESC3;
	}
}

void apply_extra_descriptions(P_obj object, const player_item_snapshot &item)
{
	auto already_present = [object](const player_item_extra_description_snapshot &candidate)
	{
		std::array<char, (MAX_SKILLS + 1) / 8 + 1> spell_bits = {};
		if (candidate.spellbook && !decode_saved_spellbook(candidate, spell_bits.data()))
			return false;
		for (const extra_descr_data *existing = object->ex_description; existing;
		     existing = existing->next)
		{
			const bool existing_spellbook =
				existing->keyword && strlen(existing->keyword) == 3 &&
				existing->keyword[0] == 3 && existing->keyword[1] == 1 &&
				existing->keyword[2] == 3;
			if (candidate.spellbook != existing_spellbook)
				continue;
			if (candidate.spellbook)
			{
				if (existing->description &&
				    memcmp(existing->description, spell_bits.data(),
					   spell_bits.size()) == 0)
					return true;
				continue;
			}
			if (existing->keyword && candidate.keyword == existing->keyword &&
			    candidate.description ==
				    (existing->description ? existing->description : ""))
				return true;
		}
		return false;
	};
	for (auto description = item.extra_descriptions.rbegin();
	     description != item.extra_descriptions.rend(); ++description)
	{
		int16_t effect = 0, damage = 0, charges = 0, level = 0;
		if (sql_decode_item_trap_state(description->keyword.c_str(),
					       description->description.c_str(), &effect, &damage,
					       &charges, &level) ==
		    sql_item_trap_state_decode_status::decoded)
		{
			object->trap_eff = effect;
			object->trap_dam = damage;
			object->trap_charge = charges;
			object->trap_level = level;
			continue;
		}
		if (already_present(*description))
			continue;
		extra_descr_data *entry;
		CREATE(entry, extra_descr_data, 1, MEM_TAG_EXDESCD);
		memset(entry, 0, sizeof(*entry));
		if (description->spellbook)
		{
			const char marker[] = { 3, 1, 3, 0 };
			entry->keyword = str_dup(marker);
			const size_t byte_count = (MAX_SKILLS + 1) / 8 + 1;
			CREATE(entry->description, char, byte_count, MEM_TAG_STRING);
			memset(entry->description, 0, byte_count);
			decode_saved_spellbook(*description, entry->description);
		}
		else
		{
			entry->keyword = str_dup(description->keyword.c_str());
			entry->description = str_dup(description->description.c_str());
		}
		entry->next = object->ex_description;
		object->ex_description = entry;
		object->str_mask |= STRUNG_EDESC;
	}
}

void attach_loaded_inventory(P_char character, const std::vector<P_obj> &objects,
			     const std::vector<size_t> &roots,
			     const std::vector<player_item_snapshot> &items,
			     const std::vector<item_ownership_runtime_entry> &ownership)
{
	P_obj carrying_tail = character->carrying;
	while (carrying_tail && carrying_tail->next_content)
		carrying_tail = carrying_tail->next_content;
	for (size_t index : roots)
	{
		P_obj object = objects[index];
		const int slot = items[index].equipment_slot;
		if (slot > 0)
		{
			character->equipment[slot - 1] = object;
			object->loc.wearing = character;
			object->loc_p = LOC_WORN;
			if (IS_PC(character) && GET_ITEM_TYPE(object) == ITEM_ARMOR)
				character->only.pc->prestige += object->value[2];
			GET_CARRYING_W(character) += encumbrance_weight(GET_OBJ_WEIGHT(object)) / 2;
		}
		else
		{
			object->next_content = nullptr;
			if (carrying_tail)
				carrying_tail->next_content = object;
			else
				character->carrying = object;
			carrying_tail = object;
			object->loc.carrying = character;
			object->loc_p = LOC_CARRIED;
			object->z_cord = 0;
			GET_CARRYING_W(character) += encumbrance_weight(GET_OBJ_WEIGHT(object));
			IS_CARRYING_N(character)++;
			if (IS_PC(character) && !object->g_key && GET_LEVEL(character) < 57 &&
			    GET_PID(character) < 10000000)
				object->g_key = 1;
		}
	}
	for (size_t index = 0; index < objects.size(); ++index)
	{
		artifact_object_placed(objects[index]);
		artifact_reconcile_player_owner(objects[index], &ownership[index]);
	}
	balance_affects(character);
}
}

namespace
{
bool materialize_item_graph(P_char character, std::vector<P_obj> *detached_roots,
			    const std::vector<player_item_snapshot> &items,
			    const std::vector<player_load_item_identity> &identities,
			    const item_owner_identity &expected_owner, uint64_t owner_revision,
			    bool hydrate_ownership, bool complete_snapshot_state,
			    player_load_item_materialize_metrics *metrics,
			    const std::vector<artifact_payload_projection> *admission = nullptr,
			    bool committed_creation = false)
{
	player_load_item_materialize_metrics local_metrics = {};
	if (!metrics)
		metrics = &local_metrics;
	*metrics = {};
	const size_t item_count = items.size();
	metrics->item_count = item_count;
	const bool detached = detached_roots != nullptr;
	if ((!character && !detached) || (character && detached) ||
	    !item_owner_identity_valid(expected_owner) ||
	    expected_owner.type == item_owner_type::system ||
	    expected_owner.type == item_owner_type::destruction ||
	    identities.size() != item_count || item_count > PLAYER_LOAD_ITEM_MAX ||
	    (admission && admission->size() != item_count))
		return fail(metrics,
			    item_count > PLAYER_LOAD_ITEM_MAX ?
				    player_load_item_materialize_outcome::limit_exceeded :
				    player_load_item_materialize_outcome::invalid_snapshot);
	if (detached)
	{
		detached_roots->clear();
		try
		{
			detached_roots->reserve(item_count);
		}
		catch (const std::bad_alloc &)
		{
			return fail(metrics,
				    player_load_item_materialize_outcome::allocation_failure);
		}
	}
	if (!item_count)
	{
		if (hydrate_ownership &&
		    !item_ownership_runtime_hydrate_owner(expected_owner, owner_revision))
			return fail(metrics,
				    player_load_item_materialize_outcome::ownership_failure);
		metrics->outcome = player_load_item_materialize_outcome::applied;
		return true;
	}

	std::unordered_map<uint64_t, size_t> uid_indices;
	std::unordered_map<uint64_t, size_t> database_indices;
	std::vector<std::vector<size_t>> children;
	std::vector<size_t> roots;
	std::vector<size_t> depths;
	std::array<bool, MAX_WEAR> occupied_slots = {};
	try
	{
		uid_indices.reserve(item_count);
		database_indices.reserve(item_count);
		children.resize(item_count);
		roots.reserve(item_count);
		depths.assign(item_count, 0);
	}
	catch (const std::bad_alloc &)
	{
		return fail(metrics, player_load_item_materialize_outcome::allocation_failure);
	}

	for (size_t index = 0; index < item_count; ++index)
	{
		const player_item_snapshot &item = items[index];
		const player_load_item_identity &identity = identities[index];
		const size_t metadata_operations =
			item.extra_descriptions.size() +
			((identity.override_mask & PLAYER_LOAD_ITEM_OVERRIDE_AFFECTS) ?
				 item.affects.size() :
				 0);
		if (!count_operation(metrics, item_count, 2 + metadata_operations) ||
		    !identity.database_id || !identity.item_uid ||
		    identity.item_uid != item.object_uid || !identity.root_item_uid ||
		    identity.quantity != 1 || identity.state != item_custody_state::active ||
		    !item_owner_identity_equal(identity.owner, expected_owner) ||
		    identity.owner_revision != owner_revision ||
		    identity.override_mask & ~PLAYER_LOAD_ITEM_OVERRIDE_ALL)
			return fail(metrics,
				    player_load_item_materialize_outcome::invalid_snapshot);
		try
		{
			if (!uid_indices.emplace(identity.item_uid, index).second ||
			    !database_indices.emplace(identity.database_id, index).second)
				return fail(metrics,
					    player_load_item_materialize_outcome::invalid_snapshot);
		}
		catch (const std::bad_alloc &)
		{
			return fail(metrics,
				    player_load_item_materialize_outcome::allocation_failure);
		}
		const metadata_validation_outcome metadata =
			valid_item_metadata(item, identity, complete_snapshot_state);
		if (metadata != metadata_validation_outcome::valid)
			return fail(
				metrics,
				metadata == metadata_validation_outcome::allocation_failure ?
					player_load_item_materialize_outcome::allocation_failure :
					player_load_item_materialize_outcome::invalid_snapshot);
		if ((detached && item.equipment_slot != -1) ||
		    (!detached && (item.equipment_slot < 0 || item.equipment_slot > MAX_WEAR ||
				   (item.parent_index != PLAYER_SNAPSHOT_NO_PARENT &&
				    item.equipment_slot != 0))))
			return fail(metrics,
				    player_load_item_materialize_outcome::invalid_snapshot);
		if (!detached && item.equipment_slot > 0 && occupied_slots[item.equipment_slot - 1])
			return fail(metrics,
				    player_load_item_materialize_outcome::invalid_snapshot);
		if (!detached && item.equipment_slot > 0)
			occupied_slots[item.equipment_slot - 1] = true;
		if (item.parent_index == PLAYER_SNAPSHOT_NO_PARENT)
		{
			if (identity.serialized_parent_id || identity.parent_item_uid ||
			    identity.root_item_uid != identity.item_uid)
				return fail(metrics,
					    player_load_item_materialize_outcome::invalid_snapshot);
			roots.push_back(index);
		}
		else
		{
			if (item.parent_index < 0 ||
			    static_cast<size_t>(item.parent_index) >= item_count)
				return fail(metrics,
					    player_load_item_materialize_outcome::invalid_snapshot);
			const size_t parent = static_cast<size_t>(item.parent_index);
			const player_load_item_identity &parent_identity = identities[parent];
			if (identity.serialized_parent_id != parent_identity.database_id ||
			    identity.parent_item_uid != parent_identity.item_uid ||
			    identity.root_item_uid != parent_identity.root_item_uid)
				return fail(metrics,
					    player_load_item_materialize_outcome::invalid_snapshot);
			try
			{
				children[parent].push_back(index);
			}
			catch (const std::bad_alloc &)
			{
				return fail(
					metrics,
					player_load_item_materialize_outcome::allocation_failure);
			}
		}
	}
	if (roots.empty())
		return fail(metrics, player_load_item_materialize_outcome::invalid_snapshot);

	std::vector<size_t> traversal;
	try
	{
		traversal.reserve(item_count);
		for (size_t root : roots)
		{
			depths[root] = 1;
			traversal.push_back(root);
		}
		for (size_t cursor = 0; cursor < traversal.size(); ++cursor)
		{
			const size_t parent = traversal[cursor];
			if (!count_operation(metrics, item_count))
				return fail(metrics,
					    player_load_item_materialize_outcome::limit_exceeded);
			metrics->maximum_depth = std::max(metrics->maximum_depth, depths[parent]);
			if (depths[parent] > PLAYER_SNAPSHOT_MAX_DEPTH)
				return fail(metrics,
					    player_load_item_materialize_outcome::limit_exceeded);
			for (size_t child : children[parent])
			{
				if (depths[child])
					return fail(metrics, player_load_item_materialize_outcome::
								     invalid_snapshot);
				depths[child] = depths[parent] + 1;
				traversal.push_back(child);
			}
		}
	}
	catch (const std::bad_alloc &)
	{
		return fail(metrics, player_load_item_materialize_outcome::allocation_failure);
	}
	if (traversal.size() != item_count)
		return fail(metrics, player_load_item_materialize_outcome::invalid_snapshot);

	staged_item_graph staged;
	std::vector<item_ownership_runtime_entry> ownership;
	try
	{
		staged.objects.assign(item_count, nullptr);
		staged.roots.assign(item_count, false);
		ownership.reserve(item_count);
	}
	catch (const std::bad_alloc &)
	{
		return fail(metrics, player_load_item_materialize_outcome::allocation_failure);
	}
	for (size_t index = 0; index < item_count; ++index)
	{
		const player_item_snapshot &item = items[index];
		const player_load_item_identity &identity = identities[index];
		const int object_number = real_object(item.vnum);
		if (object_number < 0)
			return fail(metrics,
				    player_load_item_materialize_outcome::unknown_prototype);
		artifact_payload_projection owned_source = {};
		if (!admission)
		{
			// These identities have already passed the owner/revision/topology
			// checks above. Reserve their saved artifact UID before construction.
			switch (expected_owner.type)
			{
			case item_owner_type::player:
				owned_source.domain = artifact_payload_domain::player;
				break;
			case item_owner_type::pet:
				owned_source.domain = artifact_payload_domain::pet;
				break;
			case item_owner_type::corpse:
				owned_source.domain = artifact_payload_domain::corpse;
				break;
			case item_owner_type::locker:
				owned_source.domain = artifact_payload_domain::locker;
				break;
			case item_owner_type::room:
				owned_source.domain = artifact_payload_domain::room;
				break;
			case item_owner_type::shopkeeper:
				owned_source.domain = artifact_payload_domain::shopkeeper;
				break;
			case item_owner_type::auction:
				owned_source.domain = artifact_payload_domain::auction;
				break;
			case item_owner_type::collector:
				owned_source.domain = artifact_payload_domain::collector;
				break;
			case item_owner_type::container:
				owned_source.domain = artifact_payload_domain::embedded;
				break;
			default:
				return fail(metrics,
					    player_load_item_materialize_outcome::invalid_snapshot);
			}
			owned_source.row_id = identity.database_id;
			owned_source.item_uid = identity.item_uid;
			owned_source.payload_root_item_uid = identity.root_item_uid;
			owned_source.parent_item_uid = identity.parent_item_uid;
			owned_source.owner_reference = static_cast<int64_t>(expected_owner.id);
			owned_source.owner_context = expected_owner.context_id;
			owned_source.payload_owner = expected_owner;
			owned_source.vnum = item.vnum;
			owned_source.extra_flags = item.extra_flags;
			owned_source.extra_flags_present = true;
			owned_source.quantity = identity.quantity;
			owned_source.custody_examined = owned_source.custody_found =
				owned_source.custody_owner_revision_found = true;
			owned_source.custody = {
				identity.item_uid, identity.root_item_uid, identity.parent_item_uid,
				expected_owner,	   identity.item_revision, owner_revision,
				item.vnum,	   identity.state
			};
		}
		const auto &source = admission ? (*admission)[index] : owned_source;
		errno = 0;
		P_obj object = committed_creation ? read_object_for_creation_repair(source) :
						    read_object_for_recovery(source);
		if (!object)
			return fail(
				metrics,
				errno == ENOMEM ?
					player_load_item_materialize_outcome::allocation_failure :
					player_load_item_materialize_outcome::ownership_failure);
		staged.objects[index] = object;
		object->obj_uid = static_cast<unsigned long>(identity.item_uid);
		object->db_item_id = static_cast<int>(identity.database_id);
		object->g_key = item.generated_key;
		object->weight = item.weight;
		object->cost = item.cost;
		if (complete_snapshot_state)
			for (size_t timer = 0; timer < item.timers.size(); ++timer)
				object->timer[timer] = static_cast<time_t>(item.timers[timer]);
		else
			object->timer[0] = static_cast<time_t>(item.timers[0]);
		object->extra_flags = item.extra_flags;
		if (complete_snapshot_state)
		{
			object->anti_flags = item.anti_flags;
			object->anti2_flags = item.anti2_flags;
			object->extra2_flags = item.extra2_flags;
			object->craftsmanship = item.craftsmanship;
			for (auto affect = item.dynamic_affects.rbegin();
			     affect != item.dynamic_affects.rend(); ++affect)
			{
				if (affect->type == TAG_ALTERED_EXTRA2)
					continue;
				if (affect->extra2)
					set_obj_affected_extra(object, -1,
							       static_cast<sh_int>(affect->type),
							       static_cast<sh_int>(affect->data),
							       static_cast<ulong>(affect->extra2));
				else
					set_obj_affected(object, -1,
							 static_cast<sh_int>(affect->type),
							 static_cast<sh_int>(affect->data));
			}
		}
		object->condition = item.condition;
		for (size_t value_index = 0; value_index < item.values.size(); ++value_index)
			object->value[value_index] = item.values[value_index];
		if (identity.override_mask & PLAYER_LOAD_ITEM_OVERRIDE_WEAR_FLAGS)
			object->wear_flags = item.wear_flags;
		if (identity.override_mask & PLAYER_LOAD_ITEM_OVERRIDE_TYPE)
		{
			if (item.type == ITEM_CORPSE && object->type != ITEM_CORPSE)
				return fail(metrics,
					    player_load_item_materialize_outcome::invalid_snapshot);
			object->type = item.type;
		}
		if (identity.override_mask & PLAYER_LOAD_ITEM_OVERRIDE_MATERIAL)
			object->material = item.material;
		unsigned long *bitvectors[] = { &object->bitvector, &object->bitvector2,
						&object->bitvector3, &object->bitvector4,
						&object->bitvector5 };
		for (size_t bitvector = 0; bitvector < item.bitvectors.size(); ++bitvector)
			if (identity.override_mask &
			    (PLAYER_LOAD_ITEM_OVERRIDE_BITVECTOR1 << bitvector))
				*bitvectors[bitvector] =
					static_cast<unsigned long>(item.bitvectors[bitvector]);
		if (identity.override_mask & PLAYER_LOAD_ITEM_OVERRIDE_AFFECTS)
			for (size_t affect = 0; affect < item.affects.size(); ++affect)
			{
				object->affected[affect].location = item.affects[affect][0];
				object->affected[affect].modifier = item.affects[affect][1];
			}
		apply_saved_strings(object, item);
		apply_extra_descriptions(object, item);
		try
		{
			ownership.push_back({ identity.item_uid, identity.root_item_uid,
					      identity.parent_item_uid, identity.owner,
					      identity.item_revision, identity.owner_revision,
					      item.vnum, identity.state });
		}
		catch (const std::bad_alloc &)
		{
			return fail(metrics,
				    player_load_item_materialize_outcome::allocation_failure);
		}
		if (!count_operation(metrics, item_count))
			return fail(metrics, player_load_item_materialize_outcome::limit_exceeded);
	}

	std::vector<P_obj> child_tails;
	try
	{
		child_tails.assign(item_count, nullptr);
	}
	catch (const std::bad_alloc &)
	{
		return fail(metrics, player_load_item_materialize_outcome::allocation_failure);
	}
	for (size_t index = 0; index < item_count; ++index)
	{
		const int32_t parent_index = items[index].parent_index;
		if (parent_index == PLAYER_SNAPSHOT_NO_PARENT)
		{
			staged.roots[index] = true;
			continue;
		}
		if (!obj_can_nest(staged.objects[index],
				  staged.objects[static_cast<size_t>(parent_index)]))
			return fail(metrics,
				    player_load_item_materialize_outcome::invalid_snapshot);
	}
	for (size_t index = 0; index < item_count; ++index)
	{
		const int32_t parent_index = items[index].parent_index;
		if (parent_index == PLAYER_SNAPSHOT_NO_PARENT)
			continue;
		P_obj child = staged.objects[index];
		P_obj parent = staged.objects[static_cast<size_t>(parent_index)];
		child->loc_p = LOC_INSIDE;
		child->loc.inside = parent;
		child->next_content = nullptr;
		if (child_tails[parent_index])
			child_tails[parent_index]->next_content = child;
		else
			parent->contains = child;
		child_tails[parent_index] = child;
		if (!count_operation(metrics, item_count))
			return fail(metrics, player_load_item_materialize_outcome::limit_exceeded);
	}
	staged.linked = true;
	for (auto index = traversal.rbegin(); index != traversal.rend(); ++index)
	{
		recalc_container_weight(staged.objects[*index]);
		if (!count_operation(metrics, item_count))
			return fail(metrics, player_load_item_materialize_outcome::limit_exceeded);
	}

	if (hydrate_ownership &&
	    !item_ownership_runtime_hydrate_batch(ownership.data(), ownership.size()))
		return fail(metrics, player_load_item_materialize_outcome::ownership_failure);
	if (detached)
		for (size_t root : roots)
			detached_roots->push_back(staged.objects[root]);
	else
		attach_loaded_inventory(character, staged.objects, roots, items, ownership);
	for (P_obj object : staged.objects)
		artifact_object_placed(object);
	staged.published = true;
	metrics->outcome = player_load_item_materialize_outcome::applied;
	return true;
}
}

bool player_load_item_graph_materialize_for_owner(
	P_char character, const std::vector<player_item_snapshot> &items,
	const std::vector<player_load_item_identity> &identities,
	const item_owner_identity &expected_owner, uint64_t owner_revision, bool hydrate_ownership,
	bool complete_snapshot_state, player_load_item_materialize_metrics *metrics)
{
	return materialize_item_graph(character, nullptr, items, identities, expected_owner,
				      owner_revision, hydrate_ownership, complete_snapshot_state,
				      metrics);
}

bool player_load_item_graph_materialize_detached(
	const std::vector<player_item_snapshot> &items,
	const std::vector<player_load_item_identity> &identities,
	const item_owner_identity &expected_owner, uint64_t owner_revision, bool hydrate_ownership,
	bool complete_snapshot_state, std::vector<P_obj> *roots,
	player_load_item_materialize_metrics *metrics)
{
	return materialize_item_graph(nullptr, roots, items, identities, expected_owner,
				      owner_revision, hydrate_ownership, complete_snapshot_state,
				      metrics);
}

bool player_load_item_graph_materialize_creation(const item_transfer_payload &payload,
						 const item_transfer_result &result,
						 std::vector<P_obj> *roots)
{
	if (!roots || !item_owner_identity_valid(payload.from_owner) ||
	    payload.from_owner.type != item_owner_type::system ||
	    payload.to_owner.type != item_owner_type::player ||
	    !item_owner_identity_valid(payload.to_owner) ||
	    payload.reason != item_transfer_reason::creation || !payload.multi_root ||
	    !payload.item_count || payload.item_count > ITEM_TRANSFER_MAX_ITEMS ||
	    result.item_count != payload.item_count ||
	    result.root_item_uid != item_transfer_result_root(payload) ||
	    !result.to_owner_revision || payload.item_blob_size > payload.item_blob.size() ||
	    !payload.item_blob_size || payload.selected_item_uid || payload.target_root_item_uid ||
	    payload.target_parent_item_uid)
		return false;

	std::vector<player_item_snapshot> items;
	std::vector<player_load_item_identity> identities;
	std::unordered_map<uint64_t, size_t> snapshot_indices;
	try
	{
		if (player_item_snapshot_list_decode(payload.item_blob.data(),
						     payload.item_blob_size,
						     &items) != player_snapshot_codec_result::ok ||
		    items.size() != payload.item_count)
			return false;
		for (player_item_snapshot &item : items)
			item.equipment_slot = -1;
		snapshot_indices.reserve(items.size());
		identities.reserve(items.size());
		for (size_t index = 0; index < items.size(); ++index)
		{
			const player_item_snapshot &item = items[index];
			if (!item.object_uid || item.parent_index < PLAYER_SNAPSHOT_NO_PARENT ||
			    item.parent_index >= static_cast<int32_t>(items.size()) ||
			    !snapshot_indices.emplace(item.object_uid, index).second)
				return false;
		}
		for (size_t index = 0; index < items.size(); ++index)
		{
			const player_item_snapshot &item = items[index];
			const auto entry = std::find_if(
				payload.items.begin(), payload.items.begin() + payload.item_count,
				[&](const item_transfer_entry &candidate)
				{ return candidate.item_uid == item.object_uid; });
			if (entry == payload.items.begin() + payload.item_count ||
			    entry->vnum <= 0 || entry->vnum != item.vnum ||
			    entry->expected_item_revision != ITEM_TRANSFER_ABSENT_REVISION ||
			    entry->expected_state != item_custody_state::absent)
				return false;
			const bool root = item.parent_index == PLAYER_SNAPSHOT_NO_PARENT;
			if ((root &&
			     (entry->parent_item_uid || entry->root_item_uid != entry->item_uid)) ||
			    (!root &&
			     entry->parent_item_uid !=
				     items[static_cast<size_t>(item.parent_index)].object_uid))
				return false;
			player_load_item_identity identity = {};
			identity.database_id = index + 1;
			identity.serialized_parent_id =
				root ? 0 : static_cast<uint64_t>(item.parent_index) + 1;
			identity.quantity = 1;
			identity.override_mask = PLAYER_LOAD_ITEM_OVERRIDE_ALL;
			identity.item_uid = entry->item_uid;
			identity.root_item_uid = entry->root_item_uid;
			identity.parent_item_uid = entry->parent_item_uid;
			identity.owner = payload.to_owner;
			identity.item_revision = 1;
			identity.owner_revision = result.to_owner_revision;
			identity.state = item_custody_state::active;
			identities.push_back(identity);
		}
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	player_load_item_materialize_metrics metrics = {};
	return materialize_item_graph(nullptr, roots, items, identities, payload.to_owner,
				      result.to_owner_revision, false, true, &metrics, nullptr,
				      true);
}

bool player_load_item_graph_materialize(P_char character,
					const std::vector<player_item_snapshot> &items,
					const std::vector<player_load_item_identity> &identities,
					int32_t pid, uint64_t owner_revision,
					bool hydrate_ownership,
					player_load_item_materialize_metrics *metrics)
{
	if (pid <= 0)
	{
		if (metrics)
		{
			*metrics = {};
			metrics->item_count = items.size();
			metrics->outcome = player_load_item_materialize_outcome::invalid_snapshot;
		}
		return false;
	}
	return player_load_item_graph_materialize_for_owner(
		character, items, identities,
		{ item_owner_type::player, static_cast<uint64_t>(pid), 0 }, owner_revision,
		hydrate_ownership, false, metrics);
}

unsigned int player_load_items_qualify(player_load_result *result)
{
	if (!result || result->outcome != player_load_outcome::applied ||
	    result->snapshot.items.size() != result->item_identities.size())
		return EINVAL;
	try
	{
		auto &sources = result->item_sources;
		const auto &items = result->snapshot.items;
		const auto &identities = result->item_identities;
		if (result->authoritative_item_count < identities.size())
			return EINVAL;
		// Legacy-pet items share player custody and remain in this counter.
		const size_t other_owned_items =
			result->authoritative_item_count - identities.size();
		std::unordered_map<uint64_t, size_t> source_by_id;
		for (size_t index = 0; index < sources.size(); ++index)
			if (!source_by_id.emplace(sources[index].row_id, index).second)
				return EINVAL;
		std::vector<std::vector<size_t>> neighbors(sources.size());
		const auto connect = [&](uint64_t child, uint64_t parent)
		{
			const auto a = source_by_id.find(child), b = source_by_id.find(parent);
			if (a != source_by_id.end() && b != source_by_id.end())
			{
				neighbors[a->second].push_back(b->second);
				neighbors[b->second].push_back(a->second);
			}
		};
		for (const auto &source : sources)
			connect(source.row_id, source.parent_row_id);
		// Repository filtering omits foreign payloads before the materialized
		// list exists. Qualify those raw sources too, preserving artifact roots.
		const item_owner_identity player = { item_owner_type::player,
						     static_cast<uint64_t>(result->pid), 0 };
		for (auto &source : sources)
		{
			if (source.retain || !source.custody_found ||
			    item_owner_identity_equal(source.custody.owner, player))
				continue;
			artifact_payload_projection projection = {};
			projection.domain = artifact_payload_domain::player;
			projection.row_id = source.row_id;
			projection.parent_row_id = source.parent_row_id;
			projection.item_uid = source.item_uid;
			projection.vnum = source.vnum;
			projection.extra_flags = source.extra_flags;
			projection.extra_flags_present = source.extra_flags_present;
			projection.quantity = source.quantity;
			projection.payload_root_item_uid = source.root_item_uid;
			projection.owner_reference = result->pid;
			projection.payload_owner = player;
			projection.custody_examined = true;
			projection.custody_found = source.custody_found;
			projection.custody_owner_revision_found =
				source.custody_owner_revision_found;
			projection.custody = source.custody;
			if (artifact_player_source_error(projection))
				source.retain = true;
		}
		std::vector<artifact_payload_projection> projections(items.size());
		std::vector<size_t> withheld;
		bool alerted = false;
		for (size_t index = 0; index < items.size(); ++index)
		{
			const auto &item = items[index];
			const auto &identity = identities[index];
			auto &projection = projections[index];
			projection.domain = artifact_payload_domain::player;
			projection.row_id = identity.database_id;
			projection.item_uid = item.object_uid;
			projection.vnum = item.vnum;
			projection.extra_flags = item.extra_flags;
			projection.extra_flags_present = true;
			projection.quantity = identity.quantity;
			projection.owner_reference = result->pid;
			projection.payload_owner = { item_owner_type::player,
						     static_cast<uint64_t>(result->pid), 0 };
			const auto raw = source_by_id.find(identity.database_id);
			if (raw != source_by_id.end())
			{
				const auto &source = sources[raw->second];
				projection.parent_row_id = source.parent_row_id;
				projection.payload_root_item_uid = source.root_item_uid;
				const auto parent = source_by_id.find(source.parent_row_id);
				projection.parent_missing = source.parent_row_id &&
							    parent == source_by_id.end();
				projection.parent_item_uid =
					parent == source_by_id.end() ?
						0 :
						sources[parent->second].item_uid;
				projection.custody_examined = true;
				projection.custody_found = source.custody_found;
				projection.custody_owner_revision_found =
					source.custody_owner_revision_found;
				projection.custody = source.custody;
				projection.parent_owner_disagrees =
					source.item_uid != item.object_uid ||
					source.root_item_uid != identity.root_item_uid ||
					projection.parent_item_uid != identity.parent_item_uid;
			}
			// Preserve components connected by either raw FK ancestry or the
			// custody-reconciled graph; never promote a child of a withheld root.
			if (item.parent_index >= 0)
			{
				if (static_cast<size_t>(item.parent_index) >= identities.size())
					return EINVAL;
				connect(identity.database_id,
					identities[item.parent_index].database_id);
			}
			const unsigned int error = artifact_player_source_error(projection);
			if (error)
			{
				if (raw == source_by_id.end())
					return ENODATA; // No trustworthy retention selector: do not save a loss.
				sources[raw->second].retain = true;
				const char *reason =
					error == EEXIST ? "physical_copy_exists" :
					error == ESTALE ? "custody_or_topology_mismatch" :
							  "canonical_or_source_unavailable";
				if (!alerted)
				{
					persistence_alert(
						AVATAR, "artifact_identity/player_load",
						"saved_source", "none", "none", reason,
						"pid=%d first_vnum=%d source_row=%llu action=retain_source_root",
						result->pid, item.vnum,
						(unsigned long long)identity.database_id);
					alerted = true;
				}
				logit(LOG_ARTIFACT,
				      "artifact_identity/player_load: pid=%d vnum=%d uid=%llu row=%llu error=%u reason=%s outcome=source_retained",
				      result->pid, item.vnum, (unsigned long long)item.object_uid,
				      (unsigned long long)identity.database_id, error, reason);
			}
		}
		std::vector<bool> held(sources.size(), false);
		for (size_t index = 0; index < sources.size(); ++index)
			if (sources[index].retain)
			{
				held[index] = true;
				withheld.push_back(index);
			}
		for (size_t cursor = 0; cursor < withheld.size(); ++cursor)
			for (size_t adjacent : neighbors[withheld[cursor]])
				if (!held[adjacent])
				{
					held[adjacent] = true;
					withheld.push_back(adjacent);
				}
		for (size_t index : withheld)
			sources[index].retain = true;
		const unsigned int retained_error =
			player_load_retain_item_roots(sources, &result->snapshot.retained_items);
		if (retained_error)
			return retained_error;
		std::vector<player_item_snapshot> kept;
		std::vector<player_load_item_identity> kept_identities;
		std::vector<artifact_payload_projection> admitted;
		std::vector<size_t> remap(items.size());
		for (size_t index = 0; index < items.size(); ++index)
		{
			const auto raw = source_by_id.find(identities[index].database_id);
			if (raw != source_by_id.end() && held[raw->second])
				continue;
			remap[index] = kept.size();
			kept.push_back(items[index]);
			kept_identities.push_back(identities[index]);
			admitted.push_back(projections[index]);
		}
		for (auto &item : kept)
			if (item.parent_index >= 0)
				item.parent_index = static_cast<int32_t>(remap[item.parent_index]);
		result->snapshot.items = std::move(kept);
		result->item_identities = std::move(kept_identities);
		result->item_admission_sources = std::move(admitted);
		result->authoritative_item_count =
			other_owned_items + result->item_identities.size();
		return 0;
	}
	catch (const std::bad_alloc &)
	{
		return ENOMEM;
	}
}

bool player_load_item_graph_materialize_player(P_char character, const player_load_result &result,
					       bool hydrate_ownership,
					       player_load_item_materialize_metrics *metrics)
{
	return materialize_item_graph(
		character, nullptr, result.snapshot.items, result.item_identities,
		{ item_owner_type::player, static_cast<uint64_t>(result.pid), 0 },
		result.item_owner_revision, hydrate_ownership, false, metrics,
		&result.item_admission_sources);
}

bool player_load_items_materialize(P_char character, const player_load_result &result,
				   player_load_item_materialize_metrics *metrics)
{
	return player_load_item_graph_materialize_player(character, result, true, metrics);
}

void player_load_items_notify_retained(P_char character)
{
	if (character && IS_PC(character) && character->only.pc && character->desc &&
	    character->only.pc->retained_items)
		send_to_char(
			"Some saved items need staff review and remain in storage. Reference: player_load/retained.\r\n",
			character);
}

void player_load_items_activate_equipment(P_char character)
{
	if (!character)
		return;
	for (int slot = 0; slot < MAX_WEAR; ++slot)
	{
		P_obj object = character->equipment[slot];
		obj_affect *affect = object ? get_obj_affect(object, SKILL_ENCHANT) : nullptr;
		if (!affect)
			continue;
		act("&+YA magical aura forms around your body.&n", FALSE, character, object, 0,
		    TO_CHAR);
		((*skills[affect->data].spell_pointer)(static_cast<int>(GET_LEVEL(character)),
						       character, 0, SPELL_TYPE_SPELL, character,
						       0));
	}
}

void player_load_items_discard(P_char character)
{
	if (!character)
		return;
	for (int slot = 0; slot < MAX_WEAR; ++slot)
		if (character->equipment[slot])
		{
			P_obj object = character->equipment[slot];
			character->equipment[slot] = nullptr;
			object->loc_p = LOC_NOWHERE;
			object->loc.wearing = nullptr;
			clear_item_uids(object);
			extract_obj(object, FALSE);
		}
	while (character->carrying)
	{
		P_obj object = character->carrying;
		character->carrying = object->next_content;
		object->next_content = nullptr;
		object->loc_p = LOC_NOWHERE;
		object->loc.carrying = nullptr;
		clear_item_uids(object);
		extract_obj(object, FALSE);
	}
	GET_CARRYING_W(character) = 0;
	IS_CARRYING_N(character) = 0;
}
