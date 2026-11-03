#ifndef STARTER_KIT_INTENT_H
#define STARTER_KIT_INTENT_H

#include "persistence/critical_command.h"
#include <string>

enum class starter_kit_state
{
	absent,
	pending,
	committed,
	rejected,
	invalid
};

// The complete first grant, including its operation ID and item UIDs, survives
// process loss. Completed records remain evidence even after items are consumed.
bool starter_kit_intent_init(const char *parent);
starter_kit_state starter_kit_intent_read(uint32_t pid, critical_command *command);
starter_kit_state starter_kit_intent_read(const std::string &directory, uint32_t pid,
					  critical_command *command);
bool starter_kit_intent_bind(uint32_t pid, const critical_command &command);
bool starter_kit_intent_finish(uint32_t pid, const critical_command &command, bool committed);
void starter_kit_intent_shutdown();

#endif
