
/************************************************************************
 * sql.c - interface to MySQL database and functions for stats keeping  *
 *                                                                      *
 * Written by: Thima (Xenofon Papadopoulos)                             *
 *                                                                      *
 ************************************************************************/

#include "core/prototypes.h"
#include "world/difficulty.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "cmd/interp.h"
#include "item/item_uid_allocator.h"
#include "persistence/critical_command.h"
#include "flatfile/flatfile_artifact_repository.h"
#include "flatfile/flatfile_help_catalog.h"
#include "flatfile/flatfile_ip_activity_repository.h"
#include "flatfile/flatfile_item_repository.h"
#include "flatfile/flatfile_offline_message_repository.h"
#include "flatfile/flatfile_frag_leaderboard_repository.h"
#include "flatfile/flatfile_shop_trophy_history.h"
#include "flatfile/flatfile_world_quest_history.h"
#include "persistence/persistence_mode.h"
#include "core/utils.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "persistence/dupe_log.h"
#include "sql/sql_telemetry_connection.h"
#include "sql/sql_exclusion_guard.h"
#include "item/item_ownership_runtime.h"
#include "persistence/persistence_checkpoint.h"
#include "sql/sql_pool.h"
#include "player/player_snapshot_repository.h"
#include "account/session_audit_transaction.h"
#include "core/runtime_compatibility_contract.h"
#include <algorithm>
#include <atomic>
#include <memory>
#include <set>
#include <openssl/sha.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <pthread.h>
#include <algorithm>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include "account/account.h"
#include "account/account_reward.h"
#include "net/gmcp.h"
#include "net/poll.h"
#include "account/multiplay_whitelist.h"
#include "guild/assocs.h"
#include "economy/boon.h"
#include "world/epic.h"
#include "world/graph.h"
#include "core/mm.h"
#include "item/objmisc.h"
#include "redis/redis_maintenance.h"
#include "classes/specializations.h"
#include "magic/spells.h"
#include "sql/sql_player.h"
#include "combat/frag_cap_config.h"
#include "world/timers.h"
#include "core/utility.h"
#include <errno.h>
#include <limits.h>

extern P_index mob_index;
extern const struct race_names race_names_table[];
extern const struct class_names class_names_table[];
extern const struct playable_race_info playable_races[];
extern const char *specdata[][MAX_SPEC];
extern P_room world;
extern int RUNNING_PORT;
void get_assoc_name(int, char *);
bool get_equipment_list(P_char ch, char *buf, int list_only);
extern P_index obj_index;
extern struct zone_data *zone_table;
extern int top_of_zone_table;
extern const int top_of_world;
extern P_index obj_index;
extern P_obj object_list;
extern P_room world;

void get_pkill_player_description(P_char ch, char *buffer);

#ifndef __NO_MYSQL__
#include <errmsg.h>
static int sql_trace_burst = 0;
static const pid_t sql_main_process_id = getpid();
static bool sql_trace_enabled(void);
static bool sql_trace_active(void);
static void sql_trace_log_drain(MYSQL *conn, const char *phase, bool drained);
static bool sql_verify_metadata_fingerprint(void);
#endif

static int flat_sql_shop_sell(P_char ch, P_obj obj, int value)
{
	if (!obj)
		return 0;
	const int item = obj->R_num >= 0 ? obj_index[obj->R_num].virtual_number : 0;
	const int seller = ch && IS_PC(ch) ? GET_PID(ch) : 0;
	std::string error;
	if (flatfile_shop_trophy_record(persistence_mode_flatfile_root(), item, value, seller,
					static_cast<int64_t>(time(nullptr)),
					&error) != flatfile_shop_trophy_result::ok)
	{
		persistence_alert(AVATAR, "shop_trophy", "global", "none", "none", "record",
				  "flat_write_failed", "item=%d seller=%d error=%s", item, seller,
				  error.c_str());
		return -1;
	}
	return 1;
}

static int flat_sql_shop_trophy(P_obj obj)
{
	if (!obj)
		return 0;
	if (obj->name && strstr(obj->name, "_ore_"))
		return 0;
	const int objvir = OBJ_VNUM(obj);
	if (objvir >= 400000 && objvir < 400202)
		return 0;
	const int item = obj->R_num >= 0 ? obj_index[obj->R_num].virtual_number : 0;
	int count = 0;
	std::string error;
	if (flatfile_shop_trophy_count(persistence_mode_flatfile_root(), item,
				       static_cast<int64_t>(time(nullptr)), &count,
				       &error) != flatfile_shop_trophy_result::ok)
	{
		persistence_alert(AVATAR, "shop_trophy", "global", "none", "none", "count",
				  "flat_read_failed", "item=%d error=%s", item, error.c_str());
		return -1;
	}
	return count;
}

#ifdef __NO_MYSQL__
MYSQL *DB = NULL;

MYSQL *sql_open_configured_connection(unsigned long client_flags)
{
	(void)client_flags;
	return NULL;
}

MYSQL_RES *db_query_at(struct persistence_query_site site, const char *format, ...)
{
	(void)site;
	(void)format;
	return NULL;
}

bool sql_observed_execute_at(MYSQL *conn, struct persistence_query_site site,
			     enum persistence_query_context context, const char *sql, size_t len,
			     uint64_t *operation_id)
{
	(void)conn;
	(void)site;
	(void)context;
	(void)sql;
	(void)len;
	(void)operation_id;
	return false;
}

char *mysql_str(const char * /*str*/, char *buf)
{
	if (buf)
		buf[0] = '\0';
	return buf;
}

int initialize_mysql()
{
	return -1;
}
void shutdown_mysql(void) {}
void do_sql(P_char /*ch*/, char * /*argument*/, int /*cmd*/) {}
int sql_save_player_core(P_char /*ch*/)
{
	return 0;
}
void sql_insert_item(P_char /*ch*/, P_obj /*obj*/, char * /*desc*/) {}

void sql_webinfo_toggle(P_char /*ch*/) {}
void sql_update_level(P_char /*ch*/) {}
int sql_shop_trophy(P_obj obj)
{
	return flat_sql_shop_trophy(obj);
}
int sql_shop_sell(P_char ch, P_obj obj, int value)
{
	return flat_sql_shop_sell(ch, obj, value);
}
void sql_world_quest_finished(P_char ch, P_obj /*obj*/)
{
	if (!ch || !IS_PC(ch) || !ch->only.pc || GET_PID(ch) <= 0 ||
	    ch->only.pc->quest_mob_vnum <= 0)
		return;
	std::string error;
	if (flatfile_world_quest_record(
		    persistence_mode_flatfile_root(), static_cast<uint32_t>(GET_PID(ch)),
		    ch->only.pc->quest_mob_vnum, GET_LEVEL(ch), static_cast<int64_t>(time(nullptr)),
		    &error) != flatfile_world_quest_result::ok)
		persistence_alert(AVATAR, "world_quest", "player", "unknown", "record",
				  "flat_write_failed", "pid=%d error=%s", GET_PID(ch),
				  error.c_str());
}

void sql_world_quest_history_load(P_char) {}

int sql_world_quest_done_already(P_char ch, int quest_target)
{
	if (!ch || !IS_PC(ch) || !ch->only.pc || GET_PID(ch) <= 0 || quest_target <= 0)
		return -1;
	bool completed = false;
	std::string error;
	if (flatfile_world_quest_completed(persistence_mode_flatfile_root(),
					   static_cast<uint32_t>(GET_PID(ch)), quest_target,
					   &completed, &error) != flatfile_world_quest_result::ok)
	{
		logit(LOG_DEBUG, "sql_world_quest_done_already: %s", error.c_str());
		return -1;
	}
	return completed ? 1 : 0;
}

int sql_world_quest_can_do_another(P_char ch)
{
	if (!ch || !IS_PC(ch) || !ch->only.pc || GET_PID(ch) <= 0)
		return -1;
	int completed_today = 0;
	std::string error;
	if (flatfile_world_quest_count_day(persistence_mode_flatfile_root(),
					   static_cast<uint32_t>(GET_PID(ch)), GET_LEVEL(ch),
					   static_cast<int64_t>(time(nullptr)), &completed_today,
					   &error) != flatfile_world_quest_result::ok)
	{
		logit(LOG_DEBUG, "sql_world_quest_can_do_another: %s", error.c_str());
		return -1;
	}
	int maximum = 0;
	if (GET_LEVEL(ch) <= 30)
		maximum = get_property("world.quest.max.level.30.andUnder", 6.000);
	else if (GET_LEVEL(ch) <= 40)
		maximum = get_property("world.quest.max.level.40.andUnder", 6.000);
	else if (GET_LEVEL(ch) <= 50)
		maximum = get_property("world.quest.max.level.50.andUnder", 6.000);
	else if (GET_LEVEL(ch) <= 55)
		maximum = get_property("world.quest.max.level.55.andUnder", 6.000);
	else
		maximum = get_property("world.quest.max.level.other", 6.000);
	maximum = difficulty_scale_world_quest_allowance(maximum);
	return std::max(maximum - completed_today, 0);
}

static int flat_ip_racewar_side(P_char ch)
{
	return IS_TRUSTED(ch) ? RACEWAR_NONE : GET_RACEWAR(ch);
}

void sql_connectIP(P_char ch)
{
	if (!ch || !IS_PC(ch) || !ch->only.pc || GET_PID(ch) <= 0 || !ch->desc ||
	    !ch->desc->host[0])
		return;
	std::string error;
	if (flatfile_ip_activity_connect(
		    persistence_mode_flatfile_root(), static_cast<uint32_t>(GET_PID(ch)),
		    ch->desc->host, flat_ip_racewar_side(ch), static_cast<int64_t>(time(nullptr)),
		    &error) != flatfile_ip_activity_result::ok)
		logit(LOG_DEBUG, "sql_connectIP: failed to persist IP activity: %s", error.c_str());
}

void sql_disconnectIP(P_char ch)
{
	if (!ch || !IS_PC(ch) || !ch->only.pc || GET_PID(ch) <= 0 || !ch->desc)
		return;
	std::string error;
	if (flatfile_ip_activity_disconnect(
		    persistence_mode_flatfile_root(), static_cast<uint32_t>(GET_PID(ch)),
		    flat_ip_racewar_side(ch), static_cast<int64_t>(time(nullptr)),
		    &error) != flatfile_ip_activity_result::ok)
		logit(LOG_DEBUG, "sql_disconnectIP: failed to persist IP activity: %s",
		      error.c_str());
}

const char *sql_select_IP_info(P_char ch, char *buf, size_t bufSize, time_t *lastConnect,
			       time_t *lastDisconnect)
{
	if (buf && bufSize)
		buf[0] = '\0';
	if (lastConnect)
		*lastConnect = 0;
	if (lastDisconnect)
		*lastDisconnect = 0;
	if (!buf || !bufSize || !ch || !IS_PC(ch) || !ch->only.pc || GET_PID(ch) <= 0)
		return buf;

	flatfile_ip_activity_record record;
	std::string error;
	const auto loaded = flatfile_ip_activity_get(persistence_mode_flatfile_root(),
						     static_cast<uint32_t>(GET_PID(ch)), &record,
						     &error);
	if (loaded == flatfile_ip_activity_result::not_found)
		return buf;
	if (loaded != flatfile_ip_activity_result::ok)
	{
		logit(LOG_DEBUG, "sql_select_IP_info: failed to load IP activity: %s",
		      error.c_str());
		return buf;
	}

	const int64_t now = static_cast<int64_t>(time(nullptr));
	// ADR 0003: an address is not shown 30 days after the login that left it.
	if (now - record.last_connect <= 30 * 24 * 3600)
		strlcpy(buf, record.ip.c_str(), bufSize);
	if (lastConnect && record.last_connect > 0 && now >= record.last_connect)
		*lastConnect = static_cast<time_t>(now - record.last_connect);
	if (lastDisconnect && record.last_disconnect > 0 && now >= record.last_disconnect)
		*lastDisconnect = static_cast<time_t>(now - record.last_disconnect);
	return buf;
}

bool qry_at(struct persistence_query_site site, const char *format, ...)
{
	(void)site;
	(void)format;
	return FALSE;
}
static bool enqueue_flat_offline_message(const char *message, int pid,
					 const unsigned char *message_id = nullptr)
{
	const char *root = persistence_mode_flatfile_root();
	critical_operation_id operation_id = {};
	if (message_id)
		memcpy(operation_id.bytes.data(), message_id, operation_id.bytes.size());
	else if (!critical_operation_id_generate(&operation_id))
		return false;
	std::string error;
	const bool success = root && message && pid > 0 &&
			     flatfile_offline_message_enqueue(root, static_cast<uint32_t>(pid),
							      operation_id.bytes, message,
							      &error) ==
				     flatfile_offline_message_result::ok;
	if (!success)
		persistence_alert(AVATAR, "offline_message", "player", "unknown", "enqueue",
				  "flat_write_failed", "pid=%d error=%s", pid, error.c_str());
	return success;
}
void send_to_pid_offline(const char *message, int pid)
{
	enqueue_flat_offline_message(message, pid);
}
bool send_to_pid_offline_deduplicated(const char *message, int pid, const unsigned char *message_id)
{
	return message_id && enqueue_flat_offline_message(message, pid, message_id);
}
void send_offline_messages(P_char ch)
{
	const char *root = persistence_mode_flatfile_root();
	if (!root || !ch || IS_NPC(ch) || GET_PID(ch) <= 0)
		return;
	std::vector<flatfile_offline_message_record> messages;
	std::string error;
	if (flatfile_offline_message_list(root, static_cast<uint32_t>(GET_PID(ch)), &messages,
					  &error) != flatfile_offline_message_result::ok)
	{
		persistence_alert(AVATAR, "offline_message", "player", "unknown", "load",
				  "flat_read_failed", "pid=%d error=%s", GET_PID(ch),
				  error.c_str());
		return;
	}
	std::sort(messages.begin(), messages.end(),
		  [](const auto &left, const auto &right)
		  {
			  return left.created_at != right.created_at ?
					 left.created_at < right.created_at :
					 left.id < right.id;
		  });
	for (const auto &message : messages)
	{
		send_to_char(message.text.c_str(), ch);
		const auto acknowledged = flatfile_offline_message_acknowledge(
			root, static_cast<uint32_t>(GET_PID(ch)), message.id, &error);
		if (acknowledged != flatfile_offline_message_result::ok &&
		    acknowledged != flatfile_offline_message_result::not_found)
		{
			persistence_alert(AVATAR, "offline_message", "player", "unknown",
					  "acknowledge", "flat_write_failed", "pid=%d error=%s",
					  GET_PID(ch), error.c_str());
			break;
		}
	}
}
bool sql_persistence_item_owner_matches(unsigned long long /*item_uid*/,
					const char * /*owner_type*/, const char * /*owner_ref*/,
					const char * /*context*/)
{
	return false;
}
bool sql_persistence_item_owner_matches_identity(unsigned long long /*item_uid*/,
						 const char * /*owner_type*/,
						 unsigned long long /*owner_id*/,
						 unsigned long long /*owner_context_id*/,
						 const char * /*context*/)
{
	return false;
}
bool sql_persistence_reconcile_world_recovery_items(const world_recovery_authority_item *items,
						    size_t count,
						    item_ownership_runtime_entry *authoritative,
						    size_t authoritative_capacity)
{
	(void)items;
	(void)authoritative;
	return count == 0 && authoritative_capacity == 0;
}
bool sql_persistence_world_recovery_items_owned(const std::vector<uint64_t> &item_uids,
						std::unordered_set<uint64_t> *owned)
{
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	return owned && root &&
	       flatfile_item_repository_world_recovery_owned(root, item_uids, owned, &error) ==
		       flatfile_item_repository_result::ok;
}
bool sql_hydrate_item_owner_revisions(void)
{
	return false;
}
void get_level_cap_info(long *max_frags, int *racewar, int *level, time_t *next_update)
{
	if (max_frags)
		*max_frags = -1;
	if (racewar)
		*racewar = RACEWAR_NONE;
	if (level)
		*level = frag_cap_config_get()->cap_floor_level;
	if (next_update)
		*next_update = 0;
}
int sql_level_cap(int /*racewar_side*/)
{
	return frag_cap_config_get()->cap_floor_level;
}
void show_total_donated(P_char /*ch*/, const char * /*account_name*/) {}
void sql_update_frag_leaderboard(P_char ch)
{
	if (!ch || IS_NPC(ch))
		return;
	const char *root = persistence_mode_flatfile_root();
	const char *account = get_account_name_safe(ch);
	const char *name = GET_NAME(ch);
	if (!root || GET_PID(ch) <= 0 || !account || !*account || !name || !*name)
		return;
	flatfile_frag_leaderboard_record record;
	record.pid = static_cast<uint32_t>(GET_PID(ch));
	record.account_name = account;
	record.character_name = name;
	record.total_frags = ch->only.pc->frags;
	record.racewar = GET_RACEWAR(ch);
	record.race_name = race_names_table[ch->player.race].normal;
	record.class_name = class_names_table[flag2idx(ch->player.m_class)].normal;
	record.level = GET_LEVEL(ch);
	record.last_updated = static_cast<int64_t>(time(nullptr));
	record.revision = 1;
	std::string error;
	if (flatfile_frag_leaderboard_upsert(root, record, &error) !=
	    flatfile_frag_leaderboard_result::ok)
		persistence_alert(AVATAR, "frag_leaderboard", "player", "unknown", "upsert",
				  "flat_write_failed", "pid=%d error=%s", GET_PID(ch),
				  error.c_str());
}
bool sql_trace_exec_at(struct persistence_query_site /*source_site*/, const char * /*label*/,
		       const char * /*sql*/, size_t /*len*/, bool /*drain_before*/,
		       bool /*drain_after*/)
{
	return false;
}
void sql_log_player_login(P_char ch, const char *status)
{
	if (!ch || IS_NPC(ch) || !status ||
	    (strcasecmp(status, "login") && strcasecmp(status, "logout")))
		return;
	sql_log(ch, CONNECTLOG, "Session audit: %s", status);
}
void update_zone_db() {}
void show_frag_trophy(P_char ch, P_char /*who*/)
{
	send_to_char("Disabled.", ch);
}

static void sanitize_flat_log_field(const char *source, char *destination, size_t capacity)
{
	if (!destination || capacity == 0)
		return;

	size_t index = 0;
	if (source)
	{
		for (; source[index] && index + 1 < capacity; ++index)
		{
			const unsigned char byte = static_cast<unsigned char>(source[index]);
			destination[index] = byte < 0x20 || byte == 0x7f ? ' ' : source[index];
		}
	}
	destination[index] = '\0';
}

void sql_log(P_char ch, const char *kind, const char *format, ...)
{
	if (!ch)
	{
		debug("sql_log called for non-existent ch!");
		return;
	}

	if (!IS_PC(ch))
	{
		debug("sql_log called in sql.c for mobile ch - %s - Vnum %d", GET_NAME(ch),
		      GET_VNUM(ch));
		debug("sql_log kind '%s', format '%s'", kind ? kind : "(null)",
		      format ? format : "(null)");
		return;
	}

	if (!ch->only.pc || !GET_NAME(ch) || !kind || !format)
	{
		debug("sql_log called with incomplete player log data");
		return;
	}

	static char message[MAX_STRING_LENGTH];
	va_list args;
	va_start(args, format);
	const int message_length = vsnprintf(message, sizeof(message), format, args);
	va_end(args);
	if (message_length < 0 || message_length >= static_cast<int>(sizeof(message)))
	{
		debug("sql_log: Message too long or formatting error");
		return;
	}

	char safe_kind[32];
	char safe_ip[sizeof(ch->desc->host)];
	char safe_name[MAX_INPUT_LENGTH];
	sanitize_flat_log_field(kind, safe_kind, sizeof(safe_kind));
	sanitize_flat_log_field(ch->desc ? ch->desc->host : "", safe_ip, sizeof(safe_ip));
	sanitize_flat_log_field(GET_NAME(ch), safe_name, sizeof(safe_name));
	sanitize_flat_log_field(message, message, sizeof(message));

	int zone_number = NOWHERE;
	int room_vnum = NOWHERE;
	if (world && ch->in_room >= 0 && ch->in_room <= top_of_world)
	{
		room_vnum = world[ch->in_room].number;
		const int zone_rnum = world[ch->in_room].zone;
		if (zone_table && zone_rnum >= 0 && zone_rnum <= top_of_zone_table)
			zone_number = zone_table[zone_rnum].number;
	}

	const char *destination = LOG_PLAYER;
	if (!strcmp(kind, WIZLOG))
		destination = LOG_WIZ;
	else if (!strcmp(kind, EXPLOG))
		destination = LOG_EXP;

	logit(destination, "kind=%s ip=%s pid=%d player=%s zone=%d room=%d message=%s", safe_kind,
	      safe_ip, GET_PID(ch), safe_name, zone_number, room_vnum, message);
}

void sql_load_zones(void) {}
void sql_zones_refresh(void) {}
const std::vector<zone_info> &sql_zones(void)
{
	static const std::vector<zone_info> none;
	return none;
}
bool get_zone_info(int /*zone_number*/, struct zone_info * /*info*/)
{
	return FALSE;
}
void sql_set_zone_reset_perc(int /*zone_number*/, int /*reset_perc*/) {}

string escape_str(const char *str)
{
	return string(str);
}

string get_mud_info(const char *name)
{
	string contents, error;
	if (!name || !flatfile_information_read(".", name, &contents, &error))
	{
		// An absent page is the normal state of an optional one, such as "lock".
		if (error.starts_with("invalid information source"))
			logit(LOG_DEBUG, "get_mud_info: %s", error.c_str());
		return {};
	}
	return contents;
}

void sql_mud_info_reload(P_char ch, std::function<void(P_char)> done)
{
	done(ch);
}

void sql_mud_info_refresh(void) {}

void sql_update_bind_data(int vnum, int *owner_pid, int *timer)
{
	if (!owner_pid || !timer)
	{
		logit(LOG_DEBUG, "sql_update_bind_data: invalid input pointer");
		return;
	}
	std::string error;
	const auto updated = flatfile_artifact_bind_update(persistence_mode_flatfile_root(), vnum,
							   *owner_pid, *timer, &error);
	if (updated != flatfile_artifact_result::ok &&
	    updated != flatfile_artifact_result::unchanged)
		logit(LOG_DEBUG, "sql_update_bind_data: flat artifact update failed: %s",
		      error.empty() ? "invalid or missing artifact authority" : error.c_str());
}

