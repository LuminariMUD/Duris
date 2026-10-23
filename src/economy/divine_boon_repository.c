#include "economy/divine_boon_repository.h"

#include "flatfile/flatfile_authority_transaction.h"
#include "flatfile/flatfile_store.h"

#include <charconv>
#include <limits>

namespace
{
constexpr size_t maximum_bytes = 4096;
constexpr const char *filename = "divine-boons.state";

divine_boon_store_result read_flatfile(const std::string &root, divine_boon_state *state)
{
	std::vector<uint8_t> bytes;
	const auto result =
		flatfile_read(root + "/domains", filename, maximum_bytes, &bytes, nullptr);
	if (result == flatfile_read_result::not_found)
		return divine_boon_store_result::not_found;
	if (result == flatfile_read_result::invalid)
		return divine_boon_store_result::invalid;
	if (result != flatfile_read_result::ok)
		return divine_boon_store_result::io_error;
	return divine_boon_state_decode(bytes, state) ? divine_boon_store_result::ok :
							divine_boon_store_result::invalid;
}

bool prepare_save(uint64_t expected_revision, const divine_boon_state &state,
		  std::vector<uint8_t> *bytes)
{
	return expected_revision != std::numeric_limits<uint64_t>::max() &&
	       state.revision == expected_revision + 1 && divine_boon_state_encode(state, bytes);
}

#ifndef __NO_MYSQL__
std::string hex(const std::vector<uint8_t> &bytes)
{
	constexpr char digits[] = "0123456789abcdef";
	std::string result;
	result.reserve(bytes.size() * 2);
	for (uint8_t byte : bytes)
	{
		result.push_back(digits[byte >> 4]);
		result.push_back(digits[byte & 15]);
	}
	return result;
}
#endif
}

divine_boon_store_result divine_boon_flatfile_load(const std::string &root,
						   divine_boon_state *state)
{
	if (root.empty() || !state)
		return divine_boon_store_result::invalid;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, nullptr) ||
	    flatfile_authority_transaction_recover(root, lock, nullptr) !=
		    flatfile_authority_transaction_result::ok)
		return divine_boon_store_result::io_error;
	return read_flatfile(root, state);
}

divine_boon_store_result divine_boon_flatfile_save(const std::string &root,
						   uint64_t expected_revision,
						   const divine_boon_state &state)
{
	std::vector<uint8_t> bytes;
	if (root.empty() || !prepare_save(expected_revision, state, &bytes))
		return divine_boon_store_result::invalid;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, nullptr) ||
	    flatfile_authority_transaction_recover(root, lock, nullptr) !=
		    flatfile_authority_transaction_result::ok)
		return divine_boon_store_result::io_error;
	divine_boon_state current;
	const auto loaded = read_flatfile(root, &current);
	if (loaded != divine_boon_store_result::ok && loaded != divine_boon_store_result::not_found)
		return loaded;
	if (loaded == divine_boon_store_result::ok && current == state)
		return divine_boon_store_result::already_applied;
	const uint64_t revision = loaded == divine_boon_store_result::ok ? current.revision : 0;
	if (revision != expected_revision)
		return divine_boon_store_result::conflict;
	return flatfile_authority_transaction_commit(root, lock, { { filename, std::move(bytes) } },
						     nullptr) ==
			       flatfile_authority_transaction_result::ok ?
		       divine_boon_store_result::ok :
		       divine_boon_store_result::io_error;
}

