/****************************************************************************
 *
 *  File: listen.c                                              Part of Duris
 *  Usage: the listen skill: overhearing speech in nearby rooms
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include <list>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <string>
#include <vector>
using namespace std;

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include "world/epic.h"
#include "net/listen.h"
#include "magic/spells.h"
#include "sql/sql.h"
#include "abilities/abilities.h"

extern P_room world;
extern P_desc descriptor_list;

// Main call for the listen skill broadcasting
// cmd option: 0 = say, 1 = gsay, 2 = improved listen(emote)
void listen_broadcast(P_char ch, const char *buf, int cmd)
{
	P_desc i;
	P_char tch;

	if (IS_TRUSTED(ch) || IS_ILLITHID(ch) || IS_PILLITHID(ch) || IS_NPC(ch))
	{
		return;
	}

	for (i = descriptor_list; i; i = i->next)
	{
		if (!i->character || i->connected)
		{
			continue;
		}

		tch = i->character;

		// Lets weed out anyone who dosn't have listen skill, otherwise we lag!
		if (!GET_CHAR_SKILL(tch, SKILL_LISTEN))
		{
			continue;
		}

		if (tch && IS_PC(tch))
		{
			switch (cmd)
			{
			case LISTEN_SAY:
				listen_say(ch, tch, buf);
				break;

			case LISTEN_GSAY:
				listen_gsay(ch, tch, buf);
				break;

			case LISTEN_EMOTE:
				listen_emote(ch, tch, buf);
				break;

			default:
				wizlog(57,
				       "function listen_broadcast was called with an invalid subcommand.");
				break;
			}
		}
	}
}

// How many rooms away you hear a say or group say.
static int listen_range(int iskl)
{
	int range, nrange;

	nrange = (int)get_property("skill.listen.range.norm", 1);

	if (iskl)
	{
		range = (nrange + (int)get_property("skill.listen.range.norm.extend", 1));
	}
	else
	{
		range = nrange;
	}

	return range;
}

static int improved_listen_emote_range()
{
	return (int)get_property("skill.listen.range.improved", 2);
}

// A roll of 0-100 above this loses what you hear from past the next room.
static int improved_listen_far_threshold(int iskl)
{
	return BOUNDED(20, iskl, 95);
}

// A roll of 25-45 below this lets you hear it.
static int listen_hear_threshold(P_char tch)
{
	return MAX(40, GET_CHAR_SKILL(tch, SKILL_LISTEN));
}

// A roll of 15-55 below this lets you notice an emote.
static int improved_listen_emote_threshold(int iskl)
{
	return MAX(40, iskl);
}

// A roll of 70-90 above this hides who a smaller emoter is.
static int improved_listen_small_threshold(int iskl)
{
	return MAX(75, iskl);
}

std::string listen_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_LISTEN);
	if (rating < 1)
		return "  You have not learned to listen.\n";
	return fact("Chance the listen command hears something", chance_under(rating + 1, 1, 101)) +
	       "    (your luck can take a tenth off the roll)\n"
	       "  It finds beings you can't see here, and counts them from level 15.\n" +
	       fact("Rooms away you overhear a say or group say",
		    std::to_string(listen_range(GET_CHAR_SKILL(ch, SKILL_IMPROVED_LISTEN)))) +
	       fact("Chance you overhear it", chance_under(listen_hear_threshold(ch), 25, 45)) +
	       fact("Chance you catch a speaker's name", chance_under(rating, 15, 35) +
								 ", in a group say " +
								 chance_under(rating, 20, 40)) +
	       fact("Chance you catch each word, one room away",
		    chance_under(listen_hear_threshold(ch) + 1 - 10, 25, 75)) +
	       "    (10 worse for each further room)\n"
	       "  Nothing carries into a silent room.\n";
}

std::string improved_listen_facts(P_char ch)
{
	const int iskl = GET_CHAR_SKILL(ch, SKILL_IMPROVED_LISTEN);
	if (iskl < 1)
		return "  You have not learned improved listen.\n";
	return fact("Rooms away you overhear a say or group say",
		    std::to_string(listen_range(iskl))) +
	       fact("Chance past the next room",
		    chance_under(improved_listen_far_threshold(iskl) + 1, 0, 100)) +
	       fact("Rooms away you notice an emote",
		    std::to_string(improved_listen_emote_range())) +
	       fact("Chance you notice it",
		    chance_under(improved_listen_emote_threshold(iskl), 15, 55)) +
	       fact("Chance you see who a smaller emoter is",
		    chance_under(improved_listen_small_threshold(iskl) + 1, 70, 90)) +
	       "  You also need the listen skill.\n";
}

void listen_say(P_char ch, P_char tch, const char *buf)
{
	int iskl, range, howclose;
	char strn[MAX_STRING_LENGTH], buf1[MAX_STRING_LENGTH];

	if (IS_ROOM(tch->in_room, ROOM_SILENT))
		return;

	iskl = GET_CHAR_SKILL(tch, SKILL_IMPROVED_LISTEN);
	range = listen_range(iskl);

	howclose = how_close(ch->in_room, tch->in_room, range);

	if (howclose < 0)
	{
		return;
	}

	if ((howclose > 1) && (improved_listen_far_threshold(iskl) < number(0, 100)))
	{
		return;
	}

	if ((GET_CHAR_SKILL(tch, SKILL_LISTEN) && (ch != tch) &&
	     (world[ch->in_room].number != world[tch->in_room].number)))
	{
		if (listen_hear_threshold(tch) > (number(25, 45)))
		{
			muddle_listened_string(ch, tch, buf, strn, howclose);

			checked_snprintf(buf1, MAX_STRING_LENGTH,
					 "You faintly hear %s say the words '%s'.\r\n",
					 (GET_CHAR_SKILL(tch, SKILL_LISTEN) > number(15, 35)) ?
						 PERS(ch, tch, 1) :
						 "someone:",
					 strn);

			send_to_char(buf1, tch);

			notch_skill(tch, SKILL_LISTEN, 17);
		}
		else
		{
			notch_skill(tch, SKILL_LISTEN, 1);
		}
	}
}

void listen_gsay(P_char ch, P_char tch, const char *buf)
{
	int iskl, range, howclose;
	char strn[MAX_STRING_LENGTH], buf1[MAX_STRING_LENGTH];

	if (IS_ROOM(tch->in_room, ROOM_SILENT))
		return;

	iskl = GET_CHAR_SKILL(tch, SKILL_IMPROVED_LISTEN);
	range = listen_range(iskl);

	howclose = how_close(ch->in_room, tch->in_room, range);

	if (howclose < 0)
	{
		return;
	}

	if ((howclose > 1) && (improved_listen_far_threshold(iskl) < number(0, 100)))
	{
		return;
	}

	if ((GET_CHAR_SKILL(tch, SKILL_LISTEN) && ch->group != tch->group))
	{
		if (listen_hear_threshold(tch) > (number(25, 45)))
		{
			muddle_listened_string(ch, tch, buf, strn, howclose);

			checked_snprintf(buf1, MAX_STRING_LENGTH,
					 "You faintly hear %s groupsay the words '%s'.\r\n",
					 (GET_CHAR_SKILL(tch, SKILL_LISTEN) > number(20, 40)) ?
						 PERS(ch, tch, 1) :
						 "someone:",
					 strn);

			send_to_char(buf1, tch);

			notch_skill(tch, SKILL_LISTEN, 5);
		}
		else
		{
			notch_skill(tch, SKILL_LISTEN, 1);
		}
	}
}

void listen_emote(P_char ch, P_char tch, const char *buf)
{
	int iskl, irange, howclose;
	char buf1[MAX_STRING_LENGTH];

	if (IS_TRUSTED(tch))
		return;

	strcpy(buf1, "You notice in the distance, ");
	strcat(buf1, buf);

	if (ch == tch || world[ch->in_room].number == world[tch->in_room].number)
	{
		return;
	}

	iskl = GET_CHAR_SKILL(tch, SKILL_IMPROVED_LISTEN);
	irange = improved_listen_emote_range();

	howclose = how_close(ch->in_room, tch->in_room, irange);

	if (howclose < 0)
	{
		return;
	}

	if ((howclose > 1) && (improved_listen_far_threshold(iskl)) < number(0, 100))
	{
		return;
	}

	if (iskl)
	{
		if ((improved_listen_emote_threshold(iskl) > (number(15, 55))) && IS_PC(tch))
		{
			if ((GET_SIZE(ch) < GET_SIZE(tch)) &&
			    (number(70, 90) > improved_listen_small_threshold(iskl)))
			{
				send_to_char(
					"You notice someone in the distance scurrying about.\r\n",
					tch);
			}
			else
			{
				act(buf1, TRUE, ch, 0, tch, TO_VICT);
			}
		}
	}
}

/*
 * muddle_listened_string - CRYPTs and drops some words
 *
 *  ch - char talking
 *  vict - char listening
 *  arg - stuff said
 *  extr_depth - if one room away, 0, if further, >0
 */