bool sql_get_bind_data(int vnum, int *owner_pid, int *timer)
{
	if (owner_pid)
		*owner_pid = 0;
	if (timer)
		*timer = 0;
	if (!owner_pid || !timer)
	{
		logit(LOG_DEBUG, "sql_get_bind_data: invalid output pointer");
		return false;
	}
	int32_t flat_owner_pid = 0;
	int64_t flat_timer = 0;
	std::string error;
	const auto loaded = flatfile_artifact_bind_get(persistence_mode_flatfile_root(), vnum,
						       &flat_owner_pid, &flat_timer, &error);
	if (loaded != flatfile_artifact_result::ok || flat_timer > INT_MAX)
	{
		logit(LOG_DEBUG, "sql_get_bind_data: flat artifact lookup failed: %s",
		      error.empty() ? "invalid or missing artifact authority" : error.c_str());
		return false;
	}
	*owner_pid = flat_owner_pid;
	*timer = static_cast<int>(flat_timer);
	return true;
}

bool sql_pwipe(int code_verify)
{
	if (code_verify == 1723699)
	{
		logit(LOG_DEBUG,
		      "sql_pwipe: &=GlCan't wipe the SQL stuff as SQL database is not loaded.");
	}
	else
	{
		logit(LOG_DEBUG,
		      "sql_pwipe: &=GlSomeone called sql_pwipe with a bad verify code... hrm..");
	}
	return FALSE;
}
bool sql_pwipe_crossed_boundary(void)
{
	return false;
}
uint64_t sql_season_epoch(void)
{
	return 0;
}
bool sql_clear_zone_trophy()
{
	return FALSE;
}
void sql_game_loop_running(bool) {}
uint64_t sql_game_loop_query_count(void)
{
	return 0;
}
void sql_level_cap_reload(void) {}
#else

static void sql_resetConnectTimes(void);
static void sql_load_ip_activity(void);
static void sql_load_level_cap(void);
static void sql_load_recent_counts(void);
static void sql_load_mud_info(void);
static bool sql_verify_boot_database(void);

// The global database handler
MYSQL *DB;

static bool pwipe_crossed_boundary = false;
static uint64_t current_season_epoch = 0;

static bool sql_env_true(const char *name)
{
	const char *value = getenv(name);
	return value && !strcasecmp(value, "TRUE");
}

static bool sql_host_is_loopback(const char *host)
{
	return host && (!strcasecmp(host, "localhost") || !strcmp(host, "127.0.0.1") ||
			!strcmp(host, "::1"));
}

static bool sql_target_is_allowed(const char *host, const char *database)
{
	const char *allowed = getenv("DB_ALLOWED_TARGETS");
	if (!allowed || !*allowed || !host || !database)
		return false;

	char target[512];
	int written = snprintf(target, sizeof(target), "%s/%s", host, database);
	if (written < 0 || (size_t)written >= sizeof(target))
		return false;

	size_t target_len = (size_t)written;
	for (const char *start = allowed; *start;)
	{
		const char *end = strchr(start, ',');
		size_t len = end ? (size_t)(end - start) : strlen(start);
		if (len == target_len && !strncmp(start, target, len))
			return true;
		if (!end)
			break;
		start = end + 1;
	}
	return false;
}

/* The production role's plain-telnet port.  DURIS_PRODUCTION_PORT lets a second
 * production-role install share a host; unset keeps DFLT_PORT.  An invalid value
 * returns 0, which no running port matches. */
static int sql_production_port(void)
{
	const char *configured = getenv("DURIS_PRODUCTION_PORT");
	if (!configured || !*configured)
		return DFLT_PORT;

	errno = 0;
	char *end = NULL;
	long parsed = strtol(configured, &end, 10);
	if (errno == ERANGE || end == configured || *end || parsed < 1 || parsed > 65535)
		return 0;
	return (int)parsed;
}

static bool sql_runtime_config_valid(void)
{
	const char *role = getenv("ENVIRONMENT");
	if (!role || (strcmp(role, "local") && strcmp(role, "production")))
	{
		logit(LOG_STATUS,
		      "Database configuration rejected: ENVIRONMENT must be local or production");
		return false;
	}

	const char *required[] = { "DB_HOST", "DB_USER", "DB_PASSWD", "DB_NAME",
				   "DB_ALLOWED_TARGETS" };
	for (const char *name : required)
	{
		const char *value = getenv(name);
		if (!value || !*value)
		{
			logit(LOG_STATUS,
			      "Database configuration rejected: required field %s is missing",
			      name);
			return false;
		}
	}

	const char *port = getenv("DB_PORT");
	if (port && *port)
	{
		errno = 0;
		char *end = NULL;
		long parsed = strtol(port, &end, 10);
		if (errno == ERANGE || end == port || *end || parsed < 1 || parsed > 65535)
		{
			logit(LOG_STATUS, "Database configuration rejected: DB_PORT is invalid");
			return false;
		}
	}

	const int production_port = sql_production_port();
	if (!production_port)
	{
		logit(LOG_STATUS,
		      "Database configuration rejected: DURIS_PRODUCTION_PORT is invalid");
		return false;
	}

	if (!strcmp(role, "production") && RUNNING_PORT != production_port)
	{
		logit(LOG_STATUS,
		      "Database configuration rejected: production role requires the production port");
		return false;
	}

	const char *database = sql_persistence_db_name();
	if (!sql_target_is_allowed(DB_HOST, database))
	{
		logit(LOG_STATUS,
		      "Database configuration rejected: resolved target is not allow-listed");
		return false;
	}

	const char *socket_path = getenv("DB_SOCKET");
	bool protected_local = sql_host_is_loopback(DB_HOST) || (socket_path && *socket_path);
	if (socket_path && *socket_path &&
	    (!sql_host_is_loopback(DB_HOST) || strcmp(role, "local")))
	{
		logit(LOG_STATUS, "Database configuration rejected: DB_SOCKET is local-mode only");
		return false;
	}
	if (RUNTIME_DB_REMOTE_TLS_REQUIRED && !protected_local)
	{
		const char *ca = getenv("DB_SSL_CA");
		struct stat ca_stat;
		if (!sql_env_true("DB_TLS") || !ca || !*ca || stat(ca, &ca_stat) ||
		    !S_ISREG(ca_stat.st_mode))
		{
			logit(LOG_STATUS,
			      "Database configuration rejected: remote transport requires TLS and a CA file");
			return false;
		}
	}
	return true;
}

static bool sql_connection_execute(MYSQL *conn, const char *statement)
{
	if (mysql_real_query(conn, statement, strlen(statement)))
		return false;
	MYSQL_RES *result = mysql_store_result(conn);
	if (result)
		mysql_free_result(result);
	return mysql_next_result(conn) == -1;
}

static bool sql_connection_execute_affected(MYSQL *conn, const char *statement,
					    my_ulonglong *affected)
{
	if (!affected || mysql_real_query(conn, statement, strlen(statement)))
		return false;
	MYSQL_RES *result = mysql_store_result(conn);
	if (result)
		mysql_free_result(result);
	*affected = mysql_affected_rows(conn);
	return *affected != (my_ulonglong)-1 && mysql_next_result(conn) == -1;
}

static bool sql_load_active_season_state(void)
{
	MYSQL_RES *result = db_query(
		"SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1");
	if (!result)
		return false;
	MYSQL_ROW row = mysql_fetch_row(result);
	char *end = NULL;
	errno = 0;
	unsigned long long epoch = row && row[0] ? strtoull(row[0], &end, 10) : 0;
	const bool ready = row && row[0] && end && !*end && !errno && epoch > 0 && row[1] &&
			   !strcmp(row[1], "active") && mysql_fetch_row(result) == NULL;
	mysql_free_result(result);
	if (!ready)
		return false;
	current_season_epoch = epoch;
	return true;
}

static bool sql_begin_pwipe_epoch(void)
{
	pwipe_crossed_boundary = false;
	if (!DB || !sql_connection_execute(DB, "START TRANSACTION"))
		return false;
	MYSQL_RES *result = db_query(
		"SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1 FOR UPDATE");
	MYSQL_ROW row = result ? mysql_fetch_row(result) : NULL;
	char *end = NULL;
	errno = 0;
	unsigned long long epoch = row && row[0] ? strtoull(row[0], &end, 10) : 0;
	const bool active = row && row[0] && end && !*end && !errno && epoch > 0 &&
			    epoch < ULLONG_MAX && row[1] && !strcmp(row[1], "active") &&
			    mysql_fetch_row(result) == NULL;
	if (result)
		mysql_free_result(result);
	if (!active)
	{
		sql_connection_execute(DB, "ROLLBACK");
		return false;
	}
	char update[384];
	snprintf(update, sizeof update,
		 "UPDATE season_reset_state SET season_epoch=%llu,reset_status='resetting',"
		 "reset_started_at=UTC_TIMESTAMP(6),reset_completed_at=NULL "
		 "WHERE state_id=1 AND season_epoch=%llu AND reset_status='active'",
		 epoch + 1, epoch);
	my_ulonglong affected = 0;
	if (!sql_connection_execute_affected(DB, update, &affected) || affected != 1)
	{
		sql_connection_execute(DB, "ROLLBACK");
		return false;
	}
	/* The update succeeded; a failed COMMIT can now have an ambiguous outcome. */
	pwipe_crossed_boundary = true;
	if (!sql_connection_execute(DB, "COMMIT"))
		return false;
	current_season_epoch = epoch + 1;
	return true;
}

static bool sql_complete_pwipe_epoch(void)
{
	if (!DB || !current_season_epoch)
		return false;
	char update[320];
	snprintf(update, sizeof update,
		 "UPDATE season_reset_state SET reset_status='active',"
		 "reset_completed_at=UTC_TIMESTAMP(6) WHERE state_id=1 AND season_epoch=%llu "
		 "AND reset_status='resetting'",
		 (unsigned long long)current_season_epoch);
	my_ulonglong affected = 0;
	return sql_connection_execute_affected(DB, update, &affected) && affected == 1;
}

bool sql_pwipe_crossed_boundary(void)
{
	return pwipe_crossed_boundary;
}

uint64_t sql_season_epoch(void)
{
	return current_season_epoch;
}

static bool sql_mode_has(const char *mode, const char *required)
{
	if (!mode || !required)
		return false;
	size_t required_len = strlen(required);
	for (const char *start = mode; *start;)
	{
		const char *end = strchr(start, ',');
		size_t len = end ? (size_t)(end - start) : strlen(start);
		if (len == required_len && !strncmp(start, required, len))
			return true;
		if (!end)
			break;
		start = end + 1;
	}
	return false;
}

static bool sql_verify_session_contract(MYSQL *conn)
{
	const char *verify = "SELECT @@character_set_connection,@@time_zone,@@sql_mode";
	if (mysql_real_query(conn, verify, strlen(verify)))
		return false;
	MYSQL_RES *result = mysql_store_result(conn);
	MYSQL_ROW row = result ? mysql_fetch_row(result) : NULL;
	bool valid = row && row[0] && !strcmp(row[0], RUNTIME_DB_CHARACTER_SET) && row[1] &&
		     !strcmp(row[1], RUNTIME_DB_TIME_ZONE) && row[2] &&
		     sql_mode_has(row[2], "STRICT_TRANS_TABLES") &&
		     sql_mode_has(row[2], "ERROR_FOR_DIVISION_BY_ZERO") &&
		     sql_mode_has(row[2], "NO_ENGINE_SUBSTITUTION");
	if (result)
		mysql_free_result(result);
	if (!valid)
		return false;

	const char *server = mysql_get_server_info(conn);
	if (!server)
		return false;
	if (strstr(server, "MariaDB"))
	{
		const char *checks = "SELECT @@SESSION.check_constraint_checks";
		if (mysql_real_query(conn, checks, strlen(checks)))
			return false;
		result = mysql_store_result(conn);
		row = result ? mysql_fetch_row(result) : NULL;
		valid = row && row[0] && !strcmp(row[0], "1");
		if (result)
			mysql_free_result(result);
		if (!valid)
			return false;
	}

	const char *isolation_queries[] = { "SELECT @@transaction_isolation",
					    "SELECT @@tx_isolation" };
	for (const char *query : isolation_queries)
	{
		if (mysql_real_query(conn, query, strlen(query)))
			continue;
		result = mysql_store_result(conn);
		row = result ? mysql_fetch_row(result) : NULL;
		valid = row && row[0] && !strcasecmp(row[0], RUNTIME_DB_ISOLATION);
		if (result)
			mysql_free_result(result);
		if (valid)
			return true;
	}
	return false;
}

static bool sql_apply_session_contract(MYSQL *conn)
{
	if (mysql_set_character_set(conn, RUNTIME_DB_CHARACTER_SET))
		return false;
	std::string sql_mode_statement =
		"SET SESSION sql_mode='" + std::string(RUNTIME_DB_SQL_MODE) + "'";
	const char *statements[] = { "SET SESSION time_zone='+00:00'",
				     "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED",
				     sql_mode_statement.c_str() };
	for (const char *statement : statements)
		if (!sql_connection_execute(conn, statement))
			return false;
	const char *server = mysql_get_server_info(conn);
	if (!server || (strstr(server, "MariaDB") &&
			!sql_connection_execute(conn, "SET SESSION check_constraint_checks=1")))
		return false;
	return sql_verify_session_contract(conn);
}

static MYSQL *sql_open_verified_connection(unsigned long client_flags, const char *user,
					   const char *password, unsigned int timeout)
{
	if (!sql_runtime_config_valid() || !user || !*user || !password || !*password)
		return NULL;

	MYSQL *conn = mysql_init(NULL);
	if (!conn)
		return NULL;
	std::unique_ptr<MYSQL, decltype(&mysql_close)> owned(conn, mysql_close);
	try
	{
		bool options_failed = mysql_options(conn, MYSQL_OPT_CONNECT_TIMEOUT, &timeout) ||
				      mysql_options(conn, MYSQL_OPT_READ_TIMEOUT, &timeout) ||
				      mysql_options(conn, MYSQL_OPT_WRITE_TIMEOUT, &timeout);
		/* MySQL defaults automatic reconnect off and emits a deprecation warning even
	 * when MYSQL_OPT_RECONNECT is explicitly set to false. MariaDB still supports
	 * the option without that warning, so preserve the explicit setting there. */
#if defined(MARIADB_BASE_VERSION) || defined(MARIADB_PACKAGE_VERSION)
		bool reconnect = false;
		options_failed = options_failed ||
				 mysql_options(conn, MYSQL_OPT_RECONNECT, &reconnect);
#endif
		options_failed = options_failed || mysql_options(conn, MYSQL_SET_CHARSET_NAME,
								 RUNTIME_DB_CHARACTER_SET);
		if (options_failed)
		{
			return NULL;
		}

		const char *socket_path = getenv("DB_SOCKET");
		bool protected_local = sql_host_is_loopback(DB_HOST) ||
				       (socket_path && *socket_path);
		if (RUNTIME_DB_REMOTE_TLS_REQUIRED && !protected_local)
		{
			const char *ca = getenv("DB_SSL_CA");
			/* Both arms demand the same thing: TLS is mandatory, the server
		 * certificate must chain to the CA, and the name on it must match the
		 * host we asked for.  MySQL deprecated MYSQL_OPT_SSL_ENFORCE and
		 * MYSQL_OPT_SSL_VERIFY_SERVER_CERT in 5.7 and removed them in 8.0,
		 * folding both into MYSQL_OPT_SSL_MODE; MariaDB Connector/C ships only
		 * the original pair.  Build against either without weakening the
		 * requirement -- a downgrade here is silent until someone is on the
		 * wrong end of it. */
#if defined(MARIADB_BASE_VERSION) || defined(MARIADB_PACKAGE_VERSION)
			bool enabled = true;
			if (mysql_options(conn, MYSQL_OPT_SSL_ENFORCE, &enabled) ||
			    mysql_options(conn, MYSQL_OPT_SSL_VERIFY_SERVER_CERT, &enabled) ||
			    mysql_options(conn, MYSQL_OPT_SSL_CA, ca))
#else
			unsigned int ssl_mode = SSL_MODE_VERIFY_IDENTITY;
			if (mysql_options(conn, MYSQL_OPT_SSL_MODE, &ssl_mode) ||
			    mysql_options(conn, MYSQL_OPT_SSL_CA, ca))
#endif
			{
				return NULL;
			}
			client_flags |= CLIENT_SSL;
		}

		if (!mysql_real_connect(conn, DB_HOST, user, password, sql_persistence_db_name(),
					DB_PORT, socket_path && *socket_path ? socket_path : NULL,
					client_flags))
		{
			logit(LOG_STATUS, "Database connection failed error_code=%u sqlstate=%.5s",
			      (unsigned int)mysql_errno(conn), mysql_sqlstate(conn));
			return NULL;
		}
		// Every SQL socket must close on successful copyover exec, not just
		// telemetry sockets. Otherwise the inherited main connection retains
		// the runtime exclusion lock and rejects the replacement process.
		if (!sql_telemetry_set_cloexec(conn))
		{
			logit(LOG_STATUS,
			      "Database connection rejected: close-on-exec setup failed");
			return NULL;
		}
		if ((!protected_local && !mysql_get_ssl_cipher(conn)) ||
		    !sql_apply_session_contract(conn))
		{
			logit(LOG_STATUS,
			      "Database connection rejected: transport or session contract failed");
			return NULL;
		}
		if (!duris_sql_exclusion_guard_allows(conn))
		{
			logit(LOG_STATUS,
			      "Database connection rejected: runtime exclusion guard is not owned");
			return NULL;
		}
		return owned.release();
	}
	catch (...)
	{
		return NULL;
	}
}

MYSQL *sql_open_configured_connection(unsigned long client_flags)
{
	return sql_open_verified_connection(client_flags, DB_USER, DB_PASSWD,
					    RUNTIME_DB_TIMEOUT_SECONDS);
}

MYSQL *sql_open_telemetry_connection(void)
{
	/* No credential fallback or alternate target; never consult DB/sql_pool. */
	MYSQL *conn = sql_open_verified_connection(0, getenv("TELEMETRY_DB_USER"),
						   getenv("TELEMETRY_DB_PASSWD"), 2U);
	if (!conn)
		return NULL;
	// Copyover exec must release this producer's advisory writer lock. An
	// inherited SQL socket would keep the old connection (and lock) alive,
	// preventing the replacement telemetry worker from opening its writer.
	if (!sql_telemetry_set_cloexec(conn) ||
	    !sql_connection_execute(conn, "SET SESSION innodb_lock_wait_timeout=2"))
	{
		mysql_close(conn);
		return NULL;
	}
	return conn;
}

/* Escapes a string. */
char *mysql_str(const char *str, char *buf)
{
	mysql_real_escape_string(DB, buf, str, strlen(str));
	return buf;
}

string escape_str(const char *str)
{
	size_t len;
	string escaped;
	unsigned long escaped_len;

	if (!str || !DB)
		return string();

	len = strlen(str);
	if (len > (string().max_size() - 1) / 2)
		return string();

	/* mysql_real_escape_string() can expand every input byte and needs
	 * one additional byte for the terminator.  Keep the storage owned by
	 * this call so concurrent persistence workers cannot overwrite it. */
	escaped.assign(len * 2 + 1, '\0');
	escaped_len = mysql_real_escape_string(DB, &escaped[0], str, len);
	escaped.resize(escaped_len);
	return escaped;
}

static void lookup_append(std::string *output, const std::string &value)
{
	uint64_t size = value.size();
	for (int shift = 56; shift >= 0; shift -= 8)
		output->push_back((char)((size >> shift) & 0xff));
	output->append(value);
}

static std::string lookup_escape(const char *value)
{
	if (!value)
		value = "";
	std::string escaped(strlen(value) * 2 + 1, '\0');
	unsigned long length = mysql_real_escape_string(DB, &escaped[0], value, strlen(value));
	escaped.resize(length);
	return escaped;
}

static bool lookup_checksum(const std::string &canonical, char *encoded, size_t size)
{
	if (size < SHA256_DIGEST_LENGTH * 2 + 1)
		return false;
	unsigned char digest[SHA256_DIGEST_LENGTH];
	if (!SHA256((const unsigned char *)canonical.data(), canonical.size(), digest))
		return false;
	for (size_t i = 0; i < SHA256_DIGEST_LENGTH; ++i)
		snprintf(encoded + i * 2, 3, "%02x", digest[i]);
	encoded[SHA256_DIGEST_LENGTH * 2] = '\0';
	return true;
}

static bool lookup_rows_match(const char *checksum, size_t race_count, size_t class_count)
{
	const char *queries[] = { "SELECT id,name,COALESCE(short_name,''),COALESCE(ansi_name,''),"
				  "COALESCE(abbrev,''),racewar,playable FROM races ORDER BY id",
				  "SELECT id,name,COALESCE(ansi_name,''),COALESCE(short_name,''),"
				  "COALESCE(menu_char,'') FROM classes ORDER BY id" };
	const size_t widths[] = { 7, 5 };
	const char *tags[] = { "race", "class" };
	const size_t expected[] = { race_count, class_count };
	std::string canonical;
	for (size_t query_index = 0; query_index < 2; ++query_index)
	{
		if (mysql_real_query(DB, queries[query_index], strlen(queries[query_index])))
			return false;
		MYSQL_RES *result = mysql_store_result(DB);
		if (!result || mysql_num_fields(result) != widths[query_index] ||
		    mysql_num_rows(result) != expected[query_index])
		{
			if (result)
				mysql_free_result(result);
			return false;
		}
		MYSQL_ROW row;
		while ((row = mysql_fetch_row(result)) != NULL)
		{
			lookup_append(&canonical, tags[query_index]);
			for (size_t column = 0; column < widths[query_index]; ++column)
			{
				if (!row[column])
				{
					mysql_free_result(result);
					return false;
				}
				lookup_append(&canonical, row[column]);
			}
		}
		mysql_free_result(result);
	}
	char actual[SHA256_DIGEST_LENGTH * 2 + 1];
	return lookup_checksum(canonical, actual, sizeof actual) && !strcmp(actual, checksum);
}

