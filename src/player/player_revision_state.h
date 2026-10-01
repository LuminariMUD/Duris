#ifndef PLAYER_REVISION_STATE_H
#define PLAYER_REVISION_STATE_H

#include <stddef.h>
#include <stdint.h>

typedef uint64_t player_revision_t;
typedef uint64_t player_component_mask_t;

enum player_checkpoint_component : player_component_mask_t
{
	PLAYER_COMPONENT_STATUS = UINT64_C(1) << 0,
	PLAYER_COMPONENT_LANGUAGES = UINT64_C(1) << 1,
	PLAYER_COMPONENT_INTRODUCTIONS = UINT64_C(1) << 2,
	PLAYER_COMPONENT_TIMERS = UINT64_C(1) << 3,
	PLAYER_COMPONENT_UNDEAD_SLOTS = UINT64_C(1) << 4,
	PLAYER_COMPONENT_FORGED_ITEMS = UINT64_C(1) << 5,
	PLAYER_COMPONENT_GRANTED_COMMANDS = UINT64_C(1) << 6,
	PLAYER_COMPONENT_SKILLS = UINT64_C(1) << 7,
	PLAYER_COMPONENT_AFFECTS = UINT64_C(1) << 8,
	PLAYER_COMPONENT_EQUIPMENT = UINT64_C(1) << 9,
	PLAYER_COMPONENT_INVENTORY = UINT64_C(1) << 10,
	PLAYER_COMPONENT_PETS = UINT64_C(1) << 11,
	PLAYER_COMPONENT_SHAPECHANGES = UINT64_C(1) << 12,
	PLAYER_COMPONENT_TROPHIES = UINT64_C(1) << 13,
};

constexpr player_component_mask_t PLAYER_CHECKPOINT_COMPONENT_ALL =
	(PLAYER_COMPONENT_TROPHIES << 1) - 1;

struct player_revision_snapshot
{
	int pid;
	player_revision_t current_revision;
	player_revision_t acknowledged_revision;
	// The newest revision the writer has written. acknowledged_revision moves when the
	// writer accepts a save; this one when the save has landed.
	player_revision_t written_revision;
	player_component_mask_t unacknowledged_components;
	bool overflowed;
};

bool player_revision_hydrate(int pid, player_revision_t durable_revision);
bool player_revision_mark(int pid, player_component_mask_t components,
			  player_revision_t *revision_out);
// The revision and components a save captures now: everything not yet acknowledged.
bool player_revision_queue(int pid, player_revision_t *revision_out,
			   player_component_mask_t *components_out);
bool player_revision_acknowledge_durable(int pid, player_revision_t revision,
					 player_component_mask_t components);
bool player_revision_record_written(int pid, player_revision_t revision);
bool player_revision_snapshot_copy(int pid, struct player_revision_snapshot *snapshot_out);
void player_revision_forget(int pid);
void player_revision_reset_for_tests(void);
size_t player_revision_state_count(void);
size_t player_revision_dirty_count(void);

#endif
