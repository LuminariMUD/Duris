/****************************************************************************
 *
 *  File: flatfile_artifact_repository.h                        Part of Duris
 *  Usage: flat-file artifact repository types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_ARTIFACT_REPOSITORY_H
#define DURIS_FLATFILE_ARTIFACT_REPOSITORY_H

#include "flatfile/flatfile_authority_transaction.h"
#include "guild/artifact_identity.h"
#include "item/item_transfer_command.h"
#include "player/player_snapshot.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

constexpr int32_t FLATFILE_ARTIFACT_NOT_IN_GAME = 1;
constexpr int32_t FLATFILE_ARTIFACT_ON_NPC = 2;
constexpr int32_t FLATFILE_ARTIFACT_ON_PLAYER = 3;
constexpr int32_t FLATFILE_ARTIFACT_ON_GROUND = 4;
constexpr int32_t FLATFILE_ARTIFACT_ON_CORPSE = 5;

struct flatfile_artifact_record
{
	int32_t vnum = 0;
	bool owned = false;
	int32_t location_type = FLATFILE_ARTIFACT_NOT_IN_GAME;
	int32_t location = 0;
	int64_t timer = 0;
	int32_t type = 0;
	int64_t last_update = 0;
	int32_t bind_owner_pid = -1;
	int64_t bind_timer = 0;
	uint64_t revision = 0;
	uint64_t canonical_item_uid = 0;
	artifact_identity_state identity_state = artifact_identity_state::unresolved;
	bool operator==(const flatfile_artifact_record &) const = default;
};

enum class flatfile_artifact_result
{
	ok,
	not_found,
	already_exists,
	unchanged,
	conflict,
	invalid,
	io_error
};

flatfile_artifact_result
flatfile_artifact_establish(const std::string &root,
			    const std::vector<flatfile_artifact_record> &records,
			    std::string *error);
flatfile_artifact_result flatfile_artifact_ensure(const std::string &root, std::string *error);
flatfile_artifact_result flatfile_artifact_list(const std::string &root,
						std::vector<flatfile_artifact_record> *records,
						std::string *error);
flatfile_artifact_result flatfile_artifact_get(const std::string &root, int32_t vnum,
					       flatfile_artifact_record *record,
					       std::string *error);
// One writer capture, applied atomically to the catalog. Record revisions are
// assigned by the repository; unchanged captures do not advance them.
flatfile_artifact_result
flatfile_artifact_snapshot_apply(const std::string &root,
				 const std::vector<flatfile_artifact_record> &records,
				 std::string *error);
flatfile_artifact_result flatfile_artifact_prepare_player_release(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	flatfile_authority_operation *operation, std::string *error);
// A grant cannot create an artifact in a room; an operator repair within a room leaves the
// artifact catalog as it is.
bool flatfile_artifact_room_transfer_allowed(const item_transfer_payload &payload);

#endif
