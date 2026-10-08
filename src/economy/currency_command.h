/****************************************************************************
 *
 *  File: currency_command.h                                    Part of Duris
 *  Usage: currency command payload, result, and reason types
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef CURRENCY_COMMAND_H
#define CURRENCY_COMMAND_H

#include "persistence/critical_command.h"

#include <array>
#include <cstdint>

constexpr uint16_t CURRENCY_COMMAND_PAYLOAD_VERSION = 1;
constexpr size_t CURRENCY_ACCOUNT_NAME_MAX_BYTES = 50;
constexpr size_t CURRENCY_COMMAND_PAYLOAD_BYTES = 136;
constexpr size_t CURRENCY_DENOMINATION_COUNT = 4;

// Stored in locker receipts: never renumber a reason. coin_transfer (16) and
// corpse_lifecycle (18) are retired.
enum class currency_reason_type : uint16_t
{
	unknown = 0,
	atm_deposit = 1,
	atm_withdraw = 2,
	bank_payment = 3,
	bank_reward = 4,
	wallet_reward = 5,
	wallet_spend = 6,
	refund = 7,
	auction_pickup = 8,
	auction_listing = 9,
	auction_bid = 10,
	auction_claim = 11,
	ship_insurance = 12,
	boon_reward = 13,
	operator_adjustment = 14,
	chaos_starter_reward = 15,
	collector_purchase = 17,
};

struct currency_vector
{
	std::array<int64_t, CURRENCY_DENOMINATION_COUNT> amount;
};

struct currency_command_payload
{
	uint32_t pid;
	uint8_t racewar;
	currency_reason_type reason;
	int64_t reason_id;
	std::array<char, CURRENCY_ACCOUNT_NAME_MAX_BYTES + 1> account_name;
	currency_vector wallet_delta;
	currency_vector bank_delta;
};

struct currency_command_result
{
	currency_vector wallet;
	currency_vector bank;
	uint64_t wallet_revision;
	uint64_t bank_revision;
};

bool currency_account_key(const char *account_name, uint8_t racewar, critical_entity_key *key);
bool currency_command_encode_payload(const currency_command_payload &payload,
				     std::vector<uint8_t> *encoded);
bool currency_command_decode_payload(const critical_command &command,
				     currency_command_payload *payload);
bool currency_command_build(critical_command *command, critical_operation_id operation_id,
			    const currency_command_payload &payload,
			    uint64_t expected_wallet_revision, uint64_t expected_bank_revision,
			    critical_source_site source_site,
			    critical_deadline_class deadline_class);

#endif
