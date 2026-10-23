#ifndef CURRENCY_VALUE_H
#define CURRENCY_VALUE_H

#include "economy/currency_command.h"
#include <climits>

inline currency_vector currency_canonical_value(int64_t value)
{
	currency_vector result{};
	constexpr std::array<int64_t, 4> units{ 1, 10, 100, 1000 };
	for (size_t i = units.size(); i-- > 0;)
	{
		result.amount[i] = value / units[i];
		value %= units[i];
	}
	return result;
}

// Same purse semantics as the live facade: positive value adds denominations;
// spending makes change from the total. The facade reports range refusal via
// its existing synchronous completion, so delta preparation itself is unbounded.
inline bool currency_wallet_value_delta(const currency_vector &before, int64_t value,
					currency_vector *delta)
{
	if (!delta || !value || value == INT64_MIN)
		return false;
	if (value > 0)
	{
		*delta = currency_canonical_value(value);
		return true;
	}
	constexpr std::array<int64_t, 4> units{ 1, 10, 100, 1000 };
	int64_t total = 0;
	for (size_t i = 0; i < units.size(); ++i)
	{
		if (before.amount[i] < 0 || before.amount[i] > (INT64_MAX - total) / units[i])
			return false;
		total += before.amount[i] * units[i];
	}
	if (total < -value)
		return false;
	const auto after = currency_canonical_value(total + value);
	for (size_t i = 0; i < units.size(); ++i)
		delta->amount[i] = after.amount[i] - before.amount[i];
	return true;
}

inline bool currency_wallet_after_value(const currency_vector &before, int64_t value,
					currency_vector *after)
{
	if (!after)
		return false;
	for (int64_t coin : before.amount)
		if (coin < 0 || coin > INT_MAX)
			return false;
	currency_vector delta{};
	if (value && !currency_wallet_value_delta(before, value, &delta))
		return false;
	currency_vector result{};
	for (size_t i = 0; i < result.amount.size(); ++i)
	{
		result.amount[i] = before.amount[i] + delta.amount[i];
		if (result.amount[i] < 0 || result.amount[i] > INT_MAX)
			return false;
	}
	*after = result;
	return true;
}

#endif
