/****************************************************************************
 *
 *  File: flatfile_collector_repository.h                       Part of Duris
 *  Usage: flat-file collector repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_COLLECTOR_REPOSITORY_H
#define DURIS_FLATFILE_COLLECTOR_REPOSITORY_H

#include "economy/collector_command.h"
#include "economy/collector_custody_boundary.h"
#include "economy/collector_storage.h"
#include "flatfile/flatfile_authority_transaction.h"
#include "persistence/critical_command_coordinator.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

enum class flatfile_collector_repository_result
{
	ok,
	not_found,
	unchanged,
	conflict,
	invalid,
	io_error,
};

struct flatfile_collector_enrollment_mutation
{
	flatfile_authority_after_image after_image;
	uint64_t catalog_revision = 0;
	size_t cancelled = 0;
};

flatfile_collector_repository_result flatfile_collector_repository_read_bootstrap(
	const std::string &root, collector_bootstrap_snapshot *snapshot, std::string *error);
flatfile_collector_repository_result
flatfile_collector_repository_read_listing(const std::string &root, uint64_t listing,
					   collector_listing_detail *detail, bool *found,
					   std::string *error);

// Records a player's death and its eligible corpse items as collector candidates. Called
// by the corpse save under the shared authority lock; the returned catalog image is
// committed with the corpse's. A later save of the same corpse adds only items not yet
// listed.
flatfile_collector_repository_result flatfile_collector_prepare_death_enrollment(
	const std::string &root, const flatfile_authority_lock &lock,
	const collector_death_snapshot &death, const std::vector<uint64_t> &item_uids,
	flatfile_collector_enrollment_mutation *mutation, unsigned int *result_code,
	std::string *error);

// Compose candidate cancellation (including every captured container child) into one
// collector after-image. The item repository commits this image with custody and all
// other domain images.
flatfile_collector_repository_result flatfile_collector_prepare_item_boundary(
	const std::string &root, const flatfile_authority_lock &lock,
	const item_transfer_payload &payload, const item_transfer_result &transfer,
	flatfile_collector_enrollment_mutation *mutation, unsigned int *result_code,
	std::string *error);

critical_apply_result flatfile_collector_repository_apply(const std::string &root,
							  const critical_command &command);

#endif
