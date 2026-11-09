/*
 ***************************************************************************
 *  File: spec.assign.c                                      Part of Duris *
 *  Usage: assign function pointers for special procs.                     *
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.    *
 *  Copyright 1994 - 2008 - Duris Systems Ltd.                             *
 ***************************************************************************
 */

#include "core/prototypes.h"
#include "core/structs.h"
#include "world/db.h"
#include "world/events.h"
#include "core/utils.h"
#include <dlfcn.h>
#include <stdio.h>
#include "world/buildings.h"
#include "world/outposts.h"
#include "world/world_singletons.h"
#include "core/proc-libs.h"
#include "specs/specs.barovia.h"
#include "specs/specs.caertannad.h"
#include "specs/specs.eth2.h"
#include "specs/specs.firep.h"
#include "specs/specs.juiblex.h"
#include "specs/specs.keleks.h"
#include "world/specs.prototypes.h"
#include "specs/specs.ravenloft.h"
#include "specs/specs.snogres.h"
#include "specs/specs.winterhaven.h"
#include "specs/specs.zion.h"
#include "economy/tradeskill.h"
#include "world/vnum.mob.h"
#include "world/vnum.obj.h"
#include "world/zone_story_quest_runtime.h"
#include "specs/object_bindings.h"

extern const int top_of_world;
extern P_index mob_index;
extern P_index obj_index;
extern P_obj object_list;
extern P_room world;

// Added gellz Procs
int gellz_test_obj_procs(P_obj obj, P_char ch, int cmd, char *argument);
int magic_deck(P_obj obj, P_char ch, int cmd, char *argument);
int blackjack_table(P_obj obj, P_char ch, int cmd, char *argument);

int unmulti_altar(P_obj obj, P_char ch, int cmd, char *arg);
int harpy_gate(P_obj obj, P_char ch, int cmd, char *arg);
int block_dir(P_char ch, P_char pl, int cmd, char *arg);

int ship_shop_proc(int room, P_char ch, int cmd, char *arg);
void assign_ship_crew_funcs();

int cards_object(P_obj obj, P_char ch, int cmd, char *argument);

#ifdef SHLIB

/*
   first entry is the name of the lib on the disk (excluding the
   trailing .so).  The second entry SHOULD ALWAYS BE NULL.  Last entry
   should have a NULL name (so I can find the end of the list)
 */

dynamic_procs dynam_proc_list[] = { { "specs.myranth", NULL },
				    { "specs.bloodstone", NULL },
				    { NULL, NULL } };

/*
   I'm gonna be ultra-paranoid here and do redundant sanity checks on
   the lib name.... fucking this up will cause some MAJOR havoc..
 */

int load_proc_lib(char *name)
{
	int i;
	char buf[180];
	void *handle;

	for (i = 0; dynam_proc_list[i].name; i++)
		if (!str_cmp(name, dynam_proc_list[i].name))
		{
			if (dynam_proc_list[i].handle)
				return 0;
			snprintf(buf, 180, "%s.so", dynam_proc_list[i].name);
			handle = dlopen(buf, RTLD_NOW);
			if (!handle)
			{
				logit(LOG_EXIT, "lib: %s: %s", buf, dlerror());
				return 0;
			}
			dynam_proc_list[i].handle = handle;
			return 1;
		}
	return 0;
}

int unload_proc_lib(char *name)
{
	int i;
	char buf[180];
	const char *error;

	for (i = 0; dynam_proc_list[i].name; i++)
		if (!str_cmp(name, dynam_proc_list[i].name))
		{
			if (!dynam_proc_list[i].handle)
				return 0;
			dlclose(dynam_proc_list[i].handle);
			error = dlerror();
			if (error)
			{
				logit(LOG_EXIT, "lib: %s.so: %s", dynam_proc_list[i].name, error);
				return 0;
			}
			dynam_proc_list[i].handle = NULL;
			return 1;
		}
	return 0;
}

void load_all_proc_libs(void)
{
	int i;
	char name[180];
	void *handle;

	for (i = 0; dynam_proc_list[i].name; i++)
	{
		snprintf(name, 180, "%s.so", dynam_proc_list[i].name);
		handle = dlopen(name, RTLD_NOW);
		if (!handle)
		{
			fatal_boot_error("specs.assign", "lib: %s: %s", name, dlerror());
		}
		dynam_proc_list[i].handle = handle;
	}
}

int mob_proc_stub(P_char ch, P_char pl, int cmd, char *arg)
{
	// All mobs are mundane, but not necessarily periodic.
	if (cmd == CMD_SET_PERIODIC)
		return FALSE;

	return FALSE;
}

int obj_proc_stub(P_obj obj, P_char ch, int cmd, char *arg)
{
	// All objs don't get a periodic.. that's dumb.
	if (cmd == CMD_SET_PERIODIC)
		return FALSE;

	return FALSE;
}

int room_proc_stub(int room, P_char ch, int cmd, char *arg)
{
	return FALSE;
}

#endif /*                                                                                                                                                                                              \
          SHLIB                                                                                                                                                                                        \
        */

/*
 ********************************************************************
 *  Assignments                                                        *
 ********************************************************************
 */

/*
   assign special procedures to mobiles
 */

