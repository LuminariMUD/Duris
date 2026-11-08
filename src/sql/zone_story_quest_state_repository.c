/****************************************************************************
 *
 *  File: zone_story_quest_state_repository.c                   Part of Duris
 *  Usage: SQL zone story quest state repository, read at boot
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "sql/zone_story_quest_state_repository.h"

#include "sql/sql.h"

#include <cerrno>
#include <cstdlib>
#include <limits>

#ifndef __NO_MYSQL__
#include "sql/sql_async.h"

#include <cstdlib>
#include <mysql.h>
#endif

sql_zone_story_quest_state_result
sql_zone_story_quest_state_load(uint32_t expected_catalog_revision, std::string *state,
				std::string *error)
{
	if (!expected_catalog_revision || !state)
	{
		if (error)
			*error = "zone-story SQL state output is null";
		return sql_zone_story_quest_state_result::invalid;
	}
#ifdef __NO_MYSQL__
	if (error)
		*error = "SQL state repository is unavailable in a flat-file build";
	return sql_zone_story_quest_state_result::io_error;
#else
	// Boot only (zone_story_quest_runtime::bootstrap()).
	MYSQL_RES *result = db_query("SELECT state_version,catalog_revision,state_blob "
				     "FROM zone_story_quest_state WHERE state_id=1 LIMIT 1");
	if (!result)
	{
		if (error)
			*error = "zone-story SQL state query failed";
		return sql_zone_story_quest_state_result::io_error;
	}
	MYSQL_ROW row = mysql_fetch_row(result);
	unsigned long *lengths = mysql_fetch_lengths(result);
	if (!row)
	{
		mysql_free_result(result);
		return sql_zone_story_quest_state_result::not_found;
	}
	if (!row[0] || !row[1] || !row[2] || !lengths)
	{
		mysql_free_result(result);
		if (error)
			*error = "zone-story SQL state row is null";
		return sql_zone_story_quest_state_result::invalid;
	}
	char *version_end = nullptr;
	char *revision_end = nullptr;
	errno = 0;
	const unsigned long version = std::strtoul(row[0], &version_end, 10);
	const int version_errno = errno;
	errno = 0;
	const unsigned long revision = std::strtoul(row[1], &revision_end, 10);
	const int revision_errno = errno;
	if (version_errno || revision_errno || version_end == row[0] || revision_end == row[1] ||
	    *version_end || *revision_end || version != 1 ||
	    revision != expected_catalog_revision ||
	    revision > std::numeric_limits<uint32_t>::max())
	{
		mysql_free_result(result);
		if (error)
			*error = "zone-story SQL state schema or catalog revision is invalid";
		return sql_zone_story_quest_state_result::invalid;
	}
	state->assign(row[2], lengths[2]);
	mysql_free_result(result);
	MYSQL_RES *parts = db_query("SELECT part_blob FROM zone_story_quest_state_part "
				    "ORDER BY part_index");
	if (!parts)
	{
		if (error)
			*error = "zone-story SQL state part query failed";
		return sql_zone_story_quest_state_result::io_error;
	}
	while (MYSQL_ROW part = mysql_fetch_row(parts))
		state->append(part[0], mysql_fetch_lengths(parts)[0]);
	mysql_free_result(parts);
	return sql_zone_story_quest_state_result::ok;
#endif
}

sql_zone_story_quest_state_result
sql_zone_story_quest_state_save(uint32_t catalog_revision,
				std::vector<std::shared_ptr<const std::string>> parts,
				size_t unshared_bytes, std::string *error)
{
	/* Each part is saved in its own statement, below the 16 MiB packet and column limits;
	 * the document as a whole has no such limit. */
	if (!catalog_revision || parts.empty())
	{
		if (error)
			*error = "zone-story SQL state is invalid";
		return sql_zone_story_quest_state_result::invalid;
	}
#ifdef __NO_MYSQL__
	(void)catalog_revision;
	(void)unshared_bytes;
	if (error)
		*error = "SQL state repository is unavailable in a flat-file build";
	return sql_zone_story_quest_state_result::io_error;
#else
	// Queued on the writer, in capture order with the saves; the writer logs a failure.
	// It escapes and formats the parts too, which the game thread must not pay for. Only
	// the parts this save alone keeps alive count against the writer's limit. The writer
	// runs the work in one transaction, so a load never sees a partly saved document.
	const bool queued = sql_queue_sized_work(
		unshared_bytes,
		[catalog_revision, parts = std::move(parts)](MYSQL *connection) -> unsigned int
		{
			const auto escape = [connection](const std::string &part)
			{
				std::string escaped(part.size() * 2 + 1, '\0');
				escaped.resize(mysql_real_escape_string(connection, escaped.data(),
									part.data(), part.size()));
				return escaped;
			};
			unsigned int failed = sql_execute(
				connection,
				sql_format(
					"INSERT INTO zone_story_quest_state (state_id,state_version,catalog_revision,state_blob,updated_at) "
					"VALUES (1,1,%u,'%s',UTC_TIMESTAMP(6)) "
					"ON DUPLICATE KEY UPDATE state_version=VALUES(state_version), "
					"catalog_revision=VALUES(catalog_revision),state_blob=VALUES(state_blob),updated_at=VALUES(updated_at)",
					catalog_revision, escape(*parts[0]).c_str()));
			for (size_t index = 1; !failed && index < parts.size(); ++index)
				failed = sql_execute(
					connection,
					sql_format(
						"INSERT INTO zone_story_quest_state_part (part_index,part_blob) "
						"VALUES (%zu,'%s') ON DUPLICATE KEY UPDATE part_blob=VALUES(part_blob)",
						index, escape(*parts[index]).c_str()));
			return failed ?
				       failed :
				       sql_execute(
					       connection,
					       sql_format(
						       "DELETE FROM zone_story_quest_state_part WHERE part_index>=%zu",
						       parts.size()));
		});
	if (!queued)
	{
		if (error)
			*error = "zone-story SQL state write could not be queued";
		return sql_zone_story_quest_state_result::io_error;
	}
	return sql_zone_story_quest_state_result::ok;
#endif
}
