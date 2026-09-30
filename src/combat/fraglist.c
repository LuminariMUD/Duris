#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include "guild/assocs.h"
#include "core/config.h"
#include "combat/frag_cap_config.h"
#include "redis/redis_report_cache.h"
#include "ships/ships.h"
#include "magic/spells.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#define MAX_FRAG_SIZE 10 /* max size of high/low lists */

extern const struct class_names class_names_table[];
extern const struct race_names race_names_table[];
extern P_char misfire_check(P_char ch, P_char spell_target, int flag);

extern P_room world;
extern const racewar_struct racewar_color[MAX_RACEWAR + 2];

extern void get_level_cap_info(long *max_frags, int *racewar, int *level, time_t *next_update);
extern int sql_level_cap(int racewar_side);

/*
 * fragWorthy - is ch worthy of gaining a frag and victim worthy of losing
 *              one?
 */

int fragWorthy(P_char ch, P_char victim)
{
	int racew;

	if (IS_NPC(victim))
		return FALSE;

	if (IS_NPC(ch))
	{
		if (ch->following && IS_PC(ch->following))
			ch = ch->following;
		else
			return FALSE;
	}

	if ((GET_LEVEL(ch) > 56) || (GET_LEVEL(victim) > 56))
		return FALSE;

	if (CHAR_IN_ARENA(ch) || CHAR_IN_ARENA(victim))
		return FALSE;

	/* killing people under 20 - no frag.  killing people more than 10
	   levels under you - no frag. */

	/* non-floating point floating point system, dig it?  100 frags = 1.00 */
	/* Commenting this out for the 2017 wipe.
	  if ((ch->only.pc->frags > 2000) && (GET_LEVEL(victim) < 40))
	    return FALSE;
	*/

	if (GET_LEVEL(victim) < 20)
		return FALSE;

	racew = (opposite_racewar(ch, victim) /* || (IS_ILLITHID(ch) && !IS_ILLITHID(victim)) ||
	                                         (IS_DISGUISE(victim) && (EVIL_RACE(victim) != EVIL_RACE(ch))) */
	);

	if (!racew)
		return FALSE;

	/* Kvark adding harder check for frags, connected to missfire. */
	/*
	  misfire_check(ch, victim,
	                  DISALLOW_SELF | DISALLOW_BACKRANK);

	  if(!affected_by_spell(ch, TAG_NOMISFIRE))
	  {
	      send_to_char("&+WThis kind of frag counts as nothing, go prove your self in a fair fight instead.&n\n", ch);
	                return FALSE;

	  }
	*/
	/*
	else
	{
	 for (tch = world[ch->in_room].people; tch; tch = tch->next_in_room)
	 {
	  if(tch)
	   if (tch != ch)
	    if(opposite_racewar(victim, tch) && !IS_TRUSTED(tch))
	     if(!affected_by_spell(tch, TAG_NOMISFIRE)){
	        send_to_char("This kind of frag counts as nothing, blame your firends.", tch);
	        return FALSE;
	     }
	 }

	}
	*/

	if (victim->only.pc->frags > 500)
		return TRUE;

	if (racew && (victim->only.pc->frags > 200))
		return TRUE;

	if ((GET_LEVEL(victim) + 10) < GET_LEVEL(ch))
		return FALSE;

	return racew;
	/*  if (racew) return TRUE;

	  if (IS_ILLITHID(ch) && !IS_ILLITHID(victim)) return TRUE;

	  return FALSE;*/
}

// Flags ch at the top or bottom of the overall fraglist, from the leaderboard read on the
// writer, behind the update queued before it.
static void check_frag_position(P_char ch)
{
	if (!ch || IS_NPC(ch))
		return;

	const uint64_t runtime_id = ch->runtime_id;
	sql_read("(SELECT 'lead', char_name FROM frag_leaderboard "
		 "WHERE deleted_at IS NULL AND total_frags > 0 "
		 "ORDER BY total_frags DESC, id ASC LIMIT 1) UNION ALL "
		 "(SELECT 'low', char_name FROM frag_leaderboard "
		 "WHERE deleted_at IS NULL ORDER BY total_frags ASC LIMIT 1)",
		 [runtime_id](bool ok, const sql_rows &rows)
		 {
			 P_char live = find_character_by_runtime_id(runtime_id);
			 if (!ok || !live)
				 return;
			 bool lead = false, low = false;
			 for (const sql_row &row : rows)
				 if (row[0] && row[1] && isname(row[1], GET_NAME(live)))
					 (strcmp(row[0], "lead") ? low : lead) = true;
			 if (lead)
				 SET_BIT(live->specials.act3, PLR3_FRAGLEAD);
			 else
				 REMOVE_BIT(live->specials.act3, PLR3_FRAGLEAD);
			 if (low)
				 SET_BIT(live->specials.act3, PLR3_FRAGLOW);
			 else
				 REMOVE_BIT(live->specials.act3, PLR3_FRAGLOW);
		 });
}

