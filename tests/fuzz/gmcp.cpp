// GMCP input from a client that has not logged in: gmcp_handle_input(), which takes
// Core.Hello, Client.Info and bounded new-stream control. The rest of gmcp.c sends to a logged-in character; it is
// linked, and what it calls is stubbed here.
// fuzz-sources: src/net/gmcp.c
// fuzz-libs: -lcjson -lcrypto
// fuzz-max-len: 1048600 (past GMCP_MAX_INPUT_SIZE (1 MiB))
#include "core/structs.h"
#include "core/prototypes.h"
#include "core/json_utils.h"
#include "net/gmcp.h"
#include "net/websocket.h"
#include "ships/ships.h"
#include "world/map.h"
#include <cstdint>
#include <cstdlib>
#include <cjson/cJSON.h>

void __free(void *memory, const char *, int)
{
	std::free(memory);
}
P_desc descriptor_list = nullptr;
const char *where[MAX_WEAR] = {};
bool ac_can_see_obj(P_char, P_obj, int)
{
	return true;
}
bool has_innate(P_char, int)
{
	return false;
}
char *item_condition(P_obj)
{
	static char condition[] = "";
	return condition;
}

time_info_data time_info{};
P_room world = nullptr;
P_obj object_list = nullptr;
int top_of_world = -1;
struct zone_data *zone_table = nullptr;
extern const struct class_names class_names_table[] = {};
extern const struct race_names race_names_table[] = {};
struct ContactData contacts[MAXSHIPS];
ShipObjHash::ShipObjHash()
	: table{}
	, sz(0)
{
}
ShipObjHash shipObjHash;
bool ShipObjHash::get_first(visitor &)
{
	return false;
}
bool ShipObjHash::get_next(visitor &)
{
	return false;
}
int ShipData::get_maxspeed(P_char) const
{
	return 0;
}
int getcontacts(P_ship, bool)
{
	return 0;
}
P_ship get_ship_from_char(P_char)
{
	return nullptr;
}
int IS_MORPH(P_char)
{
	return 0;
}
int get_property(const char *, int fallback)
{
	return fallback;
}
bool ac_can_see(P_char, P_char, bool)
{
	return true;
}
char *PERS(P_char ch, P_char, int, bool)
{
	return ch->player.name;
}
void update_groupies(P_char, bool) {}
char *json_build_char_affects(struct char_data *)
{
	return nullptr;
}
char *json_build_char_status(struct char_data *)
{
	return nullptr;
}
char *json_build_char_vitals(struct char_data *)
{
	return nullptr;
}
char *json_build_comm_channel(const char *, const char *, const char *)
{
	return nullptr;
}
char *json_build_comm_channel_ex(const char *, const char *, const char *, const char *)
{
	return nullptr;
}
char *json_build_quest_status(struct char_data *, world_quest_target_status)
{
	return nullptr;
}
world_quest_target_status world_quest_refresh(P_char, int)
{
	return world_quest_target_status::unproven;
}
char *json_build_room_info(struct room_data *, struct char_data *)
{
	return nullptr;
}
char *json_build_ship_info(struct ShipData *, struct char_data *)
{
	return nullptr;
}
int write_to_descriptor_binary(P_desc, const unsigned char *, size_t)
{
	return 0;
}
const char *input_command_label(const char *)
{
	return "";
}
void display_map_room(struct char_data *, int, int, int, int) {}
int flag2idx(int)
{
	return 0;
}
int is_desc_valid(P_desc)
{
	return 1;
}
int real_room(const int)
{
	return -1;
}
void char_from_room(P_char) {}
bool char_to_room(P_char, int, int)
{
	return false;
}
std::string strip_ansi(const char *text)
{
	return text;
}
int websocket_send_json(struct descriptor_data *, const char *, const char *)
{
	return 0;
}

uint64_t latency_trace_monotonic_us()
{
	return 1000000;
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
	descriptor_data d{};
	d.descriptor = -1;
	d.gmcp_enabled = 1;
	d.gmcp_supports = GMCP_SUPPORT_CAPABILITIES;
	gmcp_handle_input(&d, reinterpret_cast<const char *>(data), size);
	if (size && data[0] == '{')
	{
		const char *end = nullptr;
		const char *raw = reinterpret_cast<const char *>(data);
		cJSON *message = cJSON_ParseWithLengthOpts(raw, size, &end, 0);
		if (message)
		{
			gmcp_handle_control_json(&d, message, raw, size, end);
			cJSON_Delete(message);
		}
	}

	descriptor_list = &d;
	gmcp_flush_initial_states();
	descriptor_list = nullptr;
	return 0;
}
