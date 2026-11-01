#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "core/json_utils.h"
#include "net/gmcp.h"
#include "net/websocket.h"
#include "net/ws_auth.h"
#include "persistence/latency_trace.h"
#include <algorithm>
#include <cctype>
#include "ships/ships.h"
#include "world/db.h"
#include "magic/spells.h"
#include "combat/damage.h"
#include "guild/assocs.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include <unordered_map>
#include <cmath>

static room_data rooms[3];
P_room world = rooms;
// Selector rules have their own native round-trip harness. This fixture checks
// that Room.Info carries the result through its normal serializer/framing path.
bool get_char_room_target(P_char, P_char target, char *out, size_t capacity)
{
	return snprintf(out, capacity, "1.%s", GET_NAME(target)) < static_cast<int>(capacity);
}
static zone_data zones[1];
zone_data *zone_table = zones;
const int top_of_world = 3;
P_desc descriptor_list;
ContactData contacts[MAXSHIPS];
const ShipTypeData ship_type_data[MAXSHIPCLASS] = { []
						    {
							    ShipTypeData t{};
							    t._hull = 330;
							    t._mxweight = 165;
							    t._mxsail = 130;
							    t._mxcargo = 70;
							    return t;
						    }() };
const ShipCrewData ship_crew_data[MAXCREWS] = {};
const ShipChiefData ship_chief_data[MAXCHIEFS] = {};
const WeaponData weapon_data[MAXWEAPON] = { []
					    {
						    WeaponData t{};
						    t.name = "Long cannon";
						    t.weight = 4;
						    t.ammo = 12;
						    return t;
					    }() };
const EquipmentData equipment_data[MAXEQUIPMENT] = { []
						     {
							     EquipmentData t{};
							     t.name = "Test equipment";
							     t.weight = 3;
							     return t;
						     }() };
