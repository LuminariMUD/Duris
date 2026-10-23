#include "economy/divine_trade.h"

#include "ships/ships.h"

#include <algorithm>
#include <limits>
#include <map>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <set>

namespace
{
constexpr std::array<uint8_t, 8> magic = { 'D', 'U', 'R', 'D', 'T', 'R', '0', '1' };
constexpr uint32_t version = 1;
constexpr size_t header_bytes = 56;
constexpr size_t lot_bytes = 58;
constexpr uint64_t maximum_value = std::numeric_limits<int32_t>::max();

bool goods_valid(divine_trade_goods goods)
{
	return goods == divine_trade_goods::cargo || goods == divine_trade_goods::contraband;
}

bool port_valid(int port)
{
	return port >= 0 && port < NUM_PORTS;
}

bool boon_valid(const divine_boon_slot &boon)
{
	return boon.id && boon.category == divine_boon_category::cargo && boon.starts_at >= 0 &&
	       boon.expires_at > boon.starts_at && port_valid(boon.source_port) &&
	       port_valid(boon.destination_port) && boon.source_port != boon.destination_port &&
	       boon.cargo_commodity == boon.source_port &&
	       boon.contraband_commodity == boon.source_port;
}

bool empty(const divine_trade_book &book)
{
	return !book.revision && !book.account && !book.boon_id && !book.first_ship_id &&
	       !book.first_full_hold && !book.consumed && book.lots.empty();
}

// Lots must fit inside the caller's slot. A slot holding only lots must carry
// exactly their basis, or emptying it would leave basis on zero crates.
bool slot_totals(const divine_trade_book &book, uint32_t ship, uint8_t slot,
		 divine_trade_goods goods, int source, uint32_t slot_quantity, int64_t slot_basis,
		 uint64_t *quantity, int64_t *basis)
{
	*quantity = 0;
	*basis = 0;
	for (const auto &lot : book.lots)
		if (lot.ship_id == ship && lot.slot == slot)
		{
			if (lot.goods != goods || lot.source_port != source)
				return false;
			*quantity += lot.remaining_quantity;
			*basis += lot.remaining_basis;
			if (*quantity > maximum_value ||
			    *basis > static_cast<int64_t>(maximum_value))
				return false;
		}
	return *quantity <= slot_quantity && *basis <= slot_basis &&
	       (*quantity < slot_quantity || *basis == slot_basis);
}

// All quantities and slot bases fit their existing signed 32-bit ship fields.
// Their product fits uint64_t; each split's remainder stays with the unsold lot.
int64_t take_basis(int64_t basis, uint32_t take, uint32_t quantity)
{
	return static_cast<int64_t>(static_cast<uint64_t>(basis) * take / quantity);
}

template <typename T> void append(std::vector<uint8_t> &bytes, T value)
{
	for (size_t byte = 0; byte < sizeof(T); ++byte)
		bytes.push_back(static_cast<uint8_t>(static_cast<uint64_t>(value) >> (byte * 8)));
}

template <typename T> bool read(const std::vector<uint8_t> &bytes, size_t &offset, T &value)
{
	if (offset > bytes.size() || bytes.size() - offset < sizeof(T))
		return false;
	uint64_t decoded = 0;
	for (size_t byte = 0; byte < sizeof(T); ++byte)
		decoded |= static_cast<uint64_t>(bytes[offset++]) << (byte * 8);
	value = static_cast<T>(decoded);
	return true;
}
}

bool divine_trade_book_valid(const divine_trade_book &book)
{
	if (empty(book))
		return true;
	if (!book.revision || !book.account || !book.boon_id || !book.first_ship_id ||
	    !book.first_full_hold || book.first_full_hold > maximum_value ||
	    book.consumed > 3ULL * book.first_full_hold ||
	    book.lots.size() >
		    (CRITICAL_COMMAND_MAX_PAYLOAD_BYTES - header_bytes - SHA256_DIGEST_LENGTH) /
			    lot_bytes)
		return false;
	std::set<std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES>> purchases;
	struct slot_state
	{
		divine_trade_goods goods;
		int source;
		uint64_t quantity;
		int64_t basis;
	};
	std::map<std::pair<uint32_t, uint8_t>, slot_state> slots;
	for (const auto &lot : book.lots)
	{
		if (critical_operation_id_is_zero(lot.purchase) ||
		    !purchases.insert(lot.purchase.bytes).second || !lot.ship_id ||
		    lot.slot >= MAXSLOTS || !goods_valid(lot.goods) ||
		    !port_valid(lot.source_port) || lot.purchased_at <= 0 ||
		    !lot.purchased_quantity || lot.purchased_quantity > maximum_value ||
		    !lot.remaining_quantity || lot.remaining_quantity > lot.purchased_quantity ||
		    lot.invoice_basis <= 0 ||
		    lot.invoice_basis > static_cast<int64_t>(maximum_value) ||
		    lot.remaining_basis < 0 || lot.remaining_basis > lot.invoice_basis)
			return false;
		auto [found, inserted] =
			slots.try_emplace(std::make_pair(lot.ship_id, lot.slot),
					  slot_state{ lot.goods, lot.source_port, 0, 0 });
		auto &slot = found->second;
		if (!inserted && (slot.goods != lot.goods || slot.source != lot.source_port))
			return false;
		slot.quantity += lot.remaining_quantity;
		slot.basis += lot.remaining_basis;
		if (slot.quantity > maximum_value ||
		    slot.basis > static_cast<int64_t>(maximum_value))
			return false;
	}
	return true;
}

