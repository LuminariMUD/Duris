/****************************************************************************
 *
 *  File: timers.c                                              Part of Duris
 *  Usage: named player timers: encoding, storage, and queued saves
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "world/timers.h"
#include "guild/assocs.h"
#include "world/epic.h"
#include "ships/ships.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "core/utility.h"
#include <stdlib.h>

void set_timer(const char *name)
{
	set_timer(name, time(NULL));
}

// Queued on the writer, in capture order with the saves.
void set_timer(const char *name, int date)
{
	if (!sql_queue("REPLACE INTO timers (name, date) VALUES ('%s', '%d')", name, date))
		logit(LOG_DEBUG, "set_timer: failed to queue timer %s", name ? name : "<null>");
}

// Boot only (the cargo market's last updates); the game loop reads no timer.
int get_timer(const char *name)
{
	if (!qry("SELECT date FROM timers WHERE name = '%s'", name))
	{
		return 0;
	}

	MYSQL_RES *res = mysql_store_result(DB);
	if (!res)
	{
		logit(LOG_DEBUG, "%s: mysql_store_result failed", __func__);
		return FALSE;
	}

	if (mysql_num_rows(res) < 1)
	{
		mysql_free_result(res);
		return 0;
	}

	MYSQL_ROW row = mysql_fetch_row(res);

	int date = atoi(row[0]);
	mysql_free_result(res);

	return date;
}

bool has_elapsed(const char *name, int seconds)
{
	int timer = get_timer(name);

	if (time(NULL) > (timer + seconds))
	{
		return TRUE;
	}
	else
	{
		return FALSE;
	}
}

void timers_activity()
{
	//  prestige_update();
	cargo_activity();
}
