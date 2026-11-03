/****************************************************************************
 *
 *  File: flatfile_shop_trade_repository.h                      Part of Duris
 *  Usage: flat-file shop trade repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_SHOP_TRADE_REPOSITORY_H
#define DURIS_FLATFILE_SHOP_TRADE_REPOSITORY_H

#include "persistence/critical_command_coordinator.h"
#include "flatfile/flatfile_player_domain_repository.h"

#include <string>

critical_apply_result flatfile_shop_trade_repository_apply(const std::string &root,
							   const critical_command &command);

// Read-only validation of the complete replay catalog, including lazy entries.
bool flatfile_shop_trade_repository_validate(const std::string &root, std::string *error);
// Caller holds authority; settle a pre-publication save from the exact receipt.
// not_found means this is not a retained shop operation.
flatfile_player_domain_result
flatfile_shop_trade_settle_snapshot(const std::string &root, const flatfile_authority_lock &lock,
				    player_snapshot *snapshot, std::string *error);

#endif
