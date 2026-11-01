/*
 * gmcp.c - gmcp protocol for durismud
 *
 * sends game data to clients via telnet or websocket.
 */

#include "core/prototypes.h"
#include "cmd/interp.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "core/utils.h"
#include "net/gmcp.h"
#include <cjson/cJSON.h>
#include <math.h>
#include <algorithm>
#include <ctype.h>
#include <mysql.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unordered_map>
#include "world/handler.h"
#include "core/json_utils.h"
#include "world/map.h"
#include "ships/ships.h"
#include "magic/spells.h"
#include "sql/sql.h"
#include "net/websocket.h"
#include "net/ws_auth.h"
#include "persistence/latency_trace.h"

extern const int top_of_world;

/* externs */
extern struct room_data *world;
extern struct zone_data *zone_table;
extern const char *pc_class_types[];
extern struct descriptor_data *descriptor_list;
extern const struct class_names class_names_table[];
extern const struct race_names race_names_table[];

extern struct time_info_data time_info;

// New-stream control and time. Kept together for executable production-path tests.
static bool gmcp_queue(struct descriptor_data *d, const char *package, const char *json);
static void gmcp_flush_combat(P_desc d);
static uint64_t gmcp_clock_revision;
static int gmcp_clock_hour = -1;
static char gmcp_clock_json[128];
static char gmcp_session_process[33];

static bool gmcp_streaming_enabled(P_desc d)
{
	return d && d->gmcp_enabled && !d->write_failed &&
	       (!d->character || !PLR3_FLAGGED(GET_TRUE_CHAR(d->character), PLR3_NOGMCP));
}

enum class gmcp_session_phase : unsigned char
{
	account,
	chargen,
	playing
};

static P_char gmcp_session_player(P_desc d)
{
	P_char player = d ? GET_TRUE_CHAR_D(d) : nullptr;
	return player && IS_PC(player) ? player : nullptr;
}

static bool gmcp_session_supported(P_desc d)
{
	return d && d->gmcp_enabled &&
	       (d->gmcp_supports & (GMCP_SUPPORT_CAPABILITIES | GMCP_SUPPORT_SESSION)) ==
		       (GMCP_SUPPORT_CAPABILITIES | GMCP_SUPPORT_SESSION);
}

static gmcp_session_phase gmcp_session_current_phase(P_desc d)
{
	if (STATE(d) == CON_PLAYING && d->character && gmcp_session_player(d))
		return gmcp_session_phase::playing;
	if (d->websocket && d->chargen_phase != CHARGEN_UNSTARTED)
		return gmcp_session_phase::chargen;
	switch (STATE(d))
	{
	case CON_ACCT_NEW_CHAR:
	case CON_ACCT_NEW_CHAR_NAME:
	case CON_APPROPRIATE_NAME:
	case CON_NEW_NAME:
	case CON_NAME_CONF:
	case CON_GET_SEX:
	case CON_GET_RACE:
	case CON_GET_CLASS:
	case CON_HARDCORE:
	case CON_NEWBIE:
	case CON_STAT_METHOD:
	case CON_REROLL:
	case CON_BONUS1:
	case CON_BONUS2:
	case CON_BONUS3:
	case CON_BONUS4:
	case CON_BONUS5:
	case CON_SWAPSTATYN:
	case CON_SWAPSTAT:
	case CON_ALIGN:
	case CON_HOMETOWN:
	case CON_KEEPCHAR:
	case CON_RMOTD:
	case CON_ACCEPTWAIT:
		return gmcp_session_phase::chargen;
	default:
		return gmcp_session_phase::account;
	}
}

static void gmcp_session_observe(P_desc d)
{
	const auto phase = gmcp_session_current_phase(d);
	const bool playing = phase == gmcp_session_phase::playing;
	const uint64_t player = playing ? gmcp_session_player(d)->runtime_id : 0;
	const uint64_t body = playing ? d->character->runtime_id : 0;
	const bool entry = playing && (d->gmcp_session_state != static_cast<unsigned char>(phase) ||
				       d->gmcp_session_player != player);
	const bool changed = d->gmcp_session_state != static_cast<unsigned char>(phase) ||
			     d->gmcp_session_player != player || d->gmcp_session_body != body;
	if (entry)
	{
		++d->gmcp_session_generation;
		d->gmcp_session_body_revision = 1;
		d->gmcp_session_resumed = false;
	}
	else if (playing && body != d->gmcp_session_body)
		++d->gmcp_session_body_revision;
	if (d->gmcp_session_state != static_cast<unsigned char>(phase) || entry)
		d->gmcp_time_revision = 0;
	if (changed)
	{
		d->gmcp_combat_state_sent = false;
		if (playing && gmcp_session_supported(d))
			d->gmcp_initial_state_pending = true;
		d->gmcp_session_state = static_cast<unsigned char>(phase);
		d->gmcp_session_player = player;
		d->gmcp_session_body = body;
		d->gmcp_session_pending = true;
	}
}

static bool gmcp_time_active(P_desc d)
{
	return gmcp_streaming_enabled(d) && STATE(d) == CON_PLAYING && d->character &&
	       gmcp_session_player(d) && (d->gmcp_supports & GMCP_SUPPORT_CAPABILITIES) &&
	       (d->gmcp_supports & d->gmcp_interests & GMCP_SUPPORT_TIME);
}

void gmcp_preferences_changed(P_desc d)
{
	if (!d)
		return;
	if (d->gmcp_enabled && (d->gmcp_supports & GMCP_SUPPORT_CAPABILITIES))
		d->gmcp_control_pending = true;
	d->gmcp_time_revision = 0;
	if (gmcp_session_supported(d))
		d->gmcp_session_pending = true;
}

static void gmcp_flush_capabilities(P_desc d)
{
	if (!d || !d->gmcp_enabled || d->write_failed ||
	    (!(d->gmcp_supports & GMCP_SUPPORT_CAPABILITIES) && !d->gmcp_control_pending))
		return;
	const uint32_t active = gmcp_time_active(d) ? GMCP_SUPPORT_TIME : 0;
	if (active != d->gmcp_active_streams)
	{
		d->gmcp_control_pending = true;
		d->gmcp_time_revision = 0;
	}
	if (!d->gmcp_control_pending)
		return;
	char json[512];
	const int length = snprintf(
		json, sizeof(json),
		"{\"version\":1,\"enabled\":%s,\"features\":{\"Duris.Capabilities\":1,"
		"\"Duris.Subscribe\":1,\"Duris.Time\":1,\"Duris.Session\":1},\"supported\":[%s],"
		"\"interested\":[%s],\"active\":[%s],\"control\":[%s]}",
		gmcp_streaming_enabled(d) ? "true" : "false",
		d->gmcp_supports & GMCP_SUPPORT_TIME ? "\"Duris.Time\"" : "",
		d->gmcp_interests & GMCP_SUPPORT_TIME ? "\"Duris.Time\"" : "",
		gmcp_time_active(d) ? "\"Duris.Time\"" : "",
		gmcp_session_supported(d) ? "\"Duris.Session\"" : "");
	if (length > 0 && static_cast<size_t>(length) < sizeof(json) &&
	    gmcp_queue(d, "Duris.Capabilities", json))
	{
		d->gmcp_control_pending = false;
		d->gmcp_active_streams = active;
	}
}

static bool gmcp_session_nonce(char (&output)[33])
{
	if (output[0])
		return true;
	unsigned char nonce[16];
	if (RAND_bytes(nonce, sizeof(nonce)) != 1)
		return false;
	for (size_t index = 0; index < sizeof(nonce); ++index)
		snprintf(output + index * 2, 3, "%02x", nonce[index]);
	return true;
}

