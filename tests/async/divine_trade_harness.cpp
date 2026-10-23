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
	payload.slots_before.push_back({ 3, SLOT_EMPTY, -1, -1, 0, { -1, -1, -1, -1, -1 } });
	payload.market_after.push_back({ 2, 2, divine_trade_goods::cargo, 1.03f, 100 });
	payload.book_after = book;
	critical_command command;
	assert(divine_trade_command_build(&command, operation(900), payload));
	auto other_owner = payload;
	other_owner.ship_owner_pid++;
	critical_command invalid_owner;
	assert(!divine_trade_command_build(&invalid_owner, operation(900), other_owner));
	for (size_t field = 0; field < 7; ++field)
	{
		auto altered = payload;
		int32_t *values[] = { &altered.crew_after.crew_index,
				      &altered.crew_after.sail_skill_milli,
				      &altered.crew_after.guns_skill_milli,
				      &altered.crew_after.repair_skill_milli,
				      &altered.crew_after.sail_chief,
				      &altered.crew_after.guns_chief,
				      &altered.crew_after.repair_chief };
		++*values[field];
		assert(!divine_trade_command_build(&invalid_owner, operation(900), altered));
	}
	auto missing_preimage = payload;
	missing_preimage.slots_before.clear();
	critical_command refused_preimage;
	assert(!divine_trade_command_build(&refused_preimage, operation(900), missing_preimage));

	for (size_t coin = 0; coin < 4; ++coin)
	{
		auto overflow = payload;
		overflow.wallet_after.amount[coin] = static_cast<int64_t>(INT32_MAX) + 1;
		critical_command refused;
		assert(!divine_trade_command_build(&refused, operation(900), overflow));
	}
	for (size_t field = 0; field < 3; ++field)
		for (int chief : { -1, MAXCHIEFS })
		{
			auto malformed = payload;
			int32_t *chiefs[] = { &malformed.crew_after.sail_chief,
					      &malformed.crew_after.guns_chief,
					      &malformed.crew_after.repair_chief };
			*chiefs[field] = chief;
			critical_command refused;
			assert(!divine_trade_command_build(&refused, operation(900), malformed));
		}
	command.accepted_at_usec = 123456;
	divine_trade_payload decoded;
	assert(divine_trade_command_decode(command, &decoded));
	assert(decoded.book_after == book && decoded.wallet_revision == 9);
	assert(command.keys.size() == 4 && command.keys.back().type == critical_entity_type::ship);
	assert(divine_trade_book_transition_valid(blank, decoded));
	// Repository preimage checks preserve the exact manifest, not just its cap.
	auto next_buy = purchase(901);
	next_buy.slot_quantity_before = 1;
	next_buy.slot_basis_before = 100;
	auto next_payload = payload;
	next_payload.book_revision = book.revision;
	next_payload.slots_before = payload.slots_after;
	next_payload.slots_after[0].values[0] = 2;
	next_payload.slots_after[0].values[1] = 200;
	assert(divine_trade_prepare_purchase(book, boon, next_buy, &next_payload.book_after));
	assert(divine_trade_book_transition_valid(book, next_payload));
	assert(divine_trade_command_build(&command, operation(901), next_payload));
	for (size_t field : { size_t{ 0 }, size_t{ 1 } })
		for (int adjustment : { -1, 1 })
		{
			auto phantom = next_payload;
			phantom.slots_after[0].values[field] += adjustment;
			critical_command refused;
			assert(!divine_trade_command_build(&refused, operation(901), phantom));
		}
	// Retain the original receipt for the legacy wire checks below.
	assert(divine_trade_command_build(&command, operation(900), payload));
	command.accepted_at_usec = 123456;

	auto forged = next_payload;
	forged.book_after.lots.erase(forged.book_after.lots.begin());
	assert(!divine_trade_book_transition_valid(book, forged));
	forged = next_payload;
	forged.book_after.lots[0].purchase = operation(999);
	assert(!divine_trade_book_transition_valid(book, forged));
	forged = next_payload;
	forged.book_after.revision++;
	assert(!divine_trade_book_transition_valid(book, forged));
	auto unsold_buy = purchase(902);
	unsold_buy.ship_id = 99;
	unsold_buy.slot = 4;
	divine_trade_book with_unsold;
	assert(divine_trade_prepare_purchase(next_payload.book_after, boon, unsold_buy,
					     &with_unsold));
	auto sale_payload = next_payload;
	sale_payload.action = divine_trade_action::sale;
	sale_payload.slots_before = next_payload.slots_after;
	sale_payload.book_revision = with_unsold.revision;
	sale_payload.payment = 250;
	sale_payload.admitted_at = 200;
	sale_payload.slots_after[0] = { 3, SLOT_EMPTY, -1, -1, 0, { -1, -1, -1, -1, -1 } };
	sale_payload.market_after[0].port = 4;
	divine_trade_consumption sale_used;
	assert(divine_trade_prepare_removal(with_unsold, boon, removal(2, 2, 200),
					    &sale_payload.book_after, &sale_used));
	sale_payload.qualifying_quantity = sale_used.qualifying_quantity;
	assert(divine_trade_book_transition_valid(with_unsold, sale_payload));
	critical_command checked_sale;
	assert(divine_trade_command_build(&checked_sale, operation(903), sale_payload));
	auto wrong_sale = sale_payload;
	wrong_sale.slots_before[0].slot_type = SLOT_EMPTY;
	assert(!divine_trade_command_build(&checked_sale, operation(903), wrong_sale));
	wrong_sale = sale_payload;
	wrong_sale.market_after[0].commodity = 7;
	assert(!divine_trade_command_build(&checked_sale, operation(903), wrong_sale));
	wrong_sale = sale_payload;
	wrong_sale.market_after[0].goods = divine_trade_goods::contraband;
	assert(!divine_trade_command_build(&checked_sale, operation(903), wrong_sale));
	wrong_sale = sale_payload;
	--wrong_sale.slots_before[0].values[0];
	assert(!divine_trade_book_transition_valid(with_unsold, wrong_sale));
	wrong_sale = sale_payload;
	--wrong_sale.slots_before[0].values[1];
	assert(!divine_trade_book_transition_valid(with_unsold, wrong_sale));

	forged = sale_payload;
	forged.book_after.lots.clear();
	assert(!divine_trade_book_transition_valid(with_unsold, forged));
	forged = sale_payload;
	forged.book_after.lots[0].purchase = operation(999);
	assert(!divine_trade_book_transition_valid(with_unsold, forged));
	forged = sale_payload;
	forged.book_after.revision--;
	assert(!divine_trade_book_transition_valid(with_unsold, forged));

	std::vector<uint8_t> wire;
	critical_command restored_command;
	assert(critical_command_encode(command, &wire) == critical_command_codec_result::ok);
	assert(critical_command_decode(wire.data(), wire.size(), &restored_command) ==
	       critical_command_codec_result::ok);
	assert(divine_trade_command_decode(restored_command, &decoded));
	std::vector<uint8_t> retained_book;
	assert(divine_trade_book_encode(payload.book_after, &retained_book));
	auto old_command = command;
	old_command.payload_version = 1;
	const size_t preimage_bytes = 4 + 7 * sizeof(int32_t) + payload.slots_before.size() * 37;
	const auto book_offset = old_command.payload.size() - retained_book.size();
	old_command.payload.erase(old_command.payload.begin() + book_offset - preimage_bytes,
				  old_command.payload.begin() + book_offset);
	assert(divine_trade_command_decode(old_command, &decoded) && decoded.slots_before.empty());
	auto v2_command = command;
	v2_command.payload_version = 2;
	v2_command.payload.erase(v2_command.payload.begin() + book_offset - (preimage_bytes - 4),
				 v2_command.payload.begin() + book_offset);
	assert(divine_trade_command_decode(v2_command, &decoded) && decoded.slots_before.empty() &&
	       !decoded.has_cargo_effect);

	auto sale = payload;
	sale.slots_before = payload.slots_after;
	sale.crew_before = payload.crew_after;
	sale.action = divine_trade_action::sale;
	sale.admitted_at = 200;
	sale.payment = 150;
	sale.book_revision = book.revision;
	sale.qualifying_quantity = 1;
	divine_trade_consumption effect_used;
	assert(divine_trade_prepare_removal(book, boon, removal(1, 1, 100), &sale.book_after,
					    &effect_used));
	sale.slots_after = { { 3, SLOT_EMPTY, -1, -1, 0, { -1, -1, -1, -1, -1 } } };
	sale.market_after = { { 4, 2, divine_trade_goods::cargo, .95f, 120 } };
	sale.has_cargo_effect = true;
	sale.cargo_effect.type = PLAYER_TRADE_CARGO_AFFECT;
	sale.cargo_effect.duration = -1;
	sale.cargo_effect.modifier = 10005;
	critical_command effect_command;
	assert(divine_trade_command_build(&effect_command, operation(901), sale) &&
	       divine_trade_command_decode(effect_command, &decoded) && decoded.has_cargo_effect &&
	       decoded.cargo_effect.modifier == 10005);
	std::vector<uint8_t> effect_book;
	assert(divine_trade_book_encode(sale.book_after, &effect_book));
	auto v2_effect = effect_command;
	v2_effect.payload_version = 2;
	const auto effect_book_offset = v2_effect.payload.size() - effect_book.size();
	v2_effect.payload.erase(v2_effect.payload.begin() + effect_book_offset -
					(preimage_bytes - 4),
				v2_effect.payload.begin() + effect_book_offset);
	assert(divine_trade_command_decode(v2_effect, &decoded) && decoded.has_cargo_effect &&
	       decoded.cargo_effect.modifier == 10005 && decoded.slots_before.empty());

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
