#include "player/player_save_pipeline.h"
#include "persistence/persistence_observability.h"
#include <cstdlib>
#include <cstring>

#include "core/prototypes.h"
#include "core/files.h"
#include "flatfile/flatfile_player_repository.h"
#include "player/player_save_journal.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_repository.h"
#include "core/structs.h"
#include "core/utils.h"

#include <array>
#include <cerrno>
#include <chrono>
#include <limits>
#include <mutex>
#include <thread>
#include <utility>

extern P_char character_list;

namespace
{
/** Cache the explicit diagnostic switch for player-save capture and durability tracing. */
bool trace_player_saves()
{
	static const bool enabled = []
	{
		const char *value = std::getenv("DURIS_NEVENT_TRACE_PLAYER");
		return value && std::strcmp(value, "1") == 0;
	}();
	return enabled;
}

std::mutex pipeline_mutex;
player_save_pipeline_health health = {};
bool accepting = false;

player_save_apply_fn selected_snapshot_apply()
{
#ifdef __NO_MYSQL__
	return flatfile_player_snapshot_apply_selected;
#else
	return player_snapshot_repository_apply_from_pool;
#endif
}

struct terminal_fence
{
	int pid = 0;
	player_revision_t revision = 0;
	bool acknowledged = false;
};

std::array<terminal_fence, PLAYER_SAVE_PIPELINE_MAX_SNAPSHOTS> terminal_fences = {};

struct target_save_login_fence
{
	int pid = 0;
	player_revision_t expected_revision = 0;
};

std::array<target_save_login_fence, PLAYER_SAVE_PIPELINE_MAX_SNAPSHOTS>
	target_save_login_fences = {};

target_save_login_fence *find_target_save_login_fence_locked(int pid);

/** Find a player durability fence; the caller must hold pipeline_mutex. */
terminal_fence *find_terminal_fence_locked(int pid)
{
	for (terminal_fence &fence : terminal_fences)
		if (fence.pid == pid)
			return &fence;
	return nullptr;
}

terminal_fence *allocate_terminal_fence_locked(int pid)
{
	if (find_target_save_login_fence_locked(pid))
		return nullptr;
	if (terminal_fence *existing = find_terminal_fence_locked(pid))
		return existing;
	for (terminal_fence &fence : terminal_fences)
		if (!fence.pid)
		{
			fence.pid = pid;
			++health.terminal_fences;
			return &fence;
		}
	return nullptr;
}

/** Find a recipient-only save/login fence; the caller must hold pipeline_mutex. */
target_save_login_fence *find_target_save_login_fence_locked(int pid)
{
	for (target_save_login_fence &fence : target_save_login_fences)
		if (fence.pid == pid)
			return &fence;
	return nullptr;
}

target_save_login_fence *
allocate_target_save_login_fence_locked(int pid, player_revision_t expected_revision)
{
	if (find_target_save_login_fence_locked(pid))
		return nullptr;
	for (target_save_login_fence &fence : target_save_login_fences)
		if (!fence.pid)
		{
			fence.pid = pid;
			fence.expected_revision = expected_revision;
			return &fence;
		}
	return nullptr;
}

/**
 * Replay a player-save journal left behind by a server that still journaled, then
 * retire it. The journal is never written again, so a record left in it after this
 * boot could only ever roll a character back.
 */
void replay_legacy_journal(const char *directory)
{
	if (!directory || directory[0] != '/')
		return;
	if (!player_save_journal_init(directory))
	{
		logit(LOG_STATUS, "Legacy player-save journal unavailable; nothing replayed.");
		return;
	}
	const player_save_journal_result replayed =
		player_save_journal_replay(selected_snapshot_apply(), nullptr);
	const player_save_journal_health journal = player_save_journal_health_copy();
	bool retired = false;
	if (journal.records)
		retired = player_save_journal_retire();
	player_save_journal_shutdown();
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		health.legacy_journal_replayed = journal.replayed;
		health.legacy_journal_retired = retired;
	}
	logit(LOG_STATUS,
	      "Legacy player-save journal: replayed=%llu remaining=%llu result=%u retired=%d",
	      (unsigned long long)journal.replayed, (unsigned long long)journal.records,
	      (unsigned)replayed, retired ? 1 : 0);
	if (journal.records)
		persistence_alert(AVATAR, "player_save", "legacy_journal", "none", "none",
				  "replay_incomplete", "remaining=%llu retired=%d",
				  (unsigned long long)journal.records, retired ? 1 : 0);
}

