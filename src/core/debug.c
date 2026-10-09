
/*
 * ***************************************************************************
 * *  File: debug.c                                            Part of Duris *
 * *  Usage: runtime debugging routines.
 * * *  Copyright 1994 - 2008 - Duris Systems Ltd.
 * *
 * ***************************************************************************
 */

#include <ctype.h>
/*
 * #include <errno.h>
 */
#include "cmd/interp.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>
#include "core/mm.h"
#include "core/profile.h"
#include "ships/ship_npc_ai.h"
#include "ships/ships.h"

/*
 * external variables
 */

extern P_char character_list;
extern P_desc descriptor_list;
extern P_room world;
extern const int top_of_world;

extern mm_ds_list *mmds_list;
extern mem_usage mem_used[];
extern long allocation_list_node_count;
extern const char *command[];

char debug_mode = 1;
uint logcount = 0;

/*
 * called once per game_loop
 */

void loop_debug(void)
{
	FILE *fl;
	P_desc d;

	fl = fopen("logs/log/loop.debug", "w");

	for (d = descriptor_list; d; d = d->next)
	{
		if (d->character)
		{
			if (d->character->in_room >= 0 && d->character->in_room < top_of_world)
				fprintf(fl, "%s m[%d] r[%d] v[%d]\n", GET_NAME(d->character),
					d->connected, d->character->in_room,
					world[d->character->in_room].number);
			else
				fprintf(fl, "%s m[%d] r[NOWHERE]\n", GET_NAME(d->character),
					d->connected);
		}
		else
			fprintf(fl, "[No name] m[%d]\n", d->connected);
	}
	fclose(fl);
}

void hour_debug(void) {}

// The last CMDLOG_LINES player commands. They are kept in memory: writing each to
// logs/log/cmd.debug as it came held the game loop, before every command, for as long as
// a busy disk held the write. write_cmdlog() puts them in the file when the server exits
// or crashes.
#define CMDLOG_LINES 500
static char cmdlog_lines[CMDLOG_LINES][256];

// Makes only calls a signal handler may make: a crash writes the log too.
void write_cmdlog(void)
{
	const int fd = open("logs/log/cmd.debug", O_WRONLY | O_CREAT | O_TRUNC, 0644);
	if (fd < 0)
		return;
	// Oldest first. Once the ring is full, the next line to be replaced is the oldest.
	const uint count = logcount < CMDLOG_LINES ? logcount : CMDLOG_LINES;
	for (uint i = logcount - count; i != logcount; i++)
	{
		const char *line = cmdlog_lines[i % CMDLOG_LINES];
		const ssize_t written = write(fd, line, strlen(line));
		(void)written;
	}
	close(fd);
}

void init_cmdlog(void)
{
	atexit(write_cmdlog);
}

/* Players' conversation is not logged (ADR 0003): a say, tell or other conversation command
 * keeps its command word in cmd.debug and drops its text. Returns the length to keep, or -1
 * to keep the whole line. */
static int cmdlog_kept_length(const char *str)
{
	char word[MAX_INPUT_LENGTH];
	int begin = 0, length = 0;

	while (str[begin] == ' ')
		begin++;
	/* "'" and ":" are say and emote, with or without a space before the text. */
	if (str[begin] == '\'' || str[begin] == ':')
		return begin + 1;
	while (str[begin + length] > ' ' && length < (int)sizeof(word) - 1)
	{
		word[length] = LOWER(str[begin + length]);
		length++;
	}
	word[length] = '\0';
	switch (old_search_block(word, 0, length, command, 2))
	{
	case CMD_SAY:
	case CMD_TELL:
	case CMD_REPLY:
	case CMD_WHISPER:
	case CMD_ASK:
	case CMD_EMOTE:
	case CMD_PROJECT:
	case CMD_BEEP:
	case CMD_GSAY:
	case CMD_GCC:
	case CMD_ACC:
	case CMD_JESTROS:
	case CMD_SHOUT:
		return begin + length;
	default:
		return -1;
	}
}

