#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "net/output_style.h"
#include "player/output_preferences.h"
#include "player/output_message.h"
#include "player/player_save_pipeline.h"
#include "player/news.h"
#include "net/gmcp.h"
#include "net/chat_presentation.h"
#include "world/specs.prototypes.h"
#include "cmd/interp.h"
#include "core/files.h"
#include "combat/combat_outcome_command.h"
#include "guild/alliances.h"
#include <cjson/cJSON.h>
#include <cassert>
#include <algorithm>
#include <cstdarg>
#include <cstring>
#include <functional>
#include <vector>
#include <tuple>
#include <fstream>
#include <filesystem>

#ifdef COLORIZATION_BENCHMARK
#include "colorization_benchmark_support.inc"
#endif

// Allocation and outside-world visibility/logging boundaries are test doubles;
// the output/pager logic below is extracted verbatim from production sources.
#undef CREATE
#undef RECREATE
#undef FREE
#define CREATE(result, type, number, tag) result = (type *)calloc(number, sizeof(type))
#define RECREATE(result, type, number) result = (type *)realloc(result, sizeof(type) * (number))
#define FREE(pointer)              \
	do                         \
	{                          \
		free(pointer);     \
		pointer = nullptr; \
	} while (false)
#define PAGE_WIDTH 80
static char send_to_char_f_buf[MAX_STRING_LENGTH];
P_char executing_ch = nullptr;
static room_data rooms[3]{};
P_room world = rooms;
static index_data indexes[1]{};
P_index obj_index = indexes;
static bool visible = true;
static P_char hidden_recipient = nullptr;
static std::vector<std::pair<std::string, int>> logged;
static std::function<void(P_char)> command_action;
static player_save_pipeline_result save_result = player_save_pipeline_result::queued;
static P_char saved_owner;
static int save_calls;
player_save_pipeline_result
player_save_pipeline_request(P_char owner, player_component_mask_t components, int, int)
{
	assert(components == PLAYER_COMPONENT_STATUS);
	saved_owner = owner;
	++save_calls;
	return save_result;
}
void command_interpreter(P_char ch, char *)
{
	command_action(ch);
}
static P_char morphed;
int IS_MORPH(P_char ch)
{
	return ch == morphed;
}
void production_write_to_pc_log(P_char, const char *, int);
void write_to_pc_log(P_char ch, const char *message, int policy)
{
	logged.emplace_back(message, policy);
	production_write_to_pc_log(ch, message, policy);
}
bool ac_can_see(P_char, P_char, bool)
{
	return visible;
}
bool ac_can_see_obj(P_char, P_obj, int)
{
	return visible;
}
char *PERS(P_char ch, P_char to, int)
{
	static char unknown[] = "someone";
	return to == hidden_recipient ? unknown : ch->player.name;
}
char *FirstWord(char *input)
{
	return input;
}
char *str_dup(const char *input)
{
	return strdup(input);
}
char *one_argument(const char *input, char *out)
{
	while (*input == ' ')
		++input;
	while (*input && *input != ' ')
		*out++ = *input++;
	*out = 0;
	return const_cast<char *>(input);
}

// Keep the real tell/reply command and its recipient gates. Language and GMCP
// are controlled boundaries, so transformation is deterministic in this test.
P_desc descriptor_list = nullptr;
static unsigned language_calls = 0;
static const char *language_override = nullptr;
bool can_talk(P_char)
{
	return true;
}
bool is_silent(P_char, bool)
{
	return false;
}
bool racewar(P_char, P_char)
{
	return false;
}
bool isname(const char *name, const char *candidate)
{
	return !strcasecmp(name, candidate);
}
int is_linked_from(P_char, P_char, ush_int)
{
	return 0;
}
void half_chop(char *input, char *first, char *rest)
{
	const char *remaining = one_argument(input, first);
	while (*remaining == ' ')
		++remaining;
	strcpy(rest, remaining);
}
char *language_CRYPT(P_char, P_char, char *message)
{
	++language_calls;
	return language_override ? const_cast<char *>(language_override) : message;
}
const char *language_known(P_char, P_char)
{
	return "";
}
float get_property(const char *, double value)
{
	return value;
}
static std::vector<std::pair<P_desc, std::string>> chat_packets;
void gmcp_send(P_desc d, const char *package, const char *json)
{
	assert(std::string(package) == "Comm.Channel");
	chat_packets.emplace_back(d, json);
}

#include "world_output_stubs.inc"
#include "combat_prompt_stubs.inc"
#include "chat_presentation_stubs.inc"
const auto race_names_table = []
{
	std::array<struct race_names, 256> names{};
	for (auto &name : names)
		name = { "Human", "Human", "Human", "H" };
	return names;
}();
const char *command[] = { "\n" };
void do_color_preferences(P_char, const char *)
{
	assert(false);
}
void show_toggles(P_char)
{
	assert(false);
}
void gmcp_send_initial_state(P_char)
{
	assert(false);
}
void quest_ask(P_char, P_char) {}
int nq_action_check(P_char, P_char, char *)
{
	return 0;
}
int is_introd(P_char, P_char)
{
	return true;
}
char *skip_spaces(char *text)
{
	while (*text == ' ')
		++text;
	return text;
}
void gmcp_comm_channel(P_char, const char *, const char *, const char *) {}
P_char get_char_room_vis(P_char ch, const char *name)
{
	for (auto *candidate = world[ch->in_room].people; candidate;
	     candidate = candidate->next_in_room)
		if (!strcasecmp(candidate->player.name, name))
			return candidate;
	return nullptr;
}
bool get_equipment_list(P_char, char *buffer, int)
{
	strcpy(buffer, "EQUIPMENT_FIXTURE\r\n");
	return true;
}
const char *get_account_name_safe(P_char)
{
	return "privacy-fixture";
}
const char *get_class_name(P_char, P_char)
{
	return "Warrior";
}
struct PrivacyAlliance : Alliance
{
	void set(P_Guild guild) { forging_assoc = joining_assoc = guild; }
};
static PrivacyAlliance privacy_alliance;
P_Alliance Guild::get_alliance()
{
	return &privacy_alliance;
}
#include "production_output.inc"

