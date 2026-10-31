#include "combat/frag_cap.h"

#include <algorithm>
#include <array>
#include <limits>
#include <openssl/crypto.h>
#include <openssl/sha.h>

namespace
{
constexpr std::array<uint8_t, 8> magic = { 'D', 'U', 'R', 'C', 'A', 'P', '0', '1' };
constexpr int64_t maximum_duration = 3650 * 24 * FRAG_CAP_HOUR;

bool valid_time(int64_t value)
{
	return value > 0 && value <= std::numeric_limits<int64_t>::max() - maximum_duration;
}

bool valid_policy(const frag_cap_policy &policy)
{
	return policy.earliest_after > 0 && policy.automatic_after >= policy.earliest_after &&
	       policy.automatic_after <= maximum_duration && policy.target_points > 0 &&
	       policy.target_points <= 100;
}

void start_round(frag_cap_state &state, int64_t at, const frag_cap_policy &policy)
{
	state.round_start = at;
	state.qualified_at = 0;
	state.earned.clear();
	state.target_points = policy.target_points;
	state.earliest_at = state.level == FRAG_CAP_MAXIMUM_LEVEL ? 0 : at + policy.earliest_after;
	state.automatic_at = state.level == FRAG_CAP_MAXIMUM_LEVEL ? 0 :
								     at + policy.automatic_after;
}

bool settle(frag_cap_state &state, int64_t now, const frag_cap_policy &policy)
{
	while (state.level < FRAG_CAP_MAXIMUM_LEVEL && now >= frag_cap_due_at(state))
	{
		const int64_t due = frag_cap_due_at(state);
		if (!valid_time(due))
			return false;
		++state.level;
		start_round(state, due, policy);
	}
	return true;
}

bool finish(frag_cap_state *state, frag_cap_state next)
{
	if (next == *state)
		return true;
	if (next.revision == std::numeric_limits<uint64_t>::max())
		return false;
	++next.revision;
	if (!frag_cap_state_valid(next))
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
}

bool frag_cap_state_valid(const frag_cap_state &state)
{
	if (!state.revision || state.level < FRAG_CAP_INITIAL_LEVEL ||
	    state.level > FRAG_CAP_MAXIMUM_LEVEL || !valid_time(state.credit_cutoff) ||
	    !valid_time(state.round_start) || state.round_start < state.credit_cutoff ||
	    !state.target_points || state.target_points > 100 ||
	    state.earned.size() > FRAG_CAP_MAX_CONTRIBUTORS)
		return false;
	if (state.level == FRAG_CAP_MAXIMUM_LEVEL)
		return !state.earliest_at && !state.automatic_at && !state.qualified_at &&
		       state.earned.empty();
	if (!valid_time(state.earliest_at) || !valid_time(state.automatic_at) ||
	    state.earliest_at < state.round_start || state.automatic_at <= state.round_start ||
	    state.automatic_at < state.earliest_at ||
	    state.automatic_at - state.round_start > maximum_duration)
		return false;
	if (state.qualified_at &&
	    (state.qualified_at < state.round_start || state.qualified_at >= state.automatic_at ||
	     !state.earned.empty()))
		return false;
	for (const auto &[pid, points] : state.earned)
		if (!pid || !points || points >= state.target_points)
			return false;
	return true;
}

int64_t frag_cap_due_at(const frag_cap_state &state)
{
	if (state.level == FRAG_CAP_MAXIMUM_LEVEL)
		return 0;
	return state.qualified_at ? std::min(state.automatic_at,
					     std::max(state.earliest_at, state.qualified_at)) :
				    state.automatic_at;
}

bool frag_cap_adopt(frag_cap_state *state, int legacy_level, int64_t legacy_deadline, int64_t now,
		    const frag_cap_policy &policy)
{
	if (!state || !valid_time(now) || !valid_policy(policy) || legacy_level < 1 ||
	    legacy_level > FRAG_CAP_MAXIMUM_LEVEL || legacy_deadline < 0 ||
	    (legacy_deadline && !valid_time(legacy_deadline)))
		return false;
	frag_cap_state next;
	next.level = std::max(FRAG_CAP_INITIAL_LEVEL, legacy_level);
	next.credit_cutoff = now;
	start_round(next, now, policy);
	if (legacy_level >= FRAG_CAP_INITIAL_LEVEL && next.level < FRAG_CAP_MAXIMUM_LEVEL &&
	    legacy_deadline)
	{
		if (legacy_deadline <= now)
		{
			++next.level;
			start_round(next, now, policy);
		}
		else
		{
			next.automatic_at = std::min(next.automatic_at, legacy_deadline);
			next.earliest_at =
				std::max(now, next.automatic_at - (policy.automatic_after -
								   policy.earliest_after));
		}
	}
	if (!frag_cap_state_valid(next))
		return false;
	*state = std::move(next);
	return true;
}

bool frag_cap_settle(frag_cap_state *state, int64_t now, const frag_cap_policy &policy)
{
	if (!state || !frag_cap_state_valid(*state) || !valid_time(now) ||
	    now < state->round_start || !valid_policy(policy))
		return false;
	auto next = *state;
	return settle(next, now, policy) && finish(state, std::move(next));
}

bool frag_cap_apply(frag_cap_state *state, int64_t admitted_at, int64_t now,
		    const frag_cap_award *awards, size_t count, const frag_cap_policy &policy)
{
	if (!state || !frag_cap_state_valid(*state) || !valid_time(now) ||
	    now < state->round_start || !valid_policy(policy) || (count && !awards))
		return false;
	auto next = *state;
	if (!settle(next, now, policy))
		return false;
	if (next.level < FRAG_CAP_MAXIMUM_LEVEL && !next.qualified_at &&
	    admitted_at >= next.credit_cutoff && admitted_at >= next.round_start &&
	    admitted_at <= now)
	{
		for (size_t index = 0; index < count; ++index)
		{
			const auto &award = awards[index];
			if (!award.pid || award.points <= 0)
				continue;
			auto found = next.earned.find(award.pid);
			const uint16_t previous = found == next.earned.end() ? 0 : found->second;
			if (award.points >= next.target_points - previous)
			{
				next.qualified_at = now;
				next.earned.clear();
				break;
			}
			if (found == next.earned.end() &&
			    next.earned.size() == FRAG_CAP_MAX_CONTRIBUTORS)
				return false;
			next.earned[award.pid] = previous + static_cast<uint16_t>(award.points);
		}
		// Consume the entire event in the old round, including every recipient's
		// surplus. An immediate unlock cannot apply later recipients again.
		if (!settle(next, now, policy))
			return false;
	}
	return finish(state, std::move(next));
}

bool frag_cap_state_encode(const frag_cap_state &state, std::vector<uint8_t> *bytes)
{
	if (!bytes || !frag_cap_state_valid(state))
		return false;
	std::vector<uint8_t> encoded(magic.begin(), magic.end());
	append(encoded, UINT32_C(1));
	append(encoded, state.revision);
	append(encoded, state.level);
	append(encoded, state.credit_cutoff);
	append(encoded, state.round_start);
	append(encoded, state.earliest_at);
	append(encoded, state.automatic_at);
	append(encoded, state.qualified_at);
	append(encoded, state.target_points);
	append(encoded, static_cast<uint32_t>(state.earned.size()));
	for (const auto &[pid, points] : state.earned)
	{
		append(encoded, pid);
		append(encoded, points);
	}
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest;
	SHA256(encoded.data(), encoded.size(), digest.data());
	encoded.insert(encoded.end(), digest.begin(), digest.end());
	*bytes = std::move(encoded);
	return true;
}

bool frag_cap_state_decode(const std::vector<uint8_t> &bytes, frag_cap_state *state)
{
	if (!state || bytes.size() < 102 || bytes.size() > FRAG_CAP_MAX_BYTES ||
	    !std::equal(magic.begin(), magic.end(), bytes.begin()))
		return false;
	const size_t payload_size = bytes.size() - SHA256_DIGEST_LENGTH;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest;
	SHA256(bytes.data(), payload_size, digest.data());
	if (CRYPTO_memcmp(digest.data(), bytes.data() + payload_size, digest.size()))
		return false;
	size_t offset = magic.size();
	uint32_t version = 0, count = 0;
	frag_cap_state decoded;
	if (!read(bytes, offset, version) || version != 1 ||
	    !read(bytes, offset, decoded.revision) || !read(bytes, offset, decoded.level) ||
	    !read(bytes, offset, decoded.credit_cutoff) ||
	    !read(bytes, offset, decoded.round_start) ||
	    !read(bytes, offset, decoded.earliest_at) ||
	    !read(bytes, offset, decoded.automatic_at) ||
	    !read(bytes, offset, decoded.qualified_at) ||
	    !read(bytes, offset, decoded.target_points) || !read(bytes, offset, count) ||
	    count > FRAG_CAP_MAX_CONTRIBUTORS ||
	    payload_size != offset + 6 * static_cast<size_t>(count))
		return false;
	uint32_t previous_pid = 0;
	for (uint32_t index = 0; index < count; ++index)
	{
		uint32_t pid = 0;
		uint16_t points = 0;
		if (!read(bytes, offset, pid) || !read(bytes, offset, points) ||
		    pid <= previous_pid)
			return false;
		decoded.earned.emplace(pid, points);
		previous_pid = pid;
	}
	if (!frag_cap_state_valid(decoded))
		return false;
	*state = std::move(decoded);
	return true;
}
