#ifndef PLAYER_SAVE_PIPELINE_H
#define PLAYER_SAVE_PIPELINE_H

#include "player/player_revision_state.h"
#include "player/player_save_worker.h"
#include "persistence/critical_command.h"

#include <cstddef>
#include <cstdint>
#include <vector>

struct char_data;
typedef struct char_data *P_char;
struct obj_data;
typedef struct obj_data *P_obj;

constexpr size_t PLAYER_SAVE_PIPELINE_MAX_SNAPSHOTS = 256;
constexpr size_t PLAYER_SAVE_PIPELINE_PULSE_BUDGET = 64;

enum class player_save_pipeline_result : uint8_t
{
	queued,
	coalesced,
	unchanged,
	invalid,
	capture_failed,
	unavailable,
};

enum class player_save_terminal_result : uint8_t
{
	database_acknowledged,
	invalid,
	unavailable,
	timed_out,
};

struct player_save_pipeline_health
{
	uint64_t marked;
	uint64_t captured;
	uint64_t coalesced;
	uint64_t unchanged;
	uint64_t capture_failures;
	uint64_t submit_failures;
	uint64_t completions;
	uint64_t write_failures;
	uint64_t terminal_fences;
	uint64_t terminal_database_acks;
	uint64_t terminal_timeouts;
	uint64_t drain_failures;
	uint64_t legacy_journal_replayed;
	bool legacy_journal_retired;
	bool initialized;
	bool accepting;
};

// A leftover player-save journal from an older server is replayed once, then
// retired. legacy_journal_directory may be null; nothing new is journaled.
bool player_save_pipeline_init(const char *legacy_journal_directory);
void player_save_pipeline_shutdown(void);
bool player_save_pipeline_mark(int pid, player_component_mask_t components);
player_save_pipeline_result player_save_pipeline_checkpoint_dirty(P_char ch, int save_intent,
								  int room_vnum);
player_save_pipeline_result player_save_pipeline_request(P_char ch,
							 player_component_mask_t components,
							 int save_intent, int room_vnum);
player_save_terminal_result player_save_pipeline_terminal(P_char ch, int save_intent, int room_vnum,
							  uint64_t timeout_msec);
// Capture the immutable death disposition for ch and wait for it to become
// durable. wallet_pile may be null; when the wallet still holds coins it must be
// an unattached pile carrying the complete remaining wallet.
player_save_terminal_result
player_save_pipeline_terminal_death(P_char ch, P_obj corpse, P_obj wallet_pile,
				    const critical_operation_id &operation_id, int room_vnum,
				    uint64_t timeout_msec);
void player_save_pipeline_pulse(void);
void player_save_pipeline_quiesce(void);
void player_save_pipeline_resume(void);
// Stop taking new saves and wait for the writer to write everything queued.
bool player_save_pipeline_drain(uint64_t timeout_msec);
// Shutdown, once nothing queues a write any more: the writer gets until deadline_usec
// (persistence_observability_now_usec() time) for what is queued, then stops. A job
// still being written then is cut short through `interrupt`. Returns every owner left
// unwritten, and shuts the pipeline down.
std::vector<persistence_job_owner> player_save_pipeline_finish(uint64_t deadline_usec,
							       void (*interrupt)(void));
player_save_pipeline_health player_save_pipeline_health_copy(void);
size_t player_save_pipeline_dirty_count(void);
bool player_save_pipeline_is_nonterminal_type(int save_intent);
// Exact-PID save/login barrier used by offline critical commands.  A target
// fence rejects new saves for that PID without quiescing unrelated players.
bool player_save_pipeline_target_save_pending(int pid);
bool player_save_pipeline_acquire_target_save_login_fence(int pid,
							  player_revision_t expected_revision);
void player_save_pipeline_release_target_save_login_fence(int pid,
							  player_revision_t expected_revision);
bool player_save_pipeline_target_save_login_fenced(int pid);
bool player_save_pipeline_save_admitted(int pid);
// A load of this character waits: its save is queued or a staff fence holds it.
bool player_save_pipeline_load_held(int pid);
void player_save_pipeline_reset_for_tests(void);

#endif