P_char live_player(int pid)
{
	for (P_char ch = character_list; ch; ch = ch->next)
		if (IS_PC(ch) && GET_PID(ch) == pid)
			return ch;
	return nullptr;
}

bool completion_succeeded(const player_save_completion &completion)
{
	return completion.outcome == player_save_apply_outcome::applied ||
	       completion.outcome == player_save_apply_outcome::already_applied ||
	       completion.outcome == player_save_apply_outcome::stale_revision;
}

/** Account for one writer completion on the game thread. */
void finish_completion(const player_save_completion &completion)
{
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=completion mono_us=%llu kind=%s owner=%llu revision=%llu components=%llu outcome=%u error=%u retries=%u queued_us=%llu started_us=%llu completed_us=%llu",
		      (unsigned long long)persistence_observability_now_usec(),
		      persistence_job_kind_name(completion.kind),
		      (unsigned long long)completion.owner, (unsigned long long)completion.revision,
		      (unsigned long long)completion.components, (unsigned)completion.outcome,
		      completion.error_code, completion.retry_count,
		      (unsigned long long)completion.queued_at_usec,
		      (unsigned long long)completion.started_at_usec,
		      (unsigned long long)completion.completed_at_usec);
	const bool succeeded = completion_succeeded(completion);
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.completions;
		if (!succeeded)
			++health.write_failures;
		if (terminal_fence *fence = completion.kind == persistence_job_kind::player ?
						    find_terminal_fence_locked(completion.pid) :
						    nullptr;
		    fence && succeeded && completion.revision >= fence->revision)
			fence->acknowledged = true;
	}
	if (succeeded)
		return;
	if (completion.kind != persistence_job_kind::player)
	{
		persistence_alert(AVATAR, "persistence_writer",
				  persistence_job_kind_name(completion.kind), "none", "none",
				  "write_failed", "error=%u", completion.error_code);
		return;
	}
	// The job is gone. Mark the owner dirty so its next save carries the state again.
	P_char ch = live_player(completion.pid);
	if (ch && completion.error_code == ENOENT)
		SET_BIT(ch->runtime_flags, CHAR_RFLAG_NO_DB_BASELINE);
	const bool remarked = ch &&
			      player_save_pipeline_mark(completion.pid, completion.components);
	persistence_alert(AVATAR, "player_save", "redacted", "none", "none", "write_failed",
			  "pid=%d revision=%llu error=%u remarked=%d", completion.pid,
			  (unsigned long long)completion.revision, completion.error_code,
			  remarked ? 1 : 0);
}

/** Hand a sealed capture to the writer. The owner is clean once it is queued. */
player_save_pipeline_result submit_snapshot(player_snapshot snapshot)
{
	const int pid = snapshot.pid;
	const player_revision_t revision = snapshot.revision;
	const player_component_mask_t components = snapshot.components;
	const player_save_submit_result submitted = player_save_worker_submit(std::move(snapshot));
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=submit mono_us=%llu pid=%d revision=%llu outcome=%u",
		      (unsigned long long)persistence_observability_now_usec(), pid,
		      (unsigned long long)revision, (unsigned)submitted);
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (submitted != player_save_submit_result::accepted &&
	    submitted != player_save_submit_result::replaced)
	{
		++health.submit_failures;
		return player_save_pipeline_result::unavailable;
	}
	player_revision_acknowledge_durable(pid, revision, components);
	if (submitted == player_save_submit_result::replaced)
	{
		++health.coalesced;
		return player_save_pipeline_result::coalesced;
	}
	++health.captured;
	return player_save_pipeline_result::queued;
}
} // namespace

bool player_save_pipeline_init(const char *legacy_journal_directory)
{
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (health.initialized)
			return false;
		health = {};
	}
	replay_legacy_journal(legacy_journal_directory);
	if (!player_save_worker_init(selected_snapshot_apply(), nullptr))
		return false;
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	health.initialized = true;
	accepting = true;
	health.accepting = true;
	return true;
}

/** Stop the writer and release pipeline state. */
void player_save_pipeline_shutdown(void)
{
	player_save_worker_shutdown();
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	terminal_fences.fill({});
	target_save_login_fences.fill({});
	accepting = false;
	health.accepting = false;
	health.initialized = false;
}