static std::string drain(P_desc d)
{
	std::string output;
	char buffer[MAX_STRING_LENGTH];
	while (get_from_q(&d->output, buffer))
		output += buffer;
	return output;
}

#include "world_output_checks.inc"
#include "combat_prompt_checks.inc"
#include "chat_presentation_checks.inc"
#include "artifact_activation_checks.inc"
#include "news_prompt_checks.inc"
#ifdef COLORIZATION_BENCHMARK
#include "colorization_benchmark.inc"
#endif

static void privacy_delivery_matrix()
{
	char_data a{}, b{}, observer{};
	pc_only_data ap{}, bp{}, op{};
	descriptor_data ad{}, bd{}, od{};
	Guild guild;
	privacy_alliance.set(&guild);
	char an[] = "Alice", bn[] = "Bob", on[] = "Observer";
	a.only.pc = &ap;
	b.only.pc = &bp;
	observer.only.pc = &op;
	a.player.name = an;
	b.player.name = bn;
	observer.player.name = on;
	a.desc = &ad;
	b.desc = &bd;
	observer.desc = &od;
	ad.character = &a;
	bd.character = &b;
	od.character = &observer;
	ad.next = &bd;
	bd.next = &od;
	descriptor_list = &ad;
	ad.connected = bd.connected = od.connected = CON_PLAYING;
	a.specials.position = b.specials.position = observer.specials.position =
		POS_STANDING + STAT_NORMAL;
	a.player.level = 30;
	b.player.level = 30;
	observer.player.level = 30;
	ap.pid = 100;
	bp.pid = 101;
	op.pid = 102;
	SET_BIT(a.specials.act, PLR_ECHO | PLR_GCC);
	SET_BIT(b.specials.act, PLR_ECHO | PLR_GCC);
	SET_BIT(a.specials.act2, PLR2_ACC);
	SET_BIT(b.specials.act2, PLR2_ACC | PLR2_WEBINFO);
	SET_BIT(observer.specials.act2, PLR2_WEBINFO);
	a.specials.guild = b.specials.guild = &guild;
	a.specials.guild_status = b.specials.guild_status = A_SF2 | A_NORMAL;
	world[0].people = &a;
	a.next_in_room = &b;
	b.next_in_room = &observer;
	struct group_list member
	{
	};
	member.ch = &b;
	a.group = &member;
	language_override = nullptr;
	for (bool sender_on : { false, true })
	{
		if (sender_on)
			SET_BIT(a.specials.act2, PLR2_WEBINFO);
		else
			REMOVE_BIT(a.specials.act2, PLR2_WEBINFO);
		for (auto command : { do_tell, do_whisper, do_ask, do_gsay, do_gcc, do_acc })
		{
			for (bool telepathic : { false, true })
			{
				a.player.race = b.player.race = telepathic ? RACE_ILLITHID :
									     RACE_HUMAN;
				for (bool echo : { true, false })
				{
					if (echo)
						SET_BIT(a.specials.act, PLR_ECHO);
					else
						REMOVE_BIT(a.specials.act, PLR_ECHO);
					char direct[] = "Bob PRIVATE_MARKER $n &+gtest&n";
					char channel[] = "PRIVATE_MARKER $n &+gtest&n";
					send_to_char("PUBLIC_CONTROL\r\n", &b);
					drain(&bd);
					command(&a,
						(command == do_tell || command == do_whisper ||
						 command == do_ask) ?
							direct :
							channel,
						0);
					auto sent = drain(&ad), received = drain(&bd),
					     notice = drain(&od);
					if (received.find("PRIVATE_MARKER") == std::string::npos)
						fprintf(stderr,
							"privacy delivery command=%s telepathic=%d echo=%d sent=%s received=%s\n",
							command == do_tell    ? "tell" :
							command == do_whisper ? "whisper" :
							command == do_ask     ? "ask" :
							command == do_gsay    ? "gsay" :
							command == do_gcc     ? "gcc" :
										"acc",
							telepathic, echo, sent.c_str(),
							received.c_str());
					assert(received.find("PRIVATE_MARKER") !=
					       std::string::npos);
					assert((sent.find("PRIVATE_MARKER") != std::string::npos) ==
					       echo);
					assert(std::string(
						       GET_PLAYER_LOG(&a)->read_export(MAX_LOG_LEN))
						       .find("PRIVATE_MARKER") ==
					       std::string::npos);
					if (echo)
						assert(std::string(
							       GET_PLAYER_LOG(&a)->read(
								       LOG_PRIVATE, MAX_LOG_LEN))
							       .find("PRIVATE_MARKER") !=
						       std::string::npos);
					assert(notice.find("PRIVATE_MARKER") == std::string::npos);
					if (!telepathic &&
					    (command == do_whisper || command == do_ask))
					{
						assert(!notice.empty());
						assert(std::string(
							       GET_PLAYER_LOG(&observer)
								       ->read_export(MAX_LOG_LEN))
							       .find(command == do_whisper ?
									     "whispers something" :
									     "a question") !=
						       std::string::npos);
					}
					assert(received.find("$n") != std::string::npos);
					assert(std::string(GET_PLAYER_LOG(&b)->read(LOG_PRIVATE,
										    MAX_LOG_LEN))
						       .find("PRIVATE_MARKER") !=
					       std::string::npos);
					combat_outcome_payload payload{};
					auto *entry = combat_outcome_add_participant(
						&payload, &b, combat_participant_role::victim, true,
						false);
					assert(entry->webinfo_at_capture == combat_webinfo::on);
					assert(entry->log.find("PRIVATE_MARKER") ==
					       std::string::npos);
					assert(entry->log.find("PUBLIC_CONTROL") !=
					       std::string::npos);
					assert(entry->equipment == "EQUIPMENT_FIXTURE\r\n");
				}
			}
		}
	}
	char reply[] = "REPLY_PRIVATE";
	do_reply(&b, reply, 0);
	assert(drain(&ad).find("REPLY_PRIVATE") != std::string::npos);
	assert(std::string(GET_PLAYER_LOG(&b)->read_export(MAX_LOG_LEN)).find("REPLY_PRIVATE") ==
	       std::string::npos);
	drain(&bd);
	// Ordinary whisper/ask language transformation still delivers the translated
	// body privately, including literal act metacharacters.
	a.player.race = b.player.race = RACE_HUMAN;
	SET_BIT(a.specials.act, PLR_ECHO);
	language_override = "TRANSLATED_PRIVATE $n";
	for (auto command : { do_whisper, do_ask })
	{
		char message[] = "Bob ORIGINAL_PRIVATE";
		command(&a, message, 0);
		const auto translated = drain(&bd);
		assert(translated.find("TRANSLATED_PRIVATE") != std::string::npos);
		assert(translated.find("$n") != std::string::npos);
		assert(drain(&ad).find("ORIGINAL_PRIVATE") != std::string::npos);
		assert(std::string(GET_PLAYER_LOG(&b)->read(LOG_PRIVATE, MAX_LOG_LEN))
			       .find("TRANSLATED_PRIVATE") != std::string::npos);
		assert(std::string(GET_PLAYER_LOG(&b)->read_export(MAX_LOG_LEN))
			       .find("TRANSLATED_PRIVATE") == std::string::npos);
		assert(std::string(GET_PLAYER_LOG(&a)->read_export(MAX_LOG_LEN))
			       .find("ORIGINAL_PRIVATE") == std::string::npos);
	}
	language_override = nullptr;
	// Switched delivery follows the owning player's consent, not the NPC body.
	char_data body{};
	npc_only_data body_pc{};
	body.only.npc = &body_pc;
	body.specials.act = ACT_ISNPC;
	body.desc = &ad;
	ad.original = &a;
	REMOVE_BIT(a.specials.act2, PLR2_WEBINFO);
	production_write_to_pc_log(&body, "SWITCHED_OFF", LOG_PUBLIC);
	assert(std::string(GET_PLAYER_LOG(&a)->read_export(MAX_LOG_LEN)).empty());
	SET_BIT(a.specials.act2, PLR2_WEBINFO);
	production_write_to_pc_log(&body, "SWITCHED_ON", LOG_PUBLIC);
	assert(std::string(GET_PLAYER_LOG(&a)->read_export(MAX_LOG_LEN)) == "SWITCHED_ON");
	REMOVE_BIT(a.specials.act2, PLR2_WEBINFO);
	ad.original = nullptr;
	// Off-period equipment stays in personal recall but cannot enter a later capture.
	send_to_char("OFF_EQUIPMENT_MARKER", &a);
	SET_BIT(a.specials.act2, PLR2_WEBINFO);
	send_to_char("ON_MARKER", &a);
	combat_outcome_payload payload{};
	auto *entry = combat_outcome_add_participant(&payload, &a, combat_participant_role::killer,
						     true, false);
	assert(entry->log == "ON_MARKER");
	assert(std::string(GET_PLAYER_LOG(&a)->read(LOG_PUBLIC, MAX_LOG_LEN))
		       .find("OFF_EQUIPMENT_MARKER") != std::string::npos);
	// Optional handoff: replay these exact game-thread captures through the real
	// SQL repository and the paired website. Only synthetic fixture messages exist.
	if (const char *directory = getenv("PVP_CAPTURE_COMMAND_DIR"))
	{
		std::filesystem::create_directories(directory);
		for (int battle = 0; battle < 5; ++battle)
		{
			for (P_char ch : { &a, &b })
			{
				const bool on = battle != 2 && (battle != 0 || ch == &a);
				char setting[40];
				strcpy(setting, on ? "webinfo on" : "webinfo off");
				do_toggle(ch, setting, 0);
				GET_PLAYER_LOG(ch)->reset_export_window();
				if (battle != 3)
					send_to_char(ch == &a ? "PUBLIC_A_LINE\r\n" :
								"PUBLIC_B_LINE\r\n",
						     ch);
			}
			char whisper[] = "Bob PRIVATE_HANDOFF_MARKER $n";
			if (battle != 3)
				do_whisper(&a, whisper, 0);
			combat_outcome_payload handoff{};
			handoff.victim_pid = battle == 1 ? ap.pid : bp.pid;
			handoff.room_vnum = 1234;
			strcpy(handoff.room_name.data(), "Synthetic privacy room");
			combat_outcome_add_participant(&handoff, &a,
						       battle == 1 ?
							       combat_participant_role::victim :
							       combat_participant_role::killer,
						       true, true);
			combat_outcome_add_participant(&handoff, &b,
						       battle == 1 ?
							       combat_participant_role::killer :
							       combat_participant_role::victim,
						       true, false);
			critical_operation_id operation{};
			assert(critical_operation_id_generate(&operation));
			critical_command captured{};
			assert(combat_outcome_command_build(&captured, operation, handoff));
			captured.accepted_at_usec = 1;
			if (battle == 4)
			{
				captured.payload_version = 3;
				captured.payload.resize(captured.payload.size() -
							handoff.participant_count);
			}
			std::vector<uint8_t> encoded;
			assert(critical_command_encode(captured, &encoded) ==
			       critical_command_codec_result::ok);
			std::ofstream file(std::filesystem::path(directory) /
						   (std::to_string(battle) + ".command"),
					   std::ios::binary);
			file.write(reinterpret_cast<const char *>(encoded.data()), encoded.size());
			assert(file.good());
		}
	}
	for (P_char ch : { &a, &b, &observer })
	{
		delete GET_PLAYER_LOG(ch);
		GET_PLAYER_LOG(ch) = nullptr;
		drain(ch->desc);
	}
	descriptor_list = nullptr;
	world[0].people = nullptr;
}

