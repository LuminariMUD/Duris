/****************************************************************************
 *
 *  File: flatfile_player_domain_repository.c                   Part of Duris
 *  Usage: flat-file player domains: wallet, bank, stats, and authority
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "flatfile/flatfile_player_domain_repository.h"

#include "flatfile/flatfile_authority_transaction.h"
#include "flatfile/flatfile_store.h"
#include "combat/combat_outcome_command.h"
#include "economy/currency_command.h"
#include "world/epic_command.h"
#include "world/zone_touch_command.h"
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_player_snapshot_file.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <charconv>
#include <filesystem>
#include <array>
#include <cerrno>
#include <cstring>
#include <limits>
#include <mutex>
#include <new>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <type_traits>
#include <vector>

namespace
{
// Native formats 2 and 3 retain their 2048-byte receipt limit independently
// of the larger in-memory completion buffer. No persistent format change.
constexpr size_t FLATFILE_LEGACY_DOMAIN_RESULT_MAX_BYTES = 2048;
static_assert(FLATFILE_LEGACY_DOMAIN_RESULT_MAX_BYTES <= CRITICAL_COMPLETION_RESULT_MAX_BYTES);
constexpr uint32_t domain_format_version = 3;
constexpr std::array<uint8_t, 8> player_magic = { 'D', 'U', 'R', 'P', 'D', 'O', 'M', 0 };
constexpr std::array<uint8_t, 8> bank_magic = { 'D', 'U', 'R', 'B', 'A', 'N', 'K', 0 };
constexpr std::array<uint8_t, 8> transaction_magic = { 'D', 'U', 'R', 'T', 'X', 'N', 0, 0 };
constexpr std::array<uint8_t, 8> zone_magic = { 'D', 'U', 'R', 'Z', 'O', 'N', 'E', 0 };
constexpr std::array<uint8_t, 8> receipt_magic = { 'D', 'U', 'R', 'R', 'C', 'P', 'T', 0 };
constexpr std::array<uint8_t, 8> artifact_pending_magic = { 'D', 'U', 'R', 'A', 'G', 'P', 'N', 0 };
constexpr const char *artifact_pending_filename = "artifact_guild_pending";
constexpr unsigned int artifact_delivery_pending = 0x41470000;
constexpr unsigned int artifact_delivery_acked = artifact_delivery_pending + 1;
static_assert(COMBAT_OUTCOME_MAX_PARTICIPANTS * 2 + 2 <=
	      flatfile_authority_transaction_maximum_operations);
static_assert(ZONE_TOUCH_MAX_PARTICIPANTS * 2 + 4 <=
	      flatfile_authority_transaction_maximum_operations);

// Only unpaid prepared awards and the last prepared edge remain per player.
// Permanent command receipts live independently, without a lifetime count cap.
constexpr size_t domain_maximum_operations = DIVINE_EPIC_RECOVERY_MAX + 1;
// Accommodate the declared receipt count, including complete combat results.
constexpr size_t domain_maximum_bytes =
	(FLATFILE_LEGACY_DOMAIN_RESULT_MAX_BYTES + 64) * domain_maximum_operations + 64 * 1024;
constexpr size_t transaction_maximum_records = COMBAT_OUTCOME_MAX_PARTICIPANTS * 2;
constexpr size_t transaction_maximum_bytes =
	domain_maximum_bytes * transaction_maximum_records + 4096;
constexpr size_t account_maximum_bytes = PLAYER_LOAD_ACCOUNT_MAX;
constexpr const char *transaction_filename = ".player-domain-transaction";
std::mutex domain_mutex;

struct bank_record
{
	std::string account_name;
	int8_t racewar = 0;
	uint64_t revision = 0;
	std::array<uint64_t, 4> balances = {};
};

struct domain_operation
{
	critical_operation_id operation_id;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> command_digest;
	unsigned int result_code = 0;
	uint16_t result_size = 0;
	std::array<uint8_t, FLATFILE_LEGACY_DOMAIN_RESULT_MAX_BYTES> result = {};
};

struct player_authority
{
	flatfile_player_domain_record record;
	std::vector<domain_operation> operations;
};

struct transaction_player
{
	int32_t pid = 0;
	std::vector<uint8_t> bytes;
};

struct transaction_bank
{
	std::string account_name;
	int8_t racewar = 0;
	std::vector<uint8_t> bytes;
};

struct domain_transaction
{
	std::vector<transaction_player> players;
	// Only an older server's currency command wrote a bank here; recovery finishes it.
	std::vector<transaction_bank> banks;
};

enum class player_publish_result
{
	ok,
	invalid,
	io_error
};

struct encoder
{
	std::vector<uint8_t> bytes;
	bool valid = true;

	template <typename T> void number(T value)
	{
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

	void string(const std::string &value)
	{
		number<uint32_t>(value.size());
		try
		{
			bytes.insert(bytes.end(), value.begin(), value.end());
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

	bool string(std::string *value)
	{
		uint32_t length = 0;
		if (!value || !number(&length) || !length || length > account_maximum_bytes ||
		    size - offset < length)
			return false;
		value->assign(reinterpret_cast<const char *>(data + offset), length);
		offset += length;
		return value->find('\0') == std::string::npos;
	}

	bool raw(uint8_t *value, size_t count)
	{
		if (!value || size - offset < count)
			return false;
		memcpy(value, data + offset, count);
		offset += count;
		return true;
	}
};

void encode_operation(encoder &payload, const domain_operation &operation)
{
	payload.raw(operation.operation_id.bytes.data(), operation.operation_id.bytes.size());
	payload.raw(operation.command_digest.data(), operation.command_digest.size());
	payload.number(operation.result_code);
	payload.number(operation.result_size);
	payload.raw(operation.result.data(), operation.result_size);
}

bool decode_operation(decoder &payload, domain_operation *operation)
{
	return operation &&
	       payload.raw(operation->operation_id.bytes.data(),
			   operation->operation_id.bytes.size()) &&
	       payload.raw(operation->command_digest.data(), operation->command_digest.size()) &&
	       payload.number(&operation->result_code) && payload.number(&operation->result_size) &&
	       operation->result_size <= operation->result.size() &&
	       payload.raw(operation->result.data(), operation->result_size) &&
	       !critical_operation_id_is_zero(operation->operation_id);
}

std::string domains_directory(const std::string &root)
{
	return root + "/domains";
}

bool canonical_account(const std::string &input, std::string *canonical)
{
	if (!canonical || input.empty() || input.size() > account_maximum_bytes)
		return false;
	canonical->clear();
	canonical->reserve(input.size());
	for (unsigned char character : input)
	{
		if (character >= 'A' && character <= 'Z')
			canonical->push_back(static_cast<char>(character - 'A' + 'a'));
		else if ((character >= 'a' && character <= 'z') ||
			 (character >= '0' && character <= '9') || character == '_' ||
			 character == '-')
			canonical->push_back(static_cast<char>(character));
		else
			return false;
	}
	return true;
}

std::string player_filename(int32_t pid)
{
	return "player-" + std::to_string(pid) + ".domain";
}

std::string bank_filename(const std::string &account, int8_t racewar)
{
	return "bank-" + account + "-" + std::to_string(static_cast<int>(racewar)) + ".domain";
}

bool valid_gameplay(const flatfile_player_domain_record &record)
{
	if (record.recent_pvp_deaths.size() > PLAYER_LOAD_RECENT_PVP_MAX ||
	    record.completed_epic_zones.size() > PLAYER_LOAD_COMPLETED_ZONE_MAX)
		return false;
	for (size_t index = 0; index < record.recent_pvp_deaths.size(); ++index)
		if (record.recent_pvp_deaths[index] <= 0 ||
		    (index &&
		     record.recent_pvp_deaths[index - 1] < record.recent_pvp_deaths[index]))
			return false;
	for (size_t index = 0; index < record.completed_epic_zones.size(); ++index)
		if (record.completed_epic_zones[index] <= 0 ||
		    (index &&
		     record.completed_epic_zones[index - 1] >= record.completed_epic_zones[index]))
			return false;
	if (!record.domains.base_stat_revision &&
	    record.domains.base_stats != std::array<int16_t, 10>{})
		return false;
	for (int16_t stat : record.domains.base_stats)
		if (stat < 0 || stat > 100)
			return false;
	return true;
}

bool encode_envelope(const std::array<uint8_t, 8> &magic, const std::vector<uint8_t> &payload,
		     uint64_t revision, size_t maximum_bytes, std::vector<uint8_t> *bytes)
{
	if (!bytes || !revision || payload.size() > maximum_bytes)
		return false;
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(payload.data(), payload.size(), digest);
	encoder file;
	try
	{
		file.bytes.insert(file.bytes.end(), magic.begin(), magic.end());
		file.number<uint32_t>(domain_format_version);
		file.number<uint32_t>(payload.size());
		file.number(revision);
		file.bytes.insert(file.bytes.end(), digest, digest + sizeof(digest));
		file.bytes.insert(file.bytes.end(), payload.begin(), payload.end());
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	if (!file.valid || file.bytes.size() > maximum_bytes)
		return false;
	*bytes = std::move(file.bytes);
	return true;
}

bool encode_file(const std::array<uint8_t, 8> &magic, const std::vector<uint8_t> &payload,
		 uint64_t revision, std::vector<uint8_t> *bytes)
{
	return encode_envelope(magic, payload, revision, domain_maximum_bytes, bytes);
}

flatfile_player_domain_result decode_envelope(const std::vector<uint8_t> &bytes,
					      const std::array<uint8_t, 8> &magic, decoder *payload,
					      uint64_t *revision, uint32_t *format_version)
{
	constexpr size_t header_size =
		8 + sizeof(uint32_t) * 2 + sizeof(uint64_t) + SHA256_DIGEST_LENGTH;
	if (!payload || !revision || !format_version || bytes.size() < header_size ||
	    memcmp(bytes.data(), magic.data(), magic.size()))
		return flatfile_player_domain_result::invalid;
	decoder header{ bytes.data() + magic.size(), bytes.size() - magic.size() };
	uint32_t version = 0, payload_size = 0;
	if (!header.number(&version) || !header.number(&payload_size) || !header.number(revision) ||
	    !version || version > domain_format_version || !*revision ||
	    payload_size != bytes.size() - header_size)
		return flatfile_player_domain_result::invalid;
	const uint8_t *digest =
		bytes.data() + magic.size() + sizeof(uint32_t) * 2 + sizeof(uint64_t);
	const uint8_t *data = bytes.data() + header_size;
	unsigned char actual[SHA256_DIGEST_LENGTH];
	SHA256(data, payload_size, actual);
	if (CRYPTO_memcmp(digest, actual, sizeof(actual)))
		return flatfile_player_domain_result::invalid;
	*payload = { data, payload_size };
	*format_version = version;
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result read_bytes(const std::string &root, const std::string &filename,
					 std::vector<uint8_t> *bytes, std::string *error)
{
	const flatfile_read_result read = flatfile_read(domains_directory(root), filename,
							domain_maximum_bytes, bytes, error);
	if (read == flatfile_read_result::not_found)
		return flatfile_player_domain_result::not_found;
	if (read == flatfile_read_result::invalid)
		return flatfile_player_domain_result::invalid;
	return read == flatfile_read_result::ok ? flatfile_player_domain_result::ok :
						  flatfile_player_domain_result::io_error;
}

std::string receipt_filename(const critical_operation_id &operation)
{
	char hex[CRITICAL_COMMAND_ID_HEX_SIZE] = {};
	critical_operation_id_to_hex(operation, hex, sizeof(hex));
	return std::string("command-") + hex + ".receipt";
}

bool encode_receipt(const domain_operation &operation, flatfile_authority_operation *write)
{
	encoder payload;
	encode_operation(payload, operation);
	write->filename = receipt_filename(operation.operation_id);
	return payload.valid && encode_file(receipt_magic, payload.bytes, 1, &write->bytes);
}

flatfile_player_domain_result load_receipt_file(const std::string &root,
						const std::string &filename,
						domain_operation *receipt, std::string *error)
{
	std::vector<uint8_t> bytes;
	const auto read = read_bytes(root, filename, &bytes, error);
	if (read != flatfile_player_domain_result::ok)
		return read;
	decoder payload{ nullptr, 0 };
	uint64_t revision = 0;
	uint32_t version = 0;
	if (decode_envelope(bytes, receipt_magic, &payload, &revision, &version) !=
		    flatfile_player_domain_result::ok ||
	    revision != 1 || version != domain_format_version ||
	    !decode_operation(payload, receipt) || payload.offset != payload.size)
		return flatfile_player_domain_result::invalid;
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result load_receipt(const std::string &root,
					   const critical_operation_id &operation,
					   domain_operation *receipt, std::string *error)
{
	const auto loaded = load_receipt_file(root, receipt_filename(operation), receipt, error);
	if (loaded == flatfile_player_domain_result::ok &&
	    !critical_operation_id_equal(receipt->operation_id, operation))
		return flatfile_player_domain_result::invalid;
	return loaded;
}

flatfile_player_domain_result load_zone_state(const std::string &root, uint32_t number,
					      flatfile_zone_touch_state *state, std::string *error)
{
	std::vector<uint8_t> bytes;
	const auto loaded =
		read_bytes(root, "zone-" + std::to_string(number) + ".state", &bytes, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	decoder payload{ nullptr, 0 };
	uint64_t revision = 0;
	uint32_t version = 0;
	if (decode_envelope(bytes, zone_magic, &payload, &revision, &version) !=
		    flatfile_player_domain_result::ok ||
	    !payload.number(&state->number) || !payload.number(&state->alignment) ||
	    !payload.number(&state->last_touch) || state->number != number ||
	    state->alignment < -5 || state->alignment > 5 || state->last_touch <= 0 ||
	    payload.offset != payload.size)
		return flatfile_player_domain_result::invalid;
	return flatfile_player_domain_result::ok;
}

critical_apply_result replay_receipt(const critical_command &command,
				     const std::array<uint8_t, SHA256_DIGEST_LENGTH> &digest,
				     const domain_operation &receipt)
{
	if (CRYPTO_memcmp(receipt.command_digest.data(), digest.data(), digest.size()))
		return { critical_apply_outcome::terminal_failure, 0, EEXIST };
	uint64_t revision = 0;
	if (command.type == critical_command_type::combat_outcome)
	{
		combat_outcome_result result;
		if (!combat_outcome_command_decode_result(receipt.result.data(),
							  receipt.result_size, &result))
			return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
		for (const auto &entry : result.participants)
			revision = std::max({ revision, entry.frag_revision, entry.epic_revision,
					      entry.wallet_revision, entry.bank_revision });
	}
	else if (command.type == critical_command_type::zone)
	{
		zone_touch_result result;
		if (!zone_touch_command_decode_result(receipt.result.data(), receipt.result_size,
						      &result))
			return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
		for (size_t i = 0; i < result.group_size; ++i)
			revision = std::max(revision, result.revisions[i]);
	}
	else
	{
		epic_command_result result;
		if (!epic_command_decode_result(receipt.result.data(), receipt.result_size,
						&result))
			return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
		revision = result.revision;
	}
	critical_apply_result result = { receipt.result_code ?
						 critical_apply_outcome::terminal_failure :
						 critical_apply_outcome::already_applied,
					 revision, receipt.result_code };
	result.result_size = receipt.result_size;
	std::copy_n(receipt.result.begin(), receipt.result_size, result.result_payload.begin());
	return result;
}

// Both producers share one recipient sequence. Ordinary receipts have no delivery.
bool operation_delivery(const domain_operation &operation, uint32_t pid,
			divine_epic_delivery *delivery)
{
	*delivery = {};
	if (operation.result_code)
		return true;
	if (operation.result_size == COMBAT_OUTCOME_RESULT_BYTES &&
	    !memcmp(operation.result.data(), "DBCOMB05", 8))
	{
		combat_outcome_result result;
		if (!combat_outcome_command_decode_result(operation.result.data(),
							  operation.result_size, &result))
			return false;
		for (size_t i = 0; i < result.participant_count; ++i)
			if (result.participants[i].pid == pid &&
			    result.participants[i].epic_delivery_flags)
				return divine_epic_delivery_from_combat(operation.operation_id,
									result, i, delivery);
	}
	else if (operation.result_size == ZONE_TOUCH_RESULT_BYTES)
	{
		zone_touch_result result;
		if (!zone_touch_command_decode_result(operation.result.data(),
						      operation.result_size, &result))
			return false;
		if (result.prepared_delivery)
			for (size_t i = 0; i < result.group_size; ++i)
				if (result.participant_pids[i] == pid)
					return divine_epic_delivery_from_zone(
						result.parent_operation, result, i, delivery);
	}
	return true;
}

// Copy legacy receipts before dropping their per-player duplicate. A crash here
// leaves an extra identical receipt; the player checkpoint still owns payment.
flatfile_player_domain_result compact_receipts(const std::string &root, player_authority *player,
					       uint64_t paid, size_t *unpaid, std::string *error)
{
	std::vector<uint64_t> sequences;
	uint64_t latest = 0;
	*unpaid = 0;
	for (const auto &operation : player->operations)
	{
		divine_epic_delivery delivery;
		if (!operation_delivery(operation, static_cast<uint32_t>(player->record.pid),
					&delivery))
			return flatfile_player_domain_result::invalid;
		const uint64_t sequence = delivery.sequence;
		sequences.push_back(sequence);
		latest = std::max(latest, sequence);
		if (sequence > paid)
			++*unpaid;
	}
	size_t kept = 0;
	for (size_t index = 0; index < player->operations.size(); ++index)
	{
		const auto &operation = player->operations[index];
		const uint64_t sequence = sequences[index];
		if (sequence && (sequence > paid || sequence == latest))
		{
			player->operations[kept++] = operation;
			continue;
		}
		domain_operation archived;
		const auto loaded = load_receipt(root, operation.operation_id, &archived, error);
		if (loaded == flatfile_player_domain_result::not_found)
		{
			flatfile_authority_operation write;
			if (!encode_receipt(operation, &write))
				return flatfile_player_domain_result::invalid;
			if (!flatfile_atomic_write(domains_directory(root), write.filename,
						   write.bytes, error))
				return flatfile_player_domain_result::io_error;
		}
		else if (loaded != flatfile_player_domain_result::ok)
			return loaded;
		else if (archived.command_digest != operation.command_digest ||
			 archived.result_code != operation.result_code ||
			 archived.result_size != operation.result_size ||
			 memcmp(archived.result.data(), operation.result.data(),
				operation.result_size))
			return flatfile_player_domain_result::invalid;
	}
	player->operations.resize(kept);
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result decode_transaction(const std::vector<uint8_t> &bytes,
						 domain_transaction *transaction)
{
	if (!transaction)
		return flatfile_player_domain_result::invalid;
	*transaction = {};
	decoder payload{ nullptr, 0 };
	uint64_t revision = 0;
	uint32_t format_version = 0;
	uint16_t player_count = 0, bank_count = 0;
	if (decode_envelope(bytes, transaction_magic, &payload, &revision, &format_version) !=
		    flatfile_player_domain_result::ok ||
	    format_version < 2 || format_version > domain_format_version || revision != 1 ||
	    !payload.number(&player_count) || !payload.number(&bank_count) || !player_count ||
	    static_cast<size_t>(player_count) + bank_count > transaction_maximum_records)
		return flatfile_player_domain_result::invalid;
	try
	{
		transaction->players.resize(player_count);
		transaction->banks.resize(bank_count);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_player_domain_result::io_error;
	}
	for (size_t index = 0; index < transaction->players.size(); ++index)
	{
		auto &player = transaction->players[index];
		uint32_t size = 0;
		if (!payload.number(&player.pid) || !payload.number(&size) || player.pid <= 0 ||
		    !size || size > domain_maximum_bytes)
			return flatfile_player_domain_result::invalid;
		try
		{
			player.bytes.resize(size);
		}
		catch (const std::bad_alloc &)
		{
			return flatfile_player_domain_result::io_error;
		}
		if (!payload.raw(player.bytes.data(), player.bytes.size()))
			return flatfile_player_domain_result::invalid;
		decoder embedded{ nullptr, 0 };
		uint64_t embedded_revision = 0;
		uint32_t embedded_version = 0;
		int32_t embedded_pid = 0;
		if (decode_envelope(player.bytes, player_magic, &embedded, &embedded_revision,
				    &embedded_version) != flatfile_player_domain_result::ok ||
		    !embedded.number(&embedded_pid) || embedded_pid != player.pid)
			return flatfile_player_domain_result::invalid;
		for (size_t prior = 0; prior < index; ++prior)
			if (transaction->players[prior].pid == player.pid)
				return flatfile_player_domain_result::invalid;
	}
	for (size_t index = 0; index < transaction->banks.size(); ++index)
	{
		auto &bank = transaction->banks[index];
		uint32_t size = 0;
		if (!payload.string(&bank.account_name) || !payload.number(&bank.racewar) ||
		    !payload.number(&size) || !size || size > domain_maximum_bytes)
			return flatfile_player_domain_result::invalid;
		try
		{
			bank.bytes.resize(size);
		}
		catch (const std::bad_alloc &)
		{
			return flatfile_player_domain_result::io_error;
		}
		if (!payload.raw(bank.bytes.data(), bank.bytes.size()))
			return flatfile_player_domain_result::invalid;
		std::string canonical, embedded_account;
		int8_t embedded_racewar = 0;
		decoder embedded{ nullptr, 0 };
		uint64_t embedded_revision = 0;
		uint32_t embedded_version = 0;
		if (!canonical_account(bank.account_name, &canonical) ||
		    canonical != bank.account_name ||
		    decode_envelope(bank.bytes, bank_magic, &embedded, &embedded_revision,
				    &embedded_version) != flatfile_player_domain_result::ok ||
		    !embedded.string(&embedded_account) || !embedded.number(&embedded_racewar) ||
		    embedded_account != bank.account_name || embedded_racewar != bank.racewar)
			return flatfile_player_domain_result::invalid;
		for (size_t prior = 0; prior < index; ++prior)
			if (transaction->banks[prior].account_name == bank.account_name &&
			    transaction->banks[prior].racewar == bank.racewar)
				return flatfile_player_domain_result::invalid;
	}
	if (payload.offset != payload.size)
		return flatfile_player_domain_result::invalid;
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result recover_transaction(const std::string &root, std::string *error)
{
	std::vector<uint8_t> bytes;
	const flatfile_read_result read = flatfile_read(domains_directory(root),
							transaction_filename,
							transaction_maximum_bytes, &bytes, error);
	if (read == flatfile_read_result::not_found)
		return flatfile_player_domain_result::ok;
	if (read == flatfile_read_result::invalid)
		return flatfile_player_domain_result::invalid;
	if (read != flatfile_read_result::ok)
		return flatfile_player_domain_result::io_error;
	domain_transaction transaction;
	const auto decoded = decode_transaction(bytes, &transaction);
	if (decoded != flatfile_player_domain_result::ok)
		return decoded;
	for (const transaction_bank &bank : transaction.banks)
		if (!flatfile_atomic_write(domains_directory(root),
					   bank_filename(bank.account_name, bank.racewar),
					   bank.bytes, error))
			return flatfile_player_domain_result::io_error;
	for (const transaction_player &player : transaction.players)
		if (!flatfile_atomic_write(domains_directory(root), player_filename(player.pid),
					   player.bytes, error))
			return flatfile_player_domain_result::io_error;
	if (!flatfile_atomic_remove(domains_directory(root), transaction_filename, false, error))
		return flatfile_player_domain_result::io_error;
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result
recover_authority(const std::string &root, const flatfile_authority_lock &lock, std::string *error)
{
	const auto recovered = flatfile_authority_transaction_recover(root, lock, error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return recovered == flatfile_authority_transaction_result::io_error ?
			       flatfile_player_domain_result::io_error :
			       flatfile_player_domain_result::invalid;
	return recover_transaction(root, error);
}

flatfile_player_domain_result decode_bank_record(const std::vector<uint8_t> &bytes,
						 const std::string &account, int8_t racewar,
						 bank_record *record)
{
	decoder payload{ nullptr, 0 };
	uint64_t revision = 0;
	uint32_t format_version = 0;
	if (decode_envelope(bytes, bank_magic, &payload, &revision, &format_version) !=
	    flatfile_player_domain_result::ok)
		return flatfile_player_domain_result::invalid;
	(void)format_version;
	bank_record decoded;
	if (!payload.string(&decoded.account_name) || !payload.number(&decoded.racewar))
		return flatfile_player_domain_result::invalid;
	for (uint64_t &balance : decoded.balances)
		if (!payload.number(&balance))
			return flatfile_player_domain_result::invalid;
	std::string canonical;
	if (payload.offset != payload.size ||
	    !canonical_account(decoded.account_name, &canonical) || canonical != account ||
	    decoded.racewar != racewar)
		return flatfile_player_domain_result::invalid;
	decoded.revision = revision;
	*record = std::move(decoded);
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result load_bank(const std::string &root, const std::string &account,
					int8_t racewar, bank_record *record, std::string *error)
{
	if (!record)
		return flatfile_player_domain_result::invalid;
	std::vector<uint8_t> bytes;
	const auto read = read_bytes(root, bank_filename(account, racewar), &bytes, error);
	return read == flatfile_player_domain_result::ok ?
		       decode_bank_record(bytes, account, racewar, record) :
		       read;
}

bool encode_bank_record(const bank_record &record, std::vector<uint8_t> *bytes)
{
	encoder payload;
	payload.string(record.account_name);
	payload.number(record.racewar);
	for (uint64_t balance : record.balances)
		payload.number(balance);
	return payload.valid && encode_file(bank_magic, payload.bytes, record.revision, bytes);
}

bool publish_bank(const std::string &root, const bank_record &record, std::string *error)
{
	std::vector<uint8_t> bytes;
	return encode_bank_record(record, &bytes) &&
	       flatfile_atomic_write(domains_directory(root),
				     bank_filename(record.account_name, record.racewar), bytes,
				     error);
}

flatfile_player_domain_result decode_player_authority(const std::vector<uint8_t> &bytes,
						      int32_t pid, player_authority *authority)
{
	decoder payload{ nullptr, 0 };
	uint64_t file_revision = 0;
	uint32_t format_version = 0;
	if (decode_envelope(bytes, player_magic, &payload, &file_revision, &format_version) !=
	    flatfile_player_domain_result::ok)
		return flatfile_player_domain_result::invalid;
	player_authority decoded;
	uint32_t recent_count = 0, zone_count = 0, operation_count = 0;
	if (!payload.number(&decoded.record.pid) || !payload.string(&decoded.record.account_name) ||
	    !payload.number(&decoded.record.racewar) ||
	    !payload.number(&decoded.record.domains.wallet_revision) ||
	    !payload.number(&decoded.record.domains.epic_revision) ||
	    !payload.number(&decoded.record.domains.frag_revision))
		return flatfile_player_domain_result::invalid;
	for (uint64_t &balance : decoded.record.domains.wallet)
		if (!payload.number(&balance))
			return flatfile_player_domain_result::invalid;
	if (!payload.number(&decoded.record.domains.epics) ||
	    !payload.number(&decoded.record.domains.frags) ||
	    !payload.number(&decoded.record.domains.old_frags) || !payload.number(&recent_count) ||
	    recent_count > PLAYER_LOAD_RECENT_PVP_MAX)
		return flatfile_player_domain_result::invalid;
	try
	{
		decoded.record.recent_pvp_deaths.resize(recent_count);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_player_domain_result::io_error;
	}
	for (int64_t &death : decoded.record.recent_pvp_deaths)
		if (!payload.number(&death))
			return flatfile_player_domain_result::invalid;
	if (!payload.number(&zone_count) || zone_count > PLAYER_LOAD_COMPLETED_ZONE_MAX)
		return flatfile_player_domain_result::invalid;
	try
	{
		decoded.record.completed_epic_zones.resize(zone_count);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_player_domain_result::io_error;
	}
	for (int32_t &zone : decoded.record.completed_epic_zones)
		if (!payload.number(&zone))
			return flatfile_player_domain_result::invalid;
	if (format_version >= 3)
	{
		if (!payload.number(&decoded.record.domains.base_stat_revision))
			return flatfile_player_domain_result::invalid;
		for (int16_t &stat : decoded.record.domains.base_stats)
			if (!payload.number(&stat))
				return flatfile_player_domain_result::invalid;
	}
	if (format_version >= 2)
	{
		if (!payload.number(&operation_count) ||
		    operation_count > domain_maximum_operations)
			return flatfile_player_domain_result::invalid;
		try
		{
			decoded.operations.resize(operation_count);
		}
		catch (const std::bad_alloc &)
		{
			return flatfile_player_domain_result::io_error;
		}
		for (domain_operation &operation : decoded.operations)
			if (!decode_operation(payload, &operation))
				return flatfile_player_domain_result::invalid;
	}
	std::string canonical;
	if (payload.offset != payload.size || decoded.record.pid != pid ||
	    !canonical_account(decoded.record.account_name, &canonical) ||
	    decoded.record.account_name != canonical || !valid_gameplay(decoded.record) ||
	    file_revision != std::max({ decoded.record.domains.wallet_revision,
					decoded.record.domains.epic_revision,
					decoded.record.domains.frag_revision,
					decoded.record.domains.base_stat_revision, UINT64_C(1) }))
		return flatfile_player_domain_result::invalid;
	for (size_t index = 0; index < decoded.operations.size(); ++index)
		for (size_t other = index + 1; other < decoded.operations.size(); ++other)
			if (critical_operation_id_equal(decoded.operations[index].operation_id,
							decoded.operations[other].operation_id))
				return flatfile_player_domain_result::invalid;
	*authority = std::move(decoded);
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result load_player_authority(const std::string &root, int32_t pid,
						    player_authority *authority, std::string *error)
{
	if (!authority || pid <= 0)
		return flatfile_player_domain_result::invalid;
	std::vector<uint8_t> bytes;
	const auto read = read_bytes(root, player_filename(pid), &bytes, error);
	return read == flatfile_player_domain_result::ok ?
		       decode_player_authority(bytes, pid, authority) :
		       read;
}

flatfile_player_domain_result load_player(const std::string &root, int32_t pid,
					  flatfile_player_domain_record *record, std::string *error)
{
	player_authority authority;
	const auto loaded = load_player_authority(root, pid, &authority, error);
	if (loaded == flatfile_player_domain_result::ok)
		*record = std::move(authority.record);
	return loaded;
}

bool encode_player_authority(const player_authority &authority, std::vector<uint8_t> *bytes)
{
	const flatfile_player_domain_record &record = authority.record;
	encoder payload;
	payload.number(record.pid);
	payload.string(record.account_name);
	payload.number(record.racewar);
	payload.number(record.domains.wallet_revision);
	payload.number(record.domains.epic_revision);
	payload.number(record.domains.frag_revision);
	for (uint64_t balance : record.domains.wallet)
		payload.number(balance);
	payload.number(record.domains.epics);
	payload.number(record.domains.frags);
	payload.number(record.domains.old_frags);
	payload.number<uint32_t>(record.recent_pvp_deaths.size());
	for (int64_t death : record.recent_pvp_deaths)
		payload.number(death);
	payload.number<uint32_t>(record.completed_epic_zones.size());
	for (int32_t zone : record.completed_epic_zones)
		payload.number(zone);
	payload.number(record.domains.base_stat_revision);
	for (int16_t stat : record.domains.base_stats)
		payload.number(stat);
	payload.number<uint32_t>(authority.operations.size());
	for (const domain_operation &operation : authority.operations)
		encode_operation(payload, operation);
	const uint64_t revision = std::max(
		{ record.domains.wallet_revision, record.domains.epic_revision,
		  record.domains.frag_revision, record.domains.base_stat_revision, UINT64_C(1) });
	return payload.valid && encode_file(player_magic, payload.bytes, revision, bytes);
}

player_publish_result publish_player_authority(const std::string &root,
					       const player_authority &authority,
					       std::string *error)
{
	std::vector<uint8_t> bytes;
	if (!encode_player_authority(authority, &bytes))
		return player_publish_result::invalid;
	return flatfile_atomic_write(domains_directory(root), player_filename(authority.record.pid),
				     bytes, error) ?
		       player_publish_result::ok :
		       player_publish_result::io_error;
}

bool publish_player(const std::string &root, const flatfile_player_domain_record &record,
		    std::string *error)
{
	return publish_player_authority(root, { record, {} }, error) == player_publish_result::ok;
}

flatfile_player_domain_result establish(const std::string &root,
					const flatfile_player_domain_record &record,
					bool require_bank_match, std::string *error)
{
	std::string account;
	if (root.empty() || record.pid <= 0 || !canonical_account(record.account_name, &account) ||
	    record.domains.wallet_revision || record.domains.epic_revision ||
	    record.domains.frag_revision || record.domains.bank_revision ||
	    record.domains.base_stat_revision > 1 || !valid_gameplay(record) ||
	    (!require_bank_match && record.domains.bank != std::array<uint64_t, 4>{}))
		return flatfile_player_domain_result::invalid;
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	const auto recovered = recover_authority(root, authority, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	flatfile_player_domain_record existing;
	const auto player_loaded = load_player(root, record.pid, &existing, error);
	if (player_loaded == flatfile_player_domain_result::ok)
	{
		if (existing.account_name != account || existing.racewar != record.racewar ||
		    existing.domains.wallet != record.domains.wallet ||
		    existing.domains.epics != record.domains.epics ||
		    existing.domains.frags != record.domains.frags ||
		    existing.domains.old_frags != record.domains.old_frags ||
		    existing.domains.base_stat_revision != record.domains.base_stat_revision ||
		    existing.domains.base_stats != record.domains.base_stats ||
		    existing.recent_pvp_deaths != record.recent_pvp_deaths ||
		    existing.completed_epic_zones != record.completed_epic_zones)
			return flatfile_player_domain_result::conflict;
		bank_record bank;
		const auto bank_loaded = load_bank(root, account, record.racewar, &bank, error);
		if (bank_loaded != flatfile_player_domain_result::ok)
			return bank_loaded;
		return !require_bank_match || bank.balances == record.domains.bank ?
			       flatfile_player_domain_result::ok :
			       flatfile_player_domain_result::conflict;
	}
	if (player_loaded != flatfile_player_domain_result::not_found)
		return player_loaded;
	bank_record bank;
	const auto bank_loaded = load_bank(root, account, record.racewar, &bank, error);
	if (bank_loaded == flatfile_player_domain_result::not_found)
	{
		bank = { account, record.racewar, 1, record.domains.bank };
		if (!publish_bank(root, bank, error))
			return flatfile_player_domain_result::io_error;
	}
	else if (bank_loaded != flatfile_player_domain_result::ok)
		return bank_loaded;
	else if (require_bank_match && bank.balances != record.domains.bank)
		return flatfile_player_domain_result::conflict;
	flatfile_player_domain_record canonical = record;
	canonical.account_name = account;
	if (!publish_player(root, canonical, error))
		return flatfile_player_domain_result::io_error;
	return flatfile_player_domain_result::ok;
}
flatfile_player_domain_result
load_artifact_pending(const std::string &root, artifact_guild_delivery_ids *ids, std::string *error)
{
	ids->clear();
	std::vector<uint8_t> bytes;
	const auto loaded = read_bytes(root, artifact_pending_filename, &bytes, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	decoder payload{ nullptr, 0 };
	uint64_t revision = 0;
	uint32_t version = 0;
	uint16_t count = 0;
	if (decode_envelope(bytes, artifact_pending_magic, &payload, &revision, &version) !=
		    flatfile_player_domain_result::ok ||
	    version != domain_format_version || revision != 1 || !payload.number(&count) ||
	    count > ARTIFACT_GUILD_PENDING_MAX)
		return flatfile_player_domain_result::invalid;
	ids->resize(count);
	for (auto &id : *ids)
		if (!payload.raw(id.data(), id.size()))
			return flatfile_player_domain_result::invalid;
	return payload.offset == payload.size && artifact_guild_delivery_ids_valid(*ids) ?
		       flatfile_player_domain_result::ok :
		       flatfile_player_domain_result::invalid;
}

bool encode_artifact_pending(const artifact_guild_delivery_ids &ids,
			     flatfile_authority_operation *write)
{
	if (!artifact_guild_delivery_ids_valid(ids))
		return false;
	encoder payload;
	payload.number<uint16_t>(ids.size());
	for (const auto &id : ids)
		payload.raw(id.data(), id.size());
	write->filename = artifact_pending_filename;
	return payload.valid &&
	       encode_file(artifact_pending_magic, payload.bytes, 1, &write->bytes);
}

flatfile_player_domain_result load_artifact_delivery(const std::string &root,
						     const critical_operation_id &id,
						     domain_operation *receipt,
						     critical_command *command, std::string *error)
{
	const auto loaded = load_receipt(root, id, receipt, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	artifact_guild_payload payload{};
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest{};
	SHA256(receipt->result.data(), receipt->result_size, digest.data());
	if ((receipt->result_code != artifact_delivery_pending &&
	     receipt->result_code != artifact_delivery_acked) ||
	    digest != receipt->command_digest ||
	    critical_command_decode(receipt->result.data(), receipt->result_size, command) !=
		    critical_command_codec_result::ok ||
	    command->operation_id.bytes != id.bytes ||
	    !artifact_guild_command_decode_payload(*command, &payload) ||
	    !artifact_guild_command_valid_delivery(*command, payload.parent_operation_id))
		return flatfile_player_domain_result::invalid;
	return flatfile_player_domain_result::ok;
}

} // namespace

flatfile_player_domain_result
flatfile_artifact_deliveries_list(const std::string &root, const flatfile_authority_lock &lock,
				  std::vector<critical_command> *commands, std::string *error)
{
	if (!lock.matches(root) || !commands)
		return flatfile_player_domain_result::invalid;
	commands->clear();
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	artifact_guild_delivery_ids ids;
	const auto loaded = load_artifact_pending(root, &ids, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	for (const auto &id : ids)
	{
		domain_operation receipt;
		critical_command command;
		const auto read = load_artifact_delivery(root, critical_operation_id{ id },
							 &receipt, &command, error);
		if (read != flatfile_player_domain_result::ok)
			return read;
		if (receipt.result_code != artifact_delivery_pending)
			return flatfile_player_domain_result::invalid;
		commands->push_back(std::move(command));
	}
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result
flatfile_artifact_deliveries_prepare(const std::string &root, const flatfile_authority_lock &lock,
				     const std::vector<critical_command> &commands,
				     std::vector<flatfile_authority_operation> *operations,
				     std::string *error)
{
	if (!lock.matches(root) || !operations || commands.size() > ARTIFACT_GUILD_PENDING_MAX)
		return flatfile_player_domain_result::invalid;
	std::vector<critical_command> pending;
	const auto loaded = flatfile_artifact_deliveries_list(root, lock, &pending, error);
	if (loaded != flatfile_player_domain_result::ok &&
	    loaded != flatfile_player_domain_result::not_found)
		return loaded;
	if (pending.size() + commands.size() > ARTIFACT_GUILD_PENDING_MAX)
		return flatfile_player_domain_result::conflict;
	artifact_guild_delivery_ids ids;
	for (const auto &command : pending)
		ids.push_back(command.operation_id.bytes);
	for (const auto &command : commands)
	{
		artifact_guild_payload payload{};
		std::vector<uint8_t> encoded;
		if (!artifact_guild_command_decode_payload(command, &payload) ||
		    !artifact_guild_command_valid_delivery(command, payload.parent_operation_id) ||
		    critical_command_encode(command, &encoded) !=
			    critical_command_codec_result::ok ||
		    encoded.size() > FLATFILE_LEGACY_DOMAIN_RESULT_MAX_BYTES)
			return flatfile_player_domain_result::invalid;
		domain_operation existing;
		const auto prior = load_receipt(root, command.operation_id, &existing, error);
		if (prior != flatfile_player_domain_result::not_found)
			return prior == flatfile_player_domain_result::ok ?
				       flatfile_player_domain_result::conflict :
				       prior;
		domain_operation receipt{};
		receipt.operation_id = command.operation_id;
		SHA256(encoded.data(), encoded.size(), receipt.command_digest.data());
		receipt.result_code = artifact_delivery_pending;
		receipt.result_size = encoded.size();
		std::copy(encoded.begin(), encoded.end(), receipt.result.begin());
		flatfile_authority_operation write;
		if (!encode_receipt(receipt, &write))
			return flatfile_player_domain_result::invalid;
		operations->push_back(std::move(write));
		ids.push_back(command.operation_id.bytes);
	}
	std::sort(ids.begin(), ids.end());
	flatfile_authority_operation index;
	if (!encode_artifact_pending(ids, &index))
		return flatfile_player_domain_result::invalid;
	operations->push_back(std::move(index));
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result
flatfile_artifact_delivery_load(const std::string &root, const flatfile_authority_lock &lock,
				const critical_operation_id &operation, critical_command *command,
				bool *acknowledged, std::string *error)
{
	if (!lock.matches(root) || !command || !acknowledged)
		return flatfile_player_domain_result::invalid;
	*acknowledged = false;
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	domain_operation receipt;
	const auto loaded = load_artifact_delivery(root, operation, &receipt, command, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	artifact_guild_delivery_ids ids;
	const auto indexed = load_artifact_pending(root, &ids, error);
	if (indexed != flatfile_player_domain_result::ok)
		return indexed;
	*acknowledged = receipt.result_code == artifact_delivery_acked;
	return std::binary_search(ids.begin(), ids.end(), operation.bytes) == !*acknowledged ?
		       flatfile_player_domain_result::ok :
		       flatfile_player_domain_result::invalid;
}

flatfile_player_domain_result flatfile_artifact_delivery_acknowledged(
	const std::string &root, const flatfile_authority_lock &lock,
	const critical_command &expected, bool *acknowledged, std::string *error)
{
	if (!lock.matches(root) || !acknowledged)
		return flatfile_player_domain_result::invalid;
	*acknowledged = false;
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	domain_operation receipt;
	critical_command command;
	const auto loaded =
		load_artifact_delivery(root, expected.operation_id, &receipt, &command, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	artifact_guild_delivery_ids ids;
	const auto indexed = load_artifact_pending(root, &ids, error);
	if (indexed != flatfile_player_domain_result::ok)
		return indexed;
	std::vector<uint8_t> encoded;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest{};
	if (critical_command_encode(expected, &encoded) != critical_command_codec_result::ok)
		return flatfile_player_domain_result::invalid;
	SHA256(encoded.data(), encoded.size(), digest.data());
	if (digest != receipt.command_digest)
		return flatfile_player_domain_result::conflict;
	*acknowledged = receipt.result_code == artifact_delivery_acked;
	return std::binary_search(ids.begin(), ids.end(), expected.operation_id.bytes) ==
			       !*acknowledged ?
		       flatfile_player_domain_result::ok :
		       flatfile_player_domain_result::invalid;
}

flatfile_player_domain_result
flatfile_artifact_delivery_prepare_ack(const std::string &root, const flatfile_authority_lock &lock,
				       const critical_command &expected,
				       std::vector<flatfile_authority_operation> *writes,
				       std::string *error)
{
	if (!writes)
		return flatfile_player_domain_result::invalid;
	bool acknowledged = false;
	const auto checked =
		flatfile_artifact_delivery_acknowledged(root, lock, expected, &acknowledged, error);
	if (checked != flatfile_player_domain_result::ok || acknowledged)
		return checked;
	artifact_guild_delivery_ids ids;
	if (load_artifact_pending(root, &ids, error) != flatfile_player_domain_result::ok)
		return flatfile_player_domain_result::invalid;
	domain_operation receipt;
	critical_command command;
	const auto loaded =
		load_artifact_delivery(root, expected.operation_id, &receipt, &command, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	ids.erase(std::lower_bound(ids.begin(), ids.end(), expected.operation_id.bytes));
	receipt.result_code = artifact_delivery_acked;
	flatfile_authority_operation index, proof;
	if (!encode_artifact_pending(ids, &index) || !encode_receipt(receipt, &proof))
		return flatfile_player_domain_result::invalid;
	writes->push_back(std::move(index));
	writes->push_back(std::move(proof));
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result
flatfile_player_domain_establish(const std::string &root,
				 const flatfile_player_domain_record &record, std::string *error)
{
	return establish(root, record, true, error);
}

flatfile_player_domain_result flatfile_player_domain_establish_initial_player(
	const std::string &root, const flatfile_player_domain_record &record, std::string *error)
{
	return establish(root, record, false, error);
}

flatfile_player_domain_result flatfile_player_domain_restore_recover(const std::string &root,
								     std::string *error)
{
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	const auto recovered = recover_authority(root, authority, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	artifact_guild_delivery_ids pending_ids;
	const auto pending_loaded = load_artifact_pending(root, &pending_ids, error);
	if (pending_loaded != flatfile_player_domain_result::ok &&
	    pending_loaded != flatfile_player_domain_result::not_found)
		return pending_loaded;
	std::error_code ec;
	std::filesystem::directory_iterator current(domains_directory(root), ec), end;
	if (ec == std::errc::no_such_file_or_directory)
		return flatfile_player_domain_result::ok;
	for (; !ec && current != end; current.increment(ec))
	{
		const auto name = current->path().filename().string();
		if (name.starts_with("stone-") && name.ends_with(".claim"))
		{
			const auto key = name.substr(6, name.size() - 12);
			uint64_t uid = 0;
			const auto parsed =
				std::from_chars(key.data(), key.data() + key.size(), uid);
			domain_operation receipt;
			zone_touch_result result;
			if (parsed.ec != std::errc{} || parsed.ptr != key.data() + key.size() ||
			    !uid || name != "stone-" + std::to_string(uid) + ".claim" ||
			    load_receipt_file(root, name, &receipt, error) !=
				    flatfile_player_domain_result::ok ||
			    receipt.result_code ||
			    !zone_touch_command_decode_result(receipt.result.data(),
							      receipt.result_size, &result) ||
			    result.stone_uid != uid ||
			    !critical_operation_id_equal(result.parent_operation,
							 receipt.operation_id))
				return flatfile_player_domain_result::invalid;
			continue;
		}
		if (name.starts_with("zone-") && name.ends_with(".state"))
		{
			const auto key = name.substr(5, name.size() - 11);
			uint32_t number = 0;
			const auto parsed =
				std::from_chars(key.data(), key.data() + key.size(), number);
			flatfile_zone_touch_state state;
			if (parsed.ec != std::errc{} || parsed.ptr != key.data() + key.size() ||
			    !number || name != "zone-" + std::to_string(number) + ".state" ||
			    load_zone_state(root, number, &state, error) !=
				    flatfile_player_domain_result::ok)
				return flatfile_player_domain_result::invalid;
			continue;
		}
		if (!name.starts_with("command-") || !name.ends_with(".receipt"))
			continue;
		constexpr size_t prefix = sizeof("command-") - 1;
		constexpr size_t suffix = sizeof(".receipt") - 1;
		constexpr size_t hex_size = CRITICAL_COMMAND_ID_HEX_SIZE - 1;
		critical_operation_id operation;
		if (name.size() != prefix + hex_size + suffix ||
		    !critical_operation_id_from_hex(name.substr(prefix, hex_size).c_str(),
						    &operation) ||
		    name != receipt_filename(operation))
			return flatfile_player_domain_result::invalid;
		domain_operation receipt;
		const auto retained = load_receipt(root, operation, &receipt, error);
		if (retained != flatfile_player_domain_result::ok)
			return retained == flatfile_player_domain_result::io_error ?
				       retained :
				       flatfile_player_domain_result::invalid;
		if ((receipt.result_code & 0xffff0000U) == artifact_delivery_pending)
		{
			critical_command child;
			const auto checked =
				load_artifact_delivery(root, operation, &receipt, &child, error);
			if (checked != flatfile_player_domain_result::ok)
				return checked;
			const bool indexed = std::binary_search(pending_ids.begin(),
								pending_ids.end(), operation.bytes);
			if (indexed != (receipt.result_code == artifact_delivery_pending))
				return flatfile_player_domain_result::invalid;
		}
	}
	if (ec)
		return flatfile_player_domain_result::io_error;
	if (pending_loaded == flatfile_player_domain_result::ok)
	{
		std::vector<critical_command> commands;
		return flatfile_artifact_deliveries_list(root, authority, &commands, error);
	}
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result flatfile_player_domain_load(const std::string &root, int32_t pid,
							  const std::string &account_name,
							  int8_t racewar,
							  flatfile_player_domain_record *record,
							  std::string *error)
{
	std::string account;
	if (!record || pid <= 0 || !canonical_account(account_name, &account))
		return flatfile_player_domain_result::invalid;
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	try
	{
		const auto recovered = recover_authority(root, authority, error);
		if (recovered != flatfile_player_domain_result::ok)
			return recovered;
		flatfile_player_domain_record loaded;
		const auto player_loaded = load_player(root, pid, &loaded, error);
		if (player_loaded != flatfile_player_domain_result::ok)
			return player_loaded;
		if (loaded.account_name != account || loaded.racewar != racewar)
			return flatfile_player_domain_result::conflict;
		bank_record bank;
		const auto bank_loaded = load_bank(root, account, racewar, &bank, error);
		if (bank_loaded != flatfile_player_domain_result::ok)
			return bank_loaded;
		loaded.domains.bank = bank.balances;
		loaded.domains.bank_revision = bank.revision;
		*record = std::move(loaded);
		return flatfile_player_domain_result::ok;
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_player_domain_result::io_error;
	}
}

flatfile_player_domain_result flatfile_player_domain_prepare_saved_balances(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	flatfile_saved_balances &balances, flatfile_authority_operation *operation,
	std::string *error)
{
	if (!operation || !pid || !lock.matches(root))
		return flatfile_player_domain_result::invalid;
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	player_authority player;
	const auto loaded = load_player_authority(root, pid, &player, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	// A terminal capture may outlive its character. Keep its other state even
	// when a committed trade has already advanced the saved wallet.
	if (balances.wallet_revision < player.record.domains.wallet_revision)
	{
		balances.wallet = player.record.domains.wallet;
		balances.wallet_revision = player.record.domains.wallet_revision;
	}
	size_t unpaid = 0;
	const auto compacted =
		compact_receipts(root, &player, balances.divine_boon_delivery_seq, &unpaid, error);
	if (compacted != flatfile_player_domain_result::ok)
		return compacted;
	player.record.domains.wallet = balances.wallet;
	player.record.domains.wallet_revision = balances.wallet_revision;
	player.record.domains.epics = balances.epics;
	player.record.domains.frags = balances.frags;
	player.record.domains.old_frags = balances.old_frags;
	*operation = {};
	operation->filename = player_filename(pid);
	return encode_player_authority(player, &operation->bytes) ?
		       flatfile_player_domain_result::ok :
		       flatfile_player_domain_result::invalid;
}

flatfile_player_domain_result flatfile_player_domain_prepare_bank_delta(
	const std::string &root, const flatfile_authority_lock &lock,
	const std::string &account_name, int8_t racewar, const std::array<int64_t, 4> &delta,
	flatfile_authority_operation *operation, std::string *error)
{
	std::string account;
	if (!operation || !lock.matches(root) || !canonical_account(account_name, &account))
		return flatfile_player_domain_result::invalid;
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	bank_record bank;
	const auto loaded = load_bank(root, account, racewar, &bank, error);
	if (loaded == flatfile_player_domain_result::not_found)
	{
		bank.account_name = account;
		bank.racewar = racewar;
	}
	else if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	for (size_t index = 0; index < bank.balances.size(); ++index)
	{
		// A debit the record cannot cover is refused rather than wrapped.
		if (delta[index] < 0 && bank.balances[index] < static_cast<uint64_t>(-delta[index]))
			return flatfile_player_domain_result::conflict;
		bank.balances[index] += delta[index];
	}
	++bank.revision;
	*operation = {};
	operation->filename = bank_filename(account, racewar);
	return encode_bank_record(bank, &operation->bytes) ? flatfile_player_domain_result::ok :
							     flatfile_player_domain_result::invalid;
}

flatfile_player_domain_result flatfile_player_domain_prepare_base_stat(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	uint8_t stat_index, bool apply_increment, flatfile_base_stat_mutation *mutation,
	unsigned int *result_code, std::string *error)
{
	if (!mutation || !result_code || !pid ||
	    stat_index >= player_load_domain_state{}.base_stats.size() || !lock.matches(root))
		return flatfile_player_domain_result::invalid;
	*mutation = {};
	*result_code = 0;
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	player_authority player;
	const auto loaded = load_player_authority(root, pid, &player, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	mutation->stat_value = player.record.domains.base_stats[stat_index];
	mutation->stat_revision = player.record.domains.base_stat_revision;
	if (!mutation->stat_revision)
	{
		*result_code = ENODATA;
		return flatfile_player_domain_result::ok;
	}
	if (!apply_increment)
		return flatfile_player_domain_result::ok;
	if (mutation->stat_value >= 100)
	{
		*result_code = EALREADY;
		return flatfile_player_domain_result::ok;
	}
	if (mutation->stat_value < 0 ||
	    mutation->stat_revision == std::numeric_limits<uint64_t>::max())
	{
		*result_code = ERANGE;
		return flatfile_player_domain_result::ok;
	}
	++mutation->stat_value;
	++mutation->stat_revision;
	player.record.domains.base_stats[stat_index] = mutation->stat_value;
	player.record.domains.base_stat_revision = mutation->stat_revision;
	try
	{
		mutation->after_image.filename = player_filename(pid);
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_player_domain_result::io_error;
	}
	if (!encode_player_authority(player, &mutation->after_image.bytes))
		return flatfile_player_domain_result::invalid;
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result
flatfile_player_domain_prepare_remove(const std::string &root, const flatfile_authority_lock &lock,
				      uint32_t pid, flatfile_authority_operation *operation,
				      std::string *error)
{
	if (!operation || !pid || !lock.matches(root))
		return flatfile_player_domain_result::invalid;
	*operation = {};
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	flatfile_player_domain_record record;
	const auto loaded = load_player(root, pid, &record, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	operation->store = flatfile_authority_store::domains;
	operation->kind = flatfile_authority_operation_kind::remove;
	operation->filename = player_filename(pid);
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result flatfile_player_domain_prepare_account_remove(
	const std::string &root, const flatfile_authority_lock &lock,
	const std::string &account_name, std::vector<flatfile_authority_operation> *operations,
	std::string *error)
{
	std::string account;
	if (!operations || !lock.matches(root) || !canonical_account(account_name, &account))
		return flatfile_player_domain_result::invalid;
	operations->clear();
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	try
	{
		/* Account banks use the complete RACEWAR_* range (none through neutral). */
		for (int racewar = 0; racewar <= 4; ++racewar)
		{
			bank_record bank;
			const auto loaded = load_bank(root, account, static_cast<int8_t>(racewar),
						      &bank, error);
			if (loaded == flatfile_player_domain_result::not_found)
				continue;
			if (loaded != flatfile_player_domain_result::ok)
				return loaded;
			operations->push_back(
				{ flatfile_authority_store::domains,
				  flatfile_authority_operation_kind::remove,
				  bank_filename(account, static_cast<int8_t>(racewar)),
				  {} });
		}
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_player_domain_result::io_error;
	}
	return flatfile_player_domain_result::ok;
}

