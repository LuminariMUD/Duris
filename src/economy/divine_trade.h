#ifndef DIVINE_TRADE_H
#define DIVINE_TRADE_H

#include "economy/divine_boon.h"
#include "persistence/critical_command.h"

#include <cstdint>
#include <tuple>
#include <vector>

enum class divine_trade_goods : uint8_t
{
	cargo,
	contraband,
};

// One paid purchase remains one lot even when the ordinary ship slot merges it.
// The permanent transaction receipt retains the original after this lot is spent.
struct divine_trade_lot
{
	critical_operation_id purchase = {};
	uint32_t ship_id = 0;
	uint8_t slot = 0;
	divine_trade_goods goods = divine_trade_goods::cargo;
	int32_t source_port = -1;
	int64_t purchased_at = 0;
	uint32_t purchased_quantity = 0;
	uint32_t remaining_quantity = 0;
	int64_t invoice_basis = 0;
	int64_t remaining_basis = 0;
	bool operator==(const divine_trade_lot &other) const
	{
		return purchase.bytes == other.purchase.bytes &&
		       std::tie(ship_id, slot, goods, source_port, purchased_at, purchased_quantity,
				remaining_quantity, invoice_basis, remaining_basis) ==
			       std::tie(other.ship_id, other.slot, other.goods, other.source_port,
					other.purchased_at, other.purchased_quantity,
					other.remaining_quantity, other.invoice_basis,
					other.remaining_basis);
	}
};

// Keyed by the existing canonical account key with racewar=0, and boon ID.
// Neither a character/side change nor another ship creates another allowance.
struct divine_trade_book
{
	uint64_t revision = 0;
	uint64_t account = 0;
	uint64_t boon_id = 0;
	uint32_t first_ship_id = 0;
	uint32_t first_full_hold = 0;
	uint64_t consumed = 0;
	std::vector<divine_trade_lot> lots;
	bool operator==(const divine_trade_book &) const = default;
};

struct divine_trade_purchase
{
	critical_operation_id operation = {};
	uint64_t account = 0;
	uint32_t ship_id = 0;
	uint32_t full_hold = 0; // Full SHIP_MAX_CARGO, including current crew modifier.
	uint8_t slot = 0;
	divine_trade_goods goods = divine_trade_goods::cargo;
	int32_t source_port = -1;
	int64_t at = 0;
	uint32_t quantity = 0;
	int64_t paid = 0;
	uint32_t slot_quantity_before = 0;
	int64_t slot_basis_before = 0;
};

struct divine_trade_removal
{
	uint64_t account = 0; // Zero for loss; a different account cannot claim the lot.
	uint32_t ship_id = 0;
	uint8_t slot = 0;
	divine_trade_goods goods = divine_trade_goods::cargo;
	int32_t source_port = -1;
	int32_t destination_port = -1; // -1 for jettison, confiscation or other loss.
	int64_t at = 0;
	uint32_t slot_quantity_before = 0;
	int64_t slot_basis_before = 0;
	uint32_t quantity = 0;
};

struct divine_trade_consumption
{
	uint32_t qualifying_quantity = 0;
	int64_t qualifying_basis = 0;
	int64_t removed_basis = 0;
};

// Game-thread preparation only. Rejection preserves every input/output. The
// caller commits the prepared book with its wallet, ship and market after-images
// before publishing any success, using the operation's permanent retry receipt.
bool divine_trade_book_valid(const divine_trade_book &book);
bool divine_trade_prepare_purchase(const divine_trade_book &before, const divine_boon_slot &boon,
				   const divine_trade_purchase &purchase, divine_trade_book *after);
bool divine_trade_prepare_removal(const divine_trade_book &before, const divine_boon_slot &boon,
				  const divine_trade_removal &removal, divine_trade_book *after,
				  divine_trade_consumption *consumption);
// Unauthenticated salvage/ownership transfers remove proof, not ordinary goods.
// Slot -1 invalidates all of this account's lots on the persistent ship ID.
bool divine_trade_prepare_invalidation(const divine_trade_book &before, uint32_t ship_id, int slot,
				       divine_trade_book *after);

bool divine_trade_book_encode(const divine_trade_book &book, std::vector<uint8_t> *bytes);
bool divine_trade_book_decode(const std::vector<uint8_t> &bytes, divine_trade_book *book);

#endif
