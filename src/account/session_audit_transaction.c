/****************************************************************************
 *
 *  File: session_audit_transaction.c                           Part of Duris
 *  Usage: submits session audit records to the writer
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "account/session_audit_transaction.h"

#include "persistence/critical_command_coordinator.h"
#include "core/prototypes.h"
#include "core/utils.h"

#include <ctime>

bool session_audit_transaction_submit(P_char character, session_audit_event event)
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0)
		return false;
	critical_operation_id operation_id = {};
	critical_command command = {};
	const session_audit_payload payload = { static_cast<uint32_t>(GET_PID(character)), event,
						time(nullptr) };
	if (!critical_operation_id_generate(&operation_id) ||
	    !session_audit_command_build(&command, operation_id, payload))
		return false;
	const critical_submit_result submitted =
		critical_command_coordinator_submit(std::move(command));
	return critical_submit_result_keeps_operation(submitted);
}