void cmdlog(P_char ch, char *str)
{
	char tbuf[30];
	time_t ct;

	if (!ch || !ch->player.name)
	{
		logit(LOG_EXIT, "bogus char in call to cmdlog");
		return;
	}
	if (IS_NPC(ch))
		return;
	// A one-letter command (n, s, k) is a command; an empty line is not.
	if (*str != '\0')
	{
		char *line = cmdlog_lines[logcount % CMDLOG_LINES];
		logcount++;
		ct = time(0);
		strcpy(tbuf, asctime(localtime(&ct)));
		tbuf[strlen(tbuf) - 1] = '\0';
		char withheld[64]; // a command word and the note
		const char *text = str;
		int kept = cmdlog_kept_length(str);
		if (kept >= 0)
		{
			static const char note[] = " <text withheld>";
			kept = MIN(kept, (int)(sizeof withheld - sizeof note));
			memcpy(withheld, str, kept);
			memcpy(withheld + kept, note, sizeof note);
			text = withheld;
		}
		// A command too long for the line is cut, and still ends its line.
		if (snprintf(line, sizeof cmdlog_lines[0], "%s :: [%u] %s in %d: %s\n", tbuf,
			     logcount, GET_NAME(ch), world[ch->in_room].number,
			     text) >= (int)sizeof cmdlog_lines[0])
			line[sizeof cmdlog_lines[0] - 2] = '\n';
	}
}

void do_debug(P_char ch, char *argument, int /*cmd*/)
{
	char arg1[MAX_STRING_LENGTH], arg2[MAX_STRING_LENGTH];
	if (*argument)
	{
		half_chop(argument, arg1, arg2);
		if (isname(arg1, "profile"))
		{
#ifdef DO_PROFILE
			if (isname(arg2, "on"))
			{
				if (!do_profile)
				{
					PROFILES(REBASE);
					do_profile = true;
					send_to_char("Profiling mode is now ON.\r\n", ch);
				}
				else
					send_to_char("Profiling mode is already ON.\r\n", ch);
			}
			else if (isname(arg2, "off"))
			{
				if (do_profile)
				{
					do_profile = false;
					send_to_char("Profiling mode is now OFF.\r\n", ch);
				}
				else
					send_to_char("Profiling mode is already OFF.\r\n", ch);
			}
			else if (isname(arg2, "reset"))
			{
				send_to_char("Resetting profiling results.\r\n", ch);
				PROFILES(RESET);
				reset_func_call_info();
			}
			else if (isname(arg2, "save"))
			{
				send_to_char("Saving profiling results.\r\n", ch);
				PROFILES(SAVE);
				save_func_call_info();
			}
			else
			{
				send_to_char("Syntex: debug profile <on|off|reset|save>.\r\n", ch);
			}
#else
			send_to_char("Profiling is not defined.\r\n", ch);
#endif
			return;
		}
		if (isname(arg1, "ship"))
		{
			ShipVisitor svs;
			if (isname(arg2, "off"))
			{
				for (bool fn = shipObjHash.get_first(svs); fn;
				     fn = shipObjHash.get_next(svs))
				{
					P_ship ship = svs;
					if (ship->npc_ai && ship->npc_ai->debug_char == ch)
					{
						ship->npc_ai->debug_char = 0;
						send_to_char("Done.\r\n", ch);
					}
				}
				return;
			}
			else
			{
				for (bool fn = shipObjHash.get_first(svs); fn;
				     fn = shipObjHash.get_next(svs))
				{
					P_ship ship = svs;
					if (isname(arg2, ship->id))
					{
						if (!ship->npc_ai)
						{
							send_to_char(
								"This ship is not under NPC control, nothing to debug.\r\n",
								ch);
							return;
						}
						ship->npc_ai->debug_char = ch;
						return;
					}
				}
				send_to_char("No ship with such id in game.\r\n", ch);
				return;
			}
		}
	}
	if (debug_mode)
	{
		debug_mode = 0;
		send_to_char("Debug mode is now OFF.\r\n", ch);
		statuslog(ch->player.level, "debug mode OFF.");
	}
	else
	{
		debug_mode = 1;
		send_to_char("Debug mode is now ON.\r\n", ch);
		statuslog(ch->player.level, "debug mode ON.");
	}
}

