#!/usr/bin/env python3
"""Runtime regressions for MUD Server Status Protocol (MSSP) negotiation."""

from _paths import SRC
import subprocess
import tempfile
from pathlib import Path


COMM = (SRC / "comm.c").read_text()
MCCP = (SRC / "mccp.c").read_text()
assert "gmcp_negotiate(newd);\n\tmssp_advertise(newd);" in COMM
assert "case TELOPT_MSSP:\n\t\t\tmssp_send(player);\n\t\t\treturn 3;" in MCCP

HARNESS = r'''
#include "net/mssp.h"
#include "net/telnet.h"
#include "core/utils.h"

#include <cstdio>
#include <cstdlib>
#include <string>

P_desc descriptor_list = nullptr;
long boot_time = 1761631200;

static std::string sent;
static int writes;

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

static std::string mssp_pair(const char *var, const char *val)
{
	return std::string(1, MSSP_VAR) + var + std::string(1, MSSP_VAL) + val;
}

int main()
{
	int tests = 0;

	// 1. Telnet clients are offered MSSP; WebSockets and null descriptors are not.
	{
		descriptor_data websocket = {};
		websocket.websocket = 1;
		writes = 0;
		mssp_advertise(nullptr);
		mssp_advertise(&websocket);
		mssp_send(&websocket);
		require(writes == 0, 1);

		descriptor_data d = {};
		mssp_advertise(&d);
		const unsigned char expected[] = { IAC, WILL, TELOPT_MSSP };
		require(sent == std::string(reinterpret_cast<const char *>(expected), 3), 2);
	}
	tests++;

	// 2. The reply is one IAC SB MSSP ... IAC SE block that counts only playing mortals.
	{
		char_data mortal = {}, immortal = {};
		mortal.player.level = 10;
		immortal.player.level = MINLVLIMMORTAL;
		descriptor_data playing = {}, imm = {}, logging_in = {}, crawler = {};
		playing.character = &mortal;
		imm.character = &immortal;
		logging_in.character = &mortal;
		STATE(&logging_in) = CON_PLAYING + 1;
		playing.next = &imm;
		imm.next = &logging_in;
		logging_in.next = &crawler;
		descriptor_list = &playing;

		mssp_send(&crawler);
		require(sent.size() > 5, 3);
		require((unsigned char)sent[0] == IAC && (unsigned char)sent[1] == SB &&
				(unsigned char)sent[2] == TELOPT_MSSP,
			4);
		require((unsigned char)sent[sent.size() - 2] == IAC &&
				(unsigned char)sent[sent.size() - 1] == SE,
			5);
		require(sent.find(mssp_pair("PLAYERS", "1")) != std::string::npos, 6);
		require(sent.find(mssp_pair("UPTIME", "1761631200")) != std::string::npos, 7);
		require(sent.find(mssp_pair("NAME", "DurisMUD")) != std::string::npos, 8);

		// No stray IAC inside the payload, which would end the block early.
		require(sent.find(static_cast<char>(IAC), 1) == sent.size() - 2, 9);
	}
	tests++;

	std::printf("%d MSSP runtime cases passed\n", tests);
	return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="duris-mssp-runtime-") as directory:
    temp = Path(directory)
    harness = temp / "harness.cpp"
    binary = temp / "harness"
    harness.write_text(HARNESS)
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
