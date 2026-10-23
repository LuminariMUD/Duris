/****************************************************************************
 *
 *  File: flatfile_player_domain_repository.h                   Part of Duris
 *  Usage: flat-file player domain repository types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_PLAYER_DOMAIN_REPOSITORY_H
#define DURIS_FLATFILE_PLAYER_DOMAIN_REPOSITORY_H

#include "flatfile/flatfile_authority_transaction.h"
#include "player/player_load_repository.h"
#include "persistence/critical_command_coordinator.h"
#include "economy/currency_command.h"
#include "economy/divine_boon_delivery.h"

#include <cstdint>
#include <string>
#include <optional>
#include <vector>

struct flatfile_player_domain_record
{
	int32_t pid = 0;
	std::string account_name;
	int8_t racewar = 0;
	player_load_domain_state domains = {};
	std::vector<int64_t> recent_pvp_deaths;
	std::vector<int32_t> completed_epic_zones;
};

enum class flatfile_player_domain_result
{
	ok,
	not_found,
	conflict,
	invalid,
	io_error
};

// Compound prepared effects share the caller's primary authority transaction.
flatfile_player_domain_result
flatfile_artifact_deliveries_prepare(const std::string &root, const flatfile_authority_lock &lock,
				     const std::vector<critical_command> &commands,
				     std::vector<flatfile_authority_operation> *operations,
				     std::string *error);
flatfile_player_domain_result
flatfile_artifact_deliveries_list(const std::string &root, const flatfile_authority_lock &lock,
				  std::vector<critical_command> *commands, std::string *error);
// Verify native entity snapshots while holding lock before preparing this ACK.
flatfile_player_domain_result
flatfile_artifact_delivery_prepare_ack(const std::string &root, const flatfile_authority_lock &lock,
				       const critical_command &command,
				       std::vector<flatfile_authority_operation> *writes,
				       std::string *error);
flatfile_player_domain_result
flatfile_artifact_delivery_load(const std::string &root, const flatfile_authority_lock &lock,
				const critical_operation_id &operation, critical_command *command,
				bool *acknowledged, std::string *error);
flatfile_player_domain_result flatfile_artifact_delivery_acknowledged(
	const std::string &root, const flatfile_authority_lock &lock,
	const critical_command &command, bool *acknowledged, std::string *error);

struct flatfile_wallet_mutation
{
	currency_vector wallet = {};
	currency_vector bank = {};
	uint64_t wallet_revision = 0;
	uint64_t bank_revision = 0;
	std::vector<flatfile_authority_after_image> after_images;
};

struct flatfile_base_stat_mutation
{
	int16_t stat_value = 0;
	uint64_t stat_revision = 0;
	flatfile_authority_after_image after_image;
};

struct flatfile_identity_record;
// Read snapshot, saved balances and pending receipts under one authority lock.
flatfile_player_domain_result
flatfile_player_domain_load_checkpoint(const std::string &root,
				       const flatfile_identity_record &identity,
				       player_load_result *result, std::string *error);

flatfile_player_domain_result
flatfile_player_domain_establish(const std::string &root,
				 const flatfile_player_domain_record &record, std::string *error);
flatfile_player_domain_result flatfile_player_domain_establish_initial_player(
	const std::string &root, const flatfile_player_domain_record &record, std::string *error);
// Recover complete authority/domain intents without requiring an existing player.
flatfile_player_domain_result flatfile_player_domain_restore_recover(const std::string &root,
								     std::string *error);
flatfile_player_domain_result flatfile_player_domain_load(const std::string &root, int32_t pid,
							  const std::string &account_name,
							  int8_t racewar,
							  flatfile_player_domain_record *record,
							  std::string *error);
critical_apply_result flatfile_player_domain_apply(const std::string &root,
						   const critical_command &command);
flatfile_player_domain_result
flatfile_player_domain_pending_divine_epics(const std::string &root, uint32_t pid, uint64_t after,
					    std::vector<divine_epic_delivery> *deliveries,
					    std::string *error);
// Save balances; a stale wallet is replaced with the committed purse and revision.
struct flatfile_saved_balances
{
	std::array<uint64_t, 4> wallet = {};
	int64_t epics = 0;
	int64_t frags = 0;
	int64_t old_frags = 0;
	uint64_t divine_boon_delivery_seq = 0;
	uint64_t wallet_revision = 0;
};
flatfile_player_domain_result flatfile_player_domain_prepare_saved_balances(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	flatfile_saved_balances &balances, flatfile_authority_operation *operation,
	std::string *error);
// All native snapshot writers own authority. The compound operation uses that
// same lock to prepare its player file and domain wallet together; it never
// takes a player lock while holding authority.
flatfile_player_domain_result flatfile_player_domain_prepare_wallet(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	uint64_t expected_revision, uint64_t expected_account,
	const std::array<uint64_t, 4> &wallet,
	std::vector<flatfile_authority_operation> *operations, std::string *error,
	const player_affect_snapshot *cargo_effect = nullptr);

// A change to one account's bank on one side, added to its record (created when missing).
flatfile_player_domain_result flatfile_player_domain_prepare_bank_delta(
	const std::string &root, const flatfile_authority_lock &lock,
	const std::string &account_name, int8_t racewar, const std::array<int64_t, 4> &delta,
	flatfile_authority_operation *operation, std::string *error);
flatfile_player_domain_result flatfile_player_domain_prepare_base_stat(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t pid,
	uint8_t stat_index, bool apply_increment, flatfile_base_stat_mutation *mutation,
	unsigned int *result_code, std::string *error);
flatfile_player_domain_result
flatfile_player_domain_prepare_remove(const std::string &root, const flatfile_authority_lock &lock,
				      uint32_t pid, flatfile_authority_operation *operation,
				      std::string *error);
flatfile_player_domain_result flatfile_player_domain_prepare_account_remove(
	const std::string &root, const flatfile_authority_lock &lock,
	const std::string &account_name, std::vector<flatfile_authority_operation> *operations,
	std::string *error);

struct flatfile_zone_touch_state
{
	uint32_t number = 0;
	int32_t alignment = 0;
	int64_t last_touch = 0;
};
flatfile_player_domain_result flatfile_zone_touch_load(const std::string &root, uint32_t number,
						       flatfile_zone_touch_state *state,
						       std::string *error);

#endif