static ShipData vessel, enemy, second_vessel;
static bool second_ship_enabled;
static std::map<P_desc, std::vector<std::string>> wire;
static std::map<P_desc, std::map<std::string, std::string>> ws_wire;
int top_of_zone_table = 0;
static index_data quest_profile{};
index_data *mob_index = &quest_profile, *obj_index;
Skill skills[MAX_SKILLS];
static int affect_remaining_pulses = 2640;
int ne_event_time(P_nevent)
{
	return affect_remaining_pulses;
}
void event_short_affect(P_char, P_char, P_obj, void *) {}
char *get_class_string(P_char, char *buf)
{
	std::strcpy(buf, "Warrior");
	return buf;
}
int get_vis_mode(P_char, int)
{
	return 0;
}
static P_char concealed;
static int visibility_checks;
bool ac_can_see(P_char, P_char subject, bool)
{
	++visibility_checks;
	return subject != concealed;
}
char *PERS(P_char subject, P_char, int, bool)
{
	return GET_NAME(subject);
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

static uint64_t control_clock_us = 10000000;
uint64_t latency_trace_monotonic_us()
{
	return control_clock_us;
}
const char *input_command_label(const char *)
{
	return "unknown";
}
static int json_allocation_budget = -1;
static int json_allocation_calls;
static void *bounded_json_allocate(size_t size)
{
	++json_allocation_calls;
	if (json_allocation_budget == 0)
		return nullptr;
	if (json_allocation_budget > 0)
		--json_allocation_budget;
	return std::malloc(size);
}
static bool queue_reject;
static unsigned creation_menus;
bool account_commit_character_admission(P_desc d, P_char ch, bool, account_racewar_admission *)
{
	assert(d->character == ch && d->chargen_phase == CHARGEN_READY);
	return false;
}
void account_format_racewar_denial(const account_racewar_admission *, char *out, size_t size)
{
	snprintf(out, size, "Admission rejected");
}
void ws_send_system(P_desc, const char *, const char *) {}
void item_creation_grant_cancel_batch_before_entry(P_char) {}
void free_char(P_char ch)
{
	assert(!ch->desc);
}
void ws_send_auth_success(P_desc d, const char *)
{
	assert(STATE(d) == CON_ACCT_SELECT_CHAR && !d->character);
	++creation_menus;
}
static std::map<P_desc, std::vector<std::string>> packages;
static std::map<P_desc, std::vector<std::pair<std::string, std::string>>> deliveries;

static int contact_count = 1;
static int contact_scans;
static unsigned descriptor_validations;
int is_desc_valid(P_desc d)
{
	++descriptor_validations;
	return d != nullptr;
}
int write_to_descriptor_binary(P_desc d, const unsigned char *bytes, size_t size)
{
	if (queue_reject)
		return -1;
	wire[d].emplace_back(reinterpret_cast<const char *>(bytes), size);
	if (size >= 5 && bytes[0] == TELNET_IAC && bytes[1] == TELNET_SB && bytes[2] == TELOPT_GMCP)
	{
		const std::string frame(reinterpret_cast<const char *>(bytes + 3), size - 3);
		const size_t split = frame.find(' ');
		packages[d].push_back(frame.substr(0, split));
		deliveries[d].emplace_back(frame.substr(0, split),
					   frame.substr(split + 1, frame.size() - split - 3));
	}
	return 0;
}
int websocket_send_json(P_desc d, const char *package, const char *json)
{
	if (queue_reject)
		return -1;
	++websockets;
	packages[d].push_back(package);
	deliveries[d].emplace_back(package, json);
	ws_wire[d][package] = json;
	return 0;
}
P_ship get_ship_from_char(P_char)
{
	assert(false && "periodic GMCP must not scan all ship rooms per observer");
	return nullptr;
}
ShipObjHash::ShipObjHash()
	: table{}
	, sz(0)
{
}
ShipObjHash shipObjHash;
static int ship_visits;
bool ShipObjHash::get_first(visitor &vs)
{
	vs.curr = &vessel;
	++ship_visits;
	return true;
}
bool ShipObjHash::get_next(visitor &vs)
{
	if (vs.curr == &vessel && second_ship_enabled)
	{
		vs.curr = &second_vessel;
		++ship_visits;
		return true;
	}
	return false;
}
static int queued_looks;
void write_to_q(const char *text, struct txt_q *, const int)
{
	assert(std::string(text) == "look");
	++queued_looks;
}
int real_room(const int room)
{
	return room;
}
int getcontacts(P_ship ship, bool)
{
	++contact_scans;
	return ship == &second_vessel ? 0 : contact_count;
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
const char *contra_type_name(int)
{
	return "forbidden relics";
}

// Isolate world/mechanics dependencies while exercising production serializers.

static world_quest_target_status quest_availability = world_quest_target_status::valid;
static int quest_checks = 0;
world_quest_target_status world_quest_refresh(P_char, int)
{
	++quest_checks;
	return quest_availability;
}

int sql_world_quest_can_do_another(P_char)
{
	return 2;
}
static int quest_loads;
P_char read_mobile(int, int)
{
	++quest_loads;
	std::abort();
}
int real_mobile(const int)
{
	return 0;
}
int real_zone(const int)
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
void char_from_room(P_char)
{
	assert(false && "GMCP map refresh must not run movement hooks");
}
bool char_to_room(P_char, int, int)
{
	assert(false && "GMCP map refresh must not run movement hooks");
	return false;
}
void display_map_room(P_char ch, int room, int radius, int mode, int package)
{
	assert(ch->in_room == room && room == 2);
	assert(radius == 20 && mode == 999 && package == 1);
	gmcp_send_quest_map(ch, "quest map");
}

static void replace_hour_flower(int, int, int)
{
	assert(false && "midnight rollover must not replace hour flowers");
}
static int clock_shop_saves;
bool save_dirty_shopkeepers(bool)
{
	++clock_shop_saves;
	return true;
}

static damage_messages captured_damage;
int raw_damage(P_char, P_char, double, uint, damage_messages *messages, int *)
{
	captured_damage = *messages;
	return DAM_NONEDEAD;
}
#include "production.inc"

static std::string payload(P_desc d, const char *package)
{
	if (d->websocket)
	{
		assert(ws_wire[d].contains(package) && "missing WebSocket GMCP package");
		return ws_wire[d][package];
	}
	const std::string prefix = std::string("\xff\xfa\xc9", 3) + package + " ";
	for (auto i = wire[d].rbegin(); i != wire[d].rend(); ++i)
	{
		if (i->starts_with(prefix))
		{
			assert(i->ends_with(std::string("\xff\xf0", 2)));
			return i->substr(prefix.size(), i->size() - prefix.size() - 2);
		}
	}
	fprintf(stderr, "missing GMCP package: %s\n", package);
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

static void control_time_contract(P_char actor)
{
	const P_desc saved_descriptor = actor->desc;
	const P_desc saved_list = descriptor_list;
	for (bool websocket : { false, true })
	{
		descriptor_data d{};
		d.websocket = websocket;
		d.connected = CON_ACCT_SELECT_CHAR;
		descriptor_list = &d;
		wire.erase(&d);
		ws_wire.erase(&d);
		packages.erase(&d);
		const auto send = [&](const std::string &request, bool advance = true)
		{
			if (advance)
				control_clock_us += 1000000;
			gmcp_handle_input(&d, request.data(), request.size());
		};
		const auto count = [&]() { return packages[&d].size(); };
		const auto check_time = [&](int hour, const char *phase)
		{
			cJSON *root = cJSON_Parse(payload(&d, "Duris.Time").c_str());
			assert(root);
			assert(cJSON_GetObjectItem(root, "hour")->valueint == hour);
			assert(std::string(cJSON_GetStringValue(
				       cJSON_GetObjectItem(root, "phase"))) == phase);
			assert(cJSON_IsString(cJSON_GetObjectItem(root, "revision")));
			assert(std::strlen(cJSON_GetStringValue(
				       cJSON_GetObjectItem(root, "process"))) == 32);
			cJSON_Delete(root);
		};
		// Transport negotiation and supported decoding are not a panel subscription.
		send("Core.Supports.Set [\"Duris.Capabilities 1\",\"Duris.Time 1\"]");
		assert(!d.gmcp_supports);
		gmcp_handle_negotiation(&d, TELNET_DO);
		send("Core.Supports.Set [\"Duris.Capabilities 1\",\"Duris.Time 1\"]");
		gmcp_flush_initial_states();
		assert(count() == 1 && packages[&d].back() == "Duris.Capabilities");
		assert(payload(&d, "Duris.Capabilities").find("\"active\":[]") !=
		       std::string::npos);
		send("Duris.Subscribe [\"Duris.Time 1\"]");
		gmcp_flush_initial_states();
		assert(count() == 2); // no gameplay time stream before character entry
		d.character = actor;
		d.connected = CON_PLAYING;
		actor->desc = &d;
		time_info.hour = 9;
		gmcp_send_initial_state(actor);
		assert(packages[&d][2] == "Duris.Capabilities");
		assert(packages[&d].back() == "Duris.Time");
		check_time(9, "day");
		d.character = nullptr;
		d.connected = CON_ACCT_SELECT_CHAR;
		const auto departed = count();
		gmcp_flush_initial_states();
		assert(count() == departed + 1 && !d.gmcp_active_streams);
		assert(payload(&d, "Duris.Capabilities").find("\"active\":[]") !=
		       std::string::npos);
		d.character = actor;
		d.connected = CON_PLAYING;
		gmcp_flush_initial_states();
		assert(count() == departed + 4 && d.gmcp_active_streams == GMCP_SUPPORT_TIME);
		check_time(9, "day");
		const size_t initial_count = count();
		gmcp_flush_initial_states();
		assert(count() == initial_count); // idle is silent
		for (const auto &[hour, phase] :
		     std::vector<std::pair<int, const char *>>{ { 0, "night" },
								{ 3, "night" },
								{ 4, "dawn" },
								{ 8, "dawn" },
								{ 9, "day" },
								{ 15, "day" },
								{ 16, "dusk" },
								{ 18, "dusk" },
								{ 19, "night" },
								{ 23, "night" } })
		{
			const size_t before = count();
			time_info.hour = hour;
			gmcp_time_changed();
			assert(count() == before); // mutation only invalidates the shared cache
			gmcp_flush_initial_states();
			assert(count() == before + 1);
			check_time(hour, phase);
			gmcp_flush_initial_states();
			assert(count() == before + 1);
		}
		time_info.hour = 23;
		time_info.day = 34;
		time_info.month = 16;
		const int year = time_info.year;
		const int saves = clock_shop_saves;
		event_another_hour(nullptr, nullptr, nullptr, nullptr);
		assert(time_info.hour == 0 && time_info.day == 0 && time_info.month == 0 &&
		       time_info.year == year + 1);
		assert(clock_shop_saves == saves + 1);
		gmcp_flush_initial_states();
		check_time(0, "night");
		const auto revision = d.gmcp_time_revision;
		actor->specials.act3 |= PLR3_NOGMCP;
		gmcp_preferences_changed(&d);
		gmcp_flush_initial_states();
		assert(payload(&d, "Duris.Capabilities").find("\"enabled\":false") !=
		       std::string::npos);
		assert(payload(&d, "Duris.Capabilities").find("\"active\":[]") !=
		       std::string::npos);
		time_info.hour = 10;
		gmcp_time_changed();
		const size_t disabled = count();
		gmcp_flush_initial_states();
		assert(count() == disabled && gmcp_clock_json[0] == '\0');
		actor->specials.act3 &= ~PLR3_NOGMCP;
		gmcp_preferences_changed(&d);
		gmcp_flush_initial_states();
		assert(count() == disabled + 2 && d.gmcp_time_revision > revision);
		assert(packages[&d][disabled] == "Duris.Capabilities");
		check_time(10, "day");
		send("Core.Supports.Remove [\"Duris.Time 1\"]");
		gmcp_flush_initial_states();
		assert(!d.gmcp_interests && !gmcp_time_active(&d));
		send("Core.Supports.Add [\"Duris.Time 2\",\"Char.Items 1\",\"unknown 1\"]");
		assert(!(d.gmcp_supports & GMCP_SUPPORT_TIME));
		send("Core.Supports.Add [\"Duris.Time 1\"]");
		assert(!d.gmcp_interests); // re-advertising support does not re-open a panel
		gmcp_clock_json[0] = '\0';
		gmcp_flush_initial_states();
		assert(gmcp_clock_json[0] == '\0');
		const auto supports = d.gmcp_supports;
		for (const auto &invalid : std::vector<std::string>{
			     "Core.Supports.Set {}", "Core.Supports.Set [true]",
			     "Core.Supports.Set [null]",
			     "Core.Supports.Set [\"Duris.Time 1\"] trailing",
			     "Core.Supports.Set [\"Duris.Time 1\\u0000hidden\"]",
			     "Core.Supports.Set [\"" + std::string(97, 'x') + "\"]",
			     "Core.Supports.Set [" + std::string(8192, ' ') + "]" })
		{
			send(invalid);
			assert(d.gmcp_supports == supports && !d.gmcp_interests);
		}
		std::string oversized = "Core.Supports.Set [\"Duris.Time 1\"";
		for (int index = 0; index < 64; ++index)
			oversized += ",\"Duris.Time 1\"";
		oversized += "]";
		send(oversized);
		assert(d.gmcp_supports == supports);
		send(std::string("Core.Supports.Set []") + '\0' + "ignored");
		assert(d.gmcp_supports == supports);
		// Independent families: a subscription flood cannot refill Supports or vice versa.
		d.gmcp_request_refill_ms[0] = 0;
		send("Core.Supports.Add []", false);
		send("Core.Supports.Add []", false);
		send("Core.Supports.Remove [\"Duris.Time 1\"]", false);
		assert(d.gmcp_supports == supports);
		control_clock_us += 999000;
		send("Core.Supports.Remove [\"Duris.Time 1\"]", false);
		assert(d.gmcp_supports == supports);
		control_clock_us += 1000;
		send("Core.Supports.Remove [\"Duris.Time 1\"]", false);
		assert(!(d.gmcp_supports & GMCP_SUPPORT_TIME));
		send("Core.Supports.Add [\"Duris.Time 1\"]");
		send("Duris.Subscribe [\"Duris.Time 1\"]");
		queue_reject = true;
		const size_t failed = count();
		gmcp_flush_initial_states();
		assert(d.gmcp_control_pending && d.gmcp_time_revision == 0 && count() == failed);
		queue_reject = false;
		gmcp_flush_initial_states();
		assert(!d.gmcp_control_pending && d.gmcp_time_revision && count() == failed + 2);
		gmcp_handle_negotiation(&d, TELNET_DONT);
		const size_t stopped = count();
		gmcp_flush_initial_states();
		assert(count() == stopped);
		d.connected = CON_ACCT_SELECT_CHAR;
		gmcp_handle_negotiation(&d, TELNET_DO);
		d.connected = CON_PLAYING;
		gmcp_flush_initial_states();
		assert(count() == stopped + 2); // re-enable resynchronizes the retained interest
		if (!websocket)
		{
			emit(&d, "Duris.Capabilities", "control");
			emit(&d, "Duris.Time", "time");
		}
		d.gmcp_request_refill_ms[0] = 0;
		send("Core.Supports.Set []", false);
		send("Core.Supports.Set []", false);
		assert(d.gmcp_control_pending);
		queue_reject = true;
		gmcp_flush_initial_states();
		assert(d.gmcp_control_pending);
		control_clock_us += 1000000;
		send("Core.Supports.Remove []", false);
		assert(d.gmcp_control_pending);
		queue_reject = false;
		gmcp_flush_initial_states();
		assert(!d.gmcp_supports && !d.gmcp_interests);
		assert(payload(&d, "Duris.Capabilities").find("\"active\":[]") !=
		       std::string::npos);
		const auto removed = count();
		gmcp_flush_initial_states();
		assert(count() == removed);
		descriptor_data fresh{};
		assert(!fresh.gmcp_supports && !fresh.gmcp_interests && !fresh.gmcp_time_revision);
	}
	actor->desc = saved_descriptor;
	descriptor_list = saved_list;
}

static void session_contract(P_char actor, bool websocket)
{
	const auto saved_list = descriptor_list;
	const auto saved_desc = actor->desc;
	const auto saved_id = actor->runtime_id;
	actor->runtime_id = 100;
	descriptor_data d{};
	d.websocket = websocket;
	d.connected = CON_ACCT_SELECT_CHAR;
	d.gmcp_enabled = 1;
	descriptor_list = &d;
	wire.erase(&d);
	packages.erase(&d);
	ws_wire.erase(&d);
	deliveries.erase(&d);
	const auto send = [&](const std::string &request)
	{
		control_clock_us += 1000000;
		gmcp_handle_input(&d, request.data(), request.size());
	};
	const auto session = [&]() { return cJSON_Parse(payload(&d, "Duris.Session").c_str()); };
	const auto check = [&](const char *state, const char *generation, const char *name,
			       const char *body = "1")
	{
		cJSON *root = session();
		assert(root);
		assert(std::string(cJSON_GetStringValue(cJSON_GetObjectItem(root, "state"))) ==
		       state);
		assert(std::string(cJSON_GetStringValue(cJSON_GetObjectItem(root, "generation"))) ==
		       generation);
		assert(std::strlen(cJSON_GetStringValue(cJSON_GetObjectItem(root, "context"))) ==
		       32);
		assert(std::strlen(cJSON_GetStringValue(cJSON_GetObjectItem(root, "process"))) ==
		       32);
		const cJSON *character = cJSON_GetObjectItem(root, "character");
		if (name)
		{
			assert(std::string(cJSON_GetStringValue(
				       cJSON_GetObjectItem(character, "name"))) == name);
			assert(std::string(cJSON_GetStringValue(
				       cJSON_GetObjectItem(character, "bodyRevision"))) == body);
		}
		else
			assert(cJSON_IsNull(character));
		cJSON_Delete(root);
	};
	send("Core.Supports.Set [\"Duris.Capabilities 1\",\"Duris.Time 1\",\"Duris.Session 1\"]");
	send("Duris.Subscribe [\"Duris.Time 1\"]");
	gmcp_flush_initial_states();
	check("account", "0", nullptr);
	const std::string context = d.gmcp_session_context;
	if (!websocket)
		emit(&d, "Duris.Session", "session-account");
	d.connected = CON_ACCT_NEW_CHAR;
	gmcp_session_update(&d);
	check("chargen", "0", nullptr);
	d.connected = CON_ACCT_SELECT_CHAR;
	gmcp_session_update(&d);
	check("account", "0", nullptr);
	if (websocket)
	{
		acct_entry account{};
		d.account = &account;
		d.chargen_phase = CHARGEN_READY;
		d.character = actor;
		actor->desc = &d;
		gmcp_session_update(&d);
		check("chargen", "0", nullptr);
		const auto menus = creation_menus;
		rejected_creation(&d, actor);
		assert(creation_menus == menus + 1 && d.chargen_phase == CHARGEN_UNSTARTED);
		gmcp_session_update(&d);
		check("account", "0", nullptr);
		d.account = nullptr;
	}
	d.character = actor;
	actor->desc = &d;
	d.connected = CON_PLAYING;
	const auto begin = packages[&d].size();
	gmcp_send_initial_state(actor);
	assert(packages[&d][begin] == "Duris.Capabilities");
	assert(packages[&d][begin + 1] == "Duris.Session");
	check("playing", "1", "Tester");
	if (!websocket)
		emit(&d, "Duris.Session", "session-enter");
	gmcp_send_initial_state(actor);
	gmcp_handle_negotiation(&d, TELNET_DO);
	send("Core.Supports.Add [\"Duris.Session 1\"]");
	gmcp_flush_initial_states();
	assert(d.gmcp_session_generation == 1 && context == d.gmcp_session_context);
	check("playing", "1", "Tester");
	cJSON_Hooks hooks{};
	hooks.malloc_fn = bounded_json_allocate;
	hooks.free_fn = std::free;
	cJSON_InitHooks(&hooks);
	for (int budget = 0; budget < 40; ++budget)
	{
		const auto before = packages[&d].size();
		d.gmcp_session_pending = true;
		json_allocation_budget = budget;
		gmcp_session_update(&d);
		const bool waiting = d.gmcp_session_pending;
		assert(packages[&d].size() == before + (waiting ? 0 : 1));
		json_allocation_budget = -1;
		gmcp_session_update(&d);
		assert(!d.gmcp_session_pending && packages[&d].size() == before + 1);
		check("playing", "1", "Tester");
	}
	cJSON_InitHooks(nullptr);
	const auto validations = descriptor_validations;
	gmcp_char_vitals(actor);
	assert(descriptor_validations ==
	       validations + 1); // no extra population scan on a stable gameplay packet
	actor->specials.act3 |= PLR3_NOGMCP;
	gmcp_preferences_changed(&d);
	gmcp_flush_initial_states();
	check("playing", "1", "Tester"); // control remains available while gameplay is disabled
	actor->specials.act3 &= ~PLR3_NOGMCP;
	gmcp_preferences_changed(&d);
	gmcp_flush_initial_states();
	char_data body{};
	npc_only_data body_npc{};
	body.only.npc = &body_npc;
	body.specials.act = ACT_ISNPC;
	body.runtime_id = 200;
	body.desc = &d;
	body.player.name = const_cast<char *>("borrowed body");
	body.in_room = actor->in_room;
	body.points.hit = 37;
	body.points.max_hit = 80;
	d.original = actor;
	d.character = &body;
	actor->desc = nullptr;
	const auto switched = packages[&d].size();
	gmcp_char_vitals(&body);
	assert(packages[&d][switched] == "Duris.Session");
	assert(packages[&d].back() == "Char.Vitals");
	check("playing", "1", "Tester", "2");
	assert(d.gmcp_session_generation == 1);
	const auto before_bootstrap = packages[&d].size();
	gmcp_flush_initial_states();
	assert(!d.gmcp_initial_state_pending);
	const auto &body_packets = packages[&d];
	for (const char *package : { "Char.Vitals", "Char.Affects", "Room.Info" })
		assert(std::find(body_packets.begin() + before_bootstrap, body_packets.end(),
				 package) != body_packets.end());
	check("playing", "1", "Tester", "2");
	d.character = actor;
	d.original = nullptr;
	actor->desc = &d;
	body.desc = nullptr;
	gmcp_char_vitals(actor);
	check("playing", "1", "Tester", "3");
	// Even a direct replacement must clear the preceding character before any new data.
	char_data other{};
	pc_only_data other_pc{};
	other.only.pc = &other_pc;
	other.player.name = const_cast<char *>("Second");
	other.runtime_id = 300;
	other.in_room = 1;
	other.desc = &d;
	d.character = &other;
	actor->desc = nullptr;
	queue_reject = true;
	const auto rejected = packages[&d].size();
	gmcp_char_vitals(&other);
	assert(packages[&d].size() == rejected && d.gmcp_session_pending &&
	       d.gmcp_initial_state_pending);
	queue_reject = false;
	gmcp_flush_initial_states();
	assert(d.gmcp_session_generation == 2 && !d.gmcp_session_pending);
	std::vector<std::string> transitions;
	for (size_t index = rejected; index < deliveries[&d].size(); ++index)
		if (deliveries[&d][index].first == "Duris.Session")
			transitions.push_back(deliveries[&d][index].second);
	assert(transitions.size() == 2 &&
	       transitions[0].find("\"character\":null") != std::string::npos);
	check("playing", "2", "Second");
	// Terminal invalidation is constructed while the body is still valid, then holds no pointer.
	d.connected = CON_DISPLAY_ACCT_MENU;
	gmcp_session_update(&d);
	check("account", "2", nullptr);
	if (!websocket)
		emit(&d, "Duris.Session", "session-clear");
	d.character = nullptr;
	other.desc = nullptr;
	gmcp_handle_negotiation(&d, TELNET_DONT);
	d.character = actor;
	actor->desc = &d;
	d.connected = CON_PLAYING;
	gmcp_send_initial_state(actor);
	assert(!d.gmcp_control_pending && !d.gmcp_initial_state_pending);
	gmcp_handle_negotiation(&d, TELNET_DO);
	gmcp_flush_initial_states();
	check("playing", "3", "Tester");
	assert(context == d.gmcp_session_context);
	if (!websocket)
	{
		// A recovered descriptor adopts the same entry but a new process marker.
		const auto generation = d.gmcp_session_generation;
		const auto body_revision = d.gmcp_session_body_revision;
		const std::string old_process = gmcp_session_process;
		descriptor_data restored{};
		restored.gmcp_enabled = 1;
		restored.gmcp_supports = d.gmcp_supports;
		restored.gmcp_interests = d.gmcp_interests;
		restored.gmcp_session_generation = generation;
		restored.gmcp_session_body_revision = body_revision;
		std::strcpy(restored.gmcp_session_context, d.gmcp_session_context);
		restored.connected = CON_PLAYING;
		restored.character = actor;
		actor->desc = &restored;
		descriptor_list = &restored;
		gmcp_session_process[0] = 0;
		gmcp_clock_revision = 0;
		gmcp_clock_hour = -1;
		gmcp_clock_json[0] = 0;
		gmcp_session_restored(&restored);
		gmcp_flush_initial_states();
		assert(restored.gmcp_session_generation == generation &&
		       restored.gmcp_session_resumed);
		assert(context == restored.gmcp_session_context);
		assert(old_process != gmcp_session_process);
		assert(payload(&restored, "Duris.Time").find(gmcp_session_process) !=
		       std::string::npos);
		assert(payload(&restored, "Duris.Session").find("\"resumed\":true") !=
		       std::string::npos);
		assert(payload(&restored, "Duris.Session").find("\"generation\":\"3\"") !=
		       std::string::npos);
		restored.gmcp_session_generation = 9007199254740993ULL;
		restored.gmcp_session_pending = true;
		gmcp_session_update(&restored);
		assert(payload(&restored, "Duris.Session")
			       .find("\"generation\":\"9007199254740993\"") != std::string::npos);
	}
	actor->desc = saved_desc;
	actor->runtime_id = saved_id;
	descriptor_list = saved_list;
}

static void combat_contract(bool websocket)
{
	P_desc saved_list = descriptor_list;
	char_data viewer{}, enemy{}, tank{}, replacement{};
	pc_only_data player{}, ally{}, other{};
	npc_only_data npc{};
	descriptor_data d{};
	viewer.only.pc = &player;
	tank.only.pc = &ally;
	replacement.only.pc = &other;
	enemy.only.npc = &npc;
	enemy.specials.act = ACT_ISNPC;
	viewer.runtime_id = 10;
	enemy.runtime_id = 11;
	tank.runtime_id = 12;
	replacement.runtime_id = 13;
	viewer.player.name = const_cast<char *>("Viewer");
	enemy.player.name = const_cast<char *>("wolf grey beast");
	tank.player.name = const_cast<char *>("Ally");
	replacement.player.name = const_cast<char *>("Rescuer");
	viewer.in_room = enemy.in_room = tank.in_room = replacement.in_room = 1;
	viewer.points.max_hit = enemy.points.max_hit = tank.points.max_hit =
		replacement.points.max_hit = 100;
	viewer.points.hit = 10;
	enemy.points.hit = 80;
	tank.points.hit = 5;
	replacement.points.hit = 60;
	SET_POS(&enemy, POS_STANDING);
	SET_POS(&tank, POS_KNEELING);
	viewer.specials.fighting = &enemy;
	enemy.specials.fighting = &tank;
	viewer.desc = &d;
	d.character = &viewer;
	d.connected = CON_PLAYING;
	d.gmcp_enabled = 1;
	d.websocket = websocket;
	descriptor_list = &d;
	const auto count = [&]
	{ return std::count(packages[&d].begin(), packages[&d].end(), "Combat.Update"); };
	const auto check =
		[&](const char *target_name, int target_hp, const char *tank_name, int tank_hp)
	{
		cJSON *json = cJSON_Parse(payload(&d, "Combat.Update").c_str());
		for (const auto &[key, name, hp] : { std::tuple{ "target", target_name, target_hp },
						     std::tuple{ "tank", tank_name, tank_hp } })
		{
			cJSON *subject = cJSON_GetObjectItem(json, key);
			if (!name)
				assert(cJSON_IsNull(subject));
			else
			{
				assert(cJSON_IsObject(subject));
				assert(std::string(cJSON_GetStringValue(
					       cJSON_GetObjectItem(subject, "name"))) == name);
				assert(cJSON_GetObjectItem(subject, "healthPercent")->valueint ==
				       hp);
			}
		}
		assert(cJSON_IsString(cJSON_GetObjectItem(json, "revision")));
		cJSON_Delete(json);
	};
	gmcp_flush_initial_states();
	check("wolf", 80, "Ally", 5);
	assert(payload(&d, "Combat.Update").find("kneeling") != std::string::npos);
	emit(&d, "Combat.Update", "combat-subjects");
	// raw_damage publishes before damage() establishes the first combat relationship.
	viewer.specials.fighting = enemy.specials.fighting = nullptr;
	applied_damage_notice(&viewer, &enemy, 8);
	check("wolf", 72, nullptr, 0);
	assert(payload(&d, "Combat.Update").find("\"damage\":8") != std::string::npos);
	gmcp_flush_combat(&d);
	check(nullptr, 0, nullptr, 0);
	// A lethal first hit can finish without ever establishing that relationship.
	enemy.points.hit = 10;
	applied_damage_notice(&viewer, &enemy, 111);
	check("wolf", 0, nullptr, 0);
	gmcp_flush_combat(&d);
	check(nullptr, 0, nullptr, 0);
	enemy.points.hit = 80;
	viewer.specials.fighting = &enemy;
	enemy.specials.fighting = &tank;
	gmcp_flush_combat(&d);
	cJSON_Hooks hooks{ bounded_json_allocate, std::free };
	cJSON_InitHooks(&hooks);
	const auto stable_count = count();
	const auto allocations = json_allocation_calls;
	for (int n = 0; n < 100; ++n)
		gmcp_flush_combat(&d);
	assert(count() == stable_count && json_allocation_calls == allocations);
	// No event hook: direct non-GMCP ally healing and posture still refresh.
	tank.points.hit = 75;
	SET_POS(&tank, POS_SITTING);
	gmcp_flush_combat(&d);
	check("wolf", 80, "Ally", 75);
	assert(payload(&d, "Combat.Update").find("sitting") != std::string::npos);
	// Multiple hits coalesce; self HP never becomes target or tank HP.
	enemy.points.hit = 25;
	enemy.points.hit = 1;
	viewer.points.hit = 95;
	const auto before_hits = count();
	gmcp_flush_combat(&d);
	assert(count() == before_hits + 1);
	check("wolf", 1, "Ally", 75);
	concealed = &tank;
	gmcp_flush_combat(&d);
	check("wolf", 1, "someone", 75);
	assert(payload(&d, "Combat.Update").find("Ally") == std::string::npos);
	concealed = nullptr;
	// Rescue changes the opponent's opponent without retargeting the viewer.
	enemy.specials.fighting = &replacement;
	gmcp_flush_combat(&d);
	check("wolf", 1, "Rescuer", 60);
	// Departure clears a tank, then an off-room primary clears both.
	replacement.in_room = 2;
	gmcp_flush_combat(&d);
	check("wolf", 1, nullptr, 0);
	enemy.in_room = 2;
	gmcp_flush_combat(&d);
	check(nullptr, 0, nullptr, 0);
	enemy.in_room = replacement.in_room = 1;
	enemy.specials.fighting = &viewer;
	gmcp_flush_combat(&d);
	check("wolf", 1, "Viewer", 95);
	enemy.points.hit = -5;
	gmcp_flush_combat(&d);
	check("wolf", 0, "Viewer", 95);
	assert(payload(&d, "Combat.Update").find("bleeding to death") != std::string::npos);
	enemy.points.hit = 200;
	gmcp_flush_combat(&d);
	check("wolf", 100, "Viewer", 95);
	const auto before_identity = count();
	++enemy.runtime_id;
	gmcp_flush_combat(&d);
	assert(count() == before_identity + 1); // same address/name/vitals, new live identity
	std::string long_name(600, 'x');
	enemy.player.name = long_name.data();
	gmcp_flush_combat(&d);
	assert(std::strlen(d.gmcp_combat_subjects[0].name) == 255);
	assert(payload(&d, "Combat.Update").size() < 4096);
	enemy.player.name = const_cast<char *>("wolf grey beast");
	gmcp_flush_combat(&d);
	// Cache advances only when a complete snapshot enters the FIFO.
	for (int budget = 0; budget < 30; ++budget)
	{
		d.gmcp_combat_state_sent = false;
		json_allocation_budget = budget;
		gmcp_flush_combat(&d);
		const auto before_retry = count();
		const bool pending = !d.gmcp_combat_state_sent;
		json_allocation_budget = -1;
		gmcp_flush_combat(&d);
		assert(count() == before_retry + (pending ? 1 : 0));
		check("wolf", 100, "Viewer", 95);
	}
	enemy.points.hit = 90;
	queue_reject = true;
	const auto before_retry = count();
	gmcp_flush_combat(&d);
	assert(count() == before_retry);
	queue_reject = false;
	gmcp_flush_combat(&d);
	check("wolf", 90, "Viewer", 95);
	// Disabled/pre-entry streams do not resolve names or allocate JSON.
	for (int mode = 0; mode < 3; ++mode)
	{
		d.gmcp_enabled = mode != 0;
		if (mode == 1)
			viewer.specials.act3 |= PLR3_NOGMCP;
		if (mode == 2)
			d.connected = CON_DISPLAY_ACCT_MENU;
		const auto before = json_allocation_calls;
		const auto visibility = visibility_checks;
		gmcp_flush_combat(&d);
		assert(json_allocation_calls == before && visibility_checks == visibility);
		viewer.specials.act3 &= ~PLR3_NOGMCP;
	}
	d.connected = CON_PLAYING;
	viewer.specials.fighting = nullptr;
	gmcp_combat_end(&viewer);
	check(nullptr, 0, nullptr, 0);
	char_data *extracted = new char_data{};
	extracted->only.npc = &npc;
	extracted->specials.act = ACT_ISNPC;
	extracted->runtime_id = 99;
	extracted->player.name = const_cast<char *>("pet companion");
	extracted->in_room = 1;
	extracted->points.hit = 1;
	extracted->points.max_hit = 100;
	viewer.specials.fighting = extracted;
	gmcp_flush_combat(&d);
	check("pet", 1, nullptr, 0);
	viewer.specials.fighting = nullptr;
	delete extracted;
	gmcp_flush_combat(&d); // prior view has no live pointer to the freed pet
	check(nullptr, 0, nullptr, 0);
	cJSON_InitHooks(nullptr);
	descriptor_list = saved_list;
}

static void combat_events_contract(bool websocket)
{
	P_desc saved_list = descriptor_list;
	char_data actor{}, primary{}, secondary{};
	pc_only_data actor_pc{}, primary_pc{}, secondary_pc{};
	actor.only.pc = &actor_pc;
	primary.only.pc = &primary_pc;
	secondary.only.pc = &secondary_pc;
	actor.runtime_id = 21;
	primary.runtime_id = 22;
	secondary.runtime_id = 23;
	actor.player.name = const_cast<char *>("Actor");
	primary.player.name = const_cast<char *>("Primary");
	secondary.player.name = const_cast<char *>("Secondary");
	actor.in_room = primary.in_room = secondary.in_room = 1;
	actor.points.hit = primary.points.hit = secondary.points.hit = 100;
	actor.points.max_hit = primary.points.max_hit = secondary.points.max_hit = 100;
	actor.specials.fighting = &primary;
	descriptor_data d{};
	const auto reset = [&]
	{
		d = descriptor_data{};
		d.websocket = websocket;
		d.character = &actor;
		d.connected = CON_PLAYING;
		d.gmcp_enabled = 1;
		d.gmcp_supports = GMCP_SUPPORT_CAPABILITIES | GMCP_SUPPORT_SESSION |
				  GMCP_SUPPORT_COMBAT;
		d.gmcp_interests = GMCP_SUPPORT_COMBAT;
		actor.desc = &d;
		descriptor_list = &d;
		gmcp_session_update(&d);
	};
	reset();
	d.gmcp_supports = GMCP_SUPPORT_CAPABILITIES;
	d.gmcp_interests = 0;
	const char supports[] = "Core.Supports.Add [\"Duris.Session 1\",\"Duris.Combat 1\"]";
	gmcp_handle_input(&d, supports, sizeof(supports) - 1);
	assert(d.gmcp_supports & GMCP_SUPPORT_COMBAT);
	assert(!d.gmcp_interests);
	const char subscribe[] = "Duris.Subscribe [\"Duris.Combat 1\"]";
	gmcp_handle_input(&d, subscribe, sizeof(subscribe) - 1);
	gmcp_flush_initial_states();
	assert(d.gmcp_interests == GMCP_SUPPORT_COMBAT);
	assert(payload(&d, "Duris.Capabilities").find("\"active\":[\"Duris.Combat\"]") !=
	       std::string::npos);
	const auto count = [&]
	{ return std::count(packages[&d].begin(), packages[&d].end(), "Duris.Combat"); };
	damage_messages hit{};
	hit.damage_kind = -1;
	hit.critical_known = hit.critical = true;
	capture_spell_delivery(&actor, &primary, 10, SPLDAM_FIRE, 0, &hit);
	assert(captured_damage.damage_kind == SPLDAM_FIRE && !captured_damage.critical_known);
	assert(hit.damage_kind == -1 && hit.critical_known && hit.critical);
	capture_physical_delivery(&actor, &primary, 10, 0, &hit);
	assert(captured_damage.damage_kind == -1 && captured_damage.critical_known &&
	       captured_damage.critical);
	const auto before = packages[&d].size();
	applied_damage_notice(&actor, &secondary, 17, &hit);
	assert(actor.specials.fighting == &primary && secondary.points.hit == 83);
	assert(packages[&d].size() == before + 1 && packages[&d].back() == "Duris.Combat");
	cJSON *json = cJSON_Parse(payload(&d, "Duris.Combat").c_str());
	assert(cJSON_GetObjectItem(json, "damage")->valueint == 17);
	assert(cJSON_IsFalse(cJSON_GetObjectItem(json, "primary")));
	assert(cJSON_IsTrue(cJSON_GetObjectItem(json, "critical")));
	assert(std::string(cJSON_GetStringValue(cJSON_GetObjectItem(json, "damageType"))) ==
	       "physical");
	assert(std::string(cJSON_GetStringValue(cJSON_GetObjectItem(json, "target"))) ==
	       "Secondary");
	assert(std::string(cJSON_GetStringValue(cJSON_GetObjectItem(json, "sequence"))) == "1");
	assert(std::string(cJSON_GetStringValue(cJSON_GetObjectItem(json, "generation"))) == "1");
	assert(std::strlen(cJSON_GetStringValue(cJSON_GetObjectItem(json, "context"))) == 32);
	cJSON_Delete(json);
	emit(&d, "Duris.Combat", "damage-secondary");
	// Execute the authoritative no-kill/death caps before measuring the applied delta.
	secondary.points.hit = 10;
	applied_damage_notice(&actor, &secondary, 100, &hit, RAWDAM_NOKILL);
	assert(secondary.points.hit == 1);
	json = cJSON_Parse(payload(&d, "Duris.Combat").c_str());
	assert(cJSON_GetObjectItem(json, "damage")->valueint == 9);
	cJSON_Delete(json);
	secondary.points.hit = 10;
	applied_damage_notice(&actor, &secondary, 1000, &hit);
	assert(secondary.points.hit == -11);
	json = cJSON_Parse(payload(&d, "Duris.Combat").c_str());
	assert(cJSON_GetObjectItem(json, "damage")->valueint == 21);
	cJSON_Delete(json);
	secondary.points.hit = 100;
	// Production HP compound assignment removes two whole HP for a 1.9 input.
	applied_damage_notice(&actor, &secondary, 1.9);
	json = cJSON_Parse(payload(&d, "Duris.Combat").c_str());
	assert(cJSON_GetObjectItem(json, "damage")->valueint == 2);
	assert(cJSON_IsNull(cJSON_GetObjectItem(json, "critical")));
	assert(std::string(cJSON_GetStringValue(cJSON_GetObjectItem(json, "damageType"))) ==
	       "unknown");
	cJSON_Delete(json);
	concealed = &secondary;
	gmcp_combat_damage(&actor, &secondary, 3, nullptr);
	assert(payload(&d, "Duris.Combat").find("someone") != std::string::npos);
	assert(payload(&d, "Duris.Combat").find("Secondary") == std::string::npos);
	concealed = nullptr;
	hit.damage_kind = SPLDAM_FIRE;
	hit.critical = false;
	gmcp_combat_damage(&actor, &primary, 8, &hit);
	json = cJSON_Parse(payload(&d, "Duris.Combat").c_str());
	assert(cJSON_IsTrue(cJSON_GetObjectItem(json, "primary")));
	assert(cJSON_IsFalse(cJSON_GetObjectItem(json, "critical")));
	assert(std::string(cJSON_GetStringValue(cJSON_GetObjectItem(json, "damageType"))) ==
	       "fire");
	cJSON_Delete(json);
	const auto events = count();
	gmcp_flush_initial_states();
	assert(count() == events && d.gmcp_event_count == 0);
	assert(payload(&d, "Combat.Update").find("Primary") != std::string::npos);
	assert(payload(&d, "Combat.Update").find("round") == std::string::npos);
	// Each event is retained in FIFO order; state resync never replays events.
	for (int n = 0; n < 64; ++n)
		gmcp_combat_damage(&actor, &primary, n + 1, &hit);
	assert(count() == events + 64 && d.gmcp_event_count == 64 && d.gmcp_event_bytes < 65536);
	const auto stopped_sequence = d.gmcp_event_sequence;
	gmcp_combat_damage(&actor, &primary, 1, &hit);
	assert(!d.write_failed && count() == events + 64);
	assert(!(d.gmcp_interests & GMCP_SUPPORT_COMBAT) && d.gmcp_control_pending);
	assert(d.gmcp_event_sequence == stopped_sequence);
	const auto stopped = packages[&d].size();
	gmcp_flush_initial_states();
	assert(!d.write_failed && !d.gmcp_control_pending && !d.gmcp_active_streams);
	assert(packages[&d][stopped] == "Duris.Capabilities");
	assert(packages[&d].back() == "Combat.Update");
	assert(payload(&d, "Duris.Capabilities").find("\"active\":[]") != std::string::npos);
	assert(payload(&d, "Combat.Update").find("Primary") != std::string::npos);
	gmcp_combat_damage(&actor, &primary, 1, &hit);
	assert(!d.write_failed && count() == events + 64);
	// Only an explicit new Subscribe restarts events; it never replays the lost hit.
	control_clock_us += 1000000;
	gmcp_handle_input(&d, subscribe, sizeof(subscribe) - 1);
	gmcp_flush_initial_states();
	gmcp_combat_damage(&actor, &primary, 1, &hit);
	assert(!d.write_failed && count() == events + 65);
	assert(d.gmcp_event_sequence == stopped_sequence + 1);
	reset();
	d.gmcp_supports |= GMCP_SUPPORT_TIME;
	d.gmcp_interests |= GMCP_SUPPORT_TIME;
	d.gmcp_event_bytes = 65536;
	gmcp_combat_damage(&actor, &primary, 1, &hit);
	assert(!d.write_failed && !d.gmcp_event_sequence);
	assert(d.gmcp_interests == GMCP_SUPPORT_TIME && d.gmcp_control_pending);
	queue_reject = true;
	gmcp_flush_initial_states();
	assert(!d.write_failed && d.gmcp_control_pending);
	queue_reject = false;
	gmcp_flush_initial_states();
	assert(!d.write_failed && !d.gmcp_control_pending);
	assert(d.gmcp_active_streams == GMCP_SUPPORT_TIME);
	reset();
	d.gmcp_event_sequence = 9007199254740992ULL;
	gmcp_combat_damage(&actor, &primary, 1, &hit);
	assert(payload(&d, "Duris.Combat").find("\"sequence\":\"9007199254740993\"") !=
	       std::string::npos);
	cJSON_Hooks hooks{ bounded_json_allocate, std::free };
	cJSON_InitHooks(&hooks);
	for (int budget = 0; budget < 45; ++budget)
	{
		reset();
		json_allocation_budget = budget;
		const auto previous = count();
		gmcp_combat_damage(&actor, &primary, 1, &hit);
		json_allocation_budget = -1;
		assert(count() == previous + (d.write_failed ? 0 : 1));
		assert(d.gmcp_event_sequence == (d.write_failed ? 0U : 1U));
	}
	reset();
	queue_reject = true;
	const auto rejected = count();
	gmcp_combat_damage(&actor, &primary, 1, &hit);
	queue_reject = false;
	assert(d.write_failed && count() == rejected && !d.gmcp_event_sequence);
	reset();
	d.gmcp_enabled = 0;
	const auto disabled_allocations = json_allocation_calls;
	const auto disabled_visibility = visibility_checks;
	gmcp_combat_damage(&actor, &primary, 1, &hit);
	assert(json_allocation_calls == disabled_allocations &&
	       visibility_checks == disabled_visibility);
	cJSON_InitHooks(nullptr);
	descriptor_list = saved_list;
}

int main()
{
	combat_contract(false);
	combat_contract(true);
	combat_events_contract(false);
	combat_events_contract(true);
	wire.clear();
	ws_wire.clear();
	packages.clear();
	deliveries.clear();
	websockets = 0;
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
	vessel.runtime_ref = { 1, 9007199254740993ULL };
	vessel.bridge = 1;
	vessel.location = 2;
	vessel.name = const_cast<char *>("Bronze Voyager");
	vessel.id = const_cast<char *>("AA");
	vessel.heading = 90;
	vessel.speed = 12;
	vessel.setheading = 359.9;
	vessel.setspeed = 8;
	vessel.crew.stamina = -400;
	vessel.crew.max_stamina = 800;
	vessel.armor[0] = 80;
	vessel.maxarmor[0] = 100;
	vessel.internal[0] = 40;
	vessel.maxinternal[0] = 50;
	vessel.slot[0].type = SLOT_CARGO;
	vessel.slot[0].val0 = 3;
	vessel.slot[0].val1 = 156000;
	vessel.slot[1].type = SLOT_CONTRABAND;
	vessel.slot[1].val0 = 2;
	vessel.slot[1].val1 = 56000;
	for (int i = 2; i < MAXSLOTS; ++i)
	{
		vessel.slot[i].type = i % 2 == 0 ? SLOT_WEAPON : SLOT_EQUIPMENT;
		vessel.slot[i].index = 0;
		vessel.slot[i].position = i % 4;
		vessel.slot[i].val1 = 5;
		vessel.slot[i].timer = 6;
	}
	// Exact production display boundaries, independent of timer readiness.
	for (const auto &[damage, expected] :
	     std::vector<std::pair<int, const char *>>{ { 0, "6" },
							{ 1, "Damaged" },
							{ 20, "Damaged" },
							{ 21, "Badly Damaged" },
							{ 99, "Badly Damaged" },
							{ 100, "Badly Damaged" },
							{ 101, "Destroyed" } })
	{
		vessel.slot[2].val2 = damage;
		char *data = json_build_ship_info(&vessel, &a);
		cJSON *root = cJSON_Parse(data);
		cJSON *weapon = cJSON_GetArrayItem(cJSON_GetObjectItem(root, "weapons"), 0);
		assert(std::string(cJSON_GetStringValue(
			       cJSON_GetObjectItem(weapon, "statusText"))) == expected);
		assert(cJSON_IsTrue(cJSON_GetObjectItem(weapon, "destroyed")) == (damage >= 100));
		assert(cJSON_IsFalse(cJSON_GetObjectItem(weapon, "ready")));
		cJSON_Delete(root);
		free(data);
	}
	vessel.slot[2].val2 = 100;
	vessel.slot[2].timer = 0;
	vessel.slot[3].val2 = 21;
	rooms[2].zone = 0;
	zones[0].flags = ZONE_MAP;
	zones[0].mapx = 100;
	zones[0].mapy = 100;
	enemy.name = const_cast<char *>("Enemy vessel");
	enemy.flags = LOADED;
	enemy.id = const_cast<char *>("BB");
	enemy.race = EVILSHIP;
	enemy.heading = 50;
	enemy.speed = 8;
	enemy.target = &vessel;
	vessel.target = &enemy;
	contacts[0].ship = &enemy;
	contacts[0].range = 5;
	contacts[0].bearing = 70;
	std::strcpy(contacts[0].arc, "SF");
	contacts[0].x = 54;
	contacts[0].y = 48;
	flush();
	assert(wire[&ad].size() == 2);
	emit(&ad, "Ship.Info");
	emit(&ad, "Ship.Contacts");
	auto json = payload(&ad, "Ship.Contacts");
	assert(json.find("\"shipKey\":\"1:9007199254740993\"") != std::string::npos);
	auto info = payload(&ad, "Ship.Info");
	assert(info.find("\"hullWeight\":330000") != std::string::npos);
	assert(info.find("\"current\":136,\"max\":165") != std::string::npos);
	assert(info.find("\"setHeading\":359,\"setSpeed\":8") != std::string::npos);
	assert(info.find("\"displayCrewStamina\":-20,\"crewStaminaBand\":\"fatigued\"") !=
	       std::string::npos);
	assert(info.find("forbidden relics") != std::string::npos);
	assert(info.find("\"target\":{\"id\":\"BB\",\"name\":\"Enemy vessel\"}") !=
	       std::string::npos);
	for (const auto &[stamina, band] :
	     std::vector<std::pair<float, const char *>>{ { 1, "rested" },
							  { 0, "fatigued" },
							  { -0.5, "fatigued" },
							  { -799, "fatigued" },
							  { -800, "exhausted" },
							  { -801, "exhausted" } })
	{
		vessel.crew.stamina = stamina;
		char *data = json_build_ship_info(&vessel, &a);
		assert(std::string(data).find(std::string("\"crewStaminaBand\":\"") + band +
					      "\"") != std::string::npos);
		free(data);
	}
	vessel.crew.stamina = -400;
	// Weight comes from the real slot/levistone helpers, including flight.
	ShipSlot saved = vessel.slot[3];
	vessel.slot[3].index = E_LEVISTONE;
	assert(vessel.slot[3].get_weight(&vessel) == 9);
	vessel.flags |= FLYING;
	assert(vessel.slot[3].get_weight(&vessel) == 0);
	vessel.flags &= ~FLYING;
	vessel.slot[3] = saved;
	assert(json.find("\"worldX\"") == std::string::npos);
	assert(json.find("\"you_targeting\":true") != std::string::npos);
	assert(json.find("\"heading\":90") != std::string::npos);
	wire.clear();
	flush();
	assert(wire.empty());
	static descriptor_data land_descriptors[128];
	static char_data land_players[128];
	for (int i = 0; i < 128; ++i)
	{
		land_players[i].desc = &land_descriptors[i];
		land_players[i].in_room = 0;
		land_descriptors[i].character = &land_players[i];
		land_descriptors[i].connected = CON_PLAYING;
		land_descriptors[i].gmcp_enabled = 1;
		land_descriptors[i].next = i < 127 ? &land_descriptors[i + 1] : nullptr;
	}
	ad.next = land_descriptors;
	ship_visits = contact_scans = 0;
	flush();
	assert(ship_visits == 2 && contact_scans == 1 && wire.empty());
	ad.next = &bd;
	contact_scans = 0;
	flush();
	assert(contact_scans == 1); // one all-ships scan for both bridge observers
	assert(wire[&ad].empty() && wire[&bd].size() == 2); // stationary newcomer
	assert(payload(&bd, "Ship.Info").find("\"maxSpeed\":23") != std::string::npos);
	bd.durisweb_verified = 1;
	wire.clear();
	contact_scans = 0;
	flush();
	assert(contact_scans == 1);
	assert(payload(&bd, "Ship.Contacts").find("\"worldX\"") != std::string::npos);
	assert(wire[&ad].empty());
	bd.durisweb_verified = 0;
	flush();
	assert(payload(&bd, "Ship.Contacts").find("\"worldX\"") == std::string::npos);
	second_vessel.flags = LOADED;
	second_vessel.runtime_ref = { 2, 2 };
	second_vessel.bridge = 0;
	second_vessel.location = 2;
	second_ship_enabled = true;
	b.in_room = 0;
	contact_scans = 0;
	gmcp_flush_dirty_ship_contacts();
	assert(contact_scans == 2); // independent contact set for each occupied ship
	assert(payload(&bd, "Ship.Contacts").find("\"contacts\":[]") != std::string::npos);
	second_ship_enabled = false;
	b.in_room = 1;
	flush();
	vessel.flags &= ~LOADED;
	flush();
	assert(payload(&ad, "Ship.Info") == "{}");
	assert(payload(&bd, "Ship.Contacts") == "{\"contacts\":[]}");
	vessel.flags |= LOADED;
	flush();
	assert(payload(&ad, "Ship.Info").find("Bronze Voyager") != std::string::npos);
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
	assert(wire.empty());
	gmcp_flush_initial_states();
	for (const char *pkg : { "Char.Status", "Char.Vitals", "Char.Affects", "Group.Status",
				 "Room.Info", "Quest.Status", "Combat.Update" })
		payload(&ad, pkg);
	wire.clear();
	gmcp_handle_negotiation(&ad, TELNET_DO);
	gmcp_flush_initial_states();
	assert(wire.empty());
	gmcp_send_room_map(&a, "&+G@&n\n");
	emit(&ad, "Room.Map");
	assert(websockets == 0); // Telnet framing retained
	a.player.name = const_cast<char *>("Tester");
	victim.player.name = const_cast<char *>("wolf");
	victim.points.hit = 40;
	victim.points.max_hit = 100;
	a.specials.fighting = &victim;
	victim.in_room = a.in_room;
	applied_damage_notice(&a, &victim, 8);
	emit(&ad, "Combat.Update");
	static char_data primary;
	primary.player.name = const_cast<char *>("primary");
	primary.in_room = a.in_room;
	victim.in_room = a.in_room;
	primary.points.hit = 90;
	primary.points.max_hit = 100;
	a.specials.fighting = &primary;
	applied_damage_notice(&a, &victim, 8);
	gmcp_flush_initial_states();
	assert(payload(&ad, "Combat.Update").find("\"name\":\"primary\"") != std::string::npos);
	assert(payload(&ad, "Combat.Update").find("\"round\"") == std::string::npos);
	a.specials.fighting = &victim;
	applied_damage_notice(&a, &victim, 8);
	assert(payload(&ad, "Combat.Update").find("\"name\":\"wolf\"") != std::string::npos);
	assert(payload(&ad, "Combat.Update").find("\"damage\":8") != std::string::npos);
	a.specials.fighting = nullptr;
	gmcp_combat_end(&a);
	assert(payload(&ad, "Combat.Update").find("\"target\":null") != std::string::npos);
	assert(payload(&ad, "Combat.Update").find("\"tank\":null") != std::string::npos);
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
	// Pulse-timed protections must report remaining elapsed seconds, including
	// after the stored duration has become stale while the event counts down.
	affect.flags = AFFTYPE_SHORT;
	affect.duration = 2640;
	event_short_affect_data timed_data{ &a, &affect };
	nevent_data timed_event{};
	timed_event.func = event_short_affect;
	timed_event.data = &timed_data;
	a.nevents = &timed_event;
	auto affect_seconds = [&]()
	{
		char *encoded = json_build_char_affects(&a);
		cJSON *decoded = cJSON_Parse(encoded);
		assert(decoded);
		int duration =
			cJSON_GetObjectItem(cJSON_GetArrayItem(decoded, 0), "duration")->valueint;
		cJSON_Delete(decoded);
		free(encoded);
		return duration;
	};
	assert(affect_seconds() == 660);
	affect_remaining_pulses = 1720;
	assert(affect_seconds() == 430);
	a.nevents = nullptr;
	assert(affect_seconds() == 0);
	affect.flags = 0;
	affect.duration = 3;
	assert(affect_seconds() == 180); // ordinary display behavior stays unchanged
	quest_profile.desc2 = const_cast<char *>("bronze guardian");
	apc.quest_active = 1;
	apc.quest_type = FIND_AND_KILL;
	apc.quest_kill_original = 5;
	apc.quest_kill_how_many = 2;
	gmcp_quest_status(&a);
	emit(&ad, "Quest.Status");
	apc.quest_map_bought = 1;
	apc.quest_map_room = 2;
	apc.quest_zone_number = 228;
	ad.gmcp_quest_map_sent = 1;
	quest_loads = 0;
	wire.clear();
	for (int i = 0; i < 500; ++i)
	{
		gmcp_handle_negotiation(&ad, TELNET_DONT);
		gmcp_handle_negotiation(&ad, TELNET_DO);
	}
	assert(wire.empty() && quest_loads == 0);
	gmcp_flush_initial_states();
	assert(quest_loads == 0 && ad.gmcp_quest_map_sent == 1);
	assert(payload(&ad, "Quest.Map") == "{\"map\":\"quest map\",\"zoneNumber\":228}");
	assert(a.in_room == 1);
	// Text QUEST uses the same non-moving viewpoint and Quest.Map package.
	const int old_position = a.specials.position;
	a.specials.position = STAT_NORMAL | POS_STANDING;
	const auto before_quest_map = apc;
	const auto before_room = rooms[1];
	wire.clear();
	show_map_at(&a, 2);
	assert(payload(&ad, "Quest.Map") == "{\"map\":\"quest map\",\"zoneNumber\":228}");
	assert(wire[&ad].size() == 1 && a.in_room == 1);
	assert(!memcmp(&apc, &before_quest_map, sizeof(apc)));
	assert(!memcmp(&rooms[1], &before_room, sizeof(before_room)));
	wire.clear();
	show_map_at(&a, NOWHERE);
	show_map_at(&a, top_of_world + 1);
	assert(wire.empty() && a.in_room == 1);
	apc.quest_map_bought = 0;
	show_map_at(&a, 2);
	assert(wire.empty() && a.in_room == 1);
	apc.quest_map_bought = 1;
	a.specials.position = old_position;

	// A checked command reuses its verdict. Neither serialization nor the
	// checked transport overload may run another eligibility query.
	const auto saved_quest = apc;
	const int checks_before = quest_checks;
	for (auto status :
	     { world_quest_target_status::blocked, world_quest_target_status::unproven,
	       world_quest_target_status::needs_origin, world_quest_target_status::unavailable })
	{
		wire.clear();
		gmcp_quest_status(&a, status);
		assert(quest_checks == checks_before);
		assert(!memcmp(&apc, &saved_quest, sizeof(apc)));
		const std::string state = payload(&ad, "Quest.Status");
		assert(state.find("\"zoneNumber\"") == std::string::npos);
		assert(state.find("bronze guardian") == std::string::npos);
		assert(state.find("\"mapBought\":true") != std::string::npos);
		assert(payload(&ad, "Quest.Map") == "{\"map\":\"\",\"zoneNumber\":0}");
		assert(ad.gmcp_quest_map_sent == 0);
	}
	apc.quest_active = 0;
	apc.quest_replacement_due = 1;
	wire.clear();
	gmcp_quest_status(&a, world_quest_target_status::unavailable);
	const std::string pending = payload(&ad, "Quest.Status");
	assert(pending.find("\"active\":false") != std::string::npos);
	assert(pending.find("\"replacementDue\":true") != std::string::npos);
	assert(pending.find("\"killCount\":2") != std::string::npos);
	assert(pending.find("\"killRequired\":5") != std::string::npos);
	assert(pending.find("\"mapBought\":true") != std::string::npos);
	assert(payload(&ad, "Quest.Map") == "{\"map\":\"\",\"zoneNumber\":0}");
	apc = saved_quest;
	ad.gmcp_quest_map_sent = 1;

	wire.clear();
	gmcp_flush_initial_states();
	assert(wire.empty() && quest_loads == 0);
	gmcp_handle_negotiation(&ad, TELNET_DONT);
	gmcp_handle_negotiation(&ad, TELNET_DO);
	gmcp_handle_negotiation(&ad, TELNET_DONT);
	gmcp_flush_initial_states();
	assert(wire.empty()); // disabling before the flush cancels the request
	gmcp_handle_negotiation(&ad, TELNET_DO);
	gmcp_flush_initial_states();
	assert(quest_loads == 0); // later legitimate re-negotiation is not lost
	payload(&ad, "Quest.Status");
	payload(&ad, "Quest.Map");
	wire.clear();
	gmcp_send_initial_state(&a); // toggle/reconnect also resends an already-sent map
	payload(&ad, "Quest.Map");
	static char_data morph;
	static npc_only_data morph_npc;
	morph.player.name = const_cast<char *>("morph body");
	morph.specials.act = ACT_ISNPC;
	morph.only.npc = &morph_npc;
	morph_npc.orig_char = &a;
	morph.desc = &ad;
	morph.in_room = 0;
	morph.points.hit = 37;
	morph.points.max_hit = 80;
	morph.affected = &affect;
	morph.specials.fighting = &victim;
	victim.in_room = morph.in_room;
	rooms[0].name = const_cast<char *>("Morph room");
	ad.original = &a;
	ad.character = &morph;
	a.desc = nullptr;
	wire.clear();
	gmcp_send_initial_state(&morph);
	assert(payload(&ad, "Char.Status").find("\"name\":\"Tester\"") != std::string::npos);
	assert(payload(&ad, "Char.Vitals").find("\"hp\":37") != std::string::npos);
	assert(payload(&ad, "Char.Affects").find("bless") != std::string::npos);
	assert(payload(&ad, "Room.Info").find("Morph room") != std::string::npos);
	assert(payload(&ad, "Combat.Update").find("wolf") != std::string::npos);
	assert(payload(&ad, "Quest.Status").find("\"active\":true") != std::string::npos);
	assert(payload(&ad, "Quest.Map").find("\"zoneNumber\":228") != std::string::npos);
	payload(&ad, "Group.Status");
	assert(morph.in_room == 0 && a.in_room == 1 && !a.desc && ad.character == &morph);
	a.specials.act3 |= PLR3_NOGMCP;
	wire.clear();
	gmcp_send_initial_state(&morph);
	gmcp_quest_status(&morph);
	assert(wire.empty()); // the original player's preference controls the morph
	a.specials.act3 &= ~PLR3_NOGMCP;
	gmcp_send_initial_state(&morph);
	payload(&ad, "Quest.Map");
	ad.original = nullptr;
	ad.character = &a;
	victim.in_room = a.in_room;
	a.desc = &ad;
	morph.desc = nullptr;
	apc.quest_map_bought = 0;
	gmcp_comm_channel_ex(&a, "nchat", "Tester", "hello", "good");
	emit(&ad, "Comm.Channel");
	group_list member_b = { &b, nullptr };
	group_list member_a = { &a, &member_b };
	a.group = b.group = &member_a;
	b.player.name = const_cast<char *>("Ally");
	ad.websocket = 1;
	ad.ws_handshake_done = 0;
	ws_send_full_game_state(&ad);
	assert(ws_wire.empty() && queued_looks == 1);
	ad.ws_handshake_done = 1;
	a.specials.fighting = &victim;
	apc.quest_map_bought = ad.gmcp_quest_map_sent = 1;
	ws_send_full_game_state(&ad);
	assert(queued_looks == 2);
	for (const char *pkg :
	     { "Char.Status", "Char.Vitals", "Char.Affects", "Room.Info", "Quest.Status",
	       "Quest.Map", "Group.Status", "Combat.Update", "Ship.Info", "Ship.Contacts" })
		payload(&ad, pkg);
	assert(payload(&ad, "Group.Status").find("Ally") != std::string::npos);
	assert(payload(&ad, "Combat.Update").find("wolf") != std::string::npos);
	assert(payload(&ad, "Ship.Info") == "{}");
	flush();
	assert(payload(&ad, "Ship.Info").find("Bronze Voyager") != std::string::npos);
	a.specials.fighting = nullptr;
	a.group = nullptr;
	ws_wire.clear();
	ws_send_full_game_state(&ad);
	assert(payload(&ad, "Combat.Update").find("\"target\":null") != std::string::npos);
	assert(payload(&ad, "Combat.Update").find("\"tank\":null") != std::string::npos);
	assert(payload(&ad, "Group.Status").find("\"members\":[]") != std::string::npos);
	ad.websocket = 0;
	apc.quest_map_bought = 0;
	a.group = &member_a;
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
	control_time_contract(&a);
	session_contract(&a, false);
	session_contract(&a, true);
}
