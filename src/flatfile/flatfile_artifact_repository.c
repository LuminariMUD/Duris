/****************************************************************************
 *
 *  File: flatfile_artifact_repository.c                        Part of Duris
 *  Usage: flat-file artifact catalog snapshots and player release
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "flatfile/flatfile_artifact_repository.h"

#include "flatfile/flatfile_store.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <new>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <type_traits>

namespace
{
constexpr std::array<uint8_t, 8> catalog_magic = { 'D', 'U', 'R', 'A', 'R', 'T', 'F', 0 };
constexpr uint32_t catalog_version = 3;
constexpr size_t catalog_maximum_bytes = 64 * 1024 * 1024;
constexpr const char *catalog_filename = "artifact_catalog";
constexpr uint32_t artifact_extra_flag = 1U << 28;

struct artifact_catalog
{
	uint64_t revision = 1;
	std::vector<flatfile_artifact_record> records;
};

struct encoder
{
	std::vector<uint8_t> bytes;
	bool valid = true;

	template <typename T> void number(T value)
	{
		using U = std::make_unsigned_t<T>;
		U bits = static_cast<U>(value);
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
		using U = std::make_unsigned_t<T>;
		U bits = 0;
		for (size_t index = 0; index < sizeof(T); ++index)
			bits |= static_cast<U>(data[offset++]) << (index * 8);
		*value = static_cast<T>(bits);
		return true;
	}
};

std::string domains_directory(const std::string &root)
{
	return root + "/domains";
}

bool record_less(const flatfile_artifact_record &left, const flatfile_artifact_record &right)
{
	return left.vnum < right.vnum;
}

bool valid_record(const flatfile_artifact_record &record)
{
	return record.vnum > 0 && record.location_type >= FLATFILE_ARTIFACT_NOT_IN_GAME &&
	       record.location_type <= FLATFILE_ARTIFACT_ON_CORPSE && record.timer >= 0 &&
	       record.type >= 1 && record.type <= 3 && record.last_update >= 0 &&
	       record.bind_owner_pid >= -1 && record.bind_timer >= 0 && record.revision &&
	       artifact_identity_valid(record.canonical_item_uid, record.identity_state);
}

bool valid_records(const std::vector<flatfile_artifact_record> &records)
{
	if (records.size() > ARTIFACT_IDENTITY_MAX_RECORDS ||
	    !std::is_sorted(records.begin(), records.end(), record_less))
		return false;
	std::vector<uint64_t> identities;
	try
	{
		identities.reserve(records.size());
		for (size_t index = 0; index < records.size(); ++index)
		{
			if (!valid_record(records[index]) ||
			    (index && records[index - 1].vnum == records[index].vnum))
				return false;
			if (records[index].canonical_item_uid)
				identities.push_back(records[index].canonical_item_uid);
		}
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	std::sort(identities.begin(), identities.end());
	return std::adjacent_find(identities.begin(), identities.end()) == identities.end();
}

bool encode_catalog(const artifact_catalog &catalog, std::vector<uint8_t> *bytes)
{
	if (!bytes || !catalog.revision || !valid_records(catalog.records))
		return false;
	encoder payload;
	payload.number<uint32_t>(catalog.records.size());
	for (const auto &record : catalog.records)
	{
		payload.number(record.vnum);
		payload.number<uint8_t>(record.owned ? 1 : 0);
		payload.number(record.location_type);
		payload.number(record.location);
		payload.number(record.timer);
		payload.number(record.type);
		payload.number(record.last_update);
		payload.number(record.bind_owner_pid);
		payload.number(record.bind_timer);
		payload.number(record.revision);
		payload.number(record.canonical_item_uid);
		payload.number(static_cast<uint8_t>(record.identity_state));
		payload.number<uint8_t>(record.identity_only ? 1 : 0);
	}
	if (!payload.valid || payload.bytes.size() > catalog_maximum_bytes)
		return false;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(payload.bytes.data(), payload.bytes.size(), digest.data());
	encoder file;
	file.raw(catalog_magic.data(), catalog_magic.size());
	file.number(catalog_version);
	file.number<uint32_t>(payload.bytes.size());
	file.number(catalog.revision);
	file.raw(digest.data(), digest.size());
	file.raw(payload.bytes.data(), payload.bytes.size());
	if (!file.valid || file.bytes.size() > catalog_maximum_bytes)
		return false;
	*bytes = std::move(file.bytes);
	return true;
}

bool decode_catalog(const std::vector<uint8_t> &bytes, artifact_catalog *catalog)
{
	constexpr size_t header_size = 8 + 4 + 4 + 8 + SHA256_DIGEST_LENGTH;
	if (!catalog || bytes.size() < header_size ||
	    memcmp(bytes.data(), catalog_magic.data(), catalog_magic.size()))
		return false;
	decoder header{ bytes.data() + 8, bytes.size() - 8 };
	uint32_t version = 0, payload_size = 0;
	uint64_t revision = 0;
	if (!header.number(&version) || !header.number(&payload_size) ||
	    !header.number(&revision) || (version < 1 || version > catalog_version) || !revision ||
	    payload_size != bytes.size() - header_size)
		return false;
	const uint8_t *payload_bytes = bytes.data() + header_size;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(payload_bytes, payload_size, digest.data());
	if (CRYPTO_memcmp(bytes.data() + 24, digest.data(), digest.size()))
		return false;
	decoder payload{ payload_bytes, payload_size };
	artifact_catalog decoded;
	decoded.revision = revision;
	uint32_t count = 0;
	if (!payload.number(&count) || count > ARTIFACT_IDENTITY_MAX_RECORDS)
		return false;
	try
	{
		decoded.records.resize(count);
		for (auto &record : decoded.records)
		{
			uint8_t owned = 0;
			if (!payload.number(&record.vnum) || !payload.number(&owned) || owned > 1 ||
			    !payload.number(&record.location_type) ||
			    !payload.number(&record.location) || !payload.number(&record.timer) ||
			    !payload.number(&record.type) || !payload.number(&record.last_update) ||
			    !payload.number(&record.bind_owner_pid) ||
			    !payload.number(&record.bind_timer) ||
			    !payload.number(&record.revision))
				return false;
			if (version >= 2)
			{
				uint8_t state = 0;
				if (!payload.number(&record.canonical_item_uid) ||
				    !payload.number(&state))
					return false;
				record.identity_state = static_cast<artifact_identity_state>(state);
			}
			record.owned = owned != 0;
			if (version >= 3)
			{
				uint8_t identity_only = 0;
				if (!payload.number(&identity_only) || identity_only > 1)
					return false;
				record.identity_only = identity_only != 0;
			}
			else
				// Preserve the v1/v2 load rule; unresolved legacy rows cannot be
				// distinguished from old reservations without an explicit marker.
				record.identity_only =
					!record.owned &&
					record.location_type == FLATFILE_ARTIFACT_NOT_IN_GAME &&
					(record.identity_state ==
						 artifact_identity_state::retired ||
					 record.identity_state == artifact_identity_state::absent);
		}
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	if (payload.offset != payload.size || !valid_records(decoded.records))
		return false;
	*catalog = std::move(decoded);
	return true;
}

flatfile_artifact_result recover(const std::string &root, const flatfile_authority_lock &lock,
				 std::string *error)
{
	const auto result = flatfile_authority_transaction_recover(root, lock, error);
	if (result == flatfile_authority_transaction_result::ok)
		return flatfile_artifact_result::ok;
	return result == flatfile_authority_transaction_result::io_error ?
		       flatfile_artifact_result::io_error :
		       flatfile_artifact_result::invalid;
}

flatfile_artifact_result load_catalog(const std::string &root, artifact_catalog *catalog,
				      std::string *error)
{
	std::vector<uint8_t> bytes;
	const auto loaded = flatfile_read(domains_directory(root), catalog_filename,
					  catalog_maximum_bytes, &bytes, error);
	if (loaded == flatfile_read_result::not_found)
		return flatfile_artifact_result::not_found;
	if (loaded == flatfile_read_result::io_error)
		return flatfile_artifact_result::io_error;
	if (loaded != flatfile_read_result::ok || !decode_catalog(bytes, catalog))
	{
		if (error && error->empty())
			*error = "artifact catalog is corrupt";
		return flatfile_artifact_result::invalid;
	}
	return flatfile_artifact_result::ok;
}
} // namespace

flatfile_artifact_result
flatfile_artifact_establish(const std::string &root,
			    const std::vector<flatfile_artifact_record> &records,
			    std::string *error)
{
	if (root.empty())
		return flatfile_artifact_result::invalid;
	artifact_catalog candidate;
	try
	{
		candidate.records = records;
		std::sort(candidate.records.begin(), candidate.records.end(), record_less);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_artifact_result::io_error;
	}
	if (!valid_records(candidate.records))
		return flatfile_artifact_result::invalid;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_artifact_result::io_error;
	const auto recovered = recover(root, lock, error);
	if (recovered != flatfile_artifact_result::ok)
		return recovered;
	artifact_catalog existing;
	const auto loaded = load_catalog(root, &existing, error);
	if (loaded == flatfile_artifact_result::ok)
		return existing.records == candidate.records ?
			       flatfile_artifact_result::already_exists :
			       flatfile_artifact_result::invalid;
	if (loaded != flatfile_artifact_result::not_found)
		return loaded;
	std::vector<uint8_t> bytes;
	if (!encode_catalog(candidate, &bytes))
		return flatfile_artifact_result::invalid;
	return flatfile_atomic_write(domains_directory(root), catalog_filename, bytes, error) ?
		       flatfile_artifact_result::ok :
		       flatfile_artifact_result::io_error;
}

flatfile_artifact_result flatfile_artifact_ensure(const std::string &root, std::string *error)
{
	if (root.empty())
		return flatfile_artifact_result::invalid;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_artifact_result::io_error;
	const auto recovered = recover(root, lock, error);
	if (recovered != flatfile_artifact_result::ok)
		return recovered;
	artifact_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded == flatfile_artifact_result::ok)
		return flatfile_artifact_result::already_exists;
	if (loaded != flatfile_artifact_result::not_found)
		return loaded;
	std::vector<uint8_t> bytes;
	if (!encode_catalog(catalog, &bytes))
		return flatfile_artifact_result::invalid;
	return flatfile_atomic_write(domains_directory(root), catalog_filename, bytes, error) ?
		       flatfile_artifact_result::ok :
		       flatfile_artifact_result::io_error;
}

flatfile_artifact_result flatfile_artifact_list(const std::string &root,
						std::vector<flatfile_artifact_record> *records,
						std::string *error)
{
	if (root.empty() || !records)
		return flatfile_artifact_result::invalid;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_artifact_result::io_error;
	const auto recovered = recover(root, lock, error);
	if (recovered != flatfile_artifact_result::ok)
		return recovered;
	artifact_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_artifact_result::ok)
		return loaded;
	try
	{
		*records = catalog.records;
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_artifact_result::io_error;
	}
	return flatfile_artifact_result::ok;
}

flatfile_artifact_result flatfile_artifact_get(const std::string &root, int32_t vnum,
					       flatfile_artifact_record *record, std::string *error)
{
	if (record)
		*record = {};
	if (root.empty() || vnum <= 0 || !record)
		return flatfile_artifact_result::invalid;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_artifact_result::io_error;
	const auto recovered = recover(root, lock, error);
	if (recovered != flatfile_artifact_result::ok)
		return recovered;
	artifact_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_artifact_result::ok)
		return loaded;
	const auto found = std::lower_bound(catalog.records.begin(), catalog.records.end(), vnum,
					    [](const flatfile_artifact_record &candidate,
					       int32_t sought) { return candidate.vnum < sought; });
	if (found == catalog.records.end() || found->vnum != vnum)
		return flatfile_artifact_result::not_found;
	*record = *found;
	return flatfile_artifact_result::ok;
}

flatfile_artifact_result
flatfile_artifact_snapshot_apply(const std::string &root,
				 const std::vector<flatfile_artifact_record> &records,
				 std::string *error)
{
	if (root.empty() || records.empty() || records.size() > ARTIFACT_IDENTITY_MAX_RECORDS)
		return flatfile_artifact_result::invalid;
	try
	{
		auto captured = records;
		for (auto &record : captured)
			record.revision = 1;
		std::sort(captured.begin(), captured.end(), record_less);
		if (!valid_records(captured))
			return flatfile_artifact_result::invalid;
		flatfile_authority_lock lock;
		if (!lock.acquire(root, error))
			return flatfile_artifact_result::io_error;
		const auto recovered = recover(root, lock, error);
		if (recovered != flatfile_artifact_result::ok)
			return recovered;
		artifact_catalog catalog;
		const auto loaded = load_catalog(root, &catalog, error);
		if (loaded != flatfile_artifact_result::ok)
			return loaded;
		std::vector<flatfile_artifact_record> merged;
		merged.reserve(std::min(ARTIFACT_IDENTITY_MAX_RECORDS,
					catalog.records.size() + captured.size()));
		auto old = catalog.records.begin();
		auto next = captured.begin();
		bool changed = false;
		while (old != catalog.records.end() || next != captured.end())
		{
			if (merged.size() == ARTIFACT_IDENTITY_MAX_RECORDS)
				return flatfile_artifact_result::invalid;
			if (next == captured.end() ||
			    (old != catalog.records.end() && old->vnum < next->vnum))
			{
				merged.push_back(*old++);
				continue;
			}
			auto desired = *next++;
			if (old != catalog.records.end() && old->vnum == desired.vnum)
			{
				desired.revision = old->revision;
				if (desired != *old)
				{
					if (desired.revision == UINT64_MAX)
						return flatfile_artifact_result::invalid;
					++desired.revision;
					changed = true;
				}
				++old;
			}
			else
				changed = true;
			merged.push_back(desired);
		}
		if (!changed)
			return flatfile_artifact_result::unchanged;
		if (!valid_records(merged))
			return flatfile_artifact_result::conflict;
		if (catalog.revision == UINT64_MAX)
			return flatfile_artifact_result::invalid;
		catalog.records = std::move(merged);
		++catalog.revision;
		std::vector<uint8_t> bytes;
		if (!encode_catalog(catalog, &bytes))
			return flatfile_artifact_result::invalid;
		return flatfile_atomic_write(domains_directory(root), catalog_filename, bytes,
					     error) ?
			       flatfile_artifact_result::ok :
			       flatfile_artifact_result::io_error;
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_artifact_result::io_error;
	}
}

flatfile_artifact_result flatfile_artifact_prepare_player_release(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	flatfile_authority_operation *operation, std::string *error)
{
	if (root.empty() || !pid || !operation || !lock.matches(root))
		return flatfile_artifact_result::invalid;
	*operation = {};
	const auto recovered = recover(root, lock, error);
	if (recovered != flatfile_artifact_result::ok)
		return recovered;
	artifact_catalog catalog;
	const auto loaded = load_catalog(root, &catalog, error);
	if (loaded != flatfile_artifact_result::ok)
		return loaded;
	bool changed = false;
	for (auto &record : catalog.records)
	{
		const bool held = (record.location_type == FLATFILE_ARTIFACT_ON_PLAYER ||
				   record.location_type == FLATFILE_ARTIFACT_ON_CORPSE) &&
				  record.location == static_cast<int32_t>(pid);
		const bool bound = record.bind_owner_pid == static_cast<int32_t>(pid);
		if (!held && !bound)
			continue;
		if (record.revision == std::numeric_limits<uint64_t>::max())
			return flatfile_artifact_result::invalid;
		if (held)
		{
			record.owned = false;
			record.location_type = FLATFILE_ARTIFACT_NOT_IN_GAME;
			record.location = 0;
			record.timer = 0;
		}
		if (bound)
		{
			record.bind_owner_pid = -1;
			record.bind_timer = 0;
		}
		++record.revision;
		changed = true;
	}
	if (!changed)
		return flatfile_artifact_result::unchanged;
	if (catalog.revision == std::numeric_limits<uint64_t>::max())
		return flatfile_artifact_result::invalid;
	++catalog.revision;
	std::vector<uint8_t> bytes;
	if (!encode_catalog(catalog, &bytes))
		return flatfile_artifact_result::invalid;
	operation->store = flatfile_authority_store::domains;
	operation->kind = flatfile_authority_operation_kind::write;
	operation->filename = catalog_filename;
	operation->bytes = std::move(bytes);
	return flatfile_artifact_result::ok;
}

bool flatfile_artifact_room_transfer_allowed(const item_transfer_payload &payload)
{
	if (payload.from_owner.type != item_owner_type::system)
		return true;
	std::vector<player_item_snapshot> items;
	return player_item_snapshot_list_decode(payload.item_blob.data(), payload.item_blob_size,
						&items) == player_snapshot_codec_result::ok &&
	       std::none_of(items.begin(), items.end(), [](const auto &item)
			    { return item.extra_flags & artifact_extra_flag; });
}
