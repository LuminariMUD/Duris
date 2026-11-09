/* Shutdown-only locker recovery. Ordinary checkpoints and copyover keep using
 * the writer. This image is frozen after the writer stops and before world cleanup;
 * boot replays it before any owner can load or custody cleanup can run. */
#include "persistence/locker_recovery.h"
#include "persistence/persistence_mode.h"
#include "persistence/persistence_observability.h"
#include "flatfile/flatfile_player_repository.h"
#include "flatfile/flatfile_store.h"
#include "player/player_snapshot_codec.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "sql/sql.h"

#include <array>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <unordered_set>

namespace
{
constexpr size_t image_max = 128 * 1024 * 1024;
constexpr uint32_t entry_max = 65536;
constexpr const char *image_name = "shutdown.image";
std::string directory;
std::string backend_identity;
int directory_fd = -1, service_lock = -1;
pid_t child = -1;
bool capture_complete = false;

void number(std::vector<uint8_t> &out, uint32_t value)
{
	for (unsigned n = 0; n < 4; ++n)
		out.push_back(static_cast<uint8_t>(value >> (8 * n)));
}

void text(std::vector<uint8_t> &out, const std::string &value)
{
	number(out, static_cast<uint32_t>(value.size()));
	out.insert(out.end(), value.begin(), value.end());
}

struct reader
{
	const std::vector<uint8_t> &bytes;
	size_t at = 0;
	bool ok = true;
	uint32_t number()
	{
		if (!ok || bytes.size() - at < 4)
		{
			ok = false;
			return 0;
		}
		uint32_t value = 0;
		for (unsigned n = 0; n < 4; ++n)
			value |= static_cast<uint32_t>(bytes[at++]) << (8 * n);
		return value;
	}
	std::string text()
	{
		const size_t size = number();
		if (!ok || size > 4096 || size > bytes.size() - at)
		{
			ok = false;
			return {};
		}
		std::string result(reinterpret_cast<const char *>(bytes.data() + at), size);
		at += size;
		ok = result.find('\0') == std::string::npos;
		return result;
	}
};

std::string backend()
{
	const char *root = persistence_mode_flatfile_root();
	return root ? std::string("flatfile:") + root : backend_identity;
}

bool encode(const std::vector<locker_recovery_entry> &entries,
	    const std::vector<player_snapshot> &players, bool complete, std::vector<uint8_t> *bytes)
{
	if (entries.size() > entry_max)
		return false;
	*bytes = { 'L', 'S', 'R', 1 };
	number(*bytes, complete ? 1 : 0);
	text(*bytes, backend());
	number(*bytes, static_cast<uint32_t>(entries.size()));
	std::unordered_set<uint64_t> uids;
	for (const auto &entry : entries)
	{
		std::vector<uint8_t> items;
		if (entry.contents.locker_name.empty() || entry.contents.locker_name.size() > 100 ||
		    player_item_snapshot_list_encode(entry.contents.items, &items) !=
			    player_snapshot_codec_result::ok)
			return false;
		for (const auto &item : entry.contents.items)
			if (!uids.insert(item.object_uid).second)
				return false;
		text(*bytes, entry.contents.locker_name);
		number(*bytes, static_cast<uint32_t>(entry.contents.racewar));
		number(*bytes, static_cast<uint32_t>(entry.contents.race));
		number(*bytes, static_cast<uint32_t>(entry.locker_id));
		number(*bytes, static_cast<uint32_t>(entry.chest_id));
		number(*bytes, static_cast<uint32_t>(items.size()));
		if (bytes->size() > image_max || items.size() > image_max - bytes->size())
			return false;
		bytes->insert(bytes->end(), items.begin(), items.end());
	}
	number(*bytes, static_cast<uint32_t>(players.size()));
	for (const auto &player : players)
	{
		std::vector<uint8_t> snapshot;
		if (player_snapshot_encode(player, &snapshot) != player_snapshot_codec_result::ok)
			return false;
		for (const auto &item : player.items)
			if (!uids.insert(item.object_uid).second)
				return false;
		number(*bytes, static_cast<uint32_t>(snapshot.size()));
		if (bytes->size() > image_max || snapshot.size() > image_max - bytes->size())
			return false;
		bytes->insert(bytes->end(), snapshot.begin(), snapshot.end());
	}
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest{};
	SHA256(bytes->data(), bytes->size(), digest.data());
	bytes->insert(bytes->end(), digest.begin(), digest.end());
	return bytes->size() <= image_max;
}

bool decode(const std::vector<uint8_t> &bytes, std::vector<locker_recovery_entry> *entries,
	    std::vector<player_snapshot> *players)
{
	if (bytes.size() < 16 + SHA256_DIGEST_LENGTH || bytes.size() > image_max ||
	    memcmp(bytes.data(), "LSR\1", 4))
		return false;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest{};
	const size_t payload_size = bytes.size() - digest.size();
	SHA256(bytes.data(), payload_size, digest.data());
	if (CRYPTO_memcmp(digest.data(), bytes.data() + payload_size, digest.size()))
		return false;
	reader input{ bytes, 4 };
	if (input.number() != 1 || input.text() != backend())
		return false;
	const uint32_t count = input.number();
	if (!input.ok || count > entry_max)
		return false;
	std::unordered_set<uint64_t> uids;
	for (uint32_t n = 0; n < count; ++n)
	{
		locker_recovery_entry entry;
		entry.contents.locker_name = input.text();
		entry.contents.racewar = static_cast<int32_t>(input.number());
		entry.contents.race = static_cast<int32_t>(input.number());
		entry.locker_id = static_cast<int32_t>(input.number());
		entry.chest_id = static_cast<int32_t>(input.number());
		const size_t size = input.number();
		if (!input.ok || input.at > payload_size || size > payload_size - input.at ||
		    entry.contents.locker_name.empty() || entry.contents.locker_name.size() > 100 ||
		    entry.locker_id < 0 || entry.chest_id < 0 ||
		    (entry.chest_id && !entry.locker_id) ||
		    player_item_snapshot_list_decode(bytes.data() + input.at, size,
						     &entry.contents.items) !=
			    player_snapshot_codec_result::ok)
			return false;
		input.at += size;
		for (const auto &item : entry.contents.items)
			if (!uids.insert(item.object_uid).second)
				return false;
		entries->push_back(std::move(entry));
	}
	const uint32_t player_count = input.number();
	if (!input.ok || player_count > entry_max)
		return false;
	std::unordered_set<int32_t> pids;
	for (uint32_t n = 0; n < player_count; ++n)
	{
		const size_t size = input.number();
		player_snapshot player;
		if (!input.ok || input.at > payload_size || size > payload_size - input.at ||
		    player_snapshot_decode(bytes.data() + input.at, size, &player) !=
			    player_snapshot_codec_result::ok ||
		    player.components !=
			    (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY) ||
		    !pids.insert(player.pid).second)
			return false;
		input.at += size;
		for (const auto &item : player.items)
			if (!uids.insert(item.object_uid).second)
				return false;
		players->push_back(std::move(player));
	}
	return input.ok && input.at == payload_size;
}

player_save_apply_result apply(locker_recovery_entry &entry)
{
	const std::string &name = entry.contents.locker_name;
	if (name.starts_with("guild."))
		entry.contents.owner_assoc_id = atoi(name.c_str() + 6);
	else if (!name.starts_with("account."))
		entry.contents.owner_name = name.substr(0, name.rfind(".locker"));
	if (const char *root = persistence_mode_flatfile_root())
	{
		// Native flat-file lockers currently expose only public chests.
		if (entry.chest_id)
			return { player_save_apply_outcome::terminal_failure, 0, EINVAL };
		flatfile_locker_save save;
		save.locker_name = entry.contents.locker_name;
		save.owner_assoc_id = entry.contents.owner_assoc_id;
		save.racewar = static_cast<int8_t>(entry.contents.racewar);
		save.race = static_cast<int8_t>(entry.contents.race);
		save.items = entry.contents.items;
		std::string error;
		return flatfile_locker_snapshot_apply(root, save, &error);
	}
	if (entry.chest_id)
		return locker_chest_snapshot_repository_apply(DB, { entry.locker_id, entry.chest_id,
								    entry.contents.items });
	return locker_snapshot_repository_apply(DB, entry.contents);
}

// After fork a multithreaded process may only call async-signal-safe functions.
// Paths and bytes are prepared by the parent. Do not use the C++ file store,
// allocation, logging, mutexes, or database connections in this child.
void publish(const uint8_t *bytes, size_t size)
{
	const int fd = openat(directory_fd, "shutdown.pending",
			      O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
	if (fd < 0)
		_exit(1);
	bool ok = true;
	while (size)
	{
		const ssize_t written = write(fd, bytes, size);
		if (written < 0 && errno == EINTR)
			continue;
		if (written <= 0)
		{
			ok = false;
			break;
		}
		bytes += written;
		size -= static_cast<size_t>(written);
	}
	ok = ok && fsync(fd) == 0;
	if (close(fd))
		ok = false;
	if (ok)
		ok = renameat(directory_fd, "shutdown.pending", directory_fd, image_name) == 0 &&
		     fsync(directory_fd) == 0;
	_exit(ok ? 0 : 1);
}
} // namespace

bool locker_recovery_boot(void)
{
	try
	{
		const char *root = persistence_mode_flatfile_root();
		if (!root)
		{
			backend_identity = std::string("mariadb:") + sql_persistence_db_name();
			for (const char *key : { "DB_HOST", "DB_PORT", "DB_SOCKET" })
			{
				const char *value = getenv(key);
				backend_identity += std::string(":") + (value ? value : "");
			}
		}
		directory = root ? std::string(root) + "/locker-shutdown" :
				   "runtime/locker-shutdown";
		bool runtime_created = false;
		if (!root)
		{
			runtime_created = mkdir("runtime", 0700) == 0;
			if (!runtime_created && errno != EEXIST)
				return false;
		}
		if (mkdir(directory.c_str(), 0700) && errno != EEXIST)
			return false;
		std::string error;
		if (!flatfile_lock_acquire(directory, ".service-lock", &service_lock, &error))
			return false;
		directory_fd =
			open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
		if (directory_fd < 0)
			return false;
		// Persist the directory before relying on a later image within it.
		const std::string parent = std::filesystem::path(directory).parent_path().string();
		const int parent_fd = open(parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
		if (parent_fd < 0)
			return false;
		const bool synced = fsync(parent_fd) == 0;
		close(parent_fd);
		if (!synced)
			return false;
		if (runtime_created)
		{
			// runtime/ can itself be new on the first boot. Sync its entry in
			// the data directory too, not only locker-shutdown/ inside runtime/.
			const int data_fd = open(".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
			if (data_fd < 0)
				return false;
			const bool parent_synced = fsync(data_fd) == 0;
			close(data_fd);
			if (!parent_synced)
				return false;
		}
		// An interrupted publication is ambiguous evidence. Keep it for staff;
		// neither an empty writer nor an older database proves it was recovered.
		struct stat info;
		if (fstatat(directory_fd, "shutdown.pending", &info, AT_SYMLINK_NOFOLLOW) == 0 ||
		    errno != ENOENT)
			return false;
		std::vector<uint8_t> bytes;
		const auto read = flatfile_read(directory, image_name, image_max, &bytes, &error);
		if (read == flatfile_read_result::not_found)
			return true;
		std::vector<locker_recovery_entry> entries;
		std::vector<player_snapshot> players;
		if (read != flatfile_read_result::ok || !decode(bytes, &entries, &players))
		{
			logit(LOG_FILE,
			      "Locker shutdown image unresolved: read_result=%d; invalid, incomplete or wrong backend evidence must be retained",
			      static_cast<int>(read));
			return false;
		}
		// Decode every owner before touching storage. Whole-image replay is safe
		// after a partial apply: no live gameplay can interleave with these saves.
		for (auto &entry : entries)
		{
			const auto result = apply(entry);
			if (result.outcome != player_save_apply_outcome::applied &&
			    result.outcome != player_save_apply_outcome::already_applied)
			{
				logit(LOG_FILE,
				      "Locker shutdown replay failed: locker=%s chest_id=%d error=%u",
				      entry.contents.locker_name.c_str(), entry.chest_id,
				      result.error_code);
				return false;
			}
		}
		for (const auto &player : players)
		{
			player_save_apply_result result;
			if (root)
			{
				std::string detail;
				result = flatfile_player_snapshot_apply(root, player, &detail);
			}
			else
				result = player_snapshot_repository_apply(DB, player);
			if (result.outcome != player_save_apply_outcome::applied &&
			    result.outcome != player_save_apply_outcome::already_applied)
			{
				logit(LOG_FILE,
				      "Locker shutdown replay failed: player_pid=%d error=%u",
				      player.pid, result.error_code);
				return false;
			}
		}
		if (!flatfile_atomic_remove(directory, image_name, false, &error))
			return false;
		logit(LOG_STATUS, "Locker shutdown recovery applied: chests=%zu players=%zu",
		      entries.size(), players.size());
		return true;
	}
	catch (...)
	{
		return false;
	}
}

void locker_recovery_begin(void)
{
	try
	{
		std::vector<locker_recovery_entry> entries;
		std::vector<player_snapshot> players;
		capture_complete = locker_shutdown_capture(&entries, &players);
		if (entries.empty() && capture_complete)
			return;
		std::vector<uint8_t> bytes;
		if (directory_fd >= 0 && encode(entries, players, capture_complete, &bytes))
		{
			child = fork();
			if (child == 0)
				publish(bytes.data(), bytes.size());
			if (child > 0)
				return;
		}
	}
	catch (...)
	{
		capture_complete = false;
	}
	capture_complete = false;
	logit(LOG_FILE, "UNRECOVERED locker shutdown: image could not be captured or started");
	fprintf(stderr, "UNRECOVERED locker shutdown: image could not be captured or started\n");
}

void locker_recovery_finish(uint64_t deadline_usec)
{
	if (child < 0)
		return;
	int status = 0;
	pid_t result;
	do
	{
		result = waitpid(child, &status, WNOHANG);
		if (result < 0 && errno == ECHILD && take_reaped_child_status(child, &status))
			result = child;
		if (result == child || (result < 0 && errno != EINTR))
			break;
		if (persistence_observability_now_usec() >= deadline_usec)
		{
			// Do not join a child stuck in filesystem I/O. Its pending/image file
			// remains evidence; boot refuses an incomplete publication.
			kill(child, SIGKILL);
			break;
		}
		usleep(1000);
	} while (true);
	const bool saved = result == child && WIFEXITED(status) && WEXITSTATUS(status) == 0;
	const char *outcome = saved && capture_complete ? "RECOVERABLE" : "UNRECOVERED";
	logit(LOG_FILE, "%s locker shutdown: image_published=%d capture_complete=%d path=%s/%s",
	      outcome, saved ? 1 : 0, capture_complete ? 1 : 0, directory.c_str(), image_name);
	fprintf(stderr, "%s locker shutdown: image_published=%d capture_complete=%d path=%s/%s\n",
		outcome, saved ? 1 : 0, capture_complete ? 1 : 0, directory.c_str(), image_name);
	child = -1;
}