void assign_mobiles(void)
{
	int i;

	/* speed wipe entry to Tharn Rifts */
	mob_index[real_mobile0(500129)].func.mob = Baltazo;
	/* scorched valley */
	mob_index[real_mobile0(71223)].func.mob = block_up;
	mob_index[real_mobile0(71259)].func.mob = yeenoghu;

	/* useless god toys */
	mob_index[real_mobile0(444)].func.mob = io_assistant;

	/* rename char mobiles */
	mob_index[real_mobile0(76013)].func.mob = mob_do_rename_hook;

	/* mob clear epic task */
	mob_index[real_mobile0(22428)].func.mob = clear_epic_task_spec;

	/* monk quest mob */
	// mob_index[real_mobile0(55178)].func.mob = monk_remort;

	/* player castles */

	/* Shipyards */
	mob_index[real_mobile0(43101)].func.mob = money_changer;
	mob_index[real_mobile0(43110)].func.mob = money_changer;

	/* Ailvio */
	mob_index[real_mobile0(VMOB_AILVIO_INCAPACITATED)].func.mob = bandage_mob;
	mob_index[real_mobile0(VMOB_AILVIO_WIFE)].func.mob = bandage_reward_mob;
	mob_index[real_mobile0(VMOB_WUTVR_INCAPACITATED)].func.mob = bandage_mob;
	mob_index[real_mobile0(VMOB_WUTVR_WIFE)].func.mob = bandage_reward_mob;
	mob_index[real_mobile0(29236)].func.mob = newbie_spellup_mob;
	mob_index[real_mobile0(29238)].func.mob = newbie_spellup_mob;
	mob_index[real_mobile0(29232)].func.mob = newbie_spellup_mob;
	mob_index[real_mobile0(29237)].func.mob = newbie_spellup_mob;
	mob_index[real_mobile0(91436)].func.mob = newbie_spellup_mob;
	mob_index[real_mobile0(91438)].func.mob = newbie_spellup_mob;
	mob_index[real_mobile0(91432)].func.mob = newbie_spellup_mob;
	mob_index[real_mobile0(91437)].func.mob = newbie_spellup_mob;

	/* Ako */
	mob_index[real_mobile0(3715)].func.mob = ako_hypersquirrel;
	mob_index[real_mobile0(3701)].func.mob = ako_songbird;
	mob_index[real_mobile0(3716)].func.mob = ako_vulture;
	mob_index[real_mobile0(3721)].func.mob = ako_wildmare;
	mob_index[real_mobile0(3720)].func.mob = ako_cow;

	/* Orogs */
	mob_index[real_mobile0(45818)].func.mob = rentacleric;
	mob_index[real_mobile0(45833)].func.mob = money_changer;

	/* Undead HT */
	mob_index[real_mobile0(90387)].func.mob = money_changer;

	/* WinterHaven */

	world[real_room0(55201)].funct = pet_shops; /* WH Mercenaries */
	world[real_room0(55203)].funct = pet_shops; /* WH Mounts */
	world[real_room0(55126)].funct = welfare_well;
	mob_index[real_mobile0(55128)].func.mob = world_quest; /* WH Questmaster */
	// mob_index[real_mobile0(55021)].func.mob = winterhaven_shout_one;
	// mob_index[real_mobile0(55022)].func.mob = winterhaven_shout_two;
	mob_index[real_mobile0(55008)].func.mob = wh_janitor;
	mob_index[real_mobile0(55009)].func.mob = wh_janitor;
	mob_index[real_mobile0(55010)].func.mob = wh_janitor;
	mob_index[real_mobile0(55020)].func.mob = wh_guard;
	mob_index[real_mobile0(55021)].func.mob = wh_guard;
	mob_index[real_mobile0(55022)].func.mob = wh_guard;
	mob_index[real_mobile0(55022)].func.mob = wh_guard;
	mob_index[real_mobile0(55003)].func.mob = wh_guard;
	//  mob_index[real_mobile0(55184)].func.mob = wh_guard;
	mob_index[real_mobile0(55057)].func.mob = wh_guard;
	mob_index[real_mobile0(55126)].func.mob = rentacleric;
	mob_index[real_mobile0(55500)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55246)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55501)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55502)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55503)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55504)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55505)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55506)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55507)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55508)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55509)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55510)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55511)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55512)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55513)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55514)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55515)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55516)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55517)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55518)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55519)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55520)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55521)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55550)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55551)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55552)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55553)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55554)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(500102)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(500103)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(55184)].func.mob = newbie_spellup_mob; // Priest of WH
	mob_index[real_mobile0(55124)].func.mob = money_changer;
	//  mob_index[real_mobile0(55026)].func.mob = volo_teleport;
	//  mob_index[real_mobile0()].func.mob = mob_death_proc;
	mob_index[real_mobile0(19617)].func.mob = tiamat_human_to_rareloads;
	mob_index[real_mobile0(6816)].func.mob = dragonnia_heart;
	mob_index[real_mobile0(29025)].func.mob = lanella_heart;
	mob_index[real_mobile0(22024)].func.mob = cerberus_load;
	mob_index[real_mobile0(55264)].func.mob = leviathan;

	/* Aravne */
	mob_index[real_mobile0(21673)].func.mob = wh_corpse_to_object;

	/* Myrabolus */
	mob_index[real_mobile0(82521)].func.mob = money_changer;

	/* NAX */
	mob_index[real_mobile0(37764)].func.mob = world_quest; // Nax

	/* arcium */
	world[real_room0(22439)].funct = inn;

	/* halfcut hills */
	mob_index[real_mobile0(27009)].func.mob = crossbow_ambusher;

	/* highway */
	mob_index[real_mobile0(41900)].func.mob = mir_spider;

	mob_index[real_mobile0(42172)].func.mob = red_wyrm_shout;
	mob_index[real_mobile0(42173)].func.mob = white_wyrm_shout;
	mob_index[real_mobile0(42174)].func.mob = blue_wyrm_shout;

	mob_index[real_mobile0(42166)].func.mob = amphisbean;
	mob_index[real_mobile0(42167)].func.mob = amphisbean;

	/* claw cavern */
	for (i = 80706; i <= 80734; i++)
	{
		if ((i == 80711) || (i == 80712) || (i == 80714) || ((i > 80724) && (i < 80728)))
			continue;

		mob_index[real_mobile0(i)].func.mob = clwcvrn_crys_die;
	}

	mob_index[real_mobile0(80735)].func.mob = clwcvrn_golem_shatter;
	mob_index[real_mobile0(80739)].func.mob = clwcvrn_protect;
	mob_index[real_mobile0(80726)].func.mob = claw_cavern_drow_mage;

	/* darkfall_forest */
	mob_index[real_mobile0(75013)].func.mob = archer;

	/* Undead Map (map10) */
	mob_index[real_mobile0(VMOB_CHARON_BOATMAN)].func.mob = charon;

	/* breale */
	mob_index[real_mobile0(2613)].func.mob = breale_townsfolk;
	mob_index[real_mobile0(2614)].func.mob = breale_townsfolk;
	mob_index[real_mobile0(2619)].func.mob = breale_townsfolk;
	mob_index[real_mobile0(2620)].func.mob = breale_townsfolk;
	mob_index[real_mobile0(2621)].func.mob = breale_townsfolk;
	mob_index[real_mobile0(2622)].func.mob = breale_townsfolk;
	mob_index[real_mobile0(2623)].func.mob = breale_townsfolk;
	mob_index[real_mobile0(2624)].func.mob = breale_townsfolk;
	mob_index[real_mobile0(2625)].func.mob = breale_townsfolk;

	/* Braddistock Mansion */
	mob_index[real_mobile0(135014)].func.mob = braddistock;

	/* Orc town? */
	mob_index[real_mobile0(97545)].func.mob = troll_slave;
	mob_index[real_mobile0(97509)].func.mob = stray_dog;
	mob_index[real_mobile0(97534)].func.mob = hardworking_fisherman;
	mob_index[real_mobile0(97554)].func.mob = orcish_jailkeeper;
	mob_index[real_mobile0(97539)].func.mob = orcish_woman;

	/* Vella's Bordello */
	mob_index[real_mobile0(93600)].func.mob = Vella_slut;
	mob_index[real_mobile0(93602)].func.mob = sex_crazed_prostitute;
	mob_index[real_mobile0(93603)].func.mob = well_built_prostitute;
	mob_index[real_mobile0(93605)].func.mob = Padh_bouncer;
	mob_index[real_mobile0(93607)].func.mob = Vem_rouge;
	mob_index[real_mobile0(93611)].func.mob = sleezy_prostitute;
	mob_index[real_mobile0(93613)].func.mob = tired_young_man;

	mob_index[real_mobile0(1250)].func.mob = archer;
	mob_index[real_mobile0(1251)].func.mob = archer;
	mob_index[real_mobile0(1252)].func.mob = archer;
	mob_index[real_mobile0(1253)].func.mob = archer;
	mob_index[real_mobile0(1254)].func.mob = archer;

	/* Charing */
	mob_index[real_mobile0(45033)].func.mob = cityguard;
	mob_index[real_mobile0(45036)].func.mob = cityguard;
	mob_index[real_mobile0(45046)].func.mob = cityguard;

	/* transparent tower */
	mob_index[real_mobile0(16205)].func.mob = transp_tow_acerlade;

	/* necro dracoliches */
	mob_index[real_mobile0(3)].func.mob = necro_dracolich;
	mob_index[real_mobile0(4)].func.mob = necro_dracolich;
	mob_index[real_mobile0(5)].func.mob = necro_dracolich;
	mob_index[real_mobile0(6)].func.mob = necro_dracolich;
	mob_index[real_mobile0(7)].func.mob = necro_dracolich;
	mob_index[real_mobile0(8)].func.mob = necro_dracolich;
	mob_index[real_mobile0(9)].func.mob = necro_dracolich;
	mob_index[real_mobile0(10)].func.mob = necro_dracolich;
	mob_index[real_mobile0(1201)].func.mob = necro_dracolich;

	/* Illusionist */

	mob_index[real_mobile0(1106)].func.mob = shadow_monster; // shadow monster proc
	mob_index[real_mobile0(1108)].func.mob = illus_dragon; // dragon proc
	mob_index[real_mobile0(1107)].func.mob = insects; // spell_insect so they poison
	mob_index[real_mobile0(650)].func.mob = illus_titan; // titan disappears when not fighting

	/* Lower God Rooms */
	mob_index[real_mobile0(200)].func.mob = shadow_demon_of_torm;

	/* Main God Rooms */
	mob_index[real_mobile0(1205)].func.mob = sales_spec;
	mob_index[real_mobile0(1228)].func.mob = beavis;
	mob_index[real_mobile0(1229)].func.mob = butthead;
	mob_index[real_mobile0(1230)].func.mob = billthecat;

	/* Kobold Settlement */
	mob_index[real_mobile0(1407)].func.mob = chicken;
	mob_index[real_mobile0(1433)].func.mob = stone_crumble;
	mob_index[real_mobile0(1436)].func.mob = tako_demon;
	mob_index[real_mobile0(1437)].func.mob = kobold_priest;
	mob_index[real_mobile0(1438)].func.mob = stone_golem;

	mob_index[real_mobile0(36203)].func.mob = mob_index[real_mobile0(132599)].func.mob =
		rentacleric;

	/* Evil Spec teachers */
	mob_index[real_mobile0(22467)].func.mob = 0; // zerker
	mob_index[real_mobile0(36440)].func.mob = 0; // assassin
	mob_index[real_mobile0(4401)].func.mob = 0; // cleric
	mob_index[real_mobile0(97585)].func.mob = 0; // illus
	mob_index[real_mobile0(36441)].func.mob = 0; // reaver
	mob_index[real_mobile0(36442)].func.mob = 0; // bard
	mob_index[real_mobile0(22434)].func.mob = 0; // warrior

	/* Undead Spec teachers */
	mob_index[real_mobile0(66238)].func.mob = 0; // reaver
	mob_index[real_mobile0(22415)].func.mob = 0; // AP
	mob_index[real_mobile0(22435)].func.mob = 0; // Mercenary
	mob_index[real_mobile0(90306)].func.mob = 0; // piper
	mob_index[real_mobile0(90328)].func.mob = 0; // dreadlord

	/* Goodie Spec teachers */
	mob_index[real_mobile0(82507)].func.mob = 0; // conj
	mob_index[real_mobile0(82500)].func.mob = 0; // ranger

	/* All side spec teachers */
	mob_index[real_mobile0(66736)].func.mob = 0; // shaman
	mob_index[real_mobile0(22420)].func.mob = 0; // shaman
	mob_index[real_mobile0(22441)].func.mob = 0; // thief
	mob_index[real_mobile0(9420)].func.mob = 0; // thief
	mob_index[real_mobile0(22440)].func.mob = 0; // assassin

	mob_index[real_mobile0(66732)].func.mob = 0; // AP
	mob_index[real_mobile0(9432)].func.mob = 0; // Warrior
	mob_index[real_mobile0(66731)].func.mob = 0; // Mercenary
	mob_index[real_mobile0(66631)].func.mob = 0; // Bard
	mob_index[real_mobile0(9454)].func.mob = 0; // Alch

	/* Bahamut */
	mob_index[real_mobile0(25700)].func.mob = bahamut;
	/* fooquest, now in Black Pearl */
	mob_index[real_mobile0(142212)].func.mob = fooquest_mob;
	mob_index[real_mobile0(142213)].func.mob = fooquest_boss;

	/* Goodie Highwayman */
	mob_index[real_mobile0(500058)].func.mob = goodie_guardian;

	/* images */
	mob_index[real_mobile0(250)].func.mob = imageproc;

	/*
	   Mt. Skelenak (New Moria)
	 */

	mob_index[real_mobile0(15)].func.mob = witch_doctor;
	mob_index[real_mobile0(21549)].func.mob = llyren;

	/*
	   The Underworld
	 */
	mob_index[real_mobile0(4480)].func.mob = purple_worm;
	mob_index[real_mobile0(700004)].func.mob = purple_worm;
	mob_index[real_mobile0(131232)].func.mob = purple_worm;
	mob_index[real_mobile0(4530)].func.mob = piercer;
	mob_index[real_mobile0(4520)].func.mob = underdark_track;
	mob_index[real_mobile0(4510)].func.mob = underdark_track;
	mob_index[real_mobile0(550)].func.mob = underdark_track;
	mob_index[real_mobile0(551)].func.mob = underdark_track;

	// Newbie guards! - Kvark
	mob_index[real_mobile0(910)].func.mob = newbie_guard_north;
	mob_index[real_mobile0(912)].func.mob = newbie_guard_east;
	mob_index[real_mobile0(911)].func.mob = newbie_guard_south;
	mob_index[real_mobile0(4800)].func.mob = newbie_guard_east;
	mob_index[real_mobile0(913)].func.mob = newbie_guard_west;

	// living earth proc!
	mob_index[real_mobile0(1104)].func.mob = living_stone;
	mob_index[real_mobile0(1105)].func.mob = greater_living_stone;

	// elemental swarm hulks
	/*
	mob_index[real_mobile0(69)].func.mob = elemental_swarm_earth;
	mob_index[real_mobile0(70)].func.mob = elemental_swarm_fire;
	mob_index[real_mobile0(71)].func.mob = elemental_swarm_air;
	mob_index[real_mobile0(72)].func.mob = elemental_swarm_water;
	*/

	/*Astral_Tiamat
	 */

	mob_index[real_mobile0(19705)].func.mob = guild_guard;

	/*
	   Alterian Region
	 */

	/*
	   dlsc (snik's zone) - temporary for testing
	 */

	/*
	   Western Realms
	 */
	mob_index[real_mobile0(5701)].func.mob = dryad;
	mob_index[real_mobile0(5702)].func.mob = dryad;
	mob_index[real_mobile0(5739)].func.mob = navagator;

	/* Human HT - Tharnadia */

	world[real_room0(132507)].funct = welfare_well;

	mob_index[real_mobile0(132593)].func.mob = janitor;
	mob_index[real_mobile0(132519)].func.mob = money_changer;
	mob_index[real_mobile0(98718)].func.mob = money_changer;
	mob_index[real_mobile0(82224)].func.mob = money_changer;
	mob_index[real_mobile0(132501)].func.mob = tharn_tall_merchant;
	mob_index[real_mobile0(132509)].func.mob = tharn_beach_guard;
	mob_index[real_mobile0(132510)].func.mob = tharn_male_commoner;
	mob_index[real_mobile0(132511)].func.mob = tharn_female_commoner;
	mob_index[real_mobile0(132537)].func.mob = tharn_female_commoner;
	mob_index[real_mobile0(132539)].func.mob = tharn_female_commoner;
	mob_index[real_mobile0(132532)].func.mob = tharn_human_merchant;
	mob_index[real_mobile0(132514)].func.mob = tharn_lighthouse_attendent;
	mob_index[real_mobile0(132531)].func.mob = tharn_crier_one;

	mob_index[real_mobile0(36420)].func.mob = world_quest; // Drow HT
	mob_index[real_mobile0(97540)].func.mob = world_quest; // Ixie
	mob_index[real_mobile0(132555)].func.mob = world_quest; // Tharn
	mob_index[real_mobile0(16553)].func.mob = world_quest; // Woodseer

	mob_index[real_mobile0(53670)].func.mob = world_quest; // Sunwell

	/* Hall of the Ancients */
	mob_index[real_mobile0(77714)].func.mob = morkoth_mother;
	mob_index[real_mobile0(77747)].func.mob = akckx;
	mob_index[real_mobile0(77750)].func.mob = human_girl;
	mob_index[real_mobile0(77751)].func.mob = hoa_death;
	mob_index[real_mobile0(77752)].func.mob = hoa_sin;

	/* Vecna */
	mob_index[real_mobile0(130002)].func.mob = vecna_mob_rebirth;
	mob_index[real_mobile0(130003)].func.mob = vecna_mob_rebirth;
	mob_index[real_mobile0(130004)].func.mob = vecna_mob_rebirth;
	mob_index[real_mobile0(130005)].func.mob = vecna_mob_rebirth;
	mob_index[real_mobile0(130030)].func.mob = block_dir;
	mob_index[real_mobile0(130031)].func.mob = block_dir;
	mob_index[real_mobile0(130032)].func.mob = block_dir;
	mob_index[real_mobile0(130033)].func.mob = block_dir;
	mob_index[real_mobile0(130034)].func.mob = block_dir;
	mob_index[real_mobile0(130035)].func.mob = vecnas_fight_proc;
	mob_index[real_mobile0(130016)].func.mob = chressan_shout;
	mob_index[real_mobile0(130028)].func.mob = vecna_black_mass;

	mob_index[real_mobile0(67324)].func.mob = world_quest;
	mob_index[real_mobile0(97540)].func.mob = world_quest;
	mob_index[real_mobile0(95517)].func.mob = world_quest;
	mob_index[real_mobile0(85751)].func.mob = world_quest;
	mob_index[real_mobile0(82511)].func.mob = world_quest;
	mob_index[real_mobile0(80194)].func.mob = world_quest;
	mob_index[real_mobile0(80123)].func.mob = world_quest;
	mob_index[real_mobile0(70029)].func.mob = world_quest;
	mob_index[real_mobile0(66041)].func.mob = world_quest;
	mob_index[real_mobile0(45055)].func.mob = world_quest;
	mob_index[real_mobile0(40466)].func.mob = world_quest;
	mob_index[real_mobile0(40410)].func.mob = world_quest;
	mob_index[real_mobile0(30831)].func.mob = world_quest;
	mob_index[real_mobile0(18707)].func.mob = world_quest;
	mob_index[real_mobile0(17022)].func.mob = world_quest;
	mob_index[real_mobile0(11601)].func.mob = world_quest;
	mob_index[real_mobile0(45010)].func.mob = world_quest;
	mob_index[real_mobile0(5755)].func.mob = world_quest;
	mob_index[real_mobile0(1603)].func.mob = world_quest;

	mob_index[real_mobile0(36420)].func.mob = world_quest;
	mob_index[real_mobile0(82229)].func.mob = world_quest;
	mob_index[real_mobile0(82208)].func.mob = world_quest;
	mob_index[real_mobile0(45063)].func.mob = world_quest;

	mob_index[real_mobile0(16553)].func.mob = world_quest;
	mob_index[real_mobile0(16553)].func.mob = world_quest;
	mob_index[real_mobile0(16553)].func.mob = world_quest;
	mob_index[real_mobile0(16553)].func.mob = world_quest;

	mob_index[real_mobile0(5347)].func.mob = world_quest;
	mob_index[real_mobile0(37718)].func.mob = world_quest;
	mob_index[real_mobile0(74060)].func.mob = world_quest;

	mob_index[real_mobile0(132551)].func.mob = world_quest;
	mob_index[real_mobile0(38309)].func.mob = world_quest;
	mob_index[real_mobile0(49064)].func.mob = world_quest;

	mob_index[real_mobile0(132542)].func.mob = tharn_shady_mercenary;
	mob_index[real_mobile0(132543)].func.mob = tharn_shady_youth;
	mob_index[real_mobile0(132544)].func.mob = tharn_jailor;
	mob_index[real_mobile0(132540)].func.mob = tharn_old_man;

	/* Harpy hometown */
	mob_index[real_mobile0(31103)].func.mob = money_changer;

	/* Sarmiz'Duul */

	mob_index[real_mobile0(9445)].func.mob = money_changer;
	mob_index[real_mobile0(9453)].func.mob = erzul_proc;

	/* Undead hometown */

	mob_index[real_mobile0(66208)].func.mob = money_changer;

	/* Aracdrathos */
	mob_index[real_mobile0(36413)].func.mob = money_changer;

	/* New Hope */
	mob_index[real_mobile0(89181)].func.mob = tentacler_death;

	/* Dragonnia */

	mob_index[real_mobile0(6801)].func.mob = demodragon;
	mob_index[real_mobile0(6814)].func.mob = dragon_guard;
	mob_index[real_mobile0(6828)].func.mob = baby_dragon;
	mob_index[real_mobile0(6813)].func.mob = dragon_guard;

	/* Harpy Hometown */
	mob_index[real_mobile0(31108)].func.mob = gargoyle_master;
	mob_index[real_mobile0(31109)].func.mob = harpy_good;
	mob_index[real_mobile0(31124)].func.mob = harpy_evil;

	/* Jademini - Jade Empire */
	mob_index[real_mobile0(77216)].func.mob = archer;

	/* Kimordril - Dwarf HT */
	mob_index[real_mobile0(95506)].func.mob = archer;
	mob_index[real_mobile0(95503)].func.mob = money_changer;
	mob_index[real_mobile0(95535)].func.mob = kimordril_shout;

	/* Ixarkon */
	mob_index[real_mobile0(96449)].func.mob = money_changer;
	world[real_room0(96549)].funct = pet_shops;

	/* Bloodstone */
	mob_index[real_mobile0(74073)].func.mob = bs_boss;
	mob_index[real_mobile0(74000)].func.mob = bs_citizen;
	mob_index[real_mobile0(74001)].func.mob = bs_comwoman;
	mob_index[real_mobile0(74088)].func.mob = bs_brat;
	mob_index[real_mobile0(74003)].func.mob = bs_holyman;
	mob_index[real_mobile0(74004)].func.mob = bs_merchant;
	mob_index[real_mobile0(74005)].func.mob = bs_wino;
	mob_index[real_mobile0(74092)].func.mob = bs_wino;
	mob_index[real_mobile0(74232)].func.mob = bs_watcher;
	mob_index[real_mobile0(74244)].func.mob = bs_guard;
	mob_index[real_mobile0(74245)].func.mob = bs_squire;
	mob_index[real_mobile0(74245)].func.mob = bs_squire;
	mob_index[real_mobile0(74006)].func.mob = bs_peddler;
	mob_index[real_mobile0(74242)].func.mob = bs_critter;
	mob_index[real_mobile0(74024)].func.mob = bs_critter;
	mob_index[real_mobile0(74113)].func.mob = bs_critter;
	mob_index[real_mobile0(74243)].func.mob = bs_critter;
	mob_index[real_mobile0(74007)].func.mob = bs_timid;
	mob_index[real_mobile0(74008)].func.mob = bs_shady;
	mob_index[real_mobile0(74009)].func.mob = bs_sinister;
	mob_index[real_mobile0(74009)].func.mob = bs_menacing;
	mob_index[real_mobile0(74009)].func.mob = bs_menacing;
	mob_index[real_mobile0(74011)].func.mob = bs_executioner;
	mob_index[real_mobile0(74012)].func.mob = bs_baron;
	mob_index[real_mobile0(74014)].func.mob = bs_sparrow;
	mob_index[real_mobile0(74015)].func.mob = bs_squirrel;
	mob_index[real_mobile0(74016)].func.mob = bs_squirrel;
	mob_index[real_mobile0(74017)].func.mob = bs_crow;
	mob_index[real_mobile0(74018)].func.mob = bs_mountainman;
	mob_index[real_mobile0(74019)].func.mob = bs_salesman;
	mob_index[real_mobile0(74020)].func.mob = bs_nomad;
	mob_index[real_mobile0(74241)].func.mob = bs_insane;
	mob_index[real_mobile0(74021)].func.mob = bs_homeless;
	mob_index[real_mobile0(74022)].func.mob = bs_servant;
	mob_index[real_mobile0(74023)].func.mob = bs_wolf;
	mob_index[real_mobile0(74026)].func.mob = bs_gnoll;
	mob_index[real_mobile0(74246)].func.mob = bs_griffon;
	mob_index[real_mobile0(74029)].func.mob = bs_boar;
	mob_index[real_mobile0(74030)].func.mob = bs_cub;
	mob_index[real_mobile0(74031)].func.mob = bs_fierce;
	mob_index[real_mobile0(74032)].func.mob = bs_fierce;
	mob_index[real_mobile0(74034)].func.mob = bs_stirge;
	mob_index[real_mobile0(74178)].func.mob = devour;
	mob_index[real_mobile0(74134)].func.mob = poison;
	mob_index[real_mobile0(74091)].func.mob = poison;
	mob_index[real_mobile0(74138)].func.mob = poison;
	mob_index[real_mobile0(74185)].func.mob = bs_barons_mistress;

	/* Obsidian Citadel */
	// mob_index[real_mobile0(75615)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75631)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75632)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75633)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75634)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75635)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75636)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75637)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75638)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75639)].func.mob = obsid_cit_death_knight;
	mob_index[real_mobile0(75640)].func.mob = obsid_cit_satar_ghulan;

	/* Charing */
	mob_index[real_mobile0(45025)].func.mob = guild_guard;
	mob_index[real_mobile0(45034)].func.mob = guild_guard;
	mob_index[real_mobile0(45001)].func.mob = guild_guard;
	mob_index[real_mobile0(45040)].func.mob = guild_guard;
	mob_index[real_mobile0(45041)].func.mob = guild_guard;
	mob_index[real_mobile0(45042)].func.mob = guild_guard;
	mob_index[real_mobile0(45044)].func.mob = janitor;
	mob_index[real_mobile0(45065)].func.mob = guild_guard;
	mob_index[real_mobile0(45066)].func.mob = guild_guard;
	mob_index[real_mobile0(45067)].func.mob = guild_guard;

	mob_index[real_mobile0(45049)].func.mob = guild_guard;

	/*
	   Split Shield
	 */
	mob_index[real_mobile0(10301)].func.mob = gate_guard;
	mob_index[real_mobile0(10302)].func.mob = shady_man;

	/*
	   Realms Master
	 */
	/*
	   Moonshae
	 */
	mob_index[real_mobile0(26218)].func.mob = sister_knight;
	mob_index[real_mobile0(26219)].func.mob = sister_knight;
	mob_index[real_mobile0(26220)].func.mob = sister_knight;
	mob_index[real_mobile0(26221)].func.mob = sister_knight;
	mob_index[real_mobile0(26222)].func.mob = sister_knight;

	/* Troll HT - Ghore */
	mob_index[real_mobile0(11542)].func.mob = ghore_paradise;
	mob_index[real_mobile0(11559)].func.mob = money_changer;
	mob_index[real_mobile0(11640)].func.mob = devour;
	mob_index[real_mobile0(11518)].func.mob = poison;

	/*
	   Lava Tubes One
	 */
	mob_index[real_mobile0(12000)].func.mob = snowbeast;
	mob_index[real_mobile0(12001)].func.mob = snowvulture;
	mob_index[real_mobile0(12002)].func.mob = spiny;
	mob_index[real_mobile0(12003)].func.mob = spiny;
	mob_index[real_mobile0(12005)].func.mob = phalanx;
	mob_index[real_mobile0(12006)].func.mob = skeleton;
	mob_index[real_mobile0(12022)].func.mob = spore_ball;
	mob_index[real_mobile0(12023)].func.mob = spore_ball;
	mob_index[real_mobile0(12024)].func.mob = skeleton;
	mob_index[real_mobile0(12025)].func.mob = xexos;
	mob_index[real_mobile0(12026)].func.mob = agthrodos;
	mob_index[real_mobile0(12027)].func.mob = automaton_unblock;

	/*
	   Twin Towers - Forest
	 */
	mob_index[real_mobile0(13505)].func.mob = mob_index[real_mobile0(13508)].func.mob =
		mob_index[real_mobile0(13511)].func.mob = mob_index[real_mobile0(13513)].func.mob =
			mob_index[real_mobile0(13515)].func.mob =
				mob_index[real_mobile0(13516)].func.mob =
					mob_index[real_mobile0(13517)].func.mob =
						mob_index[real_mobile0(13518)].func.mob =
							mob_index[real_mobile0(13519)].func.mob =
								forest_animals;

	/*
	   Faerie Realm
	 */
	mob_index[real_mobile0(14015)].func.mob = finn;
	mob_index[real_mobile0(14026)].func.mob = tree_spirit;
	mob_index[real_mobile0(14029)].func.mob = faerie;
	mob_index[real_mobile0(14048)].func.mob = cricket;

	/* Temple Zone */
	mob_index[real_mobile0(18302)].func.mob = temple_illyn;

	/*
	   WD bypass road
	 */
	mob_index[real_mobile0(14601)].func.mob = plant_attacks_poison;
	mob_index[real_mobile0(14602)].func.mob = plant_attacks_paralysis;
	mob_index[real_mobile0(14603)].func.mob = plant_attacks_blindness;
	mob_index[real_mobile0(14605)].func.mob = barbarian_spiritist;

	/* Duergar HT - Khildarak */
	mob_index[real_mobile0(17012)].func.mob = archer;
	mob_index[real_mobile0(17132)].func.mob = mob_index[real_mobile0(17134)].func.mob =
		mob_index[real_mobile0(17092)].func.mob = mob_index[real_mobile0(17049)].func.mob =
			mob_index[real_mobile0(17199)].func.mob =
				/*      mob_index[real_mobile0(17247)].func.mob =*/
		mob_index[real_mobile0(17202)].func.mob = devour;
	mob_index[real_mobile0(17247)].func.mob = guild_guard;
	mob_index[real_mobile0(17193)].func.mob = devour;
	mob_index[real_mobile0(17194)].func.mob = devour;
	mob_index[real_mobile0(17195)].func.mob = devour;
	mob_index[real_mobile0(17261)].func.mob = poison;

	/* Ogre HT - Faang */
	mob_index[real_mobile0(15200)].func.mob = boulder_pusher;
	mob_index[real_mobile0(15213)].func.mob = poison;
	mob_index[real_mobile0(15215)].func.mob = poison;

	/*
	   New Cavecity
	 */
	mob_index[real_mobile0(15113)].func.mob = dranum_jurtrem;
	mob_index[real_mobile0(15125)].func.mob = dranum_jurtrem;

	mob_index[real_mobile0(1255)].func.mob = random_quest_mob_proc;
	mob_index[real_mobile0(1256)].func.mob = random_mob_proc;
	/*
	   Astral Plane - Tiamat
	 */
	mob_index[real_mobile0(19700)].func.mob = tiamat;
	mob_index[real_mobile0(19710)].func.mob = guild_guard;
	mob_index[real_mobile0(19720)].func.mob = guild_guard;
	mob_index[real_mobile0(19730)].func.mob = guild_guard;
	mob_index[real_mobile0(19740)].func.mob = guild_guard;
	mob_index[real_mobile0(19880)].func.mob = astral_succubus;
	mob_index[real_mobile0(19600)].func.mob = block_dir;

	/* Shabo shouts */

	mob_index[real_mobile0(32828)].func.mob = strychnesch_shout;
	mob_index[real_mobile0(32830)].func.mob = morgoor_shout;
	mob_index[real_mobile0(32829)].func.mob = jabulanth_shout;
	mob_index[real_mobile0(32831)].func.mob = redpal_shout;
	mob_index[real_mobile0(32832)].func.mob = cyvrand_shout;
	mob_index[real_mobile0(32802)].func.mob = overseer_shout;
	mob_index[real_mobile0(32838)].func.mob = shabo_caran;

	/*
	   Plane of Fire One
	 */
	mob_index[real_mobile0(25400)].func.mob = guild_guard;
	mob_index[real_mobile0(25440)].func.mob = imix_shout;
	/* City of Brass */
	mob_index[real_mobile0(139001)].func.mob = guild_guard;
	mob_index[real_mobile0(139004)].func.mob = guild_guard;

	/*
	     Prison
	*/
	mob_index[real_mobile0(7333)].func.mob = warden_shout;

	/*
	     Nizari
	   */
	mob_index[real_mobile0(40053)].func.mob = thief;
	mob_index[real_mobile0(40054)].func.mob = thief;
	mob_index[real_mobile0(40055)].func.mob = thief;

	/*
	   Ashrumite Village
	 */
	mob_index[real_mobile0(66037)].func.mob = drunk_one;
	mob_index[real_mobile0(66001)].func.mob = cityguard;
	mob_index[real_mobile0(66002)].func.mob = cityguard;
	mob_index[real_mobile0(66003)].func.mob = cityguard;
	mob_index[real_mobile0(66031)].func.mob = guild_guard;
	mob_index[real_mobile0(66024)].func.mob = guild_guard;
	mob_index[real_mobile0(66023)].func.mob = guild_guard;
	mob_index[real_mobile0(66025)].func.mob = guild_guard;
	mob_index[real_mobile0(66022)].func.mob = guild_guard;
	mob_index[real_mobile0(66036)].func.mob = janitor;
	mob_index[real_mobile0(66038)].func.mob = money_changer;

	/*
	   Menden-on-the-Deep
	 */
	mob_index[real_mobile0(88805)].func.mob = menden_fisherman;
	mob_index[real_mobile0(88806)].func.mob = menden_magus;
	mob_index[real_mobile0(88812)].func.mob = menden_inv_serv_die;
	mob_index[real_mobile0(88813)].func.mob = menden_figurine_die;
	mob_index[real_mobile0(88814)].func.mob = crystal_golem_die;
	mob_index[real_mobile0(88815)].func.mob = hippogriff_die;

	/*
	   Mirar (Chionthar) Ferry
	 */
	/*
	  mob_index[real_mobile0(90590)].func.mob = navagator;
	*/

	/*
	   icecrag keep
	 */
	mob_index[real_mobile0(97000)].func.mob = ice_snooty_wife;
	mob_index[real_mobile0(97001)].func.mob = ice_cleaning_crew;
	mob_index[real_mobile0(97002)].func.mob = ice_artist;
	mob_index[real_mobile0(97005)].func.mob = ice_privates;
	mob_index[real_mobile0(97006)].func.mob = ice_masha;
	mob_index[real_mobile0(97007)].func.mob = ice_tubby_merchant;
	mob_index[real_mobile0(97008)].func.mob = ice_priest;
	mob_index[real_mobile0(97011)].func.mob = ice_garden_attendant;
	mob_index[real_mobile0(97014)].func.mob = ice_raucous_guest;
	mob_index[real_mobile0(97016)].func.mob = ice_tar;
	mob_index[real_mobile0(97021)].func.mob = ice_commander;
	mob_index[real_mobile0(97023)].func.mob = ice_viscount;
	mob_index[real_mobile0(97028)].func.mob = ice_masonary_crew;
	mob_index[real_mobile0(97033)].func.mob = ice_impatient_guest;
	/*
	  mob_index[real_mobile0(97018)].func.mob = ice_privates2;
	  mob_index[real_mobile0(97019)].func.mob = ice_privates2;
	*/
	mob_index[real_mobile0(97040)].func.mob = ice_bodyguards;
	mob_index[real_mobile0(97041)].func.mob = ice_bodyguards;
	mob_index[real_mobile0(97042)].func.mob = ice_bodyguards;
	mob_index[real_mobile0(97030)].func.mob = ice_wolf;
	mob_index[real_mobile0(97003)].func.mob = ice_malice;

	// Outposts
	mob_index[real_mobile0(OUTPOST_BUILDING_MOB)].func.mob = building_mob_proc;
	mob_index[real_mobile0(OUTPOST_GATEGUARD_WAR)].func.mob = outpost_gateguard_proc;

	/*
	   jotunhiem
	 */
	mob_index[real_mobile0(96030)].func.mob = jotun_balor;
	mob_index[real_mobile0(96040)].func.mob = jotun_utgard_loki;
	mob_index[real_mobile0(96013)].func.mob = jotun_mimer;
	mob_index[real_mobile0(96027)].func.mob = jotun_thrym;

	/*
	   torg
	 */
	mob_index[real_mobile0(28961)].func.mob = timoro_die;

	/*
	bogentok
	*/

	/*
	   negative material plan
	 */
	mob_index[real_mobile0(26603)].func.mob = neg_pocket;

	/*
	   neverwinter
	 */
	mob_index[real_mobile0(99001)].func.mob = nw_woodelf;
	mob_index[real_mobile0(99002)].func.mob = nw_elfhealer;
	mob_index[real_mobile0(99003)].func.mob = nw_ammaster;
	mob_index[real_mobile0(99004)].func.mob = nw_sapmaster;
	mob_index[real_mobile0(99005)].func.mob = nw_diamaster;
	mob_index[real_mobile0(99006)].func.mob = nw_rubmaster;
	mob_index[real_mobile0(99007)].func.mob = nw_emmaster;
	mob_index[real_mobile0(99009)].func.mob = nw_human;
	mob_index[real_mobile0(99010)].func.mob = nw_hafbreed;
	mob_index[real_mobile0(99011)].func.mob = nw_owl;
	mob_index[real_mobile0(99015)].func.mob = nw_golem;
	mob_index[real_mobile0(99016)].func.mob = nw_mirroid;
	mob_index[real_mobile0(99017)].func.mob = nw_agatha;
	mob_index[real_mobile0(99018)].func.mob = nw_farmer;
	mob_index[real_mobile0(99019)].func.mob = nw_chicken;
	mob_index[real_mobile0(99021)].func.mob = nw_pig;
	mob_index[real_mobile0(99022)].func.mob = nw_cow;
	mob_index[real_mobile0(99023)].func.mob = nw_chief;
	mob_index[real_mobile0(99028)].func.mob = nw_malchor;
	mob_index[real_mobile0(99029)].func.mob = nw_builder;
	mob_index[real_mobile0(99030)].func.mob = nw_carpen;
	mob_index[real_mobile0(99031)].func.mob = nw_logger;
	mob_index[real_mobile0(99032)].func.mob = nw_cutter;
	mob_index[real_mobile0(99033)].func.mob = nw_foreman;
	mob_index[real_mobile0(99034)].func.mob = nw_ansal;
	mob_index[real_mobile0(99035)].func.mob = nw_brock;
	mob_index[real_mobile0(99036)].func.mob = nw_merthol;
	mob_index[real_mobile0(99037)].func.mob = nw_vitnor;

	/*
	   undermountain
	 */

	/* elemental plane bosses shout */
	mob_index[real_mobile0(12400)].func.mob = menzellon_shout;
	mob_index[real_mobile0(23806)].func.mob = ogremoch_shout;
	mob_index[real_mobile0(23808)].func.mob = ogremoch_shout;
	mob_index[real_mobile0(23240)].func.mob = olhydra_shout;
	mob_index[real_mobile0(24440)].func.mob = yancbin_shout;
	mob_index[real_mobile0(23807)].func.mob = earth_treant;

	/* jind */
	mob_index[real_mobile0(82000)].func.mob = jindo_ticket_master;
	/* newbie zone this mob gives a special item to the newbie */
	mob_index[real_mobile0(22801)].func.mob = newbie_paladin;
	mob_index[real_mobile0(VMOB_CHAOS_GUIDE)].func.mob = newbie_paladin;
	// lowbie quest proc dont do this if your below lvl 35 thing
	mob_index[real_mobile0(142215)].func.mob = newbie_quest;
	mob_index[real_mobile0(142216)].func.mob = newbie_quest;
	mob_index[real_mobile0(142218)].func.mob = newbie_quest;
	mob_index[real_mobile0(142219)].func.mob = newbie_quest;
	mob_index[real_mobile0(142222)].func.mob = newbie_quest;
	mob_index[real_mobile0(142224)].func.mob = newbie_quest;
	mob_index[real_mobile0(142226)].func.mob = newbie_quest;
	mob_index[real_mobile0(142228)].func.mob = newbie_quest;
	mob_index[real_mobile0(142229)].func.mob = newbie_quest;
	mob_index[real_mobile0(142230)].func.mob = newbie_quest;
	mob_index[real_mobile0(142232)].func.mob = newbie_quest;
	mob_index[real_mobile0(142233)].func.mob = newbie_quest;
	mob_index[real_mobile0(142234)].func.mob = newbie_quest;

	/*CELESTIA PROCS*/
	mob_index[real_mobile0(45565)].func.mob = Malevolence;
	mob_index[real_mobile0(45571)].func.mob = Malevolence_vapor;
	mob_index[real_mobile0(45510)].func.mob = celestia_pulsar;

	/* Nyneth */
	mob_index[real_mobile0(22956)].func.mob = construct;
	mob_index[real_mobile0(38737)].func.mob = nyneth;

	// Myrloch Vale
	mob_index[real_mobile0(26402)].func.mob = unblock_on_death;
	mob_index[real_mobile0(25401)].func.mob = unblock_on_death;

	logit(LOG_STATUS, "   Booting the shops.");
	fprintf(stderr, "--    Booting the shops.\n");
	boot_the_shops();
	logit(LOG_STATUS, "   Assigning the shopkeepers.");
	fprintf(stderr, "--    Booting the shopkeepers.\n");
	assign_the_shopkeepers();
	index_shopkeeper_prototypes();

	logit(LOG_STATUS, "   Booting quests.");
	fprintf(stderr, "--    Booting the quests.\n");
	boot_the_quests();
	std::string zone_story_error;
	if (!zone_story_quest_runtime::bootstrap(&zone_story_error))
		logit(LOG_DEBUG, "Zone-story quest catalog disabled at boot: %s",
		      zone_story_error.c_str());
	else
		logit(LOG_STATUS, "Zone-story quest catalog ready: %zu definitions, revision %u",
		      zone_story_quest_runtime::service()->catalog().definitions.size(),
		      zone_story_quest_runtime::content_revision());
	logit(LOG_STATUS, "   Assigning questers.");
	fprintf(stderr, "--    Assigning the questors.\n");
	assign_the_questers();
}