critical_apply_result apply_epic_command(const std::string &root, const critical_command &command)
{
	epic_command_payload payload = {};
	std::vector<uint8_t> encoded_command;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	if (root.empty() || !critical_command_valid(command) ||
	    !epic_command_decode_payload(command, &payload) ||
	    critical_command_encode(command, &encoded_command) != critical_command_codec_result::ok)
		return { critical_apply_outcome::terminal_failure, 0, EINVAL };
	SHA256(encoded_command.data(), encoded_command.size(), digest.data());
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock lock;
	std::string error;
	if (!lock.acquire(root, &error))
		return { critical_apply_outcome::retryable_failure, 0, EIO };
	const auto recovered = recover_authority(root, lock, &error);
	if (recovered != flatfile_player_domain_result::ok)
		return { recovered == flatfile_player_domain_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 recovered == flatfile_player_domain_result::io_error ? EIO :
											EILSEQ) };
	domain_operation receipt;
	const auto retained = load_receipt(root, command.operation_id, &receipt, &error);
	if (retained == flatfile_player_domain_result::ok)
		return replay_receipt(command, digest, receipt);
	if (retained != flatfile_player_domain_result::not_found)
		return { retained == flatfile_player_domain_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 retained == flatfile_player_domain_result::io_error ? EIO :
										       EILSEQ) };
	player_authority authority;
	const auto loaded = load_player_authority(root, payload.pid, &authority, &error);
	if (loaded != flatfile_player_domain_result::ok)
		return { loaded == flatfile_player_domain_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 loaded == flatfile_player_domain_result::not_found ? ENOENT :
				 loaded == flatfile_player_domain_result::io_error  ? EIO :
										      EILSEQ) };
	for (const domain_operation &operation : authority.operations)
		if (critical_operation_id_equal(operation.operation_id, command.operation_id))
		{
			if (CRYPTO_memcmp(operation.command_digest.data(), digest.data(),
					  digest.size()))
				return { critical_apply_outcome::terminal_failure,
					 authority.record.domains.epic_revision, EEXIST };
			epic_command_result replay = {};
			if (!epic_command_decode_result(operation.result.data(),
							operation.result_size, &replay))
				return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
			critical_apply_result result = {
				operation.result_code ? critical_apply_outcome::terminal_failure :
							critical_apply_outcome::already_applied,
				replay.revision, operation.result_code
			};
			result.result_size = operation.result_size;
			std::copy_n(operation.result.begin(), operation.result_size,
				    result.result_payload.begin());
			return result;
		}
	// Epic points are memory's: the submit changed the balance and the player's save
	// writes it. The command is only recorded.
	const epic_command_result epic_result = { authority.record.domains.epics,
						  authority.record.domains.epic_revision,
						  payload.delta };
	const unsigned int result_code = 0;
	std::array<uint8_t, EPIC_RESULT_PAYLOAD_BYTES> encoded_result = {};
	if (!epic_command_encode_result(epic_result, &encoded_result))
		return { critical_apply_outcome::terminal_failure, epic_result.revision, EBADMSG };
	domain_operation operation = {};
	operation.operation_id = command.operation_id;
	operation.command_digest = digest;
	operation.result_code = result_code;
	operation.result_size = encoded_result.size();
	std::copy(encoded_result.begin(), encoded_result.end(), operation.result.begin());
	flatfile_authority_operation write;
	if (!encode_receipt(operation, &write))
		return { critical_apply_outcome::terminal_failure, epic_result.revision, EBADMSG };
	if (!flatfile_atomic_write(domains_directory(root), write.filename, write.bytes, &error))
		return { critical_apply_outcome::retryable_failure, epic_result.revision, EIO };
	critical_apply_result result = { result_code ? critical_apply_outcome::terminal_failure :
						       critical_apply_outcome::applied,
					 epic_result.revision, result_code };
	result.result_size = encoded_result.size();
	std::copy(encoded_result.begin(), encoded_result.end(), result.result_payload.begin());
	return result;
}