static bool lookup_state_matches(const char *checksum, size_t race_count, size_t class_count)
{
	char query[256];
	snprintf(query, sizeof query,
		 "SELECT dataset_version,LOWER(HEX(dataset_checksum)),race_count,class_count "
		 "FROM lookup_dataset_state WHERE dataset_name='%s'",
		 LOOKUP_DATASET_NAME);
	if (mysql_real_query(DB, query, strlen(query)))
		return false;
	MYSQL_RES *result = mysql_store_result(DB);
	MYSQL_ROW row = result ? mysql_fetch_row(result) : NULL;
	bool matches = row && row[0] && atoi(row[0]) == (int)LOOKUP_DATASET_VERSION && row[1] &&
		       !strcmp(row[1], checksum) && row[2] &&
		       strtoul(row[2], NULL, 10) == race_count && row[3] &&
		       strtoul(row[3], NULL, 10) == class_count;
	if (result)
		mysql_free_result(result);
	return matches;
}

static std::string lookup_id_list(const std::vector<int> &ids)
{
	std::string list;
	for (int id : ids)
	{
		if (!list.empty())
			list += ',';
		list += std::to_string(id);
	}
	return list;
}

/* Publish the compiled race/class dataset atomically. Unchanged boots do no writes. */
bool sql_populate_lookup_tables()
{
	std::vector<std::string> race_sql, class_sql;
	std::vector<int> race_ids, class_ids;
	std::string canonical;

	for (int i = 0; i <= LAST_RACE; ++i)
	{
		if (!race_names_table[i].normal || !race_names_table[i].normal[0])
			continue;
		int racewar = 0, playable = 0;
		for (int j = 0; playable_races[j].race_id >= 0; ++j)
			if (playable_races[j].race_id == i)
			{
				playable = 1;
				if (!strcmp(playable_races[j].faction, "good"))
					racewar = RACEWAR_GOOD;
				else if (!strcmp(playable_races[j].faction, "evil"))
					racewar = RACEWAR_EVIL;
				else if (!strcmp(playable_races[j].faction, "undead"))
					racewar = RACEWAR_UNDEAD;
				else if (!strcmp(playable_races[j].faction, "neutral"))
					racewar = RACEWAR_NEUTRAL;
				break;
			}
		const char *raw[] = { race_names_table[i].normal,
				      race_names_table[i].no_spaces ?
					      race_names_table[i].no_spaces :
					      "",
				      race_names_table[i].ansi ? race_names_table[i].ansi : "",
				      race_names_table[i].code ? race_names_table[i].code : "" };
		lookup_append(&canonical, "race");
		lookup_append(&canonical, std::to_string(i));
		for (const char *value : raw)
			lookup_append(&canonical, value);
		lookup_append(&canonical, std::to_string(racewar));
		lookup_append(&canonical, std::to_string(playable));
		race_ids.push_back(i);
		race_sql.push_back(
			"INSERT INTO races(id,name,short_name,ansi_name,abbrev,racewar,playable) VALUES(" +
			std::to_string(i) + ",'" + lookup_escape(raw[0]) + "','" +
			lookup_escape(raw[1]) + "','" + lookup_escape(raw[2]) + "','" +
			lookup_escape(raw[3]) + "'," + std::to_string(racewar) + "," +
			std::to_string(playable) +
			") ON DUPLICATE KEY UPDATE name=VALUES(name),"
			"short_name=VALUES(short_name),ansi_name=VALUES(ansi_name),abbrev=VALUES(abbrev),"
			"racewar=VALUES(racewar),playable=VALUES(playable)");
	}

	for (int i = 0; i <= CLASS_COUNT; ++i)
	{
		if (!class_names_table[i].normal || !class_names_table[i].normal[0])
			continue;
		const char *raw[] = { class_names_table[i].normal,
				      class_names_table[i].ansi ? class_names_table[i].ansi : "",
				      class_names_table[i].code ? class_names_table[i].code : "" };
		char letter[] = { class_names_table[i].letter, '\0' };
		lookup_append(&canonical, "class");
		lookup_append(&canonical, std::to_string(i));
		for (const char *value : raw)
			lookup_append(&canonical, value);
		lookup_append(&canonical, letter);
		class_ids.push_back(i);
		class_sql.push_back(
			"INSERT INTO classes(id,name,ansi_name,short_name,menu_char) VALUES(" +
			std::to_string(i) + ",'" + lookup_escape(raw[0]) + "','" +
			lookup_escape(raw[1]) + "','" + lookup_escape(raw[2]) + "','" +
			lookup_escape(letter) +
			"') ON DUPLICATE KEY UPDATE name=VALUES(name),"
			"ansi_name=VALUES(ansi_name),short_name=VALUES(short_name),"
			"menu_char=VALUES(menu_char)");
	}

	char checksum[SHA256_DIGEST_LENGTH * 2 + 1];
	if (!lookup_checksum(canonical, checksum, sizeof checksum))
		return false;

	if (lookup_state_matches(checksum, race_sql.size(), class_sql.size()) &&
	    lookup_rows_match(checksum, race_sql.size(), class_sql.size()))
	{
		logit(LOG_STATUS, "Lookup dataset unchanged; publication skipped.");
		return true;
	}

	if (!sql_connection_execute(DB, "START TRANSACTION"))
		return false;
	auto rollback = []()
	{
		sql_connection_execute(DB, "ROLLBACK");
		return false;
	};
	for (const std::string &query : race_sql)
		if (!sql_connection_execute(DB, query.c_str()))
			return rollback();
	for (const std::string &query : class_sql)
		if (!sql_connection_execute(DB, query.c_str()))
			return rollback();
	std::string delete_races =
		"DELETE FROM races WHERE id NOT IN (" + lookup_id_list(race_ids) + ")";
	std::string delete_classes =
		"DELETE FROM classes WHERE id NOT IN (" + lookup_id_list(class_ids) + ")";
	if (!sql_connection_execute(DB, delete_races.c_str()) ||
	    !sql_connection_execute(DB, delete_classes.c_str()))
		return rollback();
	if (!lookup_rows_match(checksum, race_sql.size(), class_sql.size()))
		return rollback();
	std::string state =
		"INSERT INTO lookup_dataset_state(dataset_name,dataset_version,dataset_checksum,"
		"race_count,class_count) VALUES('" +
		std::string(LOOKUP_DATASET_NAME) + "'," + std::to_string(LOOKUP_DATASET_VERSION) +
		",UNHEX('" + checksum + "')," + std::to_string(race_sql.size()) + "," +
		std::to_string(class_sql.size()) +
		") ON DUPLICATE KEY UPDATE dataset_version=VALUES(dataset_version),"
		"dataset_checksum=VALUES(dataset_checksum),race_count=VALUES(race_count),"
		"class_count=VALUES(class_count)";
	if (!sql_connection_execute(DB, state.c_str()) || !sql_connection_execute(DB, "COMMIT"))
		return rollback();
	logit(LOG_STATUS, "Lookup dataset published atomically.");
	return true;
}

/* Resolve the requested database while retaining the non-default-port
 * production safety guard.  Explicit disposable/test database names must
 * remain usable on any port; only an implicit production target is redirected
 * to the development sandbox. */
const char *sql_persistence_db_name(void)
{
	const bool production_name = !strcmp(DB_NAME, "duris") || !strcmp(DB_NAME, "duris_prod");

	if (RUNNING_PORT != sql_production_port() && production_name)
		return "duris_dev";
	return DB_NAME;
}

/* Open a connection to the database. The connection will remain open
 * throughout the mud session. */
int initialize_mysql()
{
	logit(LOG_STATUS, "Initializing validated MySQL connection.");
	DB = sql_open_configured_connection(CLIENT_MULTI_STATEMENTS);
	if (!DB)
	{
		return -1;
	}
	// This connection holds the runtime lock and the game thread issues no query on it
	// after boot. MariaDB closes a connection idle past wait_timeout (8 hours by
	// default), which would release the lock and stop every write; 31536000 seconds is
	// the most it takes.
	if (!sql_connection_execute(DB, "SET SESSION wait_timeout=31536000"))
	{
		logit(LOG_STATUS,
		      "FATAL: could not keep the main database connection open; aborting boot");
		mysql_close(DB);
		DB = NULL;
		return -1;
	}
	if (!duris_sql_exclusion_guard_acquire(DB))
	{
		logit(LOG_STATUS,
		      "FATAL: database runtime exclusion guard is held by another session; aborting boot");
		mysql_close(DB);
		DB = NULL;
		return -1;
	}

	logit(LOG_STATUS, "Connection established.");

	sql_resetConnectTimes();
	sql_load_ip_activity();
	sql_load_level_cap();
	sql_load_recent_counts();
	sql_load_mud_info();
	sql_load_zones();

	if (!sql_verify_boot_database())
	{
		logit(LOG_STATUS,
		      "FATAL: required database connection/schema check failed, aborting boot");
		if (DB)
		{
			duris_sql_exclusion_guard_release();
			mysql_close(DB);
			DB = NULL;
		}
		return -1;
	}
	if (!sql_player_names_load() || !account_rewards_load() || !sql_player_recipes_load() ||
	    !artifacts_load() || !polls_load() || !sql_spellbooks_load() || !whitelist_load())
	{
		logit(LOG_STATUS,
		      "FATAL: the character names, account rewards, recipes, artifacts, "
		      "polls, spellbooks or multiplay whitelist could not be read, "
		      "aborting boot");
		duris_sql_exclusion_guard_release();
		mysql_close(DB);
		DB = NULL;
		return -1;
	}
	if (!sql_load_active_season_state())
	{
		logit(LOG_STATUS,
		      "FATAL: season reset state is missing, invalid, or not active; recovery is required");
		duris_sql_exclusion_guard_release();
		mysql_close(DB);
		DB = NULL;
		return -1;
	}
	if (!sql_populate_lookup_tables())
	{
		logit(LOG_STATUS,
		      "FATAL: COMPAT-E007 lookup dataset publication failed or commit outcome is ambiguous");
		duris_sql_exclusion_guard_release();
		mysql_close(DB);
		DB = NULL;
		return -1;
	}
	if (!item_uid_allocator_reserve(DB, ITEM_UID_BOOT_RESERVATION))
	{
		logit(LOG_STATUS,
		      "FATAL: could not reserve a collision-free item UID range at boot");
		duris_sql_exclusion_guard_release();
		mysql_close(DB);
		DB = NULL;
		return -1;
	}

	/* Initialise the connection pool for async persistence
	 * workers (item, scalar, large-payload event queues). */
	if (sql_pool_init(SQL_POOL_DEFAULT_SIZE) != 0)
	{
		logit(LOG_STATUS,
		      "Warning: connection pool init failed -- persistence workers will use sync fallback.");
		/* Non-fatal: the main DB connection still works. */
	}

	return 1;
}

void shutdown_mysql(void)
{
	sql_pool_shutdown();
	if (DB)
	{
		duris_sql_exclusion_guard_release();
		mysql_close(DB);
		DB = NULL;
	}
}

/* Handle a query, log possible errors and return results (if available) */
MYSQL_RES *db_query_at(struct persistence_query_site site, const char *format, ...)
{
	va_list args;
	int needed;
	char *buf;
	MYSQL_RES *res;

	va_start(args, format);
	needed = vsnprintf(NULL, 0, format, args);
	va_end(args);
	if (needed < 0)
	{
		logit(LOG_DEBUG, "MySQL: Query formatting error");
		return NULL;
	}

	buf = (char *)malloc((size_t)needed + 1);
	if (!buf)
		return NULL;

	va_start(args, format);
	vsnprintf(buf, (size_t)needed + 1, format, args);
	va_end(args);

	if (!buf[0])
	{
		free(buf);
		return NULL;
	}

	if (!sql_trace_exec_at(site, "db_query", buf, strlen(buf), true, false))
	{
		free(buf);
		return NULL;
	}

	res = mysql_store_result(DB);
	free(buf);
	return res;
}

/* The next id table's AUTO_INCREMENT gives, or 0 when it cannot be read. InnoDB keeps it
 * past every id the table ever stored, deleted rows included, so an allocator seeded from
 * it never gives a deleted row's id out again. */
unsigned long long sql_next_auto_increment(const char *table)
{
	MYSQL_RES *result = db_query("SELECT AUTO_INCREMENT FROM information_schema.TABLES "
				     "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s'",
				     table);
	if (!result)
		return 0;
	MYSQL_ROW row = mysql_fetch_row(result);
	const unsigned long long next = row && row[0] ? strtoull(row[0], NULL, 10) : 0;
	mysql_free_result(result);
	return next;
}

