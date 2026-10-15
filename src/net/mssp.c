/*
 * mssp.c - MUD Server Status Protocol (https://tintin.mudhalla.net/protocols/mssp/)
 *
 * Listing sites such as MudStats and Grapevine connect, see IAC WILL MSSP, answer
 * IAC DO MSSP, and read the game's name, live player count and boot time from the
 * reply.  Only mortals who are in the game are counted.
 */

#include "net/mssp.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "net/telnet.h"
#include <string>

extern P_desc descriptor_list;
extern long boot_time;

static const char *const mssp_fixed[][2] = {
	{ "NAME", "DurisMUD" },
	{ "CODEBASE", "DikuMUD" },
	{ "FAMILY", "DikuMUD" },
	{ "GENRE", "Fantasy" },
	{ "GAMEPLAY", "Player versus Player" },
	{ "STATUS", "Live" },
	{ "CREATED", "1995" },
	{ "LANGUAGE", "English" },
	{ "WEBSITE", "https://duris.sbs" },
	{ "DISCORD", "https://discord.gg/adXajEAmk" },
	{ "ANSI", "1" },
	{ "UTF-8", "1" },
	{ "GMCP", "1" },
	{ "MCCP", "1" },
};

static void add_pair(std::string &out, const char *var, const std::string &val)
{
	out += (char)MSSP_VAR;
	out += var;
	out += (char)MSSP_VAL;
	out += val;
}

void mssp_advertise(P_desc d)
{
	static const unsigned char will_mssp[] = { IAC, WILL, TELOPT_MSSP };

	if (d && !d->websocket)
		write_to_descriptor_binary(d, will_mssp, sizeof will_mssp);
}

void mssp_send(P_desc d)
{
	int players = 0;
	std::string out;

	/* One reply per connection, so repeated requests can't make us redo the work. */
	if (!d || d->websocket || d->mssp_sent)
		return;
	d->mssp_sent = 1;

	for (P_desc i = descriptor_list; i; i = i->next)
	{
		/* A switched or morphed player is counted by who they really are. */
		P_char player = i->original ? i->original : i->character;
		if (STATE(i) == CON_PLAYING && player && GET_LEVEL(player) < MINLVLIMMORTAL)
			players++;
	}

	out += (char)IAC;
	out += (char)SB;
	out += (char)TELOPT_MSSP;
	add_pair(out, "PLAYERS", std::to_string(players));
	add_pair(out, "UPTIME", std::to_string(boot_time));
	for (const auto &pair : mssp_fixed)
		add_pair(out, pair[0], pair[1]);
	out += (char)IAC;
	out += (char)SE;

	write_to_descriptor_binary(d, (const unsigned char *)out.data(), out.size());
}
