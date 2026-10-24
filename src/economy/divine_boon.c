#include "economy/divine_boon.h"

#include <algorithm>
#include <limits>
#include <openssl/crypto.h>
#include <openssl/sha.h>

namespace
{
constexpr std::array<uint8_t, 8> magic = { 'D', 'U', 'R', 'D', 'B', 'N', '0', '1' };
constexpr uint32_t version = 2;
constexpr size_t maximum_bytes = 4096;

bool valid_time(int64_t now)
{
	return now >= 0 && now <= std::numeric_limits<int64_t>::max() - 8 * DIVINE_BOON_HOUR;
}

int64_t hour(int64_t now)
{
	return now - now % DIVINE_BOON_HOUR;
}

bool pve(divine_boon_category category)
{
	return category == divine_boon_category::experience ||
	       category == divine_boon_category::epic;
}

bool valid_objective(const divine_boon_slot &slot)
{
	if (!divine_boon_duration(slot.category))
		return false;
	if (slot.category == divine_boon_category::cargo)
		return slot.zones == std::array<int32_t, 2>{ -1, -1 } && slot.source_port >= 0 &&
		       slot.destination_port >= 0 && slot.source_port != slot.destination_port &&
		       slot.cargo_commodity >= 0 && slot.contraband_commodity >= 0;
	if (slot.source_port != -1 || slot.destination_port != -1 || slot.cargo_commodity != -1 ||
	    slot.contraband_commodity != -1)
		return false;
	if (pve(slot.category))
		return slot.zones[0] >= -1 && slot.zones[1] >= -1 &&
		       (slot.zones[0] >= 0 || slot.zones[1] >= 0);
	return slot.zones == std::array<int32_t, 2>{ -1, -1 };
}

void remember(divine_boon_state &state, const divine_boon_slot &slot, int64_t expired_at)
{
	state.recent.push_back({ slot, expired_at });
	if (state.recent.size() > DIVINE_BOON_RECENT_MAX)
		state.recent.erase(state.recent.begin());
	if (!pve(slot.category))
		return;
	for (size_t side = 0; side < slot.zones.size(); ++side)
	{
		if (slot.zones[side] < 0)
			continue;
		auto found = std::find_if(state.history.begin(), state.history.end(),
					  [&](const divine_boon_zone_history &entry) {
						  return entry.side == side &&
							 entry.zone == slot.zones[side];
					  });
		if (found == state.history.end())
			state.history.push_back(
				{ slot.zones[side], static_cast<uint8_t>(side), expired_at });
		else
			found->expired_at = std::max(found->expired_at, expired_at);
	}
}

void expire(divine_boon_state &state, int64_t now)
{
	for (auto &slot : state.slots)
	{
		if (slot.id && now >= slot.expires_at)
		{
			remember(state, slot, slot.expires_at);
			slot = {};
		}
	}
	std::erase_if(state.history,
		      [now](const divine_boon_zone_history &entry) {
			      return now >= entry.expired_at &&
				     now - entry.expired_at >= DIVINE_BOON_REPEAT_WINDOW;
		      });
}

bool publish(divine_boon_state *state, divine_boon_state next)
{
	if (next == *state || next.revision == std::numeric_limits<uint64_t>::max())
		return false;
	++next.revision;
	if (!divine_boon_state_valid(next))
		return false;
	*state = std::move(next);
	return true;
}

template <typename T> void append(std::vector<uint8_t> &bytes, T value)
{
	for (size_t index = 0; index < sizeof(T); ++index)
		bytes.push_back(static_cast<uint8_t>(static_cast<uint64_t>(value) >> (index * 8)));
}

template <typename T> bool read(const std::vector<uint8_t> &bytes, size_t &offset, T &value)
{
	if (offset > bytes.size() || sizeof(T) > bytes.size() - offset)
		return false;
	uint64_t decoded = 0;
	for (size_t index = 0; index < sizeof(T); ++index)
		decoded |= static_cast<uint64_t>(bytes[offset++]) << (index * 8);
	value = static_cast<T>(decoded);
	return true;
}
void append_slot(std::vector<uint8_t> &encoded, const divine_boon_slot &slot)
{
	append(encoded, slot.id);
	append(encoded, static_cast<uint8_t>(slot.category));
	append(encoded, slot.starts_at);
	append(encoded, slot.expires_at);
	for (int32_t zone : slot.zones)
		append(encoded, zone);
	append(encoded, slot.source_port);
	append(encoded, slot.destination_port);
	append(encoded, slot.cargo_commodity);
	append(encoded, slot.contraband_commodity);
}
bool read_slot(const std::vector<uint8_t> &bytes, size_t &offset, divine_boon_slot &slot)
{
	uint8_t category = 0;
	if (!read(bytes, offset, slot.id) || !read(bytes, offset, category) ||
	    !read(bytes, offset, slot.starts_at) || !read(bytes, offset, slot.expires_at))
		return false;
	slot.category = static_cast<divine_boon_category>(category);
	for (int32_t &zone : slot.zones)
		if (!read(bytes, offset, zone))
			return false;
	if (!read(bytes, offset, slot.source_port) || !read(bytes, offset, slot.destination_port) ||
	    !read(bytes, offset, slot.cargo_commodity) ||
	    !read(bytes, offset, slot.contraband_commodity))
		return false;
	return true;
}
}

