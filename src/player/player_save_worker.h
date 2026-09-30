#ifndef PLAYER_SAVE_WORKER_H
#define PLAYER_SAVE_WORKER_H

#include "player/player_snapshot.h"

#include <cstddef>
#include <cstdint>
#include <functional>
#include <utility>
#include <vector>

/*
 * The one persistence writer. A single background thread applies every queued
 * save in the order it was captured: player saves (with their pets), corpse
 * saves, locker saves, saved room items, log_entries rows and critical commands.
 * A newer save of the same owner replaces its queued one and goes to the back of
 * the queue; each log row and each command is its own owner, so none replaces
 * another.
 *
 * A lost connection is retried at the head of the queue. Any other failure is
 * reported through the completion and the job is dropped; the caller marks the
 * owner dirty so its next save carries the state again.
 */
constexpr unsigned int PLAYER_SAVE_WORKER_DEFAULT_THREADS = 1;
constexpr uint64_t PLAYER_SAVE_WORKER_MAX_AGE_MSEC = 5 * 60 * 1000;
constexpr uint64_t PLAYER_SAVE_WORKER_RETRY_INITIAL_MSEC = 100;
constexpr uint64_t PLAYER_SAVE_WORKER_RETRY_MAX_MSEC = 5000;
// How long an interrupted writer gets to stop before shutdown goes on without it.
constexpr uint64_t PLAYER_SAVE_WORKER_STOP_GRACE_MSEC = 1000;

enum class persistence_job_kind : uint8_t
{
	player,
	corpse,
	locker,
	saved_item,
	log,
	// A critical command (critical_command_coordinator.c), in capture order with the saves.
	critical,
	// A change to an account's bank, added to what the database holds.
	bank,
	// A shopkeeper's stock, keyed by shop.
	shopkeeper,
	// Statements or a read the game thread queued (sql_async.c); each is its own owner.
	sql,
};

enum class player_save_apply_outcome : uint8_t
{
	applied,
	already_applied,
	stale_revision,
	retryable_failure,
	terminal_failure,
	ambiguous_commit,
};

struct player_save_apply_result
{
	player_save_apply_outcome outcome;
	player_revision_t durable_revision;
	unsigned int error_code;
};

struct player_save_completion
{
	persistence_job_kind kind;
	uint64_t owner;
	int32_t pid;
	player_revision_t revision;
	player_component_mask_t components;
	player_save_apply_outcome outcome;
	unsigned int error_code;
	unsigned int retry_count;
	uint64_t queued_at_usec;
	uint64_t started_at_usec;
	uint64_t completed_at_usec;
};

enum class player_save_submit_result : uint8_t
{
	accepted,
	replaced,
	invalid,
	unavailable,
};

struct player_save_worker_health
{
	uint64_t queued_jobs;
	uint64_t inflight_jobs;
	uint64_t queued_bytes;
	uint64_t high_water_jobs;
	uint64_t high_water_bytes;
	uint64_t oldest_age_msec;
	bool age_limit_exceeded;
	uint64_t submitted;
	uint64_t replaced;
	uint64_t applied;
	uint64_t connection_retries;
	uint64_t failures;
	uint64_t max_capture_to_apply_usec;
	uint64_t max_apply_usec;
	bool running;
	bool stop_pending;
};

// The apply context of the one-time replay of a journal left by an older server,
// the only apply that keeps the revision fence.
inline char player_save_legacy_replay_marker = 0;
#define PLAYER_SAVE_LEGACY_REPLAY (static_cast<void *>(&player_save_legacy_replay_marker))

using player_save_apply_fn = player_save_apply_result (*)(const player_snapshot &snapshot,
							  void *context);
// Writes one sealed corpse, locker, saved room item or log job on the writer thread.
using persistence_job_write_fn = std::function<player_save_apply_result()>;
using persistence_job_owner = std::pair<persistence_job_kind, uint64_t>;

bool player_save_worker_init(player_save_apply_fn apply, void *context);
// Stops after the job being written. If one is being written, `interrupt` (when given)
// is called to cut its database call short; the job then stays pending. A writer that
// has not stopped within PLAYER_SAVE_WORKER_STOP_GRACE_MSEC after that (a new
// connection being opened cannot be cut short) is left to finish on its own. Jobs
// still queued are not written: persistence_writer_pending_owners() names them all.
void player_save_worker_shutdown(void (*interrupt)(void) = nullptr);
player_save_submit_result player_save_worker_submit(player_snapshot snapshot);
player_save_submit_result persistence_writer_submit(persistence_job_kind kind, uint64_t owner,
						    size_t bytes, persistence_job_write_fn write);
size_t player_save_worker_pulse(player_save_completion *completions_out, size_t capacity);
// True while this owner has a save queued or being written.
bool player_save_worker_pid_pending(int pid);
bool persistence_writer_pending(persistence_job_kind kind, uint64_t owner);
// Blocks until nothing is queued or being written, or the timeout passes.
bool persistence_writer_wait_idle(uint64_t timeout_msec);
std::vector<persistence_job_owner> persistence_writer_pending_owners(void);
const char *persistence_job_kind_name(persistence_job_kind kind);
player_save_worker_health player_save_worker_health_copy(void);
void player_save_worker_reset_for_tests(void);

#endif
