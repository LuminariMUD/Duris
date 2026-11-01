#include "economy/shopkeeper_boot.h"

#include "flatfile/flatfile_store.h"

#include <cerrno>
#include <cstring>
#include <sys/stat.h>
#include <vector>

namespace
{
bool restock = false;
bool started = false;
constexpr const char *state_file = "state";
}

bool shopkeeper_boot_begin(const std::string &directory, bool recovery, std::string *error)
{
	restock = false;
	started = false;
	if (mkdir(directory.c_str(), 0700) < 0 && errno != EEXIST)
	{
		if (error)
			*error =
				std::string("create shopkeeper boot directory: ") + strerror(errno);
		return false;
	}
	std::vector<uint8_t> previous;
	const auto read = flatfile_read(directory, state_file, 1, &previous, error);
	if (read != flatfile_read_result::ok && read != flatfile_read_result::not_found)
		return false;
	if (read == flatfile_read_result::ok && previous != std::vector<uint8_t>{ 'C' } &&
	    previous != std::vector<uint8_t>{ 'R' })
	{
		if (error)
			*error = "invalid shopkeeper boot state";
		return false;
	}
	// Consume the clean stop before any world changes. An absent marker is unknown,
	// including the first boot after upgrading; it does not authorize a refill.
	if (!flatfile_atomic_write(directory, state_file, { 'R' }, error))
		return false;
	restock = !recovery && previous == std::vector<uint8_t>{ 'C' };
	started = true;
	return true;
}

bool shopkeeper_boot_finish(const std::string &directory, std::string *error)
{
	restock = false;
	if (!started)
		return false;
	started = false;
	return flatfile_atomic_write(directory, state_file, { 'C' }, error);
}

bool shopkeeper_boot_restock()
{
	return restock;
}
