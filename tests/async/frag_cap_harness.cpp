#include "combat/frag_cap.h"
#include <cassert>
#include <iostream>
#include <set>
#include <utility>
#include <openssl/sha.h>

constexpr int64_t start = INT64_C(1800000000000000);
constexpr int64_t hour = FRAG_CAP_HOUR;
using side = frag_cap_side;
frag_cap_state fresh()
{
	frag_cap_state state;
	assert(frag_cap_adopt(&state, 30, 0, start));
	assert(state.level == 31 && state.deadline == start + 72 * hour);
	return state;
}
void award(frag_cap_state &state, side faction, int64_t points, int64_t at)
{
	const frag_cap_award credit{ faction, points };
	assert(frag_cap_apply(&state, at, at, &credit, 1));
}
int main()
{
	// Compare every reachable compressed state against the literal two-cap rule.
	std::set<std::pair<int, int>> states{ { 31, 0 } };
	size_t count = 0;
	for (int level = 31; level < 56; ++level)
	{
		std::set<std::pair<int, int>> next;
		for (auto [top, leader] : states)
			for (auto scores : { std::pair<uint64_t, uint64_t>{ 0, 0 },
					     { 100, 100 },
					     { 1, 0 },
					     { 0, 1 },
					     { 20, 10 },
					     { 10, 20 },
					     { 100, 0 } })
			{
				auto state = fresh();
				state.level = top;
				state.advantage = static_cast<side>(leader);
				state.earned = { scores.first, scores.second };
				const int good = frag_cap_for_side(state, side::good),
					  evil = frag_cap_for_side(state, side::evil);
				assert(frag_cap_settle(&state, state.deadline));
				const int g = frag_cap_for_side(state, side::good),
					  e = frag_cap_for_side(state, side::evil);
				const int n = top + 1;
				const bool circle = (n - 1) % 5 == 0;
				const int expected_g = circle			    ? n :
						       scores.first > scores.second ? n :
						       scores.second > scores.first ? n - 1 :
										      good + 1;
				const int expected_e = circle			    ? n :
						       scores.second > scores.first ? n :
						       scores.first > scores.second ? n - 1 :
										      evil + 1;
				assert(g == expected_g && e == expected_e && g >= good &&
				       e >= evil && abs(g - e) <= 1);
				assert(state.earned == (std::array<uint64_t, 2>{}));
				next.emplace(state.level, static_cast<int>(state.advantage));
				++count;
			}
		states = next;
	}
	assert(count == 455 && states == (std::set<std::pair<int, int>>{ { 56, 0 } }));
	std::cout
		<< "PASS 455 native transitions: winners, sub-frag scores, ties, one-level gap and every circle\n";

	auto state = fresh();
	std::array<frag_cap_award, 20> group;
	group.fill({ side::evil, 5 });
	assert(frag_cap_apply(&state, start, start, group.data(), group.size()));
	assert(state.earned[1] == 100 && state.level == 31);
	award(state, side::good, 50, start + hour);
	award(state, side::good, 60, start + 47 * hour);
	award(state, side::evil, -1000, start + 48 * hour);
	award(state, side::none, 1000, start + 48 * hour);
	assert(state.earned[0] == 110 && state.earned[1] == 100);
	assert(frag_cap_settle(&state, start + 72 * hour - 1) && state.level == 31);
	assert(frag_cap_settle(&state, start + 72 * hour));
	assert(frag_cap_for_side(state, side::good) == 32 &&
	       frag_cap_for_side(state, side::evil) == 31);
	const auto before = state;
	assert(frag_cap_settle(&state, start + 72 * hour) && state == before);
	assert(frag_cap_settle(&state, start + 144 * hour));
	assert(frag_cap_for_side(state, side::good) == 33 &&
	       frag_cap_for_side(state, side::evil) == 32);
	std::cout
		<< "PASS pooled events, changing provisional leader, full counting, ignored losses and no early unlock\n";

	state = fresh();
	award(state, side::evil, 1, start + 72 * hour);
	assert(state.level == 32 && state.advantage == side::none && state.earned[1] == 1);
	const frag_cap_award late{ side::good, 1000 };
	const auto boundary = state;
	assert(frag_cap_apply(&state, start + 72 * hour - 1, start + 72 * hour + 1, &late, 1) &&
	       state == boundary);
	assert(frag_cap_apply(&state, start - 1, start + 72 * hour + 1, &late, 1) &&
	       state == boundary);
	assert(frag_cap_apply(&state, start + 73 * hour, start + 72 * hour + 1, &late, 1) &&
	       state == boundary);
	assert(frag_cap_settle(&state, start + 216 * hour));
	assert(state.level == 34 && state.advantage == side::evil && state.earned[1] == 0);
	assert(frag_cap_settle(&state, start + 75 * 24 * hour));
	assert(state.level == 56 && !state.deadline && state.advantage == side::none);
	const auto terminal = state;
	award(state, side::good, 100, start + 100 * 24 * hour);
	assert(state == terminal);
	std::cout
		<< "PASS admission boundary, late/cutover/future exclusion, missed zero-score ties and 75-day ceiling\n";

	assert(frag_cap_adopt(&state, 25, start - hour, start) && state.level == 31);
	assert(frag_cap_adopt(&state, 40, start + 12 * hour, start) &&
	       state.deadline == start + 12 * hour);
	assert(frag_cap_adopt(&state, 40, start + 100 * hour, start) &&
	       state.deadline == start + 72 * hour);
	assert(frag_cap_adopt(&state, 40, start - 100 * 24 * hour, start) && state.level == 41 &&
	       state.round_start == start);
	assert(frag_cap_adopt(&state, 56, start, start) && !state.deadline);
	state = fresh();
	const frag_cap_policy changed{ 36 * hour };
	assert(frag_cap_settle(&state, start + 72 * hour, changed) &&
	       state.deadline == start + 108 * hour);
	std::cout << "PASS legacy adoption and frozen active deadline\n";

	state = fresh();
	state.earned[0] = UINT64_MAX;
	const auto full = state;
	const frag_cap_award overflow{ side::good, 1 };
	assert(!frag_cap_apply(&state, start, start, &overflow, 1) && state == full);
	const frag_cap_award invalid{ static_cast<side>(3), 1 };
	assert(!frag_cap_apply(&state, start, start, &invalid, 1) && state == full);
	assert(!frag_cap_settle(&state, INT64_MAX) && state == full);
	assert(!frag_cap_apply(&state, start, start, nullptr, 1) && state == full);
	state.revision = UINT64_MAX;
	const auto exhausted = state;
	assert(!frag_cap_settle(&state, state.deadline) && state == exhausted);
	state = full;
	std::vector<uint8_t> bytes;
	assert(frag_cap_state_encode(state, &bytes) && bytes.size() == FRAG_CAP_MAX_BYTES);
	frag_cap_state decoded;
	assert(frag_cap_state_decode(bytes, &decoded) && decoded == state);
	for (size_t i = 0; i < bytes.size(); ++i)
	{
		auto corrupt = bytes;
		corrupt[i] ^= 1;
		assert(!frag_cap_state_decode(corrupt, &decoded) && decoded == state);
	}
	for (size_t size = 0; size < bytes.size(); ++size)
		assert(!frag_cap_state_decode({ bytes.begin(), bytes.begin() + size }, &decoded));
	bytes[8] = 1;
	SHA256(bytes.data(), bytes.size() - SHA256_DIGEST_LENGTH,
	       bytes.data() + bytes.size() - SHA256_DIGEST_LENGTH);
	assert(!frag_cap_state_decode(bytes, &decoded));
	state = fresh();
	state.advantage = side::good;
	assert(!frag_cap_state_valid(state));
	std::cout
		<< "PASS fixed 97-byte versioned codec, corruption, overflow and atomic failure\n";
}
