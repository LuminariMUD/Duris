// Exercise the production WebSocket dispatcher, game handler, queue and pager.
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "net/command_latency.h"
#include "net/session_input.h"
#include "net/ws_handlers.h"
#include "net/output_style.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

// Use ordinary allocations so ASan can check queue and pager ownership.
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

static std::string output;
static std::vector<std::string> commands;
static unsigned errors;
static bool creation_grant_blocked, playing_queue_blocked;
static unsigned playing_queue_calls;

void logit(const char *, const char *, ...)
{
	assert(false);
}
void ws_send_system(P_desc, const char *status, const char *message)
{
	assert(!strcmp(status, "error") && !strcmp(message, "Character not playing"));
	++errors;
}
void send_to_char(const char *text, P_char, int)
{
	output += text;
}
void send_to_char(const char *text, P_char ch, int log, const OutputContext &)
{
	send_to_char(text, ch, log);
}

// This fixture has no pending world transactions, casting or account admission.
bool pwipe_launch_admit(P_desc)
{
	return true;
}
bool item_creation_grant_blocks_commands(P_char)
{
	return creation_grant_blocked;
}
static bool casting_input_for_descriptor(P_desc, P_char)
{
	return false;
}
int get_casting_cmd_from_q(P_char, struct txt_q *, char *)
{
	assert(false);
	return 0;
}
static int get_playing_cmd_from_q(P_char, struct txt_q *queue, char *input)
{
	++playing_queue_calls;
	if (playing_queue_blocked)
		return 0;
	return get_from_q(queue, input);
}
static void dispatch_playing_command(P_char, char *input)
{
	commands.emplace_back(input);
}
void gmcp_input_receipt(P_desc, const char *) {}
void gmcp_session_update(P_desc) {}
int is_desc_valid(P_desc)
{
	return true;
}
void string_add(P_desc, char *)
{
	assert(false);
}
void nanny(P_desc, char *)
{
	assert(false);
}
static void prepare_descriptor_latency_event(command_latency_event *, command_latency_kind, P_desc,
					     const char *)
{
}
static uint64_t loop_monotonic_us()
{
	return 0;
}
uint64_t latency_trace_elapsed_us(uint64_t, uint64_t)
{
	return 0;
}
void command_latency_record(command_latency_tracker *, const command_latency_event *, uint64_t) {}
void command_latency_event_set_get_arguments(command_latency_event *, const char *) {}
size_t command_latency_take_bulk_items()
{
	return 0;
}

#include "production_pager.inc"

static void assert_empty_queue(P_desc d)
{
	assert(!d->input.head && !d->input.tail);
}

static void assert_pager_released(P_desc d)
{
	assert(!d->showstr_count && !d->showstr_head && !d->showstr_vector);
}

static void begin_pager(P_desc d)
{
	assert_empty_queue(d);
	assert_pager_released(d);
	d->showstr_head = strdup("page1\npage2\npage3\n");
	d->showstr_vector = (char **)calloc(3, sizeof(char *));
	for (int i = 0; i < 3; ++i)
		d->showstr_vector[i] = d->showstr_head + i * 6;
	d->showstr_count = 3;
	d->showstr_page = 1; // Page 1 was already displayed by the originating command.
	output.clear();
}

static void send_json(P_desc d, const char *json)
{
	cJSON *data = cJSON_Parse(json);
	assert(data);
	ws_handle_command(d, "game", data);
	cJSON_Delete(data);
}

static void dispatch_input(P_desc d, session_input_route expected)
{
	char input[MAX_STRING_LENGTH] = {};
	const auto route = select_session_input(d, d->character, input);
	assert(route == expected);
	command_latency_tracker latency{};
	dispatch_session_input(d, d->character, input, route, &latency);
}