// Shows the frag totals by side and the fraglist matching filter, both read on the writer.
static void show_fraglist(P_char ch, const std::string &filter)
{
	sql_read_work_for(
		ch,
		[filter](MYSQL *connection, sql_rows *rows) -> unsigned int
		{
			if (const unsigned int error_code = sql_select(
				    connection,
				    "SELECT 'total', racewar, SUM(total_frags) FROM frag_leaderboard "
				    "GROUP BY racewar",
				    rows))
				return error_code;
			return fraglist_leaders(connection, filter.c_str(), rows) ?
				       0 :
				       (mysql_errno(connection) ? mysql_errno(connection) : EIO);
		},
		[](P_char viewer, const sql_rows &rows)
		{
			char buf[65536], buf2[2048], name[256];
			int count;
			int cap_level, cap_racewar;
			long cap_frags;
			time_t cap_timer;
			int days, hours, mins, secs;

			// get level cap info (already uses sql)
			get_level_cap_info(&cap_frags, &cap_racewar, &cap_level, &cap_timer);
			cap_timer -= time(NULL);

			if (cap_timer <= 0)
			{
				secs = mins = hours = days = 0;
			}
			else
			{
				secs = cap_timer % 60;
				cap_timer /= 60;
				mins = cap_timer % 60;
				cap_timer /= 60;
				hours = cap_timer % 24;
				cap_timer /= 24;
				days = cap_timer;
			}

			long frag_totals[MAX_RACEWAR] = { 0 };
			for (const sql_row &row : rows)
				if (!strcmp(row[0], "total") && row[1] && row[2])
				{
					const int racewar = atoi(row[1]);
					if (racewar >= 0 && racewar < MAX_RACEWAR)
						frag_totals[racewar] = atol(row[2]);
				}

			snprintf(
				buf, MAX_STRING_LENGTH,
				"&+YFrag Level Cap:&+w %d - All, &+WGoodies Total Frags - &+w%d.%02d, &+REvils Total Frags - &+w%d.%02d\n&+YTimer:&+w %02d:%02d:%02d:%02d &+YFrags needed:&+w %.2f&n\n\n&+WTop Fraggers\n\n",
				cap_level, (int)(frag_totals[RACEWAR_GOOD] / 100),
				(int)(frag_totals[RACEWAR_GOOD] % 100),
				(int)(frag_totals[RACEWAR_EVIL] / 100),
				(int)(frag_totals[RACEWAR_EVIL] % 100), days, hours, mins, secs,
				frag_cap_config_frags_for_level(cap_level + 1));

			for (const char *tag : { "top", "low" })
			{
				if (!strcmp(tag, "low"))
					strcat(buf, "\r\n\r\n&+LLowest Fraggers\r\n\r\n");
				count = 0;
				for (const sql_row &row : rows)
				{
					if (strcmp(row[0], tag) || !row[1] || !row[2] ||
					    count >= MAX_FRAG_SIZE)
						continue;
					strlcpy(name, row[1], sizeof name);
					name[0] = toupper(name[0]);
					snprintf(buf2, sizeof buf2,
						 "   &+Y%-30s             &+R% 6.2f\r\n", name,
						 atoi(row[2]) / 100.0);
					strcat(buf, buf2);
					count++;
				}
				// pad with "nobody" if less than 10 results
				while (count < MAX_FRAG_SIZE)
				{
					snprintf(buf2, sizeof buf2,
						 "   &+Y%-30s             &+R% 6.2f\r\n", "Nobody",
						 0.0);
					strcat(buf, buf2);
					count++;
				}
			}

			strcat(buf, "\r\n");

			page_string(viewer->desc, buf, 1);
		});
}

