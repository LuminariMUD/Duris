#ifndef DIVINE_BOON_SELECTION_H
#define DIVINE_BOON_SELECTION_H

#include "economy/divine_boon.h"
#include "economy/divine_boon_activity.h"

// Uses the existing boot mobile profiles and actual reset locations. Unknown
// content stays outside the reviewed pool. No item rewards or quest level gate.
bool divine_boon_selection_bootstrap();
bool divine_boon_select(const divine_boon_state &state, int64_t now,
			const std::array<divine_boon_population, 2> &population,
			divine_boon_slot *choice);
// Rechecks runtime flags and the proved ordinary path for display/admission.
bool divine_boon_zone_eligible(int zone_number, unsigned side);
// Game-thread tick: choose once per fixed hour, then use the existing writer.
void divine_boon_selection_pulse(int64_t now);

#endif
