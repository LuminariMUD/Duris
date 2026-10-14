#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "core/json_utils.h"
#include "net/gmcp.h"
#include "ships/ships.h"
#include "world/db.h"
#include "magic/spells.h"
#include "guild/assocs.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

static room_data rooms[3];
P_room world = rooms;
static zone_data zones[1];
zone_data *zone_table = zones;
const int top_of_world = 3;
P_desc descriptor_list;
ContactData contacts[MAXSHIPS];
const ShipTypeData ship_type_data[MAXSHIPCLASS] = {};
const ShipCrewData ship_crew_data[MAXCREWS] = {};
const ShipChiefData ship_chief_data[MAXCHIEFS] = {};
const WeaponData weapon_data[MAXWEAPON] = {};
const EquipmentData equipment_data[MAXEQUIPMENT] = {};
static ShipData vessel, enemy;
static std::map<P_desc, std::vector<std::string>> wire;
int top_of_zone_table = 0;
index_data *mob_index, *obj_index;
Skill skills[MAX_SKILLS];
char *get_class_string(P_char, char *buf)
{
	std::strcpy(buf, "Warrior");
	return buf;
}
int get_vis_mode(P_char, int)
{
	return 0;
}
bool ac_can_see(P_char, P_char, bool)
{
	return true;
}
bool ac_can_see_obj(P_char, P_obj, int)
{
	return true;
}
static int websockets;
const class_names class_names_table[64] = { { "Warrior", "Warrior", "War", 'W' } };
extern const race_names race_names_table[LAST_RACE + 1] = { { "Human", "Human", "Human", "Hum" } };
long new_exp_table[100] = {};
static int group_limit = 13;
int get_property(const char *, int)
{
	return group_limit;
}
int GET_PRIME_CLASS(P_char, unsigned int)
{
	return 0;
}
int GET_SECONDARY_CLASS(P_char, unsigned int)
{
	return 0;
}
void update_groupies(P_char ch, bool)
{
	if (ch->desc)
		ch->desc->last_group_update = 1;
}
int flag2idx(int flags)
{
	(void)flags;
	return 0;
}

static int contact_count = 1;
int is_desc_valid(P_desc d)
{
	return d != nullptr;
}
int write_to_descriptor_binary(P_desc d, const unsigned char *bytes, size_t size)
{
	wire[d].emplace_back(reinterpret_cast<const char *>(bytes), size);
	return 0;
}
int websocket_send_json(P_desc, const char *, const char *)
{
	++websockets;
	return 0;
}
P_ship get_ship_from_char(P_char ch)
{
	return ch->in_room == 1 ? &vessel : nullptr;
}
int real_room(const int room)
{
	return room;
}
int getcontacts(P_ship, bool)
{
	return contact_count;
}
string strip_ansi(const char *text)
{
	return text ? text : "";
}
int ShipData::get_maxspeed(P_char ch) const
{
	return ch ? ch->points.mana : 20;
}
int ShipCrew::get_contact_range_mod() const
{
	return 0;
}
int ShipCrew::sail_mod()
{
	return 0;
}
int ShipCrew::guns_mod()
{
	return 0;
}
int ShipCrew::rpar_mod()
{
	return 0;
}
int num_people_in_ship(P_ship)
{
	return 2;
}
const char *get_ship_status(P_ship ship)
{
	return SHIP_DOCKED(ship) ? "docked" : "sailing";
}
const char *cargo_type_name(int)
{
	return "silk";
}

// Isolate world/mechanics dependencies while exercising production serializers.

int sql_world_quest_can_do_another(P_char)
{
	return 2;
}
static char_data quest_mob;
P_char read_mobile(int, int)
{
	return &quest_mob;
}
int real_mobile(const int)
{
	return 0;
}
int real_zone0(const int)
{
	return 0;
}
void extract_char(P_char) {}
time_info_data time_info;
const char *month_name[] = { "Moon" };
void gmcp_quest_status(P_char ch)
{
	char *json = json_build_quest_status(ch);
	gmcp_send(ch->desc, "Quest.Status", json);
	free(json);
}

