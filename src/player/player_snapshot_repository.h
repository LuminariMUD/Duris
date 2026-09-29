#ifndef PLAYER_SNAPSHOT_REPOSITORY_H
#define PLAYER_SNAPSHOT_REPOSITORY_H

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

#endif
