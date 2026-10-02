#include "player/player_save_pipeline.h"
#include "persistence/persistence_observability.h"
#include <cstdlib>
#include <cstring>

#include "core/prototypes.h"
#include "core/files.h"
#include "economy/collector_death_enrollment.h"
#include "flatfile/flatfile_player_repository.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_repository.h"
#include "core/structs.h"
#include "core/utils.h"

#include <array>
#include <cerrno>
#include <chrono>
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
	}
	if (succeeded)
	{
		if (completion.kind == persistence_job_kind::player)
			player_revision_record_written(completion.pid, completion.revision);
		if (completion.kind == persistence_job_kind::corpse)
			collector_death_enrollment_saved(completion.owner, completion.error_code);
		return;
	}
	if (completion.kind != persistence_job_kind::player)
	{
		persistence_alert(AVATAR, "persistence_writer",
				  persistence_job_kind_name(completion.kind), "none", "none",
				  "write_failed", "owner=%llu error=%u",
				  (unsigned long long)completion.owner, completion.error_code);
		return;
	}
	// The job is gone. Mark the owner dirty so its next save carries the state again.
	P_char ch = live_player(completion.pid);
#ifdef __NO_MYSQL__
	// The player's records are missing: the next save establishes them synchronously.
	// (MariaDB has no such save; its writer inserts a missing row from the status.)
	if (ch && completion.error_code == ENOENT)
		SET_BIT(ch->runtime_flags, CHAR_RFLAG_NO_DB_BASELINE);
#endif
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

bool player_save_pipeline_init(void)
{
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (health.initialized)
			return false;
		health = {};
	}
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
	accepting = false;
	health.accepting = false;
	health.initialized = false;
}

/** Mark player components dirty. */
bool player_save_pipeline_mark(int pid, player_component_mask_t components)
{
	/* Equipment and inventory are one item graph: a save writes both halves. */
	if (components & (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY))
		components |= PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY;
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (!accepting)
		return false;
	player_revision_t revision = 0;
	if (!player_revision_mark(pid, components, &revision))
		return false;
	++health.marked;
	return true;
}

/** Capture and queue pending player components with the supplied save intent and room. */
player_save_pipeline_result player_save_pipeline_checkpoint_dirty(P_char ch, int save_intent,
								  int room_vnum)
{
	if (!ch || IS_NPC(ch) || GET_PID(ch) <= 0)
		return player_save_pipeline_result::invalid;
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (!health.initialized)
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
	if (!ch || IS_NPC(ch) || !player_save_pipeline_mark(GET_PID(ch), components))
		return player_save_pipeline_result::invalid;
	return player_save_pipeline_checkpoint_dirty(ch, save_intent, room_vnum);
}

/** Capture fresh terminal intent and wait for it to be written within the caller timeout. */
player_save_terminal_result player_save_pipeline_terminal(P_char ch, int save_intent, int room_vnum,
							  uint64_t timeout_msec)
{
	if (!ch || IS_NPC(ch) || GET_PID(ch) <= 0 || !timeout_msec)
		return player_save_terminal_result::invalid;
	const int pid = GET_PID(ch);
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (!health.initialized)
			return player_save_terminal_result::unavailable;
		++health.terminal_saves;
	}
	// Every terminal call captures the caller's current intent and room.
	player_revision_t revision = 0;
	if (!player_revision_mark(pid, PLAYER_CHECKPOINT_COMPONENT_ALL, &revision))
		return player_save_terminal_result::unavailable;
	const auto checkpoint = player_save_pipeline_checkpoint_dirty(ch, save_intent, room_vnum);
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=terminal_begin mono_us=%llu pid=%d revision=%llu checkpoint=%u intent=%d timeout_ms=%llu",
		      (unsigned long long)persistence_observability_now_usec(), pid,
		      (unsigned long long)revision, (unsigned)checkpoint, save_intent,
		      (unsigned long long)timeout_msec);
	const auto deadline =
		std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_msec);
	while (std::chrono::steady_clock::now() < deadline)
	{
		player_save_pipeline_pulse();
		player_revision_snapshot written = {};
		if (player_revision_snapshot_copy(pid, &written) &&
		    written.written_revision >= revision)
		{
			std::lock_guard<std::mutex> lock(pipeline_mutex);
			++health.terminal_database_acks;
			return player_save_terminal_result::database_acknowledged;
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

std::vector<persistence_job_owner> player_save_pipeline_finish(uint64_t deadline_usec,
							       void (*interrupt)(void))
{
	player_save_pipeline_quiesce();
	const uint64_t now = persistence_observability_now_usec();
	const bool drained = persistence_writer_wait_idle(
		deadline_usec > now ? (deadline_usec - now) / 1000 : 0);
	player_save_pipeline_pulse();
	player_save_worker_shutdown(drained ? nullptr : interrupt);
	// The job the writer was on when it stopped may have failed since the pulse.
	player_save_pipeline_pulse();
	std::vector<persistence_job_owner> left = persistence_writer_pending_owners();
	player_save_pipeline_shutdown();
	return left;
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

bool player_save_pipeline_load_held(int pid)
{
	return pid > 0 && player_save_worker_pid_pending(pid);
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
}