divine_boon_store_result divine_boon_sql_load(MYSQL *connection, divine_boon_state *state,
					      bool for_update)
{
#ifdef __NO_MYSQL__
	(void)connection;
	(void)state;
	(void)for_update;
	return divine_boon_store_result::io_error;
#else
	if (!connection || !state)
		return divine_boon_store_result::invalid;
	const char *query =
		for_update ?
			"SELECT revision,snapshot FROM divine_boon_state WHERE state_id=1 FOR UPDATE" :
			"SELECT revision,snapshot FROM divine_boon_state WHERE state_id=1";
	if (mysql_query(connection, query))
		return divine_boon_store_result::io_error;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return divine_boon_store_result::io_error;
	MYSQL_ROW row = mysql_fetch_row(result);
	if (!row)
	{
		const bool failed = mysql_errno(connection) != 0;
		mysql_free_result(result);
		return failed ? divine_boon_store_result::io_error :
				divine_boon_store_result::not_found;
	}
	const unsigned long *lengths = mysql_fetch_lengths(result);
	divine_boon_state decoded;
	uint64_t revision = 0;
	bool valid = row[0] && row[1] && lengths && lengths[0] && lengths[1] <= maximum_bytes;
	if (valid)
	{
		const auto parsed = std::from_chars(row[0], row[0] + lengths[0], revision);
		valid = parsed.ec == std::errc() && parsed.ptr == row[0] + lengths[0] &&
			divine_boon_state_decode({ row[1], row[1] + lengths[1] }, &decoded) &&
			decoded.revision == revision;
	}
	mysql_free_result(result);
	if (!valid)
		return divine_boon_store_result::invalid;
	*state = std::move(decoded);
	return divine_boon_store_result::ok;
#endif
}

divine_boon_store_result divine_boon_sql_save(MYSQL *connection, uint64_t expected_revision,
					      const divine_boon_state &state)
{
#ifdef __NO_MYSQL__
	(void)connection;
	(void)expected_revision;
	(void)state;
	return divine_boon_store_result::io_error;
#else
	std::vector<uint8_t> bytes;
	if (!connection || !prepare_save(expected_revision, state, &bytes))
		return divine_boon_store_result::invalid;
	divine_boon_state current;
	const auto before = divine_boon_sql_load(connection, &current);
	if (before != divine_boon_store_result::ok && before != divine_boon_store_result::not_found)
		return before;
	if (before == divine_boon_store_result::ok && current == state)
		return divine_boon_store_result::already_applied;
	if ((before == divine_boon_store_result::ok ? current.revision : 0) != expected_revision)
		return divine_boon_store_result::conflict;
	const std::string values = "revision=" + std::to_string(state.revision) +
				   ",snapshot=UNHEX('" + hex(bytes) + "')";
	const std::string query =
		expected_revision ? "UPDATE divine_boon_state SET " + values +
					    " WHERE state_id=1 AND revision=" +
					    std::to_string(expected_revision) :
				    "INSERT IGNORE INTO divine_boon_state SET state_id=1," + values;
	if (mysql_real_query(connection, query.data(), query.size()))
		return divine_boon_store_result::io_error;
	if (mysql_affected_rows(connection) == 1)
		return divine_boon_store_result::ok;
	// Also handles a retry after the server committed but the connection failed.
	const auto loaded = divine_boon_sql_load(connection, &current);
	if (loaded != divine_boon_store_result::ok)
		return loaded == divine_boon_store_result::not_found ?
			       divine_boon_store_result::conflict :
			       loaded;
	return current == state ? divine_boon_store_result::already_applied :
				  divine_boon_store_result::conflict;
#endif
}

// Pwipe calls this after its writer drain; preserve the same optimistic revision
// contract used by normal writes, with one durable transition for all old slots.
divine_boon_store_result divine_boon_sql_reset_season(MYSQL *connection, int64_t now)
{
	divine_boon_state current;
	const auto loaded = divine_boon_sql_load(connection, &current);
	if (loaded == divine_boon_store_result::not_found)
		return divine_boon_store_result::already_applied;
	if (loaded != divine_boon_store_result::ok)
		return loaded;
	auto next = current;
	if (!divine_boon_reset_season(&next, now))
		return divine_boon_store_result::invalid;
	if (next == current)
		return divine_boon_store_result::already_applied;
	return divine_boon_sql_save(connection, current.revision, next);
}
