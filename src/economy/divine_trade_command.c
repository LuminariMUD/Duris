#include "economy/divine_trade_command.h"

#include "ships/ships.h"

#include <algorithm>
#include <bit>
#include <cmath>
#include <limits>
#include <set>

namespace
{
template <typename T> void append(std::vector<uint8_t> &bytes, T value)
{
	for (size_t i = 0; i < sizeof(T); ++i)
		bytes.push_back(static_cast<uint8_t>(static_cast<uint64_t>(value) >> (i * 8)));
}

template <typename T> bool read(const std::vector<uint8_t> &bytes, size_t &offset, T &value)
{
	if (offset > bytes.size() || bytes.size() - offset < sizeof(T))
		return false;
	uint64_t number = 0;
	for (size_t i = 0; i < sizeof(T); ++i)
		number |= static_cast<uint64_t>(bytes[offset++]) << (i * 8);
	value = static_cast<T>(number);
	return true;
}

bool valid(const divine_trade_payload &p, uint16_t version)
{
	if ((p.action != divine_trade_action::purchase && p.action != divine_trade_action::sale) ||
	    !p.pid || p.pid > INT32_MAX || !p.ship_id || p.ship_id > INT32_MAX ||
	    !p.ship_owner_pid || p.ship_owner_pid > INT32_MAX || p.generation == UINT64_MAX ||
	    p.wallet_revision == UINT64_MAX || p.admitted_at <= 0 ||
	    static_cast<uint64_t>(p.admitted_at) > UINT64_MAX / 1000000 ||
	    (p.action == divine_trade_action::purchase ? p.payment >= 0 : p.payment < 0) ||
	    p.payment < -static_cast<int64_t>(INT32_MAX) || p.payment > INT32_MAX ||
	    p.qualifying_quantity > INT32_MAX || p.slots_after.empty() ||
	    p.slots_after.size() > MAXSLOTS || p.market_after.empty() ||
	    p.market_after.size() > p.slots_after.size() ||
	    !divine_trade_book_valid(p.book_after) || !p.book_after.revision ||
	    p.book_after.revision < p.book_revision ||
	    p.book_after.revision - p.book_revision > MAXSLOTS || p.crew_after.crew_index < 0 ||
	    p.crew_after.crew_index >= MAXCREWS)
		return false;
	if (version >= 3)
	{
		if (p.slots_before.size() != p.slots_after.size())
			return false;
		for (size_t i = 0; i < p.slots_after.size(); ++i)
			if (p.slots_before[i].slot_index != p.slots_after[i].slot_index)
				return false;
	}
	for (int64_t coin : p.wallet_after.amount)
		if (coin < 0 || coin > INT32_MAX)
			return false;
	const auto &crew = p.crew_after;
	for (int32_t chief : { crew.sail_chief, crew.guns_chief, crew.repair_chief })
		if (chief < 0 || chief >= MAXCHIEFS)
			return false;
	if (crew.sail_skill_milli < 0 || crew.guns_skill_milli < 0 || crew.repair_skill_milli < 0)
		return false;
	std::set<uint8_t> slots;
	std::set<std::array<uint8_t, 3>> cells;
	for (const auto &slot : p.slots_after)
	{
		if (slot.slot_index >= MAXSLOTS || !slots.insert(slot.slot_index).second ||
		    (p.action == divine_trade_action::purchase ?
			     ((slot.slot_type != SLOT_CARGO && slot.slot_type != SLOT_CONTRABAND) ||
			      slot.item_index < 0 || slot.item_index >= NUM_PORTS ||
			      slot.values[0] <= 0 || slot.values[1] <= 0 ||
			      slot.position != SLOT_HOLD) :
			     (slot.slot_type != SLOT_EMPTY || slot.item_index != -1 ||
			      slot.position != -1 || slot.timer ||
			      slot.values != std::array<int32_t, 5>{ -1, -1, -1, -1, -1 })))
			return false;
	}
	for (const auto &cell : p.market_after)
		if (cell.port >= NUM_PORTS || cell.commodity >= NUM_PORTS ||
		    (cell.goods != divine_trade_goods::cargo &&
		     cell.goods != divine_trade_goods::contraband) ||
		    !std::isfinite(cell.modifier) || cell.modifier < 0 || cell.modifier > 1000 ||
		    cell.price < 0 ||
		    !cells.insert({ cell.port, cell.commodity, static_cast<uint8_t>(cell.goods) })
			     .second)
			return false;
	return true;
}

std::vector<critical_entity_key> keys(const divine_trade_payload &p)
{
	return { { critical_entity_type::player, p.pid },
		 { critical_entity_type::account, p.book_after.account },
		 { critical_entity_type::system, DIVINE_TRADE_MARKET_KEY },
		 { critical_entity_type::ship, p.ship_id } };
}
}

