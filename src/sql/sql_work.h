/****************************************************************************
 *
 *  File: sql_work.h                                            Part of Duris
 *  Usage: SQL work row type
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef SQL_WORK_H
#define SQL_WORK_H

#include <mysql/mysql.h>

#include <cstddef>
#include <functional>
#include <optional>
#include <string>
#include <vector>

// One row a read returned, copied off its connection.
struct sql_row
{
	std::vector<std::optional<std::string>> fields;

	// The field as the C API gives it: NULL for SQL NULL or a column past the end.
	const char *operator[](size_t index) const
	{
		return index < fields.size() && fields[index] ? fields[index]->c_str() : nullptr;
	}
};

using sql_rows = std::vector<sql_row>;

// SQL run on the writer's connection (sql_async.h queues it). It returns 0 or the MySQL
// error that failed it, and must not touch the game's state: it captures what it needs
// by value.
using sql_work = std::function<unsigned int(MYSQL *connection)>;

// For sql_work: one statement, or one read whose rows are appended to *rows.
unsigned int sql_execute(MYSQL *connection, const std::string &statement);
unsigned int sql_select(MYSQL *connection, const std::string &query, sql_rows *rows);

#endif
