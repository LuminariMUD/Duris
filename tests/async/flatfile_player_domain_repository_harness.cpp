#include "flatfile/flatfile_player_domain_repository.h"
#include "combat/combat_outcome_command.h"
#include "world/epic_command.h"

#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
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
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(domains, fs::perms::owner_all, fs::perm_options::replace);

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
	for (uint32_t version : { 2U, 3U })
	{
		for (uint16_t result_size : { 2048, 2049 })
		{
			const int32_t pid = 100 + version * 2 + (result_size - 2048);
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
			append_retained_result(fixture, result_size);
			const auto expected = result_size == 2048 ?
						      flatfile_player_domain_result::ok :
						      flatfile_player_domain_result::invalid;
			require(flatfile_player_domain_load(root.string(), pid, "account-one", 1,
							    &loaded, &error) == expected,
				label + " did not preserve the native 2048-byte bound: " + error);
		}
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