critical_apply_result apply_combat_outcome_command(const std::string &root,
						   const critical_command &command)
{
	static_assert(COMBAT_OUTCOME_RESULT_BYTES <= FLATFILE_LEGACY_DOMAIN_RESULT_MAX_BYTES);
	combat_outcome_payload payload = {};
	std::vector<uint8_t> encoded_command;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	if (root.empty() || !critical_command_valid(command) ||
	    !combat_outcome_command_decode_payload(command, &payload) ||
	    critical_command_encode(command, &encoded_command) != critical_command_codec_result::ok)
		return { critical_apply_outcome::terminal_failure, 0, EINVAL };
	SHA256(encoded_command.data(), encoded_command.size(), digest.data());
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock lock;
	std::string error;
	if (!lock.acquire(root, &error))
		return { critical_apply_outcome::retryable_failure, 0, EIO };
	const auto recovered = recover_authority(root, lock, &error);
	if (recovered != flatfile_player_domain_result::ok)
		return { recovered == flatfile_player_domain_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 recovered == flatfile_player_domain_result::io_error ? EIO :
											EILSEQ) };
	domain_operation receipt;
	const auto retained = load_receipt(root, command.operation_id, &receipt, &error);
	if (retained == flatfile_player_domain_result::ok)
		return replay_receipt(command, digest, receipt);
	if (retained != flatfile_player_domain_result::not_found)
		return { retained == flatfile_player_domain_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 retained == flatfile_player_domain_result::io_error ? EIO :
										       EILSEQ) };
	std::vector<player_authority> players;
	try
	{
		players.reserve(payload.participant_count);
	}
	catch (const std::bad_alloc &)
	{
		return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
	}
	for (size_t index = 0; index < payload.participant_count; ++index)
	{
		player_authority player;
		const auto loaded = load_player_authority(root, payload.participants[index].pid,
							  &player, &error);
		if (loaded != flatfile_player_domain_result::ok)
			return { loaded == flatfile_player_domain_result::io_error ?
					 critical_apply_outcome::retryable_failure :
					 critical_apply_outcome::terminal_failure,
				 0,
				 static_cast<unsigned int>(
					 loaded == flatfile_player_domain_result::not_found ?
						 ENOENT :
					 loaded == flatfile_player_domain_result::io_error ?
						 EIO :
						 EILSEQ) };
		try
		{
			players.push_back(std::move(player));
		}
		catch (const std::bad_alloc &)
		{
			return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
		}
	}
	const domain_operation *replay_operation = nullptr;
	size_t replay_count = 0;
	for (const player_authority &player : players)
		for (const domain_operation &operation : player.operations)
			if (critical_operation_id_equal(operation.operation_id,
							command.operation_id))
			{
				if (CRYPTO_memcmp(operation.command_digest.data(), digest.data(),
						  digest.size()))
					return { critical_apply_outcome::terminal_failure, 0,
						 EEXIST };
				replay_operation = &operation;
				++replay_count;
			}
	if (replay_operation)
	{
		combat_outcome_result replay = {};
		if (replay_count != players.size() ||
		    !combat_outcome_command_decode_result(replay_operation->result.data(),
							  replay_operation->result_size, &replay))
			return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
		uint64_t durable_revision = 0;
		for (const auto &entry : replay.participants)
			durable_revision = std::max({ durable_revision, entry.frag_revision,
						      entry.epic_revision, entry.wallet_revision,
						      entry.bank_revision });
		critical_apply_result result = { replay_operation->result_code ?
							 critical_apply_outcome::terminal_failure :
							 critical_apply_outcome::already_applied,
						 durable_revision, replay_operation->result_code };
		result.result_size = replay_operation->result_size;
		std::copy_n(replay_operation->result.begin(), replay_operation->result_size,
			    result.result_payload.begin());
		return result;
	}
	// Frags, epic points and blood money are memory's: the submit changed them and the
	// players' saves write them. The outcome is only recorded.
	std::vector<player_authority> candidates;
	try
	{
		candidates = players;
		for (size_t index = 0; index < candidates.size(); ++index)
		{
			uint64_t paid = 0;
			const bool prepared = payload.participants[index].flags &
					      COMBAT_PARTICIPANT_DIVINE_EPIC;
			if (prepared)
			{
				player_snapshot snapshot;
				const auto read = flatfile_player_snapshot_read(
					root, candidates[index].record.pid, &snapshot, &error);
				if (read == flatfile_player_load_result::io_error)
					return { critical_apply_outcome::retryable_failure, 0,
						 EIO };
				if ((read != flatfile_player_load_result::ok &&
				     read != flatfile_player_load_result::not_found) ||
				    (read == flatfile_player_load_result::ok &&
				     !player_snapshot_divine_delivery_sequence(snapshot, &paid)))
					return { critical_apply_outcome::terminal_failure, 0,
						 EILSEQ };
			}
			size_t unpaid = 0;
			const auto compacted =
				compact_receipts(root, &candidates[index], paid, &unpaid, &error);
			if (compacted != flatfile_player_domain_result::ok)
				return {
					compacted == flatfile_player_domain_result::io_error ?
						critical_apply_outcome::retryable_failure :
						critical_apply_outcome::terminal_failure,
					0,
					static_cast<unsigned int>(
						compacted == flatfile_player_domain_result::io_error ?
							EIO :
							EILSEQ)
				};
			if (prepared && unpaid >= DIVINE_EPIC_RECOVERY_MAX)
				return { critical_apply_outcome::retryable_failure, 0, ENOSPC };
		}
	}
	catch (const std::bad_alloc &)
	{
		return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
	}
	const unsigned int result_code = 0;
	combat_outcome_result combat_result = {};
	std::array<uint8_t, SHA256_DIGEST_LENGTH> event_digest = {};
	SHA256(command.operation_id.bytes.data(), command.operation_id.bytes.size(),
	       event_digest.data());
	for (size_t byte = 0; byte < sizeof(combat_result.event_id); ++byte)
		combat_result.event_id |= static_cast<uint64_t>(event_digest[byte]) << (byte * 8);
	if (!combat_result.event_id)
		combat_result.event_id = 1;
	combat_result.participant_count = payload.participant_count;
	combat_result.victim_pid = payload.victim_pid;
	combat_result.prepared_at = payload.prepared_at;
	combat_result.artifact_intents = payload.artifact_intents;
	for (size_t index = 0; index < payload.participant_count; ++index)
	{
		const auto &domains = players[index].record.domains;
		combat_result.participants[index] = { .pid = payload.participants[index].pid,
						      .frags = domains.frags,
						      .epics = domains.epics,
						      .wallet_value = -1,
						      .bank = {},
						      .frag_revision = domains.frag_revision,
						      .epic_revision = domains.epic_revision,
						      .wallet_revision = 0,
						      .bank_revision = 0 };
		if (payload.participants[index].flags & COMBAT_PARTICIPANT_DIVINE_EPIC)
		{
			auto &entry = combat_result.participants[index];
			if (domains.epic_revision == UINT64_MAX ||
			    domains.epics > INT64_MAX - payload.participants[index].epic_delta)
				return { critical_apply_outcome::terminal_failure, 0, ERANGE };
			for (const auto &prior : players[index].operations)
			{
				divine_epic_delivery delivery;
				if (!operation_delivery(prior, entry.pid, &delivery))
					return { critical_apply_outcome::terminal_failure, 0,
						 EILSEQ };
				entry.epic_delivery_previous =
					std::max(entry.epic_delivery_previous, delivery.sequence);
			}
			entry.epic_revision = ++candidates[index].record.domains.epic_revision;
			entry.epic_delivery_delta = payload.participants[index].epic_delta;
			entry.epic_boon_id = payload.participants[index].epic_boon_id;
			entry.epic_base = payload.participants[index].epic_base;
			entry.epic_spill_blood = payload.participants[index].epic_spill_blood;
			entry.epic_delivery_flags =
				payload.participants[index].flags &
				(COMBAT_PARTICIPANT_DIVINE_EPIC | COMBAT_PARTICIPANT_SPILL_BLOOD);
		}
	}
	std::array<uint8_t, COMBAT_OUTCOME_RESULT_BYTES> encoded_result = {};
	const size_t encoded_size = combat_outcome_result_size(combat_result);
	if (!combat_outcome_command_encode_result(combat_result, &encoded_result))
		return { critical_apply_outcome::terminal_failure, 0, EBADMSG };
	domain_operation operation = {};
	operation.operation_id = command.operation_id;
	operation.command_digest = digest;
	operation.result_code = result_code;
	operation.result_size = encoded_size;
	std::copy(encoded_result.begin(), encoded_result.end(), operation.result.begin());
	try
	{
		for (size_t index = 0; index < candidates.size(); ++index)
			if (payload.participants[index].flags & COMBAT_PARTICIPANT_DIVINE_EPIC)
				candidates[index].operations.push_back(operation);
	}
	catch (const std::bad_alloc &)
	{
		return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
	}
	std::vector<flatfile_authority_operation> operations;
	try
	{
		flatfile_authority_operation receipt_write;
		if (!encode_receipt(operation, &receipt_write))
			return { critical_apply_outcome::terminal_failure, 0, EBADMSG };
		operations.push_back(std::move(receipt_write));
		if (payload.artifact_intents)
		{
			const auto prepared = flatfile_artifact_deliveries_prepare(
				root, lock, payload.artifact_deliveries, &operations, &error);
			if (prepared != flatfile_player_domain_result::ok)
				return { critical_apply_outcome::retryable_failure, 0,
					 static_cast<unsigned int>(
						 prepared == flatfile_player_domain_result::conflict ?
							 ENOSPC :
							 EIO) };
		}
		for (const auto &candidate : candidates)
		{
			flatfile_authority_operation write;
			write.filename = player_filename(candidate.record.pid);
			if (!encode_player_authority(candidate, &write.bytes))
				return { critical_apply_outcome::terminal_failure, 0, ENOSPC };
			operations.push_back(std::move(write));
		}
	}
	catch (const std::bad_alloc &)
	{
		return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
	}
	const auto committed =
		flatfile_authority_transaction_commit_operations(root, lock, operations, &error);
	if (committed != flatfile_authority_transaction_result::ok)
		return { committed == flatfile_authority_transaction_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 committed == flatfile_authority_transaction_result::io_error ?
					 EIO :
					 EILSEQ) };
	uint64_t durable_revision = 0;
	for (const player_authority &candidate : candidates)
		durable_revision =
			std::max({ durable_revision, candidate.record.domains.frag_revision,
				   candidate.record.domains.epic_revision,
				   candidate.record.domains.wallet_revision });
	critical_apply_result result = { result_code ? critical_apply_outcome::terminal_failure :
						       critical_apply_outcome::applied,
					 durable_revision, result_code };
	result.result_size = encoded_size;
	std::copy(encoded_result.begin(), encoded_result.end(), result.result_payload.begin());
	return result;
}