static bool gmcp_session_send(P_desc d, gmcp_session_phase phase, uint64_t generation)
{
	if (!gmcp_session_nonce(d->gmcp_session_context) ||
	    !gmcp_session_nonce(gmcp_session_process))
		return false;
	cJSON *root = cJSON_CreateObject();
	if (!root)
		return false;
	char counter[21];
	snprintf(counter, sizeof(counter), "%llu", static_cast<unsigned long long>(generation));
	cJSON *character = phase == gmcp_session_phase::playing ? cJSON_CreateObject() :
								  cJSON_CreateNull();
	bool valid = character &&
		     cJSON_AddStringToObject(root, "context", d->gmcp_session_context) &&
		     cJSON_AddStringToObject(root, "process", gmcp_session_process) &&
		     cJSON_AddStringToObject(root, "generation", counter) &&
		     cJSON_AddStringToObject(root, "state",
					     phase == gmcp_session_phase::playing ? "playing" :
					     phase == gmcp_session_phase::chargen ? "chargen" :
										    "account") &&
		     cJSON_AddBoolToObject(root, "resumed", d->gmcp_session_resumed);
	if (valid && phase == gmcp_session_phase::playing)
	{
		char name[MAX_NAME_LENGTH + 1];
		strlcpy(name, GET_NAME(gmcp_session_player(d)), sizeof(name));
		snprintf(counter, sizeof(counter), "%llu",
			 static_cast<unsigned long long>(d->gmcp_session_body_revision));
		valid = cJSON_AddStringToObject(character, "name", name) &&
			cJSON_AddStringToObject(character, "bodyRevision", counter);
	}
	if (!valid || !cJSON_AddItemToObject(root, "character", character))
	{
		cJSON_Delete(character);
		cJSON_Delete(root);
		return false;
	}
	char *json = cJSON_PrintUnformatted(root);
	cJSON_Delete(root);
	if (!json)
		return false;
	const bool accepted = gmcp_queue(d, "Duris.Session", json);
	free(json);
	return accepted;
}

static void gmcp_flush_session(P_desc d)
{
	if (d->write_failed || !gmcp_session_supported(d) || !d->gmcp_session_pending ||
	    d->gmcp_control_pending)
		return;
	const auto phase = static_cast<gmcp_session_phase>(d->gmcp_session_state);
	if (d->gmcp_session_sent &&
	    d->gmcp_session_sent_state == static_cast<unsigned char>(gmcp_session_phase::playing) &&
	    (phase != gmcp_session_phase::playing ||
	     d->gmcp_session_sent_generation != d->gmcp_session_generation))
	{
		const auto clear =
			phase == gmcp_session_phase::playing ? gmcp_session_phase::account : phase;
		if (!gmcp_session_send(d, clear, d->gmcp_session_sent_generation))
			return;
		d->gmcp_session_sent_state = static_cast<unsigned char>(clear);
		if (phase != gmcp_session_phase::playing &&
		    d->gmcp_session_sent_generation == d->gmcp_session_generation)
		{
			d->gmcp_session_pending = false;
			return;
		}
	}
	if (!gmcp_session_send(d, phase, d->gmcp_session_generation))
		return;
	d->gmcp_session_sent = true;
	d->gmcp_session_sent_state = static_cast<unsigned char>(phase);
	d->gmcp_session_sent_generation = d->gmcp_session_generation;
	d->gmcp_session_pending = false;
}

void gmcp_session_update(P_desc d)
{
	if (!d)
		return;
	gmcp_session_observe(d);
	gmcp_flush_capabilities(d);
	gmcp_flush_session(d);
}

void gmcp_session_restored(P_desc d)
{
	d->gmcp_session_state = static_cast<unsigned char>(gmcp_session_phase::playing);
	d->gmcp_session_player = gmcp_session_player(d)->runtime_id;
	d->gmcp_session_body = d->character->runtime_id;
	if (!d->gmcp_session_generation)
		d->gmcp_session_generation = 1;
	if (!d->gmcp_session_body_revision)
		d->gmcp_session_body_revision = 1;
	d->gmcp_session_resumed = true;
	d->gmcp_session_pending = true;
	d->gmcp_session_sent = false;
	d->gmcp_initial_state_pending = d->gmcp_enabled != 0;
	gmcp_preferences_changed(d);
}

void gmcp_time_changed(void)
{
	// The clock owns mutation. Even malformed old time data cannot escape the wire range.
	const int hour = (time_info.hour % 24 + 24) % 24;
	if (hour == gmcp_clock_hour)
		return;
	gmcp_clock_hour = hour;
	++gmcp_clock_revision;
	gmcp_clock_json[0] = '\0';
}

static void gmcp_flush_time(P_desc d)
{
	// No JSON construction, clock work or traversal for an uninterested descriptor.
	if (!gmcp_time_active(d) || d->gmcp_control_pending ||
	    (gmcp_session_supported(d) && d->gmcp_session_pending))
		return;
	gmcp_time_changed();
	if (d->gmcp_time_revision == gmcp_clock_revision)
		return;
	if (!gmcp_clock_json[0])
	{
		if (!gmcp_session_nonce(gmcp_session_process))
			return;
		const char *phase = gmcp_clock_hour >= 4 && gmcp_clock_hour <= 8   ? "dawn" :
				    gmcp_clock_hour >= 9 && gmcp_clock_hour <= 15  ? "day" :
				    gmcp_clock_hour >= 16 && gmcp_clock_hour <= 18 ? "dusk" :
										     "night";
		snprintf(gmcp_clock_json, sizeof(gmcp_clock_json),
			 "{\"revision\":\"%llu\",\"hour\":%d,\"phase\":\"%s\",\"process\":\"%s\"}",
			 static_cast<unsigned long long>(gmcp_clock_revision), gmcp_clock_hour,
			 phase, gmcp_session_process);
	}
	if (gmcp_queue(d, "Duris.Time", gmcp_clock_json))
		d->gmcp_time_revision = gmcp_clock_revision;
}

static bool gmcp_control_request_allowed(P_desc d, unsigned family)
{
	const uint64_t now = latency_trace_monotonic_us() / 1000;
	if (!now)
		return false;
	uint64_t &refill = d->gmcp_request_refill_ms[family];
	unsigned char &tokens = d->gmcp_request_tokens[family];
	if (!refill)
	{
		refill = now;
		tokens = 2;
	}
	if (now < refill)
		return false;
	const uint64_t elapsed = (now - refill) / 1000;
	if (elapsed)
	{
		tokens = static_cast<unsigned char>(
			std::min<uint64_t>(2, tokens + std::min<uint64_t>(2, elapsed)));
		refill += elapsed * 1000;
	}
	if (!tokens)
		return false;
	--tokens;
	return true;
}

enum class gmcp_control_kind
{
	unknown,
	set,
	add,
	remove,
	subscribe
};

static gmcp_control_kind gmcp_control_package(const char *package, size_t size)
{
	const auto named = [&](const char *name)
	{ return size == strlen(name) && !memcmp(package, name, size); };
	if (named("Core.Supports.Set"))
		return gmcp_control_kind::set;
	if (named("Core.Supports.Add"))
		return gmcp_control_kind::add;
	if (named("Core.Supports.Remove"))
		return gmcp_control_kind::remove;
	if (named("Duris.Subscribe"))
		return gmcp_control_kind::subscribe;
	return gmcp_control_kind::unknown;
}

