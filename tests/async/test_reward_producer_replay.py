#!/usr/bin/env python3
"""Real producer guards after the real coordinator's completed cache is evicted.

Database results and final gameplay notifications are controlled boundaries.
The live artifact path and full boon journey are covered by their own fixtures.
"""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS

HARNESS = r'''

#include "economy/boon_reward_transaction.h"
#include "economy/boon.h"
#include "combat/combat_outcome_transaction.h"
#include "world/zone_touch_transaction.h"
#include "world/epic.h"
#include "guild/artifact_guild_transaction.h"
#include "economy/currency_transaction.h"
#include "flatfile/flatfile_boon_repository.h"
#include "persistence/persistence_mode.h"
#include "persistence/persistence_checkpoint.h"
#include "player/player_save_worker.h"
#include "world/db.h"
#include "core/utils.h"
#include "sql/sql_async.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <thread>
#include <sys/syscall.h>
#include <unistd.h>

P_room world = nullptr;
zone_data *zone_table = nullptr;
P_index mob_index = nullptr;
static char_data actors[2] = {};
static pc_only_data pcs[2] = {};
static bool online[2] = { true, true };
static unsigned int boon_publications = 0, combat_publications = 0, stone_publications = 0;
static std::vector<critical_operation_id> artifact_parents;
static bool allow_definition_read = false;
static std::function<void(bool, const sql_rows &)> definition_read;
static std::atomic<time_t> clock_offset{0};
extern "C" int clock_gettime(clockid_t clock, timespec *value) noexcept
{
	const int result = syscall(SYS_clock_gettime, clock, value);
	if (!result && clock == CLOCK_MONOTONIC)
		value->tv_sec += clock_offset;
	return result;
}
bool sql_read_at(persistence_query_site, std::string sql,
		 std::function<void(bool, const sql_rows &)> done)
{
	assert(sql.find("FROM boons WHERE active=1") != std::string::npos);
	if (!allow_definition_read)
		return false;
	assert(!definition_read);
	definition_read = std::move(done);
	return true;
}
static void definitions_ready(bool ok, const sql_rows &rows)
{
	assert(definition_read);
	auto done = std::move(definition_read);
	definition_read = {};
	done(ok, rows);
}
P_char find_player_by_pid(int pid)
{
	for (size_t i = 0; i < 2; ++i)
		if (pcs[i].pid == pid && online[i])
			return &actors[i];
	return nullptr;
}
persistence_mode persistence_mode_get()
{
	return PERSISTENCE_MODE_MARIADB_PRIMARY;
}
bool persistence_mode_requires_mysql()
{
	return true;
}
const char *persistence_mode_flatfile_root()
{
	return nullptr;
}
flatfile_boon_result flatfile_boon_acknowledge_reward(const std::string &,
						      const critical_operation_id &, std::string *)
{
	std::abort();
}
void mark_player_dirty_components(int, player_component_mask_t) {}
void boon_publish_transaction_result(P_char ch, double, const boon_reward_result &result)
{
	assert(GET_PID(ch) == 42 && result.entry_count == 1);
	++boon_publications;
}
void epic_publish_zone_touch(const zone_touch_result &) {}
void epic_finish_stone_touch(const zone_touch_result &) {}
void epic_publish_stone_award(P_char, const zone_touch_result &, size_t)
{
	++stone_publications;
}
bool artifact_guild_transaction_submit(P_char, const critical_operation_id &parent, int, int)
{
	artifact_parents.push_back(parent);
	return true;
}
bool currency_transaction_submit_wallet_value(P_char, int64_t, currency_reason_type, int64_t,
					      critical_source_site, critical_deadline_class,
					      currency_completion_fn, const void *, size_t)
{
	std::abort();
}
static void combat_complete(bool ok, const combat_outcome_result &, unsigned int,
			    const combat_outcome_payload &)
{
	assert(ok);
	++combat_publications;
}

static critical_apply_result apply(const critical_command &command, void *)
{
	critical_apply_result result = { critical_apply_outcome::applied, 1, 0 };
	if (command.type == critical_command_type::test)
		return result;
	boon_reward_payload boon = {};
	combat_outcome_payload combat = {};
	zone_touch_payload stone = {};
	if (boon_reward_command_decode_payload(command, &boon))
	{
		boon_reward_result outcome = {};
		outcome.pid = boon.pid;
		outcome.entry_count = 1;
		outcome.entries[0].boon_id = 1;
		outcome.entries[0].type = BTYPE_EPIC;
		outcome.entries[0].flags = BOON_RESULT_COMPLETED;
		outcome.entries[0].bonus = 4;
		std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
		assert(boon_reward_command_encode_result(outcome, &bytes));
		result.result_size = bytes.size();
		std::copy(bytes.begin(), bytes.end(), result.result_payload.begin());
	}
	else if (combat_outcome_command_decode_payload(command, &combat))
	{
		combat_outcome_result outcome = {};
		outcome.event_id = 1;
		outcome.participant_count = combat.participant_count;
		for (size_t i = 0; i < outcome.participant_count; ++i)
			outcome.participants[i].pid = combat.participants[i].pid;
		std::array<uint8_t, COMBAT_OUTCOME_RESULT_BYTES> bytes;
		assert(combat_outcome_command_encode_result(outcome, &bytes));
		result.result_size = bytes.size();
		std::copy(bytes.begin(), bytes.end(), result.result_payload.begin());
	}
	else
	{
		assert(zone_touch_command_decode_payload(command, &stone));
		zone_touch_result outcome(stone);
		std::array<uint8_t, ZONE_TOUCH_RESULT_BYTES> bytes;
		assert(zone_touch_command_encode_result(outcome, &bytes));
		result.result_size = bytes.size();
		std::copy(bytes.begin(), bytes.end(), result.result_payload.begin());
	}
	return result;
}
static player_save_apply_result save(const player_snapshot &, void *)
{
	std::abort();
}
static std::vector<critical_completion> original;
static void deliver(const critical_completion *results, size_t count)
{
	for (size_t i = 0; i < count; ++i)
		if (results[i].type != critical_command_type::test)
			original.push_back(results[i]);
	boon_reward_transaction_handle_completions(results, count);
	combat_outcome_transaction_handle_completions(results, count);
	zone_touch_transaction_handle_completions(results, count);
}
static void replay()
{
	boon_reward_transaction_handle_completions(original.data(), original.size());
	combat_outcome_transaction_handle_completions(original.data(), original.size());
	zone_touch_transaction_handle_completions(original.data(), original.size());
}
static void definition_view_checks()
{
	allow_definition_read = true;
	const auto initial = boon_reward_transaction_health_copy();
	const auto submitted = [] { return boon_reward_transaction_health_copy().submitted; };
	const auto check = [] { assert(boon_reward_transaction_submit(&actors[0], nullptr, 51, BOPT_LEVEL)); };
	const auto forwarded = [&] {
		const auto before = submitted();
		check();
		assert(submitted() == before + 1);
	};
	const auto filtered = [&] {
		const auto before = submitted();
		check();
		assert(submitted() == before);
	};
	forwarded(); // Missing and loading views use the canonical writer.
	forwarded();
	definitions_ready(true, {});
	for (int i = 0; i < 100; ++i)
		filtered();
	const auto burst = boon_reward_transaction_health_copy();
	assert(burst.checked - initial.checked == 102 && burst.submitted - initial.submitted == 2 &&
	       burst.filtered - initial.filtered == 100);
	puts("definition view burst: 102 checks, 2 cold/loading submissions, 100 filtered before ID allocation");
	// A writer retry can apply after a newer view has already arrived.
	std::thread writer_retry([] { boon_reward_definition_view_invalidate(); });
	writer_retry.join();
	forwarded();
	definitions_ready(true, {});
	boon_reward_definition_view_invalidate(); // An activation/edit invalidates now.
	forwarded();
	boon_reward_definition_view_invalidate();
	definitions_ready(true, {}); // In-flight pre-edit read cannot restore negatives.
	forwarded();
	definitions_ready(true, { sql_row{ { "2", "2", "42" } } });
	filtered(); // Side mismatch.
	actors[0].player.racewar = 2;
	forwarded(); // A changed side is evaluated from the current payload.
	actors[0].player.racewar = RACEWAR_GOOD;
	boon_reward_definition_view_invalidate();
	forwarded();
	definitions_ready(true, { sql_row{ { "2", "0", "99" } } });
	filtered(); // Target mismatch.
	boon_reward_definition_view_invalidate();
	forwarded();
	definitions_ready(true, { sql_row{ { "2", "0", "42" } } });
	forwarded(); // Retargeted definition applies immediately after its fresh read.
	boon_reward_definition_view_invalidate();
	forwarded();
	definitions_ready(true, { sql_row{ { "3", "0", "0" } } });
	filtered(); // Another option cannot match.
	clock_offset += 61;
	forwarded(); // Expired negative view never drops an event.
	definitions_ready(false, {});
	forwarded(); // Read failure falls back.
	definitions_ready(true, { sql_row{ { "2", "0" } } });
	forwarded(); // An incomplete view falls back.
	definitions_ready(true, sql_rows(100, sql_row{ { "3", "0", "0" } }));
	forwarded(); // Truncated/oversize views cannot prove absence.
	clock_offset += 61;
	definitions_ready(true, {});
	forwarded(); // A delayed response is already stale at arrival.
	definitions_ready(true, {});
	filtered();
	boon_reward_definition_view_invalidate();
	allow_definition_read = false;
	forwarded(); // Refused asynchronous read falls back too.
	assert(boon_reward_transaction_health_copy().definition_failures >= 4);
	assert(critical_command_coordinator_drain(5000));
}
int main()
{
	for (size_t i = 0; i < 2; ++i)
	{
		actors[i].only.pc = &pcs[i];
		pcs[i].pid = 42 + i;
		actors[i].player.level = 51;
		actors[i].player.racewar = RACEWAR_GOOD;
		actors[i].in_room = -1;
	}
	assert(player_save_worker_init(save, nullptr));
	assert(critical_command_coordinator_init(apply, nullptr));
	critical_command_coordinator_set_drain_observer(deliver);
	assert(boon_reward_transaction_submit(&actors[0], nullptr, 51, BOPT_LEVEL));
	combat_outcome_payload combat = {};
	combat.victim_pid = 43;
	combat.room_vnum = 1;
	combat.participant_count = 2;
	combat.participants[0].pid = 42;
	combat.participants[0].role = combat_participant_role::killer;
	combat.participants[0].frag_delta = 100;
	combat.participants[0].epic_delta = 4;
	combat.participants[1].pid = 43;
	combat.participants[1].role = combat_participant_role::victim;
	combat.participants[1].frag_delta = -100;
	assert(combat_outcome_transaction_submit(combat, combat_complete));
	assert(pcs[0].epics == 4 && pcs[0].frags == 100);
	online[1] = false;
	zone_touch_payload stone = {};
	stone.zone_number = 77;
	stone.toucher_pid = 42;
	stone.stone_uid = 99;
	stone.group_size = 2;
	stone.participant_pids[0] = 42;
	stone.participant_pids[1] = 43;
	stone.awards[0] = { 4, 77, 0 };
	stone.awards[1] = { 8, 0, 0 };
	assert(zone_touch_transaction_submit(stone));
	assert(critical_command_coordinator_drain(5000));
	assert(boon_publications == 1 && combat_publications == 1 && stone_publications == 1);
	assert(original.size() == 3 && artifact_parents.size() == 1 && pcs[0].epics == 8);
	replay();
	assert(boon_publications == 1 && combat_publications == 1 && stone_publications == 1);
	// More later completions than the entire cache, without touching a live source.
	for (size_t i = 0; i < CRITICAL_COORDINATOR_COMPLETED_CACHE_MAX + 20; ++i)
	{
		critical_command filler = {};
		assert(critical_operation_id_generate(&filler.operation_id));
		filler.schema_version = CRITICAL_COMMAND_SCHEMA_VERSION;
		filler.type = critical_command_type::test;
		filler.payload_version = 1;
		filler.source_site = critical_source_site::recovery;
		filler.deadline_class = critical_deadline_class::recovery;
		filler.keys = { { critical_entity_type::item, 10000 + i } };
		filler.payload = { 1 };
		assert(critical_command_coordinator_submit(std::move(filler)) ==
		       critical_submit_result::accepted);
	}
	assert(critical_command_coordinator_drain(10000));
	assert(critical_command_coordinator_health_copy().completed_cache ==
	       CRITICAL_COORDINATOR_COMPLETED_CACHE_MAX);
	replay();
	assert(boon_publications == 1 && combat_publications == 1 && stone_publications == 1);
	assert(pcs[0].epics == 8 && pcs[0].frags == 100 && artifact_parents.size() == 1);
	online[1] = true;
	zone_touch_transaction_player_ready(&actors[1]);
	assert(stone_publications == 2 && pcs[1].epics == 8 && artifact_parents.size() == 2);
	assert(artifact_parents[0].bytes != artifact_parents[1].bytes);
	replay();
	zone_touch_transaction_player_ready(&actors[1]);
	assert(stone_publications == 2 && artifact_parents.size() == 2 && pcs[1].epics == 8);
	assert(boon_publications == 1 && combat_publications == 1);
	definition_view_checks();
	assert(persistence_writer_wait_idle(5000));
	critical_command_coordinator_reset_for_tests();
	player_save_worker_reset_for_tests();
	puts("PASS real boon/combat/stone guards survive duplicate delivery and coordinator-cache eviction; offline stone publishes once");
}
'''

outputs = ROOT / 'bin/tests'
outputs.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='reward-replay-', dir=outputs) as directory:
    cpp=Path(directory)/'replay.cpp'; binary=Path(directory)/'replay'
    cpp.write_text(HARNESS)
    sources = [
        'persistence/critical_command.c', 'persistence/critical_command_coordinator.c',
        'persistence/persistence_observability.c', 'player/player_save_worker.c',
        'economy/boon_reward_command.c', 'economy/boon_reward_transaction.c',
        'economy/currency_command.c',
        'combat/combat_outcome_command.c', 'combat/combat_outcome_transaction.c',
        'world/zone_touch_command.c', 'world/zone_touch_transaction.c', 'world/epic_command.c',
    ]
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-pthread',
                    '-ffunction-sections','-fdata-sections','-Isrc','-I/usr/include/mysql',str(cpp),
                    *[str(ROOT/'src'/p) for p in sources],str(HARNESS_STUBS),
                    '-Wl,--gc-sections','-lcrypto','-lmysqlclient','-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],check=True,timeout=30)
