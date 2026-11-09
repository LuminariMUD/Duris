#include "item/locker_receipt.h"
#include "persistence/persistence_log.h"
#include "combat/combat_outcome_intent.h"
#include "item/starter_kit_intent.h"

// Native parsers may log diagnostics containing identities; this process reports
// only aggregate success or a fixed failure code.
void logit(const char *, const char *, ...) {}
bool persistence_log_submit(const char *)
{
	return true;
}

#include <charconv>
#include <filesystem>
#include <iostream>
#include <set>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

static void require(bool valid)
{
	if (!valid)
		throw std::runtime_error("native_restore_qualification_failed");
}

// Locker identification stores durable payment receipts in the critical-command journal
// directory. The service lock is empty runtime metadata; receipts must survive restore
// and pass the same bounded decoder used when a player claims their result.
static void qualify_locker_receipts(const std::filesystem::path &directory)
{
	struct stat status = {};
	require(lstat(directory.c_str(), &status) == 0 && S_ISDIR(status.st_mode) &&
		status.st_uid == geteuid() && !(status.st_mode & 0077));
	for (const auto &entry : std::filesystem::directory_iterator(directory))
	{
		require(lstat(entry.path().c_str(), &status) == 0 && S_ISREG(status.st_mode) &&
			status.st_uid == geteuid() && status.st_nlink == 1 &&
			!(status.st_mode & 0077));
		const auto name = entry.path().filename().string();
		if (name == ".service-lock")
		{
			require(status.st_size == 0);
			continue;
		}
		require(entry.path().extension() == ".receipt");
		const auto stem = entry.path().stem().string();
		require(!stem.empty() && stem.size() <= 10 && stem[0] != '0' &&
			stem.find_first_not_of("0123456789") == std::string::npos);
		const auto pid = std::stoull(stem);
		require(pid > 0 && pid <= INT32_MAX);
		locker_receipt receipt;
		require(locker_receipt_read(directory.string(), static_cast<uint32_t>(pid),
					    &receipt) == flatfile_read_result::ok);
	}
}

static void qualify_combat_intents(const std::filesystem::path &directory)
{
	struct stat status = {};
	require(lstat(directory.c_str(), &status) == 0 && S_ISDIR(status.st_mode) &&
		status.st_uid == geteuid() && !(status.st_mode & 0077));
	std::set<std::string> operations;
	size_t pending = 0;
	for (const auto &entry : std::filesystem::directory_iterator(directory))
	{
		require(lstat(entry.path().c_str(), &status) == 0 && S_ISREG(status.st_mode) &&
			status.st_uid == geteuid() && status.st_nlink == 1 &&
			!(status.st_mode & 0077));
		const auto name = entry.path().filename().string();
		if (name == ".service-lock")
		{
			require(status.st_size == 0);
			continue;
		}
		critical_command command;
		require(combat_outcome_intent_read(directory.string(), name, &command));
		require(operations.insert(name.substr(0, 32)).second);
		if (entry.path().extension() == ".intent")
			require(++pending <= COMBAT_OUTCOME_INTENT_MAX);
	}
}

static void qualify_starter_kits(const std::filesystem::path &directory)
{
	struct stat status
	{
	};
	require(lstat(directory.c_str(), &status) == 0 && S_ISDIR(status.st_mode) &&
		status.st_uid == geteuid() && !(status.st_mode & 0077));
	for (const auto &entry : std::filesystem::directory_iterator(directory))
	{
		require(lstat(entry.path().c_str(), &status) == 0 && S_ISREG(status.st_mode) &&
			status.st_uid == geteuid() && status.st_nlink == 1 &&
			!(status.st_mode & 0077));
		const auto name = entry.path().filename().string();
		if (name == ".service-lock")
		{
			require(status.st_size == 0);
			continue;
		}
		require(name.ends_with(".kit"));
		const auto text = name.substr(0, name.size() - 4);
		uint32_t pid = 0;
		const auto parsed = std::from_chars(text.data(), text.data() + text.size(), pid);
		require(parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size() &&
			pid && pid <= INT32_MAX && text == std::to_string(pid));
		critical_command command;
		const auto state = starter_kit_intent_read(directory.string(), pid, &command);
		require(state != starter_kit_state::absent && state != starter_kit_state::invalid);
	}
}

// Durable recovery evidence plus retired, unread critical-command journal files.
static void qualify_receipts(const std::filesystem::path &candidate)
{
	require(candidate.is_absolute() &&
		std::filesystem::is_regular_file(candidate / "ISOLATED_RESTORE"));
	const auto directory = candidate / "journals/critical";
	std::filesystem::create_directories(directory);
	for (const auto &entry : std::filesystem::directory_iterator(directory))
	{
		const auto name = entry.path().filename();
		if (name == "critical-command.journal" || name == "critical-command.journal.tmp")
		{
			require(entry.is_regular_file() && !entry.is_symlink());
			continue;
		}
		if (name == "combat-intents")
			qualify_combat_intents(entry.path());
		else if (name == "starter-kits")
			qualify_starter_kits(entry.path());
		else
		{
			require(name == "locker-identification");
			qualify_locker_receipts(entry.path());
		}
	}
}

int main(int argc, char **argv)
{
	try
	{
		require(argc == 3 && std::string(argv[1]) == "--receipts");
		qualify_receipts(argv[2]);
		return 0;
	}
	catch (...)
	{
		std::cerr << "native_restore_qualification_failed\n";
		return 1;
	}
}