/*
   assign special procedures to objects
 */

namespace
{
// One source for boot assignments and read-only valuation context. Keep table
// order: later assignments win. Chained legacy assignments are right-to-left.
#define OBJECT_BINDING(vnum, proc) \
	{                          \
		vnum, proc, #proc  \
	}
const object_proc_binding object_boot_bindings[] = {
	OBJECT_BINDING(500055, tharnrifts_portal),
	OBJECT_BINDING(55007, no_kill_priest_obj),
	OBJECT_BINDING(1372, jet_black_maul),
	OBJECT_BINDING(12028, moonstone_fragment),
	OBJECT_BINDING(96073, faith),
	OBJECT_BINDING(96012, mistweave),
	OBJECT_BINDING(96027, leather_vest),
	OBJECT_BINDING(96042, deva_cloak),
	OBJECT_BINDING(96059, icicle_cloak),
	OBJECT_BINDING(8406, ogrebane),
	OBJECT_BINDING(96066, giantbane),
	OBJECT_BINDING(20000, mindbreaker),
	OBJECT_BINDING(1270, treasure_chest),
	OBJECT_BINDING(453, cards_object),
	OBJECT_BINDING(34226, dwarfslayer),
	OBJECT_BINDING(354, artifact_monolith),
	OBJECT_BINDING(83457, miners_helmet),
	OBJECT_BINDING(29328, burbul_map_obj),
	OBJECT_BINDING(29329, chyron_search_obj),
	OBJECT_BINDING(VOBJ_WUTVR_MAP_PROC, burbul_map_obj),
	OBJECT_BINDING(VOBJ_WUTVR_SEARCH_PROC, chyron_search_obj),
	OBJECT_BINDING(132581, storage_locker_obj_hook),
	OBJECT_BINDING(3097, storage_locker_obj_hook),
	OBJECT_BINDING(4, blood_stains),
	OBJECT_BINDING(50, ice_shattered_bits),
	OBJECT_BINDING(VNUM_TRACKS, tracks),
	OBJECT_BINDING(99, frost_beacon),
	OBJECT_BINDING(110, ice_block),
	OBJECT_BINDING(3833, glades_dagger),
	OBJECT_BINDING(44499, lucky_weapon),
	OBJECT_BINDING(15907, mace_dragondeath),
	OBJECT_BINDING(17021, khildarak_warhammer),
	OBJECT_BINDING(80830, ogre_warlords_sword),
	OBJECT_BINDING(7365, flaming_axe_of_azer),
	OBJECT_BINDING(25711, mrinlor_whip),
	OBJECT_BINDING(135218, sphinx_prefect_crown),
	OBJECT_BINDING(38772, platemail_of_defense),
	OBJECT_BINDING(414, platemail_of_defense),
	OBJECT_BINDING(22063, master_set),
	OBJECT_BINDING(22237, master_set),
	OBJECT_BINDING(22621, master_set),
	OBJECT_BINDING(45530, master_set),
	OBJECT_BINDING(45531, master_set),
	OBJECT_BINDING(82545, master_set),
	OBJECT_BINDING(75857, master_set),
	OBJECT_BINDING(67207, staff_of_air_conjuration),
	OBJECT_BINDING(919, ioun_sustenance),
	OBJECT_BINDING(922, deflect_ioun),
	OBJECT_BINDING(923, ioun_testicle),
	OBJECT_BINDING(924, ioun_testicle),
	OBJECT_BINDING(925, ioun_testicle),
	OBJECT_BINDING(926, ioun_testicle),
	OBJECT_BINDING(920, ioun_warp),
	OBJECT_BINDING(1210, tendrils),
	OBJECT_BINDING(26665, elvenkind_cloak),
	OBJECT_BINDING(VOBJ_UNDEAD_FERRY, charon_ship),
	OBJECT_BINDING(23808, artifact_stone),
	OBJECT_BINDING(911, artifact_stone),
	OBJECT_BINDING(25719, artifact_stone),
	OBJECT_BINDING(26653, artifact_stone),
	OBJECT_BINDING(16268, artifact_stone),
	OBJECT_BINDING(16263, artifact_stone),
	OBJECT_BINDING(67280, artifact_stone),
	OBJECT_BINDING(67244, artifact_stone),
	OBJECT_BINDING(17, artifact_stone),
	OBJECT_BINDING(23806, earthquake_gauntlet),
	OBJECT_BINDING(910, artifact_biofeedback),
	OBJECT_BINDING(67215, artifact_biofeedback),
	OBJECT_BINDING(23807, blind_boots),
	OBJECT_BINDING(400237, thanksgiving_wings),
	OBJECT_BINDING(55320, artifact_stone),
	OBJECT_BINDING(419, moonstone),
	OBJECT_BINDING(433, moonstone),
	OBJECT_BINDING(17, artifact_hide),
	OBJECT_BINDING(23809, artifact_hide),
	OBJECT_BINDING(19916, artifact_hide),
	OBJECT_BINDING(12410, artifact_hide),
	OBJECT_BINDING(139138, artifact_hide),
	OBJECT_BINDING(97118, artifact_hide),
	OBJECT_BINDING(44170, artifact_hide),
	OBJECT_BINDING(70963, pathfinder),
	OBJECT_BINDING(41204, artifact_invisible),
	OBJECT_BINDING(71231, artifact_invisible),
	OBJECT_BINDING(32428, artifact_invisible),
	OBJECT_BINDING(32861, artifact_invisible),
	OBJECT_BINDING(23203, artifact_invisible),
	OBJECT_BINDING(23202, artifact_invisible),
	OBJECT_BINDING(16904, artifact_invisible),
	OBJECT_BINDING(7371, nexus),
	OBJECT_BINDING(26621, sanguine),
	OBJECT_BINDING(26662, neg_orb),
	OBJECT_BINDING(1230, totem_of_mastery),
	OBJECT_BINDING(48, god_bp),
	OBJECT_BINDING(49, out_of_god_bp),
	OBJECT_BINDING(38763, ring_of_regeneration),
	OBJECT_BINDING(31549, glowing_necklace),
	OBJECT_BINDING(32008, staff_shadow_summoning),
	OBJECT_BINDING(67245, rod_of_magic),
	OBJECT_BINDING(76032, proc_whirlwinds),
	OBJECT_BINDING(1220, lyrical_instrument_of_time),
	OBJECT_BINDING(32001, sinister_tactics_staff),
	OBJECT_BINDING(32831, pesky_imp_chest),
	OBJECT_BINDING(32832, pesky_imp_chest),
	OBJECT_BINDING(32833, pesky_imp_chest),
	OBJECT_BINDING(32822, holy_weapon),
	OBJECT_BINDING(32836, mox_totem),
	OBJECT_BINDING(32816, flayed_mind_mask),
	OBJECT_BINDING(67281, stalker_cloak),
	OBJECT_BINDING(32837, finslayer_air),
	OBJECT_BINDING(32862, aboleth_pendant),
	OBJECT_BINDING(32864, artifact_stone),
	OBJECT_BINDING(32850, tower_summoning),
	OBJECT_BINDING(32852, shabo_trap_north_two),
	OBJECT_BINDING(32851, shabo_trap_south),
	OBJECT_BINDING(32848, shabo_trap_south_two),
	OBJECT_BINDING(32834, shabo_trap_down),
	OBJECT_BINDING(32849, shabo_trap_up),
	OBJECT_BINDING(32826, shabo_trap_up_two),
	OBJECT_BINDING(46, lightning_armor),
	OBJECT_BINDING(47, imprison_armor),
	OBJECT_BINDING(45, slot_machine),
	OBJECT_BINDING(1191, fun_dagger),
	OBJECT_BINDING(2203, unspec_altar),
	OBJECT_BINDING(12016, unspec_altar),
	OBJECT_BINDING(1190, rax_red_dagger),
	OBJECT_BINDING(2204, cutting_dagger),
	OBJECT_BINDING(142248, circlet_of_light),
	OBJECT_BINDING(142253, ljs_sword),
	OBJECT_BINDING(142255, wuss_sword),
	OBJECT_BINDING(142257, head_guard_sword),
	OBJECT_BINDING(142258, priest_rudder),
	OBJECT_BINDING(142264, alch_bag),
	OBJECT_BINDING(142267, alch_rod),
	OBJECT_BINDING(142270, ljs_armor),
	OBJECT_BINDING(142271, dragon_skull_helm),
	OBJECT_BINDING(99447, nightcrawler_dagger),
	OBJECT_BINDING(66419, righteous_blade),
	OBJECT_BINDING(666, xmas_cap),
	OBJECT_BINDING(400, khaziddea_blade),
	OBJECT_BINDING(22070, revenant_helm),
	OBJECT_BINDING(25723, dragonlord_plate),
	OBJECT_BINDING(25745, sunblade),
	OBJECT_BINDING(25710, bloodfeast),
	OBJECT_BINDING(142249, dragonslayer),
	OBJECT_BINDING(34545, mankiller),
	OBJECT_BINDING(44179, madman_mangler),
	OBJECT_BINDING(44172, madman_shield),
	OBJECT_BINDING(44188, mentality_mace),
	OBJECT_BINDING(25, artifact_biofeedback),
	OBJECT_BINDING(67203, vapor),
	OBJECT_BINDING(45528, serpent_of_miracles),
	OBJECT_BINDING(45514, transparent_blade),
	OBJECT_BINDING(45525, Einjar),
	OBJECT_BINDING(35, tripboots),
	OBJECT_BINDING(38, blindbadge),
	OBJECT_BINDING(36, fumblegaunts),
	OBJECT_BINDING(37, confusionsword),
	OBJECT_BINDING(41, guild_badge),
	OBJECT_BINDING(VOBJ_RANDOM_THRUSTED, thrusted_eq_proc),
	OBJECT_BINDING(VOBJ_RANDOM_ARMOR, set_proc),
	OBJECT_BINDING(1251, encrusted_eq_proc),
	OBJECT_BINDING(251, parchment_forge),
	OBJECT_BINDING(400210, learn_recipe),
	OBJECT_BINDING(58, relic_proc),
	OBJECT_BINDING(59, relic_proc),
	OBJECT_BINDING(68, relic_proc),
	OBJECT_BINDING(69, cold_hammer),
	OBJECT_BINDING(34559, brainripper),
	OBJECT_BINDING(22962, hammer_titans),
	OBJECT_BINDING(38725, stormbringer),
	OBJECT_BINDING(67243, living_necroplasm),
	OBJECT_BINDING(67200, vigor_mask),
	OBJECT_BINDING(67239, church_door),
	OBJECT_BINDING(67260, splinter),
	OBJECT_BINDING(67206, demo_scimitar),
	OBJECT_BINDING(67272, dranum_mask),
	OBJECT_BINDING(67220, golem_chunk),
	OBJECT_BINDING(21, good_evil_sword),
	OBJECT_BINDING(22, good_evil_sword),
	OBJECT_BINDING(1234, banana),
	OBJECT_BINDING(358, epic_stone),
	OBJECT_BINDING(359, epic_stone),
	OBJECT_BINDING(360, epic_stone),
	OBJECT_BINDING(60, stat_pool_str),
	OBJECT_BINDING(61, stat_pool_dex),
	OBJECT_BINDING(62, stat_pool_agi),
	OBJECT_BINDING(63, stat_pool_con),
	OBJECT_BINDING(64, stat_pool_pow),
	OBJECT_BINDING(65, stat_pool_int),
	OBJECT_BINDING(66, stat_pool_wis),
	OBJECT_BINDING(67, stat_pool_cha),
	OBJECT_BINDING(930, stat_pool_luc),
	OBJECT_BINDING(72, spell_pool),
	OBJECT_BINDING(26666, transp_tow_misty_gloves),
	OBJECT_BINDING(11065, magic_mouth),
	OBJECT_BINDING(11064, magic_mouth),
	OBJECT_BINDING(11063, magic_mouth),
	OBJECT_BINDING(11062, magic_mouth),
	OBJECT_BINDING(11061, magic_mouth),
	OBJECT_BINDING(11060, magic_mouth),
	OBJECT_BINDING(11059, magic_mouth),
	OBJECT_BINDING(11058, magic_mouth),
	OBJECT_BINDING(11057, magic_mouth),
	OBJECT_BINDING(11056, magic_mouth),
	OBJECT_BINDING(11055, magic_mouth),
	OBJECT_BINDING(11054, magic_mouth),
	OBJECT_BINDING(11053, magic_mouth),
	OBJECT_BINDING(11052, magic_mouth),
	OBJECT_BINDING(11051, magic_mouth),
	OBJECT_BINDING(11002, magic_mouth),
	OBJECT_BINDING(56, dragoon_blade),
	OBJECT_BINDING(93, dragoon_lance),
	OBJECT_BINDING(171, dragoon_totem),
	OBJECT_BINDING(465, gc_portal),
	OBJECT_BINDING(466, ec_portal),
	OBJECT_BINDING(467, ud_portal),
	OBJECT_BINDING(468, uc_nexus_portal),
	OBJECT_BINDING(750, druid_spring),
	OBJECT_BINDING(749, blighter_pond),
	OBJECT_BINDING(1218, flying_citadel),
	OBJECT_BINDING(1222, gfstone),
	OBJECT_BINDING(192, disarm_pick_gloves),
	OBJECT_BINDING(67279, roulette_pistol),
	OBJECT_BINDING(67282, orb_of_deception),
	OBJECT_BINDING(427, super_cannon),
	OBJECT_BINDING(428, zombies_game),
	OBJECT_BINDING(435, proc_soldon_hat),
	OBJECT_BINDING(499, proc_lohrr),
	OBJECT_BINDING(469, divine_font),
	OBJECT_BINDING(77706, trap_razor_hooks),
	OBJECT_BINDING(77721, trap_tower1_para),
	OBJECT_BINDING(77731, trap_tower2_sleep),
	OBJECT_BINDING(77738, illesarus),
	OBJECT_BINDING(77734, artifact_stone),
	OBJECT_BINDING(77752, hoa_plat),
	OBJECT_BINDING(77749, artifact_stone),
	OBJECT_BINDING(130006, vecna_deathportal),
	OBJECT_BINDING(130003, vecna_deathaltar),
	OBJECT_BINDING(130040, vecna_stonemist),
	OBJECT_BINDING(130041, vecna_ghosthands),
	OBJECT_BINDING(130041, vecna_torturerroom),
	OBJECT_BINDING(130000, vecna_gorge),
	OBJECT_BINDING(130013, vecna_pestilence),
	OBJECT_BINDING(130009, vecna_minifist),
	OBJECT_BINDING(130007, vecna_dispel),
	OBJECT_BINDING(130008, vecna_boneaxe),
	OBJECT_BINDING(130027, vecna_staffoaken),
	OBJECT_BINDING(130028, vecna_krindor_main),
	OBJECT_BINDING(130018, vecna_death_mask),
	OBJECT_BINDING(130038, mob_vecna_procs),
	OBJECT_BINDING(130200, obj_tp_no_high_levels),
	OBJECT_BINDING(67900, arenaobj_proc),
	OBJECT_BINDING(23056, lifereaver),
	OBJECT_BINDING(366, flame_blade),
	OBJECT_BINDING(31514, SeaKingdom_Tsunami),
	OBJECT_BINDING(36744, shimmering_longsword),
	OBJECT_BINDING(36760, rod_of_zarbon),
	OBJECT_BINDING(16262, trans_tower_shadow_globe),
	OBJECT_BINDING(80747, burn_touch_obj),
	OBJECT_BINDING(80556, drowcrusher),
	OBJECT_BINDING(80579, squelcher),
	OBJECT_BINDING(80569, dragonarmor),
	OBJECT_BINDING(41304, kearonor_hide),
	OBJECT_BINDING(41349, hewards_mystical_organ),
	OBJECT_BINDING(42235, amethyst_orb),
	OBJECT_BINDING(41350, wand_of_wonder),
	OBJECT_BINDING(41918, blade_of_paladins),
	OBJECT_BINDING(41913, fade_drusus),
	OBJECT_BINDING(41915, lightning_sword),
	OBJECT_BINDING(41912, elfdawn_sword),
	OBJECT_BINDING(41917, flame_of_north_sword),
	OBJECT_BINDING(41914, magebane_falchion),
	OBJECT_BINDING(41916, woundhealer_scimitar),
	OBJECT_BINDING(41911, martelo_mstar),
	OBJECT_BINDING(41907, mir_fire),
	OBJECT_BINDING(18, githpc_special_weap),
	OBJECT_BINDING(19, githpc_special_weap),
	OBJECT_BINDING(418, githpc_special_weap),
	OBJECT_BINDING(19507, random_tomb),
	OBJECT_BINDING(19511, random_glass),
	OBJECT_BINDING(19515, random_slab),
	OBJECT_BINDING(70, refreshing_fountain),
	OBJECT_BINDING(71, magical_fountain),
	OBJECT_BINDING(751, portal_door),
	OBJECT_BINDING(291, magic_pool),
	OBJECT_BINDING(770, portal_wormhole),
	OBJECT_BINDING(780, portal_etherportal),
	OBJECT_BINDING(782, portal_door),
	OBJECT_BINDING(55, trustee_artifact),
	OBJECT_BINDING(1227, orcus_wand),
	OBJECT_BINDING(30, varon),
	OBJECT_BINDING(752, portal_door),
	OBJECT_BINDING(781, portal_door),
	OBJECT_BINDING(14, banana),
	OBJECT_BINDING(15, banana),
	OBJECT_BINDING(1278, changelog),
	OBJECT_BINDING(1300, obj_imprison),
	OBJECT_BINDING(VOBJ_WALLS, wall_generic),
	OBJECT_BINDING(54, huntsman_ward),
	OBJECT_BINDING(73, huntsman_ward),
	OBJECT_BINDING(77, huntsman_ward),
	OBJECT_BINDING(400229, huntsman_ward),
	OBJECT_BINDING(1421, item_switch),
	OBJECT_BINDING(1425, item_switch),
	OBJECT_BINDING(1427, item_switch),
	OBJECT_BINDING(4505, hammer),
	OBJECT_BINDING(4403, magic_pool),
	OBJECT_BINDING(4404, magic_pool),
	OBJECT_BINDING(17, barb),
	OBJECT_BINDING(132570, die_roller),
	OBJECT_BINDING(132609, die_roller),
	OBJECT_BINDING(132610, die_roller),
	OBJECT_BINDING(425, holy_weapon),
	OBJECT_BINDING(6826, dragonkind),
	OBJECT_BINDING(6818, resurrect_totem),
	OBJECT_BINDING(11008, guildwindow),
	OBJECT_BINDING(11013, guildhome),
	OBJECT_BINDING(12000, crystal_spike),
	OBJECT_BINDING(12027, automaton_lever),
	OBJECT_BINDING(96402, illithid_teleport_veil),
	OBJECT_BINDING(13519, forest_corpse),
	OBJECT_BINDING(13518, forest_corpse),
	OBJECT_BINDING(13517, forest_corpse),
	OBJECT_BINDING(13516, forest_corpse),
	OBJECT_BINDING(13515, forest_corpse),
	OBJECT_BINDING(13513, forest_corpse),
	OBJECT_BINDING(13511, forest_corpse),
	OBJECT_BINDING(13508, forest_corpse),
	OBJECT_BINDING(13505, forest_corpse),
	OBJECT_BINDING(15116, torment),
	OBJECT_BINDING(19710, magic_pool),
	OBJECT_BINDING(19711, magic_pool),
	OBJECT_BINDING(19715, magic_pool),
	OBJECT_BINDING(19730, avernus),
	OBJECT_BINDING(19860, magic_pool),
	OBJECT_BINDING(19861, magic_pool),
	OBJECT_BINDING(19862, magic_pool),
	OBJECT_BINDING(19863, magic_pool),
	OBJECT_BINDING(19864, magic_pool),
	OBJECT_BINDING(19900, githyanki),
	OBJECT_BINDING(12460, magic_pool),
	OBJECT_BINDING(12470, teleporting_pool),
	OBJECT_BINDING(12472, teleporting_pool),
	OBJECT_BINDING(12474, teleporting_pool),
	OBJECT_BINDING(12476, teleporting_pool),
	OBJECT_BINDING(45536, teleporting_pool),
	OBJECT_BINDING(30402, teleporting_map_pool),
	OBJECT_BINDING(30403, teleporting_pool),
	OBJECT_BINDING(30404, teleporting_pool),
	OBJECT_BINDING(30405, teleporting_pool),
	OBJECT_BINDING(30406, teleporting_pool),
	OBJECT_BINDING(30407, teleporting_pool),
	OBJECT_BINDING(30408, teleporting_pool),
	OBJECT_BINDING(30409, teleporting_pool),
	OBJECT_BINDING(30410, teleporting_pool),
	OBJECT_BINDING(30411, teleporting_pool),
	OBJECT_BINDING(30412, teleporting_pool),
	OBJECT_BINDING(30413, teleporting_pool),
	OBJECT_BINDING(30414, teleporting_pool),
	OBJECT_BINDING(36884, kvasir_dagger),
	OBJECT_BINDING(87612, doombringer),
	OBJECT_BINDING(430, flamberge),
	OBJECT_BINDING(139037, ring_elemental_control),
	OBJECT_BINDING(139004, holy_mace),
	OBJECT_BINDING(139002, staff_of_blue_flames),
	OBJECT_BINDING(30, staff_of_power),
	OBJECT_BINDING(40409, reliance_pegasus),
	OBJECT_BINDING(25404, magic_pool),
	OBJECT_BINDING(24404, magic_pool),
	OBJECT_BINDING(24406, lightning),
	OBJECT_BINDING(131616, dagger_of_wind),
	OBJECT_BINDING(23204, magic_pool),
	OBJECT_BINDING(23206, orb_of_the_sea),
	OBJECT_BINDING(23804, magic_pool),
	OBJECT_BINDING(23805, zion_mace_of_earth),
	OBJECT_BINDING(41203, unholy_avenger_bloodlust),
	OBJECT_BINDING(51005, holy_weapon),
	OBJECT_BINDING(51006, tiamat_stinger),
	OBJECT_BINDING(51401, dispator),
	OBJECT_BINDING(26014, nightbringer),
	OBJECT_BINDING(26413, item_switch),
	OBJECT_BINDING(26414, item_switch),
	OBJECT_BINDING(26415, item_switch),
	OBJECT_BINDING(26416, item_switch),
	OBJECT_BINDING(92090, undead_trident),
	OBJECT_BINDING(92080, generic_drow_eq),
	OBJECT_BINDING(92081, generic_drow_eq),
	OBJECT_BINDING(92082, generic_drow_eq),
	OBJECT_BINDING(92086, generic_drow_eq),
	OBJECT_BINDING(92065, iron_flindbar),
	OBJECT_BINDING(92020, generic_parry_proc),
	OBJECT_BINDING(82500, generic_parry_proc),
	OBJECT_BINDING(83605, generic_parry_proc),
	OBJECT_BINDING(18000, generic_riposte_proc),
	OBJECT_BINDING(92121, flame_of_north),
	OBJECT_BINDING(88825, menden_figurine),
	OBJECT_BINDING(88830, llyms_altar),
	OBJECT_BINDING(88821, magic_pool),
	OBJECT_BINDING(88827, magic_pool),
	OBJECT_BINDING(90004, fw_ruby_monocle),
	OBJECT_BINDING(90010, item_switch),
	OBJECT_BINDING(38649, sevenoaks_longsword),
	OBJECT_BINDING(67262, mace_of_sea),
	OBJECT_BINDING(67237, serpent_blade),
	OBJECT_BINDING(67242, lich_spine),
	OBJECT_BINDING(67276, sword_whirlwinds),
	OBJECT_BINDING(22803, stream_of_life),
	OBJECT_BINDING(22800, newbie_sign1),
	OBJECT_BINDING(22801, newbie_sign2),
	OBJECT_BINDING(VOBJ_CHAOS_STREAM, stream_of_life),
	OBJECT_BINDING(91200, newbie_sign1),
	OBJECT_BINDING(91201, newbie_sign2),
	OBJECT_BINDING(174, vareena_statue),
	OBJECT_BINDING(352, doom_blade_Proc),
	OBJECT_BINDING(426, doom_blade_Proc),
	OBJECT_BINDING(55008, storage_locker_obj_hook),
	OBJECT_BINDING(55210, dagger_ra),
	OBJECT_BINDING(55205, illithid_axe),
	OBJECT_BINDING(55211, deathseeker_mace),
	OBJECT_BINDING(55301, demon_slayer),
	OBJECT_BINDING(55277, snowogre_warhammer),
	OBJECT_BINDING(55306, volo_longsword),
	OBJECT_BINDING(55304, blur_shortsword),
	OBJECT_BINDING(55322, buckler_saints),
	OBJECT_BINDING(55309, helmet_vampires),
	OBJECT_BINDING(55315, storm_legplates),
	OBJECT_BINDING(55280, gauntlets_legend),
	OBJECT_BINDING(55377, gladius_backstabber),
	OBJECT_BINDING(55362, attribute_scroll),
	OBJECT_BINDING(97923, elemental_wand),
	OBJECT_BINDING(55361, earring_powers),
	OBJECT_BINDING(83698, earring_powers),
	OBJECT_BINDING(55363, lorekeeper_scroll),
	OBJECT_BINDING(55520, wh_corpse_decay),
	OBJECT_BINDING(55519, wh_corpse_decay),
	OBJECT_BINDING(55518, wh_corpse_decay),
	OBJECT_BINDING(55517, wh_corpse_decay),
	OBJECT_BINDING(55516, wh_corpse_decay),
	OBJECT_BINDING(55515, wh_corpse_decay),
	OBJECT_BINDING(55514, wh_corpse_decay),
	OBJECT_BINDING(55513, wh_corpse_decay),
	OBJECT_BINDING(55512, wh_corpse_decay),
	OBJECT_BINDING(55511, wh_corpse_decay),
	OBJECT_BINDING(55510, wh_corpse_decay),
	OBJECT_BINDING(55509, wh_corpse_decay),
	OBJECT_BINDING(55508, wh_corpse_decay),
	OBJECT_BINDING(55507, wh_corpse_decay),
	OBJECT_BINDING(55506, wh_corpse_decay),
	OBJECT_BINDING(55505, wh_corpse_decay),
	OBJECT_BINDING(55504, wh_corpse_decay),
	OBJECT_BINDING(55503, wh_corpse_decay),
	OBJECT_BINDING(55502, wh_corpse_decay),
	OBJECT_BINDING(55501, wh_corpse_decay),
	OBJECT_BINDING(55500, wh_corpse_decay),
	OBJECT_BINDING(53661, damnation_staff),
	OBJECT_BINDING(53662, nuke_damnation),
	OBJECT_BINDING(53663, nuke_damnation),
	OBJECT_BINDING(97932, collar_frost),
	OBJECT_BINDING(97931, collar_flames),
	OBJECT_BINDING(VOBJ_WH_DRAGONHEART_TIAMAT, dragon_heart_decay),
	OBJECT_BINDING(VOBJ_WH_DRAGONHEART_BAHAMUT, dragon_heart_decay),
	OBJECT_BINDING(VOBJ_WH_DRAGONHEART_DRAGONNIA, dragon_heart_decay),
	OBJECT_BINDING(55420, lancer_gift),
	OBJECT_BINDING(55077, splinter),
	OBJECT_BINDING(19638, zion_shield_absorb_proc),
	OBJECT_BINDING(38761, generic_shield_block_proc),
	OBJECT_BINDING(88327, zion_fnf),
	OBJECT_BINDING(16242, zion_light_dark),
	OBJECT_BINDING(58825, barovia_undead_necklace),
	OBJECT_BINDING(58424, artifact_shadow_shield),
	OBJECT_BINDING(58413, ravenloft_bell),
	OBJECT_BINDING(58400, shimmer_shortsword),
	OBJECT_BINDING(43584, toe_chamber_switch),
	OBJECT_BINDING(87712, hellfire_axe),
	OBJECT_BINDING(87724, illithid_whip),
	OBJECT_BINDING(87701, skull_leggings),
	OBJECT_BINDING(87737, flesh_golem_repop),
	OBJECT_BINDING(87950, deliverer_hammer),
	OBJECT_BINDING(93007, blue_sword_armor),
};

const object_proc_binding room_boot_bindings[] = {
	OBJECT_BINDING(5805, sword_named_magik),
	OBJECT_BINDING(29236, newbie_portal),
	OBJECT_BINDING(91436, newbie_portal),
	OBJECT_BINDING(32486, bel_sword),
	OBJECT_BINDING(99432, zarthos_vampire_slayer),
	OBJECT_BINDING(36894, critical_attack_proc),
	OBJECT_BINDING(44165, unmulti_altar),
	OBJECT_BINDING(87546, mask_of_wildmagic),
	OBJECT_BINDING(87601, flow_amulet),
	OBJECT_BINDING(87611, juiblex_grid_mob_generator),
	OBJECT_BINDING(67274, zion_netheril),
	OBJECT_BINDING(32615, eth2_tree_obj),
	OBJECT_BINDING(32614, eth2_tree_obj),
	OBJECT_BINDING(32619, eth2_godsfury),
	OBJECT_BINDING(32621, eth2_aramus_crown),
	OBJECT_BINDING(424, lucrot_mindstone),
	OBJECT_BINDING(120051, wh_corpse_decay),
	OBJECT_BINDING(55433, magic_deck),
	OBJECT_BINDING(1203, gellz_test_obj_procs),
	OBJECT_BINDING(55434, blackjack_table),
};
#undef OBJECT_BINDING
} // namespace

