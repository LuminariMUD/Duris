#ifndef DIVINE_BOON_RUNTIME_H
#define DIVINE_BOON_RUNTIME_H

#include "economy/divine_boon.h"

// Game-thread API. Boot reads authority before gameplay; mutations run on the
// existing writer. No state is published before its durable confirmation.
bool divine_boon_runtime_boot(int64_t now);
void divine_boon_runtime_pulse();
const divine_boon_state *divine_boon_runtime_state();
bool divine_boon_runtime_pending();
// The caller prepares a next state with the core policy and verifies target
// safety and legacy settlement before requesting the corresponding transition.
bool divine_boon_runtime_queue(const divine_boon_state &next);

#endif