static void privacy_toggle_matrix()
{
	char_data ch{};
	pc_only_data pc{};
	descriptor_data d{};
	ch.only.pc = &pc;
	ch.desc = &d;
	d.character = &ch;
	ch.specials.position = POS_STANDING + STAT_NORMAL;
	pc.pid = 201;
	char name[] = "ToggleFixture";
	ch.player.name = name;
	ch.in_room = NOWHERE;
	auto toggle = [&](const char *arg)
	{
		char command[100];
		strcpy(command, arg);
		do_toggle(&ch, command, 0);
		return drain(&d);
	};
	SET_BIT(ch.specials.act2, PLR2_WEBINFO);
	send_to_char("FIRST_INTERVAL", &ch);
	drain(&d);
	const int before = save_calls;
	assert(toggle("webinfo on").find("already") != std::string::npos);
	assert(save_calls == before &&
	       std::string(GET_PLAYER_LOG(&ch)->read_export(MAX_LOG_LEN)).find("FIRST_INTERVAL") !=
		       std::string::npos);
	assert(toggle("webinfo invalid").find("boolean") != std::string::npos &&
	       save_calls == before);
	for (auto failure :
	     { player_save_pipeline_result::invalid, player_save_pipeline_result::capture_failed,
	       player_save_pipeline_result::unavailable })
	{
		save_result = failure;
		assert(toggle("webinfo off").find("did not take effect") != std::string::npos);
		assert(PLR2_FLAGGED(&ch, PLR2_WEBINFO));
		assert(std::string(GET_PLAYER_LOG(&ch)->read_export(MAX_LOG_LEN))
			       .find("FIRST_INTERVAL") != std::string::npos);
	}
	save_result = player_save_pipeline_result::queued;
	assert(toggle("webinfo off").find("save pending") != std::string::npos);
	assert(!PLR2_FLAGGED(&ch, PLR2_WEBINFO));
	send_to_char("OFF_INTERVAL_EQUIPMENT", &ch);
	drain(&d);
	assert(std::string(GET_PLAYER_LOG(&ch)->read_export(MAX_LOG_LEN)).empty());
	save_result = player_save_pipeline_result::coalesced;
	assert(toggle("webinfo").find("save pending") != std::string::npos);
	assert(PLR2_FLAGGED(&ch, PLR2_WEBINFO));
	send_to_char("NEW_INTERVAL", &ch);
	drain(&d);
	auto exported = std::string(GET_PLAYER_LOG(&ch)->read_export(MAX_LOG_LEN));
	assert(exported.find("NEW_INTERVAL") != std::string::npos &&
	       exported.find("FIRST_INTERVAL") == std::string::npos &&
	       exported.find("OFF_INTERVAL") == std::string::npos);
	assert(std::string(GET_PLAYER_LOG(&ch)->read(LOG_PUBLIC, MAX_LOG_LEN))
		       .find("OFF_INTERVAL") != std::string::npos);
	delete GET_PLAYER_LOG(&ch);
	GET_PLAYER_LOG(&ch) = nullptr;
	save_result = player_save_pipeline_result::queued;
}

