#ifndef DIVINE_TRADE_RESULT_H
#define DIVINE_TRADE_RESULT_H
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
constexpr size_t DIVINE_TRADE_RESULT_BYTES = 48;
struct divine_trade_result
{
	uint32_t pid = 0;
	uint32_t ship_id = 0;
	uint64_t generation = 0;
	uint64_t wallet_revision = 0;
	uint64_t book_revision = 0;
	int64_t payment = 0;
	uint32_t qualifying_quantity = 0;
};
inline bool divine_trade_result_encode(const divine_trade_result &r,
				       std::array<uint8_t, DIVINE_TRADE_RESULT_BYTES> *bytes)
{
	if (!bytes || !r.pid || r.pid > INT32_MAX || !r.ship_id || r.ship_id > INT32_MAX ||
	    !r.generation || !r.wallet_revision || !r.book_revision ||
	    r.payment < -static_cast<int64_t>(INT32_MAX) || r.payment > INT32_MAX ||
	    r.qualifying_quantity > INT32_MAX)
		return false;
	bytes->fill(0);
	auto put = [&](size_t offset, uint64_t value, size_t count)
	{
		for (size_t i = 0; i < count; ++i)
			(*bytes)[offset + i] = static_cast<uint8_t>(value >> (i * 8));
	};
	put(0, r.pid, 4);
	put(4, r.ship_id, 4);
	put(8, r.generation, 8);
	put(16, r.wallet_revision, 8);
	put(24, r.book_revision, 8);
	put(32, static_cast<uint64_t>(r.payment), 8);
	put(40, r.qualifying_quantity, 4);
	return true;
}
inline bool divine_trade_result_decode(const uint8_t *bytes, size_t size,
				       divine_trade_result *result)
{
	if (!bytes || size != DIVINE_TRADE_RESULT_BYTES || !result)
		return false;
	auto get = [&](size_t offset, size_t count)
	{
		uint64_t value = 0;
		for (size_t i = 0; i < count; ++i)
			value |= static_cast<uint64_t>(bytes[offset + i]) << (i * 8);
		return value;
	};
	divine_trade_result r{ static_cast<uint32_t>(get(0, 4)),
			       static_cast<uint32_t>(get(4, 4)),
			       get(8, 8),
			       get(16, 8),
			       get(24, 8),
			       static_cast<int64_t>(get(32, 8)),
			       static_cast<uint32_t>(get(40, 4)) };
	std::array<uint8_t, DIVINE_TRADE_RESULT_BYTES> canonical;
	if (!divine_trade_result_encode(r, &canonical) ||
	    !std::equal(canonical.begin(), canonical.end(), bytes))
		return false;
	*result = r;
	return true;
}
#endif
