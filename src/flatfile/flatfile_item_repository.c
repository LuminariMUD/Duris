#include "flatfile/flatfile_item_repository.h"

#include "flatfile/flatfile_auction_repository.h"
#include "flatfile/flatfile_artifact_repository.h"
#include "flatfile/flatfile_boon_repository.h"
#include "flatfile/flatfile_authority_transaction.h"
#include "flatfile/flatfile_collector_repository.h"
#include "flatfile/flatfile_locker_repository.h"
#include "flatfile/flatfile_store.h"
#include "flatfile/flatfile_player_domain_repository.h"
#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_world_item_repository.h"
#include "flatfile/flatfile_shop_trade_materialization.h"
#include "flatfile/flatfile_shop_trade_repository.h"
#include "persistence/dupe_log.h"
#include "persistence/persistence_mode.h"
#include "player/player_snapshot_codec.h"
#include "world/vnum.obj.h"
#include "core/defines.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <limits>
#include <mutex>
#include <new>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <utility>

namespace
{
constexpr uint32_t ownership_format_version = 4;
constexpr uint32_t ownership_legacy_format_version = 1;
constexpr std::array<uint8_t, 8> ownership_magic = { 'D', 'U', 'R', 'O', 'W', 'N', 0, 0 };
constexpr size_t ownership_maximum_bytes = 128 * 1024 * 1024;
constexpr size_t ownership_maximum_entries = 262144;
constexpr size_t ownership_maximum_operations = 1048576;
constexpr const char *ownership_filename = "item_ownership";
std::mutex ownership_mutex;

struct owner_state
{
	item_owner_identity owner;
	uint64_t revision;
};

struct operation_state
{
	critical_operation_id operation_id;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> command_digest;
	unsigned int result_code;
	item_transfer_result result;
};

struct ownership_catalog
{
	uint64_t revision = 0;
	std::vector<owner_state> owners;
	std::vector<flatfile_item_ownership_record> items;
	std::vector<operation_state> operations;
};

struct encoder
{
	std::vector<uint8_t> bytes;
	bool valid = true;

	template <typename T> void number(T value)
	{
		if (!valid)
			return;
		using unsigned_type = std::make_unsigned_t<T>;
		unsigned_type bits = static_cast<unsigned_type>(value);
		try
		{
			for (size_t index = 0; index < sizeof(T); ++index)
			{
				bytes.push_back(static_cast<uint8_t>(bits & 0xff));
				bits >>= 8;
			}
		}
		catch (const std::bad_alloc &)
		{
			valid = false;
		}
	}

	void raw(const uint8_t *data, size_t size)
	{
		if (!valid || (!data && size))
		{
			valid = false;
			return;
		}
		try
		{
			bytes.insert(bytes.end(), data, data + size);
		}
		catch (const std::bad_alloc &)
		{
			valid = false;
		}
	}
};

struct decoder
{
	const uint8_t *data;
	size_t size;
	size_t offset = 0;

	template <typename T> bool number(T *value)
	{
		if (!value || size - offset < sizeof(T))
			return false;
		using unsigned_type = std::make_unsigned_t<T>;
		unsigned_type bits = 0;
		for (size_t index = 0; index < sizeof(T); ++index)
			bits |= static_cast<unsigned_type>(data[offset++]) << (index * 8);
		*value = static_cast<T>(bits);
		return true;
	}