#include "production.inc"

static std::string payload(P_desc d, const char *package)
{
	const std::string prefix = std::string("\xff\xfa\xc9", 3) + package + " ";
	for (auto i = wire[d].rbegin(); i != wire[d].rend(); ++i)
	{
		if (i->starts_with(prefix))
		{
			assert(i->ends_with(std::string("\xff\xf0", 2)));
			return i->substr(prefix.size(), i->size() - prefix.size() - 2);
		}
	}
	assert(false && "missing GMCP package");
	return "";
}
static void emit(P_desc d, const char *package, const char *phase = "snapshot")
{
	printf("%s %s %s\n", phase, package, payload(d, package).c_str());
}
static void flush()
{
	gmcp_flush_dirty_ship_contacts();
	gmcp_flush_dirty_ship_info();
}
int main()
{
	static char_data a, b, victim;
	static pc_only_data apc, bpc;
	static descriptor_data ad, bd;
	a.only.pc = &apc;
	b.only.pc = &bpc;
	a.desc = &ad;
	b.desc = &bd;
	ad.character = &a;
	bd.character = &b;
	ad.connected = bd.connected = CON_PLAYING;
	ad.gmcp_enabled = bd.gmcp_enabled = 1;
	a.in_room = b.in_room = 1;
	a.points.mana = 18;
	b.points.mana = 23;
	descriptor_list = &ad;
	vessel.flags = LOADED;
	vessel.bridge = 1;
	vessel.location = 2;
	vessel.name = const_cast<char *>("Bronze Voyager");
	vessel.id = const_cast<char *>("AA");
	vessel.heading = 90;
	vessel.speed = 12;
	vessel.armor[0] = 80;
	vessel.maxarmor[0] = 100;
	vessel.internal[0] = 40;
	vessel.maxinternal[0] = 50;
	vessel.slot[0].type = SLOT_CARGO;
	vessel.slot[0].val0 = 3;
	rooms[2].zone = 0;
	zones[0].flags = ZONE_MAP;
	zones[0].mapx = 100;
	zones[0].mapy = 100;
	enemy.name = const_cast<char *>("Enemy vessel");
	enemy.id = const_cast<char *>("BB");
	enemy.race = EVILSHIP;
	enemy.heading = 50;
	enemy.speed = 8;
	enemy.target = &vessel;
	vessel.target = &enemy;
	contacts[0].ship = &enemy;
	contacts[0].range = 5;
	contacts[0].bearing = 70;
	std::strcpy(contacts[0].arc, "port");
	flush();
	assert(wire[&ad].size() == 2);
	emit(&ad, "Ship.Info");
	emit(&ad, "Ship.Contacts");
	auto json = payload(&ad, "Ship.Contacts");
	assert(json.find("\"worldX\"") == std::string::npos);
	assert(json.find("\"you_targeting\":true") != std::string::npos);
	assert(json.find("\"heading\":90") != std::string::npos);
	wire.clear();
	flush();
	assert(wire.empty());
	ad.next = &bd;
	flush();
	assert(wire[&ad].empty() && wire[&bd].size() == 2); // stationary newcomer
	assert(payload(&bd, "Ship.Info").find("\"maxSpeed\":23") != std::string::npos);
	wire.clear();
	b.points.mana = 24;
	flush();
	assert(wire[&ad].empty() && wire[&bd].size() == 1); // personalized change
	wire.clear();
	vessel.flags |= DOCKED;
	flush();
	assert(payload(&ad, "Ship.Contacts").find("\"contacts\":[]") != std::string::npos);
	wire.clear();
	a.in_room = 0;
	flush();
	assert(payload(&ad, "Ship.Info") == "{}");
	assert(payload(&ad, "Ship.Contacts") == "{\"contacts\":[]}");
	wire.clear();
	a.in_room = 1;
	flush();
	assert(wire[&ad].size() == 2);
	wire.clear();
	a.specials.act3 |= PLR3_NOGMCP;
	vessel.speed = 4;
	flush();
	assert(wire[&ad].empty());
	a.specials.act3 &= ~PLR3_NOGMCP;
	wire.clear();
	ad.gmcp_enabled = 0;
	gmcp_handle_negotiation(&ad, TELNET_DO);
	for (const char *pkg : { "Char.Status", "Char.Vitals", "Char.Affects", "Group.Status",
				 "Room.Info", "Quest.Status", "Combat.Update" })
		payload(&ad, pkg);
	wire.clear();
	gmcp_handle_negotiation(&ad, TELNET_DO);
	assert(wire.empty());
	gmcp_send_room_map(&a, "&+G@&n\n");
	emit(&ad, "Room.Map");
	assert(websockets == 0); // Telnet framing retained
	a.player.name = const_cast<char *>("Tester");
	victim.player.name = const_cast<char *>("wolf");
	victim.points.hit = 40;
	victim.points.max_hit = 100;
	applied_damage_notice(&a, &victim, 8);
	emit(&ad, "Combat.Update");
	gmcp_combat_end(&a);
	assert(payload(&ad, "Combat.Update") == "{\"target\":null}");
	zones[0].flags = 0;
	zones[0].number = 228;
	zones[0].name = const_cast<char *>("Test Zone");
	rooms[1].number = 22800;
	rooms[1].name = const_cast<char *>("Gate of \"Dawn\"");
	gmcp_room_info(&a);
	emit(&ad, "Room.Info");
	cJSON *room_json = cJSON_Parse(payload(&ad, "Room.Info").c_str());
	assert(std::string(cJSON_GetObjectItem(room_json, "name")->valuestring) == rooms[1].name);
	cJSON_Delete(room_json);
	gmcp_char_status(&a);
	emit(&ad, "Char.Status");
	affected_type affect{};
	affect.type = 1;
	affect.duration = 3;
	a.affected = &affect;
	skills[1].name = "bless";
	gmcp_char_affects(&a);
	emit(&ad, "Char.Affects");
	quest_mob.player.short_descr = const_cast<char *>("bronze guardian");
	apc.quest_active = 1;
	apc.quest_type = FIND_AND_KILL;
	apc.quest_kill_original = 5;
	apc.quest_kill_how_many = 2;
	gmcp_quest_status(&a);
	emit(&ad, "Quest.Status");
	gmcp_comm_channel_ex(&a, "nchat", "Tester", "hello", "good");
	emit(&ad, "Comm.Channel");
	group_list member_b = { &b, nullptr };
	group_list member_a = { &a, &member_b };
	a.group = b.group = &member_a;
	b.player.name = const_cast<char *>("Ally");
	gmcp_send_group_status(&a);
	emit(&ad, "Group.Status");
	assert(payload(&ad, "Group.Status").find("\"maxSize\":13") != std::string::npos);
	a.points.hit = 70;
	a.points.max_hit = 100;
	a.points.vitality = 80;
	a.points.max_vitality = 100;
	gmcp_char_vitals(&a);
	emit(&ad, "Char.Vitals");
	group_limit = 9;
	a.player.racewar = RACEWAR_GOOD;
	gmcp_send_group_status(&a);
	assert(payload(&ad, "Group.Status").find("\"maxSize\":9") != std::string::npos);
	a.group = nullptr;
	gmcp_send_group_status(&a);
	emit(&ad, "Group.Status", "clear");
	a.affected = nullptr;
	gmcp_char_affects(&a);
	emit(&ad, "Char.Affects", "clear");
	apc.quest_active = 0;
	gmcp_quest_status(&a);
	emit(&ad, "Quest.Status", "clear");
	gmcp_combat_end(&a);
	emit(&ad, "Combat.Update", "clear");
	flush();
	a.in_room = 0;
	flush();
	emit(&ad, "Ship.Info", "clear");
	emit(&ad, "Ship.Contacts", "clear");
	assert(payload(&ad, "Group.Status").find("\"members\":[]") != std::string::npos);
	ad.gmcp_enabled = 0;
	wire.clear();
	gmcp_send_room_map(&a, "hidden");
	assert(wire.empty());
}
