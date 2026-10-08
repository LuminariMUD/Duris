/****************************************************************************
 *
 *  File: session_audit_repository.c                            Part of Duris
 *  Usage: SQL session audit repository
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "account/session_audit_repository.h"

#include <cerrno>
#include <mysql.h>
#include <string>

namespace
{
std::string bytes_hex(const uint8_t *bytes, size_t size)
{
	static const char HEX[] = "0123456789abcdef";
	std::string result(size * 2, '0');
	for (size_t index = 0; index < size; ++index)
	{
		result[index * 2] = HEX[bytes[index] >> 4];
		result[index * 2 + 1] = HEX[bytes[index] & 15];
	}
	return result;
}
} // namespace

bool session_audit_repository_execute(MYSQL *connection, const critical_command &command,
				      session_audit_result *result)
{
	if (!critical_command_valid(command))
	{
		errno = EPROTONOSUPPORT;
		return false;
	}

	if (!connection || !result || !session_audit_command_decode_payload(command, result))
	{
		errno = EINVAL;
		return false;
	}
	const std::string operation =
		bytes_hex(command.operation_id.bytes.data(), command.operation_id.bytes.size());
	const std::string sql =
		"INSERT INTO session_audit_outcome(operation_id,pid,event_type,occurred_at) "
		"VALUES(UNHEX('" +
		operation + "')," + std::to_string(result->pid) + "," +
		std::to_string(static_cast<unsigned int>(result->event)) + ",FROM_UNIXTIME(" +
		std::to_string(result->occurred_at) + "))";
	return mysql_real_query(connection, sql.data(), sql.size()) == 0;
}