static bool gmcp_control_begin(P_desc d, gmcp_control_kind kind, const char *raw, size_t len)
{
	if (!d->gmcp_enabled || len > GMCP_CONTROL_MAX_INPUT_SIZE || memchr(raw, '\0', len) ||
	    !gmcp_control_request_allowed(d, kind == gmcp_control_kind::subscribe ? 1 : 0))
		return false;
	// cJSON strings have no stored length. This check must precede WebSocket reserialization.
	for (size_t index = 0; index + 6 <= len; ++index)
		if (!memcmp(raw + index, "\\u0000", 6))
			return false;
	return true;
}

static void gmcp_apply_control(P_desc d, gmcp_control_kind kind, const cJSON *array)
{
	if (!cJSON_IsArray(array))
		return;
	uint32_t requested = 0;
	size_t count = 0;
	const cJSON *entry;
	cJSON_ArrayForEach(entry, array)
	{
		if (++count > GMCP_CONTROL_MAX_ENTRIES || !cJSON_IsString(entry) ||
		    strnlen(entry->valuestring, GMCP_CONTROL_MAX_ENTRY_BYTES + 1) >
			    GMCP_CONTROL_MAX_ENTRY_BYTES)
			return;
		if (!strcmp(entry->valuestring, "Duris.Capabilities 1"))
			requested |= GMCP_SUPPORT_CAPABILITIES;
		else if (!strcmp(entry->valuestring, "Duris.Time 1"))
			requested |= GMCP_SUPPORT_TIME;
		else if (!strcmp(entry->valuestring, "Duris.Session 1"))
			requested |= GMCP_SUPPORT_SESSION;
	}
	const bool had_control = d->gmcp_supports & GMCP_SUPPORT_CAPABILITIES;
	if (kind == gmcp_control_kind::subscribe)
	{
		if (!had_control)
			return;
		d->gmcp_interests = requested & d->gmcp_supports & GMCP_INTEREST_STREAMS;
	}
	else
	{
		if (kind == gmcp_control_kind::set)
			d->gmcp_supports = requested;
		else if (kind == gmcp_control_kind::add)
			d->gmcp_supports |= requested;
		else
			d->gmcp_supports &= ~requested;
		d->gmcp_interests &= d->gmcp_supports;
		if (!(d->gmcp_supports & GMCP_SUPPORT_CAPABILITIES))
			d->gmcp_interests = 0;
	}
	d->gmcp_control_pending = d->gmcp_control_pending || had_control ||
				  (d->gmcp_supports & GMCP_SUPPORT_CAPABILITIES);
	d->gmcp_time_revision = 0;
	if (gmcp_session_supported(d))
		d->gmcp_session_pending = true;
}

static bool gmcp_handle_control(P_desc d, const char *data, size_t len)
{
	const char *space = static_cast<const char *>(
		memchr(data, ' ', std::min<size_t>(len, GMCP_MAX_PACKAGE_SIZE)));
	const auto kind =
		gmcp_control_package(data, space ? static_cast<size_t>(space - data) : len);
	if (kind == gmcp_control_kind::unknown)
		return false;
	if (!space || !gmcp_control_begin(d, kind, data, len))
		return true;
	const char *json = space + 1;
	const char *end = nullptr;
	cJSON *root =
		cJSON_ParseWithLengthOpts(json, len - static_cast<size_t>(json - data), &end, 0);
	if (!root)
		return true;
	while (end < data + len && isspace(static_cast<unsigned char>(*end)))
		++end;
	if (end == data + len)
		gmcp_apply_control(d, kind, root);
	cJSON_Delete(root);
	return true;
}

bool gmcp_handle_control_json(P_desc d, const cJSON *message, const char *raw, size_t len,
			      const char *json_end)
{
	const cJSON *package = cJSON_GetObjectItem(message, "package");
	if (!cJSON_IsString(package))
		return false;
	const auto kind = gmcp_control_package(package->valuestring, strlen(package->valuestring));
	if (kind == gmcp_control_kind::unknown)
		return false;
	if (!d || !raw || !json_end || !gmcp_control_begin(d, kind, raw, len))
		return true;
	while (json_end < raw + len && isspace(static_cast<unsigned char>(*json_end)))
		++json_end;
	if (json_end == raw + len)
		gmcp_apply_control(d, kind, cJSON_GetObjectItem(message, "data"));
	return true;
}
// End new-stream control and time.

/* send gmcp negotiation request to client */
void gmcp_negotiate(struct descriptor_data *d)
{
	unsigned char negotiate[3];

	if (!d || d->websocket)
		return; /* WebSocket clients don't need telnet negotiation */

	negotiate[0] = TELNET_IAC;
	negotiate[1] = TELNET_WILL;
	negotiate[2] = TELOPT_GMCP;

	write_to_descriptor_binary(d, negotiate, 3);
}

/* handle gmcp negotiation response */
void gmcp_handle_negotiation(struct descriptor_data *d, int cmd)
{
	if (!d)
		return;

	if (cmd == TELNET_DO)
	{
		bool was_enabled = d->gmcp_enabled;
		d->gmcp_enabled = 1;
		if (!was_enabled)
			gmcp_preferences_changed(d);
		if (!was_enabled && STATE(d) == CON_PLAYING)
			d->gmcp_initial_state_pending = true;
	}
	else if (cmd == TELNET_DONT)
	{
		d->gmcp_enabled = 0;
		d->gmcp_initial_state_pending = false;
		d->gmcp_control_pending = false;
		d->gmcp_active_streams = 0;
		d->gmcp_time_revision = 0;
	}
}

/* Coalesce option toggles until the next periodic GMCP flush. */
void gmcp_flush_initial_states(void)
{
	for (struct descriptor_data *d = descriptor_list; d; d = d->next)
	{
		if (d->gmcp_initial_state_pending && STATE(d) == CON_PLAYING)
		{
			d->gmcp_initial_state_pending = false;
			gmcp_send_initial_state(d->character);
		}
		else
			gmcp_session_update(d);
		gmcp_flush_time(d);
		gmcp_flush_combat(d);
	}
}

static int gmcp_durisweb_auth_limited(struct descriptor_data *d)
{
	return ws_auth_rate_limited(&d->durisweb_auth_window_start, &d->durisweb_auth_failures,
				    WS_AUTH_MAX_FAILURES, WS_AUTH_FAILURE_WINDOW);
}

static void gmcp_durisweb_auth_failure(struct descriptor_data *d)
{
	ws_auth_record_failure(&d->durisweb_auth_window_start, &d->durisweb_auth_failures,
			       WS_AUTH_MAX_FAILURES, WS_AUTH_FAILURE_WINDOW);
	if (d->durisweb_auth_failures >= WS_AUTH_MAX_FAILURES)
		STATE(d) = CON_EXIT;
}

void gmcp_input_receipt(struct descriptor_data *d, const char *input)
{
	if (!d || !d->gmcp_enabled || !d->gmcp_command_receipts ||
	    (input && STATE(d) != CON_PLAYING))
		return;
	if (input)
		++d->gmcp_input_sequence;
	cJSON *root = cJSON_CreateObject();
	cJSON_AddNumberToObject(root, "sequence", d->gmcp_input_sequence);
	if (input)
		cJSON_AddStringToObject(root, "command", input_command_label(input));
	char *json = cJSON_PrintUnformatted(root);
	if (json)
	{
		gmcp_send(d, "Char.Input", json);
		free(json);
	}
	cJSON_Delete(root);
}

