#include "core/defines.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "world/weather.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

// Harness state
static std::string last_output;
static room_data test_world[100000];
P_room world = test_world;
static sector_data test_sectors[100];
struct sector_data *sector_table = test_sectors;

void send_to_char(const char *text, P_char)
{
	last_output += text;
}

void send_to_char(const char *text, P_char, const OutputContext &)
{
	last_output += text;
}

void act(const char *text, int, P_char, P_obj, void *, int)
{
	if (text)
		last_output += text;
}

int in_weather_sector(int)
{
	return 0;
}

int number(int from, int)
{
	return from;
}

int BOUNDED(int min, int val, int max)
{
	if (val < min)
		return min;
	if (val > max)
		return max;
	return val;
}

char *one_argument(const char *argument, char *first_arg)
{
	if (!argument)
	{
		*first_arg = '\0';
		return nullptr;
	}
	while (*argument && isspace((unsigned char)*argument))
		argument++;
	while (*argument && !isspace((unsigned char)*argument))
		*first_arg++ = *argument++;
	*first_arg = '\0';
	while (*argument && isspace((unsigned char)*argument))
		argument++;
	return const_cast<char *>(argument);
}

// Minimal stubs for smoke.c dependencies not reached by test paths
P_obj get_obj_in_list_vis(P_char, const char *, P_obj, bool)
{
	return nullptr;
}

bool isname(const char *, const char *)
{
	return false;
}

void update_pos(P_char) {}
void extract_obj(P_obj, int) {}
int get_property(const char *, int)
{
	return 0;
}
affected_type *affect_to_char(P_char, affected_type *)
{
	return nullptr;
}
P_char get_linked_char(P_char, unsigned short)
{
	return nullptr;
}
void affect_from_char(P_char, int) {}
bool affected_by_spell(P_char, int)
{
	return false;
}
int GET_CLASS(P_char, unsigned int)
{
	return 0;
}

static char_data make_character(int race, int room_num)
{
	char_data ch;
	std::memset(&ch, 0, sizeof(ch));
	ch.in_room = room_num;
	ch.player.race = race;
	ch.specials.act = ACT_ISNPC; // alive
	SET_POS(&ch, POS_STANDING + STAT_NORMAL);
	ch.points.hit = 100;
	ch.points.max_hit = 100;
	return ch;
}

