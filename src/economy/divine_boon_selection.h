#ifndef DIVINE_BOON_SELECTION_H
#define DIVINE_BOON_SELECTION_H

#include "economy/divine_boon.h"
#include "economy/divine_boon_activity.h"

// Process-local staff-only snapshot; never persisted or exposed to players.
struct divine_boon_selection_diagnostic
{
	int64_t hour = 0;
	uint64_t committed_revision = 0;
	std::array<divine_boon_population, 2> population = {};
	std::array<unsigned, 2> experience_candidates = {};
	std::array<unsigned, 2> epic_candidates = {};
	unsigned cargo_routes = 0;
	bool pvp_eligible = false;
	bool sampled = false;
	const char *reason = "unavailable";
	divine_boon_category selected = divine_boon_category::none;
};

// Uses the existing boot mobile profiles and actual reset locations. Unknown
// content stays outside the reviewed pool. No item rewards or quest level gate.
bool divine_boon_selection_bootstrap();
bool divine_boon_select(const divine_boon_state &state, int64_t now,
			const std::array<divine_boon_population, 2> &population,
			divine_boon_slot *choice,
			divine_boon_selection_diagnostic *diagnostic = nullptr);
// Rechecks runtime flags and the proved ordinary path for display/admission.
bool divine_boon_zone_eligible(int zone_number, unsigned side);
// Bounded reward lookup; the game-thread tick refreshes paths once per second.
bool divine_boon_reward_zone_eligible(int zone_number, unsigned side);
bool divine_boon_epic_zone_eligible(int zone_number, unsigned side);
bool divine_boon_cargo_eligible(const divine_boon_slot &slot);
struct char_data;
void divine_boon_selection_status(char_data *ch);
// Game-thread tick: choose once per fixed hour, then use the existing writer.
void divine_boon_selection_pulse(int64_t now);

#endif
