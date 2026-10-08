/****************************************************************************
 *
 *  File: artifact_mana_store.h                                 Part of Duris
 *  Usage: artifact mana store interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_ARTIFACT_MANA_STORE_H
#define DURIS_ARTIFACT_MANA_STORE_H

#include "item/artifact_mana_model.h"

#include <string>

enum class artifact_mana_read
{
	found,
	missing,
	error
};

// Worker-only I/O. SQL is authoritative whenever mysql is required; failures
// never silently switch to a second authority. Flat-file root is captured at boot.
artifact_mana_read artifact_mana_store_read(bool sql, const std::string &root, uint64_t uid,
					    artifact_mana_record &);
// Compare-and-swap and exact retry recognition; stale snapshots cannot overwrite
// a newer debit. expected_version == 0 creates an empty, previously unseen UID.
bool artifact_mana_store_write(bool sql, const std::string &root, uint64_t expected_version,
			       const artifact_mana_record &);

#endif
