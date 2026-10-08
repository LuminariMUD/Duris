/****************************************************************************
 *
 *  File: item_transfer_command.c                               Part of Duris
 *  Usage: encodes and decodes item transfer commands
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "item/item_transfer_command.h"

#include "player/player_snapshot_codec.h"

#include <openssl/sha.h>

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <new>
#include <utility>

namespace
{
constexpr size_t FROM_OFFSET = 0;
constexpr size_t TO_OFFSET = 17;
constexpr size_t REASON_OFFSET = 34;
constexpr size_t COUNT_OFFSET = 36;
constexpr size_t REASON_ID_OFFSET = 40;
constexpr size_t FROM_REVISION_OFFSET = 48;
constexpr size_t TO_REVISION_OFFSET = 56;
constexpr size_t SELECTED_ITEM_OFFSET = 64;
constexpr size_t TARGET_ROOT_OFFSET = 72;
constexpr size_t TARGET_PARENT_OFFSET = 80;
constexpr size_t TARGET_PARENT_REVISION_OFFSET = 88;

void put_u16(uint8_t *output, uint16_t value)
{
	output[0] = static_cast<uint8_t>(value);
	output[1] = static_cast<uint8_t>(value >> 8);
}

void put_u32(uint8_t *output, uint32_t value)
{
	for (unsigned int byte = 0; byte < 4; ++byte)
		output[byte] = static_cast<uint8_t>(value >> (byte * 8));
}

void put_u64(uint8_t *output, uint64_t value)
{
	for (unsigned int byte = 0; byte < 8; ++byte)
		output[byte] = static_cast<uint8_t>(value >> (byte * 8));
}

uint16_t get_u16(const uint8_t *input)
{
	return static_cast<uint16_t>(input[0]) |
	       static_cast<uint16_t>(static_cast<uint16_t>(input[1]) << 8);
}

uint32_t get_u32(const uint8_t *input)
{
	uint32_t value = 0;
	for (unsigned int byte = 0; byte < 4; ++byte)
		value |= static_cast<uint32_t>(input[byte]) << (byte * 8);
	return value;
}

uint64_t get_u64(const uint8_t *input)
{
	uint64_t value = 0;
	for (unsigned int byte = 0; byte < 8; ++byte)
		value |= static_cast<uint64_t>(input[byte]) << (byte * 8);
	return value;
}

void encode_owner(uint8_t *output, const item_owner_identity &owner)
{
	output[0] = static_cast<uint8_t>(owner.type);
	put_u64(output + 1, owner.id);
	put_u64(output + 9, owner.context_id);
}

item_owner_identity decode_owner(const uint8_t *input)
{
	return { static_cast<item_owner_type>(input[0]), get_u64(input + 1), get_u64(input + 9) };
}

critical_entity_type entity_type_for_owner(item_owner_type type)
{
	switch (type)
	{
	case item_owner_type::player:
		return critical_entity_type::player;
	case item_owner_type::container:
		return critical_entity_type::item;
	case item_owner_type::corpse:
		return critical_entity_type::corpse;
	case item_owner_type::locker:
		return critical_entity_type::locker;
	case item_owner_type::auction:
		return critical_entity_type::auction;
	case item_owner_type::room:
		return critical_entity_type::room;
	case item_owner_type::shopkeeper:
		return critical_entity_type::shopkeeper;
	case item_owner_type::collector:
		return critical_entity_type::collector;
	case item_owner_type::pet:
		return critical_entity_type::pet;
	default:
		return critical_entity_type::system;
	}
}

// Item transfer commands create (grants), repair (operator repairs) and destroy
// (character deletion): the other reasons are recorded only by the commands that own them.
bool valid_reason(item_transfer_reason reason)
{
	return reason == item_transfer_reason::creation ||
	       reason == item_transfer_reason::operator_repair ||
	       reason == item_transfer_reason::destruction;
}

const item_transfer_entry *find_payload_item(const item_transfer_payload &payload,
					     uint64_t item_uid)
{
	auto found = std::lower_bound(payload.items.begin(),
				      payload.items.begin() + payload.item_count, item_uid,
				      [](const item_transfer_entry &entry, uint64_t uid)
				      { return entry.item_uid < uid; });
	return found != payload.items.begin() + payload.item_count && found->item_uid == item_uid ?
		       &*found :
		       nullptr;
}

uint64_t selected_root_for(const item_transfer_payload &payload, uint64_t item_uid)
{
	if (!payload.multi_root)
		return payload.selected_item_uid ? payload.selected_item_uid :
						   payload.items[0].root_item_uid;
	const item_transfer_entry *entry = find_payload_item(payload, item_uid);
	for (size_t depth = 0; entry && depth <= payload.item_count; ++depth)
	{
		const item_transfer_entry *parent =
			find_payload_item(payload, entry->parent_item_uid);
		if (!parent)
			return entry->item_uid;
		entry = parent;
	}
	return 0;
}

bool target_topology_for(const item_transfer_payload &payload, uint64_t item_uid,
			 uint64_t *root_item_uid, uint64_t *parent_item_uid)
{
	const item_transfer_entry *entry = find_payload_item(payload, item_uid);
	const uint64_t selected_root = selected_root_for(payload, item_uid);
	if (!entry || !selected_root || !root_item_uid || !parent_item_uid)
		return false;
	*root_item_uid = payload.target_parent_item_uid ? payload.target_root_item_uid :
							  selected_root;
	*parent_item_uid = item_uid == selected_root ? payload.target_parent_item_uid :
						       entry->parent_item_uid;
	return *root_item_uid != 0;
}

bool validate_payload(const item_transfer_payload &payload)
{
	if (!item_owner_identity_valid(payload.from_owner) ||
	    !item_owner_identity_valid(payload.to_owner) || !valid_reason(payload.reason) ||
	    !payload.item_count || payload.item_count > ITEM_TRANSFER_MAX_ITEMS ||
	    payload.item_blob_size > payload.item_blob.size() ||
	    payload.from_owner.type == item_owner_type::collector ||
	    payload.to_owner.type == item_owner_type::collector ||
	    payload.from_owner.type == item_owner_type::pet ||
	    payload.to_owner.type == item_owner_type::pet)
		return false;
	const bool creation = payload.from_owner.type == item_owner_type::system;
	const bool destruction = payload.to_owner.type == item_owner_type::destruction;
	if (payload.to_owner.type == item_owner_type::system ||
	    payload.from_owner.type == item_owner_type::destruction ||
	    (payload.reason == item_transfer_reason::creation) != creation ||
	    (payload.reason == item_transfer_reason::destruction) != destruction ||
	    ((creation || destruction) &&
	     item_owner_identity_equal(payload.from_owner, payload.to_owner)))
		return false;
	if (payload.multi_root)
	{
		// A starter kit is created, and a deleted owner's items destroyed, in one batch.
		if (payload.selected_item_uid || (!creation && !destruction) ||
		    (creation &&
		     (payload.to_owner.type != item_owner_type::player ||
		      payload.target_root_item_uid || payload.target_parent_item_uid)) ||
		    (payload.target_parent_item_uid ? !payload.target_root_item_uid :
						      payload.target_root_item_uid != 0))
			return false;
		for (size_t index = 0; index < payload.item_count; ++index)
		{
			const item_transfer_entry &entry = payload.items[index];
			if (!entry.item_uid || !entry.root_item_uid || entry.vnum <= 0 ||
			    (creation ? (entry.expected_item_revision !=
						 ITEM_TRANSFER_ABSENT_REVISION ||
					 entry.expected_state != item_custody_state::absent) :
					entry.expected_state != item_custody_state::active) ||
			    (index && payload.items[index - 1].item_uid >= entry.item_uid) ||
			    entry.item_uid == payload.target_parent_item_uid)
				return false;
			if (creation)
			{
				const uint64_t selected_root =
					selected_root_for(payload, entry.item_uid);
				const item_transfer_entry *root =
					find_payload_item(payload, selected_root);
				uint64_t target_root = 0, target_parent = 0;
				if (!root || selected_root != entry.root_item_uid ||
				    root->root_item_uid != root->item_uid ||
				    root->parent_item_uid ||
				    !target_topology_for(payload, entry.item_uid, &target_root,
							 &target_parent) ||
				    target_root != entry.root_item_uid ||
				    target_parent != entry.parent_item_uid)
					return false;
				continue;
			}
			const uint64_t selected_root = selected_root_for(payload, entry.item_uid);
			const item_transfer_entry *selected =
				find_payload_item(payload, selected_root);
			if (!selected || selected->root_item_uid != entry.root_item_uid)
				return false;
			uint64_t target_root = 0, target_parent = 0;
			if (!target_topology_for(payload, entry.item_uid, &target_root,
						 &target_parent))
				return false;
		}
		return true;
	}
	const uint64_t source_root = payload.items[0].root_item_uid;
	const uint64_t selected = payload.selected_item_uid ? payload.selected_item_uid :
							      source_root;
	const uint64_t target_root = payload.target_root_item_uid ? payload.target_root_item_uid :
								    selected;
	if (!source_root || !selected || !target_root ||
	    (!payload.target_parent_item_uid && target_root != selected))
		return false;
	bool found_selected = false;
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		const item_transfer_entry &entry = payload.items[index];
		if (!entry.item_uid || entry.root_item_uid != source_root || entry.vnum <= 0 ||
		    entry.expected_state !=
			    (creation ? item_custody_state::absent : item_custody_state::active) ||
		    (creation && entry.expected_item_revision != ITEM_TRANSFER_ABSENT_REVISION))
			return false;
		if (index && payload.items[index - 1].item_uid >= entry.item_uid)
			return false;
		if (entry.item_uid == payload.target_parent_item_uid)
			return false;
		if (entry.item_uid == selected)
		{
			if (found_selected)
				return false;
			found_selected = true;
		}
		else if (!entry.parent_item_uid)
			return false;
	}
	if (!found_selected || (creation && selected != source_root))
		return false;
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		if (payload.items[index].item_uid == selected)
			continue;
		uint64_t ancestor_uid = payload.items[index].parent_item_uid;
		bool reaches_root = false;
		for (size_t depth = 0; depth < payload.item_count; ++depth)
		{
			if (ancestor_uid == selected)
			{
				reaches_root = true;
				break;
			}
			auto parent = std::find_if(payload.items.begin(),
						   payload.items.begin() + payload.item_count,
						   [&](const item_transfer_entry &candidate)
						   { return candidate.item_uid == ancestor_uid; });
			if (parent == payload.items.begin() + payload.item_count)
				break;
			ancestor_uid = parent->parent_item_uid;
		}
		if (!reaches_root)
			return false;
	}
	return true;
}
} // namespace

uint64_t item_transfer_selected_root(const item_transfer_payload &payload, uint64_t item_uid)
{
	return selected_root_for(payload, item_uid);
}

bool item_transfer_selected_roots(const item_transfer_payload &payload,
				  std::vector<uint64_t> *roots)
{
	if (!roots)
		return false;
	try
	{
		roots->clear();
		roots->reserve(payload.item_count);
		for (size_t index = 0; index < payload.item_count; ++index)
			if (selected_root_for(payload, payload.items[index].item_uid) ==
			    payload.items[index].item_uid)
				roots->push_back(payload.items[index].item_uid);
		std::sort(roots->begin(), roots->end());
		roots->erase(std::unique(roots->begin(), roots->end()), roots->end());
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	return !roots->empty();
}

uint64_t item_transfer_result_root(const item_transfer_payload &payload)
{
	uint64_t result = 0;
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		const uint64_t selected_root =
			selected_root_for(payload, payload.items[index].item_uid);
		if (!selected_root)
			return 0;
		if (!result || selected_root < result)
			result = selected_root;
	}
	return result;
}

bool item_transfer_target_topology(const item_transfer_payload &payload, uint64_t item_uid,
				   uint64_t *root_item_uid, uint64_t *parent_item_uid)
{
	return target_topology_for(payload, item_uid, root_item_uid, parent_item_uid);
}

bool item_owner_identity_valid(const item_owner_identity &owner)
{
	if (owner.type <= item_owner_type::unknown || owner.type > item_owner_type::pet)
		return false;
	if (owner.type == item_owner_type::system || owner.type == item_owner_type::destruction)
		return owner.id == 0 && owner.context_id == 0;
	if (owner.type == item_owner_type::collector)
		return owner.id != 0 && owner.context_id == 0;
	if (owner.type == item_owner_type::pet)
		return owner.id != 0 && owner.context_id != 0 && owner.context_id <= INT32_MAX;
	return owner.id != 0;
}

bool item_owner_identity_equal(const item_owner_identity &left, const item_owner_identity &right)
{
	return left.type == right.type && left.id == right.id &&
	       left.context_id == right.context_id;
}

uint64_t item_corpse_owner_id(uint32_t player_pid, uint32_t corpse_save_id)
{
	if (!player_pid || !corpse_save_id)
		return 0;
	return (static_cast<uint64_t>(player_pid) << 32) | corpse_save_id;
}

uint64_t item_shopkeeper_owner_id(uint32_t shop_id)
{
	return static_cast<uint64_t>(shop_id) + 1;
}

uint64_t item_collector_owner_id(uint64_t listing_id)
{
	return listing_id;
}

bool item_owner_key(const item_owner_identity &owner, critical_entity_key *key)
{
	if (!key || !item_owner_identity_valid(owner))
		return false;
	if (owner.id && !owner.context_id)
	{
		*key = { entity_type_for_owner(owner.type), owner.id };
		return true;
	}
	std::array<uint8_t, 17> encoded = {};
	encode_owner(encoded.data(), owner);
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(encoded.data(), encoded.size(), digest.data());
	uint64_t identity = get_u64(digest.data());
	if (!identity)
		identity = 1;
	*key = { entity_type_for_owner(owner.type), identity };
	return true;
}

namespace
{
bool populate_command_entities(critical_command *command, const item_transfer_payload &payload)
{
	critical_entity_key from_key = {}, to_key = {};
	if (!command || !item_owner_key(payload.from_owner, &from_key) ||
	    !item_owner_key(payload.to_owner, &to_key))
		return false;
	command->keys = { from_key, to_key };
	command->expected_revisions = { { from_key, payload.expected_from_revision },
					{ to_key, payload.expected_to_revision } };
	if (item_owner_identity_equal(payload.from_owner, payload.to_owner))
	{
		if (payload.expected_from_revision != payload.expected_to_revision)
			return false;
		command->keys.pop_back();
		command->expected_revisions.pop_back();
	}
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		critical_entity_key item_key = { critical_entity_type::item,
						 payload.items[index].item_uid };
		command->keys.push_back(item_key);
		command->expected_revisions.push_back(
			{ item_key, payload.items[index].expected_item_revision });
	}
	if (payload.target_parent_item_uid)
	{
		critical_entity_key parent_key = { critical_entity_type::item,
						   payload.target_parent_item_uid };
		command->keys.push_back(parent_key);
		command->expected_revisions.push_back(
			{ parent_key, payload.expected_target_parent_revision });
	}
	std::sort(command->keys.begin(), command->keys.end(), critical_entity_key_less);
	if (std::adjacent_find(command->keys.begin(), command->keys.end(),
			       critical_entity_key_equal) != command->keys.end())
		return false;
	std::sort(command->expected_revisions.begin(), command->expected_revisions.end(),
		  [](const critical_expected_revision &left,
		     const critical_expected_revision &right)
		  { return critical_entity_key_less(left.key, right.key); });
	return true;
}
} // namespace

bool item_transfer_command_encode_payload(const item_transfer_payload &payload,
					  std::vector<uint8_t> *encoded)
{
	if (!encoded || !validate_payload(payload))
		return false;
	const size_t item_section_size =
		ITEM_TRANSFER_HEADER_BYTES + payload.item_count * ITEM_TRANSFER_ENTRY_BYTES;
	const size_t payload_size = item_section_size + sizeof(uint32_t) + payload.item_blob_size;
	if (payload_size > CRITICAL_COMMAND_MAX_PAYLOAD_BYTES)
		return false;
	encoded->assign(payload_size, 0);
	encode_owner(encoded->data() + FROM_OFFSET, payload.from_owner);
	encode_owner(encoded->data() + TO_OFFSET, payload.to_owner);
	put_u16(encoded->data() + REASON_OFFSET, static_cast<uint16_t>(payload.reason));
	put_u16(encoded->data() + COUNT_OFFSET, payload.item_count);
	put_u64(encoded->data() + REASON_ID_OFFSET, static_cast<uint64_t>(payload.reason_id));
	put_u64(encoded->data() + FROM_REVISION_OFFSET, payload.expected_from_revision);
	put_u64(encoded->data() + TO_REVISION_OFFSET, payload.expected_to_revision);
	const uint64_t selected = payload.multi_root ? 0 :
						       (payload.selected_item_uid ?
								payload.selected_item_uid :
								payload.items[0].root_item_uid);
	put_u64(encoded->data() + SELECTED_ITEM_OFFSET, selected);
	put_u64(encoded->data() + TARGET_ROOT_OFFSET,
		payload.multi_root ?
			payload.target_root_item_uid :
			(payload.target_root_item_uid ? payload.target_root_item_uid : selected));
	put_u64(encoded->data() + TARGET_PARENT_OFFSET, payload.target_parent_item_uid);
	put_u64(encoded->data() + TARGET_PARENT_REVISION_OFFSET,
		payload.expected_target_parent_revision);
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		const item_transfer_entry &entry = payload.items[index];
		uint8_t *output = encoded->data() + ITEM_TRANSFER_HEADER_BYTES +
				  index * ITEM_TRANSFER_ENTRY_BYTES;
		put_u64(output, entry.item_uid);
		put_u64(output + 8, entry.root_item_uid);
		put_u64(output + 16, entry.parent_item_uid);
		put_u64(output + 24, entry.expected_item_revision);
		put_u32(output + 32, static_cast<uint32_t>(entry.vnum));
		output[36] = static_cast<uint8_t>(entry.expected_state);
	}
	put_u32(encoded->data() + item_section_size, payload.item_blob_size);
	std::copy_n(payload.item_blob.begin(), payload.item_blob_size,
		    encoded->begin() + item_section_size + sizeof(uint32_t));
	return true;
}

bool item_transfer_command_decode_payload(const critical_command &command,
					  item_transfer_payload *payload)
{
	if (!payload || command.type != critical_command_type::item_transfer ||
	    command.payload_version != ITEM_TRANSFER_PAYLOAD_VERSION ||
	    command.payload.size() <
		    ITEM_TRANSFER_HEADER_BYTES + ITEM_TRANSFER_ENTRY_BYTES + sizeof(uint32_t))
		return false;
	*payload = {};
	payload->from_owner = decode_owner(command.payload.data() + FROM_OFFSET);
	payload->to_owner = decode_owner(command.payload.data() + TO_OFFSET);
	payload->reason =
		static_cast<item_transfer_reason>(get_u16(command.payload.data() + REASON_OFFSET));
	payload->item_count = get_u16(command.payload.data() + COUNT_OFFSET);
	payload->reason_id =
		static_cast<int64_t>(get_u64(command.payload.data() + REASON_ID_OFFSET));
	payload->expected_from_revision = get_u64(command.payload.data() + FROM_REVISION_OFFSET);
	payload->expected_to_revision = get_u64(command.payload.data() + TO_REVISION_OFFSET);
	payload->selected_item_uid = get_u64(command.payload.data() + SELECTED_ITEM_OFFSET);
	payload->target_root_item_uid = get_u64(command.payload.data() + TARGET_ROOT_OFFSET);
	payload->target_parent_item_uid = get_u64(command.payload.data() + TARGET_PARENT_OFFSET);
	payload->expected_target_parent_revision =
		get_u64(command.payload.data() + TARGET_PARENT_REVISION_OFFSET);
	payload->multi_root = payload->selected_item_uid == 0;
	if (!payload->item_count || payload->item_count > ITEM_TRANSFER_MAX_ITEMS)
		return false;
	const size_t item_section_size =
		ITEM_TRANSFER_HEADER_BYTES + payload->item_count * ITEM_TRANSFER_ENTRY_BYTES;
	if (command.payload.size() < item_section_size + sizeof(uint32_t))
		return false;
	for (size_t index = 0; index < payload->item_count; ++index)
	{
		const uint8_t *input = command.payload.data() + ITEM_TRANSFER_HEADER_BYTES +
				       index * ITEM_TRANSFER_ENTRY_BYTES;
		payload->items[index] = { get_u64(input),
					  get_u64(input + 8),
					  get_u64(input + 16),
					  get_u64(input + 24),
					  static_cast<int32_t>(get_u32(input + 32)),
					  static_cast<item_custody_state>(input[36]) };
		if (input[37] || input[38] || input[39])
			return false;
	}
	payload->item_blob_size = get_u32(command.payload.data() + item_section_size);
	if (payload->item_blob_size > payload->item_blob.size() ||
	    command.payload.size() !=
		    item_section_size + sizeof(uint32_t) + payload->item_blob_size)
		return false;
	std::copy_n(command.payload.begin() + item_section_size + sizeof(uint32_t),
		    payload->item_blob_size, payload->item_blob.begin());
	if (!validate_payload(*payload) || command.expected_revisions.size() != command.keys.size())
		return false;
	critical_command expected = {};
	if (!populate_command_entities(&expected, *payload))
		return false;
	return command.keys.size() == expected.keys.size() &&
	       command.expected_revisions.size() == expected.expected_revisions.size() &&
	       std::equal(command.keys.begin(), command.keys.end(), expected.keys.begin(),
			  [](const critical_entity_key &left, const critical_entity_key &right)
			  { return critical_entity_key_equal(left, right); }) &&
	       std::equal(command.expected_revisions.begin(), command.expected_revisions.end(),
			  expected.expected_revisions.begin(),
			  [](const critical_expected_revision &left,
			     const critical_expected_revision &right) {
				  return critical_entity_key_equal(left.key, right.key) &&
					 left.revision == right.revision;
			  });
}

bool item_transfer_command_encode_result(const item_transfer_result &result,
					 std::array<uint8_t, ITEM_TRANSFER_RESULT_BYTES> *encoded)
{
	if (!encoded || !result.root_item_uid || !result.item_count ||
	    result.item_count > ITEM_TRANSFER_MAX_ITEMS)
		return false;
	encoded->fill(0);
	put_u64(encoded->data(), result.root_item_uid);
	put_u16(encoded->data() + 8, result.item_count);
	put_u64(encoded->data() + 16, result.from_owner_revision);
	put_u64(encoded->data() + 24, result.to_owner_revision);
	put_u64(encoded->data() + 32, result.max_item_revision);
	put_u64(encoded->data() + 40, result.corpse_revision);
	(*encoded)[10] = result.collector_catalog_changed ? 1 : 0;
	return true;
}

bool item_transfer_command_decode_result(const uint8_t *encoded, size_t size,
					 item_transfer_result *result)
{
	if (!encoded || size != ITEM_TRANSFER_RESULT_BYTES || !result || encoded[10] > 1 ||
	    encoded[11] || encoded[12] || encoded[13] || encoded[14] || encoded[15])
		return false;
	*result = { get_u64(encoded),	   get_u16(encoded + 8),  get_u64(encoded + 16),
		    get_u64(encoded + 24), get_u64(encoded + 32), get_u64(encoded + 40),
		    encoded[10] != 0 };
	return result->root_item_uid && result->item_count &&
	       result->item_count <= ITEM_TRANSFER_MAX_ITEMS;
}

bool item_transfer_command_build(critical_command *command, critical_operation_id operation_id,
				 const item_transfer_payload &payload,
				 critical_source_site source_site,
				 critical_deadline_class deadline_class)
{
	if (!command || critical_operation_id_is_zero(operation_id))
		return false;
	std::vector<uint8_t> encoded;
	if (!item_transfer_command_encode_payload(payload, &encoded))
		return false;
	*command = { .schema_version = CRITICAL_COMMAND_SCHEMA_VERSION,
		     .operation_id = operation_id,
		     .type = critical_command_type::item_transfer,
		     .payload_version = ITEM_TRANSFER_PAYLOAD_VERSION,
		     .source_site = source_site,
		     .deadline_class = deadline_class,
		     .accepted_at_usec = 0,
		     .keys = {},
		     .expected_revisions = {},
		     .payload = std::move(encoded) };
	return populate_command_entities(command, payload);
}
