#include "combat/frag_cap.h"

#include <array>
#include <cassert>
#include <iostream>
#include <limits>
#include <openssl/sha.h>

namespace
{
constexpr int64_t start = INT64_C(1800000000000000);
constexpr int64_t hour = FRAG_CAP_HOUR;

frag_cap_state fresh()
{
	frag_cap_state state;
	assert(frag_cap_adopt(&state, 30, 0, start));
	assert(state.level == 31 && state.credit_cutoff == start && state.round_start == start);
	assert(state.earliest_at == start + 48 * hour && state.automatic_at == start + 72 * hour);
	assert(frag_cap_state_valid(state));
	return state;
}

void award(frag_cap_state &state, uint32_t pid, int64_t points, int64_t at)
{
	const frag_cap_award value = { pid, points };
	assert(frag_cap_apply(&state, at, at, &value, 1));
}

void timing()
{
	for (const int64_t qualifying_hour : { 1, 47, 48, 60 })
	{
		auto state = fresh();
		const int64_t at = start + qualifying_hour * hour;
		award(state, 1, 20, at);
		const int64_t due = start + std::max(INT64_C(48), qualifying_hour) * hour;
		if (qualifying_hour < 48)
		{
			assert(state.level == 31 && state.qualified_at == at);
			assert(frag_cap_due_at(state) == due);
			const auto secured = state;
			award(state, 1, 100, at + 1);
			assert(state ==
			       secured); // No later kill changes Q or banks a future round.
			assert(frag_cap_settle(&state, due - 1));
			assert(state.level == 31);
			assert(frag_cap_settle(&state, due));
		}
		assert(state.level == 32 && state.round_start == due && state.earned.empty());
		assert(!state.qualified_at && state.earliest_at == due + 48 * hour);
	}
	std::cout << "PASS qualification at hours 1/47/48/60 and immutable confirmation time\n";
}

void contribution()
{
	auto state = fresh();
	award(state, 1, 19, start);
	award(state, 2, 19, start);
	award(state, 1, -100, start + 1);
	award(state, 1, 0, start + 1);
	assert(!state.qualified_at && state.earned.at(1) == 19 && state.earned.at(2) == 19);
	award(state, 1, 1, start + 2);
	assert(state.qualified_at == start + 2 && state.earned.empty());
	state = fresh();
	std::array<frag_cap_award, 20> group;
	for (size_t index = 0; index < group.size(); ++index)
		group[index] = { static_cast<uint32_t>(index + 1), 5 };
	assert(frag_cap_apply(&state, start, start, group.data(), group.size()));
	assert(state.earned.size() == 20 && !state.qualified_at);
	for (int count = 0; count < 3; ++count)
		award(state, 1, 5, start + 1 + count);
	assert(state.qualified_at == start + 3 && state.earned.empty());
	state = fresh();
	award(state, 1, 10, start);
	award(state, 1, 10, start + 1);
	assert(state.qualified_at == start + 1);
	state = fresh();
	award(state, 1, std::numeric_limits<int64_t>::max(), start);
	assert(state.qualified_at == start); // No addition overflow for large legitimate deltas.
	std::cout
		<< "PASS 19/20 boundary, same-PID accumulation, non-pooling, negative awards, full group\n";
}

void boundaries()
{
	auto state = fresh();
	const std::array<frag_cap_award, 3> group = { { { 1, 100 }, { 2, 100 }, { 3, 19 } } };
	assert(frag_cap_apply(&state, start + 60 * hour, start + 60 * hour, group.data(),
			      group.size()));
	assert(state.level == 32 && state.earned.empty() && !state.qualified_at);
	const auto next = state;
	assert(frag_cap_apply(&state, start + 59 * hour, start + 61 * hour, group.data(),
			      group.size()));
	assert(state == next); // Late delivery keeps rewards but cannot credit the next round.
	state = fresh();
	award(state, 1, 19, start + 71 * hour);
	award(state, 1, 1, start + 72 * hour);
	assert(state.level == 32 && state.earned.at(1) == 1 && !state.qualified_at);
	state = fresh();
	assert(frag_cap_apply(&state, start + 72 * hour - 1, start + 72 * hour, group.data(),
			      group.size()));
	assert(state.level == 32 && state.earned.empty());
	const auto settled = state;
	assert(frag_cap_apply(&state, start - 1, start + 73 * hour, group.data(), group.size()));
	assert(state == settled);
	assert(frag_cap_apply(&state, start + 75 * hour, start + 73 * hour, group.data(),
			      group.size()));
	assert(state == settled); // Pre-cutover and future-invalid admissions are excluded.
	std::cout
		<< "PASS exact boundary, whole-event consumption, delayed/pre-cutover/future exclusions\n";
}

void catchup()
{
	auto quiet = fresh();
	assert(frag_cap_settle(&quiet, start + 75 * 24 * hour - 1));
	assert(quiet.level == 55);
	assert(frag_cap_settle(&quiet, start + 75 * 24 * hour));
	assert(quiet.level == 56 && quiet.round_start == start + 75 * 24 * hour);
	const auto terminal = quiet;
	award(quiet, 1, 100, start + 100 * 24 * hour);
	assert(quiet == terminal && frag_cap_due_at(quiet) == 0);
	auto active = fresh();
	for (int level = 31; level < 56; ++level)
	{
		award(active, 1, 20, active.round_start + hour);
		assert(active.level == level);
		assert(frag_cap_settle(&active, active.earliest_at));
		assert(active.level == level + 1);
	}
	assert(active.round_start == start + 50 * 24 * hour);
	auto late = fresh();
	award(late, 1, 20, start + hour);
	assert(frag_cap_settle(&late, start + 48 * hour + 3 * 72 * hour));
	assert(late.level == 35 && late.round_start == start + 48 * hour + 3 * 72 * hour);
	std::cout << "PASS downtime catch-up, 50/75-day schedules, ceiling, no reused credit\n";
}

void adoption_and_policy()
{
	frag_cap_state state;
	assert(frag_cap_adopt(&state, 25, start - hour, start));
	assert(state.level == 31 && state.automatic_at == start + 72 * hour);
	assert(frag_cap_adopt(&state, 36, start + 30 * hour, start));
	assert(state.level == 36 && state.automatic_at == start + 30 * hour);
	assert(state.earliest_at == start + 6 * hour);
	assert(frag_cap_adopt(&state, 36, start + 12 * hour, start));
	assert(state.earliest_at == start);
	assert(frag_cap_adopt(&state, 36, start + 100 * hour, start));
	assert(state.automatic_at == start + 72 * hour);
	assert(frag_cap_adopt(&state, 36, start - 100 * 24 * hour, start));
	assert(state.level == 37 && state.round_start == start);
	assert(state.automatic_at == start + 72 * hour);
	assert(frag_cap_adopt(&state, 55, start, start));
	assert(state.level == 56 && !state.automatic_at);
	assert(frag_cap_adopt(&state, 56, start, start));
	assert(state.level == 56 && !state.automatic_at);
	state = fresh();
	const frag_cap_policy changed = { 24 * hour, 36 * hour, 10 };
	const frag_cap_award credit = { 1, 10 };
	assert(frag_cap_apply(&state, start + hour, start + hour, &credit, 1, changed));
	assert(state.target_points == 20 && !state.qualified_at);
	assert(frag_cap_settle(&state, start + 72 * hour, changed));
	assert(state.level == 32 && state.earliest_at == start + 96 * hour);
	assert(state.automatic_at == start + 108 * hour && state.target_points == 10);
	std::cout
		<< "PASS legacy adoption below/above 31, shortened/expired deadlines, terminal state, frozen policy\n";
}

void codec_and_limits()
{
	auto state = fresh();
	award(state, 1, 19, start);
	std::vector<uint8_t> bytes;
	assert(frag_cap_state_encode(state, &bytes));
	assert(bytes.size() == 108);
	frag_cap_state decoded;
	assert(frag_cap_state_decode(bytes, &decoded) && decoded == state);
	const auto before = decoded;
	for (size_t index = 0; index < bytes.size(); ++index)
	{
		auto corrupt = bytes;
		corrupt[index] ^= 1;
		assert(!frag_cap_state_decode(corrupt, &decoded) && decoded == before);
	}
	for (size_t length = 0; length < bytes.size(); ++length)
		assert(!frag_cap_state_decode({ bytes.begin(), bytes.begin() + length }, &decoded));
	bytes.push_back(0);
	assert(!frag_cap_state_decode(bytes, &decoded));
	// Even correctly checksummed unsupported versions/invalid state are rejected.
	assert(frag_cap_state_encode(state, &bytes));
	bytes[8] = 2;
	SHA256(bytes.data(), bytes.size() - SHA256_DIGEST_LENGTH,
	       bytes.data() + bytes.size() - SHA256_DIGEST_LENGTH);
	assert(!frag_cap_state_decode(bytes, &decoded));
	state = fresh();
	for (uint32_t pid = 1; pid <= FRAG_CAP_MAX_CONTRIBUTORS; ++pid)
		state.earned.emplace(pid, 1);
	assert(frag_cap_state_encode(state, &bytes));
	assert(bytes.size() == FRAG_CAP_MAX_BYTES);
	assert(frag_cap_state_decode(bytes, &decoded) && decoded == state);
	const auto full = state;
	const frag_cap_award overflow = { FRAG_CAP_MAX_CONTRIBUTORS + 1, 1 };
	assert(!frag_cap_apply(&state, start, start, &overflow, 1) && state == full);
	assert(!frag_cap_settle(&state, start - 1) && state == full);
	assert(!frag_cap_settle(&state, std::numeric_limits<int64_t>::max()) && state == full);
	assert(!frag_cap_apply(&state, start, start, nullptr, 1) && state == full);
	state.revision = std::numeric_limits<uint64_t>::max();
	const auto exhausted = state;
	assert(!frag_cap_settle(&state, start + 72 * hour) && state == exhausted);
	state = fresh();
	state.earned.emplace(1, 20);
	assert(!frag_cap_state_valid(state) && !frag_cap_state_encode(state, &bytes));
	state = fresh();
	state.qualified_at = state.automatic_at;
	assert(!frag_cap_state_valid(state));
	std::cout
		<< "PASS bounded codec, corruption/truncation, 65536 contributors, atomic failure and overflow\n";
}
}

int main()
{
	timing();
	contribution();
	boundaries();
	catchup();
	adoption_and_policy();
	codec_and_limits();
}
