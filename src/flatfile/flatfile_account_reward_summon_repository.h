/****************************************************************************
 *
 *  File: flatfile_account_reward_summon_repository.h           Part of Duris
 *  Usage: flat-file account reward summon repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_ACCOUNT_REWARD_SUMMON_REPOSITORY_H
#define DURIS_FLATFILE_ACCOUNT_REWARD_SUMMON_REPOSITORY_H

#include "flatfile/flatfile_authority_transaction.h"

#include <cstdint>
#include <string>
#include <vector>

struct flatfile_account_reward_summon_record
{
	uint64_t grant_id = 0;
	uint32_t pid = 0;
	int64_t last_summoned_at = 0;
	bool recovery_ready = false;
	uint64_t revision = 0;
};

enum class flatfile_account_reward_summon_result
{
	ok,
	not_found,
	already_exists,
	unchanged,
	invalid,
	io_error
};

flatfile_account_reward_summon_result flatfile_account_reward_summon_establish(
	const std::string &root, const std::vector<flatfile_account_reward_summon_record> &records,
	std::string *error);
flatfile_account_reward_summon_result
flatfile_account_reward_summon_list(const std::string &root,
				    std::vector<flatfile_account_reward_summon_record> *records,
				    std::string *error);
flatfile_account_reward_summon_result flatfile_account_reward_summon_prepare_player_remove(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	flatfile_authority_operation *operation, std::string *error);

#endif
