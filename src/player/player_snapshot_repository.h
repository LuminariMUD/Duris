#ifndef PLAYER_SNAPSHOT_REPOSITORY_H
#define PLAYER_SNAPSHOT_REPOSITORY_H

#include "flatfile/flatfile_shopkeeper_repository.h"
#include "item/item_claim.h"
#include "player/player_save_worker.h"
#include <mysql/mysql.h>

#include <array>
#include <string>
#include <vector>

// Caller owns the transaction. Shared by checkpoint and legacy save adapters.
bool player_snapshot_repository_write_pets(MYSQL *connection, const player_snapshot &snapshot);

player_save_apply_result player_snapshot_repository_apply(MYSQL *connection,
							  const player_snapshot &snapshot);
player_save_apply_result player_snapshot_repository_apply_from_pool(const player_snapshot &snapshot,
								    void *context);

// A player corpse as its save writes it; `remove` deletes the corpse instead.
struct corpse_snapshot
{
	item_owner_identity owner;
	int32_t save_id = 0;
	std::string player_name;
	bool remove = false;
	int32_t room_vnum = 0;
	std::string short_description;
	std::string description;
	std::string keywords;
	int32_t weight = 0;
	std::array<int32_t, 8> values = {};
	std::vector<player_item_snapshot> items;
};

// Replaces a shopkeeper's row, affects and stock in one transaction.
player_save_apply_result
shopkeeper_snapshot_repository_apply(MYSQL *connection, const flatfile_shopkeeper_record &shop);
player_save_apply_result
shopkeeper_snapshot_repository_apply_from_pool(const flatfile_shopkeeper_record &shop);

// Replaces the corpse row and its items in one transaction, claiming the items for
// the corpse as a player save claims what the player holds.
player_save_apply_result corpse_snapshot_repository_apply(MYSQL *connection,
							  const corpse_snapshot &corpse);
player_save_apply_result corpse_snapshot_repository_apply_from_pool(const corpse_snapshot &corpse);

// A saved room item and its contents as its save writes them, keyed by `item_key`;
// `remove` deletes it instead.
struct saved_item_snapshot
{
	item_owner_identity owner;
	std::string item_key;
	int32_t room_vnum = 0;
	bool remove = false;
	std::vector<player_item_snapshot> items;
};

// Replaces the saved item's rows in one transaction, claiming them for the room.
player_save_apply_result saved_item_snapshot_repository_apply(MYSQL *connection,
							      const saved_item_snapshot &item);
player_save_apply_result
saved_item_snapshot_repository_apply_from_pool(const saved_item_snapshot &item);

// A private locker chest's contents as its save writes them.
struct locker_chest_snapshot
{
	int32_t locker_id = 0;
	int32_t chest_id = 0;
	std::vector<player_item_snapshot> items;
};

// Replaces the chest's rows in one transaction, claiming them for the chest.
player_save_apply_result locker_chest_snapshot_repository_apply(MYSQL *connection,
								const locker_chest_snapshot &chest);
player_save_apply_result
locker_chest_snapshot_repository_apply_from_pool(const locker_chest_snapshot &chest);

// A locker's public chest as its save writes it, keyed by the locker's name. The writer
// finds the locker's row and public chest, creating them for a new locker, so the game
// thread never queries for them.
struct locker_snapshot
{
	std::string locker_name;
	// A player locker's owner, looked up only to create its row; empty for guild and
	// account lockers.
	std::string owner_name;
	int32_t owner_assoc_id = 0;
	int32_t racewar = 0;
	int32_t race = 0;
	std::vector<player_item_snapshot> items;
};

// Replaces the public chest's rows in one transaction, claiming them for the chest.
player_save_apply_result locker_snapshot_repository_apply(MYSQL *connection,
							  const locker_snapshot &locker);
player_save_apply_result locker_snapshot_repository_apply_from_pool(const locker_snapshot &locker);

// One log_entries row (sql_log()), with the time it was logged. Strings are written as
// given; the caller keeps them within their columns.
struct log_entry_snapshot
{
	int64_t logged_at = 0;
	std::string kind;
	std::string ip_address;
	int32_t pid = 0;
	std::string player_name;
	int32_t zone_number = 0;
	int32_t room_vnum = 0;
	std::string message;
};

player_save_apply_result log_entry_repository_apply(MYSQL *connection,
						    const log_entry_snapshot &entry);
player_save_apply_result log_entry_repository_apply_from_pool(const log_entry_snapshot &entry);

// A change to one account's bank on one side, added to what account_banks holds (the
// characters of an account share its bank). The row is created when missing.
struct bank_delta_snapshot
{
	std::string account_name;
	int32_t racewar = 0;
	std::array<int64_t, 4> delta = {};
};

player_save_apply_result bank_delta_repository_apply(MYSQL *connection,
						     const bank_delta_snapshot &bank);
player_save_apply_result bank_delta_repository_apply_from_pool(const bank_delta_snapshot &bank);

#endif
