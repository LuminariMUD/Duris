#include "combat_intent_recovery_checks.h"
#include "flatfile/flatfile_store.h"
#include "combat/frag_cap_repository.h"
#include <chrono>
#include "flatfile/flatfile_player_domain_repository.h"
#include "combat/combat_outcome_command.h"
#include "world/epic_command.h"

#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <openssl/sha.h>
#include <string>

namespace fs = std::filesystem;

static void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}

static uint32_t read_u32(const std::vector<uint8_t> &bytes, size_t *offset)
{
	require(*offset + 4 <= bytes.size(), "legacy player-domain conversion overflowed");
	uint32_t value = 0;
	for (size_t byte = 0; byte < 4; ++byte)
		value |= static_cast<uint32_t>(bytes[(*offset)++]) << (byte * 8);
	return value;
}

static void write_u32(std::vector<uint8_t> *bytes, size_t offset, uint32_t value)
{
	for (size_t byte = 0; byte < 4; ++byte)
		(*bytes)[offset + byte] = static_cast<uint8_t>(value >> (byte * 8));
}

template <typename T> static void append(std::vector<uint8_t> *bytes, T value)
{
	for (size_t byte = 0; byte < sizeof(T); ++byte)
		bytes->push_back(static_cast<uint8_t>(static_cast<uint64_t>(value) >> (byte * 8)));
}

static std::vector<uint8_t> file_bytes(const fs::path &path)
{
	std::ifstream input(path, std::ios::binary);
	return { std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>() };
}

static void write_player_domain_fixture(const fs::path &path, std::vector<uint8_t> file,
					const std::vector<uint8_t> &payload)
{
	write_u32(&file, 12, payload.size());
	file.resize(56);
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(payload.data(), payload.size(), digest.data());
	std::copy(digest.begin(), digest.end(), file.begin() + 24);
	file.insert(file.end(), payload.begin(), payload.end());
	std::ofstream output(path, std::ios::binary | std::ios::trunc);
	output.write(reinterpret_cast<const char *>(file.data()), file.size());
	require(output.good(), "could not write player domain fixture");
}

static void convert_player_domain_to_v2(const fs::path &path)
{
	std::ifstream input(path, std::ios::binary);
	std::vector<uint8_t> file((std::istreambuf_iterator<char>(input)),
				  std::istreambuf_iterator<char>());
	require(file.size() >= 56, "player domain was too short for legacy conversion");
	std::vector<uint8_t> payload(file.begin() + 56, file.end());
	size_t offset = 4;
	const uint32_t account_size = read_u32(payload, &offset);
	offset += account_size + 1 + 24 + 32 + 24;
	const uint32_t death_count = read_u32(payload, &offset);
	offset += static_cast<size_t>(death_count) * 8;
	const uint32_t zone_count = read_u32(payload, &offset);
	offset += static_cast<size_t>(zone_count) * 4;
	require(offset + 28 <= payload.size(), "player stat authority was not in v3 payload");
	payload.erase(payload.begin() + offset, payload.begin() + offset + 28);
	write_u32(&file, 8, 2);
	write_player_domain_fixture(path, file, payload);
}

// Retained results are opaque during load; command replay decodes their payload.
static void append_retained_result(const fs::path &path, uint16_t result_size)
{
	std::ifstream input(path, std::ios::binary);
	std::vector<uint8_t> file((std::istreambuf_iterator<char>(input)),
				  std::istreambuf_iterator<char>());
	require(file.size() >= 60, "retained-result fixture was truncated");
	std::vector<uint8_t> payload(file.begin() + 56, file.end());
	size_t count_offset = payload.size() - 4;
	require(read_u32(payload, &count_offset) == 0,
		"retained-result fixture already contained operations");
	write_u32(&payload, payload.size() - 4, 1);
	critical_operation_id operation = {};
	operation.bytes[0] = 0x7f;
	payload.insert(payload.end(), operation.bytes.begin(), operation.bytes.end());
	payload.insert(payload.end(), SHA256_DIGEST_LENGTH, 0x5a);
	payload.insert(payload.end(), 4, 0); // Successful result code.
	payload.push_back(static_cast<uint8_t>(result_size));
	payload.push_back(static_cast<uint8_t>(result_size >> 8));
	payload.insert(payload.end(), result_size, 0xa5);
	write_player_domain_fixture(path, file, payload);
}

// Fill an otherwise empty authority with checkpointed receipts to reproduce a
// permanent full-store failure without thousands of disk transactions.
static void fill_receipt_history(const fs::path &path)
{
	std::vector<uint8_t> file = file_bytes(path);
	require(file.size() >= 60, "receipt capacity fixture was truncated");
	std::vector<uint8_t> payload(file.begin() + 56, file.end());
	size_t offset = payload.size() - 4;
	require(read_u32(payload, &offset) == 0,
		"receipt capacity fixture must start without history");
	write_u32(&payload, payload.size() - 4, 512);
	for (uint16_t index = 0; index < 512; ++index)
	{
		critical_operation_id id = {};
		id.bytes[0] = 0x7e;
		id.bytes[1] = static_cast<uint8_t>(index);
		id.bytes[2] = static_cast<uint8_t>(index >> 8);
		payload.insert(payload.end(), id.bytes.begin(), id.bytes.end());
		payload.insert(payload.end(), SHA256_DIGEST_LENGTH, 0x5a);
		append<uint32_t>(&payload, 0); // Result code.
		append<uint16_t>(&payload, 0); // Empty historical result.
	}
	write_player_domain_fixture(path, file, payload);
}

