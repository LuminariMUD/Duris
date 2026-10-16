/****************************************************************************
 *
 *  File: flatfile_shop_trade_materialization.h                 Part of Duris
 *  Usage: flat-file shop trade materialization interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_SHOP_TRADE_MATERIALIZATION_H
#define DURIS_FLATFILE_SHOP_TRADE_MATERIALIZATION_H

#include "flatfile/flatfile_authority_transaction.h"
#include "flatfile/flatfile_item_repository.h"
#include "player/player_snapshot.h"
#include "economy/shop_trade_command.h"

#include <string>
#include <vector>

enum class flatfile_shop_trade_materialization_result
{
	ok,
	unchanged,
	invalid,
	io_error
};

struct flatfile_shop_trade_materialization_mutation
{
	flatfile_authority_after_image after_image;
};

struct flatfile_shop_trade_materialization_health
{
	uint64_t revision = 0;
	uint64_t events = 0;
	uint64_t encoded_bytes = 0;
	uint64_t reclaimable_events = 0;
	uint64_t maximum_events = 0;
	uint64_t maximum_bytes = 0;
	bool near_capacity = false;
};

struct flatfile_item_materialization_projection
{
	critical_operation_id operation_id = {};
	uint32_t player_pid = 0;
	item_owner_identity owner = {};
	bool inbound = false;
	std::vector<player_item_snapshot> items;
};

// Retain inbound and outbound evidence, including raised-pet payloads. Does not
// reconcile or rewrite a player file and does not apply a historical event.
// Events remain in catalog capture order, as used by load reconciliation.
flatfile_shop_trade_materialization_result
flatfile_item_materialization_read(const std::string &root, const flatfile_authority_lock &lock,
				   std::vector<flatfile_item_materialization_projection> *events,
				   std::string *error);

flatfile_shop_trade_materialization_result flatfile_shop_trade_materialization_prepare(
	const std::string &root, const flatfile_authority_lock &lock,
	const critical_operation_id &operation_id, const shop_trade_payload &payload,
	flatfile_shop_trade_materialization_mutation *mutation, std::string *error);
flatfile_shop_trade_materialization_result flatfile_item_transfer_materialization_prepare(
	const std::string &root, const flatfile_authority_lock &lock,
	const critical_operation_id &operation_id, const item_transfer_payload &payload,
	flatfile_shop_trade_materialization_mutation *mutation, std::string *error);

flatfile_shop_trade_materialization_result flatfile_shop_trade_materialization_reconcile(
	const std::string &root, const flatfile_authority_lock &lock, uint32_t player_pid,
	const std::vector<flatfile_item_ownership_record> &owned, player_snapshot *snapshot,
	std::string *error);
flatfile_shop_trade_materialization_result flatfile_shop_trade_materialization_read_health(
	const std::string &root, const flatfile_authority_lock &lock,
	flatfile_shop_trade_materialization_health *health, std::string *error);
flatfile_shop_trade_materialization_result
flatfile_shop_trade_materialization_prepare_player_remove(const std::string &root,
							  const flatfile_authority_lock &lock,
							  uint32_t player_pid,
							  flatfile_authority_operation *operation,
							  std::string *error);

#endif
