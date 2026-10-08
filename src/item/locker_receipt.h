/****************************************************************************
 *
 *  File: locker_receipt.h                                      Part of Duris
 *  Usage: locker receipt type and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#pragma once

#include "economy/currency_command.h"
#include "flatfile/flatfile_store.h"
#include <string>

constexpr size_t LOCKER_RECEIPT_TEXT_MAX = 64 * 1024;
enum class locker_receipt_state : uint8_t
{
	prepared,
	paid,
	failed,
	delivered // paid and shown; only stat receipt repeats it
};
struct locker_receipt
{
	critical_command payment{};
	std::string text;
	locker_receipt_state state = locker_receipt_state::prepared;
};

bool locker_receipt_encode(const locker_receipt &receipt, std::vector<uint8_t> *bytes);
bool locker_receipt_decode(const std::vector<uint8_t> &bytes, uint32_t pid,
			   locker_receipt *receipt);
flatfile_read_result locker_receipt_read(const std::string &directory, uint32_t pid,
					 locker_receipt *receipt);
bool locker_receipt_write(const std::string &directory, const locker_receipt &receipt);