std::span<const object_proc_binding> object_proc_bindings(object_proc_binding_stage stage)
{
	if (stage == object_proc_binding_stage::objects)
		return object_boot_bindings;
	return room_boot_bindings;
}

void assign_object_proc_bindings(object_proc_binding_stage stage)
{
	// Empty offline catalogs have no index. Preserve the legacy lookup/fallback
	// policy when an index is present; changing missing-vnum policy is separate.
	if (!obj_index)
		return;
	for (const auto &binding : object_proc_bindings(stage))
		obj_index[real_object0(binding.vnum)].func.obj = binding.proc;
}

void assign_objects(void)
{
	assign_object_proc_bindings(object_proc_binding_stage::objects);
	mob_index[real_mobile0(33)].func.mob = necro_specpet_bone;
	mob_index[real_mobile0(34)].func.mob = necro_specpet_flesh;
	mob_index[real_mobile0(35)].func.mob = necro_specpet_flesh;
	mob_index[real_mobile0(1121)].func.mob = conj_specpet_golem;
	mob_index[real_mobile0(1122)].func.mob = conj_specpet_xorn;
	mob_index[real_mobile0(1131)].func.mob = conj_specpet_slyph;
	mob_index[real_mobile0(1132)].func.mob = conj_specpet_djinni;
	mob_index[real_mobile0(1141)].func.mob = conj_specpet_undine;
	mob_index[real_mobile0(1142)].func.mob = conj_specpet_triton;
	mob_index[real_mobile0(1112)].func.mob = conj_specpet_serpent;
	mob_index[real_mobile0(32840)].func.mob = shabo_butler;
	mob_index[real_mobile0(32843)].func.mob = shabo_petre;
	mob_index[real_mobile0(32842)].func.mob = shabo_palle;
	mob_index[real_mobile0(32803)].func.mob = shabo_derro_savant;
	mob_index[real_mobile0(1000)].func.mob = annoying_mob;
	mob_index[real_mobile0(320)].func.mob = cow_talk;
	mob_index[real_mobile0(11)].func.mob = raoul;
	mob_index[real_mobile0(12)].func.mob = christine;
	mob_index[real_mobile0(13)].func.mob = cookie_monster;
	mob_index[real_mobile0(142235)].func.mob = long_john_silver_shout;
	mob_index[real_mobile0(142242)].func.mob = undead_parrot;
	mob_index[real_mobile0(142246)].func.mob = undead_dragon_east;
	mob_index[real_mobile0(142252)].func.mob = pirate_cabinboy_talk;
	mob_index[real_mobile0(142254)].func.mob = pirate_female_talk;
	mob_index[real_mobile0(142202)].func.mob = pirate_talk;
	mob_index[real_mobile0(142203)].func.mob = pirate_talk;
	mob_index[real_mobile0(142239)].func.mob = pirate_talk;
	mob_index[real_mobile0(142240)].func.mob = pirate_talk;
	mob_index[real_mobile0(142241)].func.mob = pirate_talk;
	mob_index[real_mobile0(142249)].func.mob = pirate_talk;
	mob_index[real_mobile0(142251)].func.mob = pirate_talk;
	mob_index[real_mobile0(142261)].func.mob = pirate_talk;
	mob_index[real_mobile0(9342)].func.mob = bulette;
	mob_index[real_mobile0(9344)].func.mob = bulette;
	mob_index[real_mobile0(9345)].func.mob = bulette;
	mob_index[real_mobile0(9346)].func.mob = bulette;
	mob_index[real_mobile0(9347)].func.mob = bulette;
	mob_index[real_mobile0(9348)].func.mob = bulette;
	mob_index[real_mobile0(9349)].func.mob = bulette;
	mob_index[real_mobile0(9350)].func.mob = bulette;
	mob_index[real_mobile0(19750)].func.mob = guild_guard;
	mob_index[real_mobile0(19704)].func.mob = demogorgon;
	mob_index[real_mobile0(19920)].func.mob = demogorgon_shout;
	mob_index[real_mobile0(58387)].func.mob = ravenloft_vistani_shout;
	mob_index[real_mobile0(34014)].func.mob = block_dir;
	mob_index[real_mobile0(43576)].func.mob = eligoth_rift_spawn;
	mob_index[real_mobile0(87704)].func.mob = block_dir;
	mob_index[real_mobile0(87741)].func.mob = block_dir;
	mob_index[real_mobile0(87743)].func.mob = block_dir;
	mob_index[real_mobile0(87734)].func.mob = block_dir;
	mob_index[real_mobile0(87733)].func.mob = snogres_lich_shout;
	mob_index[real_mobile0(87734)].func.mob = snogres_flesh_golem;
	mob_index[real_mobile0(87700)].func.mob = berserker_toss;
	mob_index[real_mobile0(87724)].func.mob = remo_burn;
	mob_index[real_mobile0(78476)].func.mob = caertannad_summon;
	mob_index[real_mobile0(5503)].func.mob = undead_howl;
	mob_index[real_mobile0(6307)].func.mob = mist_protect;
	mob_index[real_mobile0(1709)].func.mob = world_quest;
	world[real_room0(1719)].funct = ship_shop_proc;
	mob_index[real_mobile0(88316)].func.mob = kossuth;
	mob_index[real_mobile0(88319)].func.mob = fruaack_shout;
	mob_index[real_mobile0(88301)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88302)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88303)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88304)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88305)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88306)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88308)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88310)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88323)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88324)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88325)].func.mob = charcoal_guard;
	mob_index[real_mobile0(88329)].func.mob = block_dir;
}

