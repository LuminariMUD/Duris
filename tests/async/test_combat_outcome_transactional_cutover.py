#!/usr/bin/env python3
"""Bounded codec, mutation route, schema, and publication contracts for PvP outcomes."""

from _paths import SRC, extract_function
from pathlib import Path
import resource
import signal
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include "combat/combat_outcome_command.h"
#include <cassert>
#include <cstring>

combat_outcome_participant participant(uint32_t pid, combat_participant_role role)
{
    combat_outcome_participant value = {};
    value.pid = pid;
    value.role = role;
    value.webinfo_at_capture = combat_webinfo::on;
    value.level = 50;
    value.racewar = 1;
    value.expected_frag_revision = pid;
    value.expected_epic_revision = pid + 1;
    value.expected_wallet_revision = pid + 2;
    value.expected_bank_revision = 9;
    memcpy(value.account_name.data(), "combat-account", 14);
    memcpy(value.description.data(), "bounded player", 14);
    return value;
}

int main()
{
    combat_outcome_payload payload = {};
    payload.victim_pid = 22;
    payload.room_vnum = 101;
    payload.killer_allies = 5;
    memcpy(payload.room_name.data(), "A bounded room", 14);
    payload.participant_count = 2;
    payload.participants[0] = participant(11, combat_participant_role::killer);
    payload.participants[0].frag_delta = 100;
    payload.participants[0].epic_delta = 500;
    payload.participants[0].wallet_delta_copper = 10000;
    payload.participants[1] = participant(22, combat_participant_role::victim);
    payload.participants[1].frag_delta = -100;
    payload.participants[0].equipment = "<wielded> a warrior's &+Rsword&n\n";
    payload.participants[0].log = "You strike the victim.\r\nThe victim falls.\r\n";

    critical_operation_id id = {};
    assert(critical_operation_id_generate(&id));
    critical_command command = {};
    assert(combat_outcome_command_build(&command, id, payload));
    assert(command.type == critical_command_type::combat_outcome);
    assert(command.keys.size() == 3);
    combat_outcome_payload decoded = {};
    assert(combat_outcome_command_decode_payload(command, &decoded));
    assert(decoded.participant_count == 2);
    assert(decoded.killer_allies == 5);
    assert(decoded.participants[0].equipment == payload.participants[0].equipment);
    assert(decoded.participants[0].log == payload.participants[0].log);
    assert(decoded.participants[0].webinfo_at_capture == combat_webinfo::on);
    auto invalid = payload;
    invalid.participants[0].webinfo_at_capture = static_cast<combat_webinfo>(2);
    critical_command refused{};
    assert(!combat_outcome_command_build(&refused, id, invalid));
    invalid.participants[0].webinfo_at_capture = combat_webinfo::off;
    assert(!combat_outcome_command_build(&refused, id, invalid));
    invalid.participants[0].log.clear(); invalid.participants[0].equipment.clear();
    assert(combat_outcome_command_build(&refused, id, invalid));
    assert(combat_outcome_command_decode_payload(refused, &decoded));
    assert(decoded.participants[0].webinfo_at_capture == combat_webinfo::off);
    for (uint8_t byte : {2, 254, 0}) {
        auto malformed = command;
        malformed.payload[malformed.payload.size() - payload.participant_count] = byte;
        assert(!combat_outcome_command_decode_payload(malformed, &decoded));
    }
    critical_command legacy = command;
    legacy.payload_version = 3;
    legacy.payload.resize(legacy.payload.size() - payload.participant_count);
    assert(combat_outcome_command_decode_payload(legacy, &decoded));
    assert(decoded.participants[0].webinfo_at_capture == combat_webinfo::unknown);
    assert(decoded.participants[0].log == payload.participants[0].log);
    legacy.payload_version = 2;
    size_t snapshot_bytes = 0;
    for (size_t i = 0; i < payload.participant_count; ++i)
        snapshot_bytes += 8 + payload.participants[i].equipment.size() + payload.participants[i].log.size();
    legacy.payload.resize(legacy.payload.size() - snapshot_bytes);
    assert(combat_outcome_command_decode_payload(legacy, &decoded));
    assert(decoded.killer_allies == 5);
    assert(decoded.participants[0].webinfo_at_capture == combat_webinfo::unknown);
    assert(decoded.participants[0].log.empty() && decoded.participants[0].equipment.empty());
    legacy.payload_version = 1;
    legacy.payload.resize(legacy.payload.size() - sizeof(uint32_t));
    assert(combat_outcome_command_decode_payload(legacy, &decoded));
    assert(decoded.killer_allies == 0);
    assert(decoded.participants[0].webinfo_at_capture == combat_webinfo::unknown);
    assert(decoded.participants[0].log.empty() && decoded.participants[0].equipment.empty());
    auto bad_revision = legacy;
    ++bad_revision.expected_revisions[0].revision;
    assert(!combat_outcome_command_decode_payload(bad_revision, &decoded));
    legacy.payload_version = COMBAT_OUTCOME_PAYLOAD_VERSION;
    assert(!combat_outcome_command_decode_payload(legacy, &decoded));
    assert(combat_outcome_command_decode_payload(command, &decoded));
    assert(decoded.participants[0].epic_delta == 500);

    // Replay the outer serialized command, not just the in-memory payload.
    std::vector<uint8_t> serialized;
    command.accepted_at_usec = 1;
    assert(critical_command_encode(command, &serialized) == critical_command_codec_result::ok);
    critical_command restored = {};
    assert(critical_command_decode(serialized.data(), serialized.size(), &restored) == critical_command_codec_result::ok);
    assert(combat_outcome_command_decode_payload(restored, &decoded));
    assert(decoded.participants[0].log == payload.participants[0].log);
    auto broken = command;
    broken.payload.pop_back();
    assert(!combat_outcome_command_decode_payload(broken, &decoded));
    broken = command;
    broken.payload.push_back(0);
    assert(!combat_outcome_command_decode_payload(broken, &decoded));

    // All 15 participants can retain the full legacy limits, without truncation
    // or rejecting their rewards just because their public logs are long.
    auto full = payload;
    full.participant_count = COMBAT_OUTCOME_MAX_PARTICIPANTS;
    for (size_t i = 0; i < full.participant_count; ++i) {
        full.participants[i] = participant(static_cast<uint32_t>(i + 22), combat_participant_role::killer_group);
        full.participants[i].equipment.assign(COMBAT_OUTCOME_EQUIPMENT_MAX_BYTES, 'e');
        full.participants[i].log.assign(COMBAT_OUTCOME_LOG_MAX_BYTES, 'l');
    }
    critical_command maximum = {};
    assert(combat_outcome_command_build(&maximum, id, full));
    maximum.accepted_at_usec = 1;
    assert(critical_command_encode(maximum, &serialized) == critical_command_codec_result::ok);
    assert(critical_command_decode(serialized.data(), serialized.size(), &restored) == critical_command_codec_result::ok);
    assert(combat_outcome_command_decode_payload(restored, &decoded));
    assert(decoded.participants[14].equipment == full.participants[14].equipment);
    assert(decoded.participants[14].log == full.participants[14].log);
    full.participants[0].log.push_back('x');
    assert(!combat_outcome_command_build(&maximum, id, full));
    full.participants[0].log = std::string("a\0b", 3);
    assert(!combat_outcome_command_build(&maximum, id, full));

    critical_command tampered = command;
    tampered.keys.pop_back();
    assert(!combat_outcome_command_decode_payload(tampered, &decoded));
    tampered = command;
    ++tampered.expected_revisions[0].revision;
    assert(!combat_outcome_command_decode_payload(tampered, &decoded));
    payload.participants[1].pid = 11;
    assert(!combat_outcome_command_build(&command, id, payload));

    combat_outcome_result result = {};
    result.event_id = 77;
    result.participant_count = COMBAT_OUTCOME_MAX_PARTICIPANTS;
    for (size_t i = 0; i < result.participant_count; ++i)
    {
        result.participants[i].pid = static_cast<uint32_t>(i + 1);
        result.participants[i].frags = 10;
        result.participants[i].epics = 20;
        result.participants[i].wallet_value = 30;
        result.participants[i].frag_revision = 1;
        result.participants[i].epic_revision = 2;
        result.participants[i].wallet_revision = 3;
        result.participants[i].bank_revision = 4;
    }
    std::array<uint8_t, COMBAT_OUTCOME_RESULT_BYTES> bytes = {};
    assert(combat_outcome_command_encode_result(result, &bytes));
    combat_outcome_result decoded_result = {};
    assert(combat_outcome_command_decode_result(bytes.data(), bytes.size(), &decoded_result));
    assert(decoded_result.participant_count == COMBAT_OUTCOME_MAX_PARTICIPANTS);
}
'''


class CombatOutcomeCutoverTests(unittest.TestCase):
    def test_capture_owns_public_snapshots_before_character_changes(self):
        capture = extract_function("fight.c", "static combat_outcome_participant *combat_outcome_add_participant(")
        harness = r'''
