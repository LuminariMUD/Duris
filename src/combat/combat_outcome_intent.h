#ifndef COMBAT_OUTCOME_INTENT_H
#define COMBAT_OUTCOME_INTENT_H

#include "persistence/critical_command.h"
#include <string>

constexpr size_t COMBAT_OUTCOME_INTENT_MAX = 128;

// One private, exclusively locked directory per game authority. Initialization
// validates every retained command before any may be replayed.
bool combat_outcome_intent_init(const char *parent, std::vector<critical_command> *retained);
void combat_outcome_intent_shutdown();
bool combat_outcome_intent_write(const critical_command &command);
// Validate pending or completed evidence without replaying or changing it.
bool combat_outcome_intent_read(const std::string &directory, const std::string &name,
				critical_command *command);
// Retain the complete command for reward reconciliation; only active intents replay.
bool combat_outcome_intent_complete(const critical_operation_id &operation);

#endif
