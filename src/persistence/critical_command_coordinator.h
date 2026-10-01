#ifndef CRITICAL_COMMAND_COORDINATOR_H
#define CRITICAL_COMMAND_COORDINATOR_H

#include "persistence/critical_command_completion.h"

#include <cstddef>
#include <cstdint>

constexpr size_t CRITICAL_COORDINATOR_MAX_OPERATIONS = 1024;
constexpr size_t CRITICAL_COORDINATOR_MAX_BYTES = 64 * 1024 * 1024;
constexpr size_t CRITICAL_COORDINATOR_COMPLETED_CACHE_MAX = 256;
constexpr size_t CRITICAL_COORDINATOR_COMPLETED_CACHE_BYTES = 8 * 1024 * 1024;

enum class critical_submit_result : uint8_t
{
	// Queued on the one persistence writer; durable once it has landed.
	accepted,
	attached,
	invalid,
	identity_conflict,
	overloaded,
	unavailable,
};

inline bool critical_submit_result_keeps_operation(critical_submit_result result)
{
	return result == critical_submit_result::accepted ||
	       result == critical_submit_result::attached;
}

struct critical_coordinator_health
{
	uint64_t queued;
	uint64_t inflight;
	uint64_t blocked;
	uint64_t publication_pending;
	uint64_t retained_bytes;
	uint64_t completed_cache;
	uint64_t fenced_keys;
	uint64_t high_water_operations;
	uint64_t high_water_bytes;
	uint64_t oldest_age_msec;
	uint64_t accepted;
	uint64_t attached;
	uint64_t completed;
	uint64_t retries;
	uint64_t ambiguous;
	uint64_t terminal_failures;
	uint64_t stale_completions;
	uint64_t overloads;
	bool initialized;
	bool accepting;
	bool running;
};

using critical_apply_fn = critical_apply_result (*)(const critical_command &command, void *context);
using critical_drain_observer_fn = void (*)(const critical_completion *completions, size_t count);

// Commands run on the one persistence writer (player_save_worker.h), which must be
// running.
bool critical_command_coordinator_init(critical_apply_fn apply, void *context);
void critical_command_coordinator_shutdown(void);
critical_submit_result critical_command_coordinator_submit(critical_command command);
// Opt-in path for commands whose durable result is not complete until the game
// thread has safely published its live projection. The operation and all of its
// entity fences remain held until critical_command_coordinator_acknowledge_publication().
critical_submit_result
critical_command_coordinator_submit_for_publication(critical_command command);
// Release a publication-held operation only after the live callback succeeded. A false
// result leaves the operation fenced.
bool critical_command_coordinator_acknowledge_publication(const critical_operation_id &operation_id);
size_t critical_command_coordinator_pulse(critical_completion *completions, size_t capacity);
bool critical_command_coordinator_is_fenced(const critical_entity_key &key,
					    critical_operation_id *operation_id);
void critical_command_coordinator_quiesce(void);
void critical_command_coordinator_resume(void);
bool critical_command_coordinator_drain(uint64_t timeout_msec);
void critical_command_coordinator_set_drain_observer(critical_drain_observer_fn observer);
critical_coordinator_health critical_command_coordinator_health_copy(void);
bool critical_command_coordinator_inject_completion_for_tests(const critical_completion &completion);
void critical_command_coordinator_reset_for_tests(void);

#endif