static bool build_version(critical_command *command, critical_operation_id operation,
			  const divine_trade_payload &p, uint16_t version)
{
	if (!command || !valid(p, version) || critical_operation_id_is_zero(operation))
		return false;
	critical_command next = {};
	next.schema_version = CRITICAL_COMMAND_SCHEMA_VERSION;
	next.operation_id = operation;
	next.type = critical_command_type::divine_trade;
	next.payload_version = version;
	next.source_site = critical_source_site::command;
	next.deadline_class = critical_deadline_class::interactive;
	next.accepted_at_usec = static_cast<uint64_t>(p.admitted_at) * 1000000;
	next.keys = keys(p);
	auto &bytes = next.payload;
	append(bytes, static_cast<uint8_t>(p.action));
	append(bytes, p.pid);
	append(bytes, p.ship_id);
	append(bytes, p.ship_owner_pid);
	append(bytes, p.generation);
	append(bytes, p.book_revision);
	append(bytes, p.wallet_revision);
	append(bytes, p.admitted_at);
	append(bytes, p.payment);
	append(bytes, p.qualifying_quantity);
	for (int64_t coin : p.wallet_after.amount)
		append(bytes, coin);
	for (int32_t field :
	     { p.crew_after.crew_index, p.crew_after.sail_skill_milli,
	       p.crew_after.guns_skill_milli, p.crew_after.repair_skill_milli,
	       p.crew_after.sail_chief, p.crew_after.guns_chief, p.crew_after.repair_chief })
		append(bytes, field);
	append(bytes, static_cast<uint8_t>(p.slots_after.size()));
	append(bytes, static_cast<uint8_t>(p.market_after.size()));
	for (const auto &slot : p.slots_after)
	{
		append(bytes, slot.slot_index);
		append(bytes, slot.slot_type);
		append(bytes, slot.item_index);
		append(bytes, slot.position);
		append(bytes, slot.timer);
		for (int32_t value : slot.values)
			append(bytes, value);
	}
	for (const auto &cell : p.market_after)
	{
		append(bytes, cell.port);
		append(bytes, cell.commodity);
		append(bytes, static_cast<uint8_t>(cell.goods));
		append(bytes, std::bit_cast<uint32_t>(cell.modifier));
		append(bytes, cell.price);
	}
	if (version >= 3)
	{
		// Reserved affect field keeps the v3 framing shared with the later
		// recipient-capture bridge; this preparation-only slice writes it empty.
		append(bytes, uint32_t{ 0 });
		for (int32_t field : { p.crew_before.crew_index, p.crew_before.sail_skill_milli,
				       p.crew_before.guns_skill_milli,
				       p.crew_before.repair_skill_milli, p.crew_before.sail_chief,
				       p.crew_before.guns_chief, p.crew_before.repair_chief })
			append(bytes, field);
		for (const auto &slot : p.slots_before)
		{
			append(bytes, slot.slot_index);
			append(bytes, slot.slot_type);
			append(bytes, slot.item_index);
			append(bytes, slot.position);
			append(bytes, slot.timer);
			for (int32_t value : slot.values)
				append(bytes, value);
		}
	}
	std::vector<uint8_t> book;
	if (!divine_trade_book_encode(p.book_after, &book))
		return false;
	bytes.insert(bytes.end(), book.begin(), book.end());
	if (p.action == divine_trade_action::purchase)
	{
		const auto lot = std::find_if(
			p.book_after.lots.begin(), p.book_after.lots.end(), [&](const auto &entry)
			{ return critical_operation_id_equal(entry.purchase, operation); });
		if (p.slots_after.size() != 1 || p.market_after.size() != 1 ||
		    p.book_after.revision - p.book_revision != 1 || p.qualifying_quantity ||
		    lot == p.book_after.lots.end() || lot->invoice_basis != -p.payment ||
		    lot->remaining_quantity != lot->purchased_quantity ||
		    lot->remaining_basis != lot->invoice_basis || lot->ship_id != p.ship_id ||
		    lot->slot != p.slots_after[0].slot_index ||
		    lot->purchased_at != p.admitted_at ||
		    lot->source_port != p.slots_after[0].item_index ||
		    lot->goods != (p.slots_after[0].slot_type == SLOT_CARGO ?
					   divine_trade_goods::cargo :
					   divine_trade_goods::contraband) ||
		    p.market_after[0].port != lot->source_port ||
		    p.market_after[0].commodity != lot->source_port ||
		    p.market_after[0].goods != lot->goods ||
		    p.slots_after[0].values[0] < static_cast<int64_t>(lot->purchased_quantity) ||
		    p.slots_after[0].values[1] < lot->invoice_basis)
			return false;
		if (version >= 3)
		{
			const auto &before = p.slots_before.front();
			const auto &after = p.slots_after.front();
			const bool empty = before.slot_type == SLOT_EMPTY;
			if ((!empty && (before.slot_type != after.slot_type ||
					before.item_index != after.item_index ||
					before.values[0] < 0 || before.values[1] < 0)) ||
			    static_cast<int64_t>(after.values[0]) !=
				    (empty ? 0 : before.values[0]) +
					    static_cast<int64_t>(lot->purchased_quantity) ||
			    static_cast<int64_t>(after.values[1]) !=
				    (empty ? 0 : before.values[1]) + lot->invoice_basis)
				return false;
		}
	}
	if (!critical_command_normalize(&next) || !critical_command_valid(next))
		return false;
	*command = std::move(next);
	return true;
}

