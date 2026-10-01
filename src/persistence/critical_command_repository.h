#ifndef CRITICAL_COMMAND_REPOSITORY_H
#define CRITICAL_COMMAND_REPOSITORY_H

#include "persistence/critical_command_coordinator.h"

#include <mysql/mysql.h>

struct item_transfer_result;

constexpr size_t CRITICAL_COMMAND_RESULT_MAX_BYTES = 4096;
static_assert(CRITICAL_COMMAND_RESULT_MAX_BYTES <= CRITICAL_COMPLETION_RESULT_MAX_BYTES);
constexpr size_t CRITICAL_OUTBOX_PAYLOAD_MAX_BYTES = 65535;

critical_apply_result critical_command_repository_apply(MYSQL *connection,
							const critical_command &command);
critical_apply_result critical_command_repository_reconcile(MYSQL *connection,
							    const critical_command &command);
critical_apply_result critical_command_repository_apply_from_pool(const critical_command &command,
								  void *context);

// Transaction-scoped support for compound administrative item operations. The
// caller owns START/COMMIT/ROLLBACK; these preserve the normal inbox and outbox
// audit contract around a nested item-transfer repository call.
bool critical_command_repository_begin_inbox_in_transaction(MYSQL *connection,
							    const critical_command &command);
bool critical_command_repository_finish_item_transfer_in_transaction(
	MYSQL *connection, const critical_command &command, const item_transfer_result &result);

#endif
