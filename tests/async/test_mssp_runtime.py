#!/usr/bin/env python3
"""Runtime regressions for MUD Server Status Protocol (MSSP) negotiation."""

from _paths import ROOT, SRC, extract_function
import subprocess
import tempfile
from pathlib import Path


COMM = (SRC / "comm.c").read_text()
assert "mssp_advertise" not in COMM

HARNESS = r'''
#include "net/mssp.h"
#include "net/mccp.h"
#include "net/gmcp.h"
#include "net/telnet.h"
#include "net/ttype.h"
#include "core/utils.h"

#include <cstdio>
#include <cstdlib>
#include <string>

P_desc descriptor_list = nullptr;
long boot_time = 1761631200;

static std::string sent;
static int writes;

// Unrelated options are stubbed; exercise the unchanged production parser.
int compress_start(P_desc, int) { return 0; }
void gmcp_handle_negotiation(P_desc, int) {}
void gmcp_handle_input(P_desc, const char *, size_t) {}
void ttype_handle_negotiation(P_desc, int) {}
void ttype_handle_subnegotiation(P_desc, const unsigned char *, int) {}

@TELNET_PARSER@

int write_to_descriptor_binary(P_desc, const unsigned char *data, size_t len)
{
	sent.assign(reinterpret_cast<const char *>(data), len);
	writes++;
	return 0;
}

static void require(bool condition, int code)
{
	if (!condition)
		std::exit(code);
}

int main()
{
	int tests = 0;
	char request[] = { (char)IAC, (char)DO, TELOPT_MSSP };
	char decline[] = { (char)IAC, (char)DONT, TELOPT_MSSP };

	// 1. MSSP is disabled; WebSocket and null descriptors emit nothing.
	{
		descriptor_data websocket = {};
		websocket.websocket = 1;
		writes = 0;
		mssp_send(nullptr);
		require(parse_telnet_options(&websocket, request, sizeof request) == 3, 11);
		require(writes == 0, 1);
	}
	tests++;

	// 2. Fragmented requests wait for completion, then receive only WONT,
	//    regardless of mortal, immortal, switched, or morphed presence.
	descriptor_data crawler = {};
	{
		char_data mortal = {}, immortal = {}, low_mob = {}, high_mob = {};
		mortal.player.level = 10;
		immortal.player.level = MINLVLIMMORTAL;
		low_mob.player.level = 5;
		high_mob.player.level = MINLVLIMMORTAL + 1;
		descriptor_data playing = {}, imm = {}, logging_in = {}, switched_imm = {},
				morphed_mortal = {};
		playing.character = &mortal;
		imm.character = &immortal;
		logging_in.character = &mortal;
		STATE(&logging_in) = CON_PLAYING + 1;
		switched_imm.character = &low_mob;
		switched_imm.original = &immortal;
		morphed_mortal.character = &high_mob;
		morphed_mortal.original = &mortal;
		playing.next = &imm;
		imm.next = &logging_in;
		logging_in.next = &switched_imm;
		switched_imm.next = &morphed_mortal;
		morphed_mortal.next = &crawler;
		descriptor_list = &playing;

		writes = 0;
		require(parse_telnet_options(&crawler, request, 1) == 0, 12);
		require(parse_telnet_options(&crawler, request, 2) == 0, 13);
		require(writes == 0 && !crawler.mssp_sent, 14);
		require(parse_telnet_options(&crawler, request, sizeof request) == 3, 15);
		require(writes == 1, 16);
		const unsigned char expected[] = { IAC, WONT, TELOPT_MSSP };
		require(sent == std::string(reinterpret_cast<const char *>(expected), 3), 2);
		descriptor_list = nullptr;
	}
	tests++;

	// 3. Neither repeated DO nor alternating DONT/DO can amplify one connection.
	{
		writes = 0;
		for (int i = 0; i < 10000; i++)
		{
			require(parse_telnet_options(&crawler, request, sizeof request) == 3, 17);
			require(parse_telnet_options(&crawler, decline, sizeof decline) == 3, 18);
			require(parse_telnet_options(&crawler, request, sizeof request) == 3, 19);
		}
		require(writes == 0, 10);
	}
	tests++;

	// 4. Declining initially does not consume a fresh connection's one reply.
	{
		descriptor_data fresh = {};
		writes = 0;
		require(parse_telnet_options(&fresh, decline, sizeof decline) == 3, 20);
		require(writes == 0 && !fresh.mssp_sent, 21);
		require(parse_telnet_options(&fresh, request, sizeof request) == 3, 22);
		require(writes == 1 && fresh.mssp_sent, 23);
		const unsigned char expected[] = { IAC, WONT, TELOPT_MSSP };
		require(sent == std::string(reinterpret_cast<const char *>(expected), 3), 24);
	}
	tests++;

	std::printf("%d MSSP runtime cases passed\n", tests);
	return 0;
}
'''

BUILD = ROOT / "bin/tests"
BUILD.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="duris-mssp-runtime-", dir=BUILD) as directory:
    temp = Path(directory)
    harness = temp / "harness.cpp"
    binary = temp / "harness"
    harness.write_text(HARNESS.replace(
        "@TELNET_PARSER@", extract_function("mccp.c", "int parse_telnet_options(")
    ))
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{SRC}",
            str(harness),
            str(SRC / "mssp.c"),
            "-lbsd",
            "-o",
            str(binary),
        ],
        check=True,
    )
    subprocess.run([str(binary)], check=True)

print("MSSP runtime regressions passed")