static void tell_command_matrix()
{
	char_data alice{}, bob{};
	pc_only_data alice_pc{}, bob_pc{};
	descriptor_data alice_connection{}, bob_connection{};
	alice.only.pc = &alice_pc;
	bob.only.pc = &bob_pc;
	alice.desc = &alice_connection;
	bob.desc = &bob_connection;
	alice_connection.character = &alice;
	bob_connection.character = &bob;
	alice_connection.next = &bob_connection;
	descriptor_list = &alice_connection;
	char alice_name[] = "Alice", bob_name[] = "Bob";
	alice.player.name = alice_name;
	bob.player.name = bob_name;
	alice.player.level = bob.player.level = 20;
	alice.specials.position = bob.specials.position = POS_STANDING + STAT_NORMAL;
	alice_pc.pid = 100;
	bob_pc.pid = 101;
	SET_BIT(alice.specials.act, PLR_ECHO);
	SET_BIT(bob.specials.act, PLR_ECHO);
	OutputProfilePreferences a, b;
	a.set_color(OutputChannel::ChatTell, ATTR_FG(27));
	b.set_color(OutputChannel::ChatTell, ATTR_FG(20));
	assert(update_player_output_preferences(&alice, a) == OutputPreferenceUpdate::PendingSave);
	assert(update_player_output_preferences(&bob, b) == OutputPreferenceUpdate::PendingSave);
	char message[] = "Bob hello &+gforest&n";
	logged.clear();
	const auto calls = language_calls;
	do_tell(&alice, message, 0);
	std::string echo = drain(&alice_connection), received = drain(&bob_connection);
	AnsiString own(echo.c_str()), incoming(received.c_str());
	assert(own.attr(14) == ATTR_FG(27)); // hello in You tell Bob 'hello ...'
	assert(incoming.attr(16) == ATTR_FG(20)); // hello in Alice tells you 'hello ...'
	assert(language_calls == calls + 1 && bob_pc.last_tell == alice.player.name);
	assert(logged.size() == 2 && logged[0].second == LOG_PRIVATE &&
	       logged[1].second == LOG_PRIVATE);
	assert(logged[0].first == "&+WYou tell Bob 'hello &+gforest&n'\r\n");
	char reply[] = "reply text";
	do_reply(&bob, reply, 0);
	AnsiString reply_in(drain(&alice_connection).c_str()),
		reply_own(drain(&bob_connection).c_str());
	assert(reply_in.attr(14) == ATTR_FG(27) && reply_own.attr(16) == ATTR_FG(20));
	bob_pc.ignored = &alice;
	do_tell(&alice, message, 0);
	assert(!bob_connection.output.head &&
	       drain(&alice_connection).find("ignoring") != std::string::npos);
	bob_pc.ignored = nullptr;
	SET_BIT(bob.specials.act, PLR_NOTELL);
	do_tell(&alice, message, 0);
	assert(!bob_connection.output.head &&
	       drain(&alice_connection).find("No-one") != std::string::npos);
	REMOVE_BIT(bob.specials.act, PLR_NOTELL);
	REMOVE_BIT(alice.specials.act, PLR_ECHO);
	do_tell(&alice, message, 0);
	assert(drain(&alice_connection) == "Ok.\r\n");
	drain(&bob_connection);
	SET_BIT(alice.specials.act, PLR_ECHO);
	a.reset(OutputChannel::ChatTell);
	b.reset(OutputChannel::ChatTell);
	assert(update_player_output_preferences(&alice, a) == OutputPreferenceUpdate::PendingSave);
	assert(update_player_output_preferences(&bob, b) == OutputPreferenceUpdate::PendingSave);
	do_tell(&alice, message, 0);
	assert(drain(&alice_connection) == "&+WYou tell Bob 'hello &+gforest&n'\r\n");
	assert(drain(&bob_connection) == "&+WAlice&+W tells you 'hello &+gforest&n'&N\r\n");
	descriptor_list = nullptr;
}

