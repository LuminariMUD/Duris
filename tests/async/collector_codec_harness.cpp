#include "economy/collector_codec.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

using namespace collector;

namespace
{
constexpr char death_operation[] = "123456789abcdef0123456789abcdef0";

record candidate(uint64_t listing, uint64_t uid)
{
	rules policy;
	policy.enabled = true;
	record entry;
	assert(enroll(listing, death_operation, 42, uid, 5, 1000, policy, &entry) ==
	       outcome::applied);
	return entry;
}

record collected(uint64_t listing, uint64_t uid)
{
	auto entry = candidate(listing, uid);
	assert(collect(&entry, entry.revision, entry.item_revision, entry.item_revision, true, 75,
		       entry.collect_at) == outcome::applied);
	return entry;
}

record available(uint64_t listing, uint64_t uid)
{
	auto entry = collected(listing, uid);
	assert(activate(&entry, entry.revision, entry.sale_at) == outcome::applied);
	return entry;
}

void same_record(const record &left, const record &right)
{
	assert(left.version == right.version && left.listing == right.listing &&
	       left.death_operation == right.death_operation &&
	       left.beneficiary == right.beneficiary && left.uid == right.uid &&
	       left.death_time == right.death_time && left.collect_at == right.collect_at &&
	       left.sale_at == right.sale_at && left.available_at == right.available_at &&
	       left.expires_at == right.expires_at && left.holding_paused == right.holding_paused &&
	       left.paused_at == right.paused_at && left.revision == right.revision &&
	       left.item_revision == right.item_revision && left.price_value == right.price_value &&
	       left.policy.enabled == right.policy.enabled &&
	       left.policy.collection_delay == right.policy.collection_delay &&
	       left.policy.sale_delay == right.policy.sale_delay &&
	       left.policy.holding_duration == right.policy.holding_duration &&
	       left.policy.price_percent == right.policy.price_percent &&
	       left.policy.minimum_value == right.policy.minimum_value &&
	       left.status == right.status && left.closed_reason == right.closed_reason);
}
}

int main()
{
	auto base = candidate(1, 101);
	assert(valid_record(base));
	std::array<uint8_t, encoded_record_bytes> encoded = {};
	assert(record_encode(base, &encoded) == codec_result::ok);
	assert(encoded.size() == 154 && encoded[0] == 1 && encoded[1] == 0 && encoded[2] == 1 &&
	       encoded[10] == 0x12 && encoded[25] == 0xf0 && encoded[78] == 0 &&
	       encoded[111] == 1 && encoded[152] == static_cast<uint8_t>(state::candidate) &&
	       encoded[153] == static_cast<uint8_t>(reason::none));
	record decoded;
	assert(record_decode(encoded.data(), encoded.size(), &decoded) == codec_result::ok);
	same_record(base, decoded);
	std::array<uint8_t, encoded_record_bytes> deterministic = {};
	assert(record_encode(decoded, &deterministic) == codec_result::ok &&
	       deterministic == encoded);

	record untouched = candidate(999, 999);
	auto corrupt = encoded;
	corrupt[0] = 2;
	assert(record_decode(corrupt.data(), corrupt.size(), &untouched) ==
	       codec_result::unsupported_version);
	assert(untouched.listing == 999);
	assert(record_decode(encoded.data(), encoded.size() - 1, &untouched) ==
	       codec_result::malformed);
	corrupt = encoded;
	corrupt[78] = 2;
	assert(record_decode(corrupt.data(), corrupt.size(), &untouched) ==
	       codec_result::malformed);
	corrupt = encoded;
	corrupt[152] = 0;
	assert(record_decode(corrupt.data(), corrupt.size(), &untouched) == codec_result::invalid);
	corrupt = encoded;
	std::fill(corrupt.begin() + 10, corrupt.begin() + 26, 0);
	assert(record_decode(corrupt.data(), corrupt.size(), &untouched) == codec_result::invalid);
	corrupt = encoded;
	++corrupt[46];
	assert(record_decode(corrupt.data(), corrupt.size(), &untouched) == codec_result::invalid);
	auto invalid = base;
	invalid.listing = 0;
	deterministic.fill(0x5a);
	assert(record_encode(invalid, &deterministic) == codec_result::invalid &&
	       std::all_of(deterministic.begin(), deterministic.end(),
			   [](uint8_t byte) { return byte == 0x5a; }));
	due_queue rejected;
	assert(!rejected.update(invalid) && rejected.size() == 0);
	invalid = base;
	invalid.death_operation[death_operation_hex_size] = 'x';
	assert(!valid_record(invalid) &&
	       record_encode(invalid, &deterministic) == codec_result::invalid);

	std::vector<record> states;
	states.push_back(base);
	states.push_back(collected(2, 102));
	states.push_back(available(3, 103));
	auto bought = available(4, 104);
	assert(purchase(&bought, bought.revision, bought.beneficiary, bought.price_value, true,
			bought.available_at) == outcome::applied);
	states.push_back(bought);
	auto paused = available(5, 105);
	assert(pause(&paused, paused.revision, paused.available_at + 10) == outcome::applied);
	states.push_back(paused);
	auto expired = available(6, 106);
	assert(expire(&expired, expired.revision, expired.expires_at) == outcome::applied);
	states.push_back(expired);
	auto claimed = candidate(7, 107);
	assert(cancel(&claimed, claimed.revision, reason::claimed) == outcome::applied);
	states.push_back(claimed);
	auto impossible_claim = collected(9, 109);
	impossible_claim.status = state::cancelled;
	impossible_claim.closed_reason = reason::claimed;
	assert(!valid_record(impossible_claim));
	auto quarantined = available(8, 108);
	assert(pause(&quarantined, quarantined.revision, quarantined.available_at + 20) ==
	       outcome::applied);
	assert(cancel(&quarantined, quarantined.revision, reason::quarantined) == outcome::applied);
	assert(!quarantined.holding_paused && !quarantined.paused_at);
	states.push_back(quarantined);
	for (const auto &entry : states)
		assert(valid_record(entry));

	catalog value;
	value.revision = 19;
	value.next_listing = 9;
	value.records = states;
	assert(valid_catalog(value));

	due_queue rebuilt;
	for (uint64_t listing = 1; listing <= 100000; ++listing)
		assert(rebuilt.update(candidate(listing, listing)));
	const auto first_batch = rebuilt.lease_due(44200, 64, 44230);
	assert(rebuilt.size() == 100000 && first_batch.size() == 64 && first_batch.front() == 1 &&
	       first_batch.back() == 64);

	std::cout << "collector codec: canonical state round trips, malformed input fails closed, "
		     "and 100000-record scheduling rebuild passed\n";
}
