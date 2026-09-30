// Synthetic account/player/domain fixture and deliberately interrupted durable
// transaction. Never use this executable with an existing authority root.
#define main player_repository_regression_main
#include "flatfile_player_repository_harness.cpp"
#undef main
#include "flatfile/flatfile_account_repository.h"
#include "flatfile/flatfile_authority_transaction.h"
#include "flatfile/flatfile_store.h"
#include "item/locker_receipt.h"

// Native fixture output must not expose repository log details.
void logit(const char *, const char *, ...) {}

static std::vector<uint8_t> fixture_bytes(const char *text)
{
	return { text, text + std::strlen(text) };
}

static critical_command fixture_currency_command(bool deposit = false)
{
	currency_command_payload payload = {};
	payload.pid = 42;
	payload.racewar = 0;
	payload.reason = deposit ? currency_reason_type::atm_deposit :
				   currency_reason_type::wallet_reward;
	std::strcpy(payload.account_name.data(), "Account-One");
	payload.wallet_delta.amount[0] = deposit ? -5 : 5;
	payload.bank_delta.amount[0] = deposit ? 5 : 0;
	critical_operation_id operation = {};
	operation.bytes[0] = deposit ? 0xa4 : 0xa3;
	critical_command command;
	// The baseline seeded below has wallet revision 0 and bank revision 1.
	// Do not load it here: that would replay the pending authority transaction.
	require(currency_command_build(&command, operation, payload, 0, 1,
				       critical_source_site::command,
				       critical_deadline_class::interactive),
		"synthetic currency encoding failed");
	command.accepted_at_usec = 1;
	require(critical_command_normalize(&command), "synthetic currency normalization failed");
	return command;
}
static std::vector<uint8_t> fixture_read_bytes(const fs::path &path)
{
	std::ifstream input(path, std::ios::binary);
	require(input.good(), "synthetic authority file missing");
	return { std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>() };
}
int main(int argc, char **argv)
{
	require(argc == 3, "fixture mode and root required");
	const std::string mode = argv[1];
	const fs::path root = argv[2];
	std::string error;
	if (mode == "seed-receipt")
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
		fs::create_directories(root);
		fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
		require(locker_receipt_write(root.string(), receipt),
			"synthetic receipt write failed");
		return 0;
	}
	if (mode == "seed-bank-interrupted" || mode == "seed-legacy-bank-interrupted")
	{
		const auto player = root / "domains/player-42.domain";
		const auto bank = root / "domains/bank-account-one-0.domain";
		const auto player_before = fixture_read_bytes(player);
		const auto bank_before = fixture_read_bytes(bank);
		const bool legacy = mode == "seed-legacy-bank-interrupted";
		if (legacy)
			setenv("DURIS_FLATFILE_TEST_LEGACY_TRANSACTION", "1", 1);
		setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_BANK", "1", 1);
		const auto applied =
			flatfile_player_domain_apply(root.string(), fixture_currency_command(true));
		unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_BANK");
		unsetenv("DURIS_FLATFILE_TEST_LEGACY_TRANSACTION");
		require(applied.outcome == critical_apply_outcome::retryable_failure,
			"native bank transaction did not interrupt");
		require(fs::exists(
				root / "domains" /
				(legacy ? ".currency-transaction" : ".player-domain-transaction")),
			"interrupted bank transaction lost its durable intent");
		require(fixture_read_bytes(player) == player_before &&
				fixture_read_bytes(bank) != bank_before,
			"bank interruption did not leave bank-after/player-before state");
		return 0;
	}
	if (mode == "verify" || mode == "verify-bank")
	{
		flatfile_account_record account;
		require(flatfile_account_load(root.string(), "Account-One", &account, &error) ==
					flatfile_account_result::ok &&
				account.characters.size() == 1 && account.characters[0].pid == 42,
			"restored synthetic account mismatch");
		player_load_request request = {};
		request.request_id = 1;
		request.pid = 42;
		request.account_name = "Account-One";
		request.deadline_usec =
			persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
		const auto loaded = flatfile_player_load_repository_execute(root.string(), request);
		require(loaded.outcome == player_load_outcome::applied &&
				loaded.domains.wallet ==
					std::array<uint64_t, 4>{ mode == "verify-bank" ? 6u : 11u,
								 12, 13, 14 } &&
				loaded.domains.epics == 15 && loaded.snapshot.revision == 1 &&
				loaded.item_identities.size() == 2,
			"restored synthetic player/domain mismatch");
		if (mode == "verify-bank")
		{
			require(loaded.domains.bank == std::array<uint64_t, 4>{ 5, 0, 0, 0 } &&
					loaded.domains.wallet_revision == 1 &&
					loaded.domains.bank_revision == 2,
				"bank transaction after-images or revisions were not recovered");
			require(!fs::exists(root / "domains/.player-domain-transaction") &&
					!fs::exists(root / "domains/.currency-transaction"),
				"bank transaction intent was not retired");
			require(flatfile_player_domain_apply(root.string(),
							     fixture_currency_command(true))
						.outcome == critical_apply_outcome::already_applied,
				"bank transfer recovery did not persist its deduplication ledger");
		}
		for (const char *name : { "restore-probe-one", "restore-probe-two" })
		{
			std::ifstream stream(root / "domains" / name);
			std::string value;
			stream >> value;
			require(value == "after",
				"pending transaction after-image was not replayed");
		}
		require(!fs::exists(root / "domains/.critical-authority-transaction"),
			"pending transaction was not retired");
		return 0;
	}
	require(mode == "seed" && !fs::exists(root), "seed requires an absent disposable root");
	for (const char *directory :
	     { "identities/names", "identities/accounts", "players", "domains" })
		fs::create_directories(root / directory);
	for (const auto &entry : fs::recursive_directory_iterator(root))
		fs::permissions(entry.path(), fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	flatfile_account_record account;
	account.name = "Account-One";
	account.email = "fixture@example.test";
	account.confirmed = 1;
	flatfile_account_character character;
	character.pid = 42;
	character.name = "Player";
	character.level = 50;
	account.characters.push_back(character);
	uint64_t revision = 0;
	require(flatfile_account_save(root.string(), account, 0, &revision, &error) ==
			flatfile_account_result::ok,
		"synthetic account seed failed");
	int32_t pid = 0;
	for (int expected = 1; expected <= 42; ++expected)
		require(flatfile_identity_allocate_pid(root.string(), &pid, &error) ==
					flatfile_identity_result::ok &&
				pid == expected,
			"synthetic identity allocation failed");
	require(flatfile_identity_claim(root.string(), 42, "Player", "Account-One", &error) ==
			flatfile_identity_result::ok,
		"synthetic identity claim failed");
	require(flatfile_player_snapshot_apply(root.string(), make_full(1), &error).outcome ==
			player_save_apply_outcome::applied,
		"synthetic snapshot seed failed");
	require(flatfile_boon_establish(root.string(), {}, &error) == flatfile_boon_result::ok,
		"synthetic boon seed failed");
	for (const char *name : { "restore-probe-one", "restore-probe-two" })
		require(flatfile_atomic_write((root / "domains").string(), name,
					      fixture_bytes("before"), &error),
			"synthetic transaction seed failed");
	{
		flatfile_authority_lock lock;
		require(lock.acquire(root.string(), &error), "synthetic authority lock failed");
		setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_IMAGE", "1", 1);
		const auto result = flatfile_authority_transaction_commit(
			root.string(), lock,
			{ { "restore-probe-one", fixture_bytes("after") },
			  { "restore-probe-two", fixture_bytes("after") } },
			&error);
		unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_IMAGE");
		require(result == flatfile_authority_transaction_result::io_error,
			"synthetic transaction was not interrupted");
	}
	require(fs::exists(root / "domains/.critical-authority-transaction"),
		"synthetic pending transaction missing");
	for (const char *name : { "restore-probe-one", "restore-probe-two" })
	{
		std::ifstream stream(root / "domains" / name);
		std::string value;
		stream >> value;
		require(value == (std::string(name) == "restore-probe-one" ? "after" : "before"),
			"synthetic interruption did not leave a split durable transaction");
	}
	return 0;
}