int main()
{
	// Set up weather sector 0 conditions
	std::memset(test_sectors, 0, sizeof(test_sectors));
	test_sectors[0].conditions.precip_rate = 50; // Active surface precipitation (rain)
	test_sectors[0].conditions.temp = 20;

	// Set up Room 96587 from areas/wld/ixarkon.wld
	// Room 96587: zone 964, flags 142639169, sector 14 (SECT_UNDRWLD_CITY)
	test_world[96587].number = 96587;
	test_world[96587].zone = 964;
	test_world[96587].sector_type = SECT_UNDRWLD_CITY;
	test_world[96587].room_flags = 142639169;

	// 1. Verify Underdark canyon room 96587 during surface rain
	{
		char_data ch = make_character(RACE_HUMAN, 96587);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
	}

	// 2. Verify all other underground terrain types during surface rain
	const int ud_sectors[] = {
		SECT_UNDRWLD_WILD,     SECT_UNDRWLD_INSIDE,   SECT_UNDRWLD_NOGROUND,
		SECT_UNDRWLD_MOUNTAIN, SECT_UNDRWLD_SLIME,    SECT_UNDRWLD_LOWCEIL,
		SECT_UNDRWLD_LIQMITH,  SECT_UNDRWLD_MUSHROOM,
	};
	int test_rnum = 1000;
	for (int sect : ud_sectors)
	{
		test_world[test_rnum].number = test_rnum;
		test_world[test_rnum].sector_type = sect;
		test_world[test_rnum].room_flags = 0; // No special room flags
		char_data ch = make_character(RACE_HUMAN, test_rnum);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
		test_rnum++;
	}

	// 3. Verify genuine rainy surface room (SECT_FIELD, outdoor, unflagged)
	{
		int field_room = 2000;
		test_world[field_room].number = field_room;
		test_world[field_room].sector_type = SECT_FIELD;
		test_world[field_room].room_flags = 0;
		char_data ch = make_character(RACE_HUMAN, field_room);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") != std::string::npos);
	}

	// 4. Verify surface outdoor room with NO precipitation (precip_rate = 0)
	{
		test_sectors[0].conditions.precip_rate = 0;
		int dry_room = 2001;
		test_world[dry_room].number = dry_room;
		test_world[dry_room].sector_type = SECT_FIELD;
		test_world[dry_room].room_flags = 0;
		char_data ch = make_character(RACE_HUMAN, dry_room);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
		// Restore precipitation
		test_sectors[0].conditions.precip_rate = 50;
	}

	// 5. Verify sheltered surface rooms during surface rain
	// 5a. ROOM_INDOORS
	{
		int indoor_room = 2002;
		test_world[indoor_room].number = indoor_room;
		test_world[indoor_room].sector_type = SECT_FIELD;
		test_world[indoor_room].room_flags = ROOM_INDOORS;
		char_data ch = make_character(RACE_HUMAN, indoor_room);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
	}
	// 5b. SECT_INSIDE
	{
		int sect_inside_room = 2003;
		test_world[sect_inside_room].number = sect_inside_room;
		test_world[sect_inside_room].sector_type = SECT_INSIDE;
		test_world[sect_inside_room].room_flags = 0;
		char_data ch = make_character(RACE_HUMAN, sect_inside_room);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
	}
	// 5c. ROOM_NO_PRECIP
	{
		int no_precip_room = 2004;
		test_world[no_precip_room].number = no_precip_room;
		test_world[no_precip_room].sector_type = SECT_FIELD;
		test_world[no_precip_room].room_flags = ROOM_NO_PRECIP;
		char_data ch = make_character(RACE_HUMAN, no_precip_room);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
	}
	// 5d. ROOM_TUNNEL
	{
		int tunnel_room = 2005;
		test_world[tunnel_room].number = tunnel_room;
		test_world[tunnel_room].sector_type = SECT_FIELD;
		test_world[tunnel_room].room_flags = ROOM_TUNNEL;
		char_data ch = make_character(RACE_HUMAN, tunnel_room);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
	}

	// 6. Verify planar rooms during precipitation
	{
		int fire_plane = 2006;
		test_world[fire_plane].number = fire_plane;
		test_world[fire_plane].sector_type = SECT_FIREPLANE;
		test_world[fire_plane].room_flags = 0;
		char_data ch = make_character(RACE_HUMAN, fire_plane);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
	}
	{
		int astral_plane = 2007;
		test_world[astral_plane].number = astral_plane;
		test_world[astral_plane].sector_type = SECT_ASTRAL;
		test_world[astral_plane].room_flags = 0;
		char_data ch = make_character(RACE_HUMAN, astral_plane);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("There is no way you can") == std::string::npos);
		assert(last_output.find("Smoke&n what?") != std::string::npos);
	}

	// 7. Verify water restrictions preserved in Underworld water sectors
	{
		int ud_water_room = 2008;
		test_world[ud_water_room].number = ud_water_room;
		test_world[ud_water_room].sector_type = SECT_UNDRWLD_WATER;
		test_world[ud_water_room].room_flags = 0;
		char_data ch = make_character(RACE_HUMAN, ud_water_room);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("impossiblity") != std::string::npos);
	}

	// 8. Verify visibility restrictions preserved underground
	{
		char_data ch = make_character(RACE_HUMAN, 96587);
		SET_BIT(ch.specials.affected_by, AFF_BLIND);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("blind") != std::string::npos);
	}

	// 9. Verify racial restrictions preserved underground
	// 9a. Illithid
	{
		char_data ch = make_character(RACE_ILLITHID, 96587);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("plebian") != std::string::npos);
	}
	// 9b. Undead
	{
		char_data ch = make_character(RACE_VAMPIRE, 96587);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("anathema") != std::string::npos);
	}
	// 9c. Dragon
	{
		char_data ch = make_character(RACE_DRAGON, 96587);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("kettle") != std::string::npos);
	}

	// 10. Verify room == NOWHERE terminates safely
	{
		char_data ch = make_character(RACE_HUMAN, NOWHERE);
		char arg[] = "";
		last_output.clear();
		do_smoke(&ch, arg, 0);
		assert(last_output.find("kicked up by your movement") != std::string::npos);
	}

	std::printf("All underground and surface smoking weather tests passed successfully.\n");
	return 0;
}
