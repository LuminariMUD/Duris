#include "economy/divine_trade_command.h"
#include "ships/ships.h"

#include <algorithm>
#include <cassert>
#include <cstdio>
#include <limits>
#include <openssl/sha.h>

namespace
{
critical_operation_id operation(uint64_t value)
{
	critical_operation_id id;
	for (unsigned i = 0; i < 8; ++i)
		id.bytes[i] = static_cast<uint8_t>(value >> (i * 8));
	return id;
}

divine_boon_slot route()
{
	divine_boon_slot boon;
	boon.id = 17;
	boon.category = divine_boon_category::cargo;
	boon.starts_at = 100;
	boon.expires_at = 14500;
	boon.source_port = boon.cargo_commodity = boon.contraband_commodity = 2;
	boon.destination_port = 4;
	return boon;
}

divine_trade_purchase purchase(uint64_t id, uint32_t quantity = 1)
{
	divine_trade_purchase result;
	result.operation = operation(id);
	result.account = 11;
	result.ship_id = 21;
	result.full_hold = 10;
	result.slot = 3;
	result.source_port = 2;
	result.at = 101;
	result.quantity = quantity;
	result.paid = quantity * 100;
	return result;
}

divine_trade_removal removal(uint32_t quantity, uint32_t existing, int64_t basis)
{
	divine_trade_removal result;
	result.account = 11;
	result.ship_id = 21;
	result.slot = 3;
	result.source_port = 2;
	result.destination_port = 4;
	result.at = 200;
	result.quantity = quantity;
	result.slot_quantity_before = existing;
	result.slot_basis_before = basis;
	return result;
}

void reload(divine_trade_book &book)
{
	std::vector<uint8_t> bytes;
	divine_trade_book restored;
	assert(divine_trade_book_encode(book, &bytes));
	assert(divine_trade_book_decode(bytes, &restored));
	assert(restored == book);
	book = restored;
	const auto original = book;
	bytes[12] ^= 1;
	assert(!divine_trade_book_decode(bytes, &book) && book == original);
}
}