int main()
{
	descriptor_data d{};
	char_data ch{};
	d.connected = CON_PLAYING;
	d.character = &ch;
	ch.desc = &d;

	for (const char *json : { R"("")", R"({"command":""})" })
	{
		begin_pager(&d);
		send_json(&d, json);
		// Admission must enqueue exactly one owned empty line, without displaying a page.
		assert(d.input.head && d.input.head == d.input.tail && !d.input.head->next);
		assert(!*d.input.head->text && d.showstr_page == 1 && output.empty());
		dispatch_input(&d, session_input_route::pager);
		assert(d.showstr_count == 3 && d.showstr_page == 2 && output == "page2\n&N");
		assert_empty_queue(&d);
		output.clear();
		dispatch_input(&d, session_input_route::none);
		assert(d.showstr_page == 2 && output.empty());
		send_json(&d, json);
		dispatch_input(&d, session_input_route::pager);
		assert(output == "page3\n");
		assert_pager_released(&d);
		assert_empty_queue(&d);
	}
	puts("PASS: blank string/object commands advance exactly one page through completion");

	begin_pager(&d);
	send_json(&d, R"("")");
	send_json(&d, R"({"command":""})");
	send_json(&d, R"("look")");
	dispatch_input(&d, session_input_route::pager);
	assert(d.showstr_page == 2 && output == "page2\n&N");
	assert(d.input.head && !*d.input.head->text && d.input.head != d.input.tail);
	output.clear();
	dispatch_input(&d, session_input_route::pager);
	assert(output == "page3\n");
	assert_pager_released(&d);
	assert(d.input.head == d.input.tail && !strcmp(d.input.head->text, "look"));
	dispatch_input(&d, session_input_route::playing);
	assert(commands == std::vector<std::string>{ "look" });
	assert_empty_queue(&d);
	puts("PASS: queued continuations remain separate and ordered before the next game command");

	begin_pager(&d);
	for (const auto &test : std::vector<std::pair<const char *, const char *>>{
		     { R"({"command":"2"})", "page2\n&N" },
		     { R"("r")", "page2\n&N" },
		     { R"({"command":"b"})", "page1\n&N" },
		     { R"(" ")", "page2\n&N" },
		     { R"("q")", "" } })
	{
		output.clear();
		send_json(&d, test.first);
		dispatch_input(&d, session_input_route::pager);
		assert(output == test.second);
		assert_empty_queue(&d);
	}
	assert_pager_released(&d);
	puts("PASS: numeric page selection, refresh, back, whitespace and quit retain their behavior");

	for (const char *help : { "help combat", "  HeLp combat", "help" })
	{
		begin_pager(&d);
		commands.clear();
		// Both transports feed this same owned command queue; WebSocket is
		// exercised above, while a typed Telnet command arrives without JSON.
		write_to_q(help, &d.input, 0);
		const unsigned before = playing_queue_calls;
		dispatch_input(&d, session_input_route::playing);
		assert(playing_queue_calls == before + 1);
		assert(commands == std::vector<std::string>{ help });
		assert(output.empty());
		assert_pager_released(&d);
		assert_empty_queue(&d);
		dispatch_input(&d, session_input_route::none);
		assert(commands.size() == 1);
	}
	begin_pager(&d);
	commands.clear();
	send_json(&d, R"({"command":"help combat"})");
	send_json(&d, R"("look")");
	dispatch_input(&d, session_input_route::playing);
	assert_pager_released(&d);
	assert(commands == std::vector<std::string>{ "help combat" });
	assert(d.input.head == d.input.tail && !strcmp(d.input.head->text, "look"));
	dispatch_input(&d, session_input_route::playing);
	assert((commands == std::vector<std::string>{ "help combat", "look" }));
	assert_empty_queue(&d);
	puts("PASS: typed and WebSocket help replace paging through normal dispatch exactly once");

	begin_pager(&d);
	commands.clear();
	send_json(&d, R"("help combat")");
	creation_grant_blocked = true;
	dispatch_input(&d, session_input_route::none);
	creation_grant_blocked = false;
	SET_BIT(ch.specials.act2, PLR2_WAIT);
	dispatch_input(&d, session_input_route::none);
	REMOVE_BIT(ch.specials.act2, PLR2_WAIT);
	SET_BIT(ch.specials.affected_by, AFF_CHARM);
	dispatch_input(&d, session_input_route::none);
	REMOVE_BIT(ch.specials.affected_by, AFF_CHARM);
	playing_queue_blocked = true;
	const unsigned before = playing_queue_calls;
	dispatch_input(&d, session_input_route::none);
	assert(playing_queue_calls == before + 1);
	assert(d.showstr_count == 3 && d.showstr_page == 1 && output.empty());
	assert(d.input.head == d.input.tail && !strcmp(d.input.head->text, "help combat"));
	assert(commands.empty());
	playing_queue_blocked = false;
	dispatch_input(&d, session_input_route::playing);
	assert(commands == std::vector<std::string>{ "help combat" });
	assert_pager_released(&d);
	assert_empty_queue(&d);
	puts("PASS: help respects action, charm, creation and playing-queue gates before releasing pages");

	for (const char *text : { "helpful", "look", "h" })
	{
		begin_pager(&d);
		commands.clear();
		write_to_q(text, &d.input, 0);
		dispatch_input(&d, session_input_route::pager);
		assert(commands.empty());
		assert_pager_released(&d);
		assert_empty_queue(&d);
	}
	begin_pager(&d);
	char *editor_text = nullptr;
	d.str = &editor_text;
	send_json(&d, R"("help combat")");
	char input[MAX_STRING_LENGTH] = {};
	assert(select_session_input(&d, &ch, input) == session_input_route::pager);
	assert(d.showstr_count == 3); // Do not promote editor input to a game command.
	d.str = nullptr;
	free_paging_data(&d);
	begin_pager(&d);
	d.connected = CON_MAIN_MENU;
	write_to_q("help combat", &d.input, 0);
	assert(select_session_input(&d, &ch, input) == session_input_route::pager);
	assert(d.showstr_count == 3);
	d.connected = CON_PLAYING;
	free_paging_data(&d);
	assert_empty_queue(&d);
	puts("PASS: other pager input, editors and non-playing states keep their existing owner");

	begin_pager(&d);
	for (const char *json :
	     { "null", "false", "42", "[]", "{}", R"({"command":null})", R"({"command":false})",
	       R"({"command":42})", R"({"command":[]})", R"({"command":{}})" })
		send_json(&d, json);
	ws_handle_command(&d, "game", nullptr);
	assert_empty_queue(&d);
	assert(d.showstr_page == 1 && output.empty() && errors == 0);
	free_paging_data(&d);
	puts("PASS: missing/malformed game payloads do not enqueue or advance the pager");

	for (const char *json : { R"("")", R"({"command":""})", R"("look")" })
	{
		const unsigned before = errors;
		d.connected = CON_GET_ACCT_NAME;
		send_json(&d, json);
		assert_empty_queue(&d);
		d.connected = CON_PLAYING;
		d.character = nullptr;
		send_json(&d, json);
		assert_empty_queue(&d);
		d.character = &ch;
		assert(errors == before + 2);

		// Exercise the real dispatch guards even with an otherwise playing descriptor.
		d.login_password_job = reinterpret_cast<decltype(d.login_password_job)>(&d);
		send_json(&d, json);
		assert_empty_queue(&d);
		d.login_password_job = nullptr;
		d.password_request = reinterpret_cast<decltype(d.password_request)>(&d);
		send_json(&d, json);
		assert_empty_queue(&d);
		d.password_request = nullptr;
		d.writer_wait_id = 1;
		send_json(&d, json);
		assert_empty_queue(&d);
		d.writer_wait_id = 0;
		d.connected = CON_FLUSH;
		send_json(&d, json);
		assert_empty_queue(&d);
		d.connected = CON_PLAYING;
		send_json(nullptr, json);
		assert(errors == before + 2);
	}
	puts("PASS: non-playing, missing-character, pending-authentication and closing states refuse input");

	commands.clear();
	send_json(&d, R"("look")");
	send_json(&d, R"({"command":"help combat"})");
	send_json(&d, R"("")");
	send_json(&d, R"({"command":""})");
	for (int i = 0; i < 4; ++i)
		dispatch_input(&d, session_input_route::playing);
	assert((commands == std::vector<std::string>{ "look", "help combat", "", "" }));
	assert_empty_queue(&d);
	puts("PASS: ordinary and blank game commands retain their text outside paging");
}