static flatfile_player_domain_record baseline(int32_t pid)
{
	flatfile_player_domain_record record;
	record.pid = pid;
	record.account_name = "Account-One";
	record.racewar = 1;
	record.domains.wallet = { 1, 2, 3, 4 };
	record.domains.bank = { 5, 6, 7, 8 };
	record.domains.epics = 9;
	record.domains.frags = 10;
	record.domains.old_frags = 11;
	record.domains.base_stat_revision = 1;
	record.domains.base_stats = { 50, 51, 52, 53, 54, 55, 56, 57, 58, 59 };
	record.recent_pvp_deaths = { 3000, 2000, 1000 };
	record.completed_epic_zones = { 7, 12, 99 };
	return record;
}

static critical_command epic(int64_t delta, uint64_t expected_revision, uint8_t operation,
			     uint16_t flags = 0)
{
	critical_operation_id operation_id = {};
	operation_id.bytes[0] = operation;
	epic_command_payload payload = { 42, delta, epic_reason_type::quest_award, flags, 77 };
	critical_command command;
	require(epic_command_build(&command, operation_id, payload, expected_revision,
				   critical_source_site::command,
				   critical_deadline_class::interactive),
		"could not build epic command");
	command.accepted_at_usec = 1;
	require(critical_command_normalize(&command), "could not normalize epic command");
	return command;
}

static critical_command combat(uint8_t operation, uint64_t killer_frag_revision = 0,
			       int64_t killer_frag_delta = 5)
{
	critical_operation_id operation_id = {};
	operation_id.bytes[0] = operation;
	combat_outcome_payload payload = {};
	payload.victim_pid = 43;
	payload.room_vnum = 100;
	strcpy(payload.room_name.data(), "Arena");
	payload.participant_count = 2;
	payload.participants[0].pid = 42;
	payload.participants[0].role = combat_participant_role::killer;
	payload.participants[0].level = 50;
	payload.participants[0].racewar = 1;
	payload.participants[0].frag_delta = killer_frag_delta;
	payload.participants[0].epic_delta = 2;
	payload.participants[0].wallet_delta_copper = 11;
	payload.participants[0].expected_frag_revision = killer_frag_revision;
	payload.participants[0].expected_epic_revision = 1;
	payload.participants[0].expected_wallet_revision = 2;
	payload.participants[0].expected_bank_revision = 3;
	strcpy(payload.participants[0].account_name.data(), "account-one");
	strcpy(payload.participants[0].description.data(), "killer");
	payload.participants[1].pid = 43;
	payload.participants[1].role = combat_participant_role::victim;
	payload.participants[1].level = 45;
	payload.participants[1].racewar = 1;
	payload.participants[1].frag_delta = -2;
	payload.participants[1].epic_delta = 3;
	payload.participants[1].wallet_delta_copper = 7;
	payload.participants[1].expected_frag_revision = 0;
	payload.participants[1].expected_epic_revision = 0;
	payload.participants[1].expected_wallet_revision = 0;
	payload.participants[1].expected_bank_revision = 3;
	strcpy(payload.participants[1].account_name.data(), "account-one");
	strcpy(payload.participants[1].description.data(), "victim");
	critical_command command;
	require(combat_outcome_command_build(&command, operation_id, payload),
		"could not build combat outcome command");
	command.accepted_at_usec = 1;
	require(critical_command_normalize(&command), "could not normalize combat command");
	return command;
}