bool divine_trade_prepare_purchase(const divine_trade_book &before, const divine_boon_slot &boon,
				   const divine_trade_purchase &purchase, divine_trade_book *after)
{
	if (!after || !divine_trade_book_valid(before) || !boon_valid(boon) ||
	    critical_operation_id_is_zero(purchase.operation) || !purchase.account ||
	    !purchase.ship_id || !purchase.full_hold || purchase.full_hold > maximum_value ||
	    purchase.slot >= MAXSLOTS || !goods_valid(purchase.goods) ||
	    purchase.source_port != boon.source_port || purchase.at <= boon.starts_at ||
	    purchase.at >= boon.expires_at || !purchase.quantity ||
	    purchase.quantity > maximum_value || purchase.paid <= 0 ||
	    purchase.paid > static_cast<int64_t>(maximum_value) ||
	    purchase.slot_quantity_before > maximum_value - purchase.quantity ||
	    purchase.slot_basis_before < 0 ||
	    purchase.slot_basis_before > static_cast<int64_t>(maximum_value) - purchase.paid ||
	    before.revision == std::numeric_limits<uint64_t>::max() ||
	    (!empty(before) && (before.account != purchase.account || before.boon_id != boon.id)))
		return false;
	uint64_t tracked = 0;
	int64_t basis = 0;
	if (!slot_totals(before, purchase.ship_id, purchase.slot, purchase.goods,
			 purchase.source_port, purchase.slot_quantity_before,
			 purchase.slot_basis_before, &tracked, &basis) ||
	    std::any_of(before.lots.begin(), before.lots.end(), [&](const auto &lot)
			{ return critical_operation_id_equal(lot.purchase, purchase.operation); }))
		return false;
	auto next = before;
	if (empty(next))
	{
		next.account = purchase.account;
		next.boon_id = boon.id;
		next.first_ship_id = purchase.ship_id;
		next.first_full_hold = purchase.full_hold;
	}
	++next.revision;
	next.lots.push_back({ purchase.operation, purchase.ship_id, purchase.slot, purchase.goods,
			      purchase.source_port, purchase.at, purchase.quantity,
			      purchase.quantity, purchase.paid, purchase.paid });
	if (!divine_trade_book_valid(next))
		return false;
	*after = std::move(next);
	return true;
}

bool divine_trade_prepare_removal(const divine_trade_book &before, const divine_boon_slot &boon,
				  const divine_trade_removal &removal, divine_trade_book *after,
				  divine_trade_consumption *consumption)
{
	if (!after || !consumption || !divine_trade_book_valid(before) ||
	    before.revision == std::numeric_limits<uint64_t>::max() || !removal.ship_id ||
	    removal.slot >= MAXSLOTS || !goods_valid(removal.goods) ||
	    !port_valid(removal.source_port) || removal.destination_port < -1 ||
	    removal.destination_port >= NUM_PORTS || removal.at < 0 || !removal.quantity ||
	    removal.quantity > removal.slot_quantity_before ||
	    removal.slot_quantity_before > maximum_value || removal.slot_basis_before < 0 ||
	    removal.slot_basis_before > static_cast<int64_t>(maximum_value))
		return false;
	uint64_t tracked = 0;
	int64_t basis = 0;
	if (!slot_totals(before, removal.ship_id, removal.slot, removal.goods, removal.source_port,
			 removal.slot_quantity_before, removal.slot_basis_before, &tracked, &basis))
		return false;
	auto next = before;
	divine_trade_consumption result;
	const auto old_quantity = removal.slot_quantity_before - static_cast<uint32_t>(tracked);
	const auto old_removed = std::min(removal.quantity, old_quantity);
	if (old_quantity)
		result.removed_basis =
			take_basis(removal.slot_basis_before - basis, old_removed, old_quantity);
	uint32_t left = removal.quantity - old_removed;
	const bool qualifies = boon_valid(boon) && boon.id == before.boon_id &&
			       removal.account == before.account &&
			       removal.source_port == boon.source_port &&
			       removal.destination_port == boon.destination_port &&
			       removal.at > boon.starts_at && removal.at < boon.expires_at;
	for (auto &lot : next.lots)
	{
		if (!left)
			break;
		if (lot.ship_id != removal.ship_id || lot.slot != removal.slot)
			continue;
		const uint32_t take = std::min(left, lot.remaining_quantity);
		const int64_t removed_basis =
			take_basis(lot.remaining_basis, take, lot.remaining_quantity);
		if (qualifies && lot.purchased_at > boon.starts_at &&
		    lot.purchased_at <= removal.at)
		{
			const auto allowed = static_cast<uint32_t>(std::min<uint64_t>(
				take, 3ULL * next.first_full_hold - next.consumed));
			result.qualifying_quantity += allowed;
			result.qualifying_basis +=
				take_basis(lot.remaining_basis, allowed, lot.remaining_quantity);
			next.consumed += allowed;
		}
		result.removed_basis += removed_basis;
		lot.remaining_basis -= removed_basis;
		lot.remaining_quantity -= take;
		left -= take;
	}
	if (left)
		return false;
	std::erase_if(next.lots, [](const auto &lot) { return !lot.remaining_quantity; });
	if (next.lots != before.lots)
		++next.revision;
	if (!divine_trade_book_valid(next))
		return false;
	*after = std::move(next);
	*consumption = result;
	return true;
}