/* Fail boot unless the database schema and required authority baselines are ready. */
static bool sql_verify_boot_database(void)
{
	if (!DB)
	{
		logit(LOG_STATUS, "FATAL: database connection is not initialized at boot.");
		return false;
	}

	MYSQL_RES *result = db_query(
		"SELECT "
		"(SELECT COUNT(*) FROM mud_schema_baselines WHERE baseline_id='%s' AND "
		"LOWER(HEX(schema_fingerprint))='%s' AND manifest_version=%u AND runner_version=1),"
		"(SELECT COUNT(*) FROM mud_schema_history WHERE migration_id='%s' AND "
		"sequence_number=%u AND LOWER(HEX(apply_checksum))='%s' AND "
		"LOWER(HEX(verify_checksum))='%s' AND runner_version=1),"
		"(SELECT COUNT(*) FROM mud_schema_migration_state WHERE state_id=1 AND "
		"applied_count=%u AND LOWER(HEX(history_checksum))='%s'),"
		"(SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() "
		"AND table_type='BASE TABLE' AND table_name IN (%s)),"
		"(SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() "
		"AND table_type='BASE TABLE' AND engine='InnoDB' AND "
		"table_collation='utf8mb4_unicode_ci' AND table_name IN (%s))",
		RUNTIME_BASELINE_ID, RUNTIME_BASELINE_FINGERPRINT,
		RUNTIME_COMPATIBILITY_MANIFEST_VERSION, RUNTIME_MIGRATION_HEAD_ID,
		RUNTIME_MIGRATION_HEAD_SEQUENCE, RUNTIME_MIGRATION_APPLY_CHECKSUM,
		RUNTIME_MIGRATION_VERIFY_CHECKSUM, RUNTIME_MIGRATION_HEAD_SEQUENCE,
		RUNTIME_MIGRATION_HISTORY_CHECKSUM, RUNTIME_TABLE_SQL_LIST, RUNTIME_TABLE_SQL_LIST);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: COMPAT-E001 compatibility metadata query failed");
		return false;
	}
	MYSQL_ROW row = mysql_fetch_row(result);
	unsigned long *lengths = row ? mysql_fetch_lengths(result) : NULL;
	bool compatibility_ok = row && lengths && row[0] && atoi(row[0]) == 1 && row[1] &&
				atoi(row[1]) == 1 && row[2] && atoi(row[2]) == 1 && row[3] &&
				atoi(row[3]) == (int)RUNTIME_CURRENT_TABLE_COUNT && row[4] &&
				atoi(row[4]) == (int)RUNTIME_CURRENT_TABLE_COUNT;
	mysql_free_result(result);
	if (!compatibility_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: COMPAT-E002 migration, table, engine, or collation identity mismatch expected_baseline=%s expected_head=%s expected_tables=%u",
		      RUNTIME_BASELINE_ID, RUNTIME_MIGRATION_HEAD_ID, RUNTIME_CURRENT_TABLE_COUNT);
		return false;
	}
	if (!sql_verify_metadata_fingerprint())
	{
		logit(LOG_STATUS,
		      "FATAL: COMPAT-E003 normalized table/column/index/foreign-key fingerprint mismatch");
		return false;
	}

	const char *probe = "SELECT 1 FROM accounts LIMIT 1";
	if (!sql_trace_exec("boot/accounts_probe", probe, strlen(probe), true, false))
	{
		logit(LOG_STATUS,
		      "FATAL: required accounts table is missing or unreadable at boot");
		return false;
	}

	result = mysql_store_result(DB);
	if (result)
		mysql_free_result(result);

	const char *player_revision_probe =
		"SELECT COUNT(*) FROM information_schema.columns "
		"WHERE table_schema=DATABASE() AND table_name='player_data' AND "
		"column_name='save_revision' AND data_type='bigint' AND "
		"column_type LIKE '%unsigned' AND "
		"is_nullable='NO' AND column_default='0'";
	result = db_query("%s", player_revision_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: player save revision schema query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool player_revision_ok = row && lengths && row[0] && atoi(row[0]) == 1;
	mysql_free_result(result);
	if (!player_revision_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: player save revision schema is missing or incompatible at boot");
		return false;
	}

	/* The asynchronous persistence workers require these tables and their
	 * idempotency/index contract.  Fail at boot rather than allowing a worker
	 * to silently divert every event to an unverified fallback path. */
	const char *event_schema_probe =
		"SELECT COUNT(*) FROM information_schema.columns "
		"WHERE table_schema=DATABASE() AND "
		"((table_name='persistence_item_events' AND column_name IN "
		"('id','ts_usec','event_type','item_uid','vnum','item','actor','actor_id','source','target','note','dedupe_key','created_at')) "
		"OR (table_name='persistence_scalar_events' AND column_name IN "
		"('id','event_type','event_key','boot_time','touched_at','zone_number','toucher_pid','group_size','epic_value','alignment_delta','dedupe_key','created_at')))";
	result = db_query("%s", event_schema_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: persistence event schema metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	bool event_columns_ok = row && lengths && row[0] && atoi(row[0]) == 25;
	mysql_free_result(result);
	if (!event_columns_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: persistence event schema is incomplete at boot (expected 25 required columns).");
		return false;
	}

	const char *event_index_probe =
		"SELECT COUNT(*) FROM (SELECT DISTINCT table_name, index_name "
		"FROM information_schema.statistics WHERE table_schema=DATABASE() AND "
		"((table_name='persistence_item_events' AND index_name IN "
		"('PRIMARY','idx_item_uid_ts','idx_event_type_created','uq_item_dedupe')) "
		"OR (table_name='persistence_scalar_events' AND index_name IN "
		"('PRIMARY','idx_scalar_event_key','idx_scalar_zone_time','uq_scalar_dedupe')))) "
		"AS required_indexes";
	result = db_query("%s", event_index_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: persistence event index metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	bool event_indexes_ok = row && lengths && row[0] && atoi(row[0]) == 8;
	mysql_free_result(result);
	if (!event_indexes_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: persistence event schema indexes are incomplete at boot (expected 8 entries).");
		return false;
	}

	/* Auction settlement uses explicit transactions and therefore requires
	 * transactional storage.  A legacy MyISAM table can make rollback appear
	 * to succeed while leaving pickup/refund state partially committed. */
	const char *auction_engine_probe =
		"SELECT COUNT(DISTINCT table_name) FROM information_schema.tables "
		"WHERE table_schema=DATABASE() AND engine='InnoDB' AND table_name IN "
		"('auction_bid_history','auction_item_pickups','auction_money_pickups','auctions')";
	result = db_query("%s", auction_engine_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: auction storage-engine metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	bool auction_engines_ok = row && lengths && row[0] && atoi(row[0]) == 4;
	mysql_free_result(result);
	if (!auction_engines_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: transactional auction tables are not all InnoDB at boot (expected 4).");
		return false;
	}

	const char *critical_schema_probe =
		"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
		"AND ((table_name='critical_operation_inbox' AND column_name IN "
		"('operation_id','command_hash','keys_hash','command_type','schema_version',"
		"'payload_version','status','result_code','durable_revision','result_payload',"
		"'created_at','committed_at')) OR (table_name='critical_test_state' AND "
		"column_name IN ('entity_type','entity_id','value','revision','updated_at')) OR "
		"(table_name='critical_outbox' AND column_name IN "
		"('outbox_id','operation_id','event_index','destination','event_type',"
		"'payload_version','payload','status','attempt_count','next_attempt_at',"
		"'created_at','delivered_at','dead_lettered_at','last_error_code')) OR "
		"(table_name='critical_outbox_delivery_dedupe' AND column_name IN "
		"('consumer_id','outbox_id','delivered_at')))";
	result = db_query("%s", critical_schema_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: critical command schema metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool critical_columns_ok = row && lengths && row[0] && atoi(row[0]) == 34;
	mysql_free_result(result);
	if (!critical_columns_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: critical command schema is incomplete at boot (expected 34 required columns).");
		return false;
	}
	const char *critical_index_probe =
		"SELECT COUNT(*) FROM (SELECT DISTINCT table_name,index_name FROM "
		"information_schema.statistics WHERE table_schema=DATABASE() AND "
		"((table_name='critical_operation_inbox' AND index_name IN "
		"('PRIMARY','idx_critical_inbox_status_created')) OR "
		"(table_name='critical_test_state' AND index_name='PRIMARY') OR "
		"(table_name='critical_outbox' AND index_name IN "
		"('PRIMARY','uq_critical_outbox_operation_event','idx_critical_outbox_claim',"
		"'idx_critical_outbox_age')) OR (table_name='critical_outbox_delivery_dedupe' "
		"AND index_name='PRIMARY'))) AS critical_required_indexes";
	result = db_query("%s", critical_index_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: critical command index metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool critical_indexes_ok = row && lengths && row[0] && atoi(row[0]) == 8;
	mysql_free_result(result);
	if (!critical_indexes_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: critical command indexes are incomplete at boot (expected 8 entries).");
		return false;
	}
	const char *epic_schema_probe =
		"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
		"AND ((table_name='player_data' AND column_name='epic_revision') OR "
		"(table_name='epic_balance_baseline' AND column_name IN "
		"('pid','opening_balance','opening_revision','captured_at')) OR "
		"(table_name='epic_ledger' AND column_name IN "
		"('operation_id','pid','delta','balance_after','epic_revision','reason_type',"
		"'reason_id','source_site','created_at')))";
	result = db_query("%s", epic_schema_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: epic ledger schema metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool epic_columns_ok = row && lengths && row[0] && atoi(row[0]) == 14;
	mysql_free_result(result);
	if (!epic_columns_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: epic ledger schema is incomplete at boot (expected 14 required columns).");
		return false;
	}
	const char *epic_index_probe =
		"SELECT COUNT(*) FROM (SELECT DISTINCT table_name,index_name FROM "
		"information_schema.statistics WHERE table_schema=DATABASE() AND "
		"((table_name='epic_balance_baseline' AND index_name='PRIMARY') OR "
		"(table_name='epic_ledger' AND index_name IN "
		"('PRIMARY','uq_epic_ledger_pid_revision','idx_epic_ledger_pid_created',"
		"'idx_epic_ledger_reason_created')))) AS epic_required_indexes";
	result = db_query("%s", epic_index_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: epic ledger index metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool epic_indexes_ok = row && lengths && row[0] && atoi(row[0]) == 5;
	mysql_free_result(result);
	if (!epic_indexes_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: epic ledger indexes are incomplete at boot (expected 5 entries).");
		return false;
	}
	const char *epic_baseline_coverage_probe =
		"SELECT COUNT(*) FROM player_data AS player LEFT JOIN epic_balance_baseline AS baseline "
		"ON baseline.pid=player.pid WHERE baseline.pid IS NULL";
	result = db_query("%s", epic_baseline_coverage_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: epic balance baseline coverage query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool epic_baseline_coverage_ok = row && lengths && row[0] && atoll(row[0]) == 0;
	mysql_free_result(result);
	if (!epic_baseline_coverage_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: epic balance baseline does not cover every player at boot.");
		return false;
	}
	const char *currency_schema_probe =
		"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
		"AND ((table_name='player_data' AND column_name='wallet_revision') OR "
		"(table_name='account_banks' AND column_name='bank_revision') OR "
		"(table_name='currency_wallet_baseline' AND column_name IN "
		"('pid','opening_copper','opening_silver','opening_gold','opening_platinum',"
		"'opening_revision','captured_at')) OR (table_name='currency_bank_baseline' AND "
		"column_name IN ('bank_id','opening_copper','opening_silver','opening_gold',"
		"'opening_platinum','opening_revision','captured_at')) OR "
		"(table_name='currency_ledger' AND column_name IN "
		"('operation_id','pid','bank_id','wallet_delta_copper','wallet_delta_silver',"
		"'wallet_delta_gold','wallet_delta_platinum','bank_delta_copper',"
		"'bank_delta_silver','bank_delta_gold','bank_delta_platinum',"
		"'wallet_after_copper','wallet_after_silver','wallet_after_gold',"
		"'wallet_after_platinum','bank_after_copper','bank_after_silver','bank_after_gold',"
		"'bank_after_platinum','wallet_revision','bank_revision','reason_type','reason_id',"
		"'source_site','created_at')))";
	result = db_query("%s", currency_schema_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: currency ledger schema metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool currency_columns_ok = row && lengths && row[0] && atoi(row[0]) == 41;
	mysql_free_result(result);
	if (!currency_columns_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: currency ledger schema is incomplete at boot (expected 41 required columns).");
		return false;
	}
	const char *currency_index_probe =
		"SELECT COUNT(*) FROM (SELECT DISTINCT table_name,index_name FROM "
		"information_schema.statistics WHERE table_schema=DATABASE() AND "
		"((table_name='currency_wallet_baseline' AND index_name='PRIMARY') OR "
		"(table_name='currency_bank_baseline' AND index_name='PRIMARY') OR "
		"(table_name='currency_ledger' AND index_name IN "
		"('PRIMARY','uq_currency_wallet_revision','uq_currency_bank_revision',"
		"'idx_currency_pid_created','idx_currency_bank_created',"
		"'idx_currency_reason_created')))) AS currency_required_indexes";
	result = db_query("%s", currency_index_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: currency ledger index metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool currency_indexes_ok = row && lengths && row[0] && atoi(row[0]) == 8;
	mysql_free_result(result);
	if (!currency_indexes_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: currency ledger indexes are incomplete at boot (expected 8 entries).");
		return false;
	}
	const char *currency_wallet_baseline_coverage_probe =
		"SELECT COUNT(*) FROM player_data AS player LEFT JOIN currency_wallet_baseline AS "
		"baseline ON baseline.pid=player.pid WHERE baseline.pid IS NULL";
	result = db_query("%s", currency_wallet_baseline_coverage_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: currency wallet baseline coverage query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool currency_wallet_coverage_ok = row && lengths && row[0] && atoll(row[0]) == 0;
	mysql_free_result(result);
	if (!currency_wallet_coverage_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: currency wallet baseline does not cover every player at boot.");
		return false;
	}
	const char *currency_bank_baseline_coverage_probe =
		"SELECT COUNT(*) FROM account_banks AS bank LEFT JOIN currency_bank_baseline AS "
		"baseline ON baseline.bank_id=bank.id WHERE baseline.bank_id IS NULL";
	result = db_query("%s", currency_bank_baseline_coverage_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: currency bank baseline coverage query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool currency_bank_coverage_ok = row && lengths && row[0] && atoll(row[0]) == 0;
	mysql_free_result(result);
	if (!currency_bank_coverage_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: currency bank baseline does not cover every account bank at boot.");
		return false;
	}
	const char *character_baseline_readiness_probe =
		"SELECT COUNT(*),"
		"COALESCE(SUM(wallet.pid IS NULL),0),"
		"COALESCE(SUM(epic.pid IS NULL),0),"
		"COALESCE(SUM(combat.pid IS NULL),0) FROM ("
		"SELECT DISTINCT player.pid FROM player_data player "
		"JOIN account_characters mapping ON mapping.pid=player.pid "
		"WHERE player.active=1 AND mapping.deleted_at IS NULL AND mapping.blocked=0"
		") eligible "
		"LEFT JOIN currency_wallet_baseline wallet ON wallet.pid=eligible.pid "
		"LEFT JOIN epic_balance_baseline epic ON epic.pid=eligible.pid "
		"LEFT JOIN combat_frag_baseline combat ON combat.pid=eligible.pid";
	result = db_query("%s", character_baseline_readiness_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: character baseline readiness query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool character_baselines_ready = row && lengths && row[0] && row[1] && row[2] &&
					       row[3] && atoll(row[1]) == 0 && atoll(row[2]) == 0 &&
					       atoll(row[3]) == 0;
	if (!character_baselines_ready)
	{
		logit(LOG_STATUS,
		      "FATAL: active mapped character baseline readiness failed "
		      "(eligible=%lld wallet_missing=%lld epic_missing=%lld "
		      "combat_missing=%lld).",
		      row && row[0] ? atoll(row[0]) : -1, row && row[1] ? atoll(row[1]) : -1,
		      row && row[2] ? atoll(row[2]) : -1, row && row[3] ? atoll(row[3]) : -1);
		mysql_free_result(result);
		return false;
	}
	mysql_free_result(result);
	const char *item_ownership_schema_probe =
		"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
		"AND ((table_name='item_uid_allocator' AND column_name IN "
		"('allocator_id','next_uid','updated_at')) OR (table_name='item_owner_revision' "
		"AND column_name IN ('owner_type','owner_id','owner_context_id','revision','updated_at')) "
		"OR (table_name='item_current_owner' AND column_name IN "
		"('item_uid','root_item_uid','parent_item_uid','owner_type','owner_id',"
		"'owner_context_id','item_revision','vnum','state','coin_payload','updated_at')) OR "
		"(table_name='item_ownership_baseline' AND column_name IN "
		"('item_uid','root_item_uid','parent_item_uid','owner_type','owner_id',"
		"'owner_context_id','opening_item_revision','vnum','source_table','source_row_id',"
		"'captured_at')) OR (table_name='item_ownership_quarantine' AND column_name IN "
		"('quarantine_id','item_uid','source_table','source_row_id','conflict_code','evidence',"
		"'detected_at','repaired_at')) OR (table_name='item_ownership_ledger' AND "
		"column_name IN ('operation_id','event_index','item_uid','root_item_uid',"
		"'parent_item_uid','from_owner_type','from_owner_id','from_owner_context_id',"
		"'to_owner_type','to_owner_id','to_owner_context_id','item_revision',"
		"'from_owner_revision','to_owner_revision','reason_type','reason_id','source_site',"
		"'created_at')))";
	result = db_query("%s", item_ownership_schema_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: item ownership schema metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool item_ownership_columns_ok = row && lengths && row[0] && atoi(row[0]) == 56;
	mysql_free_result(result);
	if (!item_ownership_columns_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: item ownership schema is incomplete at boot (expected 56 columns).");
		return false;
	}
	const char *item_ownership_index_probe =
		"SELECT COUNT(*) FROM (SELECT DISTINCT table_name,index_name FROM "
		"information_schema.statistics WHERE table_schema=DATABASE() AND ((table_name="
		"'item_uid_allocator' AND index_name='PRIMARY') OR (table_name='item_owner_revision' "
		"AND index_name IN ('PRIMARY','idx_item_owner_revision_updated')) OR (table_name="
		"'item_current_owner' AND index_name IN ('PRIMARY','idx_item_current_root_uid',"
		"'idx_item_current_owner','idx_item_current_parent')) OR (table_name="
		"'item_ownership_baseline' AND index_name IN ('PRIMARY','uq_item_baseline_source',"
		"'idx_item_baseline_owner')) OR (table_name='item_ownership_quarantine' AND index_name "
		"IN ('PRIMARY','uq_item_quarantine_evidence','idx_item_quarantine_open')) OR "
		"(table_name='item_ownership_ledger' AND index_name IN ('PRIMARY',"
		"'uq_item_ledger_item_revision','idx_item_ledger_item_created',"
		"'idx_item_ledger_from_owner','idx_item_ledger_to_owner')))) item_required_indexes";
	result = db_query("%s", item_ownership_index_probe);
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: item ownership index metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool item_ownership_indexes_ok = row && lengths && row[0] && atoi(row[0]) == 18;
	mysql_free_result(result);
	if (!item_ownership_indexes_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: item ownership indexes are incomplete at boot (expected 18).");
		return false;
	}
	const char *item_ownership_foreign_key_probe =
		"SELECT COUNT(*) FROM information_schema.referential_constraints WHERE "
		"constraint_schema=DATABASE() AND constraint_name IN "
		"('item_current_parent_fk','item_ownership_operation_fk') AND "
		"update_rule='RESTRICT' AND delete_rule='RESTRICT'";
	result = db_query("%s", item_ownership_foreign_key_probe);
	if (!result)
	{
		logit(LOG_STATUS,
		      "FATAL: item ownership foreign-key metadata query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool item_ownership_foreign_keys_ok = row && lengths && row[0] && atoi(row[0]) == 2;
	mysql_free_result(result);
	if (!item_ownership_foreign_keys_ok)
	{
		logit(LOG_STATUS,
		      "FATAL: item ownership restrictive foreign keys are incomplete at boot.");
		return false;
	}
	result = db_query(
		"SELECT COUNT(*) FROM item_uid_allocator WHERE allocator_id=1 AND next_uid>0");
	if (!result)
	{
		logit(LOG_STATUS, "FATAL: item UID allocator query failed at boot");
		return false;
	}
	row = mysql_fetch_row(result);
	lengths = row ? mysql_fetch_lengths(result) : NULL;
	const bool item_uid_allocator_ok = row && lengths && row[0] && atoi(row[0]) == 1;
	mysql_free_result(result);
	if (!item_uid_allocator_ok)
	{
		logit(LOG_STATUS, "FATAL: item UID allocator singleton is missing at boot");
		return false;
	}
	return true;
}

static bool sql_verify_metadata_fingerprint(void)
{
	std::string query =
		"SELECT CONCAT('T',CHAR(9),table_name,CHAR(9),engine,CHAR(9),table_collation) "
		"FROM information_schema.tables WHERE table_schema=DATABASE() AND "
		"table_type='BASE TABLE' AND table_name IN (";
	query += RUNTIME_TABLE_SQL_LIST;
	query +=
		") UNION ALL SELECT CONCAT('C',CHAR(9),c.table_name,CHAR(9),"
		"c.column_name,CHAR(9),c.ordinal_position,CHAR(9),c.data_type,CHAR(9),c.is_nullable,"
		"CHAR(9),COALESCE(c.character_maximum_length,0),CHAR(9),"
		"COALESCE(c.numeric_precision,0),CHAR(9),COALESCE(c.numeric_scale,0),CHAR(9),"
		"COALESCE(c.datetime_precision,0),CHAR(9),CASE WHEN c.column_default IS NULL THEN "
		"'<NULL>' WHEN UPPER(c.column_default) LIKE "
		"'CURRENT_TIMESTAMP%' THEN 'CURRENT_TIMESTAMP' ELSE TRIM(BOTH '\\'' FROM "
		"c.column_default) END,CHAR(9),CONCAT(IF(LOWER(c.extra) LIKE "
		"'%auto_increment%','A',''),IF(LOWER(c.extra) LIKE '%on update%','U',''),"
		"IF(LOWER(c.extra) LIKE '%generated%','G',''))) FROM information_schema.columns c "
		"JOIN information_schema.tables t ON t.table_schema=c.table_schema AND "
		"t.table_name=c.table_name AND t.table_type='BASE TABLE' WHERE "
		"c.table_schema=DATABASE() AND c.table_name IN (";
	query += RUNTIME_TABLE_SQL_LIST;
	query +=
		") "
		"UNION ALL SELECT CONCAT('I',CHAR(9),table_name,CHAR(9),index_name,CHAR(9),"
		"non_unique,CHAR(9),seq_in_index,CHAR(9),column_name,CHAR(9),COALESCE(sub_part,0)) "
		"FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name IN (";
	query += RUNTIME_TABLE_SQL_LIST;
	query +=
		") UNION ALL SELECT "
		"CONCAT('F',CHAR(9),k.table_name,CHAR(9),k.constraint_name,CHAR(9),k.column_name,"
		"CHAR(9),k.referenced_table_name,CHAR(9),k.referenced_column_name,CHAR(9),"
		"k.ordinal_position,CHAR(9),r.update_rule,CHAR(9),r.delete_rule) FROM "
		"information_schema.key_column_usage k JOIN information_schema.referential_constraints "
		"r ON r.constraint_schema=k.constraint_schema AND "
		"r.constraint_name=k.constraint_name WHERE k.constraint_schema=DATABASE() AND "
		"(k.table_name IN (";
	query += RUNTIME_TABLE_SQL_LIST;
	query += ") OR k.referenced_table_name IN (";
	query += RUNTIME_TABLE_SQL_LIST;
	query += ")) AND k.referenced_table_name IS NOT NULL";
	query +=
		" UNION ALL SELECT CONCAT('X',CHAR(9),table_name,CHAR(9),column_name,CHAR(9),column_type) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name IN ('economic_baseline_control','economic_baseline_reservation','economic_baseline_witness') UNION ALL SELECT CONCAT('K',CHAR(9),t.table_name,CHAR(9),t.constraint_name,CHAR(9),c.check_clause) FROM information_schema.table_constraints t JOIN information_schema.check_constraints c ON c.constraint_schema=t.constraint_schema AND c.constraint_name=t.constraint_name WHERE t.constraint_schema=DATABASE() AND t.constraint_type='CHECK' AND t.table_name IN ('economic_baseline_control','economic_baseline_reservation','economic_baseline_witness')";
	const char *server = mysql_get_server_info(DB);
	if (!server)
		return false;
	if (!strstr(server, "MariaDB"))
		query +=
			" UNION ALL SELECT CONCAT('E',CHAR(9),table_name,CHAR(9),constraint_name,CHAR(9),enforced) FROM information_schema.table_constraints WHERE constraint_schema=DATABASE() AND constraint_type='CHECK' AND table_name IN ('economic_baseline_control','economic_baseline_reservation','economic_baseline_witness')";
	query += " ORDER BY 1";
	if (mysql_real_query(DB, query.c_str(), query.size()))
		return false;
	MYSQL_RES *result = mysql_store_result(DB);
	if (!result)
		return false;
	std::string canonical;
	MYSQL_ROW row;
	while ((row = mysql_fetch_row(result)) != NULL)
	{
		if (!row[0])
		{
			mysql_free_result(result);
			return false;
		}
		size_t row_length = strlen(row[0]);
		if (row_length >= RUNTIME_METADATA_MAX_BYTES - canonical.size())
		{
			mysql_free_result(result);
			return false;
		}
		canonical += row[0];
		canonical += '\n';
	}
	mysql_free_result(result);
	unsigned char digest[SHA256_DIGEST_LENGTH];
	if (!SHA256((const unsigned char *)canonical.data(), canonical.size(), digest))
		return false;
	char encoded[SHA256_DIGEST_LENGTH * 2 + 1];
	for (size_t i = 0; i < SHA256_DIGEST_LENGTH; ++i)
		snprintf(encoded + i * 2, 3, "%02x", digest[i]);
	encoded[SHA256_DIGEST_LENGTH * 2] = '\0';

	const char *expected = server && strstr(server, "MariaDB") ?
				       RUNTIME_MARIADB10_11_METADATA_FINGERPRINT :
				       RUNTIME_MYSQL8_METADATA_FINGERPRINT;
	return !strcmp(encoded, expected);
}

/* Store core player data to the database. We assume that only association
 * names may contain special characters */
int sql_save_player_core(P_char ch)
{
	char query[MAX_STRING_LENGTH];
	char assoc_name[MAX_STRING_LENGTH];
	char assoc_name_sql[MAX_STRING_LENGTH * 2 + 1];
	struct char_player_data *p;
	if (IS_MORPH(ch))
		ch = ch->only.npc->orig_char;
	p = &ch->player;

	if (GET_ASSOC(ch) == NULL)
	{
		assoc_name[0] = '\0';
	}
	else
	{
		snprintf(assoc_name, MAX_STRING_LENGTH, "%s", GET_ASSOC(ch)->get_name().c_str());
	}
	mysql_str(assoc_name, assoc_name_sql);

	if (IS_SPECIALIZED(ch))
	{
	}

	// deactivate any other players with same name (handles renamed characters)
	sql_player_names_set(GET_PID(ch), p->name);
	snprintf(query, MAX_STRING_LENGTH,
		 "UPDATE player_data SET active = 0 WHERE name = '%s' and pid != %d", p->name,
		 GET_PID(ch));
	sql_queue("%s", query);

	// Mark this player active and keep its denormalized account identity aligned
	// with the canonical account projection. Existing rows created before the
	// transactional status-save linkage are repaired on their next login.
	if (ch->desc && ch->desc->account && ch->desc->account->acct_name &&
	    ch->desc->account->acct_name[0])
	{
		char account_name_sql[MAX_STRING_LENGTH * 2 + 1];
		mysql_str(ch->desc->account->acct_name, account_name_sql);
		if (!sql_queue("UPDATE player_data SET active=1,account_name='%s' WHERE pid=%d",
			       account_name_sql, GET_PID(ch)))
			return 0;
	}
	else if (!sql_queue("UPDATE player_data SET active=1 WHERE pid=%d", GET_PID(ch)))
	{
		return 0;
	}

	// Update frag leaderboard tables for web statistics
	sql_update_account_character(ch);
	sql_update_frag_leaderboard(ch);

	return 1;
}

/* Save a variable delta. var_type: 1=FRAGS, 2=EXP */
#define PROGRESS_FRAGS 1
#define PROGRESS_EXP 2

// The level_cap row, read at boot and after the maintenance job changes it, and kept
// current by sql_check_level_cap(), so the game never waits to read it.
static struct
{
	bool loaded = false;
	long most_frags = -1;
	int racewar = RACEWAR_NONE;
	int level = 0;
	time_t next_update = 0;
} level_cap_row;

static void level_cap_row_publish(const char *most_frags, const char *racewar, const char *level,
				  const char *next_update)
{
	level_cap_row.loaded = most_frags && racewar && level && next_update;
	if (!level_cap_row.loaded)
		return;
	level_cap_row.most_frags = (long)(atof(most_frags) * 100. + .01);
	level_cap_row.racewar = atoi(racewar);
	level_cap_row.level = atoi(level);
	level_cap_row.next_update = atol(next_update);
}

static const char level_cap_query[] =
	"SELECT most_frags, racewar_leader, level, UNIX_TIMESTAMP(next_update) FROM level_cap";

// Boot only: the game loop is not running yet.
static void sql_load_level_cap(void)
{
	MYSQL_RES *db = db_query("%s", level_cap_query);
	MYSQL_ROW row = db ? mysql_fetch_row(db) : NULL;
	level_cap_row_publish(row ? row[0] : NULL, row ? row[1] : NULL, row ? row[2] : NULL,
			      row ? row[3] : NULL);
	if (db)
		mysql_free_result(db);
	if (!level_cap_row.loaded)
		debug("sql_load_level_cap: Database read fail.");
}

void sql_level_cap_reload(void)
{
	sql_read(level_cap_query,
		 [](bool ok, const sql_rows &rows)
		 {
			 if (ok && !rows.empty())
				 level_cap_row_publish(rows[0][0], rows[0][1], rows[0][2],
						       rows[0][3]);
		 });
}

// Retrieves the current highest number of frags and which racewar side has it.
void get_level_cap_info(long *max_frags, int *racewar, int *level, time_t *next_update)
{
	if (!level_cap_row.loaded)
	{
		*max_frags = (long)-1;
		*racewar = RACEWAR_NONE;
		*level = frag_cap_config_get()->cap_floor_level;
		*next_update = 0;
		return;
	}
	*max_frags = level_cap_row.most_frags;
	*racewar = level_cap_row.racewar;
	*level = level_cap_row.level;
	*next_update = level_cap_row.next_update;
}

// Returns the highest level achievable by mortals, limited by racewar side.
int sql_level_cap(int /*racewar_side*/)
{
	const struct frag_cap_config *config = frag_cap_config_get();
	if (!level_cap_row.loaded)
		return config->cap_floor_level;
	const int level_cap = level_cap_row.level;

	// Clamp database values to the configured mortal-cap range.
	if (level_cap >= config->cap_maximum_level)
		return config->cap_maximum_level;
	if (level_cap <= config->cap_floor_level)
		return config->cap_floor_level;

	return level_cap;
}

/*
 * Frag Leaderboard Hybrid System - for web statistics
 * These functions maintain the account_characters and frag_leaderboard tables
 * The MUD continues to use flat files, but web can query the database
 */

/*
 * Resolve an existing account_characters row id for an escaped character name,
 * or 0 when the mapping is absent.
 *
 * account_characters.id is a signed INT AUTO_INCREMENT, and MySQL consumes an
 * identity value on every INSERT ... ON DUPLICATE KEY UPDATE attempt, including
 * the ones that only update. Projecting an existing mapping on every save
 * therefore advanced the counter far past the surviving row count. Resolving the
 * row first keeps the steady-state path an UPDATE, which allocates nothing.
 */
unsigned int sql_find_account_character_id(MYSQL *connection, long pid,
					   const std::string &escaped_char_name, long *id)
{
	/* The character's active mapping by pid first, preferring one that already
	 * has its name, so a renamed character updates its row instead of adding a
	 * second one; then any row with its name. */
	sql_rows rows;
	if (const unsigned int error_code =
		    sql_select(connection,
			       sql_format("SELECT id FROM account_characters "
					  "WHERE pid=%ld AND deleted_at IS NULL "
					  "ORDER BY char_name='%s' DESC, id LIMIT 1",
					  pid, escaped_char_name.c_str()),
			       &rows))
		return error_code;
	if (rows.empty())
		if (const unsigned int error_code = sql_select(
			    connection,
			    sql_format(
				    "SELECT id FROM account_characters WHERE char_name='%s' LIMIT 1",
				    escaped_char_name.c_str()),
			    &rows))
			return error_code;
	*id = !rows.empty() && rows[0][0] ? atol(rows[0][0]) : 0;
	return 0;
}

/* Update account_characters mapping table */
void sql_update_account_character(P_char ch)
{
	char account_name_sql[MAX_STRING_LENGTH * 2 + 1];
	char char_name_sql[MAX_STRING_LENGTH * 2 + 1];
	const char *account_name;

	if (!ch || IS_NPC(ch))
		return;

	if (GET_PID(ch) <= 0)
	{
		logit(LOG_DEBUG, "sql_update_account_character: invalid pid for %s",
		      GET_NAME(ch) ? GET_NAME(ch) : "<null>");
		return;
	}

	account_name = get_account_name_safe(ch);

	// account_characters is UNIQUE on char_name and the account character list is
	// selected by account_name, so writing the get_account_name_safe() placeholder
	// would move the row off its real account and empty that account's menu while
	// player_data still holds the character. An offline or descriptor-less save has
	// nothing to project; leave the existing mapping alone.
	if (!ch->desc || !ch->desc->account || !ch->desc->account->acct_name ||
	    !ch->desc->account->acct_name[0])
	{
		logit(LOG_DEBUG,
		      "sql_update_account_character: component=mapping outcome=skipped_no_account pid=%d",
		      GET_PID(ch));
		return;
	}

	// Escape strings for SQL safety
	mysql_str(account_name, account_name_sql);
	mysql_str(ch->player.name, char_name_sql);

	// Update an existing mapping in place and insert only a genuinely new one,
	// so a repeated projection of the same character allocates no identity value.
	// created_at is preserved either way. The lookup runs on the writer, just before
	// the write it decides.
	const long pid = GET_PID(ch);
	const std::string account = account_name_sql, name = char_name_sql;
	const bool queued = sql_queue_work(
		[pid, account, name](MYSQL *connection) -> unsigned int
		{
			long mapping_id = 0;
			if (const unsigned int error_code = sql_find_account_character_id(
				    connection, pid, name, &mapping_id))
				return error_code;
			return sql_execute(
				connection,
				mapping_id > 0 ?
					sql_format(
						"UPDATE account_characters "
						"SET account_name = '%s', pid = %ld, char_name = '%s', "
						"deleted_at = NULL "
						"WHERE id = %ld",
						account.c_str(), pid, name.c_str(), mapping_id) :
					// ON DUPLICATE KEY UPDATE still converges when another row
					// with the same unique char_name appeared after the lookup.
					sql_format(
						"INSERT INTO account_characters "
						"(account_name, pid, char_name, created_at, deleted_at) "
						"VALUES('%s', %ld, '%s', NOW(), NULL) "
						"ON DUPLICATE KEY UPDATE "
						"account_name = VALUES(account_name), "
						"pid = VALUES(pid), "
						"char_name = VALUES(char_name), "
						"deleted_at = NULL",
						account.c_str(), pid, name.c_str()));
		});

	if (!queued)
	{
		logit(LOG_DEBUG, "sql_update_account_character: failed for %s",
		      GET_NAME(ch) ? GET_NAME(ch) : "<null>");
	}
}

void show_total_donated(P_char ch, const char *account_name)
{
	if (!account_name || !*account_name)
		return;
	sql_read_for(ch,
		     sql_format("SELECT total_donated FROM accounts WHERE account_name='%s'",
				escape_str(account_name).c_str()),
		     [](P_char live, const sql_rows &rows)
		     {
			     const double total = !rows.empty() && rows[0][0] ? atof(rows[0][0]) :
										0;
			     if (total <= 0)
				     return;
			     char buf[MAX_STRING_LENGTH];
			     snprintf(buf, MAX_STRING_LENGTH, "&+YTotal Donations:&n &+W$%.2f&n\n",
				      total);
			     send_to_char(buf, live);
		     });
}

/* Update frag_leaderboard table with current character data */
void sql_update_frag_leaderboard(P_char ch)
{
	char account_name_sql[MAX_STRING_LENGTH * 2 + 1];
	char char_name_sql[MAX_STRING_LENGTH * 2 + 1];
	char race_sql[MAX_STRING_LENGTH * 2 + 1];
	char class_sql[MAX_STRING_LENGTH * 2 + 1];
	const char *account_name;
	const char *race_name;
	const char *class_name;

	if (!ch || IS_NPC(ch))
		return;

	if (GET_PID(ch) <= 0)
	{
		logit(LOG_DEBUG, "sql_update_frag_leaderboard: invalid pid for %s",
		      GET_NAME(ch) ? GET_NAME(ch) : "<null>");
		return;
	}

	account_name = get_account_name_safe(ch);
	race_name = race_names_table[ch->player.race].normal;
	class_name = class_names_table[flag2idx(ch->player.m_class)].normal;

	// Escape strings for SQL safety
	mysql_str(account_name, account_name_sql);
	mysql_str(ch->player.name, char_name_sql);
	mysql_str(race_name, race_sql);
	mysql_str(class_name, class_sql);

	// Insert or update frag_leaderboard
	// Using INSERT ... ON DUPLICATE KEY UPDATE to preserve the row id while
	// refreshing the current stats.
	if (!sql_queue(
		    "INSERT INTO frag_leaderboard "
		    "(pid, account_name, char_name, total_frags, racewar, race, class, level, deleted_at) "
		    "VALUES(%d, '%s', '%s', %ld, %d, '%s', '%s', %d, NULL) "
		    "ON DUPLICATE KEY UPDATE "
		    "account_name=VALUES(account_name), "
		    "char_name=VALUES(char_name), "
		    "total_frags=VALUES(total_frags), "
		    "racewar=VALUES(racewar), "
		    "race=VALUES(race), "
		    "class=VALUES(class), "
		    "level=VALUES(level), "
		    "deleted_at=NULL",
		    GET_PID(ch), account_name_sql, char_name_sql, ch->only.pc->frags,
		    GET_RACEWAR(ch), race_sql, class_sql, GET_LEVEL(ch)))
	{
		logit(LOG_DEBUG, "sql_update_frag_leaderboard: failed for %s",
		      GET_NAME(ch) ? GET_NAME(ch) : "<null>");
	}
}

/* Save frags delta */
void sql_insert_item(P_char /*ch*/, P_obj obj, char *desc)
{
	char query[MAX_STRING_LENGTH];
	char sql_desc[MAX_STRING_LENGTH * 2 + 1];
	char sql_short[MAX_STRING_LENGTH * 2 + 1];

	int m_virtual = (obj->R_num >= 0) ? obj_index[obj->R_num].virtual_number : 0;
	mysql_str(desc, sql_desc);
	mysql_str(obj->short_description, sql_short);

	checked_snprintf(query, MAX_STRING_LENGTH,
			 "UPDATE items_stats SET  obj_stat = '%s', vnum = %d "
			 " WHERE short_desc = '%s'",
			 sql_desc, m_virtual, sql_short);
	sql_queue_statements(
		{ sql_format("INSERT IGNORE INTO items_stats VALUES( null, '%s', '', %d)",
			     sql_short, m_virtual),
		  query });
}

/* Save character's preferences about displaying extended info on
   webpage for all to see. */
void sql_webinfo_toggle(P_char ch)
{
	if (!ch || !IS_PC(ch))
		return;
	// webinfo is stored in act2 flag, saved with player_data
}

/* Update level info */
void sql_update_level(P_char ch)
{
	if (!ch || !IS_PC(ch))
		return;
	// level already saved in player_data
}

void sql_resetConnectTimes(void)
{
	// this should ONLY be called on mud bootup.  to ensure that, call it when sql is initialized
	db_query("UPDATE ip_info SET last_disconnect = NOW() WHERE last_connect > last_disconnect");
}

// ip_info, read at boot and kept current by sql_connectIP() and sql_disconnectIP(), so
// logins and finger never wait for the database. Times are UNIX seconds.
struct ip_activity
{
	std::string ip;
	time_t last_connect = 0;
	time_t last_disconnect = 0;
	int racewar_side = RACEWAR_NONE;
};
static std::unordered_map<int, ip_activity> ip_activity_by_pid;

// Boot only: the game loop is not running yet.
static void sql_load_ip_activity(void)
{
	MYSQL_RES *db = db_query("SELECT pid, last_ip, UNIX_TIMESTAMP(last_connect), "
				 "UNIX_TIMESTAMP(last_disconnect), racewar_side FROM ip_info");
	if (!db)
		return;
	while (MYSQL_ROW row = mysql_fetch_row(db))
	{
		if (!row[0])
			continue;
		ip_activity &activity = ip_activity_by_pid[atoi(row[0])];
		activity.ip = row[1] ? row[1] : "";
		activity.last_connect = row[2] ? strtoul(row[2], NULL, 10) : 0;
		activity.last_disconnect = row[3] ? strtoul(row[3], NULL, 10) : 0;
		activity.racewar_side = row[4] ? atoi(row[4]) : RACEWAR_NONE;
	}
	mysql_free_result(db);
}

void sql_disconnectIP(P_char ch)
{
	if (!ch || !IS_PC(ch))
		return;

	std::vector<std::string> statements = { sql_format(
		"INSERT IGNORE INTO ip_info (pid) VALUES (%d)", GET_PID(ch)) };
	ip_activity &activity = ip_activity_by_pid[GET_PID(ch)];
	if (ch->desc)
	{
		// Set racewar side if not an immortal.
		activity.last_disconnect = time(NULL);
		activity.racewar_side = IS_TRUSTED(ch) ? RACEWAR_NONE : GET_RACEWAR(ch);
		statements.push_back(sql_format(
			"UPDATE ip_info SET last_disconnect = FROM_UNIXTIME(%ld), racewar_side=%d WHERE pid = %d",
			(long)activity.last_disconnect, activity.racewar_side, GET_PID(ch)));
	}
	sql_queue_statements(std::move(statements));
}

void sql_connectIP(P_char ch)
{
	// insert will silently fail if the PID is already in the table
	std::vector<std::string> statements = { sql_format(
		"INSERT IGNORE INTO ip_info (pid) VALUES (%d)", GET_PID(ch)) };
	ip_activity &activity = ip_activity_by_pid[GET_PID(ch)];
	if (ch->desc)
	{
		activity.ip = ch->desc->host;
		activity.last_connect = time(NULL);
		activity.racewar_side = IS_TRUSTED(ch) ? RACEWAR_NONE : GET_RACEWAR(ch);
		statements.push_back(sql_format(
			"UPDATE ip_info SET last_ip = '%s', last_connect = FROM_UNIXTIME(%ld), racewar_side = %d WHERE pid = %d",
			escape_str(ch->desc->host).c_str(), (long)activity.last_connect,
			activity.racewar_side, GET_PID(ch)));
	}
	sql_queue_statements(std::move(statements));
}

// Each character's world quest history, read when it enters the game and kept current
// by sql_world_quest_finished(), so the quest checks never wait for the database.
struct world_quest_history
{
	std::unordered_set<int> targets;
	// Quests finished today, by the level they were finished at, and the UTC day they
	// count for.
	std::unordered_map<int, int> today_by_level;
	int today_total = 0;
	long day = 0;
};
static std::unordered_map<int, world_quest_history> world_quest_histories;
static std::unordered_set<int> world_quest_histories_loading;

// Days since the epoch in UTC, as TO_DAYS(NOW()) counts them: every connection runs in
// UTC (sql_apply_session_contract()).
static long utc_day_number(void)
{
	return (long)(time(NULL) / 86400);
}

void sql_world_quest_history_load(P_char ch)
{
	if (!ch || !IS_PC(ch) || GET_PID(ch) <= 0 ||
	    !world_quest_histories_loading.insert(GET_PID(ch)).second)
		return;
	const int pid = GET_PID(ch);
	if (!sql_read(sql_format("SELECT quest_target, player_level, "
				 "TO_DAYS(timestamp) = TO_DAYS(NOW()) "
				 "FROM world_quest_accomplished WHERE pid = %d",
				 pid),
		      [pid](bool ok, const sql_rows &rows)
		      {
			      world_quest_histories_loading.erase(pid);
			      if (!ok)
				      return;
			      world_quest_history history;
			      history.day = utc_day_number();
			      for (const sql_row &row : rows)
			      {
				      if (row[0])
					      history.targets.insert(atoi(row[0]));
				      if (row[1] && row[2] && atoi(row[2]))
				      {
					      ++history.today_by_level[atoi(row[1])];
					      ++history.today_total;
				      }
			      }
			      world_quest_histories[pid] = std::move(history);
			      // The Quest.Status sent on entering the game could not carry the
			      // count: this read was still out.
			      if (P_char online = find_player_by_pid(pid))
				      gmcp_quest_status(online);
		      }))
		world_quest_histories_loading.erase(pid);
}

// The character's history, or NULL while it is being read.
static world_quest_history *world_quest_history_of(P_char ch)
{
	const auto found = world_quest_histories.find(GET_PID(ch));
	if (found == world_quest_histories.end())
	{
		sql_world_quest_history_load(ch);
		return NULL;
	}
	if (found->second.day != utc_day_number())
	{
		found->second.today_by_level.clear();
		found->second.today_total = 0;
		found->second.day = utc_day_number();
	}
	return &found->second;
}

void sql_world_quest_finished(P_char ch, P_obj reward)
{
	char buf[MAX_STRING_LENGTH * 2 + 1];

	int reward_vnum =
		reward ? ((reward->R_num >= 0) ? obj_index[reward->R_num].virtual_number : 0) : 0;
	char *reward_desc = reward ? mysql_str(reward->short_description, buf) : mysql_str("", buf);

	sql_queue(
		"INSERT INTO world_quest_accomplished (pid, timestamp, quest_giver, player_name, player_level, quest_target, reward_vnum, reward_desc) VALUES (%d, now(), %d, '%s', %d, %d, %d, '%s')",
		GET_PID(ch), ch->only.pc->quest_giver, GET_NAME(ch), GET_LEVEL(ch),
		ch->only.pc->quest_mob_vnum, reward_vnum, reward_desc);
	const auto found = world_quest_histories.find(GET_PID(ch));
	if (found != world_quest_histories.end())
	{
		found->second.targets.insert(ch->only.pc->quest_mob_vnum);
		++found->second.today_by_level[GET_LEVEL(ch)];
		++found->second.today_total;
	}
	else
	{
		// A read queued before this insert would miss it: queue one after it.
		world_quest_histories_loading.erase(GET_PID(ch));
		sql_world_quest_history_load(ch);
	}

	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
}

int sql_world_quest_can_do_another(P_char ch)
{
	// This crashed us when paly's horse called this function.
	if (!IS_PC(ch))
		return 0;

	const world_quest_history *history = world_quest_history_of(ch);
	if (!history)
		return -1;
	int done_today = history->today_total;
	if (GET_LEVEL(ch) < 50)
	{
		const auto found = history->today_by_level.find(GET_LEVEL(ch));
		done_today = found == history->today_by_level.end() ? 0 : found->second;
	}

	int returning_value = 0;
	if (GET_LEVEL(ch) <= 30)
		returning_value = get_property("world.quest.max.level.30.andUnder", 6.000);
	else if (GET_LEVEL(ch) <= 40)
		returning_value = get_property("world.quest.max.level.40.andUnder", 6.000);
	else if (GET_LEVEL(ch) <= 50)
		returning_value = get_property("world.quest.max.level.50.andUnder", 6.000);
	else if (GET_LEVEL(ch) <= 55)
		returning_value = get_property("world.quest.max.level.55.andUnder", 6.000);
	else
		returning_value = get_property("world.quest.max.level.other", 6.000);

	returning_value = difficulty_scale_world_quest_allowance(returning_value);
	returning_value -= done_today;
	return MAX(returning_value, 0);
}

int sql_world_quest_done_already(P_char ch, int quest_target)
{
	if (!ch || !IS_PC(ch) || !ch->only.pc || GET_PID(ch) <= 0 || quest_target <= 0)
		return -1;
	const world_quest_history *history = world_quest_history_of(ch);
	if (!history)
	{
		logit(LOG_DEBUG, "sql_world_quest_done_already: history not loaded yet");
		return -1;
	}
	return history->targets.count(quest_target) ? 1 : 0;
}

const char *sql_select_IP_info(P_char ch, char *buf, size_t bufSize, time_t *lastConnect,
			       time_t *lastDisconnect)
{
	buf[0] = '\0';
	const auto found = ip_activity_by_pid.find(GET_PID(ch));
	if (found == ip_activity_by_pid.end())
		return buf;
	const time_t now = time(NULL);
	// ADR 0003: an address is not kept past 30 days, as the hourly prune clears ip_info.
	if (now - found->second.last_connect <= 30 * 24 * 3600)
		strlcpy(buf, found->second.ip.c_str(), bufSize);
	if (lastConnect)
		*lastConnect = found->second.last_connect ? now - found->second.last_connect : 0;
	if (lastDisconnect)
		*lastDisconnect =
			found->second.last_disconnect ? now - found->second.last_disconnect : 0;
	return buf;
}

static bool sql_trace_enabled(void)
{
	static int cached = -1;
	if (cached < 0)
	{
		const char *env = getenv("SQL_TRACE");
		bool on = false;

		// Both branches used to set this true, so tracing was always on -- two log
		//   lines (each an open/append/close) for every query the game runs, even
		//   with SQL_TRACE explicitly set to off.  Opt-in, as intended.
		if (env && *env && strcmp(env, "0") != 0 && strcasecmp(env, "false") != 0 &&
		    strcasecmp(env, "off") != 0)
		{
			on = true;
		}
		cached = on ? 1 : 0;
	}
	return cached != 0;
}

static bool sql_trace_active(void)
{
	return sql_trace_enabled() || sql_trace_burst > 0;
}

static enum persistence_query_context sql_current_context(void)
{
	return getpid() == sql_main_process_id ? PERSISTENCE_QUERY_CONTEXT_MAIN :
						 PERSISTENCE_QUERY_CONTEXT_CHILD;
}

static void sql_trace_log_drain(MYSQL *conn, const char *phase, bool drained)
{
	if (!conn)
		return;
	if (drained)
		sql_trace_burst = 100;
	if (!sql_trace_active() && !drained)
		return;

	logit(LOG_DEBUG,
	      "[SQLTRACE] phase=%s drained=%d burst=%d error_code=%u sqlstate=%.5s "
	      "field_count=%u more_results=%d",
	      phase, drained ? 1 : 0, sql_trace_burst, (unsigned int)mysql_errno(conn),
	      mysql_sqlstate(conn), (unsigned int)mysql_field_count(conn),
	      mysql_more_results(conn));
}

void sql_trace_panic(void)
{
	sql_trace_burst = 100;
}

bool sql_observed_execute_at(MYSQL *conn, struct persistence_query_site site,
			     enum persistence_query_context context, const char *sql, size_t len,
			     uint64_t *operation_id)
{
	if (!conn || !sql)
		return false;

	const enum persistence_statement_kind kind = persistence_statement_kind_from_sql(sql);
	const uint64_t started_at = persistence_observability_now_usec();
	const int status = mysql_real_query(conn, sql, len);
	const uint64_t finished_at = persistence_observability_now_usec();
	const uint64_t duration = finished_at >= started_at ? finished_at - started_at : 0;
	const unsigned int error_code = status == 0 ? 0 : (unsigned int)mysql_errno(conn);
	const char *mysql_state = status == 0 ? "00000" : mysql_sqlstate(conn);
	const uint64_t recorded_id = persistence_query_record(site, context, kind, duration,
							      status == 0, error_code, mysql_state);
	if (operation_id)
		*operation_id = recorded_id;

	if (status != 0 || sql_trace_active())
	{
		struct persistence_query_event event = {};
		char diagnostic[512];
		event.operation_id = recorded_id;
		event.site = site;
		event.context = context;
		event.kind = kind;
		event.duration_usec = duration;
		event.error_code = error_code;
		event.success = status == 0;
		snprintf(event.sqlstate, sizeof(event.sqlstate), "%.5s", mysql_state);
		if (persistence_query_event_format(diagnostic, sizeof(diagnostic), &event) >= 0)
			logit(status == 0 ? LOG_DEBUG : LOG_STATUS, "%s", diagnostic);
		if (sql_trace_burst > 0 && !sql_trace_enabled())
			--sql_trace_burst;
	}
	return status == 0;
}

static bool game_loop_running = false;
static uint64_t game_loop_queries = 0;
static std::set<std::pair<std::string, int>> game_loop_query_sites;

void sql_game_loop_running(bool running)
{
	game_loop_running = running;
}

uint64_t sql_game_loop_query_count(void)
{
	return game_loop_queries;
}

bool sql_trace_exec_at(struct persistence_query_site source_site, const char *label,
		       const char *sql, size_t len, bool drain_before, bool drain_after)
{
	if (!DB || !sql)
		return false;
	const struct persistence_query_site semantic_site = {
		source_site.file, label && *label ? label : source_site.function, source_site.line
	};
	if (game_loop_running && sql_current_context() == PERSISTENCE_QUERY_CONTEXT_MAIN)
	{
		++game_loop_queries;
		if (game_loop_query_sites.emplace(source_site.file, source_site.line).second)
			logit(LOG_STATUS, "game loop query site %s:%d %s (%s)", source_site.file,
			      source_site.line, source_site.function,
			      persistence_statement_kind_name(
				      persistence_statement_kind_from_sql(sql)));
	}
	if (drain_before)
		sql_clear_results_on(DB);
	uint64_t operation_id = 0;
	if (!sql_observed_execute_at(DB, semantic_site, sql_current_context(), sql, len,
				     &operation_id))
	{
		sql_trace_panic();
		return false;
	}

	if (drain_after)
		sql_clear_results_on(DB);
	return true;
}

void sql_clear_results_on(MYSQL *conn)
{
	if (!conn)
		return;

	int status = 0;
	bool drained_any = false;
	do
	{
		/* did current statement return data? */
		MYSQL_RES *result = mysql_store_result(conn);
		if (result)
		{
			my_ulonglong rows = mysql_num_rows(result);
			unsigned int fields = mysql_num_fields(result);
			drained_any = true;
			logit(LOG_DEBUG,
			      "[SQLTRACE] phase=%s conn=%lu drained_result rows=%llu fields=%u more_results=%d",
			      "clear/result", (unsigned long)mysql_thread_id(conn),
			      (unsigned long long)rows, fields, mysql_more_results(conn));
			mysql_free_result(result);
		}
		else /* no result set or error */
		{
			if (mysql_field_count(conn) == 0)
			{
				// printf("%lld rows affected\n", mysql_affected_rows(conn));
			}
			else if (mysql_errno(conn) == CR_COMMANDS_OUT_OF_SYNC)
			{
				// Legacy callers often consume and free their result before the next
				// pre-query drain. A second mysql_store_result() reports 2014 even
				// though no result remains and the connection is usable. Do not turn
				// that already-consumed state into a production trace burst.
				if (sql_trace_enabled())
					sql_trace_log_drain(conn, "clear/already_consumed", false);
				break;
			}
			else if (mysql_errno(conn) == 0)
			{
				// Benign pre-clear: no pending result and no MySQL error.
				// Keep this silent; the query/site trace already shows the caller.
			}
			else /* actual error occurred */
			{
				sql_trace_log_drain(conn, "clear/error", true);
				break;
			}
		}
		/* more results? -1 = no, >0 = error, 0 = yes (keep looping) */
		if ((status = mysql_next_result(conn)) > 0)
		{
			sql_trace_log_drain(conn, "clear/next_result_error", true);
			break;
		}
	} while (status == 0);

	if (drained_any)
		sql_trace_log_drain(conn, "clear/drained", true);
}

void sql_clear_results()
{
	sql_clear_results_on(DB);
}

bool qry_at(struct persistence_query_site site, const char *format, ...)
{
	char buf[MAX_STRING_LENGTH];
	va_list args;
	int ret;

	if (!DB)
	{
		logit(LOG_DEBUG, "MySQL error: MySQL not initialized!");
		return FALSE;
	}

	va_start(args, format);
	buf[0] = '\0';
	// SECURITY FIX: Replace vsprintf with vsnprintf to prevent buffer overflow
	ret = vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);

	// Check for overflow
	if (ret < 0 || ret >= (int)sizeof(buf))
	{
		logit(LOG_DEBUG, "MySQL error: Query too long or formatting error");
		return FALSE;
	}

	if (!sql_trace_exec_at(site, "qry/direct", buf, strlen(buf), true, false))
	{
		return FALSE;
	}

	return TRUE;
}

void send_to_pid_offline(const char *msg, int pid)
{
	char buff[MAX_STRING_LENGTH];
	mysql_real_escape_string(DB, buff, msg, strlen(msg));
	sql_queue("INSERT INTO offline_messages (date, pid, message) VALUES (now(), '%d', '%s')",
		  pid, buff);
}

static bool sql_escape_offline_message(const char *message, std::string *escaped)
{
	if (!DB || !message || !escaped)
		return false;
	const size_t message_length = strnlen(message, MAX_STRING_LENGTH);
	if (message_length >= MAX_STRING_LENGTH)
		return false;
	escaped->resize(message_length * 2 + 1);
	const unsigned long escaped_length = mysql_real_escape_string(
		DB, &(*escaped)[0], message, static_cast<unsigned long>(message_length));
	escaped->resize(escaped_length);
	return true;
}

bool send_to_pid_offline_deduplicated(const char *msg, int pid, const unsigned char *message_id)
{
	if (!DB || !msg || pid <= 0 || !message_id)
		return false;
	critical_operation_id operation_id = {};
	memcpy(operation_id.bytes.data(), message_id, operation_id.bytes.size());
	if (critical_operation_id_is_zero(operation_id))
		return false;
	char message_id_hex[CRITICAL_COMMAND_ID_HEX_SIZE] = {};
	if (!critical_operation_id_to_hex(operation_id, message_id_hex, sizeof(message_id_hex)))
		return false;

	std::string escaped_message;
	if (!sql_escape_offline_message(msg, &escaped_message))
	{
		persistence_alert(AVATAR, "offline_message", "player", "unknown", "enqueue",
				  "message_too_large", "pid=%d", pid);
		return false;
	}

	// The receipt is the durable outbox. The physical queue row is rebuilt from
	// a pending receipt, so a crash between enqueue/dequeue and restart cannot
	// lose a notification. The primary key, not an advisory lock or message
	// text, owns identity and concurrent retries. Both rows are one sql job, so
	// they commit together.
	return sql_queue_statements(
		{ sql_format("INSERT INTO offline_message_receipts "
			     "(pid,message_id,message,status) VALUES (%d,UNHEX('%s'),'%s',0) "
			     "ON DUPLICATE KEY UPDATE message=message",
			     pid, message_id_hex, escaped_message.c_str()),
		  sql_format("INSERT IGNORE INTO offline_messages (date,pid,message,message_id) "
			     "SELECT UTC_TIMESTAMP(6),pid,message,message_id "
			     "FROM offline_message_receipts WHERE pid=%d "
			     "AND message_id=UNHEX('%s') AND status IN (0,1)",
			     pid, message_id_hex) });
}

void send_offline_messages(P_char ch)
{
	if (!ch)
		return;
	const int pid = GET_PID(ch);

	// The writer finds the waiting messages and claims each durable receipt before
	// the game shows it, so a restart retries a delivery that did not finish. A
	// claimed receipt is retried only after its short lease expires.
	sql_read_work_for(
		ch,
		[pid](MYSQL *connection, sql_rows *rows) -> unsigned int
		{
			if (const unsigned int error_code = sql_execute(
				    connection,
				    sql_format(
					    "UPDATE offline_message_receipts SET status=0 "
					    "WHERE pid='%d' AND status=1 AND (last_attempt_at IS NULL OR "
					    "last_attempt_at < UTC_TIMESTAMP(6) - INTERVAL 30 SECOND)",
					    pid)))
				return error_code;
			sql_rows waiting;
			if (const unsigned int error_code = sql_select(
				    connection,
				    sql_format(
					    "SELECT 'R' AS delivery_kind, 0 AS queue_id, LOWER(HEX(r.message_id)) AS message_id, "
					    "r.message, r.created_at AS created_at FROM offline_message_receipts r "
					    "WHERE r.pid='%d' AND r.status=0 "
					    "UNION ALL "
					    "SELECT 'L', m.id, '', m.message, m.date FROM offline_messages m "
					    "WHERE m.pid='%d' AND m.message_id IS NULL "
					    "ORDER BY created_at ASC, delivery_kind ASC, queue_id ASC",
					    pid, pid),
				    &waiting))
				return error_code;
			for (sql_row &row : waiting)
			{
				const bool durable = row[0] && row[0][0] == 'R';
				if (durable)
				{
					if (!row[2] || !*row[2])
						continue;
					if (const unsigned int error_code = sql_execute(
						    connection,
						    sql_format(
							    "UPDATE offline_message_receipts SET status=1, "
							    "attempt_count=attempt_count+1,"
							    "last_attempt_at=UTC_TIMESTAMP(6) "
							    "WHERE pid='%d' AND message_id=UNHEX('%s') "
							    "AND status=0",
							    pid, row[2])))
						return error_code;
					if (mysql_affected_rows(connection) != 1)
						continue;
				}
				rows->push_back(std::move(row));
			}
			return 0;
		},
		[pid](P_char live, const sql_rows &rows)
		{
			std::vector<std::string> acknowledgements;
			for (const sql_row &delivery : rows)
			{
				send_to_char(delivery[3] ? delivery[3] : "", live);
				if (delivery[0] && delivery[0][0] == 'R')
				{
					// The receipt remains as the durable acknowledgement; delivered
					// receipts are excluded from the next delivery scan.
					acknowledgements.push_back(sql_format(
						"UPDATE offline_message_receipts SET status=2, "
						"delivered_at=UTC_TIMESTAMP(6) WHERE pid='%d' "
						"AND message_id=UNHEX('%s') AND status=1",
						pid, delivery[2]));
					acknowledgements.push_back(sql_format(
						"DELETE FROM offline_messages WHERE pid='%d' "
						"AND message_id=UNHEX('%s')",
						pid, delivery[2]));
				}
				else
					acknowledgements.push_back(sql_format(
						"DELETE FROM offline_messages WHERE id='%d'",
						delivery[1] ? atoi(delivery[1]) : 0));
			}
			if (!acknowledgements.empty() &&
			    !sql_queue_statements(std::move(acknowledgements)))
				persistence_alert(AVATAR, "offline_message", "player", "unknown",
						  "acknowledge", "database_write_failed", "pid=%d",
						  pid);
		});
}

// Recent events per key (shop sales per item, quest rewards per giver), each kept as
// the UTC day it happened on. They are read at boot and added to as they happen, so
// prices and rewards never wait for the database.
struct recent_counts
{
	int window_days;
	std::unordered_map<int, std::vector<long>> days;

	void add(int key, long day)
	{
		std::vector<long> &events = days[key];
		const long since = utc_day_number() - window_days;
		events.erase(std::remove_if(events.begin(), events.end(),
					    [since](long event) { return event < since; }),
			     events.end());
		events.push_back(day);
	}

	int count(int key) const
	{
		const auto found = days.find(key);
		if (found == days.end())
			return 0;
		const long since = utc_day_number() - window_days;
		return (int)std::count_if(found->second.begin(), found->second.end(),
					  [since](long event) { return event >= since; });
	}

	// Boot only: rows of (key, days before today).
	void load(const char *query)
	{
		MYSQL_RES *db = db_query("%s", query);
		if (!db)
			return;
		const long today = utc_day_number();
		while (MYSQL_ROW row = mysql_fetch_row(db))
			if (row[0] && row[1])
				days[atoi(row[0])].push_back(today - atol(row[1]));
		mysql_free_result(db);
	}
};
static recent_counts recent_shop_sales = { 7, {} };
static recent_counts recent_quest_rewards = { 14, {} };

static void sql_load_recent_counts(void)
{
	recent_shop_sales.load("SELECT item, TO_DAYS(NOW()) - TO_DAYS(timestamp) FROM shop_trophy "
			       "WHERE TO_DAYS(NOW()) - TO_DAYS(timestamp) <= 7");
	recent_quest_rewards.load(
		"SELECT mob_vnum, TO_DAYS(NOW()) - TO_DAYS(timestamp) FROM quest_trophy "
		"WHERE TO_DAYS(NOW()) - TO_DAYS(timestamp) <= 14");
}

int sql_shop_sell(P_char ch, P_obj obj, int value)
{
	if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
		return flat_sql_shop_sell(ch, obj, value);
	if (!obj)
		return 0;
	int m_virtual = (obj->R_num >= 0) ? obj_index[obj->R_num].virtual_number : 0;

	int pid = (IS_PC(ch) ? GET_PID(ch) : 0);

	sql_queue(
		"INSERT INTO shop_trophy (item, value, seller, timestamp) VALUES ('%d', '%d', %d, now())",
		m_virtual, value, pid);
	recent_shop_sales.add(m_virtual, utc_day_number());

	return 1;
}

int sql_shop_trophy(P_obj obj)
{
	if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
		return flat_sql_shop_trophy(obj);
	if (!obj)
		return 0;

	// mined ore doesnt devaule
	if (obj->name && strstr(obj->name, "_ore_"))
		return 0;

	int objvir = OBJ_VNUM(obj);
	if ((objvir >= 400000) && (objvir < 400202))
		return 0;

	int m_virtual = (obj->R_num >= 0) ? obj_index[obj->R_num].virtual_number : 0;
	return recent_shop_sales.count(m_virtual);
}

///

/* The prepstatement_duris_sql table looks like:
+-------------+---------+------+-----+---------+----------------+
| Field       | Type    | Null | Key | Default | Extra          |
+-------------+---------+------+-----+---------+----------------+
| id          | int(11) | NO   | PRI | NULL    | auto_increment |
| description | text    | YES  |     | NULL    |                |
| sql_code    | text    | YES  |     | NULL    |                |
+-------------+---------+------+-----+---------+----------------+
*/
void do_sql(P_char ch, char *argument, int cmd)
{
	char first[MAX_INPUT_LENGTH];
	char second[MAX_INPUT_LENGTH];
	char third[MAX_INPUT_LENGTH];
	char *rest;
	char buf[MAX_STRING_LENGTH];
	int prep_statement;

	if (!IS_TRUSTED(ch))
	{
		send_to_char("A mere mortal can't do this!\r\n", ch);
		return;
	}

	if (!*argument)
	{
		send_to_char(
			"Sql is a command to let us gods, access database easy, it suport all kind of queries.\n"
			"&=LY-=Make sure you understand what you do else this command is most likly not designed for you=-&n\n",
			ch);
		send_to_char("&+WSyntax: 'sql < query | prep <list | #> >'&n\n", ch);
		return;
	}

	wizlog(56, "SQL command executed");
	logit(LOG_WIZ, "SQL command executed");

	rest = one_argument(argument, first);
	rest = one_argument(rest, second);

	if (strstr(first, "prep"))
	{
		if (strstr(second, "list"))
		{
			do_sql(ch,
			       writable_arg("SELECT id, description FROM prepstatement_duris_sql"),
			       0);
		}
		if (!is_number(second))
		{
			//      send_to_char("\n\r&+YTo add prep queries just check how the table 'prepstatement_duris_sql' (&+Wsql desc prepstatement_duris_sql&+Y) and add!&n\n\r", ch);
			send_to_char(
				"&+YSyntax:&n sql prep < list | number > [ desc | sql | run | delete ] [ description | sql code ]\n\r",
				ch);
			return;
		}
		else
		{
			prep_statement = (int)atoi(second);
			rest = one_argument(rest, third);
			rest = skip_spaces(rest);
			if (!*third)
			{
				snprintf(third, MAX_INPUT_LENGTH,
					 "SELECT * FROM prepstatement_duris_sql WHERE id=%d",
					 prep_statement);
				do_sql(ch, third, cmd);
				/* This won't work due to the fact that we're trying a second sql command?
				        if( !qry( third ) )
				        {
				          send_to_char( "Row does not exist: attempting to create..\n\r", ch );
				          snprintf(buf, MAX_STRING_LENGTH, "INSERT INTO prepstatement_duris_sql (id, description) VALUES (%d, 'new')", prep_statement );
				          do_sql( ch, buf, cmd );
				        }
				        else
				        {
				          do_sql( ch, third, cmd );
				        }
				*/
				return;
			}
			if (strstr(third, "run"))
			{
				sql_read_for(
					ch,
					sql_format(
						"SELECT sql_code FROM prepstatement_duris_sql WHERE id=%d",
						prep_statement),
					[](P_char live, const sql_rows &rows)
					{
						if (rows.empty() || !rows[0][0])
						{
							send_to_char(
								"That prepped statement does not exist.\n\r",
								live);
							return;
						}
						char code[MAX_STRING_LENGTH];
						strlcpy(code, rows[0][0], sizeof(code));
						do_sql(live, code, 0);
					});
				return;
			}
			if (strstr(third, "desc"))
			{
				// SECURITY FIX: Escape user input to prevent SQL injection
				char escaped_desc[MAX_STRING_LENGTH * 2 + 1];
				mysql_real_escape_string(DB, escaped_desc, rest, strlen(rest));
				checked_snprintf(
					buf, MAX_STRING_LENGTH,
					"UPDATE prepstatement_duris_sql SET description = '%s' WHERE id='%d'",
					escaped_desc, prep_statement);
				do_sql(ch, buf, 0);
				return;
			}
			if (strstr(third, "sql"))
			{
				// SECURITY FIX: Escape user input to prevent SQL injection
				char escaped_sql[MAX_STRING_LENGTH * 2 + 1];
				mysql_real_escape_string(DB, escaped_sql, rest, strlen(rest));
				if (sql_queue(
					    "UPDATE prepstatement_duris_sql SET sql_code = '%s' WHERE id='%d'",
					    escaped_sql, prep_statement))
				{
					snprintf(buf, MAX_STRING_LENGTH,
						 "Row %d sql_code set to '%s'.\n\r", prep_statement,
						 rest);
					send_to_char(buf, ch);
				}
				return;
			}
			if (strstr(third, "delete"))
			{
				if (sql_queue("DELETE FROM prepstatement_duris_sql WHERE id=%d",
					      prep_statement))
				{
					snprintf(buf, MAX_STRING_LENGTH, "Row %d deleted.\n\r",
						 prep_statement);
					send_to_char(buf, ch);
				}
				return;
			}
		}
	}

	// The query runs on the writer. Its first 100 rows come back, the column names
	// first, with a 101st when there were more.
	const std::string text = argument;
	sql_read_work_for(
		ch,
		[text](MYSQL *connection, sql_rows *rows) -> unsigned int
		{
			if (mysql_real_query(connection, text.data(), text.size()))
				return mysql_errno(connection);
			MYSQL_RES *db = mysql_use_result(connection);
			if (!db)
				return mysql_errno(connection);
			const unsigned int width = mysql_num_fields(db);
			const MYSQL_FIELD *fields = mysql_fetch_fields(db);
			sql_row names;
			for (unsigned int i = 0; i < width; i++)
				names.fields.emplace_back(fields[i].name);
			rows->push_back(std::move(names));
			while (MYSQL_ROW row = mysql_fetch_row(db))
			{
				if (rows->size() > 101)
					continue;
				sql_row copied;
				for (unsigned int i = 0; i < width; i++)
					if (row[i])
						copied.fields.emplace_back(row[i]);
					else
						copied.fields.emplace_back();
				rows->push_back(std::move(copied));
			}
			const unsigned int error_code = mysql_errno(connection);
			mysql_free_result(db);
			return error_code;
		},
		[](P_char live, const sql_rows &rows)
		{
			std::string result;
			char tmp[MAX_STRING_LENGTH];
			for (size_t index = 0; index < rows.size() && index <= 100; ++index)
			{
				for (size_t i = 0; i < rows[index].fields.size(); i++)
				{
					snprintf(tmp, MAX_STRING_LENGTH, " | %-15s&n ",
						 rows[index][i] ? rows[index][i] : "(null)");
					result += tmp;
				}
				result += " |\n\n";
			}
			send_to_char(result.c_str(), live);
			if (rows.size() > 101)
				send_to_char(
					"Result to big, pls use limit. 'select * from blah &+Ylimit 10&n' will show 10 results.\n",
					live);
		});
}

void update_zone_db()
{
	/* update the zones in the database */
	for (int z = 1; z <= top_of_zone_table; z++)
	{
		int number = zone_table[z].number;

		if (!qry("SELECT id FROM zones WHERE number = '%d'", number))
		{
			logit(LOG_DEBUG, "update_zone_db(): qry failed");
			return;
		}

		char name_buff[MAX_STRING_LENGTH];
		mysql_real_escape_string(DB, name_buff, zone_table[z].name,
					 strlen(zone_table[z].name));

		MYSQL_RES *res = mysql_store_result(DB);
		if (mysql_num_rows(res) > 0)
		{
			qry("UPDATE zones SET name = '%s' WHERE number = '%d'", name_buff, number);
		}
		else
		{
			qry("INSERT INTO zones (number, name) VALUES ('%d', '%s')", number,
			    name_buff);
		}
		mysql_free_result(res);
	}

	for (P_obj o = object_list; o; o = o->next)
	{
		int epic_type = 0;

		switch (obj_index[o->R_num].virtual_number)
		{
		case EPIC_SMALL_STONE:
			epic_type = MAX(epic_type, EPIC_ZONE_TYPE_SMALL);
			break;

		case EPIC_LARGE_STONE:
			epic_type = MAX(epic_type, EPIC_ZONE_TYPE_LARGE);
			break;

		case EPIC_MONOLITH:
			epic_type = MAX(epic_type, EPIC_ZONE_TYPE_MONOLITH);
			break;
		}

		if (!epic_type)
			continue;

		int zone_id = obj_zone_id(o);

		if (zone_id >= 0)
		{
			qry("UPDATE zones SET epic_type = '%d' WHERE number = '%d'", epic_type,
			    zone_table[zone_id].number);
		}
	}
	// Boot: memory takes the rows just written.
	sql_load_zones();
}

void show_frag_trophy(P_char ch, P_char who)
{
	if (!IS_PC(who))
		return;

	sql_read_for(
		ch,
		sql_format(
			"select player_data.name, count(*) as cnt from epic_gain, player_data where epic_gain.type_id = player_data.pid and epic_gain.pid = %d and type = 1 group by type_id order by name asc",
			who->only.pc->pid),
		[](P_char live, const sql_rows &rows)
		{
			if (rows.empty())
			{
				send_to_char("&+WYou haven't fragged anyone!\r\n", live);
				return;
			}

			send_to_char("&+gFrag Trophy:\r\n", live);

			char buff[MAX_STRING_LENGTH];
			for (const sql_row &row : rows)
			{
				snprintf(buff, MAX_STRING_LENGTH, " &+g(&+G%2d&+g) &+W%s\r\n",
					 row[1] ? atoi(row[1]) : 0, row[0] ? row[0] : "");
				send_to_char(buff, live);
			}
		});
}

// At most `bytes` bytes of `value`, cut at a UTF-8 character boundary.
static std::string log_entry_field(const char *value, size_t bytes)
{
	std::string field = value ? value : "";
	if (field.size() <= bytes)
		return field;
	size_t end = bytes;
	while (end > 0 && (static_cast<unsigned char>(field[end]) & 0xC0) == 0x80)
		--end;
	field.resize(end);
	return field;
}

void sql_log(P_char ch, const char *kind, const char *format, ...)
{
	static char buff[MAX_STRING_LENGTH];
	buff[0] = '\0';

	if (!ch)
	{
		debug("sql_log called for non-existent ch!");
		return;
	}

	if (!IS_PC(ch))
	{
		debug("sql_log called in sql.c for mobile ch - %s - Vnum %d", GET_NAME(ch),
		      GET_VNUM(ch));
		debug("sql_log kind '%s', format '%s'", kind, format);
		return;
	}

	va_list args;
	int ret;

	va_start(args, format);
	// SECURITY FIX: Replace vsprintf with vsnprintf to prevent buffer overflow
	ret = vsnprintf(buff, sizeof(buff), format, args);
	va_end(args);

	// Check for overflow
	if (ret < 0 || ret >= (int)sizeof(buff))
	{
		debug("sql_log: Message too long or formatting error");
		return;
	}

	// The persistence writer inserts the row, in order with the saves, so the game
	// never waits on the database for a log line. Each field is kept to its column.
	log_entry_snapshot entry;
	entry.logged_at = time(NULL);
	entry.kind = log_entry_field(kind, 255);
	entry.ip_address = log_entry_field(ch->desc ? ch->desc->host : "", 45);
	entry.pid = GET_PID(ch);
	entry.player_name = log_entry_field(GET_NAME(ch), 255);
	if (world && ch->in_room >= 0 && ch->in_room <= top_of_world)
	{
		entry.room_vnum = world[ch->in_room].number;
		const int zone_rnum = world[ch->in_room].zone;
		if (zone_table && zone_rnum >= 0 && zone_rnum <= top_of_zone_table)
			entry.zone_number = zone_table[zone_rnum].number;
	}
	entry.message = log_entry_field(buff, 255);
	static std::atomic<uint64_t> sequence{ 0 };
	const size_t bytes = sizeof(entry) + entry.kind.size() + entry.ip_address.size() +
			     entry.player_name.size() + entry.message.size();
	const player_save_submit_result submitted = persistence_writer_submit(
		persistence_job_kind::log, ++sequence, bytes, [entry = std::move(entry)]()
		{ return log_entry_repository_apply_from_pool(entry); });
	if (submitted != player_save_submit_result::accepted &&
	    submitted != player_save_submit_result::replaced)
		logit(LOG_FILE, "log_entries row not queued: kind=%s pid=%d %s", kind, GET_PID(ch),
		      buff);
}

// The zones rows, read at boot and kept in memory, so the epic stones, zone resets and the
// epic zone lists never wait for the database. A no-reset zone's reset chance changes here
// and is queued. Alignments, last touches and rarity change on other connections (a stone
// touch, the maintenance jobs), so those three are read again on the writer after each.
static std::vector<zone_info> zones;

static zone_info *zone_row(int zone_number)
{
	for (zone_info &zone : zones)
		if (zone.number == zone_number)
			return &zone;
	return nullptr;
}

// Boot only: the game loop is not running yet.
void sql_load_zones(void)
{
	MYSQL_RES *res = db_query(
		"SELECT number, name, epic_type, frequency_mod, zone_freq_mod, epic_level, task_zone, "
		"quest_zone, trophy_zone, suggested_group_size, epic_payout, difficulty, alignment, "
		"UNIX_TIMESTAMP(last_touch), stonecount, reset_perc FROM zones ORDER BY id");
	if (!res)
		return;
	zones.clear();
	while (MYSQL_ROW row = mysql_fetch_row(res))
	{
		zone_info zone = {};
		zone.number = row[0] ? atoi(row[0]) : 0;
		zone.name = row[1] ? row[1] : "";
		zone.epic_type = row[2] ? atoi(row[2]) : 0;
		zone.frequency_mod = row[3] ? atof(row[3]) : 0;
		zone.zone_freq_mod = row[4] ? atof(row[4]) : 0;
		zone.epic_level = row[5] ? atoi(row[5]) : 0;
		zone.task_zone = row[6] && atoi(row[6]);
		zone.quest_zone = row[7] && atoi(row[7]);
		zone.trophy_zone = row[8] && atoi(row[8]);
		zone.suggested_group_size = row[9] ? atoi(row[9]) : 0;
		zone.epic_payout = row[10] ? atoi(row[10]) : 0;
		zone.difficulty = row[11] ? atoi(row[11]) : 0;
		zone.alignment = row[12] ? atoi(row[12]) : 0;
		zone.last_touch = row[13] ? atol(row[13]) : 0;
		zone.stonecount = row[14] ? atoi(row[14]) : 1;
		zone.reset_perc = row[15] ? atoi(row[15]) : 0;
		zones.push_back(zone);
	}
	mysql_free_result(res);
}

void sql_zones_refresh(void)
{
	sql_read("SELECT number, frequency_mod, alignment, UNIX_TIMESTAMP(last_touch) FROM zones",
		 [](bool ok, const sql_rows &rows)
		 {
			 if (!ok)
				 return;
			 for (const sql_row &row : rows)
				 if (zone_info *zone = row[0] ? zone_row(atoi(row[0])) : nullptr)
				 {
					 zone->frequency_mod = row[1] ? atof(row[1]) : 0;
					 zone->alignment = row[2] ? atoi(row[2]) : 0;
					 zone->last_touch = row[3] ? atol(row[3]) : 0;
				 }
		 });
}

const std::vector<zone_info> &sql_zones(void)
{
	return zones;
}

bool get_zone_info(int zone_number, struct zone_info *info)
{
	const zone_info *zone = zone_row(zone_number);
	if (!info || !zone)
		return FALSE;
	*info = *zone;
	return TRUE;
}

void sql_set_zone_reset_perc(int zone_number, int reset_perc)
{
	if (zone_info *zone = zone_row(zone_number))
		zone->reset_perc = reset_perc;
	sql_queue("UPDATE zones SET reset_perc = %d WHERE number = %d", reset_perc, zone_number);
}

// mud_info, read at boot, every minute (so a creation lock set in the database takes hold
// without waiting) and when staff reload it. Nothing waits to read it.
static std::unordered_map<std::string, std::string> mud_info;

static void mud_info_publish(const sql_rows &rows)
{
	mud_info.clear();
	for (const sql_row &row : rows)
		if (row[0])
			mud_info[row[0]] = row[1] ? row[1] : "";
}

// Boot only: the game loop is not running yet.
static void sql_load_mud_info(void)
{
	MYSQL_RES *res = db_query("SELECT name, content FROM mud_info");
	if (!res)
		return;
	sql_rows rows;
	while (MYSQL_ROW row = mysql_fetch_row(res))
	{
		sql_row copied;
		copied.fields.emplace_back(row[0] ? std::optional<std::string>(row[0]) :
						    std::nullopt);
		copied.fields.emplace_back(row[1] ? std::optional<std::string>(row[1]) :
						    std::nullopt);
		rows.push_back(std::move(copied));
	}
	mysql_free_result(res);
	mud_info_publish(rows);
}

void sql_mud_info_refresh(void)
{
	sql_read("SELECT name, content FROM mud_info",
		 [](bool ok, const sql_rows &rows)
		 {
			 if (ok)
				 mud_info_publish(rows);
		 });
}

void sql_mud_info_reload(P_char ch, std::function<void(P_char)> done)
{
	sql_read_for(ch, "SELECT name, content FROM mud_info",
		     [done = std::move(done)](P_char live, const sql_rows &rows)
		     {
			     mud_info_publish(rows);
			     done(live);
		     });
}

string get_mud_info(const char *name)
{
	// An absent row is the normal state of an optional page, such as "lock".
	const auto found = mud_info.find(name ? name : "");
	return found == mud_info.end() ? string() : found->second;
}

bool sql_clear_zone_trophy()
{
	// Update the table zones, set the alignment to 0, where there's an epic stone.
	if (!sql_queue("UPDATE zones SET alignment=0 WHERE epic_type > 0"))
	{
		debug("sql_clear_zone_trophy(): Failed sql UPDATE.. :(");
		return FALSE;
	}

	return TRUE;
}

/* Verify every runtime table and column referenced by sql_pwipe() before the
 * first destructive statement.  This must describe final runtime schema, not
 * migration-only helper tables. */
bool sql_verify_pwipe_manifest(void)
{
	static const char *const tables[] = { "account_bound_rewards",
					      "account_bound_reward_summons",
					      "account_bound_reward_pwipe_state",
					      "account_characters",
					      "account_locker_access",
					      "account_locker_item_affects",
					      "account_locker_item_extra_descr",
					      "account_locker_items",
					      "account_lockers",
					      "alliances",
					      "artifact_bind",
					      "artifacts",
					      "artifacts_mortal",
					      "associations",
					      "auction_bid_history",
					      "auction_item_pickups",
					      "auction_money_pickups",
					      "auctions",
					      "boons",
					      "boons_progress",
					      "boons_shop",
					      "corpse_item_affects",
					      "corpse_item_extra_descr",
					      "corpse_items",
					      "corpses",
					      "ctf_data",
					      "epic_bonus",
					      "epic_gain",
					      "eq_drop",
					      "frag_leaderboard",
					      "guild_members",
					      "guild_ranks",
					      "guild_transactions",
					      "guildhall_rooms",
					      "guildhalls",
					      "guilds",
					      "ip_info",
					      "level_cap",
					      "locker_access",
					      "locker_activity_log",
					      "locker_chests",
					      "locker_item_affects",
					      "locker_item_extra_descr",
					      "locker_items",
					      "locker_kickouts",
					      "locker_session_state",
					      "lockers",
					      "log_entries",
					      "nexus_stones",
					      "offline_messages",
					      "outposts",
					      "persistence_item_events",
					      "persistence_scalar_events",
					      "pkill_event",
					      "pkill_info",
					      "player_affects",
					      "player_data",
					      "player_forged_items",
					      "player_granted_cmds",
					      "player_intros",
					      "player_item_affects",
					      "player_item_extra_descr",
					      "player_items",
					      "player_languages",
					      "player_pet_item_affects",
					      "player_pet_item_extra_descr",
					      "player_pet_items",
					      "player_pets",
					      "player_recipes",
					      "player_shapechanges",
					      "player_skills",
					      "player_spellbooks",
					      "player_timers",
					      "player_undead_slots",
					      "player_witnesses",
					      "poll_options",
					      "poll_votes",
					      "polls",
					      "private_chest_log",
					      "private_chests",
					      "progress",
					      "racewar_stat_mods",
					      "saved_item_affects",
					      "saved_item_extra_descr",
					      "saved_item_recovery_handoff",
					      "saved_items",
					      "season_reset_state",
					      "ship_armor",
					      "ship_cargo_market_mods",
					      "ship_cargo_prices",
					      "ship_crew",
					      "ship_slots",
					      "ships",
					      "shop_trophy",
					      "shopkeeper_affects",
					      "shopkeeper_item_affects",
					      "shopkeeper_item_extra_descr",
					      "shopkeeper_items",
					      "shopkeepers",
					      "statistics",
					      "timers",
					      "world_quest_accomplished",
					      "zone_touches",
					      "zone_trophy",
					      NULL };
	static const char *const columns[][2] = {
		{ "account_bound_rewards", "id" },
		{ "account_bound_rewards", "expires_at" },
		{ "account_bound_rewards", "remaining_pwipes" },
		{ "account_bound_reward_summons", "grant_id" },
		{ "account_bound_reward_summons", "pid" },
		{ "account_bound_reward_summons", "last_summoned_at" },
		{ "account_bound_reward_pwipe_state", "id" },
		{ "account_bound_reward_pwipe_state", "last_processed_at" },
		{ "outposts", "owner_id" },
		{ "outposts", "level" },
		{ "outposts", "walls" },
		{ "outposts", "archers" },
		{ "outposts", "hitpoints" },
		{ "outposts", "territory" },
		{ "outposts", "portal_room" },
		{ "outposts", "resources" },
		{ "outposts", "applied_resources" },
		{ "outposts", "golems" },
		{ "outposts", "meurtriere" },
		{ "outposts", "scouts" },
		{ "nexus_stones", "align" },
		{ "nexus_stones", "last_touched_at" },
		{ "timers", "date" },
		{ "account_characters", "deleted_at" },
		{ "player_data", "active" },
		{ "level_cap", "most_frags" },
		{ "level_cap", "racewar_leader" },
		{ "level_cap", "level" },
		{ "level_cap", "next_update" },
		{ "season_reset_state", "state_id" },
		{ "season_reset_state", "season_epoch" },
		{ "season_reset_state", "reset_status" },
		{ "season_reset_state", "reset_started_at" },
		{ "season_reset_state", "reset_completed_at" },
		{ NULL, NULL }
	};
	char query[8192];
	int pos = snprintf(
		query, sizeof(query),
		"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN (");
	if (pos < 0 || (size_t)pos >= sizeof(query))
		return FALSE;
	int expected_tables = 0;
	for (int i = 0; tables[i] != NULL; i++)
	{
		int written = snprintf(query + pos, sizeof(query) - (size_t)pos, "%s'%s'",
				       i ? "," : "", tables[i]);
		if (written < 0 || (size_t)written >= sizeof(query) - (size_t)pos)
			return FALSE;
		pos += written;
		expected_tables++;
	}
	if (pos + 2 >= (int)sizeof(query))
		return FALSE;
	strcat(query, ")");
	MYSQL_RES *result = db_query("%s", query);
	if (!result)
		return FALSE;
	MYSQL_ROW row = mysql_fetch_row(result);
	bool tables_ok = row && row[0] && atoi(row[0]) == expected_tables;
	mysql_free_result(result);
	if (!tables_ok)
		return FALSE;

	pos = snprintf(
		query, sizeof(query),
		"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND (");
	if (pos < 0 || (size_t)pos >= sizeof(query))
		return FALSE;
	int expected_columns = 0;
	for (int i = 0; columns[i][0] != NULL; i++)
	{
		int written = snprintf(query + pos, sizeof(query) - (size_t)pos,
				       "%s(table_name='%s' AND column_name='%s')", i ? " OR " : "",
				       columns[i][0], columns[i][1]);
		if (written < 0 || (size_t)written >= sizeof(query) - (size_t)pos)
			return FALSE;
		pos += written;
		expected_columns++;
	}
	if (pos + 2 >= (int)sizeof(query))
		return FALSE;
	strcat(query, ")");
	result = db_query("%s", query);
	if (!result)
		return FALSE;
	row = mysql_fetch_row(result);
	bool columns_ok = row && row[0] && atoi(row[0]) == expected_columns;
	mysql_free_result(result);
	return columns_ok;
}

/* Season-reset preflight: verify persistence event schema and auction engines.
 * These are the same checks as sql_verify_boot_database() but are callable
 * from sql_pwipe() as a preflight gate without requiring a fresh boot. */
bool sql_verify_persistence_schema(void)
{
	if (!DB)
		return FALSE;

	/* Verify persistence event columns exist. */
	const char *event_schema_probe =
		"SELECT COUNT(*) FROM information_schema.columns "
		"WHERE table_schema=DATABASE() AND "
		"((table_name='persistence_item_events' AND column_name IN "
		"('id','ts_usec','event_type','item_uid','vnum','item','actor','actor_id','source','target','note','dedupe_key','created_at')) "
		"OR (table_name='persistence_scalar_events' AND column_name IN "
		"('id','event_type','event_key','boot_time','touched_at','zone_number','toucher_pid','group_size','epic_value','alignment_delta','dedupe_key','created_at')))";
	MYSQL_RES *result = db_query("%s", event_schema_probe);
	if (!result)
		return FALSE;
	MYSQL_ROW row = mysql_fetch_row(result);
	bool event_columns_ok = row && row[0] && atoi(row[0]) == 25;
	mysql_free_result(result);
	if (!event_columns_ok)
		return FALSE;

	/* Verify persistence event indexes exist. */
	const char *event_index_probe =
		"SELECT COUNT(*) FROM (SELECT DISTINCT table_name, index_name "
		"FROM information_schema.statistics WHERE table_schema=DATABASE() AND "
		"((table_name='persistence_item_events' AND index_name IN "
		"('PRIMARY','idx_item_uid_ts','idx_event_type_created','uq_item_dedupe')) "
		"OR (table_name='persistence_scalar_events' AND index_name IN "
		"('PRIMARY','idx_scalar_event_key','idx_scalar_zone_time','uq_scalar_dedupe')))) "
		"AS required_indexes";
	result = db_query("%s", event_index_probe);
	if (!result)
		return FALSE;
	row = mysql_fetch_row(result);
	bool event_indexes_ok = row && row[0] && atoi(row[0]) == 8;
	mysql_free_result(result);
	return event_indexes_ok;
}

bool sql_verify_auction_engines(void)
{
	if (!DB)
		return FALSE;

	const char *auction_engine_probe =
		"SELECT COUNT(DISTINCT table_name) FROM information_schema.tables "
		"WHERE table_schema=DATABASE() AND engine='InnoDB' AND table_name IN "
		"('auction_bid_history','auction_item_pickups','auction_money_pickups','auctions')";
	MYSQL_RES *result = db_query("%s", auction_engine_probe);
	if (!result)
		return FALSE;
	MYSQL_ROW row = mysql_fetch_row(result);
	bool auction_engines_ok = row && row[0] && atoi(row[0]) == 4;
	mysql_free_result(result);
	return auction_engines_ok;
}

bool sql_pwipe(int code_verify)
{
	pwipe_crossed_boundary = false;
	logit(LOG_DEBUG, "sql_pwipe: STARTED!");
	if (code_verify == 1723699)
	{
		/* -- Preflight: verify critical tables exist and have correct engines -- */
		logit(LOG_DEBUG, "sql_pwipe: Preflight schema check... .. .");
		send_to_all("Preflight schema check... .. .");
		if (!sql_verify_persistence_schema())
		{
			logit(LOG_DEBUG,
			      "sql_pwipe: Preflight failed: persistence schema incomplete.");
			send_to_all("Preflight FAILED: persistence schema incomplete!\n");
			return FALSE;
		}
		if (!sql_verify_pwipe_manifest())
		{
			logit(LOG_DEBUG,
			      "sql_pwipe: Preflight failed: reset manifest schema incomplete.");
			send_to_all("Preflight FAILED: reset manifest schema incomplete!\n");
			return FALSE;
		}
		/* Verify auction tables are InnoDB (transactional) before reset. */
		if (!sql_verify_auction_engines())
		{
			logit(LOG_DEBUG, "sql_pwipe: Preflight failed: auction tables not InnoDB.");
			send_to_all("Preflight FAILED: auction tables must be InnoDB!\n");
			return FALSE;
		}
		if (!redis_validate_pwipe_state())
		{
			logit(LOG_DEBUG,
			      "sql_pwipe: Preflight failed: fresh Redis administrative connection unavailable.");
			send_to_all("Preflight FAILED: Redis invalidation target unavailable!\n");
			return FALSE;
		}
		if (!sql_begin_pwipe_epoch())
		{
			logit(LOG_DEBUG,
			      "sql_pwipe: Failed to establish durable season reset boundary.");
			send_to_all("Preflight FAILED: season reset boundary unavailable!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "  success!");
		send_to_all("  success!\n");
		logit(LOG_DEBUG, "sql_pwipe: Clearing zone alignments, trophy and touches... .. .");
		send_to_all("Clearing zone alignments, trophy and touches... .. .");
		if (sql_clear_zone_trophy() && qry("DELETE FROM zone_trophy") &&
		    qry("DELETE FROM zone_touches"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing tower ownership... .. .");
		send_to_all("Clearing tower ownership... .. .");
		if (qry("UPDATE outposts SET owner_id='0', level='8', walls='1', archers='0', hitpoints='300000', territory='0',"
			" portal_room='0', resources='0', applied_resources='0', golems='0', meurtriere='0', scouts='0'"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing nexus stone data... .. .");
		send_to_all("Clearing nexus stone data... .. .");
		if (qry("UPDATE nexus_stones SET align='0', last_touched_at=NULL"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing prestige lists... .. .");
		send_to_all("Clearing prestige lists... .. .");
		if (qry("DELETE FROM associations"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing alliances... .. .");
		send_to_all("Clearing alliances... .. .");
		if (qry("DELETE FROM alliances"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing artifact bind data... .. .");
		send_to_all("Clearing artifact bind data... .. .");
		if (qry("DELETE FROM artifact_bind"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing auction data... .. .");
		send_to_all("Clearing auction data... .. .");
		if (qry("DELETE FROM auction_bid_history") &&
		    qry("DELETE FROM auction_item_pickups") &&
		    qry("DELETE FROM auction_money_pickups") && qry("DELETE FROM auctions"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing boon data... .. .");
		send_to_all("Clearing boon data... .. .");
		if (qry("DELETE FROM boons_progress") && qry("DELETE FROM boons"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing ctf data... .. .");
		send_to_all("Clearing ctf data... .. .");
		if (qry("DELETE FROM ctf_data"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing frag data and epic bonus data... .. .");
		send_to_all("Clearing frag data and epic bonus data... .. .");
		if (qry("DELETE FROM epic_bonus") && qry("DELETE FROM epic_gain") &&
		    qry("DELETE FROM progress"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing guild data... .. .");
		send_to_all("Clearing guild data... .. .");
		if (qry("DELETE FROM guild_transactions") && qry("DELETE FROM guildhall_rooms") &&
		    qry("DELETE FROM guildhalls"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing ip info... .. .");
		send_to_all("Clearing ip info... .. .");
		if (qry("DELETE FROM ip_info"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing log entries... .. .");
		send_to_all("Clearing log entries... .. .");
		if (qry("DELETE FROM log_entries"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing offline messages... .. .");
		send_to_all("Clearing offline messages... .. .");
		if (qry("DELETE FROM offline_messages"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing cargo data... .. .");
		send_to_all("Clearing cargo data... .. .");
		if (qry("DELETE FROM ship_cargo_market_mods") &&
		    qry("DELETE FROM ship_cargo_prices"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing timers... .. .");
		send_to_all("Clearing timers... .. .");
		if (qry("UPDATE timers SET date='0'"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing shop data... .. .");
		send_to_all("Clearing shop data... .. .");
		if (qry("DELETE FROM shop_trophy"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing completed quest data... .. .");
		send_to_all("Clearing completed quest data... .. .");
		if (qry("DELETE FROM world_quest_accomplished"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing locker grant list data... .. .");
		send_to_all("Clearing locker grant list data... .. .");
		if (qry("DELETE FROM locker_access"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: player-owned item graphs -- */
		/* Child tables (affects, extra_descr) must be cleared before parent item tables. */
		logit(LOG_DEBUG, "sql_pwipe: Clearing player item subtable data... .. .");
		send_to_all("Clearing player item subtable data... .. .");
		if (qry("DELETE FROM player_item_affects") &&
		    qry("DELETE FROM player_item_extra_descr"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing player items... .. .");
		send_to_all("Clearing player items... .. .");
		if (qry("DELETE FROM player_items"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: player pet graphs -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing player pet subtable data... .. .");
		send_to_all("Clearing player pet subtable data... .. .");
		if (qry("DELETE FROM player_pet_item_affects") &&
		    qry("DELETE FROM player_pet_item_extra_descr") &&
		    qry("DELETE FROM player_pet_items"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing player pets... .. .");
		send_to_all("Clearing player pets... .. .");
		if (qry("DELETE FROM player_pets"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: player character state -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing player character state data... .. .");
		send_to_all("Clearing player character state data... .. .");
		if (qry("DELETE FROM player_affects") && qry("DELETE FROM player_skills") &&
		    qry("DELETE FROM player_spellbooks") && qry("DELETE FROM player_languages") &&
		    qry("DELETE FROM player_timers") && qry("DELETE FROM player_recipes") &&
		    qry("DELETE FROM player_shapechanges") &&
		    qry("DELETE FROM player_undead_slots") && qry("DELETE FROM player_witnesses") &&
		    qry("DELETE FROM player_forged_items") &&
		    qry("DELETE FROM player_granted_cmds") && qry("DELETE FROM player_intros"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: locker/chest graphs -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing locker subtable data... .. .");
		send_to_all("Clearing locker subtable data... .. .");
		if (qry("DELETE FROM locker_item_affects") &&
		    qry("DELETE FROM locker_item_extra_descr") && qry("DELETE FROM locker_items") &&
		    qry("DELETE FROM locker_chests") && qry("DELETE FROM locker_activity_log") &&
		    qry("DELETE FROM locker_kickouts") && qry("DELETE FROM locker_session_state"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing locker data... .. .");
		send_to_all("Clearing locker data... .. .");
		if (qry("DELETE FROM lockers"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: account locker graphs -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing account locker data... .. .");
		send_to_all("Clearing account locker data... .. .");
		if (qry("DELETE FROM account_locker_item_affects") &&
		    qry("DELETE FROM account_locker_item_extra_descr") &&
		    qry("DELETE FROM account_locker_items") &&
		    qry("DELETE FROM account_locker_access") && qry("DELETE FROM account_lockers"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: private chests -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing private chest data... .. .");
		send_to_all("Clearing private chest data... .. .");
		if (qry("DELETE FROM private_chest_log") && qry("DELETE FROM private_chests"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: corpse graphs -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing corpse subtable data... .. .");
		send_to_all("Clearing corpse subtable data... .. .");
		if (qry("DELETE FROM corpse_item_affects") &&
		    qry("DELETE FROM corpse_item_extra_descr") && qry("DELETE FROM corpse_items"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing corpse data... .. .");
		send_to_all("Clearing corpse data... .. .");
		if (qry("DELETE FROM corpses"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: saved item graphs -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing saved item data... .. .");
		send_to_all("Clearing saved item data... .. .");
		if (qry("DELETE FROM saved_item_recovery_handoff") &&
		    qry("DELETE FROM saved_item_affects") &&
		    qry("DELETE FROM saved_item_extra_descr") && qry("DELETE FROM saved_items"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: ship graphs -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing ship subtable data... .. .");
		send_to_all("Clearing ship subtable data... .. .");
		if (qry("DELETE FROM ship_armor") && qry("DELETE FROM ship_crew") &&
		    qry("DELETE FROM ship_slots"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing ship data... .. .");
		send_to_all("Clearing ship data... .. .");
		if (qry("DELETE FROM ships"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: guild membership -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing guild membership data... .. .");
		send_to_all("Clearing guild membership data... .. .");
		if (qry("DELETE FROM guild_members") && qry("DELETE FROM guild_ranks") &&
		    qry("DELETE FROM guilds"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: world/competitive state -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing artifact data... .. .");
		send_to_all("Clearing artifact data... .. .");
		if (qry("DELETE FROM artifacts") && qry("DELETE FROM artifacts_mortal"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing pvp and statistics data... .. .");
		send_to_all("Clearing pvp and statistics data... .. .");
		if (qry("DELETE FROM frag_leaderboard") && qry("DELETE FROM pkill_event") &&
		    qry("DELETE FROM pkill_info") && qry("DELETE FROM statistics") &&
		    qry("DELETE FROM eq_drop") && qry("DELETE FROM racewar_stat_mods"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: shopkeeper graph -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing shopkeeper data... .. .");
		send_to_all("Clearing shopkeeper data... .. .");
		if (qry("DELETE FROM shopkeeper_affects") &&
		    qry("DELETE FROM shopkeeper_item_affects") &&
		    qry("DELETE FROM shopkeeper_item_extra_descr") &&
		    qry("DELETE FROM shopkeeper_items") && qry("DELETE FROM shopkeepers"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: polls and boon shop -- */
		logit(LOG_DEBUG, "sql_pwipe: Clearing poll and boon shop data... .. .");
		send_to_all("Clearing poll and boon shop data... .. .");
		if (qry("DELETE FROM poll_votes") && qry("DELETE FROM poll_options") &&
		    qry("DELETE FROM polls") && qry("DELETE FROM boons_shop"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		/* -- Season-reset manifest: soft-delete account characters -- */
		logit(LOG_DEBUG, "sql_pwipe: Soft-deleting account characters... .. .");
		send_to_all("Soft-deleting account characters... .. .");
		if (qry("UPDATE account_characters SET deleted_at = COALESCE(deleted_at, NOW()) WHERE deleted_at IS NULL"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Deactivating player_data... .. .");
		send_to_all("Deactivating player_data... .. .");
		if (qry("UPDATE player_data SET active = 0"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Clearing persistence event data... .. .");
		send_to_all("Clearing persistence event data... .. .");
		if (qry("DELETE FROM persistence_item_events") &&
		    qry("DELETE FROM persistence_scalar_events"))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "sql_pwipe: Resetting level_cap data... .. .");
		send_to_all("Resetting level_cap data... .. .");
		if (qry("UPDATE level_cap SET most_frags=0, racewar_leader=0, level=%d, next_update=NOW() + INTERVAL %d DAY",
			frag_cap_config_reset_level(), frag_cap_config_reset_timer_days()))
		{
			logit(LOG_DEBUG, "  success!");
			send_to_all("  success!\n");
		}
		else
		{
			logit(LOG_DEBUG, "        failure!");
			send_to_all("        failure!\n");
			return FALSE;
		}
		if (!redis_clear_pwipe_state())
		{
			logit(LOG_DEBUG, "sql_pwipe: Redis pwipe invalidation failed.");
			return FALSE;
		}
		/* -- Postflight: verify critical season-scoped tables are empty -- */
		logit(LOG_DEBUG, "sql_pwipe: Postflight invariant check... .. .");
		send_to_all("Postflight invariant check... .. .");
		{
			/* Verify that player_items, player_pets, lockers, ships, guilds, and
			 * persistence event tables are all empty after reset. */
			const char *postflight_tables[] = { "player_items",
							    "player_pets",
							    "player_affects",
							    "player_skills",
							    "player_spellbooks",
							    "player_languages",
							    "player_timers",
							    "lockers",
							    "locker_items",
							    "private_chests",
							    "corpses",
							    "corpse_items",
							    "saved_items",
							    "ships",
							    "ship_slots",
							    "ship_crew",
							    "ship_armor",
							    "guilds",
							    "guild_members",
							    "guild_ranks",
							    "artifacts",
							    "frag_leaderboard",
							    "statistics",
							    "persistence_item_events",
							    "persistence_scalar_events",
							    "polls",
							    "shopkeepers",
							    NULL };
			bool postflight_ok = TRUE;
			for (int i = 0; postflight_tables[i] != NULL; i++)
			{
				MYSQL_RES *res =
					db_query("SELECT COUNT(*) FROM %s", postflight_tables[i]);
				if (res)
				{
					MYSQL_ROW row = mysql_fetch_row(res);
					if (row && row[0] && atoi(row[0]) > 0)
					{
						logit(LOG_DEBUG,
						      "sql_pwipe: Postflight FAILED: %s has %s rows.",
						      postflight_tables[i], row[0]);
						postflight_ok = FALSE;
					}
					mysql_free_result(res);
				}
				else
				{
					logit(LOG_DEBUG,
					      "sql_pwipe: Postflight FAILED: cannot query %s.",
					      postflight_tables[i]);
					postflight_ok = FALSE;
				}
			}
			/* Verify player_data is all inactive. */
			MYSQL_RES *res =
				db_query("SELECT COUNT(*) FROM player_data WHERE active = 1");
			if (res)
			{
				MYSQL_ROW row = mysql_fetch_row(res);
				if (row && row[0] && atoi(row[0]) > 0)
				{
					logit(LOG_DEBUG,
					      "sql_pwipe: Postflight FAILED: %d active player_data rows.",
					      atoi(row[0]));
					postflight_ok = FALSE;
				}
				mysql_free_result(res);
			}
			else
			{
				logit(LOG_DEBUG,
				      "sql_pwipe: Postflight FAILED: cannot query player_data active count.");
				postflight_ok = FALSE;
			}
			/* Verify account_characters are all soft-deleted. */
			res = db_query(
				"SELECT COUNT(*) FROM account_characters WHERE deleted_at IS NULL");
			if (res)
			{
				MYSQL_ROW row = mysql_fetch_row(res);
				if (row && row[0] && atoi(row[0]) > 0)
				{
					logit(LOG_DEBUG,
					      "sql_pwipe: Postflight FAILED: %d active account_characters rows.",
					      atoi(row[0]));
					postflight_ok = FALSE;
				}
				mysql_free_result(res);
			}
			else
			{
				logit(LOG_DEBUG,
				      "sql_pwipe: Postflight FAILED: cannot query account_characters.");
				postflight_ok = FALSE;
			}
			if (!postflight_ok)
			{
				logit(LOG_DEBUG, "sql_pwipe: Postflight invariants failed.");
				send_to_all(
					"Postflight FAILED: season-reset invariants not satisfied!\n");
				return FALSE;
			}
		}
		if (!account_bound_rewards_on_successful_pwipe())
		{
			logit(LOG_DEBUG,
			      "sql_pwipe: account reward pwipe policy failed; preserving rewards for manual review.");
			send_to_all(
				"Account reward pwipe policy FAILED; rewards are being preserved for manual review.\n");
		}
		if (!sql_complete_pwipe_epoch())
		{
			logit(LOG_DEBUG,
			      "sql_pwipe: Reset data cleared but season state completion failed; shutdown remains fenced.");
			send_to_all(
				"Season reset completion FAILED; server will remain stopped for recovery.\n");
			return FALSE;
		}
		logit(LOG_DEBUG, "  success!");
		send_to_all("  success!\n");
		logit(LOG_DEBUG, "sql_pwipe: COMPLETED!");
		send_to_all("WIPE COMPLETED!");
		sleep(1);
		return TRUE;
	}
	else
	{
		logit(LOG_DEBUG,
		      "sql_pwipe: Someone called sql_pwipe with a bad verify code... hrm..");
		return FALSE;
	}
}

void sql_log_player_login(P_char ch, const char *status)
{
	if (!ch || IS_NPC(ch) || !status)
		return;
	const session_audit_event event = !strcasecmp(status, "login") ?
						  session_audit_event::login :
						  session_audit_event::logout;
	if (strcasecmp(status, "login") && strcasecmp(status, "logout"))
		return;
	if (!session_audit_transaction_submit(ch, event))
		logit(LOG_FILE,
		      "session_audit: component=submit outcome=unavailable actor=redacted");
}

static item_owner_type sql_persistence_owner_type(const char *owner_type)
{
	if (!strcmp(owner_type, "player"))
		return item_owner_type::player;
	if (!strcmp(owner_type, "container"))
		return item_owner_type::container;
	if (!strcmp(owner_type, "room"))
		return item_owner_type::room;
	if (!strcmp(owner_type, "corpse"))
		return item_owner_type::corpse;
	if (!strcmp(owner_type, "locker"))
		return item_owner_type::locker;
	if (!strcmp(owner_type, "auction"))
		return item_owner_type::auction;
	if (!strcmp(owner_type, "shopkeeper"))
		return item_owner_type::shopkeeper;
	if (!strcmp(owner_type, "collector"))
		return item_owner_type::collector;
	return item_owner_type::unknown;
}

// The rule below for an item_current_owner row already read: root, parent (0 for
// none), owner type, id and context, item revision, vnum, state and owner revision,
// or NULL when the item has no row.
static bool sql_persistence_owner_row_matches(unsigned long long item_uid,
					      const item_owner_identity &expected,
					      const char *const *row)
{
	if (!row)
		return true;
	item_ownership_runtime_entry entry = {
		.item_uid = item_uid,
		.root_item_uid = strtoull(row[0], NULL, 10),
		.parent_item_uid = strtoull(row[1], NULL, 10),
		.owner = { static_cast<item_owner_type>(strtoul(row[2], NULL, 10)),
			   strtoull(row[3], NULL, 10), strtoull(row[4], NULL, 10) },
		.item_revision = strtoull(row[5], NULL, 10),
		.owner_revision = row[8] ? strtoull(row[8], NULL, 10) : 0,
		.vnum = static_cast<int32_t>(strtol(row[6], NULL, 10)),
		.state = static_cast<item_custody_state>(strtoul(row[7], NULL, 10)),
	};
	if (!item_owner_identity_equal(entry.owner, expected))
	{
		dupe_log_item("load_skipped", item_uid, entry.vnum, expected, entry.owner);
		return false;
	}
	// The in-memory ownership catalog still serves item commands that have not moved
	// to memory yet; it only takes an active row.
	if (entry.state == item_custody_state::active && row[8])
		item_ownership_runtime_hydrate(entry);
	return true;
}

/*
 * A load takes an item when item_current_owner has no row for it or names the
 * loading owner, whatever the row's state. A row naming anyone else makes this a
 * stale or duplicate copy: it is skipped and logged to logs/log/dupes, and the
 * owner's next save removes it. A failed lookup keeps the item: losing it would
 * be worse than a copy the next claim settles.
 */
bool sql_persistence_item_owner_matches_identity(unsigned long long item_uid,
						 const char *owner_type,
						 unsigned long long expected_id,
						 unsigned long long expected_context_id,
						 const char *context)
{
	if (item_uid == 0)
		return true;
	if (!owner_type || !context || !DB)
		return false;
	const item_owner_type expected_type = sql_persistence_owner_type(owner_type);
	if (expected_type == item_owner_type::unknown || !expected_id)
		return false;
	char query[512];
	snprintf(query, sizeof(query), "%s WHERE current_item.item_uid=%llu", SQL_ITEM_OWNER_SELECT,
		 item_uid);
	MYSQL_RES *result = db_query("%s", query);
	if (!result)
	{
		logit(LOG_FILE, "sql_persistence: owner lookup failed item_uid=%llu context=%s",
		      item_uid, context);
		return true;
	}
	const bool matches = sql_persistence_owner_row_matches(
		item_uid, { expected_type, expected_id, expected_context_id },
		mysql_fetch_row(result));
	mysql_free_result(result);
	return matches;
}

bool sql_persistence_item_owner_fields_match(unsigned long long item_uid, const char *owner_type,
					     unsigned long long expected_id,
					     unsigned long long expected_context_id,
					     const char *const *row)
{
	if (item_uid == 0)
		return true;
	const item_owner_type expected_type = sql_persistence_owner_type(owner_type);
	return expected_type != item_owner_type::unknown && expected_id &&
	       sql_persistence_owner_row_matches(
		       item_uid, { expected_type, expected_id, expected_context_id }, row);
}

bool sql_persistence_item_owner_matches(unsigned long long item_uid, const char *owner_type,
					const char *owner_ref, const char *context)
{
	if (item_uid == 0)
		return true;
	if (!owner_ref)
		return false;
	char *owner_end = NULL;
	errno = 0;
	const unsigned long long owner_id = strtoull(owner_ref, &owner_end, 10);
	if (errno || !owner_end || *owner_end || !owner_id)
		return false;
	return sql_persistence_item_owner_matches_identity(item_uid, owner_type, owner_id, 0,
							   context);
}

bool sql_persistence_reconcile_world_recovery_items(const world_recovery_authority_item *items,
						    size_t count,
						    item_ownership_runtime_entry *authoritative,
						    size_t authoritative_capacity)
{
	constexpr size_t QUERY_BATCH_SIZE = 256;
	constexpr size_t MAX_RECOVERY_ITEMS = 262144;
	if ((!items && count) || (!authoritative && count) || count > MAX_RECOVERY_ITEMS ||
	    authoritative_capacity != count || !DB || sql_in_transaction())
		return false;
	if (!count)
		return true;
	std::unordered_map<uint64_t, const world_recovery_authority_item *> expected;
	size_t authoritative_count = 0;
	try
	{
		expected.reserve(count);
		for (size_t index = 0; index < count; ++index)
			if (!items[index].item_uid || !items[index].root_item_uid ||
			    !items[index].room_vnum || items[index].vnum <= 0 ||
			    !expected.emplace(items[index].item_uid, &items[index]).second)
				return false;
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	if (!sql_begin_transaction())
		return false;
	bool valid = true;
	for (size_t begin = 0; valid && begin < count; begin += QUERY_BATCH_SIZE)
	{
		const size_t end = std::min(count, begin + QUERY_BATCH_SIZE);
		std::string query =
			"SELECT current_item.item_uid,current_item.root_item_uid,"
			"COALESCE(current_item.parent_item_uid,0),current_item.owner_type,"
			"current_item.owner_id,current_item.owner_context_id,"
			"current_item.item_revision,current_item.vnum,current_item.state,"
			"owner.revision FROM item_current_owner current_item JOIN "
			"item_owner_revision owner ON owner.owner_type=current_item.owner_type "
			"AND owner.owner_id=current_item.owner_id AND "
			"owner.owner_context_id=current_item.owner_context_id WHERE "
			"current_item.item_uid IN (";
		try
		{
			for (size_t index = begin; index < end; ++index)
			{
				if (index != begin)
					query.push_back(',');
				query += std::to_string(items[index].item_uid);
			}
			query.push_back(')');
		}
		catch (const std::bad_alloc &)
		{
			valid = false;
			break;
		}
		MYSQL_RES *result = db_query("%s", query.c_str());
		if (!result)
		{
			valid = false;
			break;
		}
		MYSQL_ROW row;
		while (valid && (row = mysql_fetch_row(result)))
		{
			const uint64_t item_uid = row[0] ? strtoull(row[0], NULL, 10) : 0;
			const auto found = expected.find(item_uid);
			if (found == expected.end())
			{
				valid = false;
				break;
			}
			const world_recovery_authority_item &planned = *found->second;
			item_ownership_runtime_entry entry = {
				.item_uid = item_uid,
				.root_item_uid = row[1] ? strtoull(row[1], NULL, 10) : 0,
				.parent_item_uid = row[2] ? strtoull(row[2], NULL, 10) : 0,
				.owner = { row[3] ? static_cast<item_owner_type>(
							    strtoul(row[3], NULL, 10)) :
						    item_owner_type::unknown,
					   row[4] ? strtoull(row[4], NULL, 10) : 0,
					   row[5] ? strtoull(row[5], NULL, 10) : 0 },
				.item_revision = row[6] ? strtoull(row[6], NULL, 10) : 0,
				.owner_revision = row[9] ? strtoull(row[9], NULL, 10) : 0,
				.vnum = row[7] ? static_cast<int32_t>(strtol(row[7], NULL, 10)) : 0,
				.state = row[8] ? static_cast<item_custody_state>(
							  strtoul(row[8], NULL, 10)) :
						  item_custody_state::absent,
			};
			if (entry.root_item_uid != planned.root_item_uid ||
			    entry.parent_item_uid != planned.parent_item_uid ||
			    entry.owner.type != item_owner_type::room ||
			    entry.owner.id != static_cast<uint64_t>(planned.room_vnum) ||
			    entry.owner.context_id != 0 || entry.vnum != planned.vnum ||
			    entry.state != item_custody_state::active)
			{
				valid = false;
				break;
			}
			try
			{
				if (authoritative_count >= authoritative_capacity)
				{
					valid = false;
					break;
				}
				authoritative[authoritative_count++] = entry;
			}
			catch (const std::bad_alloc &)
			{
				valid = false;
			}
		}
		mysql_free_result(result);
	}
	valid = valid && authoritative_count == count;
	if (valid)
	{
		valid = sql_commit();
		if (!valid)
			sql_rollback();
	}
	else
		sql_rollback();
	if (!valid)
		return false;
	return true;
}

bool sql_persistence_world_recovery_items_owned(const std::vector<uint64_t> &item_uids,
						std::unordered_set<uint64_t> *owned)
{
	constexpr size_t QUERY_BATCH_SIZE = 256;
	if (!owned || !DB)
		return false;
	try
	{
		for (size_t begin = 0; begin < item_uids.size(); begin += QUERY_BATCH_SIZE)
		{
			const size_t end = std::min(item_uids.size(), begin + QUERY_BATCH_SIZE);
			std::string query =
				"SELECT own.item_uid FROM item_current_owner own WHERE NOT "
				"(own.owner_type=" +
				std::to_string(static_cast<unsigned>(item_owner_type::player)) +
				" AND own.state=" +
				std::to_string(static_cast<unsigned>(item_custody_state::active)) +
				" AND NOT EXISTS (SELECT 1 FROM player_items held WHERE "
				"held.obj_uid=own.item_uid AND held.pid=own.owner_id)) AND "
				"own.item_uid IN (";
			for (size_t index = begin; index < end; ++index)
			{
				if (index != begin)
					query.push_back(',');
				query += std::to_string(item_uids[index]);
			}
			query.push_back(')');
			MYSQL_RES *result = db_query("%s", query.c_str());
			if (!result)
				return false;
			MYSQL_ROW row;
			while ((row = mysql_fetch_row(result)))
				owned->insert(strtoull(row[0], NULL, 10));
			mysql_free_result(result);
		}
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	return true;
}

bool sql_hydrate_item_owner_revisions(void)
{
	if (!DB)
		return false;
	MYSQL_RES *result = db_query(
		"SELECT owner_type,owner_id,owner_context_id,revision FROM item_owner_revision");
	if (!result)
		return false;
	bool ok = true;
	MYSQL_ROW row;
	while ((row = mysql_fetch_row(result)))
	{
		const item_owner_identity owner = {
			static_cast<item_owner_type>(strtoul(row[0], NULL, 10)),
			strtoull(row[1], NULL, 10), strtoull(row[2], NULL, 10)
		};
		if (!item_ownership_runtime_hydrate_owner(owner, strtoull(row[3], NULL, 10)))
		{
			ok = false;
			break;
		}
	}
	mysql_free_result(result);
	return ok;
}

#endif
