/****************************************************************************
 *
 *  File: persistence_mode.c                                    Part of Duris
 *  Usage: validates the configured persistence mode
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "persistence/persistence_mode.h"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <string>

bool persistence_mode_configure(char *error, size_t error_size)
{
	const char *configured = getenv("PERSISTENCE_MODE");

	if (!configured || !*configured || !strcmp(configured, "mariadb-primary"))
		return true;
	if (error && error_size)
	{
		const std::string message =
			std::string("invalid PERSISTENCE_MODE '") + configured +
			"'; MariaDB is the only supported backend, use mariadb-primary";
		const size_t length = std::min(message.size(), error_size - 1);
		memcpy(error, message.data(), length);
		error[length] = '\0';
	}
	return false;
}

const char *persistence_mode_name(void)
{
	return "mariadb-primary";
}
