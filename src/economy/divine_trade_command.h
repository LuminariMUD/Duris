#ifndef DIVINE_TRADE_COMMAND_H
#define DIVINE_TRADE_COMMAND_H

#include "economy/divine_trade.h"
#include "economy/divine_trade_result.h"
#include "player/player_snapshot.h"
#include "economy/currency_command.h"
#include "flatfile/flatfile_ship_repository.h"

constexpr uint16_t DIVINE_TRADE_PAYLOAD_VERSION = 3;
constexpr uint16_t DIVINE_TRADE_OUTBOX_DESTINATION = 12;
constexpr uint64_t DIVINE_TRADE_MARKET_KEY = 0x445452414445;

enum class divine_trade_action : uint8_t
{
	purchase = 1,
	sale,
};

struct divine_trade_market_cell
{
	uint8_t port = 0;
	uint8_t commodity = 0;
	divine_trade_goods goods = divine_trade_goods::cargo;
	float modifier = 0;
	int32_t price = 0;
};

// All gameplay calculations happen on the game thread. The writer checks
// revisions and commits these absolute after-images; it does not quote prices
// or decide which purchases qualify for the boon.
struct divine_trade_payload
{
	divine_trade_action action = divine_trade_action::purchase;
	uint32_t pid = 0;
	uint32_t ship_id = 0;
	uint32_t ship_owner_pid = 0;
	uint64_t generation = 0; // Expected market/trade generation; commit advances one.
	uint64_t book_revision = 0;
	uint64_t wallet_revision = 0;
	int64_t admitted_at = 0;
	int64_t payment = 0; // Negative for a purchase; nonnegative for a sale.
	uint32_t qualifying_quantity = 0;
	currency_vector wallet_after = {};
	flatfile_ship_crew_record crew_after;
	std::vector<flatfile_ship_slot_record> slots_after;
	std::vector<divine_trade_market_cell> market_after;
	divine_trade_book book_after;
	flatfile_ship_crew_record crew_before;
	std::vector<flatfile_ship_slot_record> slots_before;
	bool has_cargo_effect = false;
	player_affect_snapshot cargo_effect{};
};

bool divine_trade_command_build(critical_command *command, critical_operation_id operation,
				const divine_trade_payload &payload);
bool divine_trade_command_decode(const critical_command &command, divine_trade_payload *payload);
// Checked persisted preimage versus game-thread preparation; never reprice an
// operation from database state. The first hold and spent cap cannot roll back.
bool divine_trade_book_transition_valid(const divine_trade_book &before,
					const divine_trade_payload &payload);

#endif
