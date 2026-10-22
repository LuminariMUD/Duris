#include "economy/divine_boon_delivery.h"
#include "economy/divine_boon_runtime.h"
#include "economy/divine_boon_math.h"
#include "combat/combat_outcome_command.h"
#include "combat/combat_outcome_transaction.h"
#include "economy/currency_transaction.h"
#include "guild/artifact_guild_transaction.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/db.h"
#include "world/epic.h"
#include "world/epic_bonus.h"
#include "economy/nexus_stones.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot_capture.h"
#include "persistence/persistence_observability.h"

#include <cassert>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <mutex>

P_room world;
zone_data *zone_table;
char_data player{}, victim{};
pc_only_data pc{}, victim_pc{};
room_data rooms[1] = {};
zone_data zones[1] = {};
int errand_notch = 100;
divine_boon_state state;
double nexus = 0, epic = 0;
float race_modifier = 1;
int effects = 0, hydrations = 0;
int artifact_effects = 0;
bool artifact_available = true;
bool worker_pending = false, command_pending = false;
critical_command submitted;
std::mutex pipeline_mutex;
player_save_pipeline_health health;
struct captured
{
	int64_t epics;
	uint64_t sequence;
	int effects;
	bool task;
};
std::vector<captured> captures;

int IS_MORPH(P_char)
{
	return false;
}
uint64_t persistence_observability_now_usec()
{
	return 0;
}
const divine_boon_state *divine_boon_runtime_state()
{
	return &state;
}
int get_property(const char *, int value)
{
	return value;
}
float get_property(const char *key, double value)
{
	return strstr(key, "epic.gain.modifier.") ? race_modifier : value;
}
float get_epic_bonus(P_char, int)
{
	return epic;
}
double get_epic_bonus_precise(P_char, int)
{
	return epic;
}
int check_nexus_bonus(P_char, int value, int)
{
	return value + static_cast<int>(value * nexus);
}
double check_nexus_bonus_precise(P_char, double value, int)
{
	return value * (1 + nexus);
}
bool trace_player_saves()
{
	return false;
}
bool player_save_worker_pid_pending(int)
{
	return worker_pending;
}
bool critical_command_coordinator_is_fenced(const critical_entity_key &, critical_operation_id *)
{
	return command_pending;
}
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	submitted = std::move(command);
	return critical_submit_result::accepted;
}
bool currency_transaction_submit_wallet_value(P_char, int64_t, currency_reason_type, int64_t,
					      critical_source_site, critical_deadline_class,
					      currency_completion_fn, const void *, size_t)
{
	std::abort(); // These prepared-epic cases contain no wallet award.
}
bool artifact_guild_transaction_submit(P_char ch, const critical_operation_id &operation,
				       int epics, int type)
{
	assert(ch == &player && epics > 0 && type == EPIC_PVP);
	assert(!critical_operation_id_is_zero(operation));
	assert(ch->only.pc->divine_boon_delivery_applying);
	if (!artifact_available)
		return false;
	++artifact_effects;
	return true;
}
void redis_invalidate_fraglist() {}
void critical_outbox_resume() {}
bool player_revision_snapshot_copy(int, player_revision_snapshot *revision)
{
	*revision = {};
	revision->unacknowledged_components = PLAYER_COMPONENT_STATUS | PLAYER_COMPONENT_AFFECTS;
	return true;
}
bool player_revision_queue(int, player_revision_t *revision, player_component_mask_t *components)
{
	*revision = 1;
	*components = PLAYER_COMPONENT_STATUS | PLAYER_COMPONENT_AFFECTS;
	return true;
}
player_snapshot_capture_result player_snapshot_capture(P_char ch, player_revision_t,
						       player_component_mask_t, int, int,
						       player_snapshot *)
{
	captures.push_back({ ch->only.pc->epics, ch->only.pc->divine_boon_delivery_seq, effects,
			     ch->affected != nullptr });
	return player_snapshot_capture_result::ok;
}
player_save_pipeline_result submit_snapshot(player_snapshot)
{
	return player_save_pipeline_result::queued;
}

// CHECKPOINT_BODY
// LOAD_HOLD_BODY

int writeCharacter(P_char ch, int intent, int room)
{
	const auto result = player_save_pipeline_checkpoint_dirty(ch, intent, room);
	return result == player_save_pipeline_result::queued ||
	       result == player_save_pipeline_result::coalesced;
}
P_char find_player_by_pid(int pid)
{
	return pid == 1 ? &player : nullptr;
}
void mark_player_dirty_components(int, player_component_mask_t) {}
void epic_bonus_hydrate(P_char)
{
	++hydrations;
}
affected_type *get_epic_task(P_char ch)
{
	return ch->affected;
}
void affect_remove(P_char ch, affected_type *)
{
	ch->affected = nullptr;
}
void epic_publish_pvp_award(P_char ch, int)
{
	assert(ch->only.pc->divine_boon_delivery_applying);
	const auto before = captures.size();
	assert(writeCharacter(ch, 1,
			      NOWHERE)); // A nested level save must not capture half an award.
	assert(captures.size() == before);
	++effects;
}