#include "combat/combat_outcome_command.h"
#include "player/player_log.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <bsd/string.h>
#define MAX_STRING_LENGTH 65536
#define MAX_LOG_LEN 100000
struct Association { std::string get_name() const { return "-Guild-"; } };
struct Pc { uint64_t frag_revision{}, epic_revision{}, wallet_revision{}, bank_revision{}; PlayerLog log; };
struct Character {
    int pid{11}, level{56}, race{}, racewar{1}; bool npc{}, webinfo{true};
    std::string name{"Fixture"}, equipment{"<wielded> a sword\n"};
    struct { Pc *pc; } only;
    Association *association{};
};
using P_char = Character *;
#define IS_NPC(ch) ((ch)->npc)
#define PLR2_FLAGGED(ch, flag) ((ch)->webinfo)
#define GET_PID(ch) ((ch)->pid)
#define GET_LEVEL(ch) ((ch)->level)
#define GET_RACEWAR(ch) ((ch)->racewar)
#define GET_NAME(ch) ((ch)->name.c_str())
#define GET_ASSOC(ch) ((ch)->association)
#define GET_RACE(ch) ((ch)->race)
#define GET_PLAYER_LOG(ch) (&(ch)->only.pc->log)
static const struct { const char *ansi; } race_names_table[] = {{"&+WHuman&n"}};
const char *get_account_name_safe(P_char) { return "fixture-account"; }
const char *get_class_name(P_char, P_char) { return "&+RWarrior&n"; }
static int equipment_reads = 0;
void get_equipment_list(P_char ch, char *buffer, int list_only) {
    ++equipment_reads;
    assert(list_only == 1);
    strlcpy(buffer, ch->equipment.c_str(), MAX_STRING_LENGTH);
}
'''
        harness += capture
        harness += r'''