// Claim, full prepared receipt, latest zone state and all issued recipient
// revisions share the existing authority journal. Wallet/epic snapshots remain
// the balance authority and checkpoint publication separately, exactly once.
critical_apply_result apply_zone_touch_command(const std::string &root,
					       const critical_command &command)
try
{
	zone_touch_payload payload;
	std::vector<uint8_t> encoded;
	if (!critical_command_valid(command) ||
	    !zone_touch_command_decode_payload(command, &payload) || !payload.prepared_delivery ||
	    !payload.stone_uid ||
	    critical_command_encode(command, &encoded) != critical_command_codec_result::ok)
		return { critical_apply_outcome::terminal_failure, 0, EINVAL };
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock lock;
	std::string error;
	if (!lock.acquire(root, &error))
		return { critical_apply_outcome::retryable_failure, 0, EIO };
	const auto recovered_authority = recover_authority(root, lock, &error);
	if (recovered_authority != flatfile_player_domain_result::ok)
		return { recovered_authority == flatfile_player_domain_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0,
			 static_cast<unsigned int>(
				 recovered_authority == flatfile_player_domain_result::io_error ?
					 EIO :
					 EILSEQ) };
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest;
	SHA256(encoded.data(), encoded.size(), digest.data());
	domain_operation receipt;
	auto loaded = load_receipt(root, command.operation_id, &receipt, &error);
	if (loaded == flatfile_player_domain_result::ok)
		return replay_receipt(command, digest, receipt);
	if (loaded != flatfile_player_domain_result::not_found)
		return { loaded == flatfile_player_domain_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0, EILSEQ };
	zone_touch_result result(payload);
	result.parent_operation = command.operation_id;
	const std::string claim_name = "stone-" + std::to_string(payload.stone_uid) + ".claim";
	loaded = load_receipt_file(root, claim_name, &receipt, &error);
	const bool recovered = loaded == flatfile_player_domain_result::ok;
	if (recovered)
	{
		if (!zone_touch_command_decode_result(receipt.result.data(), receipt.result_size,
						      &result) ||
		    result.stone_uid != payload.stone_uid || !result.prepared_delivery)
			return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
		result.recovered_claim = true;
	}
	else if (loaded != flatfile_player_domain_result::not_found)
		return { loaded == flatfile_player_domain_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0, EILSEQ };
	std::vector<player_authority> players;
	if (!recovered)
		for (size_t i = 0; i < payload.group_size; ++i)
		{
			player_authority player;
			loaded = load_player_authority(root, payload.participant_pids[i], &player,
						       &error);
			if (loaded != flatfile_player_domain_result::ok)
				return { loaded == flatfile_player_domain_result::io_error ?
						 critical_apply_outcome::retryable_failure :
						 critical_apply_outcome::terminal_failure,
					 0, ENOENT };
			player_snapshot snapshot;
			uint64_t paid = 0;
			const auto saved = flatfile_player_snapshot_read(root, player.record.pid,
									 &snapshot, &error);
			if (saved != flatfile_player_load_result::ok ||
			    !player_snapshot_divine_delivery_sequence(snapshot, &paid))
				return { saved == flatfile_player_load_result::io_error ?
						 critical_apply_outcome::retryable_failure :
						 critical_apply_outcome::terminal_failure,
					 0, EILSEQ };
			size_t unpaid = 0;
			loaded = compact_receipts(root, &player, paid, &unpaid, &error);
			if (loaded != flatfile_player_domain_result::ok)
				return { loaded == flatfile_player_domain_result::io_error ?
						 critical_apply_outcome::retryable_failure :
						 critical_apply_outcome::terminal_failure,
					 0, EILSEQ };
			if (unpaid >= DIVINE_EPIC_RECOVERY_MAX)
				return { critical_apply_outcome::retryable_failure, 0, ENOSPC };
			for (const auto &prior : player.operations)
			{
				divine_epic_delivery delivery;
				if (!operation_delivery(prior, player.record.pid, &delivery))
					return { critical_apply_outcome::terminal_failure, 0,
						 EILSEQ };
				result.previous[i] =
					std::max(result.previous[i], delivery.sequence);
			}
			auto &domains = player.record.domains;
			if (domains.epic_revision == UINT64_MAX ||
			    domains.epics > INT64_MAX - payload.awards[i].amount)
				return { critical_apply_outcome::terminal_failure, 0, ERANGE };
			result.balances[i] = domains.epics + payload.awards[i].amount;
			result.revisions[i] = ++domains.epic_revision;
			players.push_back(std::move(player));
		}
	std::array<uint8_t, ZONE_TOUCH_RESULT_BYTES> bytes;
	if (!zone_touch_command_encode_result(result, &bytes))
		return { critical_apply_outcome::terminal_failure, 0, EBADMSG };
	receipt = {};
	receipt.operation_id = command.operation_id;
	receipt.command_digest = digest;
	receipt.result_size = bytes.size();
	std::copy(bytes.begin(), bytes.end(), receipt.result.begin());
	std::vector<flatfile_authority_operation> operations;
	flatfile_authority_operation write;
	if (!encode_receipt(receipt, &write))
		return { critical_apply_outcome::terminal_failure, 0, EBADMSG };
	operations.push_back(write);
	if (!recovered)
	{
		write.filename = claim_name;
		operations.push_back(write);
		if (payload.artifact_intents)
		{
			const auto prepared = flatfile_artifact_deliveries_prepare(
				root, lock, payload.artifact_deliveries, &operations, &error);
			if (prepared != flatfile_player_domain_result::ok)
				return { critical_apply_outcome::retryable_failure, 0,
					 static_cast<unsigned int>(
						 prepared == flatfile_player_domain_result::conflict ?
							 ENOSPC :
							 EIO) };
		}
		if (payload.record_zone)
		{
			flatfile_zone_touch_state state;
			loaded = load_zone_state(root, payload.zone_number, &state, &error);
			if (loaded != flatfile_player_domain_result::ok &&
			    loaded != flatfile_player_domain_result::not_found)
				return { loaded == flatfile_player_domain_result::io_error ?
						 critical_apply_outcome::retryable_failure :
						 critical_apply_outcome::terminal_failure,
					 0, EILSEQ };
			state.number = payload.zone_number;
			state.alignment =
				std::clamp(state.alignment + payload.alignment_delta, -5, 5);
			state.last_touch = payload.touched_at;
			encoder fields;
			fields.number(state.number);
			fields.number(state.alignment);
			fields.number(state.last_touch);
			write.filename = "zone-" + std::to_string(state.number) + ".state";
			if (!encode_file(zone_magic, fields.bytes, 1, &write.bytes))
				return { critical_apply_outcome::terminal_failure, 0, EBADMSG };
			operations.push_back(write);
		}
		for (auto &player : players)
		{
			player.operations.push_back(receipt);
			if (payload.zone_number && payload.zone_number <= INT32_MAX)
			{
				auto &zones = player.record.completed_epic_zones;
				const auto number = static_cast<int32_t>(payload.zone_number);
				auto position =
					std::lower_bound(zones.begin(), zones.end(), number);
				if (position == zones.end() || *position != number)
				{
					if (zones.size() >= PLAYER_LOAD_COMPLETED_ZONE_MAX)
						return { critical_apply_outcome::terminal_failure,
							 0, ENOSPC };
					zones.insert(position, number);
				}
			}
			write.filename = player_filename(player.record.pid);
			if (!encode_player_authority(player, &write.bytes))
				return { critical_apply_outcome::terminal_failure, 0, ENOSPC };
			operations.push_back(write);
		}
	}
	const auto committed =
		flatfile_authority_transaction_commit_operations(root, lock, operations, &error);
	if (committed != flatfile_authority_transaction_result::ok)
		return { committed == flatfile_authority_transaction_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0, EIO };
	auto applied = replay_receipt(command, digest, receipt);
	applied.outcome = critical_apply_outcome::applied;
	return applied;
}
catch (const std::bad_alloc &)
{
	return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
}

