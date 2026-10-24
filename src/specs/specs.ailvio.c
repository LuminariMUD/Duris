/* test proc for Ailvio */
#include <ctype.h>
#include <list>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <time.h>
using namespace std;

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include "world/specs.prototypes.h"
#include "magic/spells.h"
#include "economy/tradeskill.h"
#include "world/vnum.mob.h"
#include "world/vnum.obj.h"

extern P_room world;
extern P_nevent get_scheduled(P_char ch, event_func func);
extern void event_bandage_check(P_char ch, P_char victim, P_obj, void *data);
extern P_index mob_index;

// The evil tutorial residents change identity without changing the original
// encounters' stats, innates, resistances, equipment access or victim-race XP.
// Other NPCs and every player keep their normal race profile. A changed form
// also uses its own profile rather than the copied resident's baseline.
int tutorial_mobile_mechanics_race(P_char ch)
{
	const int race = GET_RACE(ch);
	if (!IS_NPC(ch))
		return race;
	switch (GET_VNUM(ch))
	{
	case 91404:
	case 91416:
	case 91417:
	case 91421:
	case 91426:
	case 91428:
	case 91430:
	case 91431:
	case 91435:
	case 91437:
	case 91448:
		return race == RACE_MINOTAUR ? RACE_CENTAUR : race;
	case 91460:
		return race == RACE_GITHYANKI ? RACE_GITHZERAI : race;
	case 91402:
	case 91440:
	case 91504:
		return race == RACE_TIEFLING ? RACE_HALFELF : race;
	case 91403:
	case 91405:
	case 91414:
	case 91420:
	case 91447:
	case 91449:
	case 91456:
	case 91457:
	case 91478:
	case 91500:
		return race == RACE_ORC ? RACE_BARBARIAN : race;
	case 91432:
	case 91461:
	case 91480:
	case 91492:
	case 91493:
		return race == RACE_DROW ? RACE_GREY : race;
	case 91401:
	case 91419:
	case 91434:
	case 91458:
		return race == RACE_GOBLIN ? RACE_HALFLING : race;
	case 91407:
	case 91438:
	case 91463:
	case 91476:
	case 91483:
	case 91502:
		return race == RACE_KOBOLD ? RACE_GNOME : race;
	case 91201:
	case 91406:
	case 91415:
	case 91418:
	case 91429:
	case 91433:
	case 91442:
	case 91443:
	case 91450:
	case 91452:
	case 91462:
	case 91466:
	case 91467:
	case 91469:
	case 91470:
	case 91473:
	case 91477:
	case 91482:
	case 91484:
	case 91491:
	case 91497:
	case 91498:
	case 91499:
	case 91501:
	case 91503:
		return race == RACE_ORC ? RACE_HUMAN : race;
	case 91464:
		return race == RACE_TIEFLING ? RACE_HUMAN : race;
	case 91441:
	case 91459:
	case 91479:
	case 91490:
		return race == RACE_DUERGAR ? RACE_MOUNTAIN : race;
	default:
		return race;
	}
}

int burbul_map_obj(P_obj obj, P_char ch, int cmd, char *arg)
{
	P_obj map;

	/*
	   check for periodic event calls
	 */
	if (cmd == CMD_SET_PERIODIC)
		return TRUE;

	if (!ch || !obj)
		return FALSE;

	const bool wutvr = OBJ_VNUM(obj) == VOBJ_WUTVR_MAP_PROC;
	if (((cmd == CMD_ASK) && arg) || ((cmd == CMD_TELL) && arg))
	{
		if (isname(arg, wutvr ? "grubruk map" : "burbul map"))
		{
			if ((map = read_object(wutvr ? VOBJ_WUTVR_MAP : 29201, VIRTUAL)))
			{
				act(wutvr ? "&+GGrubruk &N&+ythe goblin &Nsmiles and hands you &+wa map&N." :
					    "&+GB&N&+gurbu&+Gl &N&+ythe halfling &Nsmiles and hands you &+wa map&N.",
				    FALSE, ch, 0, 0, TO_CHAR);
				act(wutvr ? "&+GGrubruk &N&+ythe goblin &Nsmiles and hands $n &+wa map&N." :
					    "&+GB&N&+gurbu&+Gl &N&+ythe halfling &Nsmiles and hands $n &+wa map&N.",
				    TRUE, ch, 0, NULL, TO_ROOM);
				obj_to_char(map, ch);
			}
			return TRUE;
		}
	}

	return FALSE;
}