/* handle incoming gmcp data from telnet client */
void gmcp_handle_input(struct descriptor_data *d, const char *data, size_t len)
{
	if (!d || !data || len == 0 || len > GMCP_MAX_INPUT_SIZE)
		return;
	if (gmcp_handle_control(d, data, len))
		return;

	if (len > 10 && strncmp(data, "Core.Hello", 10) == 0 && data[10] == ' ')
	{
		const char *end = data + len;
		const char *json_start = data + 10;
		while (json_start < end && *json_start == ' ')
			json_start++;

		if (json_start < end && *json_start == '{')
		{
			cJSON *root = cJSON_ParseWithLength(json_start, (size_t)(end - json_start));
			if (root)
			{
				cJSON *client = cJSON_GetObjectItem(root, "client");
				cJSON *version = cJSON_GetObjectItem(root, "version");
				cJSON *receipts = cJSON_GetObjectItem(root, "commandReceipts");
				if (cJSON_IsBool(receipts))
				{
					d->gmcp_command_receipts = cJSON_IsTrue(receipts);
					gmcp_input_receipt(d, nullptr);
				}
				cJSON *sig = cJSON_GetObjectItem(root, "sig");
				cJSON *challenge_request =
					cJSON_GetObjectItem(root, "requestAuthChallenge");

				if (client && cJSON_IsString(client) && client->valuestring)
					strlcpy(d->client_name, client->valuestring,
						sizeof d->client_name);
				if (version && cJSON_IsString(version) && version->valuestring)
				{
					strncpy(d->client_version, version->valuestring,
						sizeof(d->client_version) - 1);
					d->client_version[sizeof(d->client_version) - 1] = '\0';
				}
				if (challenge_request && cJSON_IsTrue(challenge_request) &&
				    !d->account && !d->character && d->connected != CON_PLAYING &&
				    !d->durisweb_verified && !d->durisweb_backend &&
				    !gmcp_durisweb_auth_limited(d))
				{
					if (ws_issue_durisweb_challenge(
						    d->durisweb_auth_challenge,
						    &d->durisweb_auth_challenge_expires))
					{
						char challenge_json[128];
						snprintf(challenge_json, sizeof(challenge_json),
							 "{\"nonce\":\"%s\",\"expiresIn\":30}",
							 d->durisweb_auth_challenge);
						gmcp_send(d, "Core.AuthChallenge", challenge_json);
					}
				}
				else if (sig && cJSON_IsString(sig))
				{
					if (d->account || d->character ||
					    d->connected == CON_PLAYING || d->durisweb_verified ||
					    d->durisweb_backend || gmcp_durisweb_auth_limited(d))
					{
						/* Player and service identities cannot be mixed. */
					}
					else if (ws_verify_durisweb_signature(
							 sig->valuestring,
							 d->durisweb_auth_challenge,
							 d->durisweb_auth_challenge_expires))
					{
						d->durisweb_verified = 1;
						d->durisweb_backend = 1;
						d->wait = 0;
						ws_auth_reset(&d->durisweb_auth_window_start,
							      &d->durisweb_auth_failures);
						d->durisweb_auth_challenge[0] = '\0';
						d->durisweb_auth_challenge_expires = 0;
					}
					else
					{
						d->durisweb_auth_challenge[0] = '\0';
						d->durisweb_auth_challenge_expires = 0;
						gmcp_durisweb_auth_failure(d);
					}
				}
				cJSON_Delete(root);
			}
		}
	}
	/* Client.Info is an alias some clients use */
	else if (len > 11 && strncmp(data, "Client.Info", 11) == 0 && data[11] == ' ')
	{
		const char *end = data + len;
		const char *json_start = data + 11;
		while (json_start < end && *json_start == ' ')
			json_start++;

		if (json_start < end && *json_start == '{')
		{
			cJSON *root = cJSON_ParseWithLength(json_start, (size_t)(end - json_start));
			if (root)
			{
				cJSON *client = cJSON_GetObjectItem(root, "client");
				cJSON *version = cJSON_GetObjectItem(root, "version");

				if (client && cJSON_IsString(client) && client->valuestring)
					strlcpy(d->client_name, client->valuestring,
						sizeof d->client_name);
				if (version && cJSON_IsString(version) && version->valuestring)
					strlcpy(d->client_version, version->valuestring,
						sizeof d->client_version);
				cJSON_Delete(root);
			}
		}
	}
}

/* core gmcp send - handles telnet and websocket */
static bool gmcp_queue(struct descriptor_data *d, const char *package, const char *json)
{
	if (!d || !package || !json)
		return false;
	if (!d->gmcp_enabled && !d->websocket)
		return false;

	/* Check descriptor is still valid (not a dangling pointer to closed socket) */
	if (!is_desc_valid(d))
		return false;
	if (d->write_failed)
		return false;
	if (gmcp_session_supported(d) && strcmp(package, "Duris.Capabilities") &&
	    strcmp(package, "Duris.Session"))
	{
		gmcp_session_update(d);
		if (d->gmcp_control_pending || d->gmcp_session_pending)
		{
			d->gmcp_initial_state_pending = STATE(d) == CON_PLAYING;
			return false;
		}
		if (d->gmcp_session_state !=
			    static_cast<unsigned char>(gmcp_session_phase::playing) &&
		    strncmp(package, "Core.", 5) && strcmp(package, "Char.Input"))
			return false;
	}

	if (d->websocket)
	{
		/* WebSocket: Send JSON message */
		return websocket_send_json(d, package, json) >= 0;
	}
	else
	{
		/* Telnet: Send IAC SB GMCP <package> <json> IAC SE */
		size_t pkg_len = strlen(package);
		size_t json_len = strlen(json);
		size_t total_len = 3 + pkg_len + 1 + json_len +
				   2; /* IAC SB GMCP + package + space + json + IAC SE */
		unsigned char *buf = (unsigned char *)malloc(total_len);

		if (!buf)
			return false;

		buf[0] = TELNET_IAC;
		buf[1] = TELNET_SB;
		buf[2] = TELOPT_GMCP;
		memcpy(buf + 3, package, pkg_len);
		buf[3 + pkg_len] = ' ';
		memcpy(buf + 4 + pkg_len, json, json_len);
		buf[total_len - 2] = TELNET_IAC;
		buf[total_len - 1] = TELNET_SE;

		/* Use binary write to handle MCCP compression properly */
		const bool queued = write_to_descriptor_binary(d, buf, total_len) >= 0;
		free(buf);
		return queued;
	}
}

void gmcp_send(struct descriptor_data *d, const char *package, const char *json)
{
	(void)gmcp_queue(d, package, json);
}

/* Bootstrap state that otherwise only changes after a gameplay event. */
void gmcp_send_initial_state(struct char_data *ch)
{
	if (ch && ch->desc)
	{
		gmcp_preferences_changed(ch->desc);
		gmcp_session_update(ch->desc);
		if (ch->desc->gmcp_control_pending ||
		    (gmcp_session_supported(ch->desc) && ch->desc->gmcp_session_pending))
		{
			ch->desc->gmcp_initial_state_pending = true;
			return;
		}
	}
	if (!GMCP_ENABLED(ch) ||
	    (IS_NPC(ch) && !IS_MORPH(ch) && (!ch->desc->original || IS_NPC(ch->desc->original))))
		return;
	ch->desc->gmcp_initial_state_pending = false;
	ch->desc->gmcp_quest_map_sent = 0;
	ch->desc->gmcp_ship_bridge = 0;
	ch->desc->gmcp_ship_contacts_hash = 0;
	ch->desc->gmcp_ship_info_hash = 0;
	gmcp_send(ch->desc, GMCP_PKG_SHIP_INFO, "{}");
	gmcp_send(ch->desc, GMCP_PKG_SHIP_CONTACTS, "{\"contacts\":[]}");
	gmcp_char_status(ch);
	gmcp_char_vitals(ch);
	gmcp_char_affects(ch);
	gmcp_send_group_status(ch);
	gmcp_room_info(ch);
	ch->desc->last_map_update = 1;
	gmcp_quest_status(ch);
	ch->desc->gmcp_combat_state_sent = false;
	gmcp_flush_combat(ch->desc);
	gmcp_flush_time(ch->desc);
}