/** Mark player components dirty and advance any outstanding terminal fence to the new revision. */
bool player_save_pipeline_mark(int pid, player_component_mask_t components)
{
	/* Equipment and inventory are one item graph: a save writes both halves. */
	if (components & (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY))
		components |= PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY;
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (!accepting)
		return false;
	if (find_target_save_login_fence_locked(pid))
		return false;
	player_revision_t revision = 0;
	// Keep admission and the revision transition under the same pipeline lock
	// as target-fence acquisition. Otherwise a save could mark dirty between
	// the offline preflight and the recipient-only fence.
	if (!player_revision_mark(pid, components, &revision))
		return false;
	if (terminal_fence *fence = find_terminal_fence_locked(pid))
	{
		fence->revision = revision;
		fence->acknowledged = false;
	}
	++health.marked;
	return true;
}

/** Capture and queue pending player components with the supplied save intent and room. */
player_save_pipeline_result player_save_pipeline_checkpoint_dirty(P_char ch, int save_intent,
								  int room_vnum)
{
	if (!ch || IS_NPC(ch) || GET_PID(ch) <= 0)
		return player_save_pipeline_result::invalid;
	if (IS_SET(ch->runtime_flags, CHAR_RFLAG_LOAD_DEGRADED))
		return player_save_pipeline_result::unavailable;
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (!health.initialized || find_target_save_login_fence_locked(GET_PID(ch)))
			return player_save_pipeline_result::unavailable;
	}
	player_revision_snapshot revision = {};
	if (!player_revision_snapshot_copy(GET_PID(ch), &revision))
		return player_save_pipeline_result::unavailable;
	if (!revision.unacknowledged_components)
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.unchanged;
		return player_save_pipeline_result::unchanged;
	}
	player_revision_t queued_revision = 0;
	player_component_mask_t components = 0;
	if (!player_revision_queue(GET_PID(ch), &queued_revision, &components))
		return player_save_pipeline_result::capture_failed;
	player_snapshot snapshot;
	if (player_snapshot_capture(ch, queued_revision, components, save_intent, room_vnum,
				    &snapshot) != player_snapshot_capture_result::ok)
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.capture_failures;
		return player_save_pipeline_result::capture_failed;
	}
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=capture mono_us=%llu pid=%d revision=%llu components=%llu intent=%d room=%d",
		      (unsigned long long)persistence_observability_now_usec(), GET_PID(ch),
		      (unsigned long long)queued_revision, (unsigned long long)components,
		      save_intent, room_vnum);
	return submit_snapshot(std::move(snapshot));
}

/** Mark requested components and capture a checkpoint with the supplied intent and room. */
player_save_pipeline_result player_save_pipeline_request(P_char ch,
							 player_component_mask_t components,
							 int save_intent, int room_vnum)
{
	if (ch && IS_SET(ch->runtime_flags, CHAR_RFLAG_LOAD_DEGRADED))
		return player_save_pipeline_result::unavailable;
	if (!ch || IS_NPC(ch) || !player_save_pipeline_mark(GET_PID(ch), components))
		return player_save_pipeline_result::invalid;
	return player_save_pipeline_checkpoint_dirty(ch, save_intent, room_vnum);
}

namespace
{
/** Reserve this player's durability fence and mark the revision the caller will wait on. */
bool begin_terminal_fence(int pid, player_revision_t *revision)
{
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (!health.initialized || find_target_save_login_fence_locked(pid))
			return false;
		if (!allocate_terminal_fence_locked(pid))
			return false;
	}
	// Every terminal call captures the caller's current intent and room.
	if (!player_revision_mark(pid, PLAYER_CHECKPOINT_COMPONENT_ALL, revision))
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (terminal_fence *fence = find_terminal_fence_locked(pid))
			*fence = {};
		return false;
	}
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	terminal_fence *fence = find_terminal_fence_locked(pid);
	if (!fence)
		return false;
	*fence = { pid, *revision, false };
	return true;
}

/** Pump the pipeline until this player revision is written or the deadline passes. */
player_save_terminal_result await_terminal_fence(int pid, player_revision_t revision,
						 uint64_t timeout_msec)
{
	const auto deadline =
		std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_msec);
	while (std::chrono::steady_clock::now() < deadline)
	{
		player_save_pipeline_pulse();
		{
			std::lock_guard<std::mutex> lock(pipeline_mutex);
			terminal_fence *fence = find_terminal_fence_locked(pid);
			if (!fence || fence->revision != revision)
				return player_save_terminal_result::unavailable;
			if (fence->acknowledged)
			{
				++health.terminal_database_acks;
				*fence = {};
				return player_save_terminal_result::database_acknowledged;
			}
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=terminal_timeout mono_us=%llu pid=%d target=%llu",
		      (unsigned long long)persistence_observability_now_usec(), pid,
		      (unsigned long long)revision);
	++health.terminal_timeouts;
	return player_save_terminal_result::timed_out;
}
} // namespace