// shows the frag list from database
void do_fraglist(P_char ch, char *arg, int /*cmd*/)
{
	char filter[256] = "";

	if (!IS_ALIVE(ch))
		return;

	// for default view (no filter), use cache
	if (!arg || !arg[0])
	{
		char *cached = redis_get_fraglist();
		if (cached)
		{
			page_string(ch->desc, cached, 1);
			free(cached);
			return;
		}
		// cache miss: the writer rebuilds it, and ch is shown the new list
		if (redis_cache_fraglist(ch))
			return;
	}

	if (arg && arg[0])
	{
		// racewar filters
		if (strstr("normal", arg))
		{
			filter[0] = '\0'; // no filter
		}
		else if (strstr("goodie", arg))
		{
			snprintf(filter, sizeof(filter), "racewar = %d", RACEWAR_GOOD);
		}
		else if (strstr("evil", arg))
		{
			snprintf(filter, sizeof(filter), "racewar = %d", RACEWAR_EVIL);
		}
		else if (strstr("undead", arg))
		{
			snprintf(filter, sizeof(filter), "racewar = %d", RACEWAR_UNDEAD);
		}
		else if (strstr("illithid", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'illithid'");
		}
		// race filters
		else if (strstr("lich", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'lich'");
		}
		else if (strstr("vampire", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'vampire'");
		}
		else if (strstr("revenant", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'revenant'");
		}
		else if (strstr("human", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'human'");
		}
		else if (strstr("barbarian", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'barbarian'");
		}
		else if (strstr("drow elf", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'drow_elf'");
		}
		else if (strstr("grey elf", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'grey_elf'");
		}
		else if (strstr("mountain dwarf", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'mountain_dwarf'");
		}
		else if (strstr("duergar dwarf", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'duergar_dwarf'");
		}
		else if (strstr("halfling", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'halfling'");
		}
		else if (strstr("gnome", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'gnome'");
		}
		else if (strstr("storm giant", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'storm_giant'");
		}
		else if (strstr("ogre", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'ogre'");
		}
		else if (strstr("troll", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'troll'");
		}
		else if (strstr("drider", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'drider'");
		}
		else if (strstr("half elf", arg) || strstr("half-elf", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'half-elf'");
		}
		else if (strstr("orc", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'orc'");
		}
		else if (strstr("thrikreen", arg) || strstr("thri-kreen", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'thri-kreen'");
		}
		else if (strstr("centaur", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'centaur'");
		}
		else if (strstr("githyanki", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'githyanki'");
		}
		else if (strstr("minotaur", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'minotaur'");
		}
		else if (strstr("goblin", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'goblin'");
		}
		else if (strstr("orog", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'orog'");
		}
		else if (strstr("githzerai", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'githzerai'");
		}
		else if (strstr("agathinon", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'agathinon'");
		}
		else if (strstr("eladrin", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'eladrin'");
		}
		else if (strstr("pillithid", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'planetbound_illithid'");
		}
		else if (strstr("wood elf", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'wood_elf'");
		}
		else if (strstr("kobold", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'kobold'");
		}
		else if (strstr("kuo toa", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'kuo_toa'");
		}
		else if (strstr("firbolg", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'firbolg'");
		}
		else if (strstr("tiefling", arg))
		{
			snprintf(filter, sizeof(filter), "race = 'tiefling'");
		}
		// class filters
		else if (strstr("warrior", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'warrior'");
		}
		else if (strstr("ranger", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'ranger'");
		}
		else if (strstr("paladin", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'paladin'");
		}
		else if (strstr("psionicist", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'psionicist'");
		}
		else if (strstr("anti-paladin", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'anti-paladin'");
		}
		else if (strstr("cleric", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'cleric'");
		}
		else if (strstr("monk", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'monk'");
		}
		else if (strstr("unholy-piper", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'unholy-piper'");
		}
		else if (strstr("shaman", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'shaman'");
		}
		else if (strstr("sorcerer", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'sorcerer'");
		}
		else if (strstr("necromancer", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'necromancer'");
		}
		else if (strstr("conjurer", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'conjurer'");
		}
		else if (strstr("summoner", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'summoner'");
		}
		else if (strstr("rogue", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'rogue'");
		}
		else if (strstr("assassin", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'assassin'");
		}
		else if (strstr("mercenary", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'mercenary'");
		}
		else if (strstr("bard", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'bard'");
		}
		else if (strstr("thief", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'thief'");
		}
		else if (strstr("druid", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'druid'");
		}
		else if (strstr("blighter", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'blighter'");
		}
		else if (strstr("reaver", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'reaver'");
		}
		else if (strstr("illusionist", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'illusionist'");
		}
		else if (strstr("berserker", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'berserker'");
		}
		else if (strstr("dreadlord", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'dreadlord'");
		}
		else if (strstr("ethermancer", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'ethermancer'");
		}
		else if (strstr("avenger", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'avenger'");
		}
		else if (strstr("theurgist", arg))
		{
			snprintf(filter, sizeof(filter), "class = 'theurgist'");
		}
		else if (strstr("ship", arg))
		{
			update_shipfrags();
			display_shipfrags(ch);
			return;
		}
		else if (strstr("guild", arg))
		{
			show_guild_frags(ch);
			return;
		}
		else
		{
			send_to_char(
				"Valid fraglists exist by race, class, undead/evil/good, and overall (no argument).\r\n",
				ch);
			return;
		}
	}

	show_fraglist(ch, filter);
}

// update frag leaderboard in database and check position flags
void checkFragList(P_char ch)
{
	if (!ch || IS_NPC(ch))
		return;

	// update the database leaderboard
	sql_update_frag_leaderboard(ch);

	// check if player is at top/bottom of list for special flags
	check_frag_position(ch);
}
