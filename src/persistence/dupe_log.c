#include "persistence/dupe_log.h"

#include <cerrno>
#include <cstdio>
#include <ctime>
#include <mutex>
#include <string>
#include <sys/stat.h>

namespace
{
std::mutex dupe_log_mutex;
std::string dupe_log_path = DUPE_LOG_PATH;

FILE *open_log(const std::string &path)
{
	FILE *file = std::fopen(path.c_str(), "a");
	if (file || errno != ENOENT)
		return file;
	// Create each missing parent directory, then try once more.
	for (size_t slash = path.find('/'); slash != std::string::npos;
	     slash = path.find('/', slash + 1))
		if (slash)
			mkdir(path.substr(0, slash).c_str(), 0755);
	return std::fopen(path.c_str(), "a");
}

void write_line(const std::string &path, const char *event, uint64_t item_uid, int32_t vnum,
		const char *from_label, const item_owner_identity &from, const char *to_label,
		const item_owner_identity &to)
{
	const time_t now = time(nullptr);
	struct tm local = {};
	char stamp[32] = "";
	if (localtime_r(&now, &local))
		strftime(stamp, sizeof stamp, "%a %b %e %H:%M:%S %Y", &local);
	FILE *file = open_log(path);
	if (!file)
		return;
	std::fprintf(file, "%s::%s uid=%llu vnum=%d %s=%s:%llu:%llu %s=%s:%llu:%llu\n", stamp,
		     event ? event : "unknown", (unsigned long long)item_uid, vnum, from_label,
		     item_owner_type_label(from.type), (unsigned long long)from.id,
		     (unsigned long long)from.context_id, to_label, item_owner_type_label(to.type),
		     (unsigned long long)to.id, (unsigned long long)to.context_id);
	std::fclose(file);
}
} // namespace

const char *item_owner_type_label(item_owner_type type)
{
	switch (type)
	{
	case item_owner_type::unknown:
		return "unknown";
	case item_owner_type::player:
		return "player";
	case item_owner_type::container:
		return "container";
	case item_owner_type::room:
		return "room";
	case item_owner_type::corpse:
		return "corpse";
	case item_owner_type::locker:
		return "locker";
	case item_owner_type::auction:
		return "auction";
	case item_owner_type::system:
		return "system";
	case item_owner_type::destruction:
		return "destruction";
	case item_owner_type::shopkeeper:
		return "shopkeeper";
	case item_owner_type::collector:
		return "collector";
	case item_owner_type::pet:
		return "pet";
	}
	return "unknown";
}

void dupe_log_item(const char *event, uint64_t item_uid, int32_t vnum,
		   const item_owner_identity &lost_by, const item_owner_identity &held_by)
{
	std::lock_guard<std::mutex> lock(dupe_log_mutex);
	write_line(dupe_log_path, event, item_uid, vnum, "lost_by", lost_by, "held_by", held_by);
}

void item_claim_log_item(uint64_t item_uid, int32_t vnum, const item_owner_identity &old_owner,
			 const item_owner_identity &new_owner)
{
	std::lock_guard<std::mutex> lock(dupe_log_mutex);
	write_line(ITEM_CLAIM_LOG_PATH, "claimed", item_uid, vnum, "from", old_owner, "to",
		   new_owner);
}

void dupe_log_set_path_for_tests(const char *path)
{
	std::lock_guard<std::mutex> lock(dupe_log_mutex);
	dupe_log_path = path ? path : DUPE_LOG_PATH;
}