/* send room.info when character enters a room */
void gmcp_room_info(struct char_data *ch)
{
	char *json;
	struct room_data *room;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;

	room = &world[ch->in_room];
	json = json_build_room_info(room, ch);

	if (json)
	{
		gmcp_send(ch->desc, GMCP_PKG_ROOM_INFO, json);
		free(json);
	}
}

/*
 * send room.map for wilderness zones (surface, underdark, alatorin, newbie maps).
 * this stub is kept for backwards compatibility - the actual gmcp room.map is
 * sent from display_map_room() in map.c using gmcp_send_room_map().
 */
void gmcp_room_map(struct char_data *ch)
{
	(void)ch; /* Suppress unused parameter warning */
}

/* send pre-generated map buffer via gmcp, called from display_map_room() */
void gmcp_send_room_map(struct char_data *ch, const char *map_buf)
{
	char *json_str;
	cJSON *json;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;
	if (!map_buf || !*map_buf)
		return;

	json = cJSON_CreateObject();
	if (!json)
		return;

	cJSON_AddStringToObject(json, "map", map_buf);

	json_str = cJSON_PrintUnformatted(json);
	cJSON_Delete(json);

	if (json_str)
	{
		gmcp_send(ch->desc, GMCP_PKG_ROOM_MAP, json_str);
		free(json_str);
	}
}

/* send pre-generated quest map buffer via gmcp */
void gmcp_send_quest_map(struct char_data *ch, const char *map_buf)
{
	char *json_str;
	cJSON *json;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;
	if (!map_buf)
		return;
	struct char_data *player = GET_PLYR(ch);
	if (IS_NPC(player))
		return;

	json = cJSON_CreateObject();
	if (!json)
		return;

	cJSON_AddStringToObject(json, "map", map_buf);
	cJSON_AddNumberToObject(json, "zoneNumber",
				*map_buf ? player->only.pc->quest_zone_number : 0);

	json_str = cJSON_PrintUnformatted(json);
	cJSON_Delete(json);

	if (json_str)
	{
		gmcp_send(ch->desc, GMCP_PKG_QUEST_MAP, json_str);
		free(json_str);
	}
}

/*
 * room update throttling - track dirty rooms and flush periodically
 * to avoid flooding during high-activity scenarios like big battles
 */
#define MAX_DIRTY_ROOMS 500
static int dirty_rooms[MAX_DIRTY_ROOMS];
static int dirty_room_count = 0;

void gmcp_mark_room_dirty(int room_number)
{
	int i;

	if (room_number < 0)
		return;

	/* check if already marked */
	for (i = 0; i < dirty_room_count; i++)
	{
		if (dirty_rooms[i] == room_number)
			return;
	}

	/* add to dirty list if space available */
	if (dirty_room_count < MAX_DIRTY_ROOMS)
	{
		dirty_rooms[dirty_room_count++] = room_number;
	}
}

void gmcp_flush_dirty_rooms(void)
{
	int i;
	struct char_data *tch;
	struct room_data *room;

	for (i = 0; i < dirty_room_count; i++)
	{
		room = &world[dirty_rooms[i]];
		if (!room)
			continue;

		/* send room.info to all players in this room */
		for (tch = room->people; tch; tch = tch->next_in_room)
		{
			if (!IS_NPC(tch) && tch->desc && GMCP_ENABLED(tch))
			{
				gmcp_room_info(tch);
			}
		}
	}

	dirty_room_count = 0;
}

/*
 * ship contacts auto-update - periodically send contact updates to
 * players on ships
 */

/* Build once per flush, so observers do not each scan every ship's rooms. */
static std::unordered_map<int, struct ShipData *> gmcp_ship_bridges(void)
{
	std::unordered_map<int, struct ShipData *> bridges;
	ShipVisitor svs;
	for (bool found = shipObjHash.get_first(svs); found; found = shipObjHash.get_next(svs))
	{
		if (!SHIP_LOADED(svs))
			continue;
		int bridge = real_room(svs->bridge);
		if (bridge >= 0)
			bridges.emplace(bridge, svs.get_value());
	}
	return bridges;
}

/* Track bridge subscriptions per descriptor: a new observer needs a snapshot
 * even when the ship has not changed since another player last saw it. */
static struct ShipData *gmcp_player_ship(struct descriptor_data *d,
					 const std::unordered_map<int, struct ShipData *> &bridges)
{
	if (!d || STATE(d) != CON_PLAYING || !GMCP_ENABLED(d->character))
		return NULL;

	auto entry = bridges.find(d->character->in_room);
	struct ShipData *ship = entry == bridges.end() ? NULL : entry->second;

	int bridge = ship ? d->character->in_room + 1 : 0;
	if (bridge != d->gmcp_ship_bridge)
	{
		d->gmcp_ship_bridge = bridge;
		d->gmcp_ship_contacts_hash = 0;
		d->gmcp_ship_info_hash = 0;
		if (!ship)
		{
			gmcp_send(d, GMCP_PKG_SHIP_INFO, "{}");
			gmcp_send(d, GMCP_PKG_SHIP_CONTACTS, "{\"contacts\":[]}");
		}
	}
	return ship;
}

/* simple djb2 hash for strings */
static unsigned long hash_string(const char *str)
{
	unsigned long hash = 5381;
	int c;

	if (!str)
		return 0;

	while ((c = *str++))
	{
		hash = ((hash << 5) + hash) + c; /* hash * 33 + c */
	}

	return hash;
}