/*
   assign special procedures to rooms
 */

void assign_rooms(void)
{
	int x;
	assign_object_proc_bindings(object_proc_binding_stage::rooms);
	for (x = 32907; x <= 32909; x++)
	{
		world[real_room0(x)].funct = shaboath_alternation_tower;
	}
	for (x = 32910; x <= 32911; x++)
	{
		world[real_room0(x)].funct = shaboath_necromancy_tower;
	}
	for (x = 32901; x <= 32902; x++)
	{
		world[real_room0(x)].funct = shaboath_enchantment_tower;
	}
	world[real_room0(1134)].funct = cage_room1;
	world[real_room0(42)].funct = cage_room2;
	world[real_room0(1201)].funct = player_council_room;
	world[real_room0(17)].funct = multiclass_proc;
	world[real_room0(52904)].funct = multiclass_proc;
	for (x = 11200; x <= 11217; x++)
	{
		world[real_room0(x)].funct = squid_arena;
	}
	world[real_room0(18729)].funct = inn;
	world[real_room0(35264)].funct = inn;
	world[real_room0(37715)].funct = inn;
	world[real_room0(37313)].funct = inn;
	world[real_room0(40454)].funct = inn;
	world[real_room0(37434)].funct = inn;
	world[real_room0(21611)].funct = inn;
	world[real_room0(67493)].funct = inn;
	world[real_room0(18729)].funct = inn;
	world[real_room0(67503)].funct = inn;
	world[real_room0(81070)].funct = inn;
	world[real_room0(81028)].funct = inn;
	world[real_room0(81019)].funct = inn;
	world[real_room0(81078)].funct = inn;
	world[real_room0(81003)].funct = inn;
	world[real_room0(77442)].funct = inn;
	world[real_room0(82217)].funct = inn;
	world[real_room0(82574)].funct = inn;
	world[real_room0(99715)].funct = inn;
	world[real_room0(10857)].funct = inn;
	world[real_room0(1736)].funct = inn;
	world[real_room0(139078)].funct = inn;
	world[real_room0(36564)].funct = inn;
	world[real_room0(36567)].funct = pet_shops;
	world[real_room0(74916)].funct = stat_shops;
	world[real_room0(28281)].funct = stat_shops;
	world[real_room0(5783)].funct = pet_shops;
	world[real_room0(37716)].funct = inn;
	world[real_room0(14362)].funct = inn;
	world[real_room0(45006)].funct = inn;
	world[real_room0(45036)].funct = pet_shops;
	world[real_room0(29280)].funct = pet_shops;
	world[real_room0(29282)].funct = pet_shops;
	world[real_room0(91480)].funct = pet_shops;
	world[real_room0(91482)].funct = pet_shops;
	world[real_room0(5300)].funct = inn;
	mob_index[real_mobile0(5347)].func.mob = world_quest;
	world[real_room0(6841)].funct = room_of_sanctum;
	world[real_room0(130079)].funct = vecna_bubble_room;
	world[real_room0(39313)].funct = inn;
	world[real_room0(97757)].funct = pet_shops;
	world[real_room0(76241)].funct = pet_shops;
	world[real_room0(97663)].funct = inn;
	world[real_room0(67710)].funct = inn;
	world[real_room0(17302)].funct = pet_shops;
	world[real_room0(17591)].funct = pet_shops;
	world[real_room0(17087)].funct = inn;
	world[real_room0(132575)].funct = inn;
	world[real_room0(132614)].funct = pet_shops;
	world[real_room0(132868)].funct = pet_shops;
	world[real_room0(132743)].funct = pet_shops;
	world[real_room0(83786)].funct = ship_shop_proc;
	world[real_room0(88846)].funct = ship_shop_proc;
	world[real_room0(43198)].funct = ship_shop_proc;
	world[real_room0(43158)].funct = ship_shop_proc;
	world[real_room0(22441)].funct = ship_shop_proc;
	world[real_room0(43118)].funct = ship_shop_proc;
	world[real_room0(635260)].funct = ship_shop_proc;
	world[real_room0(584171)].funct = ship_shop_proc;
	world[real_room0(55410)].funct = ship_shop_proc;
	world[real_room0(133051)].funct = ship_shop_proc;
	world[real_room0(77)].funct = crew_shop_proc;
	world[real_room0(1734)].funct = crew_shop_proc;
	world[real_room0(9704)].funct = crew_shop_proc;
	world[real_room0(43220)].funct = crew_shop_proc;
	world[real_room0(43221)].funct = crew_shop_proc;
	world[real_room0(43222)].funct = crew_shop_proc;
	world[real_room0(28197)].funct = crew_shop_proc;
	world[real_room0(22481)].funct = crew_shop_proc;
	world[real_room0(66735)].funct = crew_shop_proc;
	world[real_room0(82641)].funct = crew_shop_proc;
	world[real_room0(54240)].funct = crew_shop_proc;
	world[real_room0(38107)].funct = crew_shop_proc;
	world[real_room0(49051)].funct = crew_shop_proc;
	world[real_room0(81021)].funct = crew_shop_proc;
	world[real_room0(76859)].funct = crew_shop_proc;
	world[real_room0(133075)].funct = crew_shop_proc;
	world[real_room0(55418)].funct = crew_shop_proc;
	world[real_room0(22648)].funct = crew_shop_proc;
	world[real_room0(559633)].funct = ship_shop_proc;
	world[real_room0(82669)].funct = ship_shop_proc;
	world[real_room0(49090)].funct = ship_shop_proc;
	world[real_room0(74271)].funct = inn;
	world[real_room0(37716)].funct = inn;
	world[real_room0(45132)].funct = dump;
	world[real_room0(45150)].funct = pet_shops;
	world[real_room0(9738)].funct = inn;
	world[real_room0(9967)].funct = ship_shop_proc;
	world[real_room0(66689)].funct = ship_shop_proc;
	world[real_room0(76659)].funct = ship_shop_proc;
	world[real_room0(30504)].funct = inn;
	world[real_room0(29701)].funct = inn;
	world[real_room0(29305)].funct = inn;
	world[real_room0(29103)].funct = inn;
	world[real_room0(29812)].funct = inn;
	world[real_room0(30104)].funct = inn;
	world[real_room0(29202)].funct = inn;
	world[real_room0(91505)].funct = inn;
	world[real_room0(91402)].funct = inn;
	world[real_room0(29403)].funct = inn;
	world[real_room0(13714)].funct = inn;
	world[real_room0(11923)].funct = dump;
	world[real_room0(11901)].funct = inn;
	world[real_room0(36334)].funct = inn;
	world[real_room0(6535)].funct = inn;
	world[real_room0(1444)].funct = inn;
	world[real_room0(26566)].funct = inn;
	world[real_room0(15264)].funct = inn;
	world[real_room0(95569)].funct = inn;
	world[real_room0(96537)].funct = inn;
	world[real_room0(12158)].funct = automaton_trapdoor;
	world[real_room0(13553)].funct = world[real_room0(13555)].funct =
		world[real_room0(13556)].funct = world[real_room0(13557)].funct =
			world[real_room0(13558)].funct = world[real_room0(13564)].funct =
				world[real_room0(13565)].funct = world[real_room0(13567)].funct =
					world[real_room0(13568)].funct =
						world[real_room0(13569)].funct =
							world[real_room0(13570)].funct =
								world[real_room0(13571)].funct =
									gardener_block;
	world[real_room0(16558)].funct = inn;
	world[real_room0(16886)].funct = pet_shops;
	world[real_room0(66054)].funct = inn;
	world[real_room0(66080)].funct = dump;
	world[real_room0(66116)].funct = pet_shops;
	world[real_room0(90107)].funct = fw_warning_room;
	world[real_room0(90112)].funct = fw_warning_room;
	world[real_room0(90114)].funct = fw_warning_room;
	world[real_room0(70175)].funct = inn;
	world[real_room0(NEUTRAL_HEAVEN_ROOM)].funct = mortal_heaven;
	world[real_room0(EVIL_HEAVEN_ROOM)].funct = mortal_heaven;
	world[real_room0(GOOD_HEAVEN_ROOM)].funct = mortal_heaven;
	world[real_room0(UNDEAD_HEAVEN_ROOM)].funct = mortal_heaven;
	mob_index[real_mobile0(46)].func.mob = epic_teacher;
	mob_index[real_mobile0(54)].func.mob = epic_familiar;
	mob_index[real_mobile0(55)].func.mob = epic_familiar;
	mob_index[real_mobile0(56)].func.mob = epic_familiar;
	mob_index[real_mobile0(57)].func.mob = epic_familiar;
	mob_index[real_mobile0(58)].func.mob = epic_familiar;
	mob_index[real_mobile0(59)].func.mob = epic_familiar;
	mob_index[real_mobile0(132674)].func.mob = learn_tradeskill;
	mob_index[real_mobile0(17264)].func.mob = learn_tradeskill;
	mob_index[real_mobile0(400000)].func.mob = epic_store;
	mob_index[real_mobile0(400001)].func.mob = pvp_store;
	mob_index[real_mobile0(132675)].func.mob = assoc_founder;
	mob_index[real_mobile0(17265)].func.mob = assoc_founder;
	world[real_room0(57068)].funct = pet_shops;
	mob_index[real_mobile0(87542)].func.mob = slime_lake;
	mob_index[real_mobile0(87543)].func.mob = juiblex_one;
	mob_index[real_mobile0(32604)].func.mob = block_dir;
	mob_index[real_mobile0(32613)].func.mob = block_dir;
	mob_index[real_mobile0(32624)].func.mob = eth2_forest_animal;
	mob_index[real_mobile0(32625)].func.mob = eth2_forest_animal;
	mob_index[real_mobile0(32626)].func.mob = eth2_forest_animal;
	mob_index[real_mobile0(32627)].func.mob = eth2_little_girl;
	mob_index[real_mobile0(32631)].func.mob = eth2_demon_princess;
	mob_index[real_mobile0(32628)].func.mob = block_dir;
	mob_index[real_mobile0(32629)].func.mob = block_dir;
	mob_index[real_mobile0(32637)].func.mob = eth2_aramus;
	mob_index[real_mobile0(83414)].func.mob = rentacleric;
	mob_index[real_mobile0(120051)].func.mob = wh_corpse_to_object;
	mob_index[real_mobile0(VMOB_ALATORIN_STEELGRIP)].func.mob = smelter;
	assign_ship_crew_funcs();
}

/*
 ********************************************************************
 *  Handling funcs                                                     *
 ********************************************************************
 */

void room_procs(void)
{
	int i;

	for (i = 0; i < top_of_world; i++)
		if (world[i].funct)
			(*world[i].funct)(i, NULL, 0, NULL);
}