int64_t divine_boon_duration(divine_boon_category category)
{
	switch (category)
	{
	case divine_boon_category::experience:
	case divine_boon_category::epic:
		return 8 * DIVINE_BOON_HOUR;
	case divine_boon_category::cargo:
	case divine_boon_category::pvp:
		return 4 * DIVINE_BOON_HOUR;
	default:
		return 0;
	}
}

unsigned divine_boon_bonus_percent(divine_boon_category category)
{
	switch (category)
	{
	case divine_boon_category::experience:
		return 100;
	case divine_boon_category::epic:
	case divine_boon_category::pvp:
		return 50;
	case divine_boon_category::cargo:
		return 25;
	default:
		return 0;
	}
}

bool divine_boon_active(const divine_boon_slot &slot, int64_t now)
{
	return slot.id && now >= slot.starts_at && now < slot.expires_at;
}

bool divine_boon_state_valid(const divine_boon_state &state)
{
	if (!state.revision || !state.next_id || !valid_time(state.last_opportunity) ||
	    state.last_opportunity != hour(state.last_opportunity) ||
	    state.mode > divine_boon_mode::divine ||
	    state.history.size() > DIVINE_BOON_HISTORY_MAX ||
	    state.recent.size() > DIVINE_BOON_RECENT_MAX)
		return false;
	for (size_t index = 0; index < state.slots.size(); ++index)
	{
		const auto &slot = state.slots[index];
		if (!slot.id)
		{
			if (slot != divine_boon_slot{})
				return false;
			continue;
		}
		if (state.mode != divine_boon_mode::divine || slot.id >= state.next_id ||
		    !valid_objective(slot) || !valid_time(slot.starts_at) ||
		    slot.starts_at != hour(slot.starts_at) ||
		    slot.starts_at > state.last_opportunity ||
		    slot.expires_at != slot.starts_at + divine_boon_duration(slot.category))
			return false;
		for (size_t previous = 0; previous < index; ++previous)
		{
			const auto &other = state.slots[previous];
			if (!other.id)
				continue;
			if (other.id == slot.id || other.starts_at == slot.starts_at ||
			    (other.category == slot.category && !pve(slot.category)))
				return false;
			if (pve(slot.category) && pve(other.category))
				for (size_t side = 0; side < slot.zones.size(); ++side)
					if (slot.zones[side] >= 0 &&
					    slot.zones[side] == other.zones[side])
						return false;
		}
	}
	for (size_t index = 0; index < state.history.size(); ++index)
	{
		const auto &entry = state.history[index];
		if (entry.zone < 0 || entry.side > 1 || !valid_time(entry.expired_at))
			return false;
		for (size_t previous = 0; previous < index; ++previous)
			if (state.history[previous].zone == entry.zone &&
			    state.history[previous].side == entry.side)
				return false;
	}
	for (size_t index = 0; index < state.recent.size(); ++index)
	{
		const auto &entry = state.recent[index];
		const auto &slot = entry.objective;
		if (!slot.id || slot.id >= state.next_id || !valid_objective(slot) ||
		    !valid_time(slot.starts_at) || slot.starts_at != hour(slot.starts_at) ||
		    slot.expires_at != slot.starts_at + divine_boon_duration(slot.category) ||
		    entry.ended_at < slot.starts_at || entry.ended_at > slot.expires_at)
			return false;
		for (const auto &active : state.slots)
			if (active.id == slot.id)
				return false;
		for (size_t prev = 0; prev < index; ++prev)
			if (state.recent[prev].objective.id == slot.id)
				return false;
	}

	return true;
}

