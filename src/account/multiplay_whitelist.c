/****************************************************************************
 *
 *  File: multiplay_whitelist.c                                 Part of Duris
 *  Usage: the multiplay whitelist: encoding, storage, and checks
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utility.h"
#include "core/utils.h"
#include "account/multiplay_whitelist.h"
#include <algorithm>
#include <cctype>
#include <ctime>
#include <string.h>
#include "sql/sql.h"

#include "sql/sql_async.h"

// The whitelist, read at boot and kept current by the staff's changes, which are queued on
// the writer: only the game writes it.
static vector<whitelist_data> stored_whitelist;

namespace
{
string trimmed(const char *value)
{
	if (!value)
		return {};
	const unsigned char *begin = reinterpret_cast<const unsigned char *>(value);
	while (*begin && isspace(*begin))
		++begin;
	const unsigned char *end = begin + strlen(reinterpret_cast<const char *>(begin));
	while (end > begin && isspace(end[-1]))
		--end;
	return string(reinterpret_cast<const char *>(begin), reinterpret_cast<const char *>(end));
}

bool current_date(string *value)
{
	if (!value)
		return false;
	const time_t now = time(nullptr);
	struct tm local = {};
	char date[11];
	if (now == static_cast<time_t>(-1) || !localtime_r(&now, &local) ||
	    strftime(date, sizeof(date), "%Y-%m-%d", &local) != 10)
		return false;
	*value = date;
	return true;
}
} // namespace

extern P_desc descriptor_list;

bool whitelisted_host(const char *host)
{
	vector<whitelist_data> whitelist = get_whitelist();

	for (vector<whitelist_data>::iterator it = whitelist.begin(); it != whitelist.end(); it++)
	{
		if (match_pattern(it->pattern.c_str(), host))
			return true;
	}

	return false;
}

vector<whitelist_data> get_whitelist()
{
	vector<whitelist_data> whitelist;

	return stored_whitelist;
}

// Boot only: the game loop is not running yet.
bool whitelist_load(void)
{
	MYSQL_RES *res =
		db_query("SELECT id, created_on, pattern, player, admin, description FROM %s",
			 MULTIPLAY_WHITELIST_TABLE_NAME);
	if (!res)
		return false;
	stored_whitelist.clear();
	while (MYSQL_ROW row = mysql_fetch_row(res))
		stored_whitelist.push_back(whitelist_data(
			atoi(row[0]), row[1] ? row[1] : "", row[2] ? row[2] : "",
			row[3] ? row[3] : "", row[4] ? row[4] : "", row[5] ? row[5] : ""));
	mysql_free_result(res);
	return true;
}

bool add_to_whitelist(P_char ch, const char *player, const char *pattern, const char *description)
{
	string created_on;
	if (!ch || !GET_NAME(ch) || !current_date(&created_on))
		return false;
	const whitelist_data entry(0, created_on, trimmed(pattern), trimmed(player),
				   trimmed(GET_NAME(ch)), trimmed(description));
	if (!sql_queue(
		    "INSERT INTO %s (created_on, admin, player, pattern, description) VALUES ('%s', '%s', '%s', '%s', '%s')",
		    MULTIPLAY_WHITELIST_TABLE_NAME, created_on.c_str(),
		    escape_str(entry.admin.c_str()).c_str(),
		    escape_str(entry.player.c_str()).c_str(),
		    escape_str(entry.pattern.c_str()).c_str(),
		    escape_str(entry.description.c_str()).c_str()))
	{
		logit(LOG_DEBUG, "add_to_whitelist(): the write could not be queued");
		return false;
	}
	stored_whitelist.push_back(entry);

	sql_log(ch, WIZLOG, "Added '%s' (%s: %s) to multiplay whitelist", pattern, player,
		description);
	return true;
}

bool remove_from_whitelist(P_char ch, const char *pattern)
{
	const string saved_pattern = trimmed(pattern);
	if (!sql_queue("DELETE FROM %s WHERE pattern = '%s'", MULTIPLAY_WHITELIST_TABLE_NAME,
		       escape_str(saved_pattern.c_str()).c_str()))
	{
		logit(LOG_DEBUG, "remove_from_whitelist(): the write could not be queued");
		return false;
	}
	stored_whitelist.erase(remove_if(stored_whitelist.begin(), stored_whitelist.end(),
					 [&](const whitelist_data &entry)
					 { return entry.pattern == saved_pattern; }),
			       stored_whitelist.end());

	sql_log(ch, WIZLOG, "Removed '%s' from multiplay whitelist", pattern);
	return true;
}

void do_whitelist_help(P_char ch)
{
	send_to_char("usage: whitelist\r\n"
		     "       whitelist add <player> <*.*.*.* ip address pattern> <description>\r\n"
		     "       whitelist remove <ip address pattern>\r\n\r\n",
		     ch);
}

bool is_connected(const char *pattern)
{
	for (P_desc k = descriptor_list; k; k = k->next)
	{
		if (match_pattern(pattern, k->host))
		{
			return true;
		}
	}
	return false;
}

void do_whitelist(P_char ch, char *argument, int /*cmd*/)
{
	char argbuf[MAX_STRING_LENGTH], linebuf[MAX_STRING_LENGTH];

	if (IS_NPC(ch) || !IS_TRUSTED(ch))
		return;

	argument = one_argument(argument, argbuf);

	if (!*argbuf)
	{
		// no arguments: list existing whitelist
		vector<whitelist_data> whitelist = get_whitelist();

		send_to_char(
			" Host pattern    | Added by     | On         | Player       | Description\r\n"
			"-----------------------------------------------------------------------------\r\n",
			ch);
		//               " 127.345.234.113 | Torgal       | 2009-12-22 | Zion         | Contacted by email, brothers who play from same net"

		for (vector<whitelist_data>::iterator it = whitelist.begin(); it != whitelist.end();
		     it++)
		{
			snprintf(linebuf, MAX_STRING_LENGTH, " %s%s | %s | %s | %s | %s&n\r\n",
				 (is_connected(it->pattern.c_str()) ? string("&+R").c_str() : ""),
				 pad_ansi(it->pattern.c_str(), 15).c_str(),
				 pad_ansi(it->admin.c_str(), 12).c_str(),
				 pad_ansi(it->created_on.c_str(), 10).c_str(),
				 pad_ansi(it->player.c_str(), 12).c_str(), it->description.c_str());

			send_to_char(linebuf, ch);
		}

		return;
	}
	else if (!strcmp(argbuf, "add"))
	{
		// argument should be: <player> <ip pattern> <description>
		char player[MAX_STRING_LENGTH];
		char pattern[MAX_STRING_LENGTH];

		argument = one_argument(argument, player);

		if (!(*player))
		{
			send_to_char("Missing player name\r\n", ch);
			do_whitelist_help(ch);
			return;
		}

		argument = one_argument(argument, pattern);

		if (!(*pattern) || !match_pattern("*.*.*.*", pattern))
		{
			send_to_char("Invalid host pattern.\r\n", ch);
			do_whitelist_help(ch);
			return;
		}

		if (!(*argument))
		{
			send_to_char("Missing description.\r\n", ch);
			do_whitelist_help(ch);
			return;
		}

		if (add_to_whitelist(ch, player, pattern, argument))
		{
			send_to_char("Host pattern added to multiplay whitelist.\r\n", ch);
		}
		else
		{
			send_to_char(
				"ERROR: host pattern could not be added to multiplay whitelist.\r\n",
				ch);
		}

		return;
	}
	else if (!strcmp(argbuf, "remove"))
	{
		// argument should be: <*.*.*.* pattern>

		if (!match_pattern("*.*.*.*", argument))
		{
			send_to_char("Invalid host pattern.\r\n", ch);
			do_whitelist_help(ch);
			return;
		}

		if (remove_from_whitelist(ch, argument))
		{
			send_to_char("Host pattern removed from multiplay whitelist.\r\n", ch);
		}
		else
		{
			send_to_char(
				"Host pattern not found or could not be removed from multiplay whitelist.\r\n",
				ch);
		}

		return;
	}
	else
	{
		do_whitelist_help(ch);
		return;
	}
}
