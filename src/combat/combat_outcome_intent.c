#include "combat/combat_outcome_intent.h"
#include "combat/combat_outcome_command.h"
#include "flatfile/flatfile_store.h"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <sys/stat.h>
#include <unistd.h>

namespace
{
std::string directory;
int service_lock = -1;

std::string filename(const critical_operation_id &operation)
{
	char reference[CRITICAL_COMMAND_ID_HEX_SIZE];
	critical_operation_id_to_hex(operation, reference, sizeof(reference));
	return std::string(reference) + ".intent";
}
}

bool combat_outcome_intent_read(const std::string &root, const std::string &name,
				critical_command *command)
{
	critical_operation_id operation;
	std::vector<uint8_t> bytes;
	combat_outcome_payload payload;
	unsigned char digest[SHA256_DIGEST_LENGTH];
	if (!command ||
	    !((name.size() == 32 + strlen(".intent") && name.ends_with(".intent")) ||
	      (name.size() == 32 + strlen(".recorded") && name.ends_with(".recorded"))) ||
	    name.substr(0, 32).find_first_not_of("0123456789abcdef") != std::string::npos ||
	    !critical_operation_id_from_hex(name.substr(0, 32).c_str(), &operation) ||
	    flatfile_read(root, name, CRITICAL_COMMAND_MAX_ENCODED_BYTES + sizeof(digest), &bytes,
			  nullptr) != flatfile_read_result::ok ||
	    bytes.size() <= sizeof(digest))
		return false;
	const size_t size = bytes.size() - sizeof(digest);
	SHA256(bytes.data(), size, digest);
	return CRYPTO_memcmp(digest, bytes.data() + size, sizeof(digest)) == 0 &&
	       critical_command_decode(bytes.data(), size, command) ==
		       critical_command_codec_result::ok &&
	       command->accepted_at_usec &&
	       critical_operation_id_equal(command->operation_id, operation) &&
	       combat_outcome_command_decode_payload(*command, &payload);
}

bool combat_outcome_intent_init(const char *parent, std::vector<critical_command> *retained)
{
	if (service_lock >= 0 || !parent || !*parent || !retained)
		return false;
	retained->clear();
	directory = std::string(parent) + "/combat-intents";
	if (mkdir(directory.c_str(), 0700) && errno != EEXIST)
		return false;
	const int parent_fd = open(parent, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	if (parent_fd < 0)
		return false;
	const bool synced = fsync(parent_fd) == 0;
	close(parent_fd);
	if (!synced || !flatfile_lock_acquire(directory, ".service-lock", &service_lock, nullptr))
		return false;
	DIR *entries = opendir(directory.c_str());
	bool ok = entries != nullptr;
	while (ok)
	{
		errno = 0;
		const dirent *entry = readdir(entries);
		if (!entry)
		{
			ok = errno == 0;
			break;
		}
		const std::string name = entry->d_name;
		if (name[0] == '.' || name.ends_with(".recorded"))
			continue; // Completed evidence and unpublished atomic-write temporaries.
		critical_command command;
		ok = combat_outcome_intent_read(directory, name, &command);
		if (ok)
		{
			ok = retained->size() < COMBAT_OUTCOME_INTENT_MAX;
			if (ok)
				retained->push_back(std::move(command));
		}
	}
	if (entries)
		closedir(entries);
	if (!ok)
	{
		retained->clear();
		combat_outcome_intent_shutdown();
		return false;
	}
	std::sort(retained->begin(), retained->end(), [](const auto &left, const auto &right)
		  { return left.accepted_at_usec < right.accepted_at_usec; });
	return true;
}

void combat_outcome_intent_shutdown()
{
	flatfile_lock_release(service_lock);
	service_lock = -1;
	directory.clear();
}

bool combat_outcome_intent_write(const critical_command &command)
{
	std::vector<uint8_t> bytes;
	combat_outcome_payload payload;
	if (service_lock < 0 || !command.accepted_at_usec ||
	    !combat_outcome_command_decode_payload(command, &payload) ||
	    critical_command_encode(command, &bytes) != critical_command_codec_result::ok)
		return false;
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(bytes.data(), bytes.size(), digest);
	bytes.insert(bytes.end(), digest, digest + sizeof(digest));
	return flatfile_atomic_write(directory, filename(command.operation_id), bytes, nullptr);
}

bool combat_outcome_intent_complete(const critical_operation_id &operation)
{
	if (service_lock < 0)
		return false;
	const int fd = open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	if (fd < 0)
		return false;
	const auto name = filename(operation);
	const auto recorded = name.substr(0, 32) + ".recorded";
	const bool ok = renameat(fd, name.c_str(), fd, recorded.c_str()) == 0 && fsync(fd) == 0;
	close(fd);
	return ok;
}
