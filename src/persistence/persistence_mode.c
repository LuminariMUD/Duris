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

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static bool fail(char *error, size_t error_size, const char *format, ...)
{
	va_list args;

	if (error && error_size)
	{
		va_start(args, format);
		vsnprintf(error, error_size, format, args);
		va_end(args);
	}
	return false;
}

bool persistence_mode_configure(char *error, size_t error_size)
{
	const char *configured = getenv("PERSISTENCE_MODE");

	if (!configured || !*configured || !strcmp(configured, "mariadb-primary"))
		return true;
	return fail(error, error_size,
		    "invalid PERSISTENCE_MODE '%s'; MariaDB is the only supported backend, "
		    "use mariadb-primary",
		    configured);
}

const char *persistence_mode_name(void)
{
	return "mariadb-primary";
}