static void begin_paging(P_char ch)
{
	executing_ch = ch;
	SET_BIT(ch->specials.act, PLR_PAGING_ON);
	command_output[0] = 0;
	output_length = 0;
}

static size_t visible_terminal_bytes(const std::string &markup)
{
	char buffer[MAX_STRING_LENGTH];
	AnsiString(markup.c_str()).term(buffer, TL_UNDERLINE);
	size_t bytes = 0;
	for (const char *p = buffer; *p; ++p)
		if (*p == '\x1b')
		{
			while (*p && *p != 'm')
				++p;
			assert(*p);
		}
		else if (*p != '\r')
			++bytes;
	return bytes;
}

int main()
{
#ifdef COLORIZATION_BENCHMARK
	colorization_benchmark();
	return 0;
#endif
	privacy_delivery_matrix();
	privacy_toggle_matrix();
	chat_presentation_matrix();
	char_data actor{}, viewer{}, observer{};
	pc_only_data pc{}, pc2{}, pc3{};
	descriptor_data desc{}, desc2{}, desc3{};
	actor.only.pc = &pc;
	viewer.only.pc = &pc2;
	observer.only.pc = &pc3;
	actor.desc = &desc;
	viewer.desc = &desc2;
	observer.desc = &desc3;
	desc.character = &actor;
	desc2.character = &viewer;
	desc3.character = &observer;
	desc.connected = desc2.connected = desc3.connected = CON_PLAYING;
	actor.specials.position = viewer.specials.position = observer.specials.position =
		STAT_NORMAL;
	char actor_name[] = "water";
	actor.player.name = actor_name;
	WordColorDictionary words = { { "water", ATTR_FG(25) }, { "forest", ATTR_FG(18) } };
	OutputContext style{ OutputChannel::Chat, OutputPolicy::Static, &words };
	OutputContext preserve = style;
	preserve.policy = OutputPolicy::Preserve;

	// The real send boundary owns a separate sequence per receiving connection and
	// channel. Interleaved sends, protected content, replay, and another recipient
	// cannot disturb a room's next frame. No room identity participates.
	OutputStyleRecipe flow;
	flow.kind = OutputRecipeKind::Flow;
	flow.palette = { ATTR_FG(25), ATTR_FG(19), ATTR_FG(27) };
	flow.palette_size = 3;
	flow.width = 2;
	WordRecipeDictionary recipes{ { "water", &flow } };
	OutputContext moving{ OutputChannel::RoomDescription, OutputPolicy::Animated, &words };
	moving.recipes = &recipes;
	const size_t room_channel = (size_t)OutputChannel::RoomDescription;
	send_to_char("water", &actor, LOG_PRIVATE, moving);
	std::string frame_zero = drain(&desc);
	assert(desc.output_sequences[room_channel] == 1);
	for (const char *unchanged : { "stone", "&+rwater&n", "wa&+rte&nr" })
	{
		send_to_char(unchanged, &actor, LOG_NONE, moving);
		assert(drain(&desc) == unchanged);
		assert(desc.output_sequences[room_channel] == 1);
	}
	OutputContext chat_motion = moving;
	chat_motion.channel = OutputChannel::ChatSay;
	send_to_char("water", &actor, LOG_NONE, chat_motion);
	assert(drain(&desc) == frame_zero);
	assert(desc.output_sequences[(size_t)OutputChannel::ChatSay] == 1);
	send_to_char("water", &viewer, LOG_NONE, moving);
	assert(drain(&desc2) == frame_zero && desc2.output_sequences[room_channel] == 1);
	send_to_char("water", &actor, LOG_NONE, moving);
	assert(drain(&desc) != frame_zero && desc.output_sequences[room_channel] == 2);
	OutputContext stationary = moving;
	stationary.policy = OutputPolicy::Static;
	send_to_char("water", &actor, LOG_NONE, stationary);
	assert(drain(&desc) == "&+Bwater&n" && desc.output_sequences[room_channel] == 2);
	stationary.policy = OutputPolicy::Preserve;
	send_to_char("water", &actor, LOG_NONE, stationary);
	assert(drain(&desc) == "water" && desc.output_sequences[room_channel] == 2);
	// Unsigned wrap is defined; a new connection starts again at frame zero.
	desc.output_sequences[room_channel] = UINT64_MAX;
	send_to_char("water", &actor, LOG_NONE, moving);
	drain(&desc);
	assert(desc.output_sequences[room_channel] == 0);
	send_to_char("water", &actor, LOG_NONE, moving);
	assert(drain(&desc) == frame_zero);
	descriptor_data reconnected{};
	reconnected.character = &actor;
	actor.desc = &reconnected;
	send_to_char("water", &actor, LOG_NONE, moving);
	assert(drain(&reconnected) == frame_zero &&
	       reconnected.output_sequences[room_channel] == 1);
	actor.desc = &desc;

	pc.screen_length = 12;
	begin_paging(&actor);
	std::string animated_pages;
	for (int i = 0; i < 20; ++i)
		animated_pages += "water\n";
	send_to_char(animated_pages.c_str(), &actor, LOG_NONE, moving);
	auto frozen_sequence = desc.output_sequences[room_channel];
	assert(frozen_sequence == 2); // one eligible message, not twenty words
	executing_ch = nullptr;
	page_string_real(&desc, command_output);
	std::string animated_page = drain(&desc);
	show_string(&desc, "r");
	assert(drain(&desc) == animated_page &&
	       desc.output_sequences[room_channel] == frozen_sequence);
	while (desc.showstr_count)
	{
		show_string(&desc, "");
		drain(&desc);
	}
	assert(desc.output_sequences[room_channel] == frozen_sequence);
	REMOVE_BIT(actor.specials.act, PLR_PAGING_ON);
	std::string oversized_animation;
	for (int i = 0; i < 8000; ++i)
		oversized_animation += "water ";
	send_to_char(oversized_animation.c_str(), &actor, LOG_NONE, moving);
	assert(drain(&desc) == oversized_animation &&
	       desc.output_sequences[room_channel] == frozen_sequence);

	// Legacy/default and explicit Preserve retain byte-for-byte messages and logs.
	const char *raw = "&Nwater &+rforest&n\n\r&&+?";
	for (int policy : { LOG_PUBLIC, LOG_PRIVATE, LOG_NONE })
	{
		logged.clear();
		send_to_char(raw, &actor, policy);
		assert(drain(&desc) == raw);
		auto baseline_log = logged;
		logged.clear();
		send_to_char(raw, &actor, policy, preserve);
		assert(drain(&desc) == raw && logged == baseline_log);
	}
	logged.clear();
	send_to_char("water", &actor, LOG_PRIVATE, style);
	assert(drain(&desc) == "&+Bwater&n");
	assert(logged.size() == 1 &&
	       logged[0] == std::make_pair(std::string("water"), LOG_PRIVATE));
	send_to_char("water", &actor, LOG_NONE, style);
	assert(drain(&desc) == "&+Bwater&n" && logged.size() == 1);
	actor.player.level = MAXLVLMORTAL + 1;
	send_to_char("water", &actor, style);
	assert(drain(&desc) == "&+Bwater&n" && logged.size() == 1);
	actor.player.level = 1;

	// Match after printf formatting. Queuing never matches across send boundaries.
	send_to_char_f(&actor, style, "%s%s %d", "wa", "ter", 7);
	assert(drain(&desc) == "&+Bwater&n 7");
	send_to_char("wa", &actor, style);
	send_to_char("ter", &actor, preserve);
	send_to_char(" forest", &actor, style);
	assert(desc.output.head == desc.output.tail); // real queue merged these sends
	assert(drain(&desc) == "water &+gforest&n");

	// Switched prefix remains authored and is outside the word renderer/log content.
	desc.original = &actor;
	send_to_char("water", &actor, style);
	assert(drain(&desc) == "&+M@&+Wwater&n: &+Bwater&n");
	desc.original = nullptr;

	// Real act() does recipient substitutions, entity protection and capitalization.
	rooms[0].people = &actor;
	actor.next_in_room = &viewer;
	viewer.next_in_room = &observer;
	hidden_recipient = &observer;
	char body[] = "wa&nter";
	act("$n sees $T in a forest.", false, &actor, nullptr, body, TO_ROOM | ACT_PRIVATE, style);
	assert(AnsiString(drain(&desc2).c_str()) ==
	       AnsiString("Water sees &+Bwater&n in a &+gforest&n.\n"));
	assert(AnsiString(drain(&desc3).c_str()) ==
	       AnsiString("Someone sees &+Bwater&n in a &+gforest&n.\n"));
	assert(!desc.output.head);
	act("water", false, &actor, nullptr, nullptr, TO_CHAR, style);
	assert(AnsiString(drain(&desc).c_str()) == AnsiString("&+BWater&n\n"));
	act("water", false, &actor, nullptr, nullptr, TO_CHAR);
	assert(drain(&desc) == "Water\n\r");
	visible = false;
	act("water", true, &actor, nullptr, nullptr, TO_ROOM, style);
	assert(!desc2.output.head && !desc3.output.head);
	visible = true;
	viewer.specials.z_cord = 1;
	observer.specials.affected_by4 = AFF4_DEAF;
	act("water", false, &actor, nullptr, nullptr, TO_ROOM | ACT_SILENCEABLE, style);
	assert(!desc2.output.head && !desc3.output.head);
	viewer.specials.z_cord = 0;
	observer.specials.affected_by4 = 0;

	// Snoop gets the already selected colors, without a second dictionary pass.
	std::string frozen;
	assert(render_output_message("water\nforest", style, frozen));
	char snoop[MAX_STRING_LENGTH];
	format_to_snoopers(frozen.data(), snoop);
	assert(AnsiString(snoop) == AnsiString("&+C%&n &+Bwater&n\n&+C%&n &+gforest&n"));
	std::string near_limit_snoop, expected_snoop;
	for (int i = 0; i < 1675; ++i)
	{
		near_limit_snoop += "water 雪\n";
		expected_snoop += "% water 雪\n";
	}
	assert(render_output_message(near_limit_snoop.c_str(), style, frozen));
	format_to_snoopers(frozen.data(), snoop);
	char terminal[MAX_STRING_LENGTH];
	AnsiString(snoop).term(terminal, TL_UNDERLINE);
	std::string snooped_plain;
	for (const char *p = terminal; *p; ++p)
	{
		if (*p == '\x1b')
		{
			while (*p && *p != 'm')
				++p;
			assert(*p);
		}
		else if (*p != '\r')
			snooped_plain += *p;
	}
	assert(snooped_plain == expected_snoop);
	// Six bytes a line more than the block: a full block of short lines is cut at the
	// snoop buffer's end instead of running past it.
	std::string short_lines;
	while (short_lines.size() + 2 < MAX_STRING_LENGTH)
		short_lines += "x\n";
	static char guarded[MAX_STRING_LENGTH + 64];
	memset(guarded, '#', sizeof(guarded));
	format_to_snoopers(short_lines.data(), guarded);
	assert(strlen(guarded) < MAX_STRING_LENGTH);
	for (size_t i = MAX_STRING_LENGTH; i < sizeof(guarded); ++i)
		assert(guarded[i] == '#');

	// Pager replay/refresh is frozen even after the dictionary changes, and does
	// not log decorated text or change the original LOG_NONE/LOG_PRIVATE choice.
	pc.screen_length = 12;
	begin_paging(&actor);
	logged.clear();
	std::string pages;
	for (int i = 0; i < 20; ++i)
		pages += "water\n";
	send_to_char(pages.c_str(), &actor, LOG_PRIVATE, style);
	send_to_char("forest\n", &actor, LOG_NONE, style);
	assert(logged.size() == 1 && logged[0].first == pages && logged[0].second == LOG_PRIVATE);
	std::string accumulated = command_output;
	assert(accumulated.find("&+Bwater") != std::string::npos);
	executing_ch = nullptr;
	words["water"] = ATTR_FG(20);
	page_string_real(&desc, command_output);
	std::string first_page = drain(&desc);
	assert(first_page.find("&+Bwater") != std::string::npos);
	show_string(&desc, "r");
	assert(drain(&desc) == first_page);
	assert(logged.size() == 1);
	while (desc.showstr_count)
	{
		show_string(&desc, "");
		drain(&desc);
	}
	assert(logged.size() == 1);

	// Literal ampersands do not advance the legacy pager's column counter. Added
	// markup across several sends must not turn a deliverable page into a rejected one.
	char command[] = "output-test";
	for (int count : { 1, 3 })
		for (OutputPolicy policy : { OutputPolicy::Preserve, OutputPolicy::Static })
		{
			OutputContext amp_style{ OutputChannel::Chat, policy, nullptr,
						 ATTR_FG(25) };
			std::string amp_chunk(8000, '&');
			command_action = [&](P_char ch)
			{
				for (int i = 0; i < count; ++i)
					send_to_char(amp_chunk.c_str(), ch, LOG_NONE, amp_style);
			};
			process_with_paging(&actor, command);
			std::string output = drain(&desc);
			assert(AnsiString(output.c_str()).size() == amp_chunk.size() * count);
			assert(visible_terminal_bytes(output) == amp_chunk.size() * count);
			assert(GET_ATTR(AnsiString(output.c_str())[0]) ==
			       (count == 1 && policy == OutputPolicy::Static ? ATTR_FG(25) : 0));
		}
	// The combined markup can fit while its terminal expansion does not. Authored
	// red ampersands alternate with default ampersands that acquire the base color.
	std::string terminal_chunk;
	for (int i = 0; i < 2200; ++i)
		terminal_chunk += "&+r&&n&";
	for (OutputPolicy policy : { OutputPolicy::Preserve, OutputPolicy::Static })
	{
		OutputContext amp_style{ OutputChannel::Chat, policy, nullptr, ATTR_FG(25) };
		command_action = [&](P_char ch)
		{
			for (int i = 0; i < 2; ++i)
				send_to_char(terminal_chunk.c_str(), ch, LOG_NONE, amp_style);
		};
		process_with_paging(&actor, command);
		assert(visible_terminal_bytes(drain(&desc)) == 8800);
	}
	// Falling back at finalization must retain the legacy accumulation warning.
	std::string warning_baseline;
	for (OutputPolicy policy : { OutputPolicy::Preserve, OutputPolicy::Static })
	{
		OutputContext amp_style{ OutputChannel::Chat, policy, nullptr, ATTR_FG(25) };
		command_action = [&](P_char ch)
		{
			std::string amp_chunk(8000, '&');
			for (int i = 0; i < 3; ++i)
				send_to_char(amp_chunk.c_str(), ch, LOG_NONE, amp_style);
			std::string excess(MAX_COMMAND_OUTPUT, 'x');
			send_to_char(excess.c_str(), ch, LOG_NONE, amp_style);
		};
		process_with_paging(&actor, command);
		std::string output = drain(&desc);
		assert(output.find("the list goes on") != std::string::npos);
		if (policy == OutputPolicy::Preserve)
			warning_baseline = output;
		else
			assert(output == warning_baseline);
	}
	// Main-menu output bypasses paging even when the paging preference is set.
	// Turning paging off during a command also makes replay send the whole command.
	for (bool menu : { false, true })
		for (OutputPolicy policy : { OutputPolicy::Preserve, OutputPolicy::Static })
		{
			OutputContext menu_style{ OutputChannel::Chat, policy, &words };
			std::string menu_chunk;
			for (int i = 0; i < 1600; ++i)
				menu_chunk += "water ";
			SET_BIT(actor.specials.act, PLR_PAGING_ON);
			desc.connected = menu ? CON_MAIN_MENU : CON_PLAYING;
			command_action = [&](P_char ch)
			{
				for (int i = 0; i < 4; ++i)
					send_to_char(menu_chunk.c_str(), ch, LOG_NONE, menu_style);
				if (!menu)
					REMOVE_BIT(ch->specials.act, PLR_PAGING_ON);
			};
			process_with_paging(&actor, command);
			assert(visible_terminal_bytes(drain(&desc)) == menu_chunk.size() * 4);
		}
	desc.connected = CON_PLAYING;
	SET_BIT(actor.specials.act, PLR_PAGING_ON);
	command_action = {};

	// Styling may never displace later visible output at the accumulation limit.
	words["water"] = ATTR_FG(25);
	begin_paging(&actor);
	std::string original;
	std::string chunk;
	for (int i = 0; i < 4000; ++i)
		chunk += "water ";
	for (int i = 0; i < 40; ++i)
	{
		send_to_char(chunk.c_str(), &actor, LOG_NONE, style);
		original += chunk;
	}
	assert(original.size() < MAX_COMMAND_OUTPUT);
	assert(std::string(command_output) == original && output_length == original.size());
	// Once original content reaches the legacy warning, later sends must leave it.
	std::string excess(MAX_COMMAND_OUTPUT, 'x');
	send_to_char(excess.c_str(), &actor, LOG_NONE, style);
	std::string warned = command_output;
	assert(warned.find("the list goes on") != std::string::npos);
	send_to_char("water", &actor, LOG_NONE, style);
	assert(std::string(command_output) == warned);
	executing_ch = nullptr;
	REMOVE_BIT(actor.specials.act, PLR_PAGING_ON);

	// Real recipient fanout resolves each character's settings after visibility.
	// A known template's color may change; authored names/body and logs retain theirs.
	OutputProfilePreferences personal, other;
	personal.set_color(OutputChannel::ChatTell, ATTR_FG(27));
	other.set_color(OutputChannel::ChatTell, ATTR_FG(20));
	pc.output_preferences = personal.state();
	pc2.output_preferences = other.state();
	const auto actor_phase = desc.output_sequences[room_channel];
	const auto viewer_phase = desc2.output_sequences[room_channel];
	for (auto [recipient, connection, color] : std::vector<std::tuple<P_char, P_desc, int>>{
		     { &actor, &desc, 27 }, { &viewer, &desc2, 20 }, { &observer, &desc3, 0 } })
	{
		logged.clear();
		PlayerOutputMessage(recipient, OutputChannel::ChatTell)
			.literal("&+W")
			.entity("&+mName&n", StyleOrigin::Sender)
			.literal("&+W tells you '")
			.body("hello &+gforest&n wa&+rter&n")
			.literal("'&N\r\n")
			.send(LOG_PRIVATE);
		std::string text = drain(connection);
		const std::string original =
			"&+W&+mName&n&+W tells you 'hello &+gforest&n wa&+rter&n'&N\r\n";
		assert(logged.size() == 1 && logged[0] == std::make_pair(original, LOG_PRIVATE));
		if (!color)
			assert(text == original);
		else
		{
			AnsiString ansi(text.c_str());
			assert(ansi.attr(0) == ATTR_FG(21));
			assert(ansi.attr(16) == ATTR_FG(color)); // hello
			assert(ansi.attr(22) == ATTR_FG(18)); // authored forest
			assert(ansi.attr(31) == ATTR_FG(20)); // partially styled water
		}
	}
	assert(desc.output_sequences[room_channel] == actor_phase &&
	       desc2.output_sequences[room_channel] == viewer_phase);
	for (OutputChannel channel :
	     { OutputChannel::ChatSay, OutputChannel::ChatGuild, OutputChannel::ChatShout,
	       OutputChannel::ChatYell, OutputChannel::ChatWhisper, OutputChannel::ChatAsk,
	       OutputChannel::ChatPetition })
	{
		personal.set_color(channel, ATTR_FG(27));
		other.set_color(channel, ATTR_FG(20));
		pc.output_preferences = personal.state();
		pc2.output_preferences = other.state();
		auto adopted = recipient_output_context(channel);
		act("$n says '$T'", false, &actor, nullptr, (void *)"hello", TO_CHAR | ACT_PRIVATE,
		    adopted);
		AnsiString own(drain(&desc).c_str());
		assert(own.attr(own.size() - 3) == ATTR_FG(27));
		act("$n says '$T'", false, &actor, nullptr, (void *)"hello", TO_ROOM | ACT_PRIVATE,
		    adopted);
		AnsiString incoming(drain(&desc2).c_str()), inherited(drain(&desc3).c_str());
		assert(incoming.attr(incoming.size() - 3) == ATTR_FG(20));
		assert(inherited.attr(inherited.size() - 3) == 0);
		assert(incoming.attr(0) == 0); // entity role never mistaken for body
		pc2.ignored = &actor;
		act("hello", false, &actor, nullptr, nullptr, TO_ROOM, adopted);
		assert(!desc2.output.head);
		drain(&desc3);
		pc2.ignored = nullptr;
	}
	personal.reset_all();
	other.reset_all();
	pc.output_preferences = personal.state();
	pc2.output_preferences = other.state();
	PlayerOutputMessage(&actor, OutputChannel::ChatTell)
		.literal("&+Whello&N\r\n")
		.send(LOG_NONE);
	assert(drain(&desc) == "&+Whello&N\r\n");
	personal.set_color(OutputChannel::ChatTell, ATTR_FG(27));
	pc.output_preferences = personal.state();
	std::string near_limit(MAX_STRING_LENGTH - 7, 'x');
	PlayerOutputMessage(&actor, OutputChannel::ChatTell)
		.literal("&+W")
		.body(near_limit)
		.literal("&N\r\n")
		.send(LOG_NONE);
	std::string fallback = "&+W" + near_limit + "&N\r\n";
	fallback.resize(MAX_STRING_LENGTH - 1);
	assert(drain(&desc) == fallback);
	personal.reset_all();
	pc.output_preferences = personal.state();

	// Oversized expansion returns original bytes, including its original UTF-8.
	std::string large;
	for (int i = 0; i < 8000; ++i)
		large += "water ";
	send_to_char(large.c_str(), &actor, LOG_NONE, style);
	assert(drain(&desc) == large);
	tell_command_matrix();
	world_output_matrix();
	combat_prompt_matrix();
	artifact_activation_matrix();
	news_prompt_matrix();
	puts("Output integration: tell/reply, recipient profiles, sends, act, queue merging, privacy, paging and snoop passed");
}