/* build json for ship contacts */
static cJSON *json_build_ship_contacts(struct ShipData *ship)
{
	cJSON *root, *contacts_arr, *contact_obj;
	int k, i;
	const char *race_str;
	const char *status_str;

	if (!ship)
		return NULL;

	root = cJSON_CreateObject();
	if (!root)
		return NULL;

	/* ship's own heading and speed */
	cJSON_AddStringToObject(root, "shipKey",
				(std::to_string(ship->runtime_ref.slot) + ":" +
				 std::to_string(ship->runtime_ref.generation))
					.c_str());
	cJSON_AddNumberToObject(root, "heading", (int)ship->heading);
	cJSON_AddNumberToObject(root, "speed", ship->speed);

	/* The flush removes world position from the unverified client payload. */
	if (ship->location >= 0 && ship->location < top_of_world)
	{
		struct zone_data *zone = &zone_table[world[ship->location].zone];
		if (IS_SET(zone->flags, ZONE_MAP) && zone->mapx > 0)
		{
			int vroom = world[ship->location].number;
			int zone_start = world[zone->real_bottom].number;
			int local_x = (vroom - zone_start) % zone->mapx;
			int local_y = ((vroom - zone_start) / zone->mapx) % zone->mapy;
			cJSON_AddNumberToObject(root, "worldX", local_x);
			cJSON_AddNumberToObject(root, "worldY", local_y);
		}
	}

	contacts_arr = cJSON_CreateArray();
	if (!contacts_arr)
	{
		cJSON_Delete(root);
		return NULL;
	}

	/* only get contacts if on open sea and not docked */
	if (IS_MAP_ROOM(ship->location) && !SHIP_DOCKED(ship))
	{
		k = getcontacts(ship);
		if (k > MAXSHIPS)
			k = MAXSHIPS; /* bounds check */

		for (i = 0; i < k; i++)
		{
			/* skip docked ships beyond range 5 */
			if (SHIP_DOCKED(contacts[i].ship) && contacts[i].range > 5)
				continue;

			contact_obj = cJSON_CreateObject();
			if (!contact_obj)
				continue;

			/* ship identification */
			cJSON_AddStringToObject(contact_obj, "id", contacts[i].ship->id);
			if (contacts[i].ship->name)
			{
				cJSON_AddStringToObject(contact_obj, "name",
							strip_ansi(contacts[i].ship->name).c_str());
			}
			else
			{
				cJSON_AddStringToObject(contact_obj, "name", "Unknown");
			}

			/* position and navigation */
			cJSON_AddNumberToObject(contact_obj, "x", contacts[i].x);
			cJSON_AddNumberToObject(contact_obj, "y", contacts[i].y);
			cJSON_AddNumberToObject(contact_obj, "range", contacts[i].range);
			cJSON_AddNumberToObject(contact_obj, "bearing", (int)contacts[i].bearing);
			cJSON_AddNumberToObject(contact_obj, "heading",
						(int)contacts[i].ship->heading);
			cJSON_AddNumberToObject(contact_obj, "speed", contacts[i].ship->speed);
			cJSON_AddStringToObject(contact_obj, "arc", contacts[i].arc);

			/* race/alignment (only if in scan range and not docked) */
			race_str = "unknown";
			if (contacts[i].range < SCAN_RANGE && !SHIP_DOCKED(contacts[i].ship))
			{
				switch (contacts[i].ship->race)
				{
				case GOODIESHIP:
					race_str = "good";
					break;
				case EVILSHIP:
					race_str = "evil";
					break;
				case UNDEADSHIP:
					race_str = "undead";
					break;
				case SQUIDSHIP:
					race_str = "squid";
					break;
				default:
					race_str = "unknown";
					break;
				}
			}
			cJSON_AddStringToObject(contact_obj, "race", race_str);

			/* status flags */
			status_str = "";
			if (SHIP_FLYING(contacts[i].ship))
				status_str = "flying";
			else if (SHIP_SINKING(contacts[i].ship))
				status_str = "sinking";
			else if (SHIP_IMMOBILE(contacts[i].ship))
				status_str = "immobile";
			else if (SHIP_DOCKED(contacts[i].ship))
				status_str = "docked";
			else if (SHIP_ANCHORED(contacts[i].ship))
				status_str = "anchored";
			cJSON_AddStringToObject(contact_obj, "status", status_str);

			/* targeting indicators */
			cJSON_AddBoolToObject(contact_obj, "targeting_you",
					      contacts[i].ship->target == ship);
			cJSON_AddBoolToObject(contact_obj, "you_targeting",
					      contacts[i].ship == ship->target);

			cJSON_AddItemToArray(contacts_arr, contact_obj);
		}
	}

	cJSON_AddItemToObject(root, "contacts", contacts_arr);

	return root;
}

void gmcp_flush_dirty_ship_contacts(void)
{
	/* Contacts depend on the ship and verification status, not the observer.
	 * Share both payload variants for this flush; keep delivery state per client. */
	struct snapshot
	{
		char *json[2] = {};
		unsigned long hash[2] = {};
	};
	std::unordered_map<struct ShipData *, snapshot> snapshots;
	const auto bridges = gmcp_ship_bridges();
	for (struct descriptor_data *d = descriptor_list; d; d = d->next)
	{
		struct ShipData *ship = gmcp_player_ship(d, bridges);
		if (!ship)
			continue;

		auto [entry, inserted] = snapshots.try_emplace(ship);
		snapshot &state = entry->second;
		if (inserted)
		{
			/* Docking produces an empty list to retire open-sea contacts. */
			cJSON *root = json_build_ship_contacts(ship);
			if (!root)
				continue;
			state.json[1] = cJSON_PrintUnformatted(root);
			cJSON_DeleteItemFromObject(root, "worldX");
			cJSON_DeleteItemFromObject(root, "worldY");
			state.json[0] = cJSON_PrintUnformatted(root);
			cJSON_Delete(root);
			state.hash[0] = hash_string(state.json[0]);
			state.hash[1] = hash_string(state.json[1]);
		}
		int variant = d->durisweb_verified ? 1 : 0;
		if (state.json[variant] && state.hash[variant] != d->gmcp_ship_contacts_hash)
		{
			gmcp_send(d, GMCP_PKG_SHIP_CONTACTS, state.json[variant]);
			d->gmcp_ship_contacts_hash = state.hash[variant];
		}
	}
	// NOLINTNEXTLINE(bugprone-nondeterministic-pointer-iteration-order): only frees temporary buffers.
	for (auto &entry : snapshots)
	{
		free(entry.second.json[0]);
		free(entry.second.json[1]);
	}
}

/* Hash the personalized payload, including this observer's racial bonuses. */
void gmcp_flush_dirty_ship_info(void)
{
	const auto bridges = gmcp_ship_bridges();
	for (struct descriptor_data *d = descriptor_list; d; d = d->next)
	{
		struct ShipData *ship = gmcp_player_ship(d, bridges);
		if (!ship)
			continue;

		char *json = json_build_ship_info(ship, d->character);
		if (!json)
			continue;
		unsigned long new_hash = hash_string(json);
		if (new_hash != d->gmcp_ship_info_hash)
		{
			gmcp_send(d, GMCP_PKG_SHIP_INFO, json);
			d->gmcp_ship_info_hash = new_hash;
		}
		free(json);
	}
}

/* send char.vitals when hp/mana/move changes */
void gmcp_char_vitals(struct char_data *ch)
{
	char *json;

	/* Group observers need changes even when this member does not use GMCP. */
	if (ch)
		update_groupies(ch);

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;

	json = json_build_char_vitals(ch);

	if (json)
	{
		gmcp_send(ch->desc, GMCP_PKG_CHAR_VITALS, json);
		free(json);
	}
}

/* send vitals update to all group members */
void gmcp_group_vitals(struct char_data *ch)
{
	struct group_list *gl;

	if (!ch || !ch->group)
		return;

	/* iterate through all group members */
	for (gl = ch->group; gl; gl = gl->next)
	{
		if (gl->ch && GMCP_ENABLED(gl->ch))
		{
			gmcp_char_vitals(gl->ch);
		}
	}
}