// Taken from actcomm.c
void muddle_listened_string(P_char ch, P_char vict, const char *arg, char *muddled, int extr_depth)
{
	const char missed_word[] = "(mumble)";
	const int missed_word_length = static_cast<int>(sizeof(missed_word) - 1);
	char buf[MAX_STRING_LENGTH];
	int i, j, k, len;

	i = j = 0;

	// okay drop some words

	while (TRUE)
	{
		// if at space, go to next non-space (word)

		if (arg[i] == ' ')
		{
			while (arg[i] == ' ')
			{
				muddled[j++] = ' ';
				i++;
			}

			if (!arg[i])
			{
				muddled[j] = '\0';
				break;
			}
		}
		if (listen_hear_threshold(vict) < (number(25, 75) + (extr_depth * 10)))
		{
			// insert an appropriate number of asterisks

			for (k = 0; k < missed_word_length; k++)
				muddled[j++] = '*';

			// advance to next space

			while ((arg[i] != ' ') && (arg[i] != '\0'))
				i++;

			if (arg[i] == '\0')
			{
				muddled[j] = '\0';
				break;
			}
		}
		else // they passed, give em the whole word
		{
			while ((arg[i] != ' ') && (arg[i] != '\0'))
				muddled[j++] = arg[i++];

			if (!arg[i])
			{
				muddled[j] = '\0';
				break;
			}
		}
	}

	// CRYPT it up

	strcpy(buf, muddled);
	strcpy(muddled, language_CRYPT(ch, vict, buf));

	// change ******** stuff to missed_word

	len = strlen(muddled);
	k = 0;

	for (i = 0; i < len; i++)
	{
		if (muddled[i] == '*')
		{
			// make sure we have the right number of em..
			if (i + missed_word_length > len)
				k = 1;

			for (j = i; j < len && j < i + missed_word_length; j++)
			{
				if (muddled[j] != '*')
				{
					while (muddled[i] == '*')
						i++;
					k = 1;
				}
			}

			if (!k)
			{
				for (j = i; j < i + missed_word_length; j++)
				{
					muddled[j] = missed_word[k++];
				}
			}

			k = 0;
		}
	}
}