bool divine_trade_command_build(critical_command *command, critical_operation_id operation,
				const divine_trade_payload &payload)
{
	return build_version(command, operation, payload, DIVINE_TRADE_PAYLOAD_VERSION);
}

bool divine_trade_command_decode(const critical_command &command, divine_trade_payload *payload)
{
	if (!payload || command.type != critical_command_type::divine_trade ||
	    (command.payload_version != 1 &&
	     command.payload_version != DIVINE_TRADE_PAYLOAD_VERSION) ||
	    !critical_command_valid(command))
		return false;
	divine_trade_payload p;
	const auto &bytes = command.payload;
	size_t offset = 0;
	uint8_t action = 0, count = 0, market_count = 0;
	if (!read(bytes, offset, action) || !read(bytes, offset, p.pid) ||
	    !read(bytes, offset, p.ship_id) || !read(bytes, offset, p.ship_owner_pid) ||
	    !read(bytes, offset, p.generation) || !read(bytes, offset, p.book_revision) ||
	    !read(bytes, offset, p.wallet_revision) || !read(bytes, offset, p.admitted_at) ||
	    !read(bytes, offset, p.payment) || !read(bytes, offset, p.qualifying_quantity))
		return false;
	p.action = static_cast<divine_trade_action>(action);
	for (auto &coin : p.wallet_after.amount)
		if (!read(bytes, offset, coin))
			return false;
	for (int32_t *field :
	     { &p.crew_after.crew_index, &p.crew_after.sail_skill_milli,
	       &p.crew_after.guns_skill_milli, &p.crew_after.repair_skill_milli,
	       &p.crew_after.sail_chief, &p.crew_after.guns_chief, &p.crew_after.repair_chief })
		if (!read(bytes, offset, *field))
			return false;
	if (!read(bytes, offset, count) || !read(bytes, offset, market_count) || !count ||
	    count > MAXSLOTS || !market_count || market_count > count)
		return false;
	p.slots_after.resize(count);
	p.market_after.resize(market_count);
	for (auto &slot : p.slots_after)
	{
		if (!read(bytes, offset, slot.slot_index) || !read(bytes, offset, slot.slot_type) ||
		    !read(bytes, offset, slot.item_index) || !read(bytes, offset, slot.position) ||
		    !read(bytes, offset, slot.timer))
			return false;
		for (int32_t &value : slot.values)
			if (!read(bytes, offset, value))
				return false;
	}
	for (auto &cell : p.market_after)
	{
		uint8_t goods = 0;
		uint32_t modifier = 0;
		if (!read(bytes, offset, cell.port) || !read(bytes, offset, cell.commodity) ||
		    !read(bytes, offset, goods) || !read(bytes, offset, modifier) ||
		    !read(bytes, offset, cell.price))
			return false;
		cell.goods = static_cast<divine_trade_goods>(goods);
		cell.modifier = std::bit_cast<float>(modifier);
	}
	if (command.payload_version >= 3)
	{
		uint32_t affect_bytes = 0;
		if (!read(bytes, offset, affect_bytes) || affect_bytes)
			return false;
		for (int32_t *field :
		     { &p.crew_before.crew_index, &p.crew_before.sail_skill_milli,
		       &p.crew_before.guns_skill_milli, &p.crew_before.repair_skill_milli,
		       &p.crew_before.sail_chief, &p.crew_before.guns_chief,
		       &p.crew_before.repair_chief })
			if (!read(bytes, offset, *field))
				return false;
		p.slots_before.resize(count);
		for (auto &slot : p.slots_before)
		{
			if (!read(bytes, offset, slot.slot_index) ||
			    !read(bytes, offset, slot.slot_type) ||
			    !read(bytes, offset, slot.item_index) ||
			    !read(bytes, offset, slot.position) || !read(bytes, offset, slot.timer))
				return false;
			for (int32_t &value : slot.values)
				if (!read(bytes, offset, value))
					return false;
		}
	}
	if (!divine_trade_book_decode(std::vector<uint8_t>(bytes.begin() + offset, bytes.end()),
				      &p.book_after) ||
	    !valid(p, command.payload_version))
		return false;
	critical_command expected;
	if (!build_version(&expected, command.operation_id, p, command.payload_version))
		return false;
	expected.accepted_at_usec = command.accepted_at_usec;
	if (!critical_command_equal(expected, command))
		return false;
	*payload = std::move(p);
	return true;
}