int main(int argc, char **argv)
{
	require(argc == 2, "state root argument required");
	const fs::path root = argv[1];
	const fs::path domains = root / "domains";
	fs::create_directories(domains);
	fs::create_directories(root / "players");
	fs::permissions(root / "players", fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(domains, fs::perms::owner_all, fs::perm_options::replace);
	const int64_t cap_start = std::chrono::duration_cast<std::chrono::microseconds>(
					  std::chrono::system_clock::now().time_since_epoch())
					  .count();
	frag_cap_state cap;
	require(frag_cap_flatfile_adopt(root.string(), 25, cap_start, &cap) ==
			frag_cap_store_result::ok,
		"cap activation failed");

	std::string error;
	flatfile_player_domain_record source = baseline(42);
	require(flatfile_player_domain_establish(root.string(), source, &error) ==
			flatfile_player_domain_result::ok,
		"domain baseline failed: " + error);
	flatfile_player_domain_record loaded;
	require(flatfile_player_domain_load(root.string(), 42, "account-one", 1, &loaded, &error) ==
				flatfile_player_domain_result::ok &&
			loaded.account_name == "account-one" &&
			loaded.domains.wallet == source.domains.wallet &&
			loaded.domains.bank == source.domains.bank &&
			loaded.domains.bank_revision == 1 && loaded.domains.epics == 9 &&
			loaded.domains.frags == 10 && loaded.domains.base_stat_revision == 1 &&
			loaded.domains.base_stats == source.domains.base_stats &&
			loaded.recent_pvp_deaths == source.recent_pvp_deaths &&
			loaded.completed_epic_zones == source.completed_epic_zones,
		"domain baseline did not round trip: " + error);
	require(flatfile_player_domain_establish(root.string(), source, &error) ==
			flatfile_player_domain_result::ok,
		"exact domain baseline retry was not idempotent");
	flatfile_player_domain_record bank_retry_conflict = source;
	bank_retry_conflict.domains.bank[0] = 99;
	require(flatfile_player_domain_establish(root.string(), bank_retry_conflict, &error) ==
			flatfile_player_domain_result::conflict,
		"conflicting bank on player baseline retry was accepted");
	source.domains.epics = 10;
	require(flatfile_player_domain_establish(root.string(), source, &error) ==
			flatfile_player_domain_result::conflict,
		"conflicting player domain baseline was accepted");

	flatfile_player_domain_record sibling = baseline(43);
	require(flatfile_player_domain_establish(root.string(), sibling, &error) ==
			flatfile_player_domain_result::ok,
		"second character could not share the account bank");
	flatfile_player_domain_record creation = baseline(45);
	creation.domains.bank = {};
	require(flatfile_player_domain_establish_initial_player(root.string(), creation, &error) ==
			flatfile_player_domain_result::ok,
		"new character could not reuse an existing authoritative account bank");
	require(flatfile_player_domain_load(root.string(), 45, "account-one", 1, &loaded, &error) ==
				flatfile_player_domain_result::ok &&
			loaded.domains.bank == sibling.domains.bank,
		"new character did not load the existing authoritative account bank");
	flatfile_player_domain_record conflict = baseline(44);
	conflict.domains.bank[0] = 99;
	require(flatfile_player_domain_establish(root.string(), conflict, &error) ==
			flatfile_player_domain_result::conflict,
		"conflicting shared bank baseline was accepted");
	require(flatfile_player_domain_load(root.string(), 42, "wrong-account", 1, &loaded,
					    &error) == flatfile_player_domain_result::conflict,
		"account mismatch was accepted during domain load");

	// Epic points are memory's: the command is only recorded, and the player's save
	// writes the balance.
	flatfile_player_domain_record before_epic;
	require(flatfile_player_domain_load(root.string(), 42, "account-one", 1, &before_epic,
					    &error) == flatfile_player_domain_result::ok,
		"could not read the balance before an epic command");
	critical_command epic_gain = epic(5, 0, 1);
	critical_apply_result applied = flatfile_player_domain_apply(root.string(), epic_gain);
	epic_command_result epic_result = {};
	require(applied.outcome == critical_apply_outcome::applied && applied.error_code == 0 &&
			epic_command_decode_result(applied.result_payload.data(),
						   applied.result_size, &epic_result) &&
			epic_result.delta == 5,
		"epic command was not recorded");
	require(flatfile_player_domain_load(root.string(), 42, "account-one", 1, &loaded, &error) ==
				flatfile_player_domain_result::ok &&
			loaded.domains.epics == before_epic.domains.epics &&
			loaded.domains.epic_revision == before_epic.domains.epic_revision,
		"an epic command changed the saved balance");
	applied = flatfile_player_domain_apply(root.string(), epic_gain);
	require(applied.outcome == critical_apply_outcome::already_applied &&
			epic_command_decode_result(applied.result_payload.data(),
						   applied.result_size, &epic_result) &&
			epic_result.delta == 5,
		"epic command replay did not return its original result");
	require(flatfile_player_domain_apply(root.string(), epic(6, 1, 1)).error_code == EEXIST,
		"conflicting epic operation ID was accepted");

	// Frags, epic points and blood money are memory's: the outcome is only recorded, and
	// leaves every saved balance alone.
	flatfile_player_domain_record killer_before, victim_before;
	require(flatfile_player_domain_load(root.string(), 42, "account-one", 1, &killer_before,
					    &error) == flatfile_player_domain_result::ok &&
			flatfile_player_domain_load(root.string(), 43, "account-one", 1,
						    &victim_before,
						    &error) == flatfile_player_domain_result::ok,
		"could not read the balances before a combat outcome");
	critical_command combat_outcome = combat(20);
	applied = flatfile_player_domain_apply(root.string(), combat_outcome);
	combat_outcome_result combat_result = {};
	require(applied.outcome == critical_apply_outcome::applied &&
			combat_outcome_command_decode_result(applied.result_payload.data(),
							     applied.result_size, &combat_result) &&
			combat_result.participant_count == 2 && combat_result.event_id != 0,
		"combat outcome was not recorded");
	for (const auto &[pid, before] :
	     { std::pair{ 42, &killer_before }, std::pair{ 43, &victim_before } })
		require(flatfile_player_domain_load(root.string(), pid, "account-one", 1, &loaded,
						    &error) == flatfile_player_domain_result::ok &&
				loaded.domains.frags == before->domains.frags &&
				loaded.domains.epics == before->domains.epics &&
				loaded.domains.wallet == before->domains.wallet &&
				loaded.domains.bank_revision == before->domains.bank_revision,
			"a combat outcome changed a saved balance");
	applied = flatfile_player_domain_apply(root.string(), combat_outcome);
	require(applied.outcome == critical_apply_outcome::already_applied &&
			combat_outcome_command_decode_result(applied.result_payload.data(),
							     applied.result_size, &combat_result) &&
			combat_result.participant_count == 2,
		"combat command did not replay its original result");
	require(flatfile_player_domain_apply(root.string(), combat(20, 1, 6)).error_code == EEXIST,
		"conflicting combat operation ID was accepted");
	require(flatfile_player_domain_apply(root.string(), combat(21)).outcome ==
			critical_apply_outcome::applied,
		"a second combat outcome was fenced by the first");

	convert_player_domain_to_v2(domains / "player-45.domain");
	require(flatfile_player_domain_load(root.string(), 45, "account-one", 1, &loaded, &error) ==
				flatfile_player_domain_result::ok &&
			loaded.domains.base_stat_revision == 0 &&
			loaded.domains.base_stats == std::array<int16_t, 10>{},
		"legacy v2 player domain did not remain readable and snapshot-owned");

	static_assert(CRITICAL_COMPLETION_RESULT_MAX_BYTES > 2048);
	for (uint32_t version : { 2U, 3U, 4U })
	{
		const uint16_t maximum = version < 4 ? 2048 : 8192;
		for (uint16_t result_size : { maximum, static_cast<uint16_t>(maximum + 1) })
		{
			const int32_t pid = 100 + version * 2 + (result_size - maximum);
			const std::string label = "v" + std::to_string(version) +
						  " retained result " + std::to_string(result_size);
			flatfile_player_domain_record receipt_fixture = baseline(pid);
			receipt_fixture.domains.bank = {};
			require(flatfile_player_domain_establish_initial_player(
					root.string(), receipt_fixture, &error) ==
					flatfile_player_domain_result::ok,
				label + " baseline failed: " + error);
			const fs::path fixture =
				domains / ("player-" + std::to_string(pid) + ".domain");
			if (version == 2)
				convert_player_domain_to_v2(fixture);
			else if (version == 3)
			{
				auto bytes = file_bytes(fixture);
				write_u32(&bytes, 8, 3);
				write_player_domain_fixture(fixture, bytes,
							    { bytes.begin() + 56, bytes.end() });
			}
			append_retained_result(fixture, result_size);
			const auto expected = result_size == maximum ?
						      flatfile_player_domain_result::ok :
						      flatfile_player_domain_result::invalid;
			require(flatfile_player_domain_load(root.string(), pid, "account-one", 1,
							    &loaded, &error) == expected,
				label + " did not enforce its native format's result bound: " +
					error);
		}
	}

	// An older server's currency command wrote the player and the account bank in one
	// intent; a crash before it finished leaves both files stale. The next domain
	// operation (this load) writes both and clears the intent.
	{
		const fs::path player_file = domains / "player-42.domain";
		const fs::path bank_file = domains / "bank-account-one-1.domain";
		const fs::path intent_file = domains / ".player-domain-transaction";
		flatfile_player_domain_record before;
		require(flatfile_player_domain_load(root.string(), 42, "account-one", 1, &before,
						    &error) == flatfile_player_domain_result::ok,
			"could not read the player before the older intent");
		const std::vector<uint8_t> player_bytes = file_bytes(player_file);
		const std::vector<uint8_t> bank_bytes = file_bytes(bank_file);
		require(!player_bytes.empty() && !bank_bytes.empty(),
			"the player and bank files were not where the intent expects them");
		const std::string account = "account-one";
		std::vector<uint8_t> payload;
		append<uint16_t>(&payload, 1);
		append<uint16_t>(&payload, 1);
		append<int32_t>(&payload, 42);
		append<uint32_t>(&payload, player_bytes.size());
		payload.insert(payload.end(), player_bytes.begin(), player_bytes.end());
		append<uint32_t>(&payload, account.size());
		payload.insert(payload.end(), account.begin(), account.end());
		append<int8_t>(&payload, 1);
		append<uint32_t>(&payload, bank_bytes.size());
		payload.insert(payload.end(), bank_bytes.begin(), bank_bytes.end());
		std::vector<uint8_t> intent = { 'D', 'U', 'R', 'T', 'X', 'N', 0, 0 };
		append<uint32_t>(&intent, 3);
		append<uint32_t>(&intent, payload.size());
		append<uint64_t>(&intent, 1);
		std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
		SHA256(payload.data(), payload.size(), digest.data());
		intent.insert(intent.end(), digest.begin(), digest.end());
		intent.insert(intent.end(), payload.begin(), payload.end());
		{
			std::ofstream output(intent_file, std::ios::binary | std::ios::trunc);
			output.write(reinterpret_cast<const char *>(intent.data()), intent.size());
			require(output.good(), "could not write the older intent");
		}
		fs::permissions(intent_file, fs::perms::owner_read | fs::perms::owner_write,
				fs::perm_options::replace);
		fs::remove(player_file);
		fs::remove(bank_file);
		require(flatfile_player_domain_load(root.string(), 42, "account-one", 1, &loaded,
						    &error) == flatfile_player_domain_result::ok &&
				loaded.domains.wallet == before.domains.wallet &&
				loaded.domains.bank == before.domains.bank &&
				loaded.domains.bank_revision == before.domains.bank_revision &&
				file_bytes(player_file) == player_bytes &&
				file_bytes(bank_file) == bank_bytes && !fs::exists(intent_file),
			"an older server's player and bank intent was not finished: " + error);
	}

	// Prepared awards record owed credit and ordered receipts, without changing
	// the saved balance. A journal interruption cannot drop or duplicate them.
	{
		auto prepared = combat(70);
		combat_outcome_payload payload;
		require(combat_outcome_command_decode_payload(prepared, &payload),
			"decode fixture");
		payload.prepared_at = 150;
		payload.participants[0].flags = COMBAT_PARTICIPANT_IN_ROOM |
						COMBAT_PARTICIPANT_DIVINE_EPIC;
		payload.participants[0].epic_delta = 150;
		payload.participants[0].epic_boon_id = 7;
		payload.participants[0].epic_base = 100;
		payload.participants[0].wallet_delta_copper = 0;
		payload.participants[1].racewar = 2;
		payload.participants[1].epic_delta = 0;
		payload.participants[1].wallet_delta_copper = 0;
		require(combat_outcome_command_build(&prepared, prepared.operation_id, payload),
			"build prepared fixture");
		prepared.accepted_at_usec = 1;
		const auto before = loaded.domains.epics;
		require(setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL", "1", 1) ==
				0,
			"set interruption");
		const auto interrupted = flatfile_player_domain_apply(root.string(), prepared);
		require(interrupted.outcome == critical_apply_outcome::retryable_failure,
			"prepared fault did not interrupt after the journal: outcome=" +
				std::to_string(static_cast<unsigned>(interrupted.outcome)) +
				", error=" + std::to_string(interrupted.error_code));
		require(unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL") == 0,
			"clear interruption");
		std::vector<divine_epic_delivery> receipts;
		const auto recovered = flatfile_player_domain_pending_divine_epics(
			root.string(), 42, 0, &receipts, &error);
		require(recovered == flatfile_player_domain_result::ok && receipts.size() == 1 &&
				receipts[0].sequence == 1 && receipts[0].previous == 0 &&
				receipts[0].amount == 150,
			"prepared journal recovery lost its receipt: result=" +
				std::to_string(static_cast<unsigned>(recovered)) +
				", count=" + std::to_string(receipts.size()) + ", error=" + error);
		require(flatfile_player_domain_apply(root.string(), prepared).outcome ==
				critical_apply_outcome::already_applied,
			"prepared command was applied twice after recovery");
		prepared.operation_id.bytes[0] = 71;
		require(flatfile_player_domain_apply(root.string(), prepared).outcome ==
				critical_apply_outcome::applied,
			"second prepared command failed");
		require(flatfile_player_domain_pending_divine_epics(root.string(), 42, 0, &receipts,
								    &error) ==
					flatfile_player_domain_result::ok &&
				receipts.size() == 2 && receipts[1].sequence == 2 &&
				receipts[1].previous == 1,
			"several awards before a checkpoint reused a sequence");
		require(flatfile_player_domain_pending_divine_epics(root.string(), 42, 1, &receipts,
								    &error) ==
					flatfile_player_domain_result::ok &&
				receipts.size() == 1 && receipts[0].sequence == 2,
			"saved delivery watermark did not filter paid receipts");
		require(flatfile_player_domain_load(root.string(), 42, "account-one", 1, &loaded,
						    &error) == flatfile_player_domain_result::ok &&
				loaded.domains.epics == before,
			"preparation changed the saved balance before recipient publication");

		// An old parent may exist only in player records. Compaction must copy
		// its exact retry identity before the recipient checkpoint drops it.
		auto first = prepared;
		first.operation_id.bytes[0] = 70;
		const auto first_result = flatfile_player_domain_apply(root.string(), first);
		char first_hex[33];
		require(critical_operation_id_to_hex(first.operation_id, first_hex,
						     sizeof(first_hex)),
			"receipt name");
		const auto first_path =
			domains / (std::string("command-") + first_hex + ".receipt");
		fs::remove(first_path);
		flatfile_saved_balances balances;
		balances.wallet = loaded.domains.wallet;
		balances.frags = loaded.domains.frags;
		balances.old_frags = loaded.domains.old_frags;
		balances.epics = before + 300;
		balances.divine_boon_delivery_seq = 2;
		auto checkpoint = [&]()
		{
			flatfile_authority_lock lock;
			require(lock.acquire(root.string(), &error), "checkpoint lock");
			flatfile_authority_operation write;
			require(flatfile_player_domain_prepare_saved_balances(
					root.string(), lock, 42, balances, &write, &error) ==
					flatfile_player_domain_result::ok,
				"compact checkpoint: " + error);
			return flatfile_authority_transaction_commit_operations(root.string(), lock,
										{ write }, &error);
		};
		setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_OPERATION", "1", 1);
		require(checkpoint() == flatfile_authority_transaction_result::io_error,
			"compaction fault");
		unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_OPERATION");
		require(flatfile_player_domain_pending_divine_epics(root.string(), 42, 2, &receipts,
								    &error) ==
					flatfile_player_domain_result::ok &&
				receipts.empty(),
			"compaction recovery");
		const auto replay = flatfile_player_domain_apply(root.string(), first);
		require(replay.outcome == critical_apply_outcome::already_applied &&
				replay.result_size == first_result.result_size &&
				replay.result_payload == first_result.result_payload,
			"archived legacy parent changed on replay");

		// Exercise more than the former lifetime ceiling through both ordinary
		// command families and repeated prepared/checkpoint cycles.
		for (uint32_t index = 1; index <= 520; ++index)
		{
			for (auto ordinary : { combat(80), epic(5, 0, 81) })
			{
				for (size_t byte = 0; byte < 4; ++byte)
					ordinary.operation_id.bytes[4 + byte] =
						static_cast<uint8_t>(index >> (byte * 8));
				require(flatfile_player_domain_apply(root.string(), ordinary)
							.outcome == critical_apply_outcome::applied,
					"ordinary receipt lifetime ceiling");
			}
			prepared.operation_id.bytes[0] = 82;
			for (size_t byte = 0; byte < 4; ++byte)
				prepared.operation_id.bytes[4 + byte] =
					static_cast<uint8_t>(index >> (byte * 8));
			require(flatfile_player_domain_apply(root.string(), prepared).outcome ==
					critical_apply_outcome::applied,
				"prepared receipt lifetime ceiling");
			require(flatfile_player_domain_pending_divine_epics(
					root.string(), 42, balances.divine_boon_delivery_seq,
					&receipts, &error) == flatfile_player_domain_result::ok &&
					receipts.size() == 1 &&
					receipts[0].previous == balances.divine_boon_delivery_seq &&
					receipts[0].sequence ==
						balances.divine_boon_delivery_seq + 1,
				"compaction broke predecessor continuity");
			balances.epics += receipts[0].amount;
			balances.divine_boon_delivery_seq = receipts[0].sequence;
			require(checkpoint() == flatfile_authority_transaction_result::ok,
				"prepared checkpoint lifetime ceiling");
		}
		require(fs::file_size(domains / "player-42.domain") < 8192,
			"paid detail grew without bound");
		require(flatfile_player_domain_apply(root.string(), first).outcome ==
				critical_apply_outcome::already_applied,
			"old retry forgotten after compaction");
		first.operation_id = prepared.operation_id;
		first.accepted_at_usec = 2;
		require(flatfile_player_domain_apply(root.string(), first).error_code == EEXIST,
			"receipt identity collision accepted");
		require(flatfile_player_domain_restore_recover(root.string(), &error) ==
				flatfile_player_domain_result::ok,
			"restore qualification rejected valid permanent receipts");
		{
			std::fstream file(first_path,
					  std::ios::in | std::ios::out | std::ios::binary);
			file.seekp(-1, std::ios::end);
			file.put(0x5a);
		}
		first.operation_id.bytes = {};
		first.operation_id.bytes[0] = 70;
		require(flatfile_player_domain_apply(root.string(), first).error_code == EILSEQ,
			"corrupt permanent receipt accepted");
		require(flatfile_player_domain_restore_recover(root.string(), &error) ==
				flatfile_player_domain_result::invalid,
			"restore qualification ignored a corrupt permanent receipt");

		// Unpaid awards stop at the recovery limit and wait for a retry. A full
		// record whose parents lack permanent receipts archives every one of them.
		std::vector<critical_command> owed;
		std::vector<critical_apply_result> owed_results;
		prepared.operation_id.bytes[0] = 83;
		critical_apply_result full = {};
		for (uint32_t index = 1; index <= DIVINE_EPIC_RECOVERY_MAX + 1; ++index)
		{
			for (size_t byte = 0; byte < 4; ++byte)
				prepared.operation_id.bytes[4 + byte] =
					static_cast<uint8_t>(index >> (byte * 8));
			full = flatfile_player_domain_apply(root.string(), prepared);
			if (full.outcome != critical_apply_outcome::applied)
				break;
			owed.push_back(prepared);
			owed_results.push_back(full);
		}
		require(full.outcome == critical_apply_outcome::retryable_failure &&
				full.error_code == ENOSPC,
			"unpaid awards passed the recovery limit");
		// Drop the permanent copies, except the newest award's: it stays in the
		// record as the delivery edge, and only legacy parents lack a receipt.
		for (size_t index = 0; index + 1 < owed.size(); ++index)
		{
			char hex[CRITICAL_COMMAND_ID_HEX_SIZE];
			require(critical_operation_id_to_hex(owed[index].operation_id, hex,
							     sizeof(hex)),
				"owed receipt name");
			require(fs::remove(domains / (std::string("command-") + hex + ".receipt")),
				"owed receipt was not permanent");
		}
		// Without a saved snapshot the paid edge still counts toward the limit.
		require(flatfile_player_domain_pending_divine_epics(root.string(), 42, 0, &receipts,
								    &error) ==
					flatfile_player_domain_result::ok &&
				receipts.size() == DIVINE_EPIC_RECOVERY_MAX,
			"recovery limit did not match the pending award list");
		require(flatfile_player_domain_pending_divine_epics(
				root.string(), 42, balances.divine_boon_delivery_seq, &receipts,
				&error) == flatfile_player_domain_result::ok &&
				receipts.size() == owed.size(),
			"owed awards were not all pending");
		for (const auto &receipt : receipts)
			balances.epics += receipt.amount;
		balances.divine_boon_delivery_seq = receipts.back().sequence;
		require(checkpoint() == flatfile_authority_transaction_result::ok,
			"full record checkpoint");
		require(fs::file_size(domains / "player-42.domain") < 8192,
			"full record was not compacted");
		for (size_t index = 0; index < owed.size(); ++index)
		{
			const auto replay =
				flatfile_player_domain_apply(root.string(), owed[index]);
			require(replay.outcome == critical_apply_outcome::already_applied &&
					replay.result_payload == owed_results[index].result_payload,
				"full record compaction lost an exact retry: index=" +
					std::to_string(index) + ", outcome=" +
					std::to_string(static_cast<unsigned>(replay.outcome)) +
					", error=" + std::to_string(replay.error_code) +
					", size=" + std::to_string(replay.result_size) + "/" +
					std::to_string(owed_results[index].result_size));
		}
		require(flatfile_player_domain_apply(root.string(), prepared).outcome ==
				critical_apply_outcome::applied,
			"paid checkpoint did not admit the waiting award");
		// Receipts began at the current format; an older header is not one.
		{
			char hex[CRITICAL_COMMAND_ID_HEX_SIZE];
			require(critical_operation_id_to_hex(prepared.operation_id, hex,
							     sizeof(hex)),
				"version receipt name");
			std::fstream file(domains / (std::string("command-") + hex + ".receipt"),
					  std::ios::in | std::ios::out | std::ios::binary);
			file.seekp(8);
			file.put(2);
		}
		require(flatfile_player_domain_apply(root.string(), prepared).error_code == EILSEQ,
			"older-format permanent receipt accepted");
	}

	// A prepared receipt must be rejected before persistence if a recipient's
	// saved balance cannot accept its credit.
	{
		flatfile_player_domain_record near_maximum = baseline(80);
		near_maximum.domains.bank = {};
		near_maximum.domains.epics = std::numeric_limits<int64_t>::max() - 100;
		require(flatfile_player_domain_establish_initial_player(root.string(), near_maximum,
									&error) ==
				flatfile_player_domain_result::ok,
			"near-maximum recipient baseline failed");
		auto counterpart = baseline(81);
		counterpart.domains.bank = {};
		counterpart.racewar = 2;
		require(flatfile_player_domain_establish_initial_player(root.string(), counterpart,
									&error) ==
				flatfile_player_domain_result::ok,
			"overflow counterpart baseline failed");
		auto prepared = combat(85);
		combat_outcome_payload payload;
		require(combat_outcome_command_decode_payload(prepared, &payload),
			"overflow fixture decode failed");
		payload.victim_pid = 81;
		payload.prepared_at = 150;
		payload.participants[0].pid = 80;
		payload.participants[0].flags = COMBAT_PARTICIPANT_IN_ROOM |
						COMBAT_PARTICIPANT_DIVINE_EPIC;
		payload.participants[0].epic_delta = 150;
		payload.participants[0].epic_boon_id = 7;
		payload.participants[0].epic_base = 100;
		payload.participants[0].wallet_delta_copper = 0;
		payload.participants[1].pid = 81;
		payload.participants[1].racewar = 2;
		payload.participants[1].epic_delta = 0;
		payload.participants[1].wallet_delta_copper = 0;
		require(combat_outcome_command_build(&prepared, prepared.operation_id, payload),
			"overflow prepared fixture build failed");
		prepared.accepted_at_usec = 1;
		const auto result = flatfile_player_domain_apply(root.string(), prepared);
		require(result.outcome == critical_apply_outcome::terminal_failure &&
				result.error_code == ERANGE,
			"unpayable Divine receipt was recorded");
		std::vector<divine_epic_delivery> receipts;
		require(flatfile_player_domain_pending_divine_epics(root.string(), 80, 0, &receipts,
								    &error) ==
					flatfile_player_domain_result::ok &&
				receipts.empty(),
			"overflowing recipient acquired a durable receipt");
	}

	// Legacy full histories compact before admitting another ordinary command.
	{
		auto saturated = baseline(82);
		saturated.domains.bank = {};
		require(flatfile_player_domain_establish_initial_player(root.string(), saturated,
									&error) ==
				flatfile_player_domain_result::ok,
			"full-store recipient baseline failed");
		auto counterpart = baseline(83);
		counterpart.domains.bank = {};
		require(flatfile_player_domain_establish_initial_player(root.string(), counterpart,
									&error) ==
				flatfile_player_domain_result::ok,
			"full-store counterpart baseline failed");
		fill_receipt_history(domains / "player-82.domain");
		auto outcome = combat(86);
		combat_outcome_payload payload;
		require(combat_outcome_command_decode_payload(outcome, &payload),
			"full-store fixture decode failed");
		payload.victim_pid = 83;
		payload.participants[0].pid = 82;
		payload.participants[1].pid = 83;
		require(combat_outcome_command_build(&outcome, outcome.operation_id, payload),
			"full-store fixture build failed");
		outcome.accepted_at_usec = 1;
		const auto result = flatfile_player_domain_apply(root.string(), outcome);
		require(result.outcome == critical_apply_outcome::applied && !result.error_code,
			"full legacy history did not compact before ordinary combat");
		require(fs::file_size(domains / "player-82.domain") < 8192,
			"full legacy history remained embedded after compaction");
		const auto replay = flatfile_player_domain_apply(root.string(), outcome);
		require(replay.outcome == critical_apply_outcome::already_applied &&
				replay.result_payload == result.result_payload,
			"ordinary combat changed after full-history compaction");
	}

	// A full 20/20 result, including prepared awards, survives storage and replay.
	{
		combat_outcome_payload payload{};
		payload.victim_pid = 1020;
		payload.room_vnum = 22800;
		payload.killer_allies = 20;
		payload.prepared_at = 150;
		payload.artifact_intents = true;
		strcpy(payload.room_name.data(), "Full racewar groups");
		payload.participant_count = 40;
		for (size_t i = 0; i < 40; ++i)
		{
			auto record = baseline(1000 + i);
			record.domains.bank = {};
			record.racewar = i < 20 ? 1 : 2;
			require(flatfile_player_domain_establish_initial_player(root.string(),
										record, &error) ==
					flatfile_player_domain_result::ok,
				"full-group baseline failed");
			auto &entry = payload.participants[i];
			entry.pid = record.pid;
			entry.role = i < 20 ? combat_participant_role::killer_group :
					      combat_participant_role::victim_group;
			entry.level = 56;
			entry.racewar = record.racewar;
			entry.flags = COMBAT_PARTICIPANT_IN_ROOM;
			strcpy(entry.account_name.data(), "account-one");
			if (i < 20)
			{
				entry.flags |= COMBAT_PARTICIPANT_DIVINE_EPIC;
				entry.frag_delta = 5;
				entry.epic_delta = 150;
				entry.epic_boon_id = 7;
				entry.epic_base = 100;
			}
		}
		critical_operation_id id{};
		id.bytes[0] = 120;
		critical_command command;
		require(combat_outcome_command_build(&command, id, payload),
			"full-group build failed");
		command.accepted_at_usec = cap_start;
		std::vector<uint8_t> saved_cap;
		require(flatfile_read(domains.string(), "frag-cap.state", 1024, &saved_cap,
				      &error) == flatfile_read_result::ok,
			"cap backup failed");
		const auto first = check_combat_intent_recovery(
			command, [&](const auto &cmd)
			{ return flatfile_player_domain_apply(root.string(), cmd); },
			[&]
			{
				require(flatfile_atomic_write(domains.string(), "frag-cap.state",
							      { 0 }, &error),
					"corruption failed");
			},
			[&]
			{
				require(flatfile_atomic_write(domains.string(), "frag-cap.state",
							      saved_cap, &error),
					"repair failed");
			});
		combat_outcome_result result{};
		require(first.outcome == critical_apply_outcome::applied &&
				first.result_size == 8192 &&
				combat_outcome_command_decode_result(first.result_payload.data(),
								     first.result_size, &result) &&
				result.participant_count == 40 &&
				result.participants[39].pid == 1039,
			"full-group result was not stored intact");
		std::vector<divine_epic_delivery> deliveries;
		require(flatfile_player_domain_pending_divine_epics(root.string(), 1019, 0,
								    &deliveries, &error) ==
					flatfile_player_domain_result::ok &&
				deliveries.size() == 1 && deliveries[0].amount == 150,
			"large retained result lost a prepared award");
		const auto replay = flatfile_player_domain_apply(root.string(), command);
		require(replay.outcome == critical_apply_outcome::already_applied &&
				replay.result_size == first.result_size &&
				replay.result_payload == first.result_payload,
			"full-group replay changed its result");
		require(frag_cap_flatfile_load(root.string(), &cap) == frag_cap_store_result::ok &&
				cap.earned[0] == 100 && cap.earned[1] == 0 && cap.level == 31,
			"twenty ordinary five-point awards did not pool by faction");
		const auto partial = cap;
		require(flatfile_player_domain_apply(root.string(), command).outcome ==
					critical_apply_outcome::already_applied &&
				frag_cap_flatfile_load(root.string(), &cap) ==
					frag_cap_store_result::ok &&
				cap == partial,
			"combat replay duplicated cap credit");
		for (int pass = 0; pass < 3; ++pass)
		{
			id.bytes[0] = 121 + pass;
			require(combat_outcome_command_build(&command, id, payload),
				"cap contribution build failed");
			command.accepted_at_usec = cap_start;
			if (pass < 2)
			{
				const char *fault =
					pass == 0 ?
						"DURIS_FLATFILE_TEST_FAIL_BEFORE_AUTHORITY_COMMIT" :
						"DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL";
				require(setenv(fault, "1", 1) == 0, "fault setup failed");
				require(flatfile_player_domain_apply(root.string(), command)
							.outcome ==
						critical_apply_outcome::retryable_failure,
					"interrupted combat unexpectedly succeeded");
				require(unsetenv(fault) == 0, "fault cleanup failed");
				require(frag_cap_flatfile_load(root.string(), &cap) ==
							frag_cap_store_result::ok &&
						cap.earned[0] == (pass == 0 ? 100 : 300),
					"cap split from combat receipt on recovery");
			}
			const auto applied = flatfile_player_domain_apply(root.string(), command);
			require(applied.outcome ==
					(pass == 1 ? critical_apply_outcome::already_applied :
						     critical_apply_outcome::applied),
				"cap combat retry failed");
		}
		require(frag_cap_flatfile_load(root.string(), &cap) == frag_cap_store_result::ok &&
				cap.earned[0] == 400 && cap.level == 31,
			"four full-group events were not counted completely");
		const auto secured = cap;
		require(flatfile_player_domain_apply(root.string(), command).outcome ==
					critical_apply_outcome::already_applied &&
				frag_cap_flatfile_load(root.string(), &cap) ==
					frag_cap_store_result::ok &&
				cap == secured,
			"secured combat replay changed qualification");
		require(frag_cap_flatfile_tick(root.string(), cap.deadline) ==
					frag_cap_store_result::ok &&
				frag_cap_flatfile_load(root.string(), &cap) ==
					frag_cap_store_result::ok &&
				cap.level == 32 && cap.earned == (std::array<uint64_t, 2>{}),
			"qualified cap did not open on the durable timer");
	}

	const fs::path player = domains / "player-42.domain";
	{
		std::fstream file(player, std::ios::in | std::ios::out | std::ios::binary);
		require(file.good(), "could not open player domain for corruption test");
		file.seekg(-1, std::ios::end);
		char value = 0;
		file.read(&value, 1);
		value ^= 0x44;
		file.seekp(-1, std::ios::end);
		file.write(&value, 1);
	}
	require(flatfile_player_domain_load(root.string(), 42, "account-one", 1, &loaded, &error) ==
			flatfile_player_domain_result::invalid,
		"corrupt player-domain checksum was accepted");
	require(flatfile_player_domain_establish(root.string(), baseline(42), &error) ==
			flatfile_player_domain_result::invalid,
		"corrupt player domain was overwritten");
	for (const fs::directory_entry &entry : fs::directory_iterator(domains))
		require(entry.path().filename().string().find(".tmp.") == std::string::npos,
			"temporary domain file was left behind");

	std::cout << "flat-file player domain repository passed\n";
	return 0;
}