// ORDINARY_PVP_MATH
// PREPARED_PVP_MATH

int main()
{
	world = rooms;
	zone_table = zones;
	player.only.pc = &pc;
	victim.only.pc = &victim_pc;
	pc.pid = 1;
	victim_pc.pid = 2;
	player.player.level = victim.player.level = 20;
	player.player.racewar = RACEWAR_GOOD;
	victim.player.racewar = RACEWAR_EVIL;
	health.initialized = true;
	state.mode = divine_boon_mode::divine;
	state.slots[0].id = 7;
	state.slots[0].category = divine_boon_category::pvp;
	state.slots[0].starts_at = 100;
	state.slots[0].expires_at = 200;
	combat_outcome_payload payload = {};
	payload.victim_pid = 2;
	payload.participant_count = 2;
	payload.participants[0].pid = 1;
	payload.participants[0].role = combat_participant_role::killer;
	payload.participants[0].racewar = RACEWAR_GOOD;
	payload.participants[0].flags = COMBAT_PARTICIPANT_IN_ROOM;
	payload.participants[0].frag_delta = 100;
	payload.participants[1].pid = 2;
	payload.participants[1].role = combat_participant_role::victim;
	payload.participants[1].racewar = RACEWAR_EVIL;
	auto &award = payload.participants[0];
	assert(epic_prepare_pvp_award(&player, &victim, 100, 100, 0, 150, &award));
	assert(award.epic_delta == 150 && award.epic_base == 100 && award.epic_boon_id == 7);
	payload.prepared_at = 150;
	critical_operation_id operation = {};
	operation.bytes[0] = 1;
	critical_command command;
	assert(combat_outcome_command_build(&command, operation, payload));
	assert(command.payload_version == 5);
	auto ordinary_payload = payload;
	ordinary_payload.prepared_at = 0;
	ordinary_payload.participants[0].flags = COMBAT_PARTICIPANT_IN_ROOM;
	ordinary_payload.participants[0].epic_boon_id = 0;
	ordinary_payload.participants[0].epic_base = 0;
	critical_command ordinary_command;
	assert(combat_outcome_command_build(&ordinary_command, operation, ordinary_payload));
	assert(ordinary_command.payload_version == 4);
	combat_outcome_payload decoded;
	assert(combat_outcome_command_decode_payload(command, &decoded));
	assert(decoded.participants[0].epic_delta == 150 && decoded.prepared_at == 150);
	state.slots[0].expires_at = 150; // Prepared replay never consults the expired slot.
	assert(combat_outcome_command_decode_payload(command, &decoded));
	state.slots[0].expires_at = 200;
	award.flags |= COMBAT_PARTICIPANT_SPILL_BLOOD;
	assert(epic_prepare_pvp_award(&player, &victim, 100, 100, 500, 150, &award));
	assert(award.epic_delta == 650); // The task's 500 is outside the Divine base.
	nexus = 0.1;
	assert(epic_prepare_pvp_award(&player, &victim, 100, 100, 500, 150, &award));
	assert(award.epic_delta == 710);
	nexus = 0;
	race_modifier = 0.9f;
	assert(epic_prepare_pvp_award(&player, &victim, 100, 100, 500, 150, &award));
	assert(award.epic_delta == 585);
	race_modifier = 1;

	combat_outcome_result outcome = {};
	outcome.event_id = 1;
	outcome.victim_pid = 2;
	outcome.prepared_at = 150;
	outcome.participant_count = 2;
	outcome.participants[1].pid = 2;
	auto &row = outcome.participants[0];
	row.pid = 1;
	row.epic_revision = 5;
	row.epic_delivery_delta = 150;
	row.epic_boon_id = 7;
	row.epic_base = 100;
	row.epic_delivery_flags = COMBAT_PARTICIPANT_DIVINE_EPIC;
	std::array<uint8_t, COMBAT_OUTCOME_RESULT_BYTES> bytes;
	assert(combat_outcome_command_encode_result(outcome, &bytes));
	combat_outcome_result restored;
	assert(combat_outcome_command_decode_result(bytes.data(), bytes.size(), &restored));
	std::array<uint8_t, COMBAT_OUTCOME_LEGACY_RESULT_BYTES> legacy = {};
	legacy[0] = 1;
	legacy[8] = 2;
	legacy[10] = 1;
	legacy[102] = 2;
	combat_outcome_result old_receipt;
	assert(combat_outcome_command_decode_result(legacy.data(), legacy.size(), &old_receipt));
	assert(old_receipt.participant_count == 2 &&
	       !old_receipt.participants[0].epic_delivery_flags);
	divine_epic_delivery first;
	assert(divine_epic_delivery_from_combat(operation, restored, 0, &first));
	auto second = first;
	second.operation_id.bytes[0] = 2;
	second.sequence = 9; // Ordinary revisions may occur between prepared awards.
	second.previous = 5;
	second.amount = 650;
	second.spill_blood = 500;
	pc.epics = 100;
	divine_boon_delivery_player_ready(&player);
	divine_boon_delivery_completed(second);
	assert(pc.epics == 100 && captures.empty());
	affected_type task = {};
	task.modifier = SPILL_BLOOD;
	player.affected = &task;
	divine_boon_delivery_completed(first);
	assert(pc.epics == 900 && pc.divine_boon_delivery_seq == 9 && effects == 2);
	assert(artifact_effects == 2);
	assert(pc.epic_revision == 9); // Publishing does not issue another ledger revision.
	assert(captures.size() == 2 && captures[0].epics == 250 && captures[0].sequence == 5);
	assert(captures[1].epics == 900 && captures[1].sequence == 9 && !captures[1].task);
	divine_boon_delivery_completed(first);
	divine_boon_delivery_completed(second);
	assert(pc.epics == 900 && effects == 2 && hydrations == 0 && artifact_effects == 2);

	// Restart from the first saved checkpoint and recover only the unpaid receipt.
	pc.epics = 250;
	pc.divine_boon_delivery_seq = 5;
	pc.divine_boon_delivery_ready = false;
	captures.clear();
	assert(divine_boon_delivery_recover(&player, { first, second }));
	assert(pc.epics == 900 && pc.divine_boon_delivery_seq == 9 && captures.empty());
	assert(artifact_effects == 3); // Offline receipt still grants the artifact effect.
	divine_boon_delivery_player_ready(&player);
	assert(writeCharacter(&player, 1, NOWHERE));
	assert(captures.size() == 1 && captures[0].epics == 900 && captures[0].sequence == 9);
	pc.epics = 100;
	pc.divine_boon_delivery_seq = 0;
	pc.divine_boon_delivery_ready = false;
	auto missing = second;
	missing.previous = 7;
	assert(!divine_boon_delivery_recover(&player, { first, missing }));
	assert(pc.epics == 100 && pc.divine_boon_delivery_seq == 0); // Validate before publication.
	assert(!player_save_pipeline_load_held(1));
	command_pending = true;
	assert(player_save_pipeline_load_held(1));
	command_pending = false;
	worker_pending = true;
	assert(player_save_pipeline_load_held(1));
	assert(!player_save_pipeline_load_held(0));

	// The real outcome submitter defers this epic delta until a committed result.
	combat_outcome_transaction_reset_for_tests();
	pc.epics = 100;
	pc.epic_revision = pc.divine_boon_delivery_seq = 0;
	pc.divine_boon_delivery_ready = true;
	payload.participants[0].flags = COMBAT_PARTICIPANT_IN_ROOM | COMBAT_PARTICIPANT_DIVINE_EPIC;
	payload.participants[0].epic_delta = 150;
	payload.participants[0].epic_boon_id = 7;
	payload.participants[0].epic_base = 100;
	payload.participants[0].epic_spill_blood = 0;
	critical_operation_id admitted;
	// A rejected parent never publishes epic or artifact rewards.
	critical_operation_id rejected;
	assert(combat_outcome_transaction_submit(payload, nullptr, &rejected));
	critical_completion failure = {};
	failure.operation_id = rejected;
	failure.outcome = critical_apply_outcome::terminal_failure;
	failure.error_code = ENOENT;
	const int artifacts_before_rejection = artifact_effects;
	combat_outcome_transaction_handle_completions(&failure, 1);
	assert(pc.epics == 100 && artifact_effects == artifacts_before_rejection);
	assert(combat_outcome_transaction_submit(payload, nullptr, &admitted));
	assert(pc.epics == 100 && pc.divine_boon_delivery_seq == 0);
	outcome.participants[0].epic_revision = 1;
	assert(combat_outcome_command_encode_result(outcome, &bytes));
	critical_completion completion = {};
	completion.operation_id = admitted;
	completion.outcome = critical_apply_outcome::applied;
	completion.result_size = bytes.size();
	std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
	combat_outcome_transaction_handle_completions(&completion, 1);
	assert(pc.epics == 250 && pc.divine_boon_delivery_seq == 1);
	assert(artifact_effects == artifacts_before_rejection + 1);
	combat_outcome_transaction_handle_completions(&completion, 1);
	assert(pc.epics == 250 && artifact_effects == artifacts_before_rejection + 1);
	artifact_available = false;
	auto third = second;
	third.operation_id.bytes[0] = 42;
	third.sequence = 10;
	third.previous = 1;
	third.amount = 100;
	pc.divine_boon_delivery_seq = 1;
	divine_boon_delivery_completed(third);
	assert(pc.epics == 350 && pc.divine_boon_delivery_seq == 10 &&
	       artifact_effects == artifacts_before_rejection + 1);
	artifact_available = true;
	std::cout
		<< "Prepared PvP math, parent codec, ordered publication and checkpoint recovery passed\n";
}
