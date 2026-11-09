// Synthetic recovery evidence for the backup and restore tests: locker receipts, combat
// intents and starter-kit records, written with the production codecs. Never use this
// executable with a live journal directory.
#include "combat/combat_outcome_command.h"
#include "combat/combat_outcome_intent.h"
#include "economy/currency_command.h"
#include "item/item_transfer_command.h"
#include "item/locker_receipt.h"
#include "item/starter_kit_intent.h"
#include "persistence/persistence_log.h"

#include <chrono>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

void logit(const char *, const char *, ...) {}
bool persistence_log_submit(const char *)
{
	return true;
}

static void require(bool valid, const char *message)
{
	if (!valid)
		throw std::runtime_error(message);
}

static void private_directory(const fs::path &path)
{
	fs::create_directories(path);
	fs::permissions(path, fs::perms::owner_all, fs::perm_options::replace);
}

static critical_command combat_command(uint8_t id, int64_t admitted)
{
	combat_outcome_payload payload = {};
	payload.victim_pid = 42;
	payload.participant_count = 1;
	payload.participants[0].pid = 42;
	payload.participants[0].role = combat_participant_role::victim;
	std::strcpy(payload.participants[0].account_name.data(), "Account-One");
	critical_operation_id operation = {};
	operation.bytes[0] = id;
	critical_command command;
	require(combat_outcome_command_build(&command, operation, payload),
		"combat command build failed");
	command.accepted_at_usec = admitted + id;
	return command;
}

static int64_t admitted_at()
{
	return std::chrono::duration_cast<std::chrono::microseconds>(
		       std::chrono::system_clock::now().time_since_epoch())
		       .count() -
	       1000000;
}

static void seed_receipt(const fs::path &directory)
{
	currency_command_payload payload = {};
	payload.pid = 42;
	payload.reason = currency_reason_type::wallet_spend;
	std::strcpy(payload.account_name.data(), "Account-One");
	payload.wallet_delta.amount[0] = -5;
	critical_operation_id operation = {};
	operation.bytes[0] = 0xb5;
	locker_receipt receipt;
	require(currency_command_build(&receipt.payment, operation, payload, 0, 1,
				       critical_source_site::command,
				       critical_deadline_class::interactive),
		"synthetic receipt payment encoding failed");
	receipt.payment.accepted_at_usec = 1;
	require(critical_command_normalize(&receipt.payment),
		"synthetic receipt normalization failed");
	receipt.text = "Synthetic locker identification result.";
	receipt.state = locker_receipt_state::paid;
	private_directory(directory);
	require(locker_receipt_write(directory.string(), receipt),
		"synthetic receipt write failed");
}

// c1 stays pending; c2 is recorded, as after its authority commit.
static void seed_combat(const fs::path &journal, bool pending)
{
	private_directory(journal);
	std::vector<critical_command> retained;
	require(combat_outcome_intent_init(journal.c_str(), &retained),
		"combat intent initialization failed");
	require(retained.empty(), "seed requires no existing intents");
	const int64_t admitted = admitted_at();
	if (pending)
		require(combat_outcome_intent_write(combat_command(0xc1, admitted)),
			"combat write failed");
	const critical_command recorded = combat_command(0xc2, admitted);
	require(combat_outcome_intent_write(recorded), "combat write failed");
	require(combat_outcome_intent_complete(recorded.operation_id), "combat completion failed");
	combat_outcome_intent_shutdown();
}

// The commit of a retained intent, without the authority it would commit to.
static void recover_combat(const fs::path &journal)
{
	std::vector<critical_command> retained;
	require(combat_outcome_intent_init(journal.c_str(), &retained),
		"combat intent initialization failed");
	require(retained.size() <= 1, "unexpected replay count");
	for (const auto &command : retained)
	{
		require(command.operation_id.bytes[0] == 0xc1,
			"completed evidence must not replay");
		require(combat_outcome_intent_complete(command.operation_id),
			"restored intent completion failed");
		std::cout << "applied\n";
	}
	combat_outcome_intent_shutdown();
}

static void seed_starter(const fs::path &journal, bool committed)
{
	private_directory(journal);
	require(starter_kit_intent_init(journal.c_str()), "starter-kit initialization failed");
	item_transfer_payload payload = {};
	payload.from_owner = { item_owner_type::system, 0, 0 };
	payload.to_owner = { item_owner_type::player, 42, 0 };
	payload.reason = item_transfer_reason::creation;
	payload.multi_root = true;
	payload.item_count = 1;
	payload.items[0] = { 100, 100,
			     0,	  ITEM_TRANSFER_ABSENT_REVISION,
			     500, item_custody_state::absent };
	payload.item_blob_size = 1;
	payload.item_blob[0] = 1;
	critical_operation_id operation = {};
	operation.bytes[0] = 0xd1;
	critical_command command;
	require(item_transfer_command_build(&command, operation, payload,
					    critical_source_site::command,
					    critical_deadline_class::interactive),
		"starter-kit command build failed");
	command.accepted_at_usec = 123;
	require(starter_kit_intent_bind(42, command), "starter-kit write failed");
	if (committed)
		require(starter_kit_intent_finish(42, command, true), "starter-kit finish failed");
	starter_kit_intent_shutdown();
}

int main(int argc, char **argv)
{
	try
	{
		require(argc == 3, "fixture mode and directory required");
		const std::string mode = argv[1];
		const fs::path directory = argv[2];
		if (mode == "seed-receipt")
			seed_receipt(directory);
		else if (mode == "seed-combat")
			seed_combat(directory, true);
		else if (mode == "seed-combat-recorded")
			seed_combat(directory, false);
		else if (mode == "recover-combat")
			recover_combat(directory);
		else if (mode == "seed-starter")
			seed_starter(directory, false);
		else if (mode == "seed-starter-committed")
			seed_starter(directory, true);
		else
			require(false, "unknown fixture mode");
		return 0;
	}
	catch (const std::exception &error)
	{
		std::cerr << error.what() << '\n';
		return 1;
	}
}
