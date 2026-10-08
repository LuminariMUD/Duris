/****************************************************************************
 *
 *  File: flatfile_account_adapter.h                            Part of Duris
 *  Usage: flat-file account state adapter interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_ACCOUNT_ADAPTER_H
#define DURIS_FLATFILE_ACCOUNT_ADAPTER_H

#include "account/account.h"

#include <string>

P_acct flatfile_account_state_load(const char *name, std::string *error);
void flatfile_account_state_release(P_acct account);
bool flatfile_account_state_save(P_acct account, std::string *error);
bool flatfile_account_state_exists(const char *name, bool *exists, std::string *error);

#endif