bool divine_boon_set_mode(divine_boon_state *state, divine_boon_mode mode, int64_t now)
{
	if (!state || !valid_time(now) || !divine_boon_state_valid(*state) ||
	    static_cast<unsigned>(mode) != static_cast<unsigned>(state->mode) + 1 ||
	    mode > divine_boon_mode::divine)
		return false;
	auto next = *state;
	next.mode = mode;
	next.last_opportunity = std::max(next.last_opportunity, hour(now));
	return publish(state, std::move(next));
}

bool divine_boon_reconcile(divine_boon_state *state, int64_t now)
{
	if (!state || !valid_time(now) || !divine_boon_state_valid(*state))
		return false;
	auto next = *state;
	expire(next, now);
	next.last_opportunity = std::max(next.last_opportunity, hour(now));
	return publish(state, std::move(next));
}

bool divine_boon_reset_season(divine_boon_state *state, int64_t now)
{
	if (!state || !valid_time(now) || !divine_boon_state_valid(*state))
		return false;
	auto next = *state;
	expire(next, now);
	for (auto &slot : next.slots)
	{
		if (!slot.id)
			continue;
		if (slot.starts_at > now)
			return false;
		remember(next, slot, now);
		slot = {};
	}
	next.history.clear();
	next.last_opportunity = std::max(next.last_opportunity, hour(now));
	return next == *state || publish(state, std::move(next));
}

bool divine_boon_set_paused(divine_boon_state *state, bool paused, int64_t now)
{
	if (!state || !valid_time(now) || !divine_boon_state_valid(*state) ||
	    state->mode != divine_boon_mode::divine || state->paused == paused)
		return false;
	auto next = *state;
	expire(next, now);
	next.paused = paused;
	next.last_opportunity = std::max(next.last_opportunity, hour(now));
	return publish(state, std::move(next));
}

bool divine_boon_replace(divine_boon_state *state, size_t index, int64_t now)
{
	if (!state || !valid_time(now) || !divine_boon_state_valid(*state) ||
	    index >= state->slots.size() || !divine_boon_active(state->slots[index], now))
		return false;
	auto next = *state;
	expire(next, now);
	remember(next, next.slots[index], now);
	next.slots[index] = {};
	next.last_opportunity = std::max(next.last_opportunity, hour(now));
	return publish(state, std::move(next));
}

bool divine_boon_rotate(divine_boon_state *state, int64_t now, const divine_boon_slot *choice)
{
	if (!state || !valid_time(now) || !divine_boon_state_valid(*state) ||
	    state->mode != divine_boon_mode::divine || hour(now) <= state->last_opportunity)
		return false;
	auto next = *state;
	expire(next, now);
	const bool skipped_hours = hour(now) - next.last_opportunity > DIVINE_BOON_HOUR;
	next.last_opportunity = hour(now);
	auto empty = std::find_if(next.slots.begin(), next.slots.end(),
				  [](const divine_boon_slot &slot) { return !slot.id; });
	if (!next.paused && !skipped_hours && choice && empty != next.slots.end())
	{
		if (choice->id || choice->starts_at || choice->expires_at ||
		    !valid_objective(*choice) ||
		    next.next_id == std::numeric_limits<uint64_t>::max())
			return false;
		*empty = *choice;
		empty->id = next.next_id++;
		empty->starts_at = hour(now);
		empty->expires_at = empty->starts_at + divine_boon_duration(empty->category);
	}
	return publish(state, std::move(next));
}

