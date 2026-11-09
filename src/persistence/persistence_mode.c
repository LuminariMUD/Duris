/****************************************************************************
 *
 *  File: persistence_mode.c                                    Part of Duris
 *  Usage: selects and provisions the persistence mode
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

#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static enum persistence_mode active_mode = PERSISTENCE_MODE_MARIADB_PRIMARY;
static const char *active_flatfile_root;

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

	active_flatfile_root = NULL;
	if (!configured || !*configured || !strcmp(configured, "mariadb-primary"))
		active_mode = PERSISTENCE_MODE_MARIADB_PRIMARY;
	else if (!strcmp(configured, "mariadb-primary-flatfile-fallback"))
		active_mode = PERSISTENCE_MODE_MARIADB_PRIMARY_FLATFILE_FALLBACK;
	else if (!strcmp(configured, "flatfile-primary"))
		active_mode = PERSISTENCE_MODE_FLATFILE_PRIMARY;
	else
		return fail(error, error_size,
			    "invalid PERSISTENCE_MODE '%s'; expected mariadb-primary, "
			    "mariadb-primary-flatfile-fallback, or flatfile-primary",
			    configured);

	if (active_mode == PERSISTENCE_MODE_MARIADB_PRIMARY)
	{
		return true;
	}

	if (active_mode == PERSISTENCE_MODE_MARIADB_PRIMARY_FLATFILE_FALLBACK)
		return fail(error, error_size,
			    "persistence mode mariadb-primary-flatfile-fallback is not supported; "
			    "select mariadb-primary or flatfile-primary explicitly");

	return fail(error, error_size,
		    "persistence mode flatfile-primary requires a client-free flatfile build");
}

enum persistence_mode persistence_mode_get(void)
{
	return active_mode;
}

const char *persistence_mode_name(void)
{
	switch (active_mode)
	{
	case PERSISTENCE_MODE_MARIADB_PRIMARY:
		return "mariadb-primary";
	case PERSISTENCE_MODE_MARIADB_PRIMARY_FLATFILE_FALLBACK:
		return "mariadb-primary-flatfile-fallback";
	case PERSISTENCE_MODE_FLATFILE_PRIMARY:
		return "flatfile-primary";
	}
	return "invalid";
}

bool persistence_mode_requires_mysql(void)
{
	return active_mode != PERSISTENCE_MODE_FLATFILE_PRIMARY;
}

const char *persistence_mode_flatfile_root(void)
{
	return active_flatfile_root;
}
