#include "item/starter_kit_intent.h"
#include "item/item_transfer_command.h"
#include "flatfile/flatfile_store.h"

#include <cerrno>
#include <fcntl.h>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <sys/stat.h>
#include <unistd.h>

namespace
{
std::string directory;
int service_lock = -1;

bool valid(uint32_t pid, const critical_command &command)
{
	item_transfer_payload payload{};
	return pid && command.accepted_at_usec &&
	       item_transfer_command_decode_payload(command, &payload) &&
	       payload.reason == item_transfer_reason::creation && payload.multi_root &&
	       payload.from_owner.type == item_owner_type::system &&
	       payload.to_owner.type == item_owner_type::player && payload.to_owner.id == pid &&
	       !payload.to_owner.context_id && !payload.target_parent_item_uid;
}

bool write(uint32_t pid, const critical_command &command, uint8_t state)
{
	std::vector<uint8_t> bytes;
	if (service_lock < 0 || !valid(pid, command) ||
	    critical_command_encode(command, &bytes) != critical_command_codec_result::ok)
		return false;
	bytes.insert(bytes.begin(), state);
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(bytes.data(), bytes.size(), digest);
	bytes.insert(bytes.end(), digest, digest + sizeof(digest));
	return flatfile_atomic_write(directory, std::to_string(pid) + ".kit", bytes, nullptr);
}
}

bool starter_kit_intent_init(const char *parent)
{
	if (service_lock >= 0 || !parent || !*parent)
		return false;
	directory = std::string(parent) + "/starter-kits";
	if (mkdir(directory.c_str(), 0700) && errno != EEXIST)
		return false;
	const int fd = open(parent, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	if (fd < 0)
		return false;
	const bool synced = fsync(fd) == 0;
	close(fd);
	return synced && flatfile_lock_acquire(directory, ".service-lock", &service_lock, nullptr);
}

starter_kit_state starter_kit_intent_read(uint32_t pid, critical_command *command)
{
	if (service_lock < 0)
		return starter_kit_state::invalid;
	return starter_kit_intent_read(directory, pid, command);
}

starter_kit_state starter_kit_intent_read(const std::string &root, uint32_t pid,
					  critical_command *command)
{
	if (!pid || !command)
		return starter_kit_state::invalid;
	std::vector<uint8_t> bytes;
	const auto loaded = flatfile_read(
		root, std::to_string(pid) + ".kit",
		CRITICAL_COMMAND_MAX_ENCODED_BYTES + 1 + SHA256_DIGEST_LENGTH, &bytes, nullptr);
	if (loaded == flatfile_read_result::not_found)
		return starter_kit_state::absent;
	if (loaded != flatfile_read_result::ok || bytes.size() <= 1 + SHA256_DIGEST_LENGTH)
		return starter_kit_state::invalid;
	const size_t size = bytes.size() - SHA256_DIGEST_LENGTH;
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(bytes.data(), size, digest);
	if (CRYPTO_memcmp(digest, bytes.data() + size, sizeof(digest)) || bytes[0] > 2 ||
	    critical_command_decode(bytes.data() + 1, size - 1, command) !=
		    critical_command_codec_result::ok ||
	    !valid(pid, *command))
		return starter_kit_state::invalid;
	return bytes[0] == 0 ? starter_kit_state::pending :
	       bytes[0] == 1 ? starter_kit_state::committed :
			       starter_kit_state::rejected;
}

bool starter_kit_intent_bind(uint32_t pid, const critical_command &command)
{
	critical_command existing;
	const auto state = starter_kit_intent_read(pid, &existing);
	if (state == starter_kit_state::absent)
		return write(pid, command, 0);
	std::vector<uint8_t> old_bytes, new_bytes;
	return state == starter_kit_state::pending &&
	       critical_command_encode(existing, &old_bytes) == critical_command_codec_result::ok &&
	       critical_command_encode(command, &new_bytes) == critical_command_codec_result::ok &&
	       old_bytes == new_bytes;
}

bool starter_kit_intent_finish(uint32_t pid, const critical_command &command, bool committed)
{
	return starter_kit_intent_bind(pid, command) && write(pid, command, committed ? 1 : 2);
}

void starter_kit_intent_shutdown()
{
	flatfile_lock_release(service_lock);
	service_lock = -1;
	directory.clear();
}
