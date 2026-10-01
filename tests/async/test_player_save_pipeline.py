#!/usr/bin/env python3
"""Player saves go straight to the one writer; nothing is journaled."""

from _paths import SRC, rel
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = (SRC / "player_save_pipeline.c").read_text()
HEADER = (SRC / "player_save_pipeline.h").read_text()
FILES = (SRC / "files.c").read_text()
ACTOTH = (SRC / "actoth.c").read_text()
CHECKPOINT = (SRC / "persistence_checkpoint.c").read_text()
EVENTS = (SRC / "new_events.c").read_text()
COMM = (SRC / "comm.c").read_text()
NANNY = (SRC / "nanny.c").read_text()


def section(text: str, start: str, end: str) -> str:
    """Extract a production function region for contract checks."""
    first = text.index(start)
    return text[first : text.index(end, first)]


HARNESS = r'''
#include "player/player_save_pipeline.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_capture.h"
#include "persistence/persistence_observability.h"
#include "core/prototypes.h"
#include "core/utils.h"

#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdlib>
#include <filesystem>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

P_char character_list = nullptr;
int alerts = 0;

void logit(const char *, const char *, ...) {}
void collector_death_enrollment_saved(uint64_t, unsigned int) {}
void persistence_alert(int, const char *, const char *, const char *, const char *,
                       const char *, const char *, ...)
{
    ++alerts;
}
int panic_corruption_int(const char *, const char *, ...)
{
    std::abort();
}

struct apply_state
{
    std::mutex mutex;
    std::condition_variable changed;
    std::vector<std::string> order;
    std::map<int, unsigned int> failures;
    bool hold = false;
    bool holding = false;
};
apply_state state;

player_save_apply_result player_snapshot_repository_apply_from_pool(const player_snapshot &snapshot,
                                                                    void *)
{
    std::unique_lock<std::mutex> lock(state.mutex);
    if (state.hold)
    {
        state.holding = true;
        state.changed.notify_all();
        state.changed.wait(lock, [] { return !state.hold; });
        state.holding = false;
    }
    state.order.push_back(std::to_string(snapshot.pid) + ":" + std::to_string(snapshot.revision));
    if (state.failures[snapshot.pid])
    {
        --state.failures[snapshot.pid];
        return {player_save_apply_outcome::terminal_failure, 0, 1452};
    }
    return {player_save_apply_outcome::applied, snapshot.revision, 0};
}

player_snapshot_capture_result player_snapshot_capture(P_char ch, player_revision_t revision,
                                                       player_component_mask_t components, int,
                                                       int, player_snapshot *snapshot)
{
    *snapshot = {};
    snapshot->schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
    snapshot->pid = GET_PID(ch);
    snapshot->revision = revision;
    snapshot->components = components;
    snapshot->encoded_size_bound = 128;
    return player_snapshot_capture_result::ok;
}

struct player
{
    char_data ch = {};
    pc_only_data pc = {};
    explicit player(int pid)
    {
        ch.only.pc = &pc;
        pc.pid = pid;
    }
};

void hold_writer(bool hold)
{
    std::lock_guard<std::mutex> lock(state.mutex);
    state.hold = hold;
    state.changed.notify_all();
}

void wait_until_held()
{
    std::unique_lock<std::mutex> lock(state.mutex);
    state.changed.wait(lock, [] { return state.holding; });
}

std::vector<std::string> take_order()
{
    std::lock_guard<std::mutex> lock(state.mutex);
    std::vector<std::string> order;
    order.swap(state.order);
    return order;
}

int main()
{
    assert(player_save_pipeline_init());
    player alice(41), bob(42), carol(44);
    alice.ch.next = &bob.ch;
    bob.ch.next = &carol.ch;
    character_list = &alice.ch;
    assert(player_revision_hydrate(41, 7));
    assert(player_revision_hydrate(42, 0));
    assert(player_revision_hydrate(44, 0));

    // Nothing dirty, nothing captured.
    assert(player_save_pipeline_checkpoint_dirty(&alice.ch, 1, 3001) ==
           player_save_pipeline_result::unchanged);

    // A queued save leaves its owner clean: the writer has it.
    hold_writer(true);
    assert(player_save_pipeline_request(&bob.ch, PLAYER_COMPONENT_SKILLS, 1, 3001) ==
           player_save_pipeline_result::queued);
    wait_until_held();
    assert(player_save_pipeline_request(&alice.ch, PLAYER_COMPONENT_STATUS, 1, 3001) ==
           player_save_pipeline_result::queued);
    player_revision_snapshot revision = {};
    assert(player_revision_snapshot_copy(41, &revision));
    assert(revision.current_revision == 8 && revision.acknowledged_revision == 8);
    assert(!revision.unacknowledged_components && !revision.dirty_components);
    // Accepted is not written: `save` reports completion on the written revision.
    assert(revision.written_revision == 7);
    // A newer save queues behind what was queued after the owner's save, and replaces
    // the owner's save only when that is the last one queued.
    assert(player_save_pipeline_request(&carol.ch, PLAYER_COMPONENT_STATUS, 1, 3001) ==
           player_save_pipeline_result::queued);
    assert(player_save_pipeline_request(&alice.ch, PLAYER_COMPONENT_AFFECTS, 1, 3001) ==
           player_save_pipeline_result::queued);
    assert(player_save_pipeline_request(&alice.ch, PLAYER_COMPONENT_SKILLS, 1, 3001) ==
           player_save_pipeline_result::coalesced);
    // Equipment and inventory are one item graph.
    assert(player_save_pipeline_mark(42, PLAYER_COMPONENT_INVENTORY));
    assert(player_revision_snapshot_copy(42, &revision));
    assert(revision.dirty_components ==
           (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY));
    assert(player_save_pipeline_checkpoint_dirty(&bob.ch, 1, 3001) ==
           player_save_pipeline_result::queued);

    // A stalled writer fails the drain within its bound and admission resumes.
    assert(!player_save_pipeline_drain(20));
    assert(player_save_pipeline_health_copy().drain_failures == 1);
    assert(!player_save_pipeline_mark(41, PLAYER_COMPONENT_STATUS));
    player_save_pipeline_resume();
    assert(player_save_pipeline_mark(41, PLAYER_COMPONENT_STATUS));

    hold_writer(false);
    assert(persistence_writer_wait_idle(5000));
    // Bob's first save was being written; everything else in capture order.
    assert((take_order() == std::vector<std::string>{"42:1", "41:8", "44:1", "41:10", "42:2"}));
    player_save_pipeline_pulse();
    assert(player_revision_snapshot_copy(41, &revision) && revision.written_revision == 10);

    // A failed write is reported and its owner is dirty again.
    state.failures[44] = 1;
    assert(player_save_pipeline_request(&carol.ch, PLAYER_COMPONENT_TIMERS, 1, 3001) ==
           player_save_pipeline_result::queued);
    assert(persistence_writer_wait_idle(5000));
    const int alerts_before = alerts;
    player_save_pipeline_pulse();
    assert(alerts == alerts_before + 1);
    assert(player_revision_snapshot_copy(44, &revision));
    assert(revision.dirty_components == PLAYER_COMPONENT_TIMERS);
    assert(revision.written_revision == 1);
    player_save_pipeline_health health = player_save_pipeline_health_copy();
    assert(health.write_failures == 1);
    assert(player_save_pipeline_checkpoint_dirty(&carol.ch, 1, 3001) ==
           player_save_pipeline_result::queued);

    assert(player_save_pipeline_drain(5000));
    assert((take_order() == std::vector<std::string>{"44:2", "44:3"}));

    // Shutdown reports a save that failed after its last pulse: the writer was still on
    // it when the drain ran out, and the interrupt made it fail.
    player_save_pipeline_resume();
    hold_writer(true);
    state.failures[41] = 1;
    assert(player_save_pipeline_request(&alice.ch, PLAYER_COMPONENT_STATUS, 1, 3001) ==
           player_save_pipeline_result::queued);
    wait_until_held();
    const int alerts_at_shutdown = alerts;
    const auto left = player_save_pipeline_finish(persistence_observability_now_usec() + 20000,
                                                  [] { hold_writer(false); });
    assert(left.empty());
    assert(alerts == alerts_at_shutdown + 1);
    player_save_pipeline_reset_for_tests();
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-player-save-pipeline-") as temp_dir:
    source = Path(temp_dir) / "pipeline_test.cpp"
    binary = Path(temp_dir) / "pipeline_test"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-pthread",
            "-Isrc",
            "-I/usr/include/mysql",
            str(source),
            rel("player_save_pipeline.c"),
            rel("player_save_worker.c"),
            rel("player_snapshot_codec.c"),
            rel("player_revision_state.c"),
            rel("persistence_observability.c"),
            "-lmysqlclient",
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run([str(binary)], check=True, timeout=60)
print("[PASS] a queued save leaves its owner clean; a newer save replaces the queued one")
print("[PASS] a failed write is reported and marks its owner dirty again")
print("[PASS] drain waits for the writer within its bound")
print("[PASS] shutdown reports a save that failed after the last pulse")

assert "PLAYER_SAVE_PIPELINE_MAX_BYTES" not in HEADER
assert "pending_append" not in PIPELINE and "durable_ready" not in PIPELINE
assert "dispatcher" not in PIPELINE
assert "player_save_journal_append" not in PIPELINE
checkpoint = section(
    PIPELINE,
    "player_save_pipeline_result player_save_pipeline_checkpoint_dirty",
    "player_save_pipeline_result player_save_pipeline_request",
)
assert checkpoint.index("player_revision_queue") < checkpoint.index("player_snapshot_capture")
for forbidden in ("player_save_journal_", "sql_", "redis_", "fopen", "open(", "write("):
    assert forbidden not in checkpoint
pulse = section(PIPELINE, "void player_save_pipeline_pulse", "void player_save_pipeline_quiesce")
assert "player_save_worker_pulse" in pulse
for forbidden in ("player_save_journal_", "sql_", "redis_", "fopen", "open(", "write("):
    assert forbidden not in pulse
print("[PASS] game-thread checkpoint and completion paths contain no external I/O")

write_character = section(FILES, "int writeCharacter(P_char ch", "character_delete_result forget_deleted_character(")
# Every MariaDB save, terminal ones too, is queued: no synchronous SQL is left in it.
branch = write_character.index("player_save_pipeline_request(")
assert "const bool queued_save = true;" in write_character[:branch]
for legacy in ("sql_save_player", "sql_update_money", "sql_save_locker"):
    assert legacy not in write_character, legacy
silent = section(ACTOTH, "bool do_save_silent(P_char ch", "void do_save(P_char")
assert silent.index("player_save_pipeline_is_nonterminal_type") < silent.index("fopen(tmp_buf")
assert silent.index("player_save_pipeline_request") < silent.index("writeCharacter(ch")
init_char = section(NANNY, "void init_char(P_char ch)", "int approve_mode")
assert "player_revision_hydrate(ch->only.pc->pid, 0)" in init_char
print("[PASS] ordinary direct and manual saves branch before legacy mutation and I/O")

mark = section(CHECKPOINT, "void mark_player_dirty(int pid)", "void flush_dirty_players(void)")
flush = section(CHECKPOINT, "void flush_dirty_players(void)", "int get_dirty_player_count(void)")
assert "player_save_pipeline_mark" in mark
assert "player_save_pipeline_checkpoint_dirty" in flush
for retired in ("redis_command", "redis_reconnect", "sql_save_player", "fork("):
    assert retired not in mark and retired not in flush
event_init = section(EVENTS, "void ne_init_events", "void zone_purge")
assert '"dirty-player-checkpoint", event_flush_dirty_players' in event_init
assert "nevent_periodic_policy::fixed_delay, true" in event_init
print("[PASS] autosave is local and the Redis dirty-save fork is retired")

assert "player_save_pipeline_init()" in COMM
assert "player_save_pipeline_pulse();" in COMM
assert "player_save_pipeline_finish(shutdown_writer_deadline_usec," in COMM
assert "player_save_pipeline_shutdown();" in section(
    (SRC / "player_save_pipeline.c").read_text(), "std::vector<persistence_job_owner> player_save_pipeline_finish(",
    "player_save_pipeline_health player_save_pipeline_health_copy(void)")
print("[PASS] the pipeline starts at boot and shutdown finishes it")

print("player save pipeline contracts passed")