bool divine_trade_prepare_invalidation(const divine_trade_book &before, uint32_t ship_id, int slot,
				       divine_trade_book *after)
{
	if (!after || !divine_trade_book_valid(before) || !ship_id || slot < -1 ||
	    slot >= MAXSLOTS || before.revision == std::numeric_limits<uint64_t>::max())
		return false;
	auto next = before;
	std::erase_if(next.lots, [&](const auto &lot)
		      { return lot.ship_id == ship_id && (slot == -1 || lot.slot == slot); });
	if (next.lots != before.lots)
		++next.revision;
	*after = std::move(next);
	return true;
}

bool divine_trade_book_encode(const divine_trade_book &book, std::vector<uint8_t> *bytes)
{
	if (!bytes || !divine_trade_book_valid(book))
		return false;
	std::vector<uint8_t> encoded(magic.begin(), magic.end());
	append(encoded, version);
	append(encoded, book.revision);
	append(encoded, book.account);
	append(encoded, book.boon_id);
	append(encoded, book.first_ship_id);
	append(encoded, book.first_full_hold);
	append(encoded, book.consumed);
	append(encoded, static_cast<uint32_t>(book.lots.size()));
	for (const auto &lot : book.lots)
	{
		encoded.insert(encoded.end(), lot.purchase.bytes.begin(), lot.purchase.bytes.end());
		append(encoded, lot.ship_id);
		append(encoded, lot.slot);
		append(encoded, static_cast<uint8_t>(lot.goods));
		append(encoded, lot.source_port);
		append(encoded, lot.purchased_at);
		append(encoded, lot.purchased_quantity);
		append(encoded, lot.remaining_quantity);
		append(encoded, lot.invoice_basis);
		append(encoded, lot.remaining_basis);
	}
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest;
	SHA256(encoded.data(), encoded.size(), digest.data());
	encoded.insert(encoded.end(), digest.begin(), digest.end());
	*bytes = std::move(encoded);
	return true;
}

bool divine_trade_book_decode(const std::vector<uint8_t> &bytes, divine_trade_book *book)
{
	if (!book || bytes.size() < header_bytes + SHA256_DIGEST_LENGTH ||
	    bytes.size() > CRITICAL_COMMAND_MAX_PAYLOAD_BYTES ||
	    !std::equal(magic.begin(), magic.end(), bytes.begin()))
		return false;
	const size_t payload_size = bytes.size() - SHA256_DIGEST_LENGTH;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest;
	SHA256(bytes.data(), payload_size, digest.data());
	if (CRYPTO_memcmp(digest.data(), bytes.data() + payload_size, digest.size()))
		return false;
	divine_trade_book decoded;
	size_t offset = magic.size();
	uint32_t decoded_version = 0, count = 0;
	if (!read(bytes, offset, decoded_version) || decoded_version != version ||
	    !read(bytes, offset, decoded.revision) || !read(bytes, offset, decoded.account) ||
	    !read(bytes, offset, decoded.boon_id) || !read(bytes, offset, decoded.first_ship_id) ||
	    !read(bytes, offset, decoded.first_full_hold) ||
	    !read(bytes, offset, decoded.consumed) || !read(bytes, offset, count) ||
	    count != (payload_size - header_bytes) / lot_bytes ||
	    payload_size != header_bytes + static_cast<size_t>(count) * lot_bytes)
		return false;
	for (uint32_t index = 0; index < count; ++index)
	{
		divine_trade_lot lot;
		std::copy_n(bytes.begin() + offset, lot.purchase.bytes.size(),
			    lot.purchase.bytes.begin());
		offset += lot.purchase.bytes.size();
		uint8_t goods = 0;
		if (!read(bytes, offset, lot.ship_id) || !read(bytes, offset, lot.slot) ||
		    !read(bytes, offset, goods) || !read(bytes, offset, lot.source_port) ||
		    !read(bytes, offset, lot.purchased_at) ||
		    !read(bytes, offset, lot.purchased_quantity) ||
		    !read(bytes, offset, lot.remaining_quantity) ||
		    !read(bytes, offset, lot.invoice_basis) ||
		    !read(bytes, offset, lot.remaining_basis))
			return false;
		lot.goods = static_cast<divine_trade_goods>(goods);
		decoded.lots.push_back(lot);
	}
	if (offset != payload_size || !divine_trade_book_valid(decoded))
		return false;
	*book = std::move(decoded);
	return true;
}
