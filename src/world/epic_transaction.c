#include "world/epic_transaction.h"

#include "world/epic.h"
#include "persistence/persistence_checkpoint.h"
#include "core/prototypes.h"
#include "core/utils.h"

#include <cerrno>
#include <limits>
#include <utility>

namespace
{
epic_transaction_health health = {};
} // namespace

// Epic points live in memory. A transaction changes the balance at once and calls its
// completion before returning: committed, or refused with ENOSPC when a purchase needs
// more than the balance (ERANGE on overflow); the submit still returns true. The player's
// save writes the balance. The command still goes to the one writer, where it only adds a
// row to the epic ledger that zone trophies and the epic bonus read.
bool epic_transaction_submit_identified(P_char character, const critical_operation_id &operation_id,
					int64_t delta, epic_reason_type reason, int64_t reason_id,
					uint16_t flags, critical_source_site source_site,
					critical_deadline_class deadline_class,
					epic_completion_fn completion, const void *context,
					size_t context_size)
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0 || !delta ||
	    context_size > EPIC_PENDING_CONTEXT_MAX_BYTES || (context_size && !context) ||
	    critical_operation_id_is_zero(operation_id))
		return false;
	critical_command command = {};
	if (!epic_command_build(&command, operation_id,
				{ .pid = static_cast<uint32_t>(GET_PID(character)),
				  .delta = delta,
				  .reason = reason,
				  .flags = flags,
				  .reason_id = reason_id },
				UINT64_MAX, source_site, deadline_class))
		return false;
	++health.submitted;
	const uint8_t *bytes = static_cast<const uint8_t *>(context);
	auto &balance = character->only.pc->epics;
	unsigned int refused = 0;
	if (delta < 0 && (flags & EPIC_COMMAND_REQUIRE_FUNDS) && balance < -delta)
		refused = ENOSPC;
	else if ((delta > 0 && balance > std::numeric_limits<int64_t>::max() - delta) ||
		 (delta < 0 && balance < std::numeric_limits<int64_t>::min() - delta))
		refused = ERANGE;
	if (refused)
	{
		++health.rejected;
		if (completion)
			completion(character, false,
				   { balance, character->only.pc->epic_revision, delta }, refused,
				   bytes, context_size);
		return true;
	}
	balance += delta;
	const epic_command_result result = { balance, ++character->only.pc->epic_revision, delta };
	mark_player_dirty_components(GET_PID(character), PLAYER_COMPONENT_STATUS);
	++health.committed;
	if (completion)
		completion(character, true, result, 0, bytes, context_size);
	if (!critical_submit_result_keeps_operation(
		    critical_command_coordinator_submit(std::move(command))))
	{
		++health.submission_failures;
		logit(LOG_DEBUG, "epic_transaction: ledger row not queued for pid %d",
		      GET_PID(character));
	}
	return true;
}

bool epic_transaction_submit(P_char character, int64_t delta, epic_reason_type reason,
			     int64_t reason_id, uint16_t flags, critical_source_site source_site,
			     critical_deadline_class deadline_class, epic_completion_fn completion,
			     const void *context, size_t context_size)
{
	critical_operation_id operation_id = {};
	return critical_operation_id_generate(&operation_id) &&
	       epic_transaction_submit_identified(character, operation_id, delta, reason, reason_id,
						  flags, source_site, deadline_class, completion,
						  context, context_size);
}

epic_transaction_health epic_transaction_health_copy(void)
{
	return health;
}

void epic_transaction_reset_for_tests(void)
{
	health = {};
}