bool divine_trade_result_encode(const divine_trade_result &r,
				std::array<uint8_t, DIVINE_TRADE_RESULT_BYTES> *bytes)
{
	if (!bytes || !r.pid || r.pid > INT32_MAX || !r.ship_id || r.ship_id > INT32_MAX ||
	    !r.generation || !r.wallet_revision || !r.book_revision ||
	    r.payment < -static_cast<int64_t>(INT32_MAX) || r.payment > INT32_MAX ||
	    r.qualifying_quantity > INT32_MAX)
		return false;
	std::vector<uint8_t> encoded;
	append(encoded, r.pid);
	append(encoded, r.ship_id);
	append(encoded, r.generation);
	append(encoded, r.wallet_revision);
	append(encoded, r.book_revision);
	append(encoded, r.payment);
	append(encoded, r.qualifying_quantity);
	append(encoded, uint32_t{ 0 });
	std::copy(encoded.begin(), encoded.end(), bytes->begin());
	return true;
}

bool divine_trade_result_decode(const uint8_t *bytes, size_t size, divine_trade_result *result)
{
	if (!bytes || size != DIVINE_TRADE_RESULT_BYTES || !result)
		return false;
	const std::vector<uint8_t> encoded(bytes, bytes + size);
	divine_trade_result r;
	size_t offset = 0;
	uint32_t reserved = 0;
	if (!read(encoded, offset, r.pid) || !read(encoded, offset, r.ship_id) ||
	    !read(encoded, offset, r.generation) || !read(encoded, offset, r.wallet_revision) ||
	    !read(encoded, offset, r.book_revision) || !read(encoded, offset, r.payment) ||
	    !read(encoded, offset, r.qualifying_quantity) || !read(encoded, offset, reserved) ||
	    reserved)
		return false;
	std::array<uint8_t, DIVINE_TRADE_RESULT_BYTES> checked;
	if (!divine_trade_result_encode(r, &checked))
		return false;
	*result = r;
	return true;
}

bool divine_trade_book_transition_valid(const divine_trade_book &before,
					const divine_trade_payload &p)
{
	const auto &after = p.book_after;
	if (!divine_trade_book_valid(before) || !valid(p, DIVINE_TRADE_PAYLOAD_VERSION) ||
	    before.revision != p.book_revision)
		return false;
	if (before.revision &&
	    (before.account != after.account || before.boon_id != after.boon_id ||
	     before.first_ship_id != after.first_ship_id ||
	     before.first_full_hold != after.first_full_hold))
		return false;
	if (before.consumed > after.consumed ||
	    after.consumed - before.consumed != p.qualifying_quantity)
		return false;
	if (p.action == divine_trade_action::purchase)
	{
		if (after.revision != before.revision + 1 || p.slots_after.size() != 1 ||
		    p.qualifying_quantity || after.lots.size() != before.lots.size() + 1 ||
		    !std::equal(before.lots.begin(), before.lots.end(), after.lots.begin()) ||
		    (!before.revision && after.first_ship_id != p.ship_id))
			return false;
		const auto &lot = after.lots.back();
		const auto &slot = p.slots_after.front();
		return lot.ship_id == p.ship_id && lot.slot == slot.slot_index &&
		       lot.source_port == slot.item_index && lot.purchased_at == p.admitted_at &&
		       lot.invoice_basis == -p.payment &&
		       lot.remaining_basis == lot.invoice_basis &&
		       lot.remaining_quantity == lot.purchased_quantity &&
		       lot.goods == (slot.slot_type == SLOT_CARGO ? divine_trade_goods::cargo :
								    divine_trade_goods::contraband);
	}
	if (!before.revision)
		return false;
	// Sales clear complete slots. Preserve every other ship/slot's exact lot
	// identity and metadata; one changed slot advances preparation once.
	auto expected = before.lots;
	std::set<uint8_t> changed;
	uint64_t removed = 0;
	std::erase_if(expected,
		      [&](const auto &lot)
		      {
			      const bool selected =
				      lot.ship_id == p.ship_id &&
				      std::any_of(p.slots_after.begin(), p.slots_after.end(),
						  [&](const auto &slot)
						  { return slot.slot_index == lot.slot; });
			      if (selected)
			      {
				      changed.insert(lot.slot);
				      removed += lot.remaining_quantity;
			      }
			      return selected;
		      });
	return expected == after.lots && p.qualifying_quantity <= removed &&
	       after.revision == before.revision + changed.size();
}
