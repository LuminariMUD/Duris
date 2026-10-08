/****************************************************************************
 *
 *  File: sql_migrate.h                                         Part of Duris
 *  Usage: schema migration note: migrations run outside the server
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Zusuk                                      Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef __SQL_MIGRATE_H__
#define __SQL_MIGRATE_H__

/*
 * Schema migrations are handled externally by shell scripts / release
 * tooling. The in-process auto-runner was removed.
 */

#ifndef __NO_MYSQL__
#include <mysql.h>
#endif

static inline int sql_run_migrations(void *db, const char *migrations_dir)
{
	(void)db;
	(void)migrations_dir;
	return 0;
}

#endif /* __SQL_MIGRATE_H__ */