/* send group.status for group panel with member hp/move/position */
void gmcp_send_group_status(struct char_data *ch)
{
	cJSON *root, *members_arr, *member_obj;
	struct group_list *gl;
	char *json_str;
	int count = 0;
	int max_size = 13;
	int is_first = 1;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;

	if (IS_RACEWAR_EVIL(ch))
		max_size = (int)get_property("groups.size.max.evil", 13);
	if (IS_RACEWAR_GOOD(ch))
		max_size = (int)get_property("groups.size.max.good", 13);
#if defined(CTF_MUD) && (CTF_MUD == 1)
	max_size = 5;
#endif

	/* if not in a group, send empty */
	if (!ch->group)
	{
		char empty[80];
		snprintf(empty, sizeof(empty), "{\"members\":[],\"size\":0,\"maxSize\":%d}",
			 max_size);
		gmcp_send(ch->desc, GMCP_PKG_GROUP_STATUS, empty);
		return;
	}

	root = cJSON_CreateObject();
	members_arr = cJSON_CreateArray();

	/* iterate through group members */
	for (gl = ch->group; gl; gl = gl->next)
	{
		struct char_data *member = gl->ch;
		if (!member)
			continue;

		member_obj = cJSON_CreateObject();

		cJSON_AddStringToObject(member_obj, "name", GET_NAME(member));
		cJSON_AddNumberToObject(member_obj, "level", GET_LEVEL(member));

		/* class - null for npcs */
		if (IS_NPC(member))
		{
			cJSON_AddNullToObject(member_obj, "class");
		}
		else
		{
			cJSON_AddStringToObject(
				member_obj, "class",
				class_names_table[flag2idx(member->player.m_class)].normal);
		}

		/* race - null for npcs */
		if (IS_NPC(member))
		{
			cJSON_AddNullToObject(member_obj, "race");
		}
		else
		{
			cJSON_AddStringToObject(member_obj, "race",
						race_names_table[(int)GET_RACE(member)].normal);
		}

		cJSON_AddNumberToObject(member_obj, "hp", GET_HIT(member));
		cJSON_AddNumberToObject(member_obj, "maxHp", GET_MAX_HIT(member));
		cJSON_AddNumberToObject(member_obj, "move", GET_VITALITY(member));
		cJSON_AddNumberToObject(member_obj, "maxMove", GET_MAX_VITALITY(member));

		/* position */
		const char *pos_str;
		switch (GET_POS(member))
		{
		case POS_PRONE:
			pos_str = "prone";
			break;
		case POS_SITTING:
			pos_str = "sitting";
			break;
		case POS_KNEELING:
			pos_str = "kneeling";
			break;
		case POS_STANDING:
			pos_str = "standing";
			break;
		default:
			pos_str = "standing";
			break;
		}
		cJSON_AddStringToObject(member_obj, "position", pos_str);

		/* rank - head for leader, front/back based on back_rank flag */
		const char *rank_str;
		if (is_first)
		{
			rank_str = "head";
			is_first = 0;
		}
		else if (!IS_NPC(member) && PLR2_FLAGGED(member, PLR2_BACK_RANK))
		{
			rank_str = "back";
		}
		else
		{
			rank_str = "front";
		}
		cJSON_AddStringToObject(member_obj, "rank", rank_str);

		cJSON_AddBoolToObject(member_obj, "isNpc", IS_NPC(member) ? 1 : 0);
		cJSON_AddBoolToObject(member_obj, "inRoom",
				      (member->in_room == ch->in_room) ? 1 : 0);

		/* for npcs, calculate target number and keyword */
		if (IS_NPC(member) && member->in_room == ch->in_room)
		{
			/* count matching mobs using lifo order (last in = target #1) */
			struct char_data *tch;
			int target_num = 0;
			int total_matching = 0;
			int member_position = 0;
			const char *first_keyword = NULL;

			/* get first keyword from npc's name list */
			if (member->player.name)
			{
				static char keyword_buf[64];
				strlcpy(keyword_buf, member->player.name, sizeof keyword_buf);
				/* get first word (keyword) */
				char *space = strchr(keyword_buf, ' ');
				if (space)
					*space = '\0';
				first_keyword = keyword_buf;
			}

			/* count matching mobs in room - lifo order means last in = #1 */
			if (first_keyword)
			{
				/* first pass: count total matching mobs and find member's position */
				for (tch = world[ch->in_room].people; tch; tch = tch->next_in_room)
				{
					if (IS_NPC(tch) && tch->player.name)
					{
						/* check if this mob matches the keyword */
						if (isname(first_keyword, tch->player.name))
						{
							total_matching++;
							if (tch == member)
							{
								member_position = total_matching;
							}
						}
					}
				}
				/* lifo: last mob in list = #1, so reverse the position */
				if (member_position > 0)
				{
					target_num = total_matching - member_position + 1;
				}
			}

			if (target_num > 0 && first_keyword)
			{
				cJSON_AddNumberToObject(member_obj, "targetNum", target_num);
				cJSON_AddStringToObject(member_obj, "targetKeyword", first_keyword);
			}
			else
			{
				cJSON_AddNullToObject(member_obj, "targetNum");
				cJSON_AddNullToObject(member_obj, "targetKeyword");
			}
		}
		else
		{
			cJSON_AddNullToObject(member_obj, "targetNum");
			cJSON_AddNullToObject(member_obj, "targetKeyword");
		}

		cJSON_AddItemToArray(members_arr, member_obj);
		count++;
	}

	cJSON_AddItemToObject(root, "members", members_arr);
	cJSON_AddNumberToObject(root, "size", count);
	cJSON_AddNumberToObject(root, "maxSize", max_size);

	json_str = cJSON_PrintUnformatted(root);
	cJSON_Delete(root);

	if (json_str)
	{
		gmcp_send(ch->desc, GMCP_PKG_GROUP_STATUS, json_str);
		free(json_str);
	}
}

/* send char.status on login, level up, etc. */
void gmcp_char_status(struct char_data *ch)
{
	char *json;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;

	json = json_build_char_status(GET_PLYR(ch));

	if (json)
	{
		gmcp_send(ch->desc, GMCP_PKG_CHAR_STATUS, json);
		free(json);
	}
}

/* send char.affects when buffs/debuffs change */
void gmcp_char_affects(struct char_data *ch)
{
	char *json;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;

	json = json_build_char_affects(ch);

	if (json)
	{
		gmcp_send(ch->desc, GMCP_PKG_CHAR_AFFECTS, json);
		free(json);
	}
}

// Combat snapshots. Sample only the two prompt relationships in the existing
// descriptor flush: direct health/posture writes and non-GMCP tanks need no
// per-hit observer scan or collection of pointers surviving gameplay mutations.
static gmcp_combat_subject gmcp_combat_sample(P_char viewer, P_char subject)
{
	gmcp_combat_subject view{};
	if (!subject || viewer->in_room < 0 || subject->in_room != viewer->in_room)
		return view;
	view.present = true;
	view.identity = subject->runtime_id;
	view.position = GET_POS(subject);
	view.bleeding = GET_HIT(subject) < 0 || GET_MAX_HIT(subject) <= 0;
	if (GET_MAX_HIT(subject) > 0)
		view.health_percent = static_cast<int>(std::clamp<int64_t>(
			static_cast<int64_t>(GET_HIT(subject)) * 100 / GET_MAX_HIT(subject), 0,
			100));
	if (subject != viewer && !CAN_SEE(viewer, subject))
		strlcpy(view.name, "someone", sizeof(view.name));
	else if (IS_PC(subject))
		strlcpy(view.name, strip_ansi(PERS(subject, viewer, 0, true)).c_str(),
			sizeof(view.name));
	else if (const char *name = GET_NAME(subject))
	{
		// Prompt's first alphabetic word, bounded instead of FirstWord's static buffer.
		while (*name == ' ')
			++name;
		size_t length = 0;
		while (length < sizeof(view.name) - 1 &&
		       isalpha(static_cast<unsigned char>(name[length])))
		{
			view.name[length] = name[length];
			++length;
		}
	}
	return view;
}

static bool gmcp_combat_equal(const gmcp_combat_subject &a, const gmcp_combat_subject &b)
{
	return a.present == b.present && a.identity == b.identity &&
	       a.health_percent == b.health_percent && a.position == b.position &&
	       a.bleeding == b.bleeding && !strcmp(a.name, b.name);
}

static cJSON *gmcp_combat_json(const gmcp_combat_subject &view)
{
	if (!view.present)
		return cJSON_CreateNull();
	const char *health = view.bleeding		? "bleeding to death" :
			     view.health_percent >= 100 ? "excellent" :
			     view.health_percent >= 90	? "few scratches" :
			     view.health_percent >= 75	? "small wounds" :
			     view.health_percent >= 50	? "quite a few wounds" :
			     view.health_percent >= 30	? "big nasty wounds" :
			     view.health_percent >= 15	? "pretty hurt" :
							  "awful";
	const char *positions[] = { "on their ass", "sitting", "kneeling", "standing" };
	cJSON *json = cJSON_CreateObject();
	if (!json || !cJSON_AddStringToObject(json, "name", view.name) ||
	    !cJSON_AddStringToObject(json, "health", health) ||
	    !cJSON_AddNumberToObject(json, "healthPercent", view.health_percent) ||
	    !cJSON_AddStringToObject(json, "position", positions[view.position]))
	{
		cJSON_Delete(json);
		return nullptr;
	}
	return json;
}

