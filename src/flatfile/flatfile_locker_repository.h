#ifndef DURIS_FLATFILE_LOCKER_REPOSITORY_H
#define DURIS_FLATFILE_LOCKER_REPOSITORY_H

#include "flatfile/flatfile_authority_transaction.h"
#include "item/item_transfer_command.h"
#include "player/player_snapshot.h"

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

struct flatfile_locker_chest_record
{
	uint32_t chest_id = 0;
	std::string chest_name;
	std::string password_hash;
	bool is_public = false;
	std::string sort_config;
	uint64_t revision = 0;
	std::vector<player_item_snapshot> items;
};

struct flatfile_account_locker_identity
{
	std::string account_name;
	int8_t racewar_side = 0;
};

struct flatfile_locker_record
{
	uint32_t locker_id = 0;
	std::string locker_name;
	int32_t owner_pid = 0;
	int32_t owner_assoc_id = 0;
	std::optional<flatfile_account_locker_identity> account_owner;
	int8_t racewar = 0;
	int8_t race = 0;
	uint64_t revision = 0;
	std::vector<flatfile_locker_chest_record> chests;
};

// A locker's public chest as its save writes it. A new locker is created for its owner: the
// guild owner_assoc_id, or the account and side its name ("account.<name>.<side>.locker")
// gives. (A player's own locker is entered only when it exists, so none is new.)
struct flatfile_locker_save
{
	std::string locker_name;
	int32_t owner_assoc_id = 0;
	int8_t racewar = 0;
	int8_t race = 0;
	std::vector<player_item_snapshot> items;
};

struct flatfile_locker_access_record
{
	std::string owner_name;
	std::string visitor_name;
	uint64_t revision = 0;
};

struct flatfile_locker_custody_item
{
	uint64_t item_uid = 0;
	int32_t vnum = 0;
};

struct flatfile_locker_custody_owner
{
	item_owner_identity owner = { item_owner_type::unknown, 0, 0 };
	std::vector<flatfile_locker_custody_item> items;
};

struct flatfile_locker_player_removal
{
	flatfile_authority_operation operation;
	std::vector<flatfile_locker_custody_owner> custody;
};

enum class flatfile_locker_result
{
	ok,
	not_found,
	already_exists,
	unchanged,
	conflict,
	invalid,
	io_error
};

flatfile_locker_result flatfile_locker_establish(
	const std::string &root, const std::vector<flatfile_locker_record> &lockers,
	const std::vector<flatfile_locker_access_record> &access, std::string *error);
flatfile_locker_result flatfile_locker_list(const std::string &root,
					    std::vector<flatfile_locker_record> *lockers,
					    std::vector<flatfile_locker_access_record> *access,
					    std::string *error);
// The stored locker named locker_name.
flatfile_locker_result flatfile_locker_find(const std::string &root, const std::string &locker_name,
					    flatfile_locker_record *locker, std::string *error);
// Under the authority lock: the owner a save of locker_name's public chest claims its items
// for, the stored locker's or the ids a new locker takes.
flatfile_locker_result flatfile_locker_public_owner(const std::string &root,
						    const flatfile_authority_lock &lock,
						    const std::string &locker_name,
						    item_owner_identity *owner, std::string *error);
// Under the same lock: write items as the public chest of save.locker_name, creating the
// locker with owner's ids when it is new.
flatfile_locker_result
flatfile_locker_prepare_public_save(const std::string &root, const flatfile_authority_lock &lock,
				    const flatfile_locker_save &save,
				    const item_owner_identity &owner,
				    const std::vector<player_item_snapshot> &items,
				    flatfile_authority_operation *operation, std::string *error);
/* Prepare player-owned locker and visitor-grant removal under the authority lock. */
flatfile_locker_result
flatfile_locker_prepare_player_remove(const std::string &root, const flatfile_authority_lock &lock,
				      uint32_t pid, const std::string &player_name,
				      flatfile_locker_player_removal *removal, std::string *error);
/* Prepare account-owned locker and visitor-grant removal under the authority lock. */
flatfile_locker_result
flatfile_locker_prepare_account_remove(const std::string &root, const flatfile_authority_lock &lock,
				       const std::string &account_name,
				       flatfile_locker_player_removal *removal, std::string *error);

#endif
