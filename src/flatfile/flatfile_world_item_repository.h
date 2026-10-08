/****************************************************************************
 *
 *  File: flatfile_world_item_repository.h                      Part of Duris
 *  Usage: flat-file world item repository types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_WORLD_ITEM_REPOSITORY_H
#define DURIS_FLATFILE_WORLD_ITEM_REPOSITORY_H

#include "flatfile/flatfile_authority_transaction.h"
#include "item/item_transfer_command.h"
#include "player/player_snapshot.h"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

struct flatfile_corpse_record
{
	uint32_t owner_pid = 0;
	std::string owner_name;
	uint32_t save_id = 0;
	int32_t room_vnum = 0;
	std::string short_description;
	std::string description;
	std::string keywords;
	int32_t weight = 0;
	std::array<int32_t, 8> values = {};
	std::array<int32_t, 4> money = {};
	uint64_t revision = 0;
	std::vector<player_item_snapshot> items;
};

struct flatfile_saved_world_item_record
{
	std::string item_key;
	int32_t room_vnum = 0;
	uint64_t revision = 0;
	std::vector<player_item_snapshot> items;
};

struct flatfile_room_item_record
{
	int32_t room_vnum = 0;
	uint64_t revision = 0;
	std::array<int32_t, 4> money = {};
	std::vector<player_item_snapshot> items;
};

struct flatfile_corpse_custody_item
{
	uint64_t item_uid = 0;
	int32_t vnum = 0;
	uint64_t root_item_uid = 0;
	uint64_t parent_item_uid = 0;
};

struct flatfile_corpse_custody_owner
{
	item_owner_identity owner = { item_owner_type::unknown, 0, 0 };
	std::vector<flatfile_corpse_custody_item> items;
};

struct flatfile_world_item_player_removal
{
	flatfile_authority_operation operation;
	std::vector<flatfile_corpse_custody_owner> custody;
};

struct flatfile_room_transfer_mutation
{
	flatfile_authority_after_image after_image;
	std::vector<flatfile_corpse_custody_item> expected_items;
	uint64_t room_revision = 0;
	bool created = false;
};

struct collector_command_payload;
struct flatfile_collector_world_mutation
{
	flatfile_authority_after_image after_image;
	bool changed = false;
};

enum class flatfile_world_item_result
{
	ok,
	not_found,
	already_exists,
	unchanged,
	conflict,
	not_empty,
	invalid,
	io_error
};

flatfile_world_item_result flatfile_world_item_establish(
	const std::string &root, const std::vector<flatfile_corpse_record> &corpses,
	const std::vector<flatfile_saved_world_item_record> &saved_items, std::string *error);
flatfile_world_item_result
flatfile_world_item_list(const std::string &root, std::vector<flatfile_corpse_record> *corpses,
			 std::vector<flatfile_saved_world_item_record> *saved_items,
			 std::string *error);
flatfile_world_item_result
flatfile_world_item_list_rooms(const std::string &root,
			       std::vector<flatfile_room_item_record> *rooms, std::string *error);
flatfile_world_item_result flatfile_world_item_prepare_player_remove(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	const std::string &expected_name, flatfile_world_item_player_removal *removal,
	std::string *error);
flatfile_world_item_result flatfile_world_item_prepare_room_transfer(
	const std::string &root, const flatfile_authority_lock &lock,
	const item_transfer_payload &payload, flatfile_room_transfer_mutation *mutation,
	std::string *error);
flatfile_world_item_result flatfile_world_item_prepare_collector_transfer(
	const std::string &root, const flatfile_authority_lock &lock,
	const collector_command_payload &payload, flatfile_collector_world_mutation *mutation,
	unsigned int *result_code, std::string *error);
// Write a player corpse as memory holds it, or remove it (the persistence reset's
// corpse save). Its items leave any other record that still lists them: the last save
// to claim an item wins.
flatfile_world_item_result flatfile_world_item_prepare_corpse_snapshot(
	const std::string &root, const flatfile_authority_lock &lock,
	const flatfile_corpse_record &corpse, bool remove, flatfile_authority_operation *operation,
	std::string *error);
// A saved room item lives in its room's record, which is what a boot restores: the
// item's graph leaves every record, and unless `remove` joins the room's.
flatfile_world_item_result flatfile_world_item_prepare_room_item_snapshot(
	const std::string &root, const flatfile_authority_lock &lock, int32_t room_vnum,
	const std::vector<player_item_snapshot> &items, bool remove,
	flatfile_authority_operation *operation, std::string *error);

#endif