int main()
{
	const auto boon = route();
	divine_trade_book blank, book;
	assert(divine_trade_book_valid(blank));
	reload(blank); // Existing goods have no invented purchase proof.
	auto buy = purchase(1);
	buy.slot_quantity_before = 9;
	buy.slot_basis_before = 900;
	assert(divine_trade_prepare_purchase(blank, boon, buy, &book));
	assert(book.first_ship_id == 21 && book.first_full_hold == 10);
	assert(book.lots.size() == 1 && book.lots[0].remaining_quantity == 1);
	reload(book);
	divine_trade_book after;
	divine_trade_consumption used;
	assert(divine_trade_prepare_removal(book, boon, removal(9, 10, 1000), &after, &used));
	assert(after == book && used.qualifying_quantity == 0 && used.removed_basis == 900);
	assert(divine_trade_prepare_removal(after, boon, removal(1, 1, 100), &after, &used));
	assert(used.qualifying_quantity == 1 && used.qualifying_basis == 100);
	assert(used.removed_basis == 100 && after.lots.empty() && after.consumed == 1);

	// Whole-slot sale of 9 old + 1 new qualifies precisely the new crate.
	assert(divine_trade_prepare_removal(book, boon, removal(10, 10, 1000), &after, &used));
	assert(used.qualifying_quantity == 1 && used.removed_basis == 1000);

	// Exact invoices remain separate within a merged ordinary slot. FIFO partial
	// removal carries division remainders forward and conserves every paid coin.
	buy = purchase(2, 3);
	buy.paid = 101;
	assert(divine_trade_prepare_purchase(blank, boon, buy, &book));
	buy = purchase(3, 2);
	buy.paid = 105;
	buy.slot_quantity_before = 3;
	buy.slot_basis_before = 101;
	assert(divine_trade_prepare_purchase(book, boon, buy, &book));
	assert(book.lots.size() == 2);
	assert(divine_trade_prepare_removal(book, boon, removal(1, 5, 206), &book, &used));
	assert(used.qualifying_quantity == 1 && used.removed_basis == 33);
	assert(book.lots[0].remaining_basis == 68 && book.lots[0].invoice_basis == 101);
	reload(book);
	assert(divine_trade_prepare_removal(book, boon, removal(2, 4, 173), &book, &used));
	assert(used.removed_basis == 68 && book.lots.size() == 1);
	assert(divine_trade_prepare_removal(book, boon, removal(2, 2, 105), &book, &used));
	assert(used.removed_basis == 105 && book.lots.empty() && book.consumed == 5);

	// One account/boon allowance combines both goods and all ships/alts/sides.
	book = {};
	for (uint64_t id = 40; id < 43; ++id)
	{
		const uint32_t quantity = id == 42 ? 5 : 10;
		buy = purchase(id, quantity);
		assert(divine_trade_prepare_purchase(book, boon, buy, &book));
		assert(divine_trade_prepare_removal(
			book, boon, removal(quantity, quantity, quantity * 100), &book, &used));
		assert(used.qualifying_quantity == quantity);
	}
	assert(book.consumed == 25);
	reload(book); // Empty lots must not discard the already-spent allowance.
	buy = purchase(5, 10);
	buy.ship_id = 99;
	buy.full_hold = 500;
	buy.goods = divine_trade_goods::contraband;
	assert(divine_trade_prepare_purchase(book, boon, buy, &book));
	assert(book.first_full_hold == 10 && book.first_ship_id == 21);
	auto sell = removal(10, 10, 1000);
	sell.ship_id = 99;
	sell.goods = divine_trade_goods::contraband;
	assert(divine_trade_prepare_removal(book, boon, sell, &book, &used));
	assert(used.qualifying_quantity == 5 && used.qualifying_basis == 500 &&
	       book.consumed == 30);
	buy = purchase(6);
	assert(divine_trade_prepare_purchase(book, boon, buy, &book));
	assert(divine_trade_prepare_removal(book, boon, removal(1, 1, 100), &book, &used));
	assert(!used.qualifying_quantity && book.consumed == 30 && book.lots.empty());

	// Unrelated accounts get their own book, never another book for the same key.
	buy = purchase(7);
	buy.account = 12;
	assert(divine_trade_prepare_purchase(blank, boon, buy, &after));
	assert(after.account == 12);
	const auto sentinel = after;
	assert(!divine_trade_prepare_purchase(book, boon, buy, &after) && after == sentinel);

	// Strict start/expiry, source loops, unpaid/duplicate commands and stale slots.
	buy = purchase(8);
	buy.at = boon.starts_at;
	assert(!divine_trade_prepare_purchase(blank, boon, buy, &after) && after == sentinel);
	buy.at = boon.expires_at;
	assert(!divine_trade_prepare_purchase(blank, boon, buy, &after));
	buy.at = 101;
	buy.paid = 0;
	assert(!divine_trade_prepare_purchase(blank, boon, buy, &after));
	buy.paid = 100;
	auto invalid = boon;
	invalid.destination_port = invalid.source_port;
	assert(!divine_trade_prepare_purchase(blank, invalid, buy, &after));
	assert(divine_trade_prepare_purchase(blank, boon, buy, &book));
	buy.slot_quantity_before = 1;
	buy.slot_basis_before = 100;
	assert(!divine_trade_prepare_purchase(book, boon, buy, &after));
	auto wrong = removal(1, 1, 100);
	wrong.goods = divine_trade_goods::contraband;
	assert(!divine_trade_prepare_removal(book, boon, wrong, &after, &used));
	// A slot holding only lots must carry exactly their basis, or emptying it
	// would strand basis on zero crates.
	assert(!divine_trade_prepare_removal(book, boon, removal(1, 1, 150), &after, &used));
	buy = purchase(10);
	buy.slot_quantity_before = 1;
	buy.slot_basis_before = 150;
	assert(!divine_trade_prepare_purchase(book, boon, buy, &after));
	assert(after == sentinel);

	for (int scenario = 0; scenario < 5; ++scenario)
	{
		auto loss = removal(1, 1, 100);
		if (scenario == 0)
			loss.destination_port = -1; // Jettison/confiscation.
		if (scenario == 1)
			loss.destination_port = loss.source_port; // Sellback.
		if (scenario == 2)
			loss.account = 12; // Unproven ownership/account transfer.
		if (scenario == 3)
			loss.at = boon.expires_at;
		if (scenario == 4)
			loss.at = 100; // Purchase timestamp is later than admission.
		assert(divine_trade_prepare_removal(book, boon, loss, &after, &used));
		assert(!used.qualifying_quantity && !after.consumed && after.lots.empty());
	}
	assert(divine_trade_prepare_invalidation(book, 21, 3, &after));
	assert(after.lots.empty() && !after.consumed && after.first_full_hold == 10);
	assert(divine_trade_prepare_invalidation(book, 21, -1, &after));
	assert(after.lots.empty());
	assert(divine_trade_prepare_invalidation(book, 99, -1, &after) && after == book);

	// A caller can reject a prepared transaction without affecting runtime state.
	const auto unchanged = book;
	assert(divine_trade_prepare_removal(book, boon, removal(1, 1, 100), &after, &used));
	assert(book == unchanged && after != book);
	reload(after);

	// More than 512 distinct purchases are not a lifetime ceiling. Spent lot IDs
	// live in permanent receipts, not an ever-growing in-memory manifest.
	book = {};
	for (uint64_t id = 100; id < 700; ++id)
	{
		buy = purchase(id);
		assert(divine_trade_prepare_purchase(book, boon, buy, &book));
		assert(divine_trade_prepare_removal(book, boon, removal(1, 1, 100), &book, &used));
	}
	assert(book.consumed == 30 && book.lots.empty());
	reload(book);

	// Checksummed but semantically invalid records are also rejected.
	buy = purchase(900);
	assert(divine_trade_prepare_purchase(blank, boon, buy, &book));
	auto corrupt = book;
	corrupt.lots.push_back(corrupt.lots[0]);
	std::vector<uint8_t> encoded;
	assert(!divine_trade_book_valid(corrupt) && !divine_trade_book_encode(corrupt, &encoded));
	assert(divine_trade_book_encode(book, &encoded));
	std::fill(encoded.begin() + 56, encoded.begin() + 72, 0); // Zero the purchase ID.
	SHA256(encoded.data(), encoded.size() - SHA256_DIGEST_LENGTH,
	       encoded.data() + encoded.size() - SHA256_DIGEST_LENGTH);
	assert(!divine_trade_book_decode(encoded, &after));
	for (size_t length = 0; length < encoded.size(); ++length)
	{
		const std::vector<uint8_t> truncated(encoded.begin(), encoded.begin() + length);
		assert(!divine_trade_book_decode(truncated, &after));
	}
	corrupt = book;
	corrupt.revision = std::numeric_limits<uint64_t>::max();
	assert(!divine_trade_prepare_invalidation(corrupt, 21, -1, &after));
	// The actual critical-command codec carries the prepared financial boundary,
	// including canonical player/account/ship/market reservations and retry identity.
	divine_trade_payload payload;
	payload.pid = 42;
	payload.ship_id = 21;
	payload.ship_owner_pid = 42;
	payload.generation = 1;
	payload.wallet_revision = 9;
	payload.admitted_at = 101;
	payload.payment = -100;
	payload.wallet_after.amount = { 0, 0, 0, 1 };
	payload.slots_after.push_back({ 3, SLOT_CARGO, 2, SLOT_HOLD, 0, { 1, 100, 0, 0, 0 } });
	payload.market_after.push_back({ 2, 2, divine_trade_goods::cargo, 1.03f, 100 });
	payload.book_after = book;
	critical_command command;
	assert(divine_trade_command_build(&command, operation(900), payload));
	command.accepted_at_usec = 123456;
	divine_trade_payload decoded;
	assert(divine_trade_command_decode(command, &decoded));
	assert(decoded.book_after == book && decoded.wallet_revision == 9);
	assert(command.keys.size() == 4 && command.keys.back().type == critical_entity_type::ship);
	assert(divine_trade_book_transition_valid(blank, decoded));
	std::vector<uint8_t> wire;
	critical_command restored_command;
	assert(critical_command_encode(command, &wire) == critical_command_codec_result::ok);
	assert(critical_command_decode(wire.data(), wire.size(), &restored_command) ==
	       critical_command_codec_result::ok);
	assert(divine_trade_command_decode(restored_command, &decoded));
	auto bad_command = command;
	bad_command.keys.back().id = 22;
	assert(!divine_trade_command_decode(bad_command, &decoded));
	bad_command = command;
	bad_command.payload.push_back(0);
	assert(!divine_trade_command_decode(bad_command, &decoded));
	for (size_t length = 0; length < command.payload.size(); ++length)
	{
		bad_command = command;
		bad_command.payload.resize(length);
		assert(!divine_trade_command_decode(bad_command, &decoded));
	}
	auto invalid_transition = payload;
	invalid_transition.book_revision = book.revision;
	invalid_transition.book_after.first_full_hold = 500;
	invalid_transition.book_after.revision++;
	assert(!divine_trade_book_transition_valid(book, invalid_transition));
	divine_trade_result result{ 42, 21, 2, 10, book.revision, -100, 0 };
	std::array<uint8_t, DIVINE_TRADE_RESULT_BYTES> result_bytes;
	assert(divine_trade_result_encode(result, &result_bytes));
	divine_trade_result decoded_result;
	assert(divine_trade_result_decode(result_bytes.data(), result_bytes.size(),
					  &decoded_result));
	assert(decoded_result.payment == -100 && decoded_result.generation == 2);
	result_bytes.back() = 1;
	assert(!divine_trade_result_decode(result_bytes.data(), result_bytes.size(),
					   &decoded_result));
	puts("PASS: exact Divine trade lots, partial basis, shared fixed cap, loss and checked reload");
}
