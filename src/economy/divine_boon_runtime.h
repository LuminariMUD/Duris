#ifndef DIVINE_BOON_RUNTIME_H
#define DIVINE_BOON_RUNTIME_H

#include "economy/divine_boon.h"

// Game-thread memory owns gameplay decisions. Boot restores durable state;
// the existing writer persists prepared mutations before memory publishes them.
bool divine_boon_runtime_boot(int64_t now);
void divine_boon_runtime_pulse();
const divine_boon_state *divine_boon_runtime_state();
bool divine_boon_runtime_pending();
// Close new legacy work as soon as draining is queued, before its commit.
// Accepted completion/delivery handlers must remain free to finish afterward.
bool divine_boon_legacy_admissions_allowed();
// The caller prepares a next state with the core policy and verifies target
// safety and legacy settlement before requesting the corresponding transition.
bool divine_boon_runtime_queue(const divine_boon_state &next);

// Emit only after durable publication on the game thread; never for boot replay.
void divine_boon_announce_changes(const std::array<divine_boon_slot, DIVINE_BOON_SLOTS> &previous,
				  const std::array<divine_boon_slot, DIVINE_BOON_SLOTS> &current,
				  int64_t now);

#endif
