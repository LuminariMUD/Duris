#include <openssl/sha.h>
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

void season_reset()
{
	auto state = activated();
	auto choice = zone(divine_boon_category::experience, 10, 20);
	assert(divine_boon_rotate(&state, H, &choice));
	choice.zones = { 30, 40 };
	assert(divine_boon_rotate(&state, 2 * H, &choice));
	assert(divine_boon_set_paused(&state, true, 2 * H));
	state.history.push_back({ 99, 0, H });
	const auto before = state;
	auto blocked = state;
	blocked.revision = std::numeric_limits<uint64_t>::max();
	const auto overflow = blocked;
	assert(!divine_boon_reset_season(&blocked, 2 * H + 1) && blocked == overflow);
	assert(divine_boon_reset_season(&state, 2 * H + 1));
	assert(!occupied(state) && state.history.empty() && state.recent.size() == 2);
	assert(state.next_id == before.next_id && state.revision == before.revision + 1);
	assert(state.mode == before.mode && state.paused);
	const auto retired = state;
	assert(divine_boon_reset_season(&state, 2 * H + 1) && state == retired);
	assert(!divine_boon_reset_season(&state, -1) && state == retired);
	assert(!divine_boon_reset_season(nullptr, 2 * H));
	assert(divine_boon_set_paused(&state, false, 2 * H + 1));
	assert(divine_boon_rotate(&state, 3 * H, &choice));
	assert(state.slots[0].id == before.next_id);
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
	// Three reserved Experience, three Epic, one Cargo and one PvP.
	for (int32_t index = 2; index <= 8; ++index)
	{
		if (index <= 3)
		{
			choice.category = divine_boon_category::experience;
			choice.zones = { 10 + index, 20 + index };
		}
		else if (index <= 6)
		{
			choice.category = divine_boon_category::epic;
			choice.zones = { 10 + index, 20 + index };
		}
		else if (index == 7)
		{
			choice = {};
			choice.category = divine_boon_category::pvp;
		}
		else
		{
			choice = {};
			choice.category = divine_boon_category::cargo;
			choice.source_port = choice.cargo_commodity = choice.contraband_commodity =
				0;
			choice.destination_port = 1;
		}
		assert(divine_boon_rotate(&state, index * H, &choice));
		assert(occupied(state) == static_cast<size_t>(index));
	}
	assert(occupied(state) == DIVINE_BOON_SLOTS);
	choice = zone(divine_boon_category::experience, 50, 60);
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
	// One hour may start one objective from each pool together.
	auto multi = activated();
	divine_boon_slot pools[3] = { zone(divine_boon_category::epic, 10, 20), {}, {} };
	pools[1].category = divine_boon_category::pvp;
	pools[2] = choice; // A second PvP in the same hour is refused.
	unchanged = multi;
	assert(!divine_boon_rotate(&multi, H, pools, 3) && multi == unchanged);
	pools[2].category = divine_boon_category::cargo;
	pools[2].source_port = pools[2].cargo_commodity = pools[2].contraband_commodity = 0;
	pools[2].destination_port = 2;
	assert(divine_boon_rotate(&multi, H, pools, 3) && occupied(multi) == 3);
	assert(multi.slots[0].starts_at == H && multi.slots[2].starts_at == H);
	assert(multi.slots[2].id == 3 && multi.next_id == 4);
	std::vector<uint8_t> bytes;
	divine_boon_state decoded;
	assert(divine_boon_state_encode(multi, &bytes) &&
	       divine_boon_state_decode(bytes, &decoded) && decoded == multi);
	assert(divine_boon_rotate(&multi, 2 * H, pools, 0)); // No choices consumes the hour.
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

void bounded_retired_history()
{
	auto state = activated();
	divine_boon_slot choice;
	choice.category = divine_boon_category::cargo;
	choice.source_port = choice.cargo_commodity = choice.contraband_commodity = 0;
	choice.destination_port = 1;
	for (unsigned index = 1; index <= 24; ++index)
	{
		choice.category = index % 2 ? divine_boon_category::cargo :
					      divine_boon_category::pvp;
		if (choice.category == divine_boon_category::pvp)
			choice.source_port = choice.destination_port = choice.cargo_commodity =
				choice.contraband_commodity = -1;
		else
		{
			choice.source_port = choice.cargo_commodity = choice.contraband_commodity =
				0;
			choice.destination_port = 1;
		}
		assert(divine_boon_rotate(&state, index * H, &choice));
		assert(divine_boon_replace(&state, 0, index * H + 1));
	}
	assert(state.recent.size() == DIVINE_BOON_RECENT_MAX &&
	       state.recent.front().objective.id == 9 && state.recent.back().objective.id == 24);
	std::vector<uint8_t> bytes;
	divine_boon_state restored;
	assert(divine_boon_state_encode(state, &bytes) &&
	       divine_boon_state_decode(bytes, &restored) && state == restored);
}

void legacy_shared_slot_reconciliation()
{
	auto state = activated();
	auto original = zone(divine_boon_category::experience, 18, -1);
	assert(divine_boon_rotate(&state, H, &original));
	// Recreate a VALID old persisted snapshot: the opposite faction's
	// second slot also targeted zone 18 but shared no same-side field.
	divine_boon_slot other = zone(divine_boon_category::experience, -1, 18);
	other.id = state.next_id++;
	other.starts_at = 2 * H;
	other.expires_at = 10 * H;
	state.slots[1] = other;
	state.last_opportunity = 2 * H;
	assert(divine_boon_state_valid(state) && occupied(state) == 2);
	assert(divine_boon_reconcile(&state, 2 * H + 1));
	assert(occupied(state) == 1 && state.slots[0].id);
	assert(state.recent.size() == 1 && state.recent[0].objective.id == other.id);
	assert(state.history.size() == 2);
	for (const auto &entry : state.history)
		assert(entry.zone == 18);
	std::vector<uint8_t> bytes;
	divine_boon_state restored;
	assert(divine_boon_state_encode(state, &bytes));
	assert(divine_boon_state_decode(bytes, &restored) && restored == state);

	// The old Evil-only target is NOT reserved by the new shared system.
	auto legacy = activated();
	original.zones = { 18, 20 };
	assert(divine_boon_rotate(&legacy, H, &original));
	auto fresh = zone(divine_boon_category::epic, 20, 20);
	assert(divine_boon_rotate(&legacy, 2 * H, &fresh));
	assert(occupied(legacy) == 2);
	assert(divine_boon_replace(&legacy, 0, 2 * H + 1));
	assert(legacy.history.size() == 2);
	for (const auto &entry : legacy.history)
		assert(entry.zone == 18); // Not the stale Evil target 20.
}

void doubled_pve_history_capacity()
{
	auto state = activated();
	// Generate and replace one of each PvE category every hour throughout
	// the 12-hour repeat window. Each retirement records two side entries.
	for (int64_t hour = 1; hour <= 12; ++hour)
	{
		divine_boon_slot choices[2] = {
			zone(divine_boon_category::experience, 1000 + 2 * hour, 1000 + 2 * hour),
			zone(divine_boon_category::epic, 1001 + 2 * hour, 1001 + 2 * hour)
		};
		assert(divine_boon_rotate(&state, hour * H, choices, 2));
		assert(divine_boon_replace(&state, 0, hour * H + 1));
		assert(divine_boon_replace(&state, 1, hour * H + 1));
	}
	assert(state.history.size() == 48 && state.history.size() <= DIVINE_BOON_HISTORY_MAX);
	std::vector<uint8_t> bytes;
	divine_boon_state restored;
	assert(divine_boon_state_encode(state, &bytes));
	assert(bytes.size() <= 4096);
	assert(divine_boon_state_decode(bytes, &restored) && restored == state);

	// All 64 entries still fit within the unchanged v2 wire payload bound.
	for (int index = 0; index < 16; ++index)
		state.history.push_back({ 3000 + index, 0, 12 * H + 1 });
	assert(state.history.size() == DIVINE_BOON_HISTORY_MAX);
	assert(divine_boon_state_valid(state));
	assert(divine_boon_state_encode(state, &bytes));
	assert(bytes.size() <= 4096);
	assert(divine_boon_state_decode(bytes, &restored) && restored == state);
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
	assert(state.recent.size() == 1 && restored.recent == state.recent);
	auto old = bytes;
	// v1 ended after the original zone history; remove v2 recent records and checksum.
	const size_t recent_bytes = 4 + state.recent.size() * (49 + 8);
	old.resize(old.size() - SHA256_DIGEST_LENGTH - recent_bytes);
	old[8] = 1;
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(old.data(), old.size(), digest);
	old.insert(old.end(), digest, digest + SHA256_DIGEST_LENGTH);
	divine_boon_state legacy;
	assert(divine_boon_state_decode(old, &legacy) && legacy.recent.empty());
	legacy.recent = state.recent;
	assert(legacy == state);

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
	season_reset();
	rotation();
	targets_and_categories();
	pause_restart_and_clock();
	snapshots_and_invalid_state();
	bounded_retired_history();
	legacy_shared_slot_reconciliation();
	doubled_pve_history_capacity();
	std::cout << "Divine Boon rotation, limits, expiry, clock and snapshot contracts passed\n";
}
