#include "combat/frag_cap_repository.h"

#include <algorithm>
#include <charconv>
#include <cstring>
#include <limits>

namespace
{
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

bool parse(const char *text, int &value)
{
	if (!text)
		return false;
	const char *end = text + strlen(text);
	const auto parsed = std::from_chars(text, end, value);
	return parsed.ec == std::errc() && parsed.ptr == end;
}
}

bool frag_cap_apply_combat(frag_cap_state *state, const critical_command &command,
			   const combat_outcome_payload &payload, int64_t now,
			   const frag_cap_policy &policy)
{
	if (payload.participant_count > payload.participants.size())
		return false;
	std::array<frag_cap_award, COMBAT_OUTCOME_MAX_PARTICIPANTS> awards;
	for (size_t index = 0; index < payload.participant_count; ++index)
		awards[index] = { payload.participants[index].racewar == 1 ? frag_cap_side::good :
				  payload.participants[index].racewar == 2 ? frag_cap_side::evil :
									     frag_cap_side::none,
				  payload.participants[index].frag_delta };
	const int64_t admitted = command.accepted_at_usec <= static_cast<uint64_t>(INT64_MAX) ?
					 static_cast<int64_t>(command.accepted_at_usec) :
					 -1;
	return frag_cap_apply(state, admitted, now, awards.data(), payload.participant_count,
			      policy);
}

frag_cap_store_result frag_cap_sql_load(MYSQL *connection, frag_cap_state *state, bool for_update)
{
	if (!connection || !state)
		return frag_cap_store_result::invalid;
	if (mysql_query(connection, for_update ?
					    "SELECT snapshot FROM level_cap WHERE id=1 FOR UPDATE" :
					    "SELECT snapshot FROM level_cap WHERE id=1"))
		return frag_cap_store_result::io_error;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return frag_cap_store_result::io_error;
	MYSQL_ROW row = mysql_fetch_row(result);
	const unsigned long *lengths = row ? mysql_fetch_lengths(result) : nullptr;
	frag_cap_store_result loaded = frag_cap_store_result::invalid;
	if (row && !row[0])
		loaded = frag_cap_store_result::not_found;
	else if (row && lengths && lengths[0] <= FRAG_CAP_MAX_BYTES &&
		 frag_cap_state_decode({ row[0], row[0] + lengths[0] }, state))
		loaded = frag_cap_store_result::ok;
	mysql_free_result(result);
	return loaded;
}

frag_cap_store_result frag_cap_sql_save(MYSQL *connection, const frag_cap_state &state)
{
	std::vector<uint8_t> bytes;
	if (!connection || !frag_cap_state_encode(state, &bytes))
		return frag_cap_store_result::invalid;
	const int64_t due = frag_cap_due_at(state);
	const std::string sql =
		"UPDATE level_cap SET snapshot=UNHEX('" + hex(bytes) +
		"'),level=" + std::to_string(frag_cap_for_side(state, frag_cap_side::none)) +
		",level_good=" + std::to_string(frag_cap_for_side(state, frag_cap_side::good)) +
		",level_evil=" + std::to_string(frag_cap_for_side(state, frag_cap_side::evil)) +
		",next_update=" +
		(due ? "FROM_UNIXTIME(" + std::to_string(due / 1000000) + ")" :
		       "FROM_UNIXTIME(0)") +
		" WHERE id=1";
	if (mysql_real_query(connection, sql.data(), sql.size()))
		return frag_cap_store_result::io_error;
	const auto affected = mysql_affected_rows(connection);
	if (affected == 1)
		return frag_cap_store_result::ok;
	if (affected != 0)
		return frag_cap_store_result::io_error;
	// Identical after-images report zero changed rows; distinguish a missing row.
	frag_cap_state stored;
	const auto loaded = frag_cap_sql_load(connection, &stored);
	if (loaded != frag_cap_store_result::ok)
		return loaded == frag_cap_store_result::not_found ? frag_cap_store_result::invalid :
								    loaded;
	return stored == state ? frag_cap_store_result::ok : frag_cap_store_result::invalid;
}

frag_cap_store_result frag_cap_sql_adopt(MYSQL *connection, int legacy_floor, int legacy_maximum,
					 int64_t now, frag_cap_state *state,
					 const frag_cap_policy &policy)
{
	const auto loaded = frag_cap_sql_load(connection, state, true);
	if (loaded != frag_cap_store_result::not_found)
		return loaded;
	if (mysql_query(connection,
			"SELECT level,level_good,level_evil,UNIX_TIMESTAMP(next_update) "
			"FROM level_cap WHERE id=1"))
		return frag_cap_store_result::io_error;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return frag_cap_store_result::io_error;
	MYSQL_ROW row = mysql_fetch_row(result);
	int level = 0, good = 0, evil = 0;
	int64_t deadline = 0;
	bool valid = row && parse(row[0], level) && parse(row[1], good) && parse(row[2], evil) &&
		     legacy_floor >= 1 && legacy_floor <= legacy_maximum && legacy_maximum <= 56 &&
		     level >= 1 && level <= 56 && good >= 0 && good <= 56 && evil >= 0 &&
		     evil <= 56;
	if (valid && row[3])
	{
		const char *end = row[3] + strlen(row[3]);
		const auto parsed = std::from_chars(row[3], end, deadline);
		valid = parsed.ec == std::errc() && parsed.ptr == end && deadline >= 0 &&
			deadline <= INT64_MAX / 1000000;
		if (valid)
			deadline *= 1000000;
	}
	mysql_free_result(result);
	frag_cap_state adopted;
	if (!valid || !frag_cap_adopt(&adopted,
				      std::clamp(std::max({ level, good, evil }), legacy_floor,
						 legacy_maximum),
				      deadline, now, policy))
		return frag_cap_store_result::invalid;
	const auto saved = frag_cap_sql_save(connection, adopted);
	if (saved == frag_cap_store_result::ok)
		*state = adopted;
	return saved;
}

frag_cap_store_result frag_cap_sql_reset_season(MYSQL *connection, int64_t reset_started_at,
						const frag_cap_policy &policy)
{
	frag_cap_state current;
	const auto loaded = frag_cap_sql_load(connection, &current, true);
	if (loaded != frag_cap_store_result::ok && loaded != frag_cap_store_result::not_found)
		return loaded;
	if (loaded == frag_cap_store_result::ok && current.credit_cutoff == reset_started_at)
		return frag_cap_store_result::ok;
	if (loaded == frag_cap_store_result::ok &&
	    (current.credit_cutoff > reset_started_at || current.revision == UINT64_MAX))
		return frag_cap_store_result::invalid;
	frag_cap_state fresh;
	if (!frag_cap_adopt(&fresh, FRAG_CAP_INITIAL_LEVEL - 1, 0, reset_started_at, policy))
		return frag_cap_store_result::invalid;
	if (loaded == frag_cap_store_result::ok)
		fresh.revision = current.revision + 1;
	return frag_cap_sql_save(connection, fresh);
}