/** Capture fresh terminal intent and wait for it to be written within the caller timeout. */
player_save_terminal_result player_save_pipeline_terminal(P_char ch, int save_intent, int room_vnum,
							  uint64_t timeout_msec)
{
	if (!ch || IS_NPC(ch) || GET_PID(ch) <= 0 || !timeout_msec)
		return player_save_terminal_result::invalid;
	if (IS_SET(ch->runtime_flags, CHAR_RFLAG_LOAD_DEGRADED))
		return player_save_terminal_result::unavailable;
	const int pid = GET_PID(ch);
	player_revision_t revision = 0;
	if (!begin_terminal_fence(pid, &revision))
		return player_save_terminal_result::unavailable;
	const auto checkpoint = player_save_pipeline_checkpoint_dirty(ch, save_intent, room_vnum);
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=terminal_begin mono_us=%llu pid=%d revision=%llu checkpoint=%u intent=%d timeout_ms=%llu",
		      (unsigned long long)persistence_observability_now_usec(), pid,
		      (unsigned long long)revision, (unsigned)checkpoint, save_intent,
		      (unsigned long long)timeout_msec);
	return await_terminal_fence(pid, revision, timeout_msec);
}

/** Record an immutable death disposition and wait for it to be written. */
player_save_terminal_result
player_save_pipeline_terminal_death(P_char ch, P_obj corpse, P_obj wallet_pile,
				    const critical_operation_id &operation_id, int room_vnum,
				    uint64_t timeout_msec)
{
	if (!ch || IS_NPC(ch) || GET_PID(ch) <= 0 || !corpse || !timeout_msec)
		return player_save_terminal_result::invalid;
	// A payload-gap load keeps its valid item graph read-only. Its only safe
	// terminal write is the immutable death disposition, which records that
	// graph and quarantines matching durable custody. Every other degraded load
	// may be missing state the disposition cannot reconstruct.
	if (IS_SET(ch->runtime_flags, CHAR_RFLAG_LOAD_DEGRADED) &&
	    !IS_SET(ch->runtime_flags, CHAR_RFLAG_LOAD_ITEM_PAYLOAD_GAP))
		return player_save_terminal_result::unavailable;
	const int pid = GET_PID(ch);
	player_revision_t revision = 0;
	if (!begin_terminal_fence(pid, &revision))
		return player_save_terminal_result::unavailable;
	// Only a queued snapshot may retain a fence for an asynchronous completion.
	// Capture/queue refusal must release capacity for other terminal saves.
	struct unqueued_fence_guard
	{
		int pid;
		bool queued = false;
		~unqueued_fence_guard()
		{
			if (!queued)
			{
				std::lock_guard<std::mutex> lock(pipeline_mutex);
				if (terminal_fence *fence = find_terminal_fence_locked(pid))
					*fence = {};
			}
		}
	} guard{ pid };
	player_snapshot snapshot;
	if (player_death_snapshot_capture(ch, corpse, wallet_pile, operation_id, revision,
					  room_vnum, {},
					  &snapshot) != player_snapshot_capture_result::ok)
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.capture_failures;
		return player_save_terminal_result::invalid;
	}
	player_revision_t queued_revision = 0;
	player_component_mask_t components = 0;
	if (!player_revision_queue(pid, &queued_revision, &components) ||
	    queued_revision != revision || components != snapshot.components)
		return player_save_terminal_result::unavailable;
	const auto queued = submit_snapshot(std::move(snapshot));
	if (queued != player_save_pipeline_result::queued &&
	    queued != player_save_pipeline_result::coalesced)
		return player_save_terminal_result::unavailable;
	guard.queued = true;
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=terminal_death_begin mono_us=%llu pid=%d revision=%llu room=%d timeout_ms=%llu",
		      (unsigned long long)persistence_observability_now_usec(), pid,
		      (unsigned long long)revision, room_vnum, (unsigned long long)timeout_msec);
	return await_terminal_fence(pid, revision, timeout_msec);
}