static void gmcp_combat_publish(P_char ch, bool force, int damage = 0,
				const char *damage_type = nullptr, int critical = 0,
				P_char hit_victim = nullptr)
{
	if (!GMCP_ENABLED(ch) || STATE(ch->desc) != CON_PLAYING || !gmcp_session_player(ch->desc) ||
	    ch->desc->write_failed)
		return;
	P_desc d = ch->desc;
	gmcp_session_update(d);
	if (d->gmcp_control_pending || (gmcp_session_supported(d) && d->gmcp_session_pending))
		return;
	P_char target = GET_OPPONENT(ch);
	if (!target)
		target = hit_victim;
	if (target && (ch->in_room < 0 || target->in_room != ch->in_room))
		target = nullptr;
	const gmcp_combat_subject views[2] = {
		gmcp_combat_sample(ch, target),
		gmcp_combat_sample(ch, target ? GET_OPPONENT(target) : nullptr)
	};
	const bool round = damage > 0 || damage_type;
	if (!force && !round && d->gmcp_combat_state_sent &&
	    gmcp_combat_equal(views[0], d->gmcp_combat_subjects[0]) &&
	    gmcp_combat_equal(views[1], d->gmcp_combat_subjects[1]))
		return;
	cJSON *root = cJSON_CreateObject();
	cJSON *target_json = gmcp_combat_json(views[0]);
	cJSON *tank_json = gmcp_combat_json(views[1]);
	if (!root || !target_json || !tank_json)
	{
		cJSON_Delete(root);
		cJSON_Delete(target_json);
		cJSON_Delete(tank_json);
		return;
	}
	cJSON_AddItemToObjectCS(root, "target", target_json);
	cJSON_AddItemToObjectCS(root, "tank", tank_json);
	const uint64_t revision = d->gmcp_combat_revision + 1;
	char revision_text[32];
	snprintf(revision_text, sizeof(revision_text), "%llu",
		 static_cast<unsigned long long>(revision));
	if (!cJSON_AddStringToObject(root, "revision", revision_text))
	{
		cJSON_Delete(root);
		return;
	}
	if (round)
	{
		cJSON *event = cJSON_AddObjectToObject(root, "round");
		if (!event || !cJSON_AddStringToObject(event, "attacker", GET_NAME(ch)) ||
		    !cJSON_AddNumberToObject(event, "damage", damage) ||
		    !cJSON_AddStringToObject(event, "damageType",
					     damage_type ? damage_type : "unknown") ||
		    !cJSON_AddBoolToObject(event, "critical", critical))
		{
			cJSON_Delete(root);
			return;
		}
	}
	char *json = cJSON_PrintUnformatted(root);
	cJSON_Delete(root);
	if (!json)
		return;
	if (gmcp_queue(d, GMCP_PKG_COMBAT_UPDATE, json))
	{
		d->gmcp_combat_subjects[0] = views[0];
		d->gmcp_combat_subjects[1] = views[1];
		d->gmcp_combat_state_sent = true;
		d->gmcp_combat_revision = revision;
	}
	free(json);
}

static void gmcp_flush_combat(P_desc d)
{
	if (d && d->character)
		gmcp_combat_publish(d->character, false);
}

/* Preserve the first hit's victim before damage() establishes the relationship. */
void gmcp_combat_update(struct char_data *ch, struct char_data *victim, int damage,
			const char *damage_type, int critical)
{
	if (victim)
		gmcp_combat_publish(ch, true, damage, damage_type, critical, victim);
}

/* Relationship changes coalesce with health and posture at the next flush. */
void gmcp_combat_target(struct char_data *ch, struct char_data *victim)
{
	(void)victim;
	if (ch && ch->desc)
		ch->desc->gmcp_combat_state_sent = false;
}

/* Explicitly clear ended combat before the character can be detached/reused. */
void gmcp_combat_end(struct char_data *ch)
{
	gmcp_combat_publish(ch, true);
}

// End combat snapshots.

/* send channel message via gmcp */
void gmcp_comm_channel(struct char_data *ch, const char *channel, const char *sender,
		       const char *text)
{
	char *json;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;

	json = json_build_comm_channel(channel, sender, text);

	if (json)
	{
		gmcp_send(ch->desc, GMCP_PKG_COMM_CHANNEL, json);
		free(json);
	}
}

/* send channel message via gmcp with alignment (for nchat) */
void gmcp_comm_channel_ex(struct char_data *ch, const char *channel, const char *sender,
			  const char *text, const char *alignment)
{
	char *json;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;

	json = json_build_comm_channel_ex(channel, sender, text, alignment);

	if (json)
	{
		gmcp_send(ch->desc, GMCP_PKG_COMM_CHANNEL, json);
		free(json);
	}
}

/* broadcast channel message to all gmcp-enabled players */
void gmcp_broadcast_channel(const char *channel, const char *sender, const char *text,
			    struct char_data *exclude)
{
	struct descriptor_data *d;
	char *json;

	json = json_build_comm_channel(channel, sender, text);
	if (!json)
		return;

	for (d = descriptor_list; d; d = d->next)
	{
		if (d->character && d->character != exclude && STATE(d) == CON_PLAYING &&
		    GMCP_ENABLED(d->character))
		{
			gmcp_send(d, GMCP_PKG_COMM_CHANNEL, json);
		}
	}

	free(json);
}

/* send quest.status for bartender quests */
void gmcp_quest_status(struct char_data *ch)
{
	if (!ch || !ch->desc || !GMCP_ENABLED(ch))
		return;
	P_char player = GET_PLYR(ch);
	if (IS_NPC(player))
		return;
	gmcp_quest_status(ch, world_quest_refresh(player));
}

void gmcp_quest_status(struct char_data *ch, world_quest_target_status status)
{
	char *json;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;

	struct char_data *player = GET_PLYR(ch);
	if (IS_NPC(player))
		return;
	json = json_build_quest_status(player, status);

	if (json)
	{
		gmcp_send(ch->desc, GMCP_PKG_QUEST_STATUS, json);
		free(json);
	}

	// Clear previously advertised directions when they are no longer proved.
	if (status != world_quest_target_status::valid || !player->only.pc->quest_active ||
	    player->only.pc->quest_accomplished)
	{
		gmcp_send_quest_map(ch, "");
		ch->desc->gmcp_quest_map_sent = 0;
	}
	else if (player->only.pc->quest_map_bought == 1 && !ch->desc->gmcp_quest_map_sent)
	{
		gmcp_quest_map(ch, status);
		ch->desc->gmcp_quest_map_sent = 1;
	}
}

/* generate and send quest.map for bartender quests */

void gmcp_quest_map(struct char_data *ch, world_quest_target_status status)
{
	int old_room, map_room;

	if (!ch || !ch->desc)
		return;
	if (!GMCP_ENABLED(ch))
		return;
	struct char_data *player = GET_PLYR(ch);
	if (IS_NPC(player) || status != world_quest_target_status::valid ||
	    !player->only.pc->quest_active || player->only.pc->quest_replacement_due ||
	    player->only.pc->quest_accomplished || player->only.pc->quest_map_bought != 1)
		return;

	map_room = real_room(player->only.pc->quest_map_room);
	if (map_room < 0)
		return;

	/* Select the map viewpoint without movement hooks, casting cancellation,
	 * or changing either room's occupant list. Rendering is synchronous. */
	old_room = ch->in_room;
	ch->in_room = map_room;

	/* generate and send quest map (20 tile radius) */
	display_map_room(ch, map_room, 20, 999, 1);

	ch->in_room = old_room;
}
