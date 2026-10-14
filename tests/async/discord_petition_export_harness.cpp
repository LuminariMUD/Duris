#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "net/discord_bridge.h"
#include "net/discord_petition.h"
#include "net/unicode.h"
#include "net/output_style.h"
#include "player/output_message.h"

#include <algorithm>
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstring>
#include <functional>
#include <iostream>
#include <string>
#include <vector>
#include <arpa/inet.h>
#include <cjson/cJSON.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

struct delivery
{
	P_char recipient;
	std::string text;
	std::string kind;
};
static std::vector<delivery> delivered;
static std::vector<std::string> audit;
static bool sane = true;
static P_char invisible_target = nullptr;
P_desc descriptor_list = nullptr;

void send_to_char(const char *text, P_char ch)
{
	delivered.push_back({ ch, text, "text" });
}
void send_to_char(const char *text, P_char ch, int)
{
	send_to_char(text, ch);
}
void send_to_char(const char *text, P_char ch, const OutputContext &)
{
	send_to_char(text, ch);
}
void act(const char *text, int, P_char, P_obj, void *recipient, int, const OutputContext &)
{
	delivered.push_back({ static_cast<P_char>(recipient), text, "act" });
}
void gmcp_comm_channel(P_char ch, const char *channel, const char *name, const char *message)
{
	delivered.push_back({ ch, std::string(channel) + ":" + name + ":" + message, "gmcp" });
}
void logit(const char *kind, const char *format, ...)
{
	char buffer[MAX_STRING_LENGTH];
	va_list args;
	va_start(args, format);
	vsnprintf(buffer, sizeof(buffer), format, args);
	va_end(args);
	audit.push_back(std::string(kind) + ":" + buffer);
}
float get_property(const char *, double)
{
	return 0;
}
bool SanityCheck(P_char, const char *)
{
	return sane;
}
bool ac_can_see(P_char, P_char target, bool)
{
	return target != invisible_target;
}
const char *player_output_template(char_data *, OutputChannel, const char *legacy, const char *)
{
	return legacy;
}

#include "petition_commands.inc"

struct player
{
	char_data ch{};
	pc_only_data pc{};
	descriptor_data desc{};
	std::string name;
	player(const char *value, int level = 10)
		: name(value)
	{
		ch.player.name = name.data();
		ch.player.level = level;
		ch.only.pc = &pc;
		ch.desc = &desc;
		ch.specials.act = PLR_PETITION | PLR_ECHO;
		desc.character = &ch;
		desc.connected = CON_PLAYING;
	}
};

static void recipients(std::initializer_list<player *> players)
{
	descriptor_list = nullptr;
	P_desc *tail = &descriptor_list;
	for (auto *p : players)
	{
		*tail = &p->desc;
		tail = &p->desc.next;
	}
	*tail = nullptr;
}

static unsigned deliveries(P_char to, const char *kind)
{
	return std::count_if(delivered.begin(), delivered.end(),
			     [=](const auto &d) { return d.recipient == to && d.kind == kind; });
}

static void invoke(void (*command)(P_char, char *, int), player &sender, const std::string &text)
{
	delivered.clear();
	audit.clear();
	std::string argument = text;
	command(&sender.ch, argument.data(), 0);
	assert(argument == text);
}