#ifdef MEM_DEBUG

void do_mreport(P_char ch, char * /*argument*/, int /*cmd*/)
{
#ifdef MEMCHK
	char buf[MAX_STRING_LENGTH] = "";
	struct mm_ds *mmds = NULL;
	struct mm_ds_list *mmlist;
	size_t mm_active, mm_inactive, mm_allocated, mm_wasted, total_allocs = 0, total_size = 0;

	if (!ch || !ch->desc || !IS_TRUSTED(ch))
		return;

	snprintf(buf, MAX_STRING_LENGTH, "&+CDirectly allocated memory:&N\n");
	checked_snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
			 "  &+WTag       &+BAllocations       &+YSize&n\n");
	checked_snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
			 "------------------------------------\n");
	for (int i = 0; i < 52; i++)
	{
		if (!mem_used[i].allocs)
			continue;
		checked_snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
				 " &+W%4s          &+B%10ld       &+Y%14ld&n\n", mem_used[i].tag,
				 (long)mem_used[i].allocs, (long)mem_used[i].size);
		total_allocs += mem_used[i].allocs;
		total_size += mem_used[i].size;
	}
	checked_snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
			 "------------------------------------\n");
	checked_snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
			 "             &+B%10ld     &+Y%14ld&n\n", (long)total_allocs,
			 (long)total_size);
	checked_snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
			 "\n&+WAllocation header consumption: %s\n",
			 comma_string((total_allocs * sizeof(ALLOCATION_HEADER))));
	total_size += total_allocs * sizeof(ALLOCATION_HEADER);

	checked_snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
			 "\n&+CPooled memory resources:&N\n");

#ifdef MM_STATS

	checked_snprintf(
		buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
		" &+WType      &+C|&+W  Active Objects       &+C|&+W  Inactive Objects     &+C|&+W  Pages Owned         &+C|&+W  Waste&N\n");

	mm_active = mm_inactive = mm_allocated = mm_wasted = 0;

	for (mmlist = mmds_list; mmlist; mmlist = mmlist->next)
	{
		size_t owned_memory, active_memory, inactive_memory;

		mmds = mmlist->mmds;

		owned_memory = (mmds->pages_owned * 4096);
		total_size += owned_memory;
		active_memory = (mmds->objs_used * mmds->size);
		inactive_memory = (owned_memory - mmds->bytes_wasted - active_memory);

		checked_snprintf(
			buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
			" %10s &+C|&n %6ld (%12ld) &+C|&N %6ld (%12ld) &+C|&N %6ld (%12ld) &+C|&n %7ld\n",
			mmds->name, (long)mmds->objs_used, (long)active_memory,
			(long)(inactive_memory / mmds->size), (long)inactive_memory,
			(long)mmds->pages_owned, (long)owned_memory, (long)mmds->bytes_wasted);

		mm_active += active_memory;
		mm_inactive += inactive_memory;
		mm_allocated += owned_memory;
		mm_wasted += mmds->bytes_wasted;
	}
	checked_snprintf(
		buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
		" &+WTOTALS  &+C|&+Y         %12ld  &+C|&+Y         %12ld  &+C|&+Y        %12ld  &+C|&+Y %7ld&N\n",
		(long)mm_active, (long)mm_inactive, (long)mm_allocated, (long)mm_wasted);

#else
	snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
		 "&+CMM_STATS not compiled in!&N\r\n");
#endif

	checked_snprintf(buf + strlen(buf), MAX_STRING_LENGTH - strlen(buf),
			 "\n&+WTotal bytes used: &+C%s&n\n", comma_string(total_size));

	send_to_char(buf, ch);
#else
	send_to_char("Memory checking not available.  Rebuild with MEMCHK defined.\n", ch);
#endif
}
#endif
