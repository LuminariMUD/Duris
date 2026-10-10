#!/usr/bin/env python3
"""The critical command codec at its edges, run on src/persistence/critical_command.c.

Operation ids: generation retries an interrupted getrandom() and refuses a failed or empty
one (getrandom is wrapped); derivation refuses no output, a zero parent or domain 0; hex
round trips in either case and refuses a short buffer, a wrong length or a non-hex digit.
Commands: every limit (keys, expected revisions, payload) is valid at its maximum; an entity
type outside player..pet, an unknown command type, a zero id, a revision for a key the
command does not hold, an unsorted or duplicate key and a later schema are refused. The
decoder refuses a wrong magic, a header with no key, extra bytes and every truncation, and
round trips a command whose last field ends the buffer.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT

HARNESS = r'''
#include "persistence/critical_command.h"

#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <sys/random.h>
#include <vector>

// Each getrandom() call takes the next scripted result: >0 fills that many bytes.
static std::vector<long> script;
extern "C" ssize_t __real_getrandom(void *, size_t, unsigned int);
extern "C" ssize_t __wrap_getrandom(void *buffer, size_t length, unsigned int flags)
{
	if (script.empty())
		return __real_getrandom(buffer, length, flags);
	const long next = script.front();
	script.erase(script.begin());
	if (next < 0)
	{
		errno = static_cast<int>(-next);
		return -1;
	}
	memset(buffer, 0x5a, static_cast<size_t>(next) < length ? next : length);
	return static_cast<size_t>(next) < length ? next : static_cast<ssize_t>(length);
}

static critical_command command_with(size_t keys, size_t revisions, size_t payload)
{
	critical_command command{};
	command.schema_version = CRITICAL_COMMAND_SCHEMA_VERSION;
	command.operation_id.bytes.fill(1);
	command.type = critical_command_type::test;
	command.payload_version = 1;
	command.source_site = critical_source_site::command;
	command.deadline_class = critical_deadline_class::interactive;
	command.accepted_at_usec = 1;
	for (size_t index = 0; index < keys; ++index)
		command.keys.push_back({ critical_entity_type::player, index + 1 });
	for (size_t index = 0; index < revisions; ++index)
		command.expected_revisions.push_back({ command.keys[index], 9 });
	command.payload.assign(payload, 7);
	return command;
}
'''

HARNESS += r'''
static critical_command_codec_result decoded(const std::vector<uint8_t> &bytes)
{
	critical_command out{};
	// A vector of exactly this size, so reading past it is a sanitizer report.
	const std::vector<uint8_t> exact(bytes);
	return critical_command_decode(exact.data(), exact.size(), &out);
}

int main()
{
	// Generation.
	critical_operation_id id{};
	assert(!critical_operation_id_generate(nullptr));
	script = { -EINTR, 16 };
	assert(critical_operation_id_generate(&id) && script.empty());
	script = { 8, 8 };
	assert(critical_operation_id_generate(&id) && script.empty());
	script = { -EIO };
	assert(!critical_operation_id_generate(&id));
	script = { 0 };
	assert(!critical_operation_id_generate(&id));
	// A call that returns nothing fails even while errno still says the last one was
	// interrupted.
	script = { 0 };
	errno = EINTR;
	assert(!critical_operation_id_generate(&id));
	script.clear();

	// Derivation and zero.
	critical_operation_id zero{}, parent{}, child{};
	parent.bytes.fill(3);
	assert(critical_operation_id_is_zero(zero) && !critical_operation_id_is_zero(parent));
	assert(!critical_operation_id_derive(parent, 1, 1, nullptr));
	assert(!critical_operation_id_derive(zero, 1, 1, &child));
	assert(!critical_operation_id_derive(parent, 0, 1, &child));
	assert(critical_operation_id_derive(parent, 1, 1, &child));

	// Hex: the exact buffer (a sanitizer report if written past), both cases, no stray digit.
	char hex[CRITICAL_COMMAND_ID_HEX_SIZE];
	assert(!critical_operation_id_to_hex(parent, nullptr, sizeof hex));
	assert(!critical_operation_id_to_hex(parent, hex, sizeof hex - 1));
	critical_operation_id round{};
	parent.bytes[0] = 0xaf;
	parent.bytes[1] = 0x09;
	assert(critical_operation_id_to_hex(parent, hex, sizeof hex));
	assert(critical_operation_id_from_hex(hex, &round) &&
	       critical_operation_id_equal(round, parent));
	const char *upper = "AF09030303030303030303030303030F";
	assert(critical_operation_id_from_hex(upper, &round) && round.bytes[0] == 0xaf &&
	       round.bytes[15] == 0x0f);
	assert(!critical_operation_id_from_hex(nullptr, &round));
	assert(!critical_operation_id_from_hex("af", &round));
	for (const char *bad : { "@F090303030303030303030303030303", "GF090303030303030303030303030303",
				 "`f090303030303030303030303030303", "gf090303030303030303030303030303",
				 "af0903030303030303030303030303:3" })
		assert(!critical_operation_id_from_hex(bad, &round));

	// Commands: every limit valid at its maximum.
	auto full = command_with(CRITICAL_COMMAND_MAX_KEYS, CRITICAL_COMMAND_MAX_KEYS,
				 CRITICAL_COMMAND_MAX_PAYLOAD_BYTES);
	full.deadline_class = critical_deadline_class::recovery;
	full.keys.back().type = critical_entity_type::pet;
	full.expected_revisions.back().key.type = critical_entity_type::pet;
	assert(critical_command_valid(full));
	std::vector<uint8_t> bytes;
	assert(critical_command_encode(full, &bytes) == critical_command_codec_result::ok);
	critical_command back{};
	assert(critical_command_decode(bytes.data(), bytes.size(), &back) ==
	       critical_command_codec_result::ok);
	assert(critical_command_equal(full, back));
	assert(critical_command_encode(full, nullptr) == critical_command_codec_result::invalid);

	// What a command may not be.
	auto refused = [](auto change)
	{
		auto command = command_with(2, 1, 4);
		change(command);
		std::vector<uint8_t> out;
		return !critical_command_valid(command) &&
		       critical_command_encode(command, &out) == critical_command_codec_result::invalid;
	};
	assert(refused([](critical_command &c) { c.schema_version = 2; }));
	assert(refused([](critical_command &c) { c.type = static_cast<critical_command_type>(4); }));
	assert(refused([](critical_command &c) { c.keys[0].type = static_cast<critical_entity_type>(0); }));
	assert(refused([](critical_command &c)
		       { c.keys[1].type = static_cast<critical_entity_type>(
				 static_cast<int>(critical_entity_type::pet) + 1); }));
	assert(refused([](critical_command &c) { c.keys[0].id = 0; }));
	assert(refused([](critical_command &c) { std::swap(c.keys[0], c.keys[1]); }));
	assert(refused([](critical_command &c) { c.expected_revisions[0].key.id = 99; }));
	assert(refused([](critical_command &c)
		       { c.deadline_class = static_cast<critical_deadline_class>(5); }));
	assert(refused([](critical_command &c)
		       { c.keys.resize(CRITICAL_COMMAND_MAX_KEYS + 1, c.keys.back()); }));
	assert(!critical_command_normalize(nullptr));
	auto duplicate = command_with(2, 0, 0);
	duplicate.keys[1] = duplicate.keys[0];
	assert(!critical_command_normalize(&duplicate));

	// The decoder: a small command whose last key id ends the buffer round trips.
	auto small = command_with(1, 0, 0);
	assert(critical_command_encode(small, &bytes) == critical_command_codec_result::ok);
	assert(decoded(bytes) == critical_command_codec_result::ok);
	for (size_t size = 0; size < bytes.size(); ++size)
		assert(decoded(std::vector<uint8_t>(bytes.begin(), bytes.begin() + size)) !=
		       critical_command_codec_result::ok);
	auto extra = bytes;
	extra.push_back(0);
	assert(decoded(extra) == critical_command_codec_result::invalid);
	auto magic = bytes;
	magic[0] = 'X';
	assert(decoded(magic) == critical_command_codec_result::invalid);
	// The header alone, 52 bytes, says it has no key.
	auto header = std::vector<uint8_t>(bytes.begin(), bytes.begin() + 52);
	header[40] = header[41] = header[42] = header[43] = 0;
	assert(decoded(header) == critical_command_codec_result::overflow);
	std::puts("critical command codec: limits, refusals and every truncation passed");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="critical-codec-", dir=ROOT / "bin/tests") as build:
    source = Path(build) / "harness.cpp"
    binary = Path(build) / "harness"
    source.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-Isrc", str(source),
                    "src/persistence/critical_command.c", "-Wl,--wrap=getrandom", "-lcrypto",
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
