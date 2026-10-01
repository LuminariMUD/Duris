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
	bool initialized;
	bool accepting;
};

bool player_save_pipeline_init(void);
void player_save_pipeline_shutdown(void);
bool player_save_pipeline_mark(int pid, player_component_mask_t components);
player_save_pipeline_result player_save_pipeline_checkpoint_dirty(P_char ch, int save_intent,
								  int room_vnum);
player_save_pipeline_result player_save_pipeline_request(P_char ch,
							 player_component_mask_t components,
							 int save_intent, int room_vnum);
player_save_terminal_result player_save_pipeline_terminal(P_char ch, int save_intent, int room_vnum,
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
// A load of this character waits while its save is queued.
bool player_save_pipeline_load_held(int pid);
void player_save_pipeline_reset_for_tests(void);

#endif
