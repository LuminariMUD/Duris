/****************************************************************************
 *
 *  File: session_audit_transaction.h                           Part of Duris
 *  Usage: session audit transaction interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef SESSION_AUDIT_TRANSACTION_H
#define SESSION_AUDIT_TRANSACTION_H

#include "account/session_audit_command.h"
#include "core/structs.h"

bool session_audit_transaction_submit(P_char character, session_audit_event event);

#endif
