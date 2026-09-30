#include "flatfile/flatfile_player_repository.h"

#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_item_repository.h"
#include "flatfile/flatfile_player_domain_repository.h"
#include "flatfile/flatfile_shop_trade_materialization.h"
#include "flatfile/flatfile_store.h"
#include "persistence/persistence_observability.h"
#include "persistence/dupe_log.h"
#include "persistence/persistence_mode.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <climits>
#include <cstring>
#include <limits>
#include <memory>
#include <mutex>
#include <new>
#include <numeric>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace
{
using namespace flatfile_player_snapshot_file;
std::mutex player_mutex;

struct encoder
{
	std::vector<uint8_t> bytes;

	template <typename T> void number(T value)
	{
		using unsigned_type = std::make_unsigned_t<T>;
		unsigned_type bits = static_cast<unsigned_type>(value);
		for (size_t index = 0; index < sizeof(T); ++index)
		{
			bytes.push_back(static_cast<uint8_t>(bits & 0xff));
			bits >>= 8;
		}
	}
};

std::string player_lock_filename(int32_t pid)
{
	return ".player-" + std::to_string(pid) + ".lock";
}

bool valid_snapshot(const player_snapshot &snapshot)
{
	const uint32_t required = snapshot.death ? PLAYER_SNAPSHOT_DEATH_SCHEMA_VERSION :
						   PLAYER_SNAPSHOT_SCHEMA_VERSION;
	return snapshot.schema_version == required && snapshot.pid > 0 && snapshot.revision &&
	       snapshot.components && !(snapshot.components & ~PLAYER_CHECKPOINT_COMPONENT_ALL) &&
	       snapshot.encoded_size_bound &&
	       snapshot.encoded_size_bound <= PLAYER_SNAPSHOT_MAX_BYTES &&
	       (!snapshot.death || !snapshot.death->corpse.empty());
}

bool same_authority_key(const std::string &left, const std::string &right)
{
	if (left.size() != right.size())
		return false;
	for (size_t index = 0; index < left.size(); ++index)
	{
		unsigned char left_character = left[index];
		unsigned char right_character = right[index];
		if (left_character >= 'A' && left_character <= 'Z')
			left_character = static_cast<unsigned char>(left_character - 'A' + 'a');
		if (right_character >= 'A' && right_character <= 'Z')
			right_character = static_cast<unsigned char>(right_character - 'A' + 'a');
		if (left_character != right_character)
			return false;
	}
	return true;
}

const std::string *snapshot_player_name(const player_snapshot &snapshot)
{
	const std::string *name = nullptr;
	for (const player_snapshot_string &entry : snapshot.status_strings)
		if (entry.field == player_status_string_field::name)
		{
			if (name)
				return nullptr;
			name = &entry.value;
		}
	return name;
}

bool snapshot_unsigned(const player_snapshot &snapshot, player_status_field field, uint64_t *value)
{
	bool found = false;
	for (const player_snapshot_integer &entry : snapshot.status_integers)
		if (entry.field == field)
		{
			if (found || (!entry.is_unsigned && entry.signed_value < 0))
				return false;
			*value = entry.is_unsigned ? entry.unsigned_value :
						     static_cast<uint64_t>(entry.signed_value);
			found = true;
		}
	return found;
}

bool snapshot_signed(const player_snapshot &snapshot, player_status_field field, int64_t *value)
{
	bool found = false;
	for (const player_snapshot_integer &entry : snapshot.status_integers)
		if (entry.field == field)
		{
			if (found || (entry.is_unsigned && entry.unsigned_value > INT64_MAX))
				return false;
			*value = entry.is_unsigned ? static_cast<int64_t>(entry.unsigned_value) :
						     entry.signed_value;
			found = true;
		}
	return found;
}

player_load_result identity_failure(const player_load_request &request,
				    flatfile_identity_result failure)
{
	player_load_result result = {};
	result.request_id = request.request_id;
	result.pid = request.pid;
	result.failed_component = "identity";
	switch (failure)
	{
	case flatfile_identity_result::not_found:
		result.outcome = player_load_outcome::not_found;
		result.error_code = ENOENT;
		break;
	case flatfile_identity_result::io_error:
		result.outcome = player_load_outcome::retryable_failure;
		result.error_code = EIO;
		break;
	case flatfile_identity_result::ok:
	case flatfile_identity_result::conflict:
	case flatfile_identity_result::unchanged:
	case flatfile_identity_result::invalid:
	case flatfile_identity_result::exhausted:
		result.outcome = player_load_outcome::component_failure;
		result.error_code = EILSEQ;
		break;
	}
	return result;
}

// A load takes a payload item when the ownership catalog has no record for it or
// names this owner, whatever the record's state. A record naming anyone else makes
// the item a stale or duplicate copy: it is skipped, logged to logs/log/dupes, and
// the contents of a skipped container move to the top level.
bool build_item_identities(
	std::vector<player_item_snapshot> *items,
	const std::unordered_map<uint64_t, flatfile_item_ownership_record> &catalog,
	const item_owner_identity &owner, uint64_t owner_revision, uint64_t *next_database_id,
	std::unordered_set<uint64_t> *consumed, std::vector<player_load_item_identity> *identities,
	player_load_result *result)
{
	if (!items || !next_database_id || !consumed || !identities || !result)
		return false;
	constexpr size_t skipped_index = static_cast<size_t>(-1);
	std::vector<uint64_t> database_ids;
	std::vector<size_t> remap;
	std::vector<player_item_snapshot> kept;
	try
	{
		database_ids.reserve(items->size());
		remap.reserve(items->size());
		kept.reserve(items->size());
		identities->reserve(items->size());
		for (size_t index = 0; index < items->size(); ++index)
		{
			player_item_snapshot item = std::move((*items)[index]);
			if (*next_database_id > static_cast<uint64_t>(INT_MAX))
				return false;
			size_t parent_new = skipped_index;
			if (item.parent_index != PLAYER_SNAPSHOT_NO_PARENT)
			{
				if (item.parent_index < 0 ||
				    static_cast<size_t>(item.parent_index) >= index)
					return false;
				parent_new = remap[static_cast<size_t>(item.parent_index)];
			}
			const auto found = catalog.find(item.object_uid);
			const bool recorded = found != catalog.end();
			const bool elsewhere =
				recorded && !item_owner_identity_equal(found->second.owner, owner);
			if (!item.object_uid || item.vnum <= 0 || elsewhere ||
			    consumed->count(item.object_uid))
			{
				if (elsewhere)
					dupe_log_item("load_skipped", item.object_uid, item.vnum,
						      owner, found->second.owner);
				remap.push_back(skipped_index);
				++result->stale_item_rows;
				continue;
			}
			consumed->insert(item.object_uid);
			uint64_t serialized_parent = 0;
			uint64_t parent_uid = 0;
			if (parent_new != skipped_index)
			{
				serialized_parent = database_ids[parent_new];
				parent_uid = kept[parent_new].object_uid;
			}
			else if (item.parent_index != PLAYER_SNAPSHOT_NO_PARENT)
				++result->promoted_item_rows;
			// A recorded item keeps the catalog's placement; an unrecorded one sits
			// where the player file puts it.
			item.parent_index = parent_new == skipped_index ?
						    PLAYER_SNAPSHOT_NO_PARENT :
						    static_cast<int32_t>(parent_new);
			const uint64_t database_id = (*next_database_id)++;
			database_ids.push_back(database_id);
			remap.push_back(kept.size());
			identities->push_back(
				{ database_id, serialized_parent, 1, PLAYER_LOAD_ITEM_OVERRIDE_ALL,
				  item.object_uid,
				  recorded && found->second.root_item_uid ?
					  found->second.root_item_uid :
					  item.object_uid,
				  recorded ? found->second.parent_item_uid : parent_uid, owner,
				  recorded ? found->second.item_revision : 0, owner_revision,
				  item_custody_state::active });
			kept.push_back(std::move(item));
		}
		*items = std::move(kept);
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	return player_load_reconcile_item_topology(items, identities, &result->promoted_item_rows,
						   &result->repaired_item_rows);
}

bool reconcile_item_ownership(const std::string &root, player_load_result *result)
{
	if (!result || result->pid <= 0)
		return false;
	const item_owner_identity owner = { item_owner_type::player,
					    static_cast<uint64_t>(result->pid), 0 };
	uint64_t owner_revision = 0;
	std::vector<flatfile_item_ownership_record> records;
	std::string error;
	flatfile_authority_lock authority;
	if (!authority.acquire(root, &error))
	{
		result->outcome = player_load_outcome::retryable_failure;
		result->error_code = EIO;
		result->failed_component = "item_ownership";
		return false;
	}
	const auto recovered = flatfile_authority_transaction_recover(root, authority, &error);
	if (recovered != flatfile_authority_transaction_result::ok)
	{
		result->outcome = recovered == flatfile_authority_transaction_result::io_error ?
					  player_load_outcome::retryable_failure :
					  player_load_outcome::component_failure;
		result->error_code =
			recovered == flatfile_authority_transaction_result::io_error ? EIO : EILSEQ;
		result->failed_component = "item_ownership";
		return false;
	}
	const flatfile_item_repository_result loaded = flatfile_item_repository_load_owner_locked(
		root, authority, owner, &owner_revision, &records, &error);
	// An owner nobody has recorded yet simply holds nothing in the catalog.
	if (loaded != flatfile_item_repository_result::ok &&
	    loaded != flatfile_item_repository_result::not_found)
	{
		result->outcome = loaded == flatfile_item_repository_result::io_error ?
					  player_load_outcome::retryable_failure :
					  player_load_outcome::component_failure;
		result->error_code = loaded == flatfile_item_repository_result::io_error ? EIO :
											   EILSEQ;
		result->failed_component = "item_ownership";
		return false;
	}
	const auto materialized = flatfile_shop_trade_materialization_reconcile(
		root, authority, static_cast<uint32_t>(result->pid), records, &result->snapshot,
		&error);
	if (materialized != flatfile_shop_trade_materialization_result::ok)
	{
		result->outcome =
			materialized == flatfile_shop_trade_materialization_result::io_error ?
				player_load_outcome::retryable_failure :
				player_load_outcome::component_failure;
		result->error_code =
			materialized == flatfile_shop_trade_materialization_result::io_error ?
				EIO :
				EILSEQ;
		result->failed_component = "shop_trade_materialization";
		return false;
	}
	// Every record the player file's items have, whoever it names.
	std::unordered_map<uint64_t, flatfile_item_ownership_record> catalog;
	std::unordered_set<uint64_t> consumed;
	std::unordered_set<uint64_t> recorded_for_owner;
	try
	{
		std::vector<uint64_t> uids;
		for (const player_item_snapshot &item : result->snapshot.items)
			uids.push_back(item.object_uid);
		for (const player_pet_snapshot &pet : result->snapshot.pets)
			for (const player_item_snapshot &item : pet.items)
				uids.push_back(item.object_uid);
		std::vector<flatfile_item_ownership_record> found;
		const auto looked_up = flatfile_item_repository_load_uids_locked(
			root, authority, uids, &found, &error);
		if (looked_up != flatfile_item_repository_result::ok)
		{
			result->outcome = looked_up == flatfile_item_repository_result::io_error ?
						  player_load_outcome::retryable_failure :
						  player_load_outcome::component_failure;
			result->error_code =
				looked_up == flatfile_item_repository_result::io_error ? EIO :
											 EILSEQ;
			result->failed_component = "item_ownership";
			return false;
		}
		for (auto &record : found)
			catalog.emplace(record.item_uid, std::move(record));
		for (const auto &record : records)
			recorded_for_owner.insert(record.item_uid);
		result->pet_identities.resize(result->snapshot.pets.size());
	}
	catch (const std::bad_alloc &)
	{
		result->outcome = player_load_outcome::retryable_failure;
		result->error_code = ENOMEM;
		result->failed_component = "item_ownership";
		return false;
	}
	uint64_t next_database_id = 1;
	size_t pet_materialized_count = 0;
	size_t legacy_pet_item_count = 0;
	if (!build_item_identities(&result->snapshot.items, catalog, owner, owner_revision,
				   &next_database_id, &consumed, &result->item_identities, result))
		goto invalid;
	for (size_t index = 0; index < result->snapshot.pets.size(); ++index)
	{
		const uint64_t pet_uid = result->snapshot.pets[index].pet_uid;
		const item_owner_identity pet_owner =
			pet_uid ? item_owner_identity{ item_owner_type::pet, pet_uid,
						       static_cast<uint64_t>(result->pid) } :
				  owner;
		uint64_t pet_revision = owner_revision;
		if (pet_uid)
		{
			std::vector<flatfile_item_ownership_record> pet_records;
			pet_revision = 0;
			const auto read = flatfile_item_repository_load_owner_locked(
				root, authority, pet_owner, &pet_revision, &pet_records, &error);
			if (read != flatfile_item_repository_result::ok &&
			    read != flatfile_item_repository_result::not_found)
			{
				result->outcome =
					read == flatfile_item_repository_result::io_error ?
						player_load_outcome::retryable_failure :
						player_load_outcome::component_failure;
				result->error_code =
					read == flatfile_item_repository_result::io_error ? EIO :
											    EILSEQ;
				result->failed_component = "pet_ownership";
				return false;
			}
			try
			{
				for (const auto &record : pet_records)
					recorded_for_owner.insert(record.item_uid);
			}
			catch (const std::bad_alloc &)
			{
				result->outcome = player_load_outcome::retryable_failure;
				result->error_code = ENOMEM;
				result->failed_component = "pet_ownership";
				return false;
			}
		}
		auto &identity = result->pet_identities[index];
		identity.database_id = index + 1;
		identity.pet_uid = pet_uid;
		identity.owner_revision = pet_revision;
		if (!build_item_identities(&result->snapshot.pets[index].items, catalog, pet_owner,
					   pet_revision, &next_database_id, &consumed,
					   &identity.item_identities, result))
			goto invalid;
		// A legacy pet without a UID carries items its owner holds.
		if (pet_uid)
			pet_materialized_count += identity.item_identities.size();
		else
			legacy_pet_item_count += identity.item_identities.size();
	}
	// A record whose payload item is gone is an item the player no longer holds; its
	// next holder claims it. It is only counted.
	result->missing_payload_rows = 0;
	for (uint64_t uid : recorded_for_owner)
		if (!consumed.count(uid))
			++result->missing_payload_rows;
	result->item_owner_revision = owner_revision;
	result->authoritative_item_count = result->item_identities.size() + legacy_pet_item_count;
	result->authoritative_pet_item_count = pet_materialized_count;
	return true;

invalid:
	result->outcome = player_load_outcome::component_failure;
	result->error_code = EILSEQ;
	result->failed_component = "item_ownership";
	return false;
}

bool normalize_size(player_snapshot *snapshot, std::vector<uint8_t> *payload)
{
	if (!snapshot || !payload)
		return false;
	snapshot->encoded_size_bound = 1;
	if (player_snapshot_encode(*snapshot, payload) != player_snapshot_codec_result::ok)
		return false;
	snapshot->encoded_size_bound = payload->size();
	return player_snapshot_encode(*snapshot, payload) == player_snapshot_codec_result::ok;
}

bool encode_file(player_snapshot *snapshot, std::vector<uint8_t> *bytes)
{
	std::vector<uint8_t> payload;
	if (!bytes || !normalize_size(snapshot, &payload))
		return false;
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(payload.data(), payload.size(), digest);
	encoder out;
	out.bytes.insert(out.bytes.end(), player_magic.begin(), player_magic.end());
	out.number<uint32_t>(player_file_version);
	out.number<uint32_t>(payload.size());
	out.number<int32_t>(snapshot->pid);
	out.number<uint64_t>(snapshot->revision);
	out.number<uint64_t>(snapshot->components);
	out.bytes.insert(out.bytes.end(), digest, digest + sizeof(digest));
	out.bytes.insert(out.bytes.end(), payload.begin(), payload.end());
	if (out.bytes.size() > player_file_maximum)
		return false;
	*bytes = std::move(out.bytes);
	return true;
}

bool replace_items_together(player_component_mask_t components)
{
	const player_component_mask_t items = PLAYER_COMPONENT_EQUIPMENT |
					      PLAYER_COMPONENT_INVENTORY;
	return !(components & items) || (components & items) == items;
}

bool merge_snapshot(const player_snapshot &incoming, player_snapshot *materialized)
{
	if (!materialized || materialized->pid != incoming.pid ||
	    materialized->components != PLAYER_CHECKPOINT_COMPONENT_ALL ||
	    !replace_items_together(incoming.components))
		return false;
	materialized->revision = incoming.revision;
	materialized->save_intent = incoming.save_intent;
	materialized->room_vnum = incoming.room_vnum;
	materialized->recipes_are_external = incoming.recipes_are_external;
	if (incoming.components & PLAYER_COMPONENT_STATUS)
	{
		materialized->status_integers = incoming.status_integers;
		materialized->status_strings = incoming.status_strings;
		materialized->conditions = incoming.conditions;
		materialized->quest_values = incoming.quest_values;
		materialized->output_preferences = incoming.output_preferences;
	}
	if (incoming.components & PLAYER_COMPONENT_LANGUAGES)
		materialized->languages = incoming.languages;
	if (incoming.components & PLAYER_COMPONENT_INTRODUCTIONS)
		materialized->introductions = incoming.introductions;
	if (incoming.components & PLAYER_COMPONENT_TIMERS)
		materialized->timers = incoming.timers;
	if (incoming.components & PLAYER_COMPONENT_UNDEAD_SLOTS)
		materialized->undead_slots = incoming.undead_slots;
	if (incoming.components & PLAYER_COMPONENT_FORGED_ITEMS)
		materialized->forged_items = incoming.forged_items;
	if (incoming.components & PLAYER_COMPONENT_GRANTED_COMMANDS)
		materialized->granted_commands = incoming.granted_commands;
	if (incoming.components & PLAYER_COMPONENT_SKILLS)
		materialized->skills = incoming.skills;
	if (incoming.components & PLAYER_COMPONENT_AFFECTS)
		materialized->affects = incoming.affects;
	if (incoming.components & (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY))
		materialized->items = incoming.items;
	if (incoming.components & PLAYER_COMPONENT_PETS)
		materialized->pets = incoming.pets;
	if (incoming.components & PLAYER_COMPONENT_SHAPECHANGES)
		materialized->shapes = incoming.shapes;
	if (incoming.components & PLAYER_COMPONENT_TROPHIES)
		materialized->trophies = incoming.trophies;
	materialized->components = PLAYER_CHECKPOINT_COMPONENT_ALL;
	return true;
}

flatfile_player_domain_result establish_domain_baseline(const std::string &root,
							const player_snapshot &snapshot,
							std::string *error)
{
	flatfile_identity_record identity;
	const flatfile_identity_result identity_loaded =
		flatfile_identity_lookup_pid(root, snapshot.pid, &identity, error);
	if (identity_loaded != flatfile_identity_result::ok)
		return identity_loaded == flatfile_identity_result::io_error ?
			       flatfile_player_domain_result::io_error :
		       identity_loaded == flatfile_identity_result::not_found ?
			       flatfile_player_domain_result::not_found :
			       flatfile_player_domain_result::invalid;
	const std::string *name = snapshot_player_name(snapshot);
	int64_t racewar = 0;
	flatfile_player_domain_record record;
	record.pid = snapshot.pid;
	record.account_name = identity.account;
	if (!identity.active || !name || !same_authority_key(*name, identity.name) ||
	    !snapshot_signed(snapshot, player_status_field::racewar, &racewar) ||
	    racewar < INT8_MIN || racewar > INT8_MAX || identity.racewar != racewar ||
	    !snapshot_unsigned(snapshot, player_status_field::copper, &record.domains.wallet[0]) ||
	    !snapshot_unsigned(snapshot, player_status_field::silver, &record.domains.wallet[1]) ||
	    !snapshot_unsigned(snapshot, player_status_field::gold, &record.domains.wallet[2]) ||
	    !snapshot_unsigned(snapshot, player_status_field::platinum,
			       &record.domains.wallet[3]) ||
	    !snapshot_signed(snapshot, player_status_field::epics, &record.domains.epics) ||
	    !snapshot_signed(snapshot, player_status_field::frags, &record.domains.frags) ||
	    !snapshot_signed(snapshot, player_status_field::old_frags, &record.domains.old_frags))
		return flatfile_player_domain_result::invalid;
	static constexpr std::array<player_status_field, 10> base_stat_fields = {
		player_status_field::base_strength, player_status_field::base_dexterity,
		player_status_field::base_agility,  player_status_field::base_constitution,
		player_status_field::base_power,    player_status_field::base_intelligence,
		player_status_field::base_wisdom,   player_status_field::base_charisma,
		player_status_field::base_karma,    player_status_field::base_luck,
	};
	for (size_t index = 0; index < base_stat_fields.size(); ++index)
	{
		int64_t stat = 0;
		if (!snapshot_signed(snapshot, base_stat_fields[index], &stat) || stat < 0 ||
		    stat > 100)
			return flatfile_player_domain_result::invalid;
		record.domains.base_stats[index] = static_cast<int16_t>(stat);
	}
	record.domains.base_stat_revision = 1;
	record.racewar = static_cast<int8_t>(racewar);
	return flatfile_player_domain_establish_initial_player(root, record, error);
}
} // namespace

struct flatfile_player_snapshot_lock::state
{
	std::unique_lock<std::mutex> process_lock;
	int fd = -1;
	std::string root;
	int32_t pid = 0;

	state()
		: process_lock(player_mutex, std::defer_lock)
	{
	}
	~state() { flatfile_lock_release(fd); }
};

flatfile_player_snapshot_lock::flatfile_player_snapshot_lock() noexcept
	: state_(new(std::nothrow) state)
{
}
flatfile_player_snapshot_lock::~flatfile_player_snapshot_lock() = default;

bool flatfile_player_snapshot_lock::acquire(const std::string &root, int32_t pid,
					    std::string *error)
{
	if (!state_ || state_->process_lock.owns_lock() || root.empty() || pid <= 0)
		return false;
	state_->process_lock.lock();
	if (flatfile_lock_acquire(player_directory(root), player_lock_filename(pid), &state_->fd,
				  error))
	{
		state_->root = root;
		state_->pid = pid;
		return true;
	}
	state_->process_lock.unlock();
	return false;
}

bool flatfile_player_snapshot_lock::owns(const std::string &root, int32_t pid) const
{
	return state_ && state_->process_lock.owns_lock() && state_->fd >= 0 &&
	       state_->root == root && state_->pid == pid;
}

bool flatfile_player_snapshot_lock::matches(const std::string &root, int32_t pid) const
{
	return owns(root, pid);
}

flatfile_player_load_result flatfile_player_snapshot_load(const std::string &root, int32_t pid,
							  player_snapshot *snapshot,
							  std::string *error)
{
	std::lock_guard<std::mutex> guard(player_mutex);
	return flatfile_player_snapshot_read(root, pid, snapshot, error);
}

player_load_result flatfile_player_load_repository_execute(const std::string &root,
							   const player_load_request &request)
{
	const uint64_t started = persistence_observability_now_usec();
	player_load_result result = {};
	result.request_id = request.request_id;
	result.pid = request.pid;
	if (!player_load_request_valid(request, started))
	{
		result.outcome = request.deadline_usec <= started ?
					 player_load_outcome::timed_out :
					 player_load_outcome::component_failure;
		result.error_code = request.deadline_usec <= started ? ETIMEDOUT : EINVAL;
		result.failed_component = "request";
		return result;
	}

	flatfile_identity_record identity = {};
	std::string error;
	const flatfile_identity_result identity_loaded =
		request.pid > 0 ?
			flatfile_identity_lookup_pid(root, request.pid, &identity, &error) :
			flatfile_identity_lookup_name(root, request.player_name, &identity, &error);
	if (identity_loaded != flatfile_identity_result::ok)
		return identity_failure(request, identity_loaded);
	result.pid = identity.pid;
	result.account_name = identity.account;
	result.saved_at = identity.last_save;
	if (!identity.active)
	{
		result.outcome = player_load_outcome::not_found;
		result.error_code = ENOENT;
		result.failed_component = "identity";
		return result;
	}
	if (identity.blocked || (!request.account_name.empty() &&
				 !same_authority_key(request.account_name, identity.account)))
	{
		result.outcome = player_load_outcome::component_failure;
		result.error_code = EACCES;
		result.failed_component = "identity";
		return result;
	}

	const flatfile_player_load_result snapshot_loaded =
		flatfile_player_snapshot_load(root, identity.pid, &result.snapshot, &error);
	if (snapshot_loaded != flatfile_player_load_result::ok)
	{
		result.failed_component = "snapshot";
		result.error_code =
			snapshot_loaded == flatfile_player_load_result::not_found ? ENOENT :
			snapshot_loaded == flatfile_player_load_result::io_error  ? EIO :
										    EILSEQ;
		result.outcome = snapshot_loaded == flatfile_player_load_result::not_found ?
					 player_load_outcome::not_found :
				 snapshot_loaded == flatfile_player_load_result::io_error ?
					 player_load_outcome::retryable_failure :
					 player_load_outcome::component_failure;
		return result;
	}
	const std::string *snapshot_name = snapshot_player_name(result.snapshot);
	if (!snapshot_name || !same_authority_key(*snapshot_name, identity.name))
	{
		result.outcome = player_load_outcome::component_failure;
		result.error_code = EILSEQ;
		result.failed_component = "snapshot_identity";
		return result;
	}
	if (request.include_items && !reconcile_item_ownership(root, &result))
		return result;
	// The identity keeps the character's own racewar. One written before it did holds
	// the account menu's immortal value (0) for an immortal instead; the snapshot's is
	// the character's own, and the next save writes it back.
	int64_t snapshot_racewar = 0;
	if (!snapshot_signed(result.snapshot, player_status_field::racewar, &snapshot_racewar) ||
	    (identity.racewar && snapshot_racewar != identity.racewar) ||
	    snapshot_racewar < INT8_MIN || snapshot_racewar > INT8_MAX)
	{
		result.outcome = player_load_outcome::component_failure;
		result.error_code = EILSEQ;
		result.failed_component = "domain_identity";
		return result;
	}
	flatfile_player_domain_record domains;
	const flatfile_player_domain_result domains_loaded = flatfile_player_domain_load(
		root, identity.pid, identity.account, static_cast<int8_t>(snapshot_racewar),
		&domains, &error);
	if (domains_loaded != flatfile_player_domain_result::ok)
	{
		result.error_code =
			domains_loaded == flatfile_player_domain_result::not_found ? ENOENT :
			domains_loaded == flatfile_player_domain_result::io_error  ? EIO :
										     EILSEQ;
		result.outcome = domains_loaded == flatfile_player_domain_result::io_error ?
					 player_load_outcome::retryable_failure :
					 player_load_outcome::component_failure;
		result.failed_component = "domains";
		return result;
	}
	else
	{
		result.domains = domains.domains;
		result.recent_pvp_deaths = std::move(domains.recent_pvp_deaths);
		result.completed_epic_zones = std::move(domains.completed_epic_zones);
		result.read_components = PLAYER_LOAD_SESSION04_READS;
	}
	if (!request.include_pets)
	{
		result.snapshot.pets.clear();
		result.pet_identities.clear();
	}
	if (!request.include_items)
	{
		result.snapshot.items.clear();
		result.item_identities.clear();
		result.item_owner_revision = 0;
		result.authoritative_item_count = 0;
	}
	result.snapshot.components = request.include_pets  ? PLAYER_LOAD_SESSION03_COMPONENTS :
				     request.include_items ? PLAYER_LOAD_SESSION02_COMPONENTS :
							     PLAYER_LOAD_SESSION01_COMPONENTS;

	result.metrics.byte_count = result.snapshot.encoded_size_bound;
	result.metrics.row_count = 1;
	result.metrics.transaction_usec = persistence_observability_now_usec() - started;
	result.outcome = player_load_outcome::applied;
	return result;
}

player_load_result
flatfile_player_load_repository_execute_selected(const player_load_request &request, void *context)
{
	const char *root = context ? static_cast<const char *>(context) :
				     persistence_mode_flatfile_root();
	if (root && *root)
		return flatfile_player_load_repository_execute(root, request);
	player_load_result result = {};
	result.request_id = request.request_id;
	result.pid = request.pid;
	result.outcome = player_load_outcome::component_failure;
	result.error_code = ENOENT;
	result.failed_component = "state_root";
	return result;
}

flatfile_player_load_result
flatfile_player_snapshot_prepare_remove(const std::string &root,
					const flatfile_player_snapshot_lock &snapshot_lock,
					const flatfile_authority_lock &authority_lock, int32_t pid,
					flatfile_authority_operation *operation, std::string *error)
{
	if (!operation || !snapshot_lock.matches(root, pid) || !authority_lock.matches(root))
		return flatfile_player_load_result::invalid;
	*operation = {};
	const auto recovered = flatfile_authority_transaction_recover(root, authority_lock, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_player_load_result::io_error :
			       flatfile_player_load_result::invalid;
	player_snapshot snapshot = {};
	const auto loaded = flatfile_player_snapshot_read(root, pid, &snapshot, error);
	if (loaded != flatfile_player_load_result::ok)
		return loaded;
	operation->store = flatfile_authority_store::players;
	operation->kind = flatfile_authority_operation_kind::remove;
	operation->filename = player_filename(pid);
	return flatfile_player_load_result::ok;
}

player_save_apply_result flatfile_player_snapshot_apply(const std::string &root,
							const player_snapshot &snapshot,
							std::string *error)
{
	if (!valid_snapshot(snapshot) || !replace_items_together(snapshot.components))
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	flatfile_player_snapshot_lock snapshot_lock;
	if (!snapshot_lock.acquire(root, snapshot.pid, error))
		return { player_save_apply_outcome::retryable_failure, 0, EIO };
	// The authority lock is not reentrant, and a new player's domain baseline takes it
	// itself, so it is held around each step rather than for the whole save.
	auto authority = std::make_unique<flatfile_authority_lock>();
	const auto lock_authority = [&]() -> player_save_apply_result
	{
		if (!authority->acquire(root, error))
			return { player_save_apply_outcome::retryable_failure, 0, EIO };
		const auto recovered =
			flatfile_authority_transaction_recover(root, *authority, error);
		if (recovered != flatfile_authority_transaction_result::ok)
			return { recovered == flatfile_authority_transaction_result::io_error ?
					 player_save_apply_outcome::retryable_failure :
					 player_save_apply_outcome::terminal_failure,
				 0, EIO };
		return { player_save_apply_outcome::applied, 0, 0 };
	};
	player_save_apply_result locked = lock_authority();
	if (locked.outcome != player_save_apply_outcome::applied)
		return locked;
	player_snapshot materialized = {};
	bool new_player = false;
	const flatfile_player_load_result loaded =
		flatfile_player_snapshot_read(root, snapshot.pid, &materialized, error);
	if (loaded == flatfile_player_load_result::invalid)
		return { player_save_apply_outcome::terminal_failure, 0, EILSEQ };
	if (loaded == flatfile_player_load_result::io_error)
		return { player_save_apply_outcome::retryable_failure, 0, EIO };
	if (loaded == flatfile_player_load_result::not_found)
	{
		if (snapshot.death || snapshot.components != PLAYER_CHECKPOINT_COMPONENT_ALL)
			return { player_save_apply_outcome::terminal_failure, 0, ENOENT };
		new_player = true;
		authority = std::make_unique<flatfile_authority_lock>();
		const flatfile_player_domain_result domain_baseline =
			establish_domain_baseline(root, snapshot, error);
		locked = lock_authority();
		if (locked.outcome != player_save_apply_outcome::applied)
			return locked;
		if (domain_baseline == flatfile_player_domain_result::io_error)
			return { player_save_apply_outcome::retryable_failure, 0, EIO };
		if (domain_baseline != flatfile_player_domain_result::ok)
			return { player_save_apply_outcome::terminal_failure, 0,
				 static_cast<unsigned int>(
					 domain_baseline ==
							 flatfile_player_domain_result::conflict ?
						 EEXIST :
					 domain_baseline ==
							 flatfile_player_domain_result::not_found ?
						 ENOENT :
						 EINVAL) };
		materialized = snapshot;
	}
	else
	{
		if (!merge_snapshot(snapshot, &materialized))
			return { player_save_apply_outcome::terminal_failure, materialized.revision,
				 EINVAL };
	}

	// Claim what the player and its pets hold, as one catalog write.
	const item_owner_identity player_owner = { item_owner_type::player,
						   static_cast<uint64_t>(snapshot.pid), 0 };
	std::vector<flatfile_item_claim> claims;
	std::vector<flatfile_item_claim_audit> audits;
	flatfile_authority_operation claimed;
	bool claim_changed = false;
	if (snapshot.components &
	    (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY | PLAYER_COMPONENT_PETS))
	{
		try
		{
			if (snapshot.components &
			    (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY))
				claims.push_back(
					{ player_owner, &materialized.items, {}, new_player });
			if (snapshot.components & PLAYER_COMPONENT_PETS)
				for (const player_pet_snapshot &pet : materialized.pets)
					claims.push_back(
						{ pet.pet_uid ?
							  item_owner_identity{
								  item_owner_type::pet, pet.pet_uid,
								  static_cast<uint64_t>(
									  snapshot.pid) } :
							  player_owner,
						  &pet.items,
						  {} });
		}
		catch (const std::bad_alloc &)
		{
			return { player_save_apply_outcome::retryable_failure, 0, ENOMEM };
		}
		const auto prepared = flatfile_item_repository_prepare_claim(
			root, *authority, &claims, &claimed, &audits, error);
		if (prepared == flatfile_item_repository_result::io_error)
			return { player_save_apply_outcome::retryable_failure, 0, EIO };
		if (prepared != flatfile_item_repository_result::ok &&
		    prepared != flatfile_item_repository_result::unchanged)
			return { player_save_apply_outcome::terminal_failure, 0, EILSEQ };
		claim_changed = prepared == flatfile_item_repository_result::ok;
		// Leave out what was destroyed, with its contents.
		size_t claim = 0;
		if (snapshot.components & (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY))
			materialized.items = item_claim_written_items(
				materialized.items, claims[claim++].outcome.left_out);
		if (snapshot.components & PLAYER_COMPONENT_PETS)
			for (player_pet_snapshot &pet : materialized.pets)
				pet.items = item_claim_written_items(
					pet.items, claims[claim++].outcome.left_out);
	}

	std::vector<uint8_t> bytes;
	// Keep the immutable evidence, quarantine and empty player projection in the
	// same recoverable authority transaction. A failed commit leaves no evidence
	// claiming a disposition that never took effect.
	std::vector<uint8_t> death_bytes;
	if (snapshot.death)
	{
		player_snapshot disposition = snapshot;
		if (!encode_file(&disposition, &death_bytes))
			return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
		materialized.death.reset();
		materialized.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	}
	if (!encode_file(&materialized, &bytes))
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	// A save that carries everything the player holds replaces what earlier
	// transfers gave it, as a MariaDB save replaces the player_items rows they wrote.
	constexpr player_component_mask_t held_components =
		PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY | PLAYER_COMPONENT_PETS;
	flatfile_authority_operation delivered;
	bool delivered_changed = false;
	if ((snapshot.components & held_components) == held_components)
	{
		const auto retired = flatfile_shop_trade_materialization_prepare_player_remove(
			root, *authority, static_cast<uint32_t>(snapshot.pid), &delivered, error);
		if (retired == flatfile_shop_trade_materialization_result::io_error)
			return { player_save_apply_outcome::retryable_failure, 0, EIO };
		if (retired != flatfile_shop_trade_materialization_result::ok &&
		    retired != flatfile_shop_trade_materialization_result::unchanged)
			return { player_save_apply_outcome::terminal_failure, 0, EILSEQ };
		delivered_changed = retired == flatfile_shop_trade_materialization_result::ok;
	}
	// The wallet, epic points and frags are memory's: a save that carries them writes
	// them into the player's domain record. A new player's baseline above already holds
	// them.
	flatfile_authority_operation saved_balances;
	flatfile_saved_balances balances;
	const bool saves_balances =
		!new_player &&
		snapshot_unsigned(snapshot, player_status_field::copper, &balances.wallet[0]) &&
		snapshot_unsigned(snapshot, player_status_field::silver, &balances.wallet[1]) &&
		snapshot_unsigned(snapshot, player_status_field::gold, &balances.wallet[2]) &&
		snapshot_unsigned(snapshot, player_status_field::platinum, &balances.wallet[3]) &&
		snapshot_signed(snapshot, player_status_field::epics, &balances.epics) &&
		snapshot_signed(snapshot, player_status_field::frags, &balances.frags) &&
		snapshot_signed(snapshot, player_status_field::old_frags, &balances.old_frags);
	if (saves_balances)
	{
		const auto prepared = flatfile_player_domain_prepare_saved_balances(
			root, *authority, static_cast<uint32_t>(snapshot.pid), balances,
			&saved_balances, error);
		if (prepared == flatfile_player_domain_result::io_error)
			return { player_save_apply_outcome::retryable_failure, 0, EIO };
		if (prepared != flatfile_player_domain_result::ok)
			return { player_save_apply_outcome::terminal_failure, 0, EILSEQ };
	}
	std::vector<flatfile_authority_operation> operations;
	try
	{
		if (claim_changed)
			operations.push_back(std::move(claimed));
		if (delivered_changed)
			operations.push_back(std::move(delivered));
		if (saves_balances)
			operations.push_back(std::move(saved_balances));
		if (snapshot.death)
		{
			operations.push_back({ flatfile_authority_store::player_deaths,
					       flatfile_authority_operation_kind::write,
					       death_filename(snapshot.pid, snapshot.revision),
					       std::move(death_bytes) });
			std::vector<uint64_t> custody_uids;
			custody_uids.reserve(snapshot.death->custody.size());
			for (const auto &row : snapshot.death->custody)
				if (row.item.item_uid)
					custody_uids.push_back(row.item.item_uid);
			flatfile_authority_operation quarantine;
			const auto quarantined = flatfile_item_repository_prepare_death_quarantine(
				root, *authority, snapshot.pid, custody_uids, &quarantine, error);
			if (quarantined == flatfile_item_repository_result::ok)
				operations.push_back(std::move(quarantine));
			else if (quarantined != flatfile_item_repository_result::unchanged)
				return { quarantined == flatfile_item_repository_result::io_error ?
						 player_save_apply_outcome::retryable_failure :
						 player_save_apply_outcome::terminal_failure,
					 0, EIO };
		}
		operations.push_back({ flatfile_authority_store::players,
				       flatfile_authority_operation_kind::write,
				       player_filename(snapshot.pid), std::move(bytes) });
	}
	catch (const std::bad_alloc &)
	{
		return { player_save_apply_outcome::retryable_failure, 0, ENOMEM };
	}
	const auto committed = flatfile_authority_transaction_commit_operations(root, *authority,
										operations, error);
	if (committed != flatfile_authority_transaction_result::ok)
		return { committed == flatfile_authority_transaction_result::io_error ?
				 player_save_apply_outcome::retryable_failure :
				 player_save_apply_outcome::terminal_failure,
			 0, EIO };
	for (const flatfile_item_claim_audit &audit : audits)
		item_claim_log_item(audit.item_uid, audit.vnum, audit.old_owner, audit.new_owner);
	for (const flatfile_item_claim &claim : claims)
		item_claim_log_dupes("save_left_out", claim.owner, claim.outcome);
	return { player_save_apply_outcome::applied, snapshot.revision, 0 };
}

namespace
{
template <typename Prepare>
player_save_apply_result apply_world_snapshot(const std::string &root,
					      const item_owner_identity &owner,
					      const std::vector<player_item_snapshot> *items,
					      Prepare prepare, std::string *error)
{
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return { player_save_apply_outcome::retryable_failure, 0, EIO };
	const auto recovered = flatfile_authority_transaction_recover(root, authority, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return { recovered == flatfile_authority_transaction_result::io_error ?
				 player_save_apply_outcome::retryable_failure :
				 player_save_apply_outcome::terminal_failure,
			 0, EIO };
	std::vector<flatfile_item_claim> claims;
	std::vector<flatfile_item_claim_audit> audits;
	std::vector<flatfile_authority_operation> operations;
	std::vector<player_item_snapshot> written;
	try
	{
		if (items)
		{
			claims.push_back({ owner, items, {} });
			flatfile_authority_operation claimed;
			const auto prepared = flatfile_item_repository_prepare_claim(
				root, authority, &claims, &claimed, &audits, error);
			if (prepared == flatfile_item_repository_result::io_error)
				return { player_save_apply_outcome::retryable_failure, 0, EIO };
			if (prepared != flatfile_item_repository_result::ok &&
			    prepared != flatfile_item_repository_result::unchanged)
				return { player_save_apply_outcome::terminal_failure, 0, EILSEQ };
			if (prepared == flatfile_item_repository_result::ok)
				operations.push_back(std::move(claimed));
			// Leave out what was destroyed, with its contents.
			written = item_claim_written_items(*items, claims[0].outcome.left_out);
		}
		flatfile_authority_operation world;
		const flatfile_world_item_result prepared = prepare(authority, written, &world);
		if (prepared == flatfile_world_item_result::io_error)
			return { player_save_apply_outcome::retryable_failure, 0, EIO };
		if (prepared == flatfile_world_item_result::ok)
			operations.push_back(std::move(world));
		else if (prepared != flatfile_world_item_result::unchanged)
			return { player_save_apply_outcome::terminal_failure, 0, EILSEQ };
	}
	catch (const std::bad_alloc &)
	{
		return { player_save_apply_outcome::retryable_failure, 0, ENOMEM };
	}
	if (operations.empty())
		return { player_save_apply_outcome::applied, 0, 0 };
	const auto committed = flatfile_authority_transaction_commit_operations(root, authority,
										operations, error);
	if (committed != flatfile_authority_transaction_result::ok)
		return { committed == flatfile_authority_transaction_result::io_error ?
				 player_save_apply_outcome::retryable_failure :
				 player_save_apply_outcome::terminal_failure,
			 0, EIO };
	for (const flatfile_item_claim_audit &audit : audits)
		item_claim_log_item(audit.item_uid, audit.vnum, audit.old_owner, audit.new_owner);
	for (const flatfile_item_claim &claim : claims)
		item_claim_log_dupes("save_left_out", claim.owner, claim.outcome);
	return { player_save_apply_outcome::applied, 0, 0 };
}
} // namespace

player_save_apply_result flatfile_bank_delta_apply(const std::string &root,
						   const std::string &account_name, int8_t racewar,
						   const std::array<int64_t, 4> &delta,
						   flatfile_authority_operation *prepared,
						   std::string *error)
{
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return { player_save_apply_outcome::retryable_failure, 0, EIO };
	const auto recovered = flatfile_authority_transaction_recover(root, authority, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return { recovered == flatfile_authority_transaction_result::io_error ?
				 player_save_apply_outcome::retryable_failure :
				 player_save_apply_outcome::terminal_failure,
			 0, EIO };
	if (prepared->filename.empty())
	{
		flatfile_authority_operation operation;
		const auto result = flatfile_player_domain_prepare_bank_delta(
			root, authority, account_name, racewar, delta, &operation, error);
		if (result == flatfile_player_domain_result::io_error)
			return { player_save_apply_outcome::retryable_failure, 0, EIO };
		if (result != flatfile_player_domain_result::ok)
			return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
		*prepared = std::move(operation);
	}
	const std::vector<flatfile_authority_operation> operations = { *prepared };
	const auto committed = flatfile_authority_transaction_commit_operations(root, authority,
										operations, error);
	if (committed != flatfile_authority_transaction_result::ok)
		return { committed == flatfile_authority_transaction_result::io_error ?
				 player_save_apply_outcome::retryable_failure :
				 player_save_apply_outcome::terminal_failure,
			 0, EIO };
	return { player_save_apply_outcome::applied, 0, 0 };
}

player_save_apply_result flatfile_corpse_snapshot_apply(const std::string &root,
							const flatfile_corpse_record &corpse,
							bool remove, std::string *error)
{
	const item_owner_identity owner = { item_owner_type::corpse,
					    item_corpse_owner_id(corpse.owner_pid, corpse.save_id),
					    0 };
	return apply_world_snapshot(
		root, owner, remove ? nullptr : &corpse.items,
		[&](const flatfile_authority_lock &lock,
		    const std::vector<player_item_snapshot> &written,
		    flatfile_authority_operation *operation)
		{
			flatfile_corpse_record record = corpse;
			record.items = written;
			return flatfile_world_item_prepare_corpse_snapshot(
				root, lock, record, remove, operation, error);
		},
		error);
}

player_save_apply_result
flatfile_saved_item_snapshot_apply(const std::string &root,
				   const flatfile_saved_world_item_record &item, bool remove,
				   std::string *error)
{
	const item_owner_identity owner = { item_owner_type::room,
					    static_cast<uint64_t>(item.room_vnum), 0 };
	return apply_world_snapshot(
		root, owner, remove ? nullptr : &item.items,
		[&](const flatfile_authority_lock &lock,
		    const std::vector<player_item_snapshot> &written,
		    flatfile_authority_operation *operation)
		{
			// A saved item whose every piece was destroyed leaves the room.
			const bool drop = remove || written.empty();
			return flatfile_world_item_prepare_room_item_snapshot(
				root, lock, item.room_vnum, drop ? item.items : written, drop,
				operation, error);
		},
		error);
}

player_save_apply_result flatfile_player_snapshot_apply_selected(const player_snapshot &snapshot,
								 void * /*context*/)
{
	const char *root = persistence_mode_flatfile_root();
	if (!root)
		return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
	std::string error;
	return flatfile_player_snapshot_apply(root, snapshot, &error);
}