static int endpoint()
{
	discord_bridge_shutdown();
	int peer = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
	assert(peer >= 0);
	sockaddr_in address{};
	address.sin_family = AF_INET;
	address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	assert(bind(peer, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0);
	socklen_t size = sizeof(address);
	assert(getsockname(peer, reinterpret_cast<sockaddr *>(&address), &size) == 0);
	close(peer);
	setenv("DURIS_DISCORD_ENABLED", "TRUE", 1);
	setenv("DURIS_DISCORD_PORT", std::to_string(ntohs(address.sin_port)).c_str(), 1);
	unsetenv("DURIS_DISCORD_AUTH_TOKEN");
	unsetenv("DURIS_DISCORD_MAX_RECORD_BYTES");
	assert(discord_bridge_init());
	peer = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
	assert(connect(peer, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0);
	assert(fcntl(peer, F_SETFL, O_NONBLOCK) == 0);
	for (unsigned i = 0; i < 1000 && !discord_bridge_get_status().connected; ++i)
	{
		discord_bridge_poll();
		usleep(1000);
	}
	assert(discord_bridge_get_status().authenticated);
	return peer;
}

static std::string received(int peer)
{
	const auto expected_bytes = discord_bridge_get_status().queued_bytes;
	std::string wire;
	char buffer[16384];
	for (unsigned i = 0; i < 10000; ++i)
	{
		discord_bridge_flush();
		ssize_t bytes = read(peer, buffer, sizeof(buffer));
		if (bytes > 0)
			wire.append(buffer, bytes);
		else if (discord_bridge_get_status().queued_events == 0 &&
			 wire.size() >= expected_bytes)
			return wire;
		else
		{
			assert(errno == EAGAIN || errno == EINTR);
			pollfd descriptor{ peer, POLLIN, 0 };
			assert(poll(&descriptor, 1, 1000) > 0);
		}
	}
	assert(!"endpoint failed to drain");
	return wire;
}

static void event(int peer, const std::string &name, const std::string &message)
{
	std::string wire = received(peer);
	assert(std::count(wire.begin(), wire.end(), '\n') == 1);
	cJSON *record = cJSON_ParseWithOpts(wire.c_str(), nullptr, true);
	assert(record);
	assert(std::string(cJSON_GetObjectItem(record, "channel")->valuestring) == "petition");
	assert(std::string(cJSON_GetObjectItem(record, "name")->valuestring) == name);
	assert(std::string(cJSON_GetObjectItem(record, "message")->valuestring) == message);
	assert(cJSON_GetObjectItem(record, "emoted")->valueint == 0);
	cJSON_Delete(record);
}

static void accepted(int peer)
{
	for (int staff_count : { 0, 1, 3 })
		for (bool echo : { false, true })
		{
			player petitioner("Player"), staff("Staff", 64), monitor("Monitor", 64),
				third("Third", 64);
			player opted_out("Optedout", 64), mortal("Mortal");
			opted_out.ch.specials.act &= ~PLR_PETITION;
			petitioner.ch.specials.act = PLR_PETITION | (echo ? PLR_ECHO : 0);
			if (staff_count == 0)
				recipients({ &petitioner, &mortal });
			else if (staff_count == 1)
				recipients({ &petitioner, &staff, &opted_out, &mortal });
			else
				recipients({ &petitioner, &staff, &monitor, &third, &opted_out,
					     &mortal });
			invoke(do_petition, petitioner, "  &+rHelp&n $n @everyone 你好 🔥");
			event(peer, "Player", "Help $n @everyone 你好 🔥");
			assert(deliveries(&petitioner.ch, "text") == 1);
			assert(deliveries(&petitioner.ch, "gmcp") == 1);
			assert(delivered.front().text.find(echo ? "You petition" : "Ok.") !=
			       std::string::npos);
			assert(std::count_if(delivered.begin(), delivered.end(),
					     [](auto &d) {
						     return d.kind == "act" &&
							    d.text.find("$$n") != std::string::npos;
					     }) == staff_count);
			assert(deliveries(&opted_out.ch, "act") == 0 &&
			       deliveries(&mortal.ch, "act") == 0);
			assert(audit.size() == 1 &&
			       audit[0].find("petitioned") != std::string::npos);

			// Zero, one, and multiple additional staff observers; sender need not be
			// present in the descriptor list for a successful command to export.
			staff.ch.specials.act = PLR_PETITION | (echo ? PLR_ECHO : 0);
			if (staff_count == 0)
				recipients({ &petitioner, &mortal });
			else if (staff_count == 1)
				recipients({ &petitioner, &monitor, &opted_out, &mortal });
			else
				recipients({ &petitioner, &monitor, &third, &staff, &opted_out,
					     &mortal });
			invoke(do_ptell, staff, "Player &+gChecking&n $1 \\\"quote\\\" 🔥");
			event(peer, "Staff -> Player", "Checking $1 \\\"quote\\\" 🔥");
			assert(deliveries(&staff.ch, "text") == 1 &&
			       deliveries(&staff.ch, "gmcp") == 1);
			assert(deliveries(&petitioner.ch, "text") == 1 &&
			       deliveries(&petitioner.ch, "gmcp") == 1);
			assert(deliveries(&monitor.ch, "gmcp") == (staff_count ? 1u : 0u));
			assert(deliveries(&third.ch, "gmcp") == (staff_count == 3 ? 1u : 0u));
			assert(deliveries(&opted_out.ch, "gmcp") == 0 &&
			       deliveries(&mortal.ch, "gmcp") == 0);
			assert(audit.size() == 1 && audit[0].find("ptells") != std::string::npos);
		}
}

static void rejected(int peer)
{
	player player_one("Player"), staff("Staff", 64);
	recipients({ &player_one, &staff });
	for (auto reject :
	     std::vector<std::function<void()>>{
		     [&] { player_one.ch.specials.act |= ACT_ISNPC; },
		     [&] { player_one.ch.specials.act |= PLR_SILENCE; },
		     [&] { player_one.ch.specials.act2 |= PLR2_B_PETITION; },
		     [&] { player_one.ch.specials.act &= ~PLR_PETITION; } })
	{
		reject();
		invoke(do_petition, player_one, "Rejected");
		assert(received(peer).empty() && delivered.size() == 1 && audit.empty());
		player_one.ch.specials.act = PLR_PETITION | PLR_ECHO;
		player_one.ch.specials.act2 = 0;
	}
	for (const char *text : { "", "   " })
	{
		invoke(do_petition, player_one, text);
		assert(received(peer).empty() && delivered[0].text == "Petition what?\r\n");
	}
	for (const char *text : { "", "Player", "Missing hi", "Staff self" })
	{
		invoke(do_ptell, staff, text);
		assert(received(peer).empty() && delivered.size() == 1 && audit.empty());
	}
	for (auto reject :
	     std::vector<std::function<void()>>{ [&] { staff.ch.specials.act |= ACT_ISNPC; },
						 [&] { player_one.ch.specials.act |= ACT_ISNPC; },
						 [&] { player_one.ch.desc = nullptr; },
						 [&] { player_one.desc.connected = CON_GET_RACE; },
						 [&] { invisible_target = &player_one.ch; },
						 [&]
						 {
							 player_one.ch.player.level = 64;
							 player_one.pc.wiz_invis = 62;
						 } })
	{
		reject();
		invoke(do_ptell, staff, "Player Rejected");
		assert(received(peer).empty() && delivered.size() == 1 && audit.empty());
		staff.ch.specials.act = PLR_PETITION | PLR_ECHO;
		player_one.ch.specials.act = PLR_PETITION | PLR_ECHO;
		player_one.ch.desc = &player_one.desc;
		player_one.desc.connected = CON_PLAYING;
		player_one.ch.player.level = 10;
		player_one.pc.wiz_invis = 0;
		invisible_target = nullptr;
	}
	sane = false;
	invoke(do_ptell, staff, "Player Rejected");
	assert(received(peer).empty() && audit.size() == 1);
	sane = true;
	char notice[] = "Staff notification";
	send_to_gods(notice);
	assert(received(peer).empty());
}

static void concealment(int peer)
{
	player staff("Staff", 64), target("Player");
	recipients({ &target, &staff });
	for (auto conceal :
	     std::vector<std::function<void()>>{
		     [&] { staff.pc.wiz_invis = 1; }, [&] { staff.pc.wiz_invis = 64; },
		     [&] { staff.ch.specials.affected_by = AFF_INVISIBLE; },
		     [&] { staff.ch.specials.affected_by = AFF_HIDE; },
		     [&] { staff.ch.specials.affected_by = AFF_WRAITHFORM; },
		     [&] { staff.ch.specials.affected_by2 = AFF2_CONCEALMENT; },
		     [&] { staff.ch.specials.affected_by3 = AFF3_ECTOPLASMIC_FORM; } })
	{
		conceal();
		invoke(do_ptell, staff, "Player Hidden reply");
		event(peer, "Someone -> Player", "Hidden reply");
		invoke(do_petition, staff, "Hidden petition");
		event(peer, "Someone", "Hidden petition");
		staff.pc.wiz_invis = 0;
		staff.ch.specials.affected_by = 0;
		staff.ch.specials.affected_by2 = 0;
		staff.ch.specials.affected_by3 = 0;
	}
	staff.ch.specials.act |= PLR_MORTAL;
	invoke(do_ptell, staff, "Player Fog reply");
	event(peer, "Someone -> Player", "Fog reply");
	staff.ch.specials.act &= ~PLR_MORTAL;
	target.ch.player.level = 60;
	target.pc.wiz_invis = 1;
	invoke(do_ptell, staff, "Player Reply to hidden staff");
	event(peer, "Staff -> Someone", "Reply to hidden staff");
}

static void input_dollars(int peer)
{
	player petitioner("Player"), staff("Staff", 64);
	recipients({ &petitioner, &staff });
	const std::string text = "Price $1; two $$; literal $n and $$n; trailing $";
	char normalized[MAX_STRING_LENGTH];
	assert(!validate_utf8_and_dollars(normalized, text.c_str()));
	invoke(do_petition, petitioner, normalized);
	event(peer, "Player", text);
	upgrade_cp437_and_dollars(normalized, ("Player " + text).c_str());
	invoke(do_ptell, staff, normalized);
	event(peer, "Staff -> Player", text);
}

static void text_and_bounds(int peer)
{
	player sender("&+rZoë&n");
	const std::vector<std::pair<std::string, std::string>> cases = {
		{ "&+rRed&n &-bBackground&N &=rGCombo", "Red Background Combo" },
		{ "& &+ &- &= &=r &+? @user $n \\ \"", "& &+ &- &= &=r &+? @user $n \\ \"" },
		{ "Before\x1b[31mRed\x1b[m After", "BeforeRed After" },
		{ "A\x1b]0;hidden title\aB\x1bPprivate payload\x1b\\C", "ABC" },
		{ "A\x1b_hidden payload\x1b\\B\x1b(Bword", "ABword" },
		{ "A\xc2\x9b"
		  "31mB\xc2\x9d"
		  "secret\xc2\x9c"
		  "C",
		  "ABC" },
		{ "\x01"
		  "A\r\nB\tC\x7f",
		  "A\nB\tC" },
		{ "A\xff\xc0\xaf"
		  "B",
		  "A��B" },
		{ "你好 🔥 café", "你好 🔥 café" },
		{ "A\x1b[31", "A" },
		{ "A\x1b]unterminated", "A" }
	};
	for (const auto &[source, expected] : cases)
	{
		discord_petition_export(&sender.ch, source.c_str());
		event(peer, "Zoë", expected);
	}
	std::string maximal(MAX_STRING_LENGTH - 1, '\\');
	discord_petition_export(&sender.ch, maximal.c_str());
	event(peer, "Zoë", maximal);
	std::string invalid(MAX_STRING_LENGTH - 1, '\xff');
	discord_petition_export(&sender.ch, invalid.c_str());
	std::string repaired;
	for (std::size_t i = 0; i < invalid.size(); ++i)
		repaired += "�";
	event(peer, "Zoë", repaired);
	const auto dropped = discord_bridge_get_status().dropped_events;
	discord_petition_export(&sender.ch, std::string(MAX_STRING_LENGTH, 'x').c_str());
	assert(received(peer).empty());
	assert(discord_bridge_get_status().dropped_events == dropped + 1);
}

static void unavailable(int peer)
{
	player sender("Player"), staff("Staff", 64);
	recipients({ &sender, &staff });
	auto native_both = [&]
	{
		invoke(do_petition, sender, "Native survives unavailable endpoint");
		assert(deliveries(&sender.ch, "text") == 1 && deliveries(&sender.ch, "gmcp") == 1);
		assert(audit.size() == 1);
		invoke(do_ptell, staff, "Player Reply survives unavailable endpoint");
		assert(deliveries(&sender.ch, "text") == 1 && deliveries(&sender.ch, "gmcp") == 1);
		assert(deliveries(&staff.ch, "text") == 1 && deliveries(&staff.ch, "gmcp") == 1);
		assert(audit.size() == 1);
	};
	for (unsigned i = 0; i < 256; ++i)
		assert(discord_bridge_publish("A", "fill"));
	const auto before_drop = discord_bridge_get_status().dropped_events;
	native_both();
	assert(discord_bridge_get_status().dropped_events == before_drop + 2);
	close(peer);
	for (unsigned i = 0; i < 1000 && discord_bridge_get_status().connected; ++i)
	{
		discord_bridge_poll();
		usleep(1000);
	}
	assert(!discord_bridge_get_status().connected);
	native_both();
	discord_bridge_shutdown();
	const auto dropped = discord_bridge_get_status().dropped_events;
	native_both();
	assert(discord_bridge_get_status().dropped_events == dropped);
}

// A test-only stdio control plane invokes the same production commands while
// an external Node process connects to the actual native bridge listener.
static int node_peer()
{
	int probe = endpoint();
	close(probe);
	discord_bridge_poll();
	std::cout << "{\"port\":" << discord_bridge_get_status().port << "}" << std::endl;
	player petitioner("Player"), staff("Staff", 64), monitor("Monitor", 64);
	recipients({ &petitioner, &staff, &monitor });
	unsigned dispatches = 0;
	for (;;)
	{
		discord_bridge_poll();
		discord_bridge_flush();
		pollfd input{ STDIN_FILENO, POLLIN, 0 };
		if (poll(&input, 1, 5) <= 0)
			continue;
		std::string line;
		if (!std::getline(std::cin, line))
			break;
		cJSON *request = cJSON_Parse(line.c_str());
		assert(request);
		const cJSON *action = cJSON_GetObjectItem(request, "action");
		const cJSON *text = cJSON_GetObjectItem(request, "text");
		assert(cJSON_IsString(action));
		const std::string command = action->valuestring;
		const std::string message = cJSON_IsString(text) ? text->valuestring : "";
		if (command == "petition" || command == "rejected_petition")
		{
			++dispatches;
			if (command == "rejected_petition")
				petitioner.ch.specials.act |= PLR_SILENCE;
			invoke(do_petition, petitioner, message);
			petitioner.ch.specials.act &= ~PLR_SILENCE;
		}
		else if (command == "reply" || command == "hidden_reply")
		{
			++dispatches;
			staff.pc.wiz_invis = command == "hidden_reply" ? 64 : 0;
			invoke(do_ptell, staff, "Player " + message);
			staff.pc.wiz_invis = 0;
		}
		else if (command == "notice")
		{
			delivered.clear();
			std::string notice = message;
			send_to_gods(notice.data());
		}
		else if (command == "restart" || command == "disable" || command == "enable")
		{
			setenv("DURIS_DISCORD_ENABLED", command == "disable" ? "FALSE" : "TRUE", 1);
			assert(discord_bridge_init());
		}
		else
			assert(command == "status" || command == "quit");
		discord_bridge_poll();
		discord_bridge_flush();
		const auto status = discord_bridge_get_status();
		cJSON *response = cJSON_CreateObject();
		cJSON_AddNumberToObject(response, "id",
					cJSON_GetObjectItem(request, "id")->valueint);
		cJSON_AddBoolToObject(response, "connected", status.connected);
		cJSON_AddBoolToObject(response, "authenticated", status.authenticated);
		cJSON_AddBoolToObject(response, "listening", status.listening);
		cJSON_AddNumberToObject(response, "sent", status.sent_events);
		cJSON_AddNumberToObject(response, "dropped", status.dropped_events);
		cJSON_AddNumberToObject(response, "rejected", status.rejected_records);
		cJSON_AddNumberToObject(response, "dispatches", dispatches);
		cJSON_AddNumberToObject(response, "native_deliveries", delivered.size());
		cJSON_AddNumberToObject(response, "audit_entries", audit.size());
		char *json = cJSON_PrintUnformatted(response);
		assert(json);
		std::cout << json << std::endl;
		cJSON_free(json);
		cJSON_Delete(response);
		cJSON_Delete(request);
		if (command == "quit")
			break;
	}
	discord_bridge_shutdown();
	return 0;
}

int main(int argc, char **argv)
{
	if (argc == 2 && strcmp(argv[1], "--node-peer") == 0)
		return node_peer();
	int peer = endpoint();
	accepted(peer);
	rejected(peer);
	concealment(peer);
	input_dollars(peer);
	text_and_bounds(peer);
	unavailable(peer);
	puts("Petition/ptell real-command export harness passed");
}