/** Account for every writer completion on the game thread. */
void player_save_pipeline_pulse(void)
{
	player_save_completion completions[PLAYER_SAVE_PIPELINE_PULSE_BUDGET] = {};
	for (;;)
	{
		const size_t completed =
			player_save_worker_pulse(completions, PLAYER_SAVE_PIPELINE_PULSE_BUDGET);
		for (size_t index = 0; index < completed; ++index)
			finish_completion(completions[index]);
		if (completed < PLAYER_SAVE_PIPELINE_PULSE_BUDGET)
			break;
	}
}

void player_save_pipeline_quiesce(void)
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	accepting = false;
	health.accepting = false;
}

void player_save_pipeline_resume(void)
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (health.initialized)
		accepting = true;
	health.accepting = accepting;
}

bool player_save_pipeline_drain(uint64_t timeout_msec)
{
	if (!timeout_msec)
		return false;
	player_save_pipeline_quiesce();
	const bool drained = persistence_writer_wait_idle(timeout_msec);
	player_save_pipeline_pulse();
	if (!drained)
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.drain_failures;
	}
	return drained;
}

player_save_pipeline_health player_save_pipeline_health_copy(void)
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	return health;
}

size_t player_save_pipeline_dirty_count(void)
{
	return player_revision_dirty_count();
}

/** Classify save intents that do not require a terminal durability fence. */
bool player_save_pipeline_is_nonterminal_type(int save_intent)
{
	return save_intent != RENT_INN && save_intent != RENT_LINKDEAD &&
	       save_intent != RENT_CAMPED && save_intent != RENT_DEATH &&
	       save_intent != RENT_POOFARTI && save_intent != RENT_SWAPARTI &&
	       save_intent != RENT_FIGHTARTI;
}

bool player_save_pipeline_target_save_pending(int pid)
{
	if (pid <= 0)
		return true;
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (!health.initialized || !accepting || find_terminal_fence_locked(pid))
			return true;
	}
	if (player_save_worker_pid_pending(pid))
		return true;
	player_revision_snapshot revision = {};
	if (!player_revision_snapshot_copy(pid, &revision))
		return false;
	return revision.overflowed || revision.dirty_components ||
	       revision.unacknowledged_components || revision.queued_components ||
	       revision.inflight_components ||
	       revision.current_revision != revision.acknowledged_revision;
}

bool player_save_pipeline_acquire_target_save_login_fence(int pid,
							  player_revision_t expected_revision)
{
	if (pid <= 0 || expected_revision == std::numeric_limits<player_revision_t>::max())
		return false;
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (!health.initialized || !accepting || find_terminal_fence_locked(pid) ||
		    find_target_save_login_fence_locked(pid) ||
		    !allocate_target_save_login_fence_locked(pid, expected_revision))
			return false;
	}

	// Reserve before checking the writer/revision state. New marks are rejected
	// while reserved, so the final check cannot race a newly admitted save.
	if (player_save_worker_pid_pending(pid))
	{
		player_save_pipeline_release_target_save_login_fence(pid, expected_revision);
		return false;
	}
	player_revision_snapshot revision = {};
	if (player_revision_snapshot_copy(pid, &revision) &&
	    (revision.overflowed || revision.dirty_components ||
	     revision.unacknowledged_components || revision.queued_components ||
	     revision.inflight_components || revision.current_revision != expected_revision ||
	     revision.acknowledged_revision != expected_revision))
	{
		player_save_pipeline_release_target_save_login_fence(pid, expected_revision);
		return false;
	}
	return true;
}

void player_save_pipeline_release_target_save_login_fence(int pid,
							  player_revision_t expected_revision)
{
	if (pid <= 0)
		return;
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (target_save_login_fence *fence = find_target_save_login_fence_locked(pid))
		if (fence->expected_revision == expected_revision)
			*fence = {};
}

bool player_save_pipeline_target_save_login_fenced(int pid)
{
	if (pid <= 0)
		return false;
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	return find_target_save_login_fence_locked(pid) != nullptr;
}

bool player_save_pipeline_save_admitted(int pid)
{
	if (pid <= 0)
		return false;
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	return find_target_save_login_fence_locked(pid) == nullptr;
}

/** Stop the pipeline and clear writer, revision, and health state for an isolated test. */
void player_save_pipeline_reset_for_tests(void)
{
	player_save_pipeline_shutdown();
	player_save_worker_reset_for_tests();
	player_revision_reset_for_tests();
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	health = {};
	accepting = false;
	terminal_fences.fill({});
	target_save_login_fences.fill({});
}