	bool raw(uint8_t *output, size_t count)
	{
		if (!output || size - offset < count)
			return false;
		memcpy(output, data + offset, count);
		offset += count;
		return true;
	}
};

struct operation_id_hash
{
	size_t operator()(const std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES> &value) const
	{
		size_t result = 0;
		for (uint8_t byte : value)
			result = result * 131 + byte;
		return result;
	}
};

std::string domains_directory(const std::string &root)
{
	return root + "/domains";
}

bool owner_less(const item_owner_identity &left, const item_owner_identity &right)
{
	if (left.type != right.type)
		return left.type < right.type;
	if (left.id != right.id)
		return left.id < right.id;
	return left.context_id < right.context_id;
}

bool item_less(const flatfile_item_ownership_record &left,
	       const flatfile_item_ownership_record &right)
{
	return left.item_uid < right.item_uid;
}

bool item_equal(const flatfile_item_ownership_record &left,
		const flatfile_item_ownership_record &right)
{
	return left.item_uid == right.item_uid && left.root_item_uid == right.root_item_uid &&
	       left.parent_item_uid == right.parent_item_uid &&
	       item_owner_identity_equal(left.owner, right.owner) &&
	       left.item_revision == right.item_revision && left.vnum == right.vnum &&
	       left.state == right.state;
}

owner_state *find_owner(ownership_catalog *catalog, const item_owner_identity &owner)
{
	if (!catalog)
		return nullptr;
	auto found =
		std::lower_bound(catalog->owners.begin(), catalog->owners.end(), owner,
				 [](const owner_state &entry, const item_owner_identity &candidate)
				 { return owner_less(entry.owner, candidate); });
	return found != catalog->owners.end() && item_owner_identity_equal(found->owner, owner) ?
		       &*found :
		       nullptr;
}

owner_state *ensure_owner(ownership_catalog *catalog, const item_owner_identity &owner)
{
	if (owner_state *existing = find_owner(catalog, owner))
		return existing;
	if (!catalog || catalog->owners.size() >= ownership_maximum_entries)
		return nullptr;
	auto at =
		std::lower_bound(catalog->owners.begin(), catalog->owners.end(), owner,
				 [](const owner_state &entry, const item_owner_identity &candidate)
				 { return owner_less(entry.owner, candidate); });
	try
	{
		at = catalog->owners.insert(at, { owner, 0 });
	}
	catch (const std::bad_alloc &)
	{
		return nullptr;
	}
	return &*at;
}

flatfile_item_ownership_record *find_item(ownership_catalog *catalog, uint64_t item_uid)
{
	if (!catalog)
		return nullptr;
	auto found =
		std::lower_bound(catalog->items.begin(), catalog->items.end(), item_uid,
				 [](const flatfile_item_ownership_record &entry, uint64_t candidate)
				 { return entry.item_uid < candidate; });
	return found != catalog->items.end() && found->item_uid == item_uid ? &*found : nullptr;
}

bool encode_catalog(const ownership_catalog &catalog, uint64_t revision,
		    std::vector<uint8_t> *bytes)
{
	if (!bytes || !revision || catalog.owners.size() > ownership_maximum_entries ||
	    catalog.items.size() > ownership_maximum_entries ||
	    catalog.operations.size() > ownership_maximum_operations)
		return false;
	encoder payload;
	payload.number<uint32_t>(catalog.owners.size());
	payload.number<uint32_t>(catalog.items.size());
	payload.number<uint32_t>(catalog.operations.size());
	for (const owner_state &entry : catalog.owners)
	{
		payload.number<uint8_t>(static_cast<uint8_t>(entry.owner.type));
		payload.number(entry.owner.id);
		payload.number(entry.owner.context_id);
		payload.number(entry.revision);
	}
	for (const flatfile_item_ownership_record &entry : catalog.items)
	{
		payload.number(entry.item_uid);
		payload.number(entry.root_item_uid);
		payload.number(entry.parent_item_uid);
		payload.number<uint8_t>(static_cast<uint8_t>(entry.owner.type));
		payload.number(entry.owner.id);
		payload.number(entry.owner.context_id);
		payload.number(entry.item_revision);
		payload.number(entry.vnum);
		payload.number<uint8_t>(static_cast<uint8_t>(entry.state));
		if (entry.coin_payload.size() > ITEM_TRANSFER_ITEM_BLOB_MAX_BYTES)
			return false;
		payload.number<uint32_t>(entry.coin_payload.size());
		if (!entry.coin_payload.empty())
			payload.raw(entry.coin_payload.data(), entry.coin_payload.size());
	}
	for (const operation_state &entry : catalog.operations)
	{
		payload.raw(entry.operation_id.bytes.data(), entry.operation_id.bytes.size());
		payload.raw(entry.command_digest.data(), entry.command_digest.size());
		payload.number<uint32_t>(entry.result_code);
		payload.number(entry.result.root_item_uid);
		payload.number(entry.result.item_count);
		payload.number(entry.result.from_owner_revision);
		payload.number(entry.result.to_owner_revision);
		payload.number(entry.result.max_item_revision);
		payload.number(entry.result.corpse_revision);
		payload.number<uint8_t>(entry.result.collector_catalog_changed ? 1 : 0);
		// The coin transfer flag, which no operation sets any more.
		payload.number<uint8_t>(0);
	}
	if (!payload.valid || payload.bytes.size() > ownership_maximum_bytes)
		return false;
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(payload.bytes.data(), payload.bytes.size(), digest);
	encoder file;
	file.raw(ownership_magic.data(), ownership_magic.size());
	file.number<uint32_t>(ownership_format_version);
	file.number<uint32_t>(payload.bytes.size());
	file.number(revision);
	file.raw(digest, sizeof(digest));
	file.raw(payload.bytes.data(), payload.bytes.size());
	if (!file.valid || file.bytes.size() > ownership_maximum_bytes)
		return false;
	*bytes = std::move(file.bytes);
	return true;
}

bool valid_catalog(const ownership_catalog &catalog)
{
	if (!std::is_sorted(catalog.owners.begin(), catalog.owners.end(),
			    [](const owner_state &left, const owner_state &right)
			    { return owner_less(left.owner, right.owner); }) ||
	    !std::is_sorted(catalog.items.begin(), catalog.items.end(), item_less))
		return false;
	for (size_t index = 0; index < catalog.owners.size(); ++index)
		if (!item_owner_identity_valid(catalog.owners[index].owner) ||
		    (index && item_owner_identity_equal(catalog.owners[index - 1].owner,
							catalog.owners[index].owner)))
			return false;
	for (size_t index = 0; index < catalog.items.size(); ++index)
	{
		const auto &entry = catalog.items[index];
		if (!entry.item_uid || !entry.root_item_uid || entry.vnum <= 0 ||
		    !item_owner_identity_valid(entry.owner) ||
		    entry.state == item_custody_state::absent ||
		    entry.state > item_custody_state::quarantined ||
		    (index && catalog.items[index - 1].item_uid == entry.item_uid) ||
		    !find_owner(const_cast<ownership_catalog *>(&catalog), entry.owner))
			return false;
		if (!entry.coin_payload.empty())
		{
			std::vector<player_item_snapshot> items;
			if (entry.coin_payload.size() > ITEM_TRANSFER_ITEM_BLOB_MAX_BYTES ||
			    player_item_snapshot_list_decode(entry.coin_payload.data(),
							     entry.coin_payload.size(), &items) !=
				    player_snapshot_codec_result::ok ||
			    items.size() != 1 || items[0].object_uid != entry.item_uid ||
			    items[0].vnum != entry.vnum || items[0].type != ITEM_MONEY)
				return false;
		}
	}
	std::unordered_set<std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES>, operation_id_hash>
		operation_ids;
	try
	{
		operation_ids.reserve(catalog.operations.size());
		for (const operation_state &entry : catalog.operations)
			if (critical_operation_id_is_zero(entry.operation_id) ||
			    !entry.result.root_item_uid || !entry.result.item_count ||
			    entry.result.item_count > ITEM_TRANSFER_MAX_ITEMS ||
			    !operation_ids.insert(entry.operation_id.bytes).second)
				return false;
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	return true;
}

flatfile_item_repository_result decode_catalog(const std::vector<uint8_t> &bytes,
					       ownership_catalog *catalog)
{
	constexpr size_t header_size = ownership_magic.size() + sizeof(uint32_t) * 2 +
				       sizeof(uint64_t) + SHA256_DIGEST_LENGTH;
	if (!catalog || bytes.size() < header_size ||
	    memcmp(bytes.data(), ownership_magic.data(), ownership_magic.size()))
		return flatfile_item_repository_result::invalid;
	decoder header{ bytes.data() + ownership_magic.size(),
			bytes.size() - ownership_magic.size() };
	uint32_t version = 0, payload_size = 0;
	uint64_t revision = 0;
	if (!header.number(&version) || !header.number(&payload_size) ||
	    !header.number(&revision) ||
	    (version < ownership_legacy_format_version || version > ownership_format_version) ||
	    !revision || payload_size != bytes.size() - header_size)
		return flatfile_item_repository_result::invalid;
	const uint8_t *stored_digest =
		bytes.data() + ownership_magic.size() + sizeof(uint32_t) * 2 + sizeof(uint64_t);
	const uint8_t *payload = bytes.data() + header_size;
	unsigned char actual_digest[SHA256_DIGEST_LENGTH];
	SHA256(payload, payload_size, actual_digest);
	if (CRYPTO_memcmp(stored_digest, actual_digest, sizeof(actual_digest)))
		return flatfile_item_repository_result::invalid;
	decoder input{ payload, payload_size };
	uint32_t owner_count = 0, item_count = 0, operation_count = 0;
	if (!input.number(&owner_count) || !input.number(&item_count) ||
	    !input.number(&operation_count) || owner_count > ownership_maximum_entries ||
	    item_count > ownership_maximum_entries ||
	    operation_count > ownership_maximum_operations)
		return flatfile_item_repository_result::invalid;
	ownership_catalog decoded;
	decoded.revision = revision;
	try
	{
		decoded.owners.resize(owner_count);
		decoded.items.resize(item_count);
		decoded.operations.resize(operation_count);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	for (owner_state &entry : decoded.owners)
	{
		uint8_t type = 0;
		if (!input.number(&type) || !input.number(&entry.owner.id) ||
		    !input.number(&entry.owner.context_id) || !input.number(&entry.revision))
			return flatfile_item_repository_result::invalid;
		entry.owner.type = static_cast<item_owner_type>(type);
	}
	for (flatfile_item_ownership_record &entry : decoded.items)
	{
		uint8_t type = 0, state = 0;
		if (!input.number(&entry.item_uid) || !input.number(&entry.root_item_uid) ||
		    !input.number(&entry.parent_item_uid) || !input.number(&type) ||
		    !input.number(&entry.owner.id) || !input.number(&entry.owner.context_id) ||
		    !input.number(&entry.item_revision) || !input.number(&entry.vnum) ||
		    !input.number(&state))
			return flatfile_item_repository_result::invalid;
		entry.owner.type = static_cast<item_owner_type>(type);
		entry.state = static_cast<item_custody_state>(state);
		if (version >= 3)
		{
			uint32_t size = 0;
			if (!input.number(&size) || size > ITEM_TRANSFER_ITEM_BLOB_MAX_BYTES ||
			    size > input.size - input.offset)
				return flatfile_item_repository_result::invalid;
			try
			{
				entry.coin_payload.resize(size);
			}
			catch (const std::bad_alloc &)
			{
				return flatfile_item_repository_result::io_error;
			}
			if (size && !input.raw(entry.coin_payload.data(), size))
				return flatfile_item_repository_result::invalid;
		}
	}
	for (operation_state &entry : decoded.operations)
	{
		if (!input.raw(entry.operation_id.bytes.data(), entry.operation_id.bytes.size()) ||
		    !input.raw(entry.command_digest.data(), entry.command_digest.size()) ||
		    !input.number(&entry.result_code) ||
		    !input.number(&entry.result.root_item_uid) ||
		    !input.number(&entry.result.item_count) ||
		    !input.number(&entry.result.from_owner_revision) ||
		    !input.number(&entry.result.to_owner_revision) ||
		    !input.number(&entry.result.max_item_revision) ||
		    (version >= 2 && !input.number(&entry.result.corpse_revision)))
			return flatfile_item_repository_result::invalid;
		if (version >= 4)
		{
			uint8_t collector_changed = 0;
			if (!input.number(&collector_changed) || collector_changed > 1)
				return flatfile_item_repository_result::invalid;
			entry.result.collector_catalog_changed = collector_changed != 0;
		}
		if (version >= 3)
		{
			uint8_t coin = 0;
			if (!input.number(&coin) || coin != 0)
				return flatfile_item_repository_result::invalid;
		}
	}
	if (input.offset != input.size || !valid_catalog(decoded))
		return flatfile_item_repository_result::invalid;
	*catalog = std::move(decoded);
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result load_catalog(const std::string &root, ownership_catalog *catalog,
					     std::string *error)
{
	if (!catalog)
		return flatfile_item_repository_result::invalid;
	std::vector<uint8_t> bytes;
	const flatfile_read_result read = flatfile_read(domains_directory(root), ownership_filename,
							ownership_maximum_bytes, &bytes, error);
	if (read == flatfile_read_result::not_found)
	{
		*catalog = {};
		return flatfile_item_repository_result::not_found;
	}
	if (read == flatfile_read_result::invalid)
		return flatfile_item_repository_result::invalid;
	if (read != flatfile_read_result::ok)
		return flatfile_item_repository_result::io_error;
	return decode_catalog(bytes, catalog);
}

critical_apply_result make_result(critical_apply_outcome outcome, unsigned int error_code,
				  const item_transfer_result &result)
{
	critical_apply_result applied = {
		outcome,
		std::max({ result.from_owner_revision, result.to_owner_revision,
			   result.max_item_revision, result.corpse_revision }),
		error_code
	};
	std::array<uint8_t, ITEM_TRANSFER_RESULT_BYTES> encoded = {};
	if (!item_transfer_command_encode_result(result, &encoded))
		return { critical_apply_outcome::terminal_failure, 0, EBADMSG };
	applied.result_size = encoded.size();
	std::copy(encoded.begin(), encoded.end(), applied.result_payload.begin());
	return applied;
}

bool command_digest(const critical_command &command,
		    std::array<uint8_t, SHA256_DIGEST_LENGTH> *digest)
{
	std::vector<uint8_t> encoded;
	if (!digest ||
	    critical_command_encode(command, &encoded) != critical_command_codec_result::ok)
		return false;
	SHA256(encoded.data(), encoded.size(), digest->data());
	return true;
}

bool generic_materialization_owner(item_owner_type type)
{
	return type == item_owner_type::player || type == item_owner_type::system ||
	       type == item_owner_type::destruction;
}

// A grant creates items in a room; an operator repair moves them to its floor.
bool room_transfer(const item_transfer_payload &payload)
{
	const bool create = payload.from_owner.type == item_owner_type::system &&
			    payload.to_owner.type == item_owner_type::room &&
			    payload.reason == item_transfer_reason::creation &&
			    !payload.target_parent_item_uid;
	const bool reparent = item_owner_identity_equal(payload.from_owner, payload.to_owner) &&
			      payload.from_owner.type == item_owner_type::room &&
			      payload.reason == item_transfer_reason::operator_repair &&
			      !payload.target_parent_item_uid;
	return create || reparent;
}

bool generic_transfer_supported(const item_transfer_payload &payload)
{
	return (generic_materialization_owner(payload.from_owner.type) &&
		generic_materialization_owner(payload.to_owner.type)) ||
	       room_transfer(payload);
}

bool room_custody_matches(ownership_catalog &catalog, const item_owner_identity &owner,
			  const std::vector<flatfile_corpse_custody_item> &expected, bool created)
{
	const owner_state *stored_owner = find_owner(&catalog, owner);
	if (!stored_owner)
		return created && expected.empty();
	if (created && (stored_owner->revision || !expected.empty()))
		return false;
	size_t index = 0;
	for (const auto &item : catalog.items)
	{
		if (item.state != item_custody_state::active ||
		    !item_owner_identity_equal(item.owner, owner))
			continue;
		if (index >= expected.size() || expected[index].item_uid != item.item_uid ||
		    expected[index].vnum != item.vnum ||
		    expected[index].root_item_uid != item.root_item_uid ||
		    expected[index].parent_item_uid != item.parent_item_uid)
			return false;
		++index;
	}
	return index == expected.size();
}

bool descendant_of(const std::vector<flatfile_item_ownership_record *> &root_items,
		   const flatfile_item_ownership_record &candidate, uint64_t selected_uid)
{
	uint64_t ancestor = candidate.item_uid;
	for (size_t depth = 0; depth <= root_items.size(); ++depth)
	{
		if (ancestor == selected_uid)
			return true;
		auto parent = std::find_if(root_items.begin(), root_items.end(),
					   [ancestor](const auto *entry)
					   { return entry->item_uid == ancestor; });
		if (parent == root_items.end() || !(*parent)->parent_item_uid)
			return false;
		ancestor = (*parent)->parent_item_uid;
	}
	return false;
}

// The flat-file form of claim_transfer_item(): make the catalog name `holder` for an
// item a transfer takes from memory. A missing record is added, another owner's
// record is taken (logged to logs/log/item_claims), and a stale placement is
// corrected. `parent_uid` null keeps the recorded parent. A destroyed record is never
// revived: *refused is set instead.
unsigned int claim_catalog_item(ownership_catalog *catalog, const item_owner_identity &holder,
				uint64_t item_uid, uint64_t root_uid, const uint64_t *parent_uid,
				int32_t vnum, uint64_t *revision, bool *refused)
{
	if (!catalog || !item_uid || !revision || !refused)
		return EINVAL;
	*refused = false;
	flatfile_item_ownership_record *item = find_item(catalog, item_uid);
	if (!item)
	{
		if (catalog->items.size() >= ownership_maximum_entries)
			return ENOSPC;
		try
		{
			const flatfile_item_ownership_record added = {
				item_uid, root_uid, parent_uid ? *parent_uid : 0, holder,
				1,	  vnum,	    item_custody_state::active
			};
			catalog->items.insert(std::upper_bound(catalog->items.begin(),
							       catalog->items.end(), added,
							       item_less),
					      added);
		}
		catch (const std::bad_alloc &)
		{
			return ENOMEM;
		}
		*revision = 1;
		return 0;
	}
	if (item_claim_leaves_out(item->state))
	{
		*refused = true;
		return 0;
	}
	const uint64_t parent = parent_uid ? *parent_uid : item->parent_item_uid;
	const int32_t wanted_vnum = vnum ? vnum : item->vnum;
	const bool owned = item_owner_identity_equal(item->owner, holder);
	*revision = item->item_revision;
	if (owned && item->root_item_uid == root_uid && item->parent_item_uid == parent &&
	    item->vnum == wanted_vnum && item->state == item_custody_state::active)
		return 0;
	if (item->item_revision == std::numeric_limits<uint64_t>::max())
		return ERANGE;
	if (!owned)
		item_claim_log_item(item_uid, wanted_vnum, item->owner, holder);
	item->owner = holder;
	item->root_item_uid = root_uid;
	item->parent_item_uid = parent;
	item->vnum = wanted_vnum;
	item->state = item_custody_state::active;
	*revision = ++item->item_revision;
	return 0;
}

unsigned int apply_transfer(ownership_catalog *catalog, const item_transfer_payload &payload,
			    item_transfer_result *result)
{
	if (!catalog || !result)
		return EINVAL;
	if (!ensure_owner(catalog, payload.from_owner) || !ensure_owner(catalog, payload.to_owner))
		return ENOSPC;
	owner_state *from_owner = find_owner(catalog, payload.from_owner);
	owner_state *to_owner = find_owner(catalog, payload.to_owner);
	if (!from_owner || !to_owner)
		return EILSEQ;
	const bool same_owner = item_owner_identity_equal(payload.from_owner, payload.to_owner);
	*result = { item_transfer_result_root(payload),
		    payload.item_count,
		    from_owner->revision,
		    to_owner->revision,
		    0,
		    0 };
	// Memory is the authority for a player, room, corpse, locker or pet: saves move
	// their revisions, so a transfer does not fence on them, and it takes the items
	// from whatever the catalog still says.
	const bool memory_held = item_claim_owner_is_memory_held(payload.from_owner.type);
	if ((!memory_held && from_owner->revision != payload.expected_from_revision) ||
	    (!item_claim_owner_is_memory_held(payload.to_owner.type) &&
	     to_owner->revision != payload.expected_to_revision))
		return ESTALE;
	const bool creation = payload.from_owner.type == item_owner_type::system;
	std::array<uint64_t, ITEM_TRANSFER_MAX_ITEMS> claimed_revisions = {};
	if (!creation && memory_held)
		for (size_t index = 0; index < payload.item_count; ++index)
		{
			const item_transfer_entry &entry = payload.items[index];
			bool refused = false;
			if (const unsigned int failed = claim_catalog_item(
				    catalog, payload.from_owner, entry.item_uid,
				    entry.root_item_uid, &entry.parent_item_uid, entry.vnum,
				    &claimed_revisions[index], &refused))
				return failed;
			if (refused)
				return ESTALE;
		}
	uint64_t target_parent_revision = payload.expected_target_parent_revision;
	if (payload.target_parent_item_uid &&
	    item_claim_owner_is_memory_held(payload.to_owner.type))
	{
		bool refused = false;
		if (const unsigned int failed = claim_catalog_item(
			    catalog, payload.to_owner, payload.target_parent_item_uid,
			    payload.target_root_item_uid, nullptr, 0, &target_parent_revision,
			    &refused))
			return failed;
		if (refused)
			return ESTALE;
	}
	std::vector<flatfile_item_ownership_record *> root_items;
	std::vector<flatfile_item_ownership_record *> selected;
	try
	{
		std::vector<uint64_t> source_roots;
		for (size_t index = 0; index < payload.item_count; ++index)
			source_roots.push_back(payload.items[index].root_item_uid);
		std::sort(source_roots.begin(), source_roots.end());
		source_roots.erase(std::unique(source_roots.begin(), source_roots.end()),
				   source_roots.end());
		for (auto &entry : catalog->items)
			if (std::binary_search(source_roots.begin(), source_roots.end(),
					       entry.root_item_uid))
				root_items.push_back(&entry);
	}
	catch (const std::bad_alloc &)
	{
		return ENOMEM;
	}
	if ((creation && !root_items.empty()) || (!creation && root_items.empty()))
		return creation ? EEXIST : ENOENT;
	if (creation)
	{
		for (size_t index = 0; index < payload.item_count; ++index)
			if (find_item(catalog, payload.items[index].item_uid))
				return EEXIST;
		if (catalog->items.size() > ownership_maximum_entries - payload.item_count)
			return ENOSPC;
	}
	else
	{
		std::vector<uint64_t> selected_roots;
		try
		{
			for (size_t index = 0; index < payload.item_count; ++index)
				if (item_transfer_selected_root(payload,
								payload.items[index].item_uid) ==
				    payload.items[index].item_uid)
					selected_roots.push_back(payload.items[index].item_uid);
		}
		catch (const std::bad_alloc &)
		{
			return ENOMEM;
		}
		for (auto *entry : root_items)
			for (uint64_t selected_root : selected_roots)
				if (descendant_of(root_items, *entry, selected_root))
				{
					selected.push_back(entry);
					break;
				}
		if (selected.size() != payload.item_count)
			return EMSGSIZE;
		std::sort(selected.begin(), selected.end(), [](const auto *left, const auto *right)
			  { return left->item_uid < right->item_uid; });
		for (size_t index = 0; index < payload.item_count; ++index)
		{
			const auto &stored = *selected[index];
			const auto &expected = payload.items[index];
			result->max_item_revision =
				std::max(result->max_item_revision, stored.item_revision);
			const auto claimed = std::find_if(
				payload.items.begin(), payload.items.begin() + payload.item_count,
				[&](const item_transfer_entry &item)
				{ return item.item_uid == stored.item_uid; });
			const uint64_t expected_revision =
				memory_held && claimed !=
							payload.items.begin() + payload.item_count ?
					claimed_revisions[static_cast<size_t>(
						claimed - payload.items.begin())] :
					expected.expected_item_revision;
			const item_custody_state expected_state =
				memory_held ? item_custody_state::active : expected.expected_state;
			if (stored.item_uid != expected.item_uid ||
			    stored.root_item_uid != expected.root_item_uid ||
			    stored.parent_item_uid != expected.parent_item_uid ||
			    !item_owner_identity_equal(stored.owner, payload.from_owner) ||
			    stored.item_revision != expected_revision ||
			    stored.vnum != expected.vnum || stored.state != expected_state)
				return ESTALE;
		}
	}
	if (payload.target_parent_item_uid)
	{
		const auto *parent = find_item(catalog, payload.target_parent_item_uid);
		if (!parent || parent->root_item_uid != payload.target_root_item_uid ||
		    !item_owner_identity_equal(parent->owner, payload.to_owner) ||
		    parent->item_revision != target_parent_revision ||
		    parent->state != item_custody_state::active)
			return ESTALE;
	}
	if (from_owner->revision == std::numeric_limits<uint64_t>::max() ||
	    (!same_owner && to_owner->revision == std::numeric_limits<uint64_t>::max()))
		return ERANGE;
	if (creation)
	{
		try
		{
			for (size_t index = 0; index < payload.item_count; ++index)
			{
				const auto &entry = payload.items[index];
				uint64_t target_root = 0, target_parent = 0;
				if (!item_transfer_target_topology(payload, entry.item_uid,
								   &target_root, &target_parent))
					return EINVAL;
				catalog->items.push_back({ entry.item_uid, target_root,
							   target_parent, payload.to_owner, 1,
							   entry.vnum,
							   item_custody_state::active });
				result->max_item_revision = 1;
			}
			std::sort(catalog->items.begin(), catalog->items.end(), item_less);
		}
		catch (const std::bad_alloc &)
		{
			return ENOMEM;
		}
	}
	else
	{
		for (size_t index = 0; index < payload.item_count; ++index)
		{
			uint64_t target_root = 0, target_parent = 0;
			if (selected[index]->item_revision ==
				    std::numeric_limits<uint64_t>::max() ||
			    !item_transfer_target_topology(payload, selected[index]->item_uid,
							   &target_root, &target_parent))
				return selected[index]->item_revision ==
						       std::numeric_limits<uint64_t>::max() ?
					       ERANGE :
					       EINVAL;
		}
		for (size_t index = 0; index < payload.item_count; ++index)
		{
			auto &entry = *selected[index];
			uint64_t target_root = 0, target_parent = 0;
			if (!item_transfer_target_topology(payload, entry.item_uid, &target_root,
							   &target_parent))
				return EINVAL;
			++entry.item_revision;
			entry.root_item_uid = target_root;
			entry.parent_item_uid = target_parent;
			entry.owner = payload.to_owner;
			entry.state = payload.to_owner.type == item_owner_type::destruction ?
					      item_custody_state::destroyed :
					      item_custody_state::active;
			result->max_item_revision =
				std::max(result->max_item_revision, entry.item_revision);
		}
	}
	++from_owner->revision;
	if (!same_owner)
		++to_owner->revision;
	result->from_owner_revision = from_owner->revision;
	result->to_owner_revision = same_owner ? from_owner->revision : to_owner->revision;
	return 0;
}
} // namespace

flatfile_item_repository_result flatfile_item_repository_load_owner(
	const std::string &root, const item_owner_identity &owner, uint64_t *owner_revision,
	std::vector<flatfile_item_ownership_record> *items, std::string *error)
{
	if (!item_owner_identity_valid(owner) || !owner_revision || !items)
		return flatfile_item_repository_result::invalid;
	std::lock_guard<std::mutex> guard(ownership_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_item_repository_result::io_error;
	const auto recovered = flatfile_authority_transaction_recover(root, authority, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	return flatfile_item_repository_load_owner_locked(root, authority, owner, owner_revision,
							  items, error);
}

flatfile_item_repository_result flatfile_item_repository_load_owner_locked(
	const std::string &root, const flatfile_authority_lock &lock,
	const item_owner_identity &owner, uint64_t *owner_revision,
	std::vector<flatfile_item_ownership_record> *items, std::string *error)
{
	if (!lock.matches(root) || !item_owner_identity_valid(owner) || !owner_revision || !items)
		return flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const flatfile_item_repository_result loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	const owner_state *stored_owner = find_owner(&catalog, owner);
	if (!stored_owner)
		return flatfile_item_repository_result::not_found;
	std::vector<flatfile_item_ownership_record> selected;
	try
	{
		for (const auto &entry : catalog.items)
			if (entry.state == item_custody_state::active &&
			    item_owner_identity_equal(entry.owner, owner))
				selected.push_back(entry);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	*owner_revision = stored_owner->revision;
	*items = std::move(selected);
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result
flatfile_item_repository_load_uids(const std::string &root, const std::vector<uint64_t> &uids,
				   std::vector<flatfile_item_ownership_record> *records,
				   std::string *error)
{
	if (!records)
		return flatfile_item_repository_result::invalid;
	std::lock_guard<std::mutex> guard(ownership_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_item_repository_result::io_error;
	const auto recovered = flatfile_authority_transaction_recover(root, authority, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	return flatfile_item_repository_load_uids_locked(root, authority, uids, records, error);
}

flatfile_item_repository_result flatfile_item_repository_load_uids_locked(
	const std::string &root, const flatfile_authority_lock &lock,
	const std::vector<uint64_t> &uids, std::vector<flatfile_item_ownership_record> *records,
	std::string *error)
{
	if (!lock.matches(root) || !records)
		return flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	records->clear();
	if (loaded == flatfile_item_repository_result::not_found)
		return flatfile_item_repository_result::ok;
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	try
	{
		for (uint64_t uid : uids)
			if (const auto *item = find_item(&catalog, uid); item)
				records->push_back(*item);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	return flatfile_item_repository_result::ok;
}

// The caller selects ITEM_MONEY identities from the original snapshot. Include
// their tombstones even though consumed records no longer have a coin payload.
flatfile_item_repository_result flatfile_item_repository_load_coins_locked(
	const std::string &root, const flatfile_authority_lock &lock,
	const std::vector<uint64_t> &uids, std::vector<flatfile_item_ownership_record> *coins,
	std::string *error)
{
	if (!lock.matches(root) || !coins || uids.size() > PLAYER_SNAPSHOT_MAX_OBJECTS)
		return flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	try
	{
		coins->clear();
		for (uint64_t uid : uids)
			if (const auto *item = find_item(&catalog, uid); item)
				coins->push_back(*item);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result flatfile_item_repository_list_collector_items_locked(
	const std::string &root, const flatfile_authority_lock &lock,
	std::vector<item_ownership_runtime_entry> *items, std::string *error)
{
	if (!lock.matches(root) || !items)
		return flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	std::vector<item_ownership_runtime_entry> selected;
	try
	{
		for (const auto &entry : catalog.items)
		{
			if (entry.owner.type != item_owner_type::collector)
				continue;
			const owner_state *owner = find_owner(&catalog, entry.owner);
			if (!owner)
				return flatfile_item_repository_result::invalid;
			selected.push_back({ entry.item_uid, entry.root_item_uid,
					     entry.parent_item_uid, entry.owner,
					     entry.item_revision, owner->revision, entry.vnum,
					     entry.state });
		}
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	*items = std::move(selected);
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result flatfile_item_repository_prepare_collector_transfer(
	const std::string &root, const flatfile_authority_lock &lock,
	const collector_command_payload &payload, flatfile_item_collector_mutation *mutation,
	unsigned int *result_code, std::string *error)
{
	if (root.empty() || !lock.matches(root) || !mutation || !result_code ||
	    !payload.item_count || payload.item_count > payload.items.size())
		return flatfile_item_repository_result::invalid;
	*mutation = {};
	*result_code = 0;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded == flatfile_item_repository_result::not_found)
	{
		*result_code = ENOENT;
		return flatfile_item_repository_result::ok;
	}
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	if (!ensure_owner(&catalog, payload.from_owner) ||
	    !ensure_owner(&catalog, payload.to_owner))
	{
		*result_code = ENOSPC;
		return flatfile_item_repository_result::ok;
	}
	owner_state *from = find_owner(&catalog, payload.from_owner);
	owner_state *to = find_owner(&catalog, payload.to_owner);
	if (!from || !to)
		return flatfile_item_repository_result::invalid;
	mutation->from_owner_revision = from->revision;
	mutation->to_owner_revision = to->revision;
	// Memory is the authority for the player buying and for the room or corpse an
	// antiquity is collected from: saves move their revisions.
	if ((!item_claim_owner_is_memory_held(payload.from_owner.type) &&
	     from->revision != payload.expected_from_owner_revision) ||
	    (!item_claim_owner_is_memory_held(payload.to_owner.type) &&
	     to->revision != payload.expected_to_owner_revision))
	{
		*result_code = ESTALE;
		return flatfile_item_repository_result::ok;
	}
	if (from->revision == UINT64_MAX || to->revision == UINT64_MAX ||
	    catalog.revision == UINT64_MAX)
	{
		*result_code = ERANGE;
		return flatfile_item_repository_result::ok;
	}
	std::vector<flatfile_item_ownership_record *> source;
	try
	{
		for (auto &item : catalog.items)
			if (item.root_item_uid == payload.items[0].root_item_uid)
				source.push_back(&item);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	if (source.size() != payload.item_count)
	{
		*result_code = EMSGSIZE;
		return flatfile_item_repository_result::ok;
	}
	std::sort(source.begin(), source.end(), [](const auto *left, const auto *right)
		  { return left->item_uid < right->item_uid; });
	for (size_t index = 0; index < source.size(); ++index)
	{
		const auto &stored = *source[index];
		const auto &expected = payload.items[index];
		if (stored.item_uid != expected.item_uid ||
		    stored.root_item_uid != expected.root_item_uid ||
		    stored.parent_item_uid != expected.parent_item_uid ||
		    !item_owner_identity_equal(stored.owner, payload.from_owner) ||
		    stored.item_revision != expected.expected_item_revision ||
		    stored.vnum != expected.vnum || stored.state != expected.expected_state)
		{
			*result_code = ESTALE;
			return flatfile_item_repository_result::ok;
		}
		if (stored.item_revision == UINT64_MAX)
		{
			*result_code = ERANGE;
			return flatfile_item_repository_result::ok;
		}
	}
	auto selected = std::find_if(source.begin(), source.end(), [&](const auto *item)
				     { return item->item_uid == payload.selected_item_uid; });
	if (selected == source.end())
	{
		*result_code = ESTALE;
		return flatfile_item_repository_result::ok;
	}
	const uint64_t selected_parent = (*selected)->parent_item_uid;
	const bool collect = payload.action == collector_action::collect;
	if (!collect && source.size() != 1)
	{
		*result_code = EMSGSIZE;
		return flatfile_item_repository_result::ok;
	}
	for (auto *item : source)
	{
		uint64_t new_root = item->root_item_uid;
		uint64_t new_parent = item->parent_item_uid;
		if (collect && item != *selected && item->root_item_uid == (*selected)->item_uid)
		{
			const flatfile_item_ownership_record *cursor = item;
			for (size_t depth = 0; depth <= source.size(); ++depth)
			{
				if (cursor->parent_item_uid == (*selected)->item_uid)
				{
					new_root = cursor->item_uid;
					break;
				}
				auto parent = std::find_if(
					source.begin(), source.end(), [&](const auto *candidate)
					{ return candidate->item_uid == cursor->parent_item_uid; });
				if (parent == source.end())
				{
					new_root = 0;
					break;
				}
				cursor = *parent;
			}
			if (!new_root)
			{
				*result_code = EBADMSG;
				return flatfile_item_repository_result::ok;
			}
		}
		if (collect && item->parent_item_uid == (*selected)->item_uid)
			new_parent = selected_parent;
		++item->item_revision;
		if (item == *selected)
		{
			item->root_item_uid = item->item_uid;
			item->parent_item_uid = 0;
			item->owner = payload.to_owner;
			item->state = payload.target_state;
			mutation->item_revision = item->item_revision;
		}
		else
		{
			item->root_item_uid = new_root;
			item->parent_item_uid = new_parent;
		}
	}
	++from->revision;
	++to->revision;
	mutation->from_owner_revision = from->revision;
	mutation->to_owner_revision = to->revision;
	mutation->after_image.filename = ownership_filename;
	if (!encode_catalog(catalog, catalog.revision + 1, &mutation->after_image.bytes))
		return flatfile_item_repository_result::invalid;
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result flatfile_item_repository_list_active_player_items(
	const std::string &root, std::vector<flatfile_item_ownership_record> *items,
	std::string *error)
{
	if (root.empty() || !items)
		return flatfile_item_repository_result::invalid;
	std::lock_guard<std::mutex> guard(ownership_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_item_repository_result::io_error;
	const auto recovered = flatfile_authority_transaction_recover(root, authority, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	std::vector<flatfile_item_ownership_record> selected;
	try
	{
		for (const auto &entry : catalog.items)
			if (entry.state == item_custody_state::active &&
			    entry.owner.type == item_owner_type::player)
				selected.push_back(entry);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	*items = std::move(selected);
	return flatfile_item_repository_result::ok;
}

namespace
{
flatfile_item_repository_result player_file_unreadable(flatfile_player_load_result read,
						       int32_t pid, std::string *error)
{
	if (error)
		*error = "player file " + flatfile_player_snapshot_file::player_filename(pid) +
			 " cannot be read" + (error->empty() ? "" : ": " + *error);
	return read == flatfile_player_load_result::io_error ?
		       flatfile_item_repository_result::io_error :
		       flatfile_item_repository_result::invalid;
}

void add_uids(const player_snapshot &snapshot, std::unordered_set<uint64_t> *uids)
{
	for (const auto &item : snapshot.items)
		uids->insert(item.object_uid);
	for (const auto &pet : snapshot.pets)
		for (const auto &item : pet.items)
			uids->insert(item.object_uid);
}

// Add the uids player pid's next load holds: its file's items and its pets', and what a
// committed transfer (a purchase, a grant) still delivers to it, which the load
// reconciles from the player's active records first. A player with no file holds
// nothing.
flatfile_item_repository_result add_player_load_uids(const std::string &root,
						     const flatfile_authority_lock &authority,
						     const ownership_catalog &catalog, uint64_t pid,
						     std::unordered_set<uint64_t> *uids,
						     std::string *error)
{
	player_snapshot snapshot;
	const auto read =
		flatfile_player_snapshot_read(root, static_cast<int32_t>(pid), &snapshot, error);
	if (read == flatfile_player_load_result::not_found)
		return flatfile_item_repository_result::ok;
	if (read != flatfile_player_load_result::ok)
		return player_file_unreadable(read, static_cast<int32_t>(pid), error);
	const item_owner_identity player = { item_owner_type::player, pid, 0 };
	std::vector<flatfile_item_ownership_record> owned;
	for (const auto &record : catalog.items)
		if (record.state == item_custody_state::active &&
		    item_owner_identity_equal(record.owner, player))
			owned.push_back(record);
	const auto reconciled = flatfile_shop_trade_materialization_reconcile(
		root, authority, static_cast<uint32_t>(pid), owned, &snapshot, error);
	if (reconciled != flatfile_shop_trade_materialization_result::ok)
		return reconciled == flatfile_shop_trade_materialization_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	add_uids(snapshot, uids);
	return flatfile_item_repository_result::ok;
}

bool active_player_record(const flatfile_item_ownership_record &record)
{
	return record.owner.type == item_owner_type::player && !record.owner.context_id &&
	       record.state == item_custody_state::active;
}
} // namespace

flatfile_item_repository_result
flatfile_item_repository_reap_unheld_player_items(const std::string &root, uint64_t *deleted,
						  std::string *error)
{
	if (root.empty() || !deleted)
		return flatfile_item_repository_result::invalid;
	*deleted = 0;
	// A load skips a copy whose record names another owner, so a record stays while any
	// stored payload carries its item: a player file, a locker chest, a corpse or a room.
	// The locker and world stores take the authority lock themselves, so they are read
	// first; at boot nothing else writes.
	std::vector<flatfile_locker_record> lockers;
	std::vector<flatfile_locker_access_record> access;
	const auto listed_lockers = flatfile_locker_list(root, &lockers, &access, error);
	if (listed_lockers != flatfile_locker_result::ok &&
	    listed_lockers != flatfile_locker_result::not_found)
		return listed_lockers == flatfile_locker_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	std::vector<flatfile_corpse_record> corpses;
	std::vector<flatfile_saved_world_item_record> saved;
	std::vector<flatfile_room_item_record> rooms;
	auto listed_world = flatfile_world_item_list(root, &corpses, &saved, error);
	if (listed_world == flatfile_world_item_result::ok)
		listed_world = flatfile_world_item_list_rooms(root, &rooms, error);
	if (listed_world != flatfile_world_item_result::ok &&
	    listed_world != flatfile_world_item_result::not_found)
		return listed_world == flatfile_world_item_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	std::lock_guard<std::mutex> guard(ownership_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_item_repository_result::io_error;
	const auto recovered = flatfile_authority_transaction_recover(root, authority, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	std::unordered_set<uint64_t> stale;
	try
	{
		std::unordered_set<uint64_t> carried;
		for (const auto &locker : lockers)
			for (const auto &chest : locker.chests)
				for (const auto &item : chest.items)
					carried.insert(item.object_uid);
		for (const auto &corpse : corpses)
			for (const auto &item : corpse.items)
				carried.insert(item.object_uid);
		for (const auto &room : rooms)
			for (const auto &item : room.items)
				carried.insert(item.object_uid);
		// Every player file; one that cannot be read stops the reap, since any record
		// may be what keeps a copy in it out.
		std::error_code listed;
		const std::string players = flatfile_player_snapshot_file::player_directory(root);
		for (std::filesystem::directory_iterator entry(players, listed), end;
		     !listed && entry != end; entry.increment(listed))
		{
			const std::string name = entry->path().filename().string();
			const long pid = strtol(name.c_str(), nullptr, 10);
			if (pid <= 0 || pid > INT32_MAX ||
			    name != flatfile_player_snapshot_file::player_filename(
					    static_cast<int32_t>(pid)))
				continue;
			player_snapshot snapshot;
			const auto read = flatfile_player_snapshot_read(
				root, static_cast<int32_t>(pid), &snapshot, error);
			if (read != flatfile_player_load_result::ok)
				return player_file_unreadable(read, static_cast<int32_t>(pid),
							      error);
			add_uids(snapshot, &carried);
		}
		if (listed && listed != std::errc::no_such_file_or_directory)
		{
			if (error)
				*error = players + ": " + listed.message();
			return flatfile_item_repository_result::io_error;
		}
		// What a committed transfer still delivers is held too; only a record naming
		// the player can be delivered to it, so only those players are reconciled.
		std::unordered_set<uint64_t> owners;
		for (const auto &record : catalog.items)
			if (active_player_record(record) && !carried.count(record.item_uid))
				owners.insert(record.owner.id);
		for (const uint64_t pid : owners)
			if (const auto read = add_player_load_uids(root, authority, catalog, pid,
								   &carried, error);
			    read != flatfile_item_repository_result::ok)
				return read;
		for (const auto &record : catalog.items)
			if (active_player_record(record) && !carried.count(record.item_uid))
				stale.insert(record.item_uid);
		// A record that stays keeps its container, and that container its own.
		for (bool changed = true; changed;)
		{
			changed = false;
			for (const auto &record : catalog.items)
				if (record.parent_item_uid && !stale.count(record.item_uid) &&
				    stale.erase(record.parent_item_uid))
					changed = true;
		}
		if (stale.empty())
			return flatfile_item_repository_result::unchanged;
		catalog.items.erase(std::remove_if(catalog.items.begin(), catalog.items.end(),
						   [&](const flatfile_item_ownership_record &record)
						   { return stale.count(record.item_uid) != 0; }),
				    catalog.items.end());
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	if (catalog.revision == std::numeric_limits<uint64_t>::max())
		return flatfile_item_repository_result::invalid;
	std::vector<uint8_t> encoded;
	if (!encode_catalog(catalog, catalog.revision + 1, &encoded))
		return flatfile_item_repository_result::invalid;
	if (!flatfile_atomic_write(domains_directory(root), ownership_filename, encoded, error))
		return flatfile_item_repository_result::io_error;
	*deleted = stale.size();
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result flatfile_item_repository_world_recovery_owned(
	const std::string &root, const std::vector<uint64_t> &uids,
	std::unordered_set<uint64_t> *owned, std::string *error)
{
	if (root.empty() || !owned)
		return flatfile_item_repository_result::invalid;
	std::lock_guard<std::mutex> guard(ownership_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_item_repository_result::io_error;
	const auto recovered = flatfile_authority_transaction_recover(root, authority, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded == flatfile_item_repository_result::not_found)
		return flatfile_item_repository_result::ok;
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	try
	{
		const std::unordered_set<uint64_t> wanted(uids.begin(), uids.end());
		std::unordered_map<uint64_t, std::unordered_set<uint64_t>> held;
		for (const auto &record : catalog.items)
		{
			if (!wanted.count(record.item_uid))
				continue;
			if (active_player_record(record))
			{
				auto found = held.find(record.owner.id);
				if (found == held.end())
				{
					found = held.emplace(record.owner.id,
							     std::unordered_set<uint64_t>{})
							.first;
					if (const auto read = add_player_load_uids(
						    root, authority, catalog, record.owner.id,
						    &found->second, error);
					    read != flatfile_item_repository_result::ok)
						return read;
				}
				if (!found->second.count(record.item_uid))
					continue;
			}
			owned->insert(record.item_uid);
		}
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	return flatfile_item_repository_result::ok;
}

flatfile_item_baseline_result
flatfile_item_repository_establish_owner(const std::string &root, const item_owner_identity &owner,
					 const std::vector<flatfile_item_ownership_record> &items,
					 std::string *error)
{
	if (root.empty() || !item_owner_identity_valid(owner) ||
	    items.size() > ownership_maximum_entries ||
	    !std::is_sorted(items.begin(), items.end(), item_less))
		return flatfile_item_baseline_result::invalid;
	for (size_t index = 0; index < items.size(); ++index)
	{
		const auto &entry = items[index];
		if (!entry.item_uid || !entry.root_item_uid || entry.vnum <= 0 ||
		    entry.item_revision != 1 || entry.state != item_custody_state::active ||
		    !item_owner_identity_equal(entry.owner, owner) ||
		    (index && items[index - 1].item_uid == entry.item_uid))
			return flatfile_item_baseline_result::invalid;
		if (entry.parent_item_uid)
		{
			auto parent = std::lower_bound(
				items.begin(), items.end(), entry.parent_item_uid,
				[](const flatfile_item_ownership_record &candidate, uint64_t uid)
				{ return candidate.item_uid < uid; });
			if (parent == items.end() || parent->item_uid != entry.parent_item_uid ||
			    parent->root_item_uid != entry.root_item_uid)
				return flatfile_item_baseline_result::invalid;
		}
		else if (entry.root_item_uid != entry.item_uid)
			return flatfile_item_baseline_result::invalid;
	}

	std::lock_guard<std::mutex> guard(ownership_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_item_baseline_result::io_error;
	const auto recovered = flatfile_authority_transaction_recover(root, authority, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_baseline_result::io_error :
			       flatfile_item_baseline_result::invalid;
	ownership_catalog catalog;
	const flatfile_item_repository_result loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok &&
	    loaded != flatfile_item_repository_result::not_found)
		return loaded == flatfile_item_repository_result::io_error ?
			       flatfile_item_baseline_result::io_error :
			       flatfile_item_baseline_result::invalid;
	owner_state *stored_owner = find_owner(&catalog, owner);
	std::vector<flatfile_item_ownership_record> existing;
	try
	{
		for (const auto &entry : catalog.items)
			if (item_owner_identity_equal(entry.owner, owner))
				existing.push_back(entry);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_baseline_result::io_error;
	}
	if (stored_owner && stored_owner->revision == 1 && existing.size() == items.size() &&
	    std::equal(existing.begin(), existing.end(), items.begin(), item_equal))
		return flatfile_item_baseline_result::already_applied;
	if ((stored_owner && stored_owner->revision != 0) || !existing.empty())
		return flatfile_item_baseline_result::conflict;
	if (catalog.items.size() > ownership_maximum_entries - items.size() ||
	    catalog.revision == std::numeric_limits<uint64_t>::max())
		return flatfile_item_baseline_result::conflict;
	if (!stored_owner)
	{
		stored_owner = ensure_owner(&catalog, owner);
		if (!stored_owner)
			return flatfile_item_baseline_result::io_error;
	}
	stored_owner->revision = 1;
	try
	{
		catalog.items.insert(catalog.items.end(), items.begin(), items.end());
		std::sort(catalog.items.begin(), catalog.items.end(), item_less);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_baseline_result::io_error;
	}
	std::vector<uint8_t> encoded;
	if (!encode_catalog(catalog, catalog.revision + 1, &encoded))
		return flatfile_item_baseline_result::invalid;
	if (!flatfile_atomic_write(domains_directory(root), ownership_filename, encoded, error))
		return flatfile_item_baseline_result::io_error;
	return flatfile_item_baseline_result::applied;
}

flatfile_item_repository_result flatfile_item_repository_prepare_auction_transfer(
	const std::string &root, const flatfile_authority_lock &lock,
	const auction_command_payload &payload, uint32_t auction_id, bool to_auction,
	flatfile_item_auction_mutation *mutation, unsigned int *result_code, std::string *error)
{
	if (!mutation || !result_code || !auction_id || !payload.actor_pid || !payload.item_count ||
	    payload.item_count > payload.items.size() || !lock.matches(root))
		return flatfile_item_repository_result::invalid;
	*mutation = {};
	*result_code = 0;
	const auto recovered = flatfile_authority_transaction_recover(root, lock, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	const item_owner_identity player_owner = { item_owner_type::player, payload.actor_pid, 0 };
	const item_owner_identity auction_owner = { item_owner_type::auction, auction_id, 0 };
	const item_owner_identity &from_owner = to_auction ? player_owner : auction_owner;
	const item_owner_identity &to_owner = to_auction ? auction_owner : player_owner;
	if (!ensure_owner(&catalog, player_owner) || !ensure_owner(&catalog, auction_owner))
		return flatfile_item_repository_result::io_error;
	owner_state *player = find_owner(&catalog, player_owner);
	owner_state *auction = find_owner(&catalog, auction_owner);
	if (!player || !auction)
		return flatfile_item_repository_result::invalid;
	if (player->revision == std::numeric_limits<uint64_t>::max() ||
	    auction->revision == std::numeric_limits<uint64_t>::max())
	{
		*result_code = ERANGE;
		return flatfile_item_repository_result::ok;
	}
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		const auto &expected = payload.items[index];
		uint64_t expected_revision = expected.expected_item_revision;
		if (to_auction)
		{
			// The seller holds it in memory: the listing takes it from whatever the
			// catalog still says, as a save would.
			const uint64_t no_parent = 0;
			bool refused = false;
			const unsigned int failed = claim_catalog_item(
				&catalog, player_owner, expected.item_uid, expected.item_uid,
				&no_parent, expected.vnum, &expected_revision, &refused);
			if (failed == ENOMEM)
				return flatfile_item_repository_result::io_error;
			if (failed || refused)
			{
				*result_code = failed ? failed : ESTALE;
				return flatfile_item_repository_result::ok;
			}
		}
		flatfile_item_ownership_record *item = find_item(&catalog, expected.item_uid);
		if (!item || item->root_item_uid != item->item_uid || item->parent_item_uid ||
		    !item_owner_identity_equal(item->owner, from_owner) ||
		    item->item_revision != expected_revision ||
		    item->item_revision == std::numeric_limits<uint64_t>::max() ||
		    item->vnum != expected.vnum || item->state != item_custody_state::active)
		{
			*result_code = ESTALE;
			return flatfile_item_repository_result::ok;
		}
		for (size_t prior = 0; prior < index; ++prior)
			if (payload.items[prior].item_uid == expected.item_uid)
			{
				*result_code = ESTALE;
				return flatfile_item_repository_result::ok;
			}
	}
	++player->revision;
	++auction->revision;
	mutation->player_owner_revision = player->revision;
	mutation->auction_owner_revision = auction->revision;
	mutation->item_count = payload.item_count;
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		flatfile_item_ownership_record *item =
			find_item(&catalog, payload.items[index].item_uid);
		if (!item)
			return flatfile_item_repository_result::invalid;
		item->owner = to_owner;
		++item->item_revision;
		mutation->item_uids[index] = item->item_uid;
		mutation->item_revisions[index] = item->item_revision;
	}
	mutation->after_image.filename = ownership_filename;
	if (catalog.revision == std::numeric_limits<uint64_t>::max() ||
	    !encode_catalog(catalog, catalog.revision + 1, &mutation->after_image.bytes))
		return flatfile_item_repository_result::invalid;
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result flatfile_item_repository_prepare_shop_trade(
	const std::string &root, const flatfile_authority_lock &lock,
	const shop_trade_payload &payload, flatfile_item_shop_trade_mutation *mutation,
	unsigned int *result_code, std::string *error)
{
	if (!mutation || !result_code || !lock.matches(root))
		return flatfile_item_repository_result::invalid;
	*mutation = {};
	*result_code = 0;
	std::vector<uint8_t> validated_payload;
	if (!shop_trade_command_encode_payload(payload, &validated_payload))
		return flatfile_item_repository_result::invalid;
	const auto recovered = flatfile_authority_transaction_recover(root, lock, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	const item_owner_identity player = { item_owner_type::player, payload.player_pid, 0 };
	const item_owner_identity shop = { item_owner_type::shopkeeper,
					   item_shopkeeper_owner_id(payload.shop_id), 0 };
	if (!find_owner(&catalog, player) || !find_owner(&catalog, shop))
	{
		*result_code = ESTALE;
		return flatfile_item_repository_result::ok;
	}
	if (payload.action == shop_trade_action::buy_produced)
	{
		const auto *stock = find_item(&catalog, payload.stock_item_uid);
		if (!stock || stock->root_item_uid != stock->item_uid || stock->parent_item_uid ||
		    !item_owner_identity_equal(stock->owner, shop) ||
		    stock->item_revision != payload.expected_stock_item_revision ||
		    stock->vnum != payload.stock_vnum || stock->state != item_custody_state::active)
		{
			*result_code = ESTALE;
			return flatfile_item_repository_result::ok;
		}
	}
	const item_owner_identity system = { item_owner_type::system, 0, 0 };
	const item_owner_identity destruction = { item_owner_type::destruction, 0, 0 };
	item_transfer_payload transfer = {};
	transfer.reason_id = payload.shop_id;
	transfer.selected_item_uid = payload.selected_item_uid;
	transfer.target_root_item_uid = payload.target_root_item_uid ?
						payload.target_root_item_uid :
						payload.selected_item_uid;
	transfer.target_parent_item_uid = payload.target_parent_item_uid;
	transfer.expected_target_parent_revision = payload.expected_target_parent_revision;
	transfer.item_count = payload.item_count;
	if (payload.action == shop_trade_action::buy_existing)
	{
		transfer.from_owner = shop;
		transfer.to_owner = player;
		transfer.reason = item_transfer_reason::shop_buy;
	}
	else if (payload.action == shop_trade_action::buy_produced)
	{
		transfer.from_owner = system;
		transfer.to_owner = player;
		transfer.reason = item_transfer_reason::creation;
		if (!ensure_owner(&catalog, system))
			return flatfile_item_repository_result::io_error;
	}
	else if (payload.action == shop_trade_action::sell_store)
	{
		transfer.from_owner = player;
		transfer.to_owner = shop;
		transfer.reason = item_transfer_reason::shop_sell;
	}
	else if (payload.action == shop_trade_action::sell_destroy)
	{
		transfer.from_owner = player;
		transfer.to_owner = destruction;
		transfer.reason = item_transfer_reason::destruction;
		if (!ensure_owner(&catalog, destruction))
			return flatfile_item_repository_result::io_error;
	}
	else if (payload.action == shop_trade_action::discard_invalid)
	{
		transfer.from_owner = shop;
		transfer.to_owner = destruction;
		transfer.reason = item_transfer_reason::destruction;
		if (!ensure_owner(&catalog, destruction))
			return flatfile_item_repository_result::io_error;
	}
	else
		return flatfile_item_repository_result::invalid;
	owner_state *from = find_owner(&catalog, transfer.from_owner);
	owner_state *to = find_owner(&catalog, transfer.to_owner);
	if (!from || !to)
		return flatfile_item_repository_result::invalid;
	transfer.expected_from_revision = from->revision;
	transfer.expected_to_revision = to->revision;
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		const auto &item = payload.items[index];
		transfer.items[index] = { item.item_uid,
					  item.root_item_uid,
					  item.parent_item_uid,
					  item.expected_item_revision,
					  item.vnum,
					  item.expected_state };
	}
	item_transfer_result transfer_result = {};
	const unsigned int applied = apply_transfer(&catalog, transfer, &transfer_result);
	if (applied)
	{
		if (applied == ENOMEM)
			return flatfile_item_repository_result::io_error;
		*result_code = applied;
		return flatfile_item_repository_result::ok;
	}
	const item_owner_identity counterparty =
		payload.action == shop_trade_action::buy_produced ? system :
		payload.action == shop_trade_action::sell_destroy ||
				payload.action == shop_trade_action::discard_invalid ?
								    destruction :
								    shop;
	const owner_state *player_owner = find_owner(
		&catalog, payload.action == shop_trade_action::discard_invalid ? shop : player);
	const owner_state *counterparty_owner = find_owner(&catalog, counterparty);
	if (!player_owner || !counterparty_owner)
		return flatfile_item_repository_result::invalid;
	mutation->player_owner_revision = player_owner->revision;
	mutation->counterparty_owner_revision = counterparty_owner->revision;
	mutation->item_count = payload.item_count;
	for (size_t index = 0; index < payload.item_count; ++index)
	{
		const auto *item = find_item(&catalog, payload.items[index].item_uid);
		if (!item)
			return flatfile_item_repository_result::invalid;
		mutation->item_uids[index] = item->item_uid;
		mutation->item_revisions[index] = item->item_revision;
	}
	mutation->after_image.filename = ownership_filename;
	if (catalog.revision == std::numeric_limits<uint64_t>::max() ||
	    !encode_catalog(catalog, catalog.revision + 1, &mutation->after_image.bytes))
		return flatfile_item_repository_result::invalid;
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result flatfile_item_repository_prepare_claim(
	const std::string &root, const flatfile_authority_lock &lock,
	std::vector<flatfile_item_claim> *claims, flatfile_authority_operation *operation,
	std::vector<flatfile_item_claim_audit> *audits, std::string *error)
{
	if (!claims || !operation || !audits || !lock.matches(root))
		return flatfile_item_repository_result::invalid;
	*operation = {};
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok &&
	    loaded != flatfile_item_repository_result::not_found)
		return loaded;
	bool changed = false;
	std::vector<item_owner_identity> changed_owners;
	try
	{
		for (flatfile_item_claim &claim : *claims)
		{
			if (!claim.items || !item_owner_identity_valid(claim.owner))
				return flatfile_item_repository_result::invalid;
			claim.outcome = {};
			bool claimer_changed = false;
			if (claim.establish)
			{
				owner_state *state = ensure_owner(&catalog, claim.owner);
				if (!state)
					return flatfile_item_repository_result::invalid;
				claimer_changed = !state->revision;
				changed = changed || claimer_changed;
			}
			const std::vector<player_item_snapshot> &items = *claim.items;
			std::vector<uint64_t> roots(items.size(), 0);
			for (size_t index = 0; index < items.size(); ++index)
			{
				const player_item_snapshot &item = items[index];
				const bool nested = item.parent_index >= 0 &&
						    static_cast<size_t>(item.parent_index) < index;
				const uint64_t parent_uid =
					nested ? items[item.parent_index].object_uid : 0;
				roots[index] = nested && roots[item.parent_index] ?
						       roots[item.parent_index] :
						       item.object_uid;
				if (!item.object_uid)
					continue;
				flatfile_item_ownership_record *record =
					find_item(&catalog, item.object_uid);
				if (parent_uid && claim.outcome.left_out.count(parent_uid))
				{
					const flatfile_item_ownership_record *holder =
						find_item(&catalog, parent_uid);
					claim.outcome.left_out.insert(item.object_uid);
					claim.outcome.dupes.push_back({ item.object_uid, item.vnum,
									record ? record->owner :
									holder ? holder->owner :
										 claim.owner });
					continue;
				}
				if (record && item_claim_leaves_out(record->state))
				{
					claim.outcome.left_out.insert(item.object_uid);
					claim.outcome.dupes.push_back(
						{ item.object_uid, item.vnum, record->owner });
					continue;
				}
				if (!ensure_owner(&catalog, claim.owner))
					return flatfile_item_repository_result::invalid;
				// ensure_owner() may insert; take the record again afterwards.
				record = find_item(&catalog, item.object_uid);
				if (!record)
				{
					if (catalog.items.size() >= ownership_maximum_entries)
						return flatfile_item_repository_result::invalid;
					const flatfile_item_ownership_record inserted = {
						item.object_uid,
						roots[index],
						parent_uid,
						claim.owner,
						1,
						item.vnum,
						item_custody_state::active
					};
					catalog.items.insert(std::lower_bound(catalog.items.begin(),
									      catalog.items.end(),
									      inserted, item_less),
							     inserted);
					++claim.outcome.inserted;
					changed = true;
					claimer_changed = true;
					continue;
				}
				const bool owned =
					item_owner_identity_equal(record->owner, claim.owner);
				if (owned && record->root_item_uid == roots[index] &&
				    record->parent_item_uid == parent_uid &&
				    record->vnum == item.vnum &&
				    record->state == item_custody_state::active)
					continue;
				if (!owned)
				{
					audits->push_back({ item.object_uid, item.vnum,
							    record->owner, claim.owner });
					changed_owners.push_back(record->owner);
					++claim.outcome.claimed;
				}
				record->owner = claim.owner;
				record->root_item_uid = roots[index];
				record->parent_item_uid = parent_uid;
				record->vnum = item.vnum;
				record->state = item_custody_state::active;
				if (record->item_revision < UINT64_MAX)
					++record->item_revision;
				changed = true;
				claimer_changed = true;
			}
			if (claimer_changed)
				changed_owners.push_back(claim.owner);
		}
		// The holdings of each claimer and of every owner that lost an item changed:
		// advance each of their revisions once.
		std::sort(changed_owners.begin(), changed_owners.end(), owner_less);
		changed_owners.erase(std::unique(changed_owners.begin(), changed_owners.end(),
						 item_owner_identity_equal),
				     changed_owners.end());
		for (const item_owner_identity &owner : changed_owners)
			if (owner_state *state = find_owner(&catalog, owner);
			    state && state->revision < UINT64_MAX)
				++state->revision;
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	if (!changed)
		return flatfile_item_repository_result::unchanged;
	if (catalog.revision == UINT64_MAX)
		return flatfile_item_repository_result::invalid;
	operation->filename = ownership_filename;
	return encode_catalog(catalog, catalog.revision + 1, &operation->bytes) ?
		       flatfile_item_repository_result::ok :
		       flatfile_item_repository_result::invalid;
}

flatfile_item_repository_result flatfile_item_repository_prepare_player_remove(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	flatfile_authority_operation *operation, std::string *error)
{
	if (!operation || !pid || !lock.matches(root))
		return flatfile_item_repository_result::invalid;
	*operation = {};
	const auto recovered = flatfile_authority_transaction_recover(root, lock, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	const item_owner_identity player = { item_owner_type::player, pid, 0 };
	const item_owner_identity destruction = { item_owner_type::destruction, 0, 0 };
	owner_state *player_owner = find_owner(&catalog, player);
	if (!player_owner)
		return flatfile_item_repository_result::unchanged;
	owner_state *destruction_owner = ensure_owner(&catalog, destruction);
	if (!destruction_owner || catalog.revision == std::numeric_limits<uint64_t>::max() ||
	    destruction_owner->revision == std::numeric_limits<uint64_t>::max())
		return flatfile_item_repository_result::invalid;
	for (const auto &item : catalog.items)
		if (item_owner_identity_equal(item.owner, player) &&
		    item.item_revision == std::numeric_limits<uint64_t>::max())
			return flatfile_item_repository_result::invalid;
	for (auto &item : catalog.items)
	{
		if (!item_owner_identity_equal(item.owner, player))
			continue;
		item.owner = destruction;
		item.state = item_custody_state::destroyed;
		++item.item_revision;
	}
	++destruction_owner->revision;
	auto owner =
		std::lower_bound(catalog.owners.begin(), catalog.owners.end(), player,
				 [](const owner_state &candidate, const item_owner_identity &value)
				 { return owner_less(candidate.owner, value); });
	if (owner == catalog.owners.end() || !item_owner_identity_equal(owner->owner, player))
		return flatfile_item_repository_result::invalid;
	catalog.owners.erase(owner);
	std::vector<uint8_t> encoded;
	if (!encode_catalog(catalog, catalog.revision + 1, &encoded))
		return flatfile_item_repository_result::invalid;
	operation->store = flatfile_authority_store::domains;
	operation->kind = flatfile_authority_operation_kind::write;
	operation->filename = ownership_filename;
	operation->bytes = std::move(encoded);
	return flatfile_item_repository_result::ok;
}

/* Prepare one authority image that destroys an exact set of player and custody owners. */
static flatfile_item_repository_result
prepare_custody_remove(const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
		       const std::vector<flatfile_locker_custody_owner> &locker_custody,
		       const std::vector<flatfile_corpse_custody_owner> &corpse_custody,
		       flatfile_authority_operation *operation, std::string *error)
{
	if (!operation || (!pid && locker_custody.empty()) || !lock.matches(root) ||
	    locker_custody.size() > ownership_maximum_entries ||
	    corpse_custody.size() > ownership_maximum_entries - locker_custody.size())
		return flatfile_item_repository_result::invalid;
	*operation = {};
	const auto recovered = flatfile_authority_transaction_recover(root, lock, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_item_repository_result::io_error :
			       flatfile_item_repository_result::invalid;
	ownership_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_item_repository_result::ok)
		return loaded;
	std::vector<item_owner_identity> owners;
	try
	{
		owners.reserve(locker_custody.size() + corpse_custody.size() + (pid ? 1 : 0));
		if (pid)
			owners.push_back({ item_owner_type::player, pid, 0 });
		for (const auto &expected : locker_custody)
		{
			if (expected.owner.type != item_owner_type::locker ||
			    !item_owner_identity_valid(expected.owner) ||
			    !std::is_sorted(expected.items.begin(), expected.items.end(),
					    [](const auto &left, const auto &right)
					    { return left.item_uid < right.item_uid; }))
				return flatfile_item_repository_result::invalid;
			if (std::find_if(owners.begin(), owners.end(),
					 [&](const auto &owner) {
						 return item_owner_identity_equal(owner,
										  expected.owner);
					 }) != owners.end())
				return flatfile_item_repository_result::invalid;
			const owner_state *stored_owner = find_owner(&catalog, expected.owner);
			if (!stored_owner)
			{
				if (expected.items.empty())
					continue;
				return flatfile_item_repository_result::invalid;
			}
			size_t item_index = 0;
			for (const auto &item : catalog.items)
			{
				if (item.state != item_custody_state::active ||
				    !item_owner_identity_equal(item.owner, expected.owner))
					continue;
				if (item_index >= expected.items.size() ||
				    expected.items[item_index].item_uid != item.item_uid ||
				    expected.items[item_index].vnum != item.vnum)
					return flatfile_item_repository_result::invalid;
				++item_index;
			}
			if (item_index != expected.items.size())
				return flatfile_item_repository_result::invalid;
			owners.push_back(expected.owner);
		}
		for (const auto &expected : corpse_custody)
		{
			if (expected.owner.type != item_owner_type::corpse ||
			    !item_owner_identity_valid(expected.owner) ||
			    !std::is_sorted(expected.items.begin(), expected.items.end(),
					    [](const auto &left, const auto &right)
					    { return left.item_uid < right.item_uid; }))
				return flatfile_item_repository_result::invalid;
			if (std::find_if(owners.begin(), owners.end(),
					 [&](const auto &owner) {
						 return item_owner_identity_equal(owner,
										  expected.owner);
					 }) != owners.end())
				return flatfile_item_repository_result::invalid;
			const owner_state *stored_owner = find_owner(&catalog, expected.owner);
			if (!stored_owner)
				return flatfile_item_repository_result::invalid;
			size_t item_index = 0;
			for (const auto &item : catalog.items)
			{
				if (item.state != item_custody_state::active ||
				    !item_owner_identity_equal(item.owner, expected.owner))
					continue;
				if (item_index >= expected.items.size() ||
				    expected.items[item_index].item_uid != item.item_uid ||
				    expected.items[item_index].vnum != item.vnum)
					return flatfile_item_repository_result::invalid;
				++item_index;
			}
			if (item_index != expected.items.size())
				return flatfile_item_repository_result::invalid;
			owners.push_back(expected.owner);
		}
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_item_repository_result::io_error;
	}
	const item_owner_identity destruction = { item_owner_type::destruction, 0, 0 };
	owner_state *destruction_owner = ensure_owner(&catalog, destruction);
	if (!destruction_owner || catalog.revision == std::numeric_limits<uint64_t>::max() ||
	    destruction_owner->revision == std::numeric_limits<uint64_t>::max())
		return flatfile_item_repository_result::invalid;
	++destruction_owner->revision;
	bool changed = false;
	for (const auto &owner : owners)
	{
		owner_state *stored_owner = find_owner(&catalog, owner);
		if (!stored_owner)
		{
			if (owner.type == item_owner_type::player)
				continue;
			return flatfile_item_repository_result::invalid;
		}
		for (auto &item : catalog.items)
		{
			if (!item_owner_identity_equal(item.owner, owner))
				continue;
			if (item.item_revision == std::numeric_limits<uint64_t>::max())
				return flatfile_item_repository_result::invalid;
			item.owner = destruction;
			item.state = item_custody_state::destroyed;
			++item.item_revision;
		}
		auto at = std::lower_bound(catalog.owners.begin(), catalog.owners.end(), owner,
					   [](const owner_state &candidate,
					      const item_owner_identity &value)
					   { return owner_less(candidate.owner, value); });
		if (at == catalog.owners.end() || !item_owner_identity_equal(at->owner, owner))
			return flatfile_item_repository_result::invalid;
		catalog.owners.erase(at);
		changed = true;
	}
	if (!changed)
		return flatfile_item_repository_result::unchanged;
	std::vector<uint8_t> encoded;
	if (!encode_catalog(catalog, catalog.revision + 1, &encoded))
		return flatfile_item_repository_result::invalid;
	operation->store = flatfile_authority_store::domains;
	operation->kind = flatfile_authority_operation_kind::write;
	operation->filename = ownership_filename;
	operation->bytes = std::move(encoded);
	return flatfile_item_repository_result::ok;
}

/* Prepare removal of one player plus verified locker and corpse custody. */
flatfile_item_repository_result flatfile_item_repository_prepare_player_and_custody_remove(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	const std::vector<flatfile_locker_custody_owner> &locker_custody,
	const std::vector<flatfile_corpse_custody_owner> &corpse_custody,
	flatfile_authority_operation *operation, std::string *error)
{
	if (!pid)
		return flatfile_item_repository_result::invalid;
	return prepare_custody_remove(root, lock, pid, locker_custody, corpse_custody, operation,
				      error);
}

/* Prepare removal of verified locker custody without requiring a player owner. */
flatfile_item_repository_result flatfile_item_repository_prepare_locker_remove(
	const std::string &root, const flatfile_authority_lock &lock,
	const std::vector<flatfile_locker_custody_owner> &locker_custody,
	flatfile_authority_operation *operation, std::string *error)
{
	return prepare_custody_remove(root, lock, 0, locker_custody, {}, operation, error);
}

critical_apply_result flatfile_item_repository_apply(const std::string &root,
						     const critical_command &command)
{
	item_transfer_payload payload = {};
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	if (root.empty() || !critical_command_valid(command) ||
	    !item_transfer_command_decode_payload(command, &payload) ||
	    !command_digest(command, &digest))
		return { critical_apply_outcome::terminal_failure, 0, EINVAL };
	std::lock_guard<std::mutex> guard(ownership_mutex);
	flatfile_authority_lock authority;
	std::string error;
	if (!authority.acquire(root, &error))
		return { critical_apply_outcome::retryable_failure, 0, EIO };
	const auto recovered = flatfile_authority_transaction_recover(root, authority, &error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return { recovered == flatfile_authority_transaction_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 recovered == flatfile_authority_transaction_result::io_error ?
					 EIO :
					 EILSEQ) };
	ownership_catalog catalog;
	const flatfile_item_repository_result loaded = load_catalog(root, &catalog, &error);
	if (loaded != flatfile_item_repository_result::ok &&
	    loaded != flatfile_item_repository_result::not_found)
		return { loaded == flatfile_item_repository_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 loaded == flatfile_item_repository_result::io_error ? EIO :
										       EILSEQ) };
	for (const operation_state &entry : catalog.operations)
		if (critical_operation_id_equal(entry.operation_id, command.operation_id))
		{
			if (CRYPTO_memcmp(entry.command_digest.data(), digest.data(),
					  digest.size()))
				return { critical_apply_outcome::terminal_failure, catalog.revision,
					 EEXIST };
			return make_result(entry.result_code ?
						   critical_apply_outcome::terminal_failure :
						   critical_apply_outcome::already_applied,
					   entry.result_code, entry.result);
		}
	if (catalog.operations.size() >= ownership_maximum_operations ||
	    catalog.revision == std::numeric_limits<uint64_t>::max())
		return { critical_apply_outcome::terminal_failure, catalog.revision, ENOSPC };
	ownership_catalog candidate;
	try
	{
		candidate = catalog;
	}
	catch (const std::bad_alloc &)
	{
		return { critical_apply_outcome::retryable_failure, catalog.revision, ENOMEM };
	}
	item_transfer_result result = {};
	unsigned int result_code = apply_transfer(&candidate, payload, &result);
	if (result_code == ENOMEM || result_code == EILSEQ)
		return { critical_apply_outcome::retryable_failure, catalog.revision, result_code };
	if (!result_code && !generic_transfer_supported(payload))
	{
		try
		{
			candidate = catalog;
		}
		catch (const std::bad_alloc &)
		{
			return { critical_apply_outcome::retryable_failure, catalog.revision,
				 ENOMEM };
		}
		const owner_state *from = find_owner(&catalog, payload.from_owner);
		const owner_state *to = find_owner(&catalog, payload.to_owner);
		result = { item_transfer_result_root(payload),
			   payload.item_count,
			   from ? from->revision : 0,
			   to ? to->revision : 0,
			   0,
			   0 };
		result_code = EOPNOTSUPP;
	}
	flatfile_collector_enrollment_mutation collector_mutation;
	bool include_collector_mutation = false;
	if (!result_code)
	{
		const auto prepared = flatfile_collector_prepare_item_boundary(
			root, authority, payload, result, &collector_mutation, &result_code,
			&error);
		if (prepared != flatfile_collector_repository_result::ok &&
		    prepared != flatfile_collector_repository_result::unchanged)
			return { prepared == flatfile_collector_repository_result::io_error ?
					 critical_apply_outcome::retryable_failure :
					 critical_apply_outcome::terminal_failure,
				 catalog.revision,
				 static_cast<unsigned int>(
					 prepared == flatfile_collector_repository_result::io_error ?
						 EIO :
						 EILSEQ) };
		include_collector_mutation = prepared == flatfile_collector_repository_result::ok &&
					     !collector_mutation.after_image.bytes.empty();
		if (result_code)
		{
			try
			{
				candidate = catalog;
			}
			catch (const std::bad_alloc &)
			{
				return { critical_apply_outcome::retryable_failure,
					 catalog.revision, ENOMEM };
			}
			const owner_state *from = find_owner(&catalog, payload.from_owner);
			const owner_state *to = find_owner(&catalog, payload.to_owner);
			result = { item_transfer_result_root(payload),
				   payload.item_count,
				   from ? from->revision : 0,
				   to ? to->revision : 0,
				   0,
				   0 };
			include_collector_mutation = false;
		}
		else if (include_collector_mutation)
			result.collector_catalog_changed = true;
	}
	try
	{
		candidate.operations.push_back(
			{ command.operation_id, digest, result_code, result });
	}
	catch (const std::bad_alloc &)
	{
		return { critical_apply_outcome::retryable_failure, catalog.revision, ENOMEM };
	}
	flatfile_shop_trade_materialization_mutation materialization;
	flatfile_room_transfer_mutation room;
	bool include_room = false;
	if (!result_code && room_transfer(payload))
	{
		if (!flatfile_artifact_room_transfer_allowed(payload))
			return { critical_apply_outcome::terminal_failure, catalog.revision,
				 EILSEQ };
		const auto prepared = flatfile_world_item_prepare_room_transfer(
			root, authority, payload, &room, &error);
		if (prepared != flatfile_world_item_result::ok)
			return { prepared == flatfile_world_item_result::io_error ?
					 critical_apply_outcome::retryable_failure :
					 critical_apply_outcome::terminal_failure,
				 catalog.revision,
				 static_cast<unsigned int>(
					 prepared == flatfile_world_item_result::io_error ?
						 EIO :
						 EILSEQ) };
		const item_owner_identity &room_owner =
			payload.from_owner.type == item_owner_type::room ? payload.from_owner :
									   payload.to_owner;
		const uint64_t result_revision = payload.from_owner.type == item_owner_type::room ?
							 result.from_owner_revision :
							 result.to_owner_revision;
		if (!room_custody_matches(catalog, room_owner, room.expected_items, room.created) ||
		    room.room_revision != result_revision)
			return { critical_apply_outcome::terminal_failure, catalog.revision,
				 EILSEQ };
		include_room = true;
	}
	bool include_materialization = false;
	if (!result_code && payload.item_blob_size)
	{
		const auto prepared = flatfile_item_transfer_materialization_prepare(
			root, authority, command.operation_id, payload, &materialization, &error);
		if (prepared != flatfile_shop_trade_materialization_result::ok &&
		    prepared != flatfile_shop_trade_materialization_result::unchanged)
			return { prepared == flatfile_shop_trade_materialization_result::io_error ?
					 critical_apply_outcome::retryable_failure :
					 critical_apply_outcome::terminal_failure,
				 catalog.revision,
				 static_cast<unsigned int>(
					 prepared == flatfile_shop_trade_materialization_result::
								 io_error ?
						 EIO :
						 EILSEQ) };
		include_materialization = prepared ==
					  flatfile_shop_trade_materialization_result::ok;
	}
	std::vector<uint8_t> encoded;
	if (!encode_catalog(candidate, catalog.revision + 1, &encoded))
		return { critical_apply_outcome::terminal_failure, catalog.revision, ENOSPC };
	std::vector<flatfile_authority_after_image> images;
	try
	{
		images.push_back({ ownership_filename, std::move(encoded) });
		if (include_room)
			images.push_back(std::move(room.after_image));
		if (include_materialization)
			images.push_back(std::move(materialization.after_image));
		if (include_collector_mutation)
			images.push_back(std::move(collector_mutation.after_image));
	}
	catch (const std::bad_alloc &)
	{
		return { critical_apply_outcome::retryable_failure, catalog.revision, ENOMEM };
	}
	const auto committed =
		flatfile_authority_transaction_commit(root, authority, images, &error);
	if (committed != flatfile_authority_transaction_result::ok)
		return { committed == flatfile_authority_transaction_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 catalog.revision,
			 static_cast<unsigned int>(
				 committed == flatfile_authority_transaction_result::io_error ?
					 EIO :
					 EILSEQ) };
	return make_result(result_code ? critical_apply_outcome::terminal_failure :
					 critical_apply_outcome::applied,
			   result_code, result);
}

critical_apply_result
flatfile_critical_command_repository_apply_selected(const critical_command &command, void *context)
{
	const char *root = context ? static_cast<const char *>(context) :
				     persistence_mode_flatfile_root();
	if (!root || !*root)
		return { critical_apply_outcome::terminal_failure, 0, ENOENT };
	if (command.type == critical_command_type::item_transfer)
		return flatfile_item_repository_apply(root, command);
	if (command.type == critical_command_type::auction)
		return flatfile_auction_repository_apply(root, command);
	if (command.type == critical_command_type::collector)
		return flatfile_collector_repository_apply(root, command);
	if (command.type == critical_command_type::boon_reward)
		return flatfile_boon_repository_apply(root, command);
	if (command.type == critical_command_type::boon_shop)
		return flatfile_boon_shop_repository_apply(root, command);
	if (command.type == critical_command_type::shop_trade)
		return flatfile_shop_trade_repository_apply(root, command);
	if (command.type == critical_command_type::epic ||
	    command.type == critical_command_type::combat_outcome)
		return flatfile_player_domain_apply(root, command);
	return { critical_apply_outcome::terminal_failure, 0, ENOTSUP };
}
