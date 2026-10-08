/****************************************************************************
 *
 *  File: collector_expiry_preparation.h                        Part of Duris
 *  Usage: collector expiry preparation interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_COLLECTOR_EXPIRY_PREPARATION_H
#define DURIS_COLLECTOR_EXPIRY_PREPARATION_H

#include "economy/collector_command.h"
#include "economy/collector_storage.h"

#include <cstdint>
#include <memory>

enum class collector_expiry_prepare_outcome : uint8_t
{
	prepared,
	invalid_request,
	stale_listing,
	not_due,
	invalid_item,
	stale_custody,
	allocation_failure,
};

// Turns an immutable listing read plus the game-thread custody projection into
// a fully fenced destruction command. A rejected preparation leaves payload
// unchanged.
collector_expiry_prepare_outcome collector_expiry_prepare(
	const collector::record &runtime_entry, const collector_listing_detail &detail,
	const item_ownership_runtime_entry &held_item, uint64_t destruction_owner_revision,
	uint64_t observed_at, std::unique_ptr<collector_command_payload> *payload);

#endif