bool divine_boon_state_encode(const divine_boon_state &state, std::vector<uint8_t> *bytes)
{
	if (!bytes || !divine_boon_state_valid(state))
		return false;
	std::vector<uint8_t> encoded(magic.begin(), magic.end());
	append(encoded, version);
	append(encoded, state.revision);
	append(encoded, state.next_id);
	append(encoded, state.last_opportunity);
	append(encoded, static_cast<uint8_t>(state.mode));
	append(encoded, static_cast<uint8_t>(state.paused));
	for (const auto &slot : state.slots)
		append_slot(encoded, slot);
	append(encoded, static_cast<uint32_t>(state.history.size()));
	for (const auto &entry : state.history)
	{
		append(encoded, entry.zone);
		append(encoded, entry.side);
		append(encoded, entry.expired_at);
	}
	append(encoded, static_cast<uint32_t>(state.recent.size()));
	for (const auto &entry : state.recent)
	{
		append_slot(encoded, entry.objective);
		append(encoded, entry.ended_at);
	}

	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(encoded.data(), encoded.size(), digest.data());
	encoded.insert(encoded.end(), digest.begin(), digest.end());
	*bytes = std::move(encoded);
	return true;
}

bool divine_boon_state_decode(const std::vector<uint8_t> &bytes, divine_boon_state *state)
{
	if (!state || bytes.size() < magic.size() + SHA256_DIGEST_LENGTH ||
	    bytes.size() > maximum_bytes || !std::equal(magic.begin(), magic.end(), bytes.begin()))
		return false;
	const size_t payload_size = bytes.size() - SHA256_DIGEST_LENGTH;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(bytes.data(), payload_size, digest.data());
	if (CRYPTO_memcmp(digest.data(), bytes.data() + payload_size, digest.size()))
		return false;
	divine_boon_state decoded;
	size_t offset = magic.size();
	uint32_t decoded_version = 0, history_size = 0;
	uint8_t mode = 0, paused = 0;
	if (!read(bytes, offset, decoded_version) ||
	    (decoded_version != 1 && decoded_version != version) ||
	    !read(bytes, offset, decoded.revision) || !read(bytes, offset, decoded.next_id) ||
	    !read(bytes, offset, decoded.last_opportunity) || !read(bytes, offset, mode) ||
	    !read(bytes, offset, paused) || paused > 1)
		return false;
	decoded.mode = static_cast<divine_boon_mode>(mode);
	decoded.paused = paused;
	for (auto &slot : decoded.slots)
		if (!read_slot(bytes, offset, slot))
			return false;
	if (!read(bytes, offset, history_size) || history_size > DIVINE_BOON_HISTORY_MAX)
		return false;
	for (uint32_t index = 0; index < history_size; ++index)
	{
		divine_boon_zone_history entry = {};
		if (!read(bytes, offset, entry.zone) || !read(bytes, offset, entry.side) ||
		    !read(bytes, offset, entry.expired_at))
			return false;
		decoded.history.push_back(entry);
	}
	if (decoded_version >= 2)
	{
		uint32_t count = 0;
		if (!read(bytes, offset, count) || count > DIVINE_BOON_RECENT_MAX)
			return false;
		for (uint32_t index = 0; index < count; ++index)
		{
			divine_boon_retired entry;
			if (!read_slot(bytes, offset, entry.objective) ||
			    !read(bytes, offset, entry.ended_at))
				return false;
			decoded.recent.push_back(entry);
		}
	}

	if (offset != payload_size || !divine_boon_state_valid(decoded))
		return false;
	*state = std::move(decoded);
	return true;
}