critical_apply_result flatfile_player_domain_apply(const std::string &root,
						   const critical_command &command)
{
	if (command.type == critical_command_type::zone)
		return apply_zone_touch_command(root, command);
	if (command.type == critical_command_type::epic)
		return apply_epic_command(root, command);
	if (command.type == critical_command_type::combat_outcome)
		return apply_combat_outcome_command(root, command);
	return { critical_apply_outcome::terminal_failure, 0, ENOTSUP };
}

static flatfile_player_domain_result
collect_divine_epics(const player_authority &player, uint32_t pid, uint64_t after,
		     std::vector<divine_epic_delivery> *deliveries)
{
	std::vector<divine_epic_delivery> pending;
	for (const auto &operation : player.operations)
	{
		divine_epic_delivery delivery;
		if (!operation_delivery(operation, pid, &delivery))
			return flatfile_player_domain_result::invalid;
		if (delivery.sequence > after)
			pending.push_back(delivery);
	}
	std::sort(pending.begin(), pending.end(), [](const auto &left, const auto &right)
		  { return left.sequence < right.sequence; });
	*deliveries = std::move(pending);
	return flatfile_player_domain_result::ok;
}

flatfile_player_domain_result
flatfile_player_domain_pending_divine_epics(const std::string &root, uint32_t pid, uint64_t after,
					    std::vector<divine_epic_delivery> *deliveries,
					    std::string *error)
{
	if (!deliveries || !pid)
		return flatfile_player_domain_result::invalid;
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	player_authority player;
	const auto loaded = load_player_authority(root, pid, &player, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	return collect_divine_epics(player, pid, after, deliveries);
}

flatfile_player_domain_result
flatfile_player_domain_load_checkpoint(const std::string &root,
				       const flatfile_identity_record &identity,
				       player_load_result *result, std::string *error)
try
{
	std::string account;
	if (!result || identity.pid <= 0 || !canonical_account(identity.account, &account))
		return flatfile_player_domain_result::invalid;
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	const auto recovered = recover_authority(root, lock, error);
	if (recovered != flatfile_player_domain_result::ok)
		return recovered;
	// All native snapshot writes own authority. Read without a player lock,
	// preserving the snapshot writer's player->authority acquisition order.
	const auto snapshot =
		flatfile_player_snapshot_read(root, identity.pid, &result->snapshot, error);
	if (snapshot != flatfile_player_load_result::ok)
	{
		result->failed_component = "snapshot";
		return snapshot == flatfile_player_load_result::not_found ?
			       flatfile_player_domain_result::not_found :
		       snapshot == flatfile_player_load_result::io_error ?
			       flatfile_player_domain_result::io_error :
			       flatfile_player_domain_result::invalid;
	}
	player_authority player;
	const auto loaded = load_player_authority(root, identity.pid, &player, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	if (player.record.account_name != account)
		return flatfile_player_domain_result::conflict;
	bool race_found = false;
	for (const auto &field : result->snapshot.status_integers)
		if (field.field == player_status_field::racewar)
		{
			if (race_found || (field.is_unsigned && field.unsigned_value > INT8_MAX))
				return flatfile_player_domain_result::invalid;
			const int64_t race = field.is_unsigned ?
						     static_cast<int64_t>(field.unsigned_value) :
						     field.signed_value;
			if (race != player.record.racewar ||
			    (identity.racewar && race != identity.racewar))
			{
				result->failed_component = "domain_identity";
				return flatfile_player_domain_result::conflict;
			}
			race_found = true;
		}
	if (!race_found)
		return flatfile_player_domain_result::invalid;
	bank_record bank;
	const auto bank_loaded = load_bank(root, account, player.record.racewar, &bank, error);
	if (bank_loaded != flatfile_player_domain_result::ok)
		return bank_loaded;
	result->domains = player.record.domains;
	result->snapshot.wallet_revision = result->domains.wallet_revision;
	result->domains.bank = bank.balances;
	result->domains.bank_revision = bank.revision;
	result->recent_pvp_deaths = player.record.recent_pvp_deaths;
	result->completed_epic_zones = player.record.completed_epic_zones;
	result->read_components = PLAYER_LOAD_SESSION04_READS;
	uint64_t after = 0;
	if (!player_snapshot_divine_delivery_sequence(result->snapshot, &after))
		return flatfile_player_domain_result::invalid;
	const auto receipts =
		collect_divine_epics(player, identity.pid, after, &result->divine_epic_deliveries);
	if (receipts != flatfile_player_domain_result::ok)
		result->failed_component = "divine_epic_delivery";
	return receipts;
}
catch (const std::bad_alloc &)
{
	return flatfile_player_domain_result::io_error;
}

flatfile_player_domain_result flatfile_zone_touch_load(const std::string &root, uint32_t number,
						       flatfile_zone_touch_state *state,
						       std::string *error)
{
	if (!state || !number)
		return flatfile_player_domain_result::invalid;
	std::lock_guard<std::mutex> guard(domain_mutex);
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	const auto recovered = recover_authority(root, lock, error);
	return recovered == flatfile_player_domain_result::ok ?
		       load_zone_state(root, number, state, error) :
		       recovered;
}

flatfile_player_domain_result flatfile_player_domain_prepare_wallet(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	uint64_t expected_revision, uint64_t expected_account,
	const std::array<uint64_t, 4> &wallet,
	std::vector<flatfile_authority_operation> *operations, std::string *error)
{
	if (!operations || !pid || !lock.matches(root) || !expected_account ||
	    expected_revision == UINT64_MAX)
		return flatfile_player_domain_result::invalid;
	player_authority player;
	const auto loaded = load_player_authority(root, pid, &player, error);
	if (loaded != flatfile_player_domain_result::ok)
		return loaded;
	critical_entity_key account;
	if (!currency_account_key(player.record.account_name.c_str(), 0, &account) ||
	    account.id != expected_account ||
	    player.record.domains.wallet_revision > expected_revision)
		return flatfile_player_domain_result::conflict;
	player_snapshot snapshot;
	const auto read =
		flatfile_player_snapshot_read(root, static_cast<int32_t>(pid), &snapshot, error);
	if (read != flatfile_player_load_result::ok)
		return read == flatfile_player_load_result::io_error ?
			       flatfile_player_domain_result::io_error :
		       read == flatfile_player_load_result::not_found ?
			       flatfile_player_domain_result::not_found :
			       flatfile_player_domain_result::invalid;
	if (snapshot.wallet_revision > expected_revision)
		return flatfile_player_domain_result::conflict;
	unsigned found = 0;
	for (auto &field : snapshot.status_integers)
		if (field.field >= player_status_field::copper &&
		    field.field <= player_status_field::platinum)
		{
			const auto index = static_cast<unsigned>(field.field) -
					   static_cast<unsigned>(player_status_field::copper);
			if ((found & (1U << index)) || wallet[index] > INT64_MAX)
				return flatfile_player_domain_result::invalid;
			found |= 1U << index;
			field = { field.field, 0, wallet[index], true };
		}
	if (found != 15)
		return flatfile_player_domain_result::invalid;
	snapshot.wallet_revision = expected_revision + 1;
	player.record.domains.wallet = wallet;
	player.record.domains.wallet_revision = snapshot.wallet_revision;
	flatfile_authority_operation saved, domain;
	saved.store = flatfile_authority_store::players;
	saved.filename = flatfile_player_snapshot_file::player_filename(static_cast<int32_t>(pid));
	domain.filename = player_filename(pid);
	if (!flatfile_player_snapshot_encode_file(&snapshot, &saved.bytes) ||
	    !encode_player_authority(player, &domain.bytes))
		return flatfile_player_domain_result::invalid;
	auto prepared = *operations;
	prepared.push_back(std::move(saved));
	prepared.push_back(std::move(domain));
	*operations = std::move(prepared);
	return flatfile_player_domain_result::ok;
}