int chyron_search_obj(P_obj obj, P_char ch, int cmd, char *arg)
{
	P_obj newobj = NULL;

	/*
	   check for periodic event calls
	 */
	if (cmd == CMD_SET_PERIODIC)
		return TRUE;

	if (!ch || !obj)
		return FALSE;

	// Capture the bound controller before obj is replaced by the requested item.
	const bool wutvr = OBJ_VNUM(obj) == VOBJ_WUTVR_SEARCH_PROC;
	if ((cmd == CMD_GET || cmd == CMD_TAKE) && arg)
	{
		if (!(obj = get_obj_in_list_vis(ch, arg, world[ch->in_room].contents)))
		{
			return FALSE;
		}
		if (isname(arg, "box") || isname(arg, "salt") || isname(arg, "wood") ||
		    isname(arg, "wooden"))
		{
			if (!(newobj = read_object(wutvr ? VOBJ_WUTVR_SALT : 29220, VIRTUAL)))
			{
				return FALSE;
			}
			act("You get &+wa s&+Wal&N&+wt box&N.", FALSE, ch, 0, 0, TO_CHAR);
			act("$n gets &+wa s&+Wal&N&+wt box&N.", TRUE, ch, 0, NULL, TO_ROOM);
		}
		else if (isname(arg, "vial") || isname(arg, "red") || isname(arg, "tear") ||
			 isname(arg, "tears") || isname(arg, "basilisk"))
		{
			if (!(newobj = read_object(wutvr ? VOBJ_WUTVR_TEARS : 29221, VIRTUAL)))
			{
				return FALSE;
			}
			act("You get &+Ra vial of ba&N&+rsili&+Rsk tears&N.", FALSE, ch, 0, 0,
			    TO_CHAR);
			act("$n gets &+Ra vial of ba&N&+rsili&+Rsk tears&N.", TRUE, ch, 0, NULL,
			    TO_ROOM);
		}
		else if (isname(arg, "all"))
		{
			act(wutvr ? "You try, but Zyrrak gets in your way and you drop everything you've picked up.&N" :
				    "You try, but Ch&+wyr&N&+gon gets in your way and you drop everything you've picked up.&N",
			    FALSE, ch, 0, 0, TO_CHAR);
			return TRUE;
		}
		if (newobj)
		{
			// char gets object in room;
			obj_from_room(obj);
			obj_to_char(obj, ch);
			// put the new object in there and hide it
			SET_BIT(newobj->extra_flags, ITEM_SECRET);
			obj_to_room(newobj, ch->in_room);
			return TRUE;
		}
	}
	return FALSE;
}

int bandage_mob(P_char ch, P_char /*pl*/, int cmd, char * /*arg*/)
{
	// Start him off incapacitated.
	if (cmd == CMD_SET_PERIODIC)
	{
		GET_HIT(ch) = -3;
		SET_POS(ch, POS_PRONE + STAT_INCAP);
		return TRUE;
	}

	if (cmd != CMD_PERIODIC || GET_STAT(ch) == STAT_DEAD)
		return FALSE;

	// If he's not dead, we need to make him bandage-able.
	GET_HIT(ch) = -3;
	// We keep him incap'd until someone saves him.  Or kills him.
	if (GET_STAT(ch) != STAT_INCAP && !IS_FIGHTING(ch))
	{
		SET_POS(ch, POS_PRONE + STAT_INCAP);
	}

	return FALSE;
}

int bandage_reward_mob(P_char ch, P_char tch, int cmd, char * /*arg*/)
{
	P_char man;
	P_nevent nev;

	if (cmd == CMD_SET_PERIODIC)
	{
		return TRUE;
	}

	if (cmd != CMD_PERIODIC)
	{
		return FALSE;
	}

	for (tch = world[ch->in_room].people; tch; tch = tch->next_in_room)
	{
		if (IS_NPC(tch))
		{
			continue;
		}
		if (IS_PC(tch) && (nev = get_scheduled(tch, event_bandage_check)))
		{
			if ((man = nev->victim) != NULL && IS_NPC(man) &&
			    GET_VNUM(man) == (GET_VNUM(ch) == VMOB_WUTVR_WIFE ?
						      VMOB_WUTVR_INCAPACITATED :
						      VMOB_AILVIO_INCAPACITATED))
			{
				act("$n&+w's eyes well up with &+Ctears&N &+wat your generosity.\n&+W'&N&+wTHANK YOU!!!&+W'&N&+w, $e sobs.",
				    FALSE, ch, 0, tch, TO_VICT);
				act("$n&+w's eyes well up with &+Ctears&N &+wat $N's generosity.\n&+W'&N&+wTHANK YOU!!!&+W'&N&+w, $e sobs.",
				    FALSE, ch, 0, tch, TO_NOTVICT);
				act("&+wOverwhelmed by the act of selflessness, you sob openly.  Then you say, 'THANK YOU!!!'",
				    FALSE, ch, 0, tch, TO_CHAR);

				do_stand(man, writable_arg(""), CMD_STAND);
				do_say(man, writable_arg("Thank you for reviving me."), CMD_SAY);
				gain_exp(tch, NULL, 1000, EXP_QUEST);
				do_say(man, writable_arg("Time for us to go."), CMD_SAY);
				act("$N and $n disappear deeper into the woods.", TRUE, ch, 0, man,
				    TO_NOTVICT);
				extract_char(man);
				extract_char(ch);
			}
		}
	}
	return FALSE;
}
