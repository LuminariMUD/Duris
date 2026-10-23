#ifndef DIVINE_BOON_DELIVERY_H
#define DIVINE_BOON_DELIVERY_H

#include "persistence/critical_command.h"

#include <vector>

struct char_data;
struct combat_outcome_result;

// A committed PvP parent receipt identifies the complete prepared epic award.
// Sequence is its issued epic revision; previous links only prepared deliveries,
// so ordinary ledger revisions may occur between them without creating a gap.
struct divine_epic_delivery
{
	critical_operation_id operation_id = {};
	uint32_t pid = 0;
	uint32_t victim_pid = 0;
	uint64_t sequence = 0;
	uint64_t previous = 0;
	uint64_t boon_id = 0;
	int64_t amount = 0;
	int64_t prepared_at = 0;
	double base = 0;
	int32_t spill_blood = 0;
};

constexpr size_t DIVINE_EPIC_RECOVERY_MAX = 512;

bool divine_epic_delivery_valid(const divine_epic_delivery &delivery);
bool divine_epic_delivery_from_combat(const critical_operation_id &operation,
				      const combat_outcome_result &result, size_t index,
				      divine_epic_delivery *delivery);
// Game-thread publication and login recovery use the same ordered checkpoint.
void divine_boon_delivery_completed(const divine_epic_delivery &delivery);
bool divine_boon_delivery_recover(char_data *character,
				  const std::vector<divine_epic_delivery> &deliveries);
void divine_boon_delivery_player_ready(char_data *character);

#endif