int main(int argc, char **argv) {
    PlayerLog bounded;
    if (argc > 1) {
        bounded.write(std::atoi(argv[1]), "invalid log index");
        return 0;
    }
    assert(std::string(bounded.read_export(100)).empty());
    bounded.write(LOG_PUBLIC, "unclassified");
    bounded.write(LOG_PUBLIC, "ab", true);
    bounded.write(LOG_PRIVATE, "secret", true);
    bounded.write(LOG_PUBLIC, "cd", true);
    assert(std::string(bounded.read_export(5)) == "abcd");
    assert(std::string(bounded.read_export(4)) == "cd");
    assert(std::string(bounded.read_export(2)).empty());
    assert(std::string(bounded.read_export(0)).empty());
    bounded.reset_export_window();
    assert(std::string(bounded.read_export(100)).empty());
    assert(std::string(bounded.read(LOG_PRIVATE, 100)) == "secret");
    for (int i = 0; i < PUBLIC_LOG_SIZE + 5; ++i) bounded.write(LOG_PUBLIC, "x", true);
    assert(std::string(bounded.read_export(MAX_LOG_LEN)) == std::string(PUBLIC_LOG_SIZE, 'x'));
    bounded.write(LOG_PUBLIC, "off", false);
    assert(std::string(bounded.read_export(MAX_LOG_LEN)).empty());
    bounded.write(LOG_PUBLIC, "on", true);
    assert(std::string(bounded.read_export(MAX_LOG_LEN)) == "on");
    bounded.clear();
    assert(std::string(bounded.read_export(MAX_LOG_LEN)).empty());
    Pc pc; Association association;
    Character character; character.only.pc = &pc; character.association = &association;
    pc.log.write(LOG_PUBLIC, "You strike.\r\n", true);
    pc.log.write(LOG_PRIVATE, "private fixture message");
    combat_outcome_payload payload{};
    auto *entry = combat_outcome_add_participant(&payload, &character, combat_participant_role::killer, true, true);
    assert(entry && entry->level == 56);
    assert(std::string(entry->description.data()) == "[56 &+RWarrior&n&n] Fixture &n-Guild- &n(&+WHuman&n&n)");
    assert(entry->equipment == "<wielded> a sword\n");
    assert(entry->log == "You strike.\r\n");
    character.webinfo = false;
    character.name = "Changed"; character.equipment.clear(); pc.log.clear();
    assert(entry->equipment == "<wielded> a sword\n" && entry->log == "You strike.\r\n");
    assert(std::string(entry->description.data()).find("Fixture") != std::string::npos);
    assert(combat_outcome_add_participant(&payload, &character, combat_participant_role::killer_group, true, false) == entry);
    assert(payload.participant_count == 1 && entry->equipment == "<wielded> a sword\n");
    assert(entry->webinfo_at_capture == combat_webinfo::on);
    character.pid = 12;
    auto *hidden = combat_outcome_add_participant(&payload, &character, combat_participant_role::victim, true, false);
    assert(hidden->webinfo_at_capture == combat_webinfo::off && hidden->log.empty() && hidden->equipment.empty());
    character.webinfo = true;
    assert(combat_outcome_add_participant(&payload, &character, combat_participant_role::killer, true, false) == hidden);
    assert(hidden->webinfo_at_capture == combat_webinfo::off && hidden->log.empty());
    assert(equipment_reads == 1); // Neither private capture nor rediscovery reads equipment.
}
'''
        with tempfile.TemporaryDirectory(dir=ROOT / "bin/tests") as directory:
            source = Path(directory) / "capture.cpp"
            binary = Path(directory) / "capture"
            source.write_text(harness)
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", f"-I{SRC}",
                            str(source), "-lbsd", "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            for invalid_index in (-1, 2):
                invalid = subprocess.run(
                    [str(binary), str(invalid_index)], capture_output=True,
                    preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
                self.assertEqual(invalid.returncode, -signal.SIGABRT)

    def test_bounded_pointer_free_codec(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "bin/tests") as directory:
            harness = Path(directory) / "combat_codec.cpp"
            binary = Path(directory) / "combat_codec"
            harness.write_text(HARNESS)
            subprocess.run([
                "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", f"-I{SRC}",
                str(harness), str(SRC / "critical_command.c"),
                str(SRC / "currency_command.c"), str(SRC / "combat_outcome_command.c"),
                "-lcrypto", "-o", str(binary),
            ], check=True)
            subprocess.run([str(binary)], check=True)

    def test_combat_route_has_no_direct_mutation_io(self):
        fight = (SRC / "fight.c").read_text()
        start = fight.index("void AddFrags(P_char ch, P_char victim)")
        end = fight.index("unsigned int calculate_ch_state", start)
        body = fight[start:end]
        self.assertIn("submit_pvp_outcome", body)
        for forbidden in ("sql_modify_frags", "sql_save_pkill", "ADD_MONEY",
                          "redis_invalidate_fraglist", "epic_frag"):
            self.assertNotIn(forbidden, body)
        capture = fight[fight.index("static bool submit_pvp_outcome"):start]
        self.assertIn("combat_outcome_transaction_submit", capture)
        capture = fight[fight.index("static combat_outcome_participant *combat_outcome_add_participant"):start]
        self.assertIn("get_equipment_list(ch, equipment, 1)", capture)
        self.assertIn("GET_PLAYER_LOG(ch)->read_export(MAX_LOG_LEN)", capture)
        self.assertIn("get_class_name(ch, ch)", capture)
        self.assertIn("race_names_table[GET_RACE(ch)].ansi", capture)
        repository = (SRC / "combat_outcome_repository.c").read_text()
        self.assertNotIn("GET_PLAYER_LOG", repository)
        self.assertNotIn("get_equipment_list", repository)

    def test_repository_composes_all_authorities_before_outbox(self):
        repository = (SRC / "combat_outcome_repository.c").read_text()
        generic = (SRC / "critical_command_repository.c").read_text()
        for token in ("FOR UPDATE", "combat_frag_ledger", "epic_ledger",
                      "pkill_event", "pkill_info", "progress"):
            self.assertIn(token, repository)
        # The balances are memory's: the outcome records the kill and the ledgers.
        for token in ("currency_ledger", "SET frags=", "SET epics=", "SET copper="):
            self.assertNotIn(token, repository)
        branch = generic[generic.index("if (combat_command)"):]
        self.assertLess(branch.index("insert_outbox"), branch.index('execute(connection, "COMMIT")'))
        self.assertLess(branch.index("finish_inbox"), branch.index('execute(connection, "COMMIT")'))

    def test_schema_and_checkpoint_protection(self):
        """Require combat schema and fresh-player baseline initialization."""
        migration = (ROOT / "migrations/combat_outcome.sql").read_text()
        bootstrap = (ROOT / "migrations/bootstrap_multithread_safe.sql").read_text()
        runner = (ROOT / "migrations/run_migration.sh").read_text()
        for token in ("frag_revision", "combat_frag_baseline", "combat_outcome",
                      "combat_outcome_participant", "combat_frag_ledger"):
            self.assertIn(token, migration)
            self.assertIn(token, bootstrap)
        self.assertIn("combat_outcome.sql", runner)
        # The save writes the frags memory holds, and a new player's row opens its baseline.
        snapshot = (SRC / "player_snapshot_repository.c").read_text()
        self.assertNotIn("row.field == player_status_field::frags", snapshot)
        self.assertIn('"frags",', snapshot)
        self.assertIn("INSERT IGNORE INTO combat_frag_baseline", snapshot)


if __name__ == "__main__":
    unittest.main()
