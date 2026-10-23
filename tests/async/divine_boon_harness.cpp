#include "economy/divine_boon.h"

#include <cassert>
#include <iostream>
#include <limits>

namespace
{
constexpr int64_t H = DIVINE_BOON_HOUR;

divine_boon_slot zone(divine_boon_category category, int32_t good, int32_t evil)
{
	divine_boon_slot choice;
	choice.category = category;
	choice.zones = { good, evil };
	return choice;
}

divine_boon_state activated(int64_t now = 100)
{
	divine_boon_state state;
	assert(!divine_boon_set_mode(&state, divine_boon_mode::divine, now));
	assert(divine_boon_set_mode(&state, divine_boon_mode::draining, now));
	assert(divine_boon_set_mode(&state, divine_boon_mode::divine, now));
	assert(!divine_boon_set_mode(&state, divine_boon_mode::legacy, now));
	return state;
}

size_t occupied(const divine_boon_state &state)
{
	size_t count = 0;
	for (const auto &slot : state.slots)
		count += slot.id != 0;
	return count;
}

void rotation()
{
	auto state = activated();
	auto choice = zone(divine_boon_category::experience, 10, 20);
	assert(!divine_boon_rotate(&state, H - 1, &choice));
	assert(divine_boon_rotate(&state, H + 2, &choice));
	assert(state.slots[0].starts_at == H && state.slots[0].expires_at == 9 * H);
	assert(state.slots[0].id == 1 && state.next_id == 2);
	assert(divine_boon_active(state.slots[0], H));
	assert(!divine_boon_active(state.slots[0], H - 1));
	assert(!divine_boon_active(state.slots[0], 9 * H));
	const auto committed = state;
	assert(!divine_boon_rotate(&state, H + 30, &choice) && state == committed);
	assert(!divine_boon_rotate(&state, 0, &choice) && state == committed);
	// No three-per-PvE limit, and never more than eight total slots.
	for (int32_t index = 2; index <= 8; ++index)
	{
		choice.zones = { 10 + index, 20 + index };
		assert(divine_boon_rotate(&state, index * H, &choice));
		assert(occupied(state) == static_cast<size_t>(index));
	}
	assert(occupied(state) == DIVINE_BOON_SLOTS);
	choice.zones = { 50, 60 };
	assert(divine_boon_rotate(&state, 9 * H, &choice));
	assert(occupied(state) == DIVINE_BOON_SLOTS && state.slots[0].id == 9);
	assert(state.history.size() == 2 && state.history[0].expired_at == 9 * H);
	assert(divine_boon_reconcile(&state, 30 * H));
	assert(!occupied(state) && state.history.empty());
}

void targets_and_categories()
{
	auto state = activated();
	auto choice = zone(divine_boon_category::experience, 10, 10);
	assert(divine_boon_rotate(&state, H, &choice)); // Contested cross-side zone is valid.
	choice.category = divine_boon_category::epic;
	auto unchanged = state;
	assert(!divine_boon_rotate(&state, 2 * H, &choice) && state == unchanged);
	choice.zones = { 20, -1 }; // No fabricated objective for the unavailable side.
	assert(divine_boon_rotate(&state, 2 * H, &choice));
	choice = {};
	choice.category = divine_boon_category::cargo;
	choice.source_port = 1;
	choice.destination_port = 1;
	choice.cargo_commodity = 0;
	choice.contraband_commodity = 0;
	unchanged = state;
	assert(!divine_boon_rotate(&state, 3 * H, &choice) && state == unchanged);
	choice.destination_port = 2;
	assert(divine_boon_rotate(&state, 3 * H, &choice));
	assert(state.slots[2].expires_at == 7 * H);
	unchanged = state;
	assert(!divine_boon_rotate(&state, 4 * H, &choice) && state == unchanged);
	choice = {};
	choice.category = divine_boon_category::pvp;
	assert(divine_boon_rotate(&state, 4 * H, &choice));
	assert(state.slots[3].expires_at == 8 * H);
	unchanged = state;
	assert(!divine_boon_rotate(&state, 5 * H, &choice) && state == unchanged);
	assert(divine_boon_rotate(&state, 5 * H, nullptr)); // No eligible choice consumes hour.
	assert(!divine_boon_rotate(&state, 5 * H + 1, &choice));
	assert(divine_boon_bonus_percent(divine_boon_category::experience) == 100);
	assert(divine_boon_bonus_percent(divine_boon_category::epic) == 50);
	assert(divine_boon_bonus_percent(divine_boon_category::pvp) == 50);
	assert(divine_boon_bonus_percent(divine_boon_category::cargo) == 25);
}

void pause_restart_and_clock()
{
	auto state = activated();
	auto choice = zone(divine_boon_category::epic, 10, 20);
	const auto running = state;
	assert(!divine_boon_set_paused(&state, false, H));
	assert(state == running); // Redundant resume must not consume the next opportunity.
	assert(divine_boon_rotate(&state, H, &choice));
	assert(divine_boon_set_paused(&state, true, H + 10));
	const auto paused = state;
	assert(!divine_boon_set_paused(&state, true, 2 * H));
	assert(state == paused);
	assert(divine_boon_rotate(&state, 2 * H, &choice));
	assert(occupied(state) == 1);
	assert(divine_boon_reconcile(&state, 9 * H));
	assert(!occupied(state)); // Expiry does not freeze during pause or downtime.
	assert(divine_boon_set_paused(&state, false, 9 * H + 1));
	assert(!divine_boon_rotate(&state, 9 * H + 2, &choice));
	assert(divine_boon_rotate(&state, 10 * H, &choice));
	// A forward clock jump skips elapsed opportunities, with no catch-up spawn.
	assert(divine_boon_rotate(&state, 15 * H, &choice));
	assert(occupied(state) == 1 && state.last_opportunity == 15 * H);
	assert(!divine_boon_rotate(&state, 14 * H, &choice));
	choice.zones = { 30, 40 };
	assert(divine_boon_rotate(&state, 16 * H, &choice));
	assert(occupied(state) == 2);
	// Reboot at an exact boundary still waits until the next scheduled hour.
	assert(divine_boon_reconcile(&state, 17 * H));
	assert(!divine_boon_rotate(&state, 17 * H, &choice));
	assert(divine_boon_replace(&state, 0, 17 * H + 10));
	assert(!divine_boon_rotate(&state, 17 * H + 11, &choice));
	assert(state.history.size() == 2 && state.history[0].expired_at == 17 * H + 10);
	assert(!divine_boon_replace(&state, 0, 17 * H + 12));
	choice.zones = { 10, 20 }; // Soft history preference is the selector's decision.
	assert(divine_boon_rotate(&state, 18 * H, &choice));
	assert(divine_boon_replace(&state, 0, 18 * H + 10));
	assert(state.history.size() == 2 && state.history[0].expired_at == 18 * H + 10);
}

void snapshots_and_invalid_state()
{
	auto state = activated();
	auto choice = zone(divine_boon_category::epic, 10, 20);
	assert(divine_boon_rotate(&state, H, &choice));
	assert(divine_boon_replace(&state, 0, H + 10));
	assert(divine_boon_rotate(&state, 2 * H, &choice));
	std::vector<uint8_t> bytes;
	assert(divine_boon_state_encode(state, &bytes));
	divine_boon_state restored;
	assert(divine_boon_state_decode(bytes, &restored) && restored == state);
	assert(!divine_boon_rotate(&restored, 2 * H + 1, &choice));
	assert(divine_boon_reconcile(&restored, 20 * H));
	assert(!occupied(restored));
	// Every byte, including header/version/revision/times, is authenticated.
	for (size_t index = 0; index < bytes.size(); ++index)
	{
		auto corrupt = bytes;
		corrupt[index] ^= 1;
		auto before = restored;
		assert(!divine_boon_state_decode(corrupt, &restored) && restored == before);
	}
	for (size_t length = 0; length < bytes.size(); ++length)
		assert(!divine_boon_state_decode({ bytes.begin(), bytes.begin() + length },
						 &restored));
	bytes.push_back(0);
	assert(!divine_boon_state_decode(bytes, &restored));
	auto invalid = state;
	invalid.slots[0].expires_at++;
	assert(!divine_boon_state_encode(invalid, &bytes));
	invalid = state;
	invalid.next_id = invalid.slots[0].id;
	assert(!divine_boon_state_valid(invalid));
	invalid = state;
	invalid.last_opportunity++;
	assert(!divine_boon_state_valid(invalid));
	invalid = state;
	invalid.revision = std::numeric_limits<uint64_t>::max();
	const auto before = invalid;
	assert(!divine_boon_rotate(&invalid, 3 * H, nullptr) && invalid == before);
	assert(!divine_boon_reconcile(&state, -1));
	assert(!divine_boon_reconcile(&state, std::numeric_limits<int64_t>::max()));
	assert(!divine_boon_rotate(nullptr, 3 * H, &choice));
	assert(!divine_boon_state_decode(bytes, nullptr));
}
}

int main()
{
	rotation();
	targets_and_categories();
	pause_restart_and_clock();
	snapshots_and_invalid_state();
	std::cout << "Divine Boon rotation, limits, expiry, clock and snapshot contracts passed\n";
}
