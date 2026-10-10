#include "economy/collector_policy.h"
#include "economy/collector_eligibility.h"
#include "core/defines.h"

#include <cassert>
#include <iostream>
#include <limits>
#include <type_traits>

using namespace collector;

namespace
{
record candidate(uint64_t listing = 1, uint64_t uid = 101)
{
	rules policy;
	policy.enabled = true;
	record entry;
	assert(enroll(listing, "123456789abcdef0123456789abcdef0", 42, uid, 5, 1000, policy,
		      &entry) == outcome::applied);
	return entry;
}

record saleable()
{
	auto entry = candidate();
	assert(collect(&entry, 1, 5, 5, true, 75, entry.collect_at) == outcome::applied);
	assert(activate(&entry, 2, entry.sale_at) == outcome::applied);
	return entry;
}
}

int main()
{
	static_assert(std::is_trivially_copyable_v<record>);
	const auto maximum = std::numeric_limits<uint64_t>::max();
	rules defaults;
	assert(!defaults.enabled && defaults.collection_delay == 43200 &&
	       defaults.sale_delay == 86400 && defaults.holding_duration == 604800 &&
	       defaults.price_percent == 200 && defaults.minimum_value == 100);
	record untouched;
	assert(enroll(1, "123456789abcdef0123456789abcdef0", 42, 101, 5, 1000, defaults,
		      &untouched) == outcome::invalid);
	assert(!untouched.listing);
	defaults.enabled = true;
	assert(enroll(1, "123456789abcdef0123456789abcdef0", 42, 101, 5, maximum, defaults,
		      &untouched) == outcome::overflow);
	assert(!untouched.listing);

	uint64_t gold = 0;
	assert(price(0, defaults, &gold) == outcome::applied && gold == 100);
	assert(price(-7, defaults, &gold) == outcome::applied && gold == 100);
	assert(price(75, defaults, &gold) == outcome::applied && gold == 150);
	defaults.price_percent = 101;
	assert(price(1, defaults, &gold) == outcome::applied && gold == 100);
	defaults.price_percent = maximum;
	assert(price(100, defaults, &gold) == outcome::applied && gold == maximum);
	assert(price(101, defaults, &gold) == outcome::overflow && gold == maximum);
	assert(price(std::numeric_limits<int64_t>::max(), defaults, &gold) == outcome::overflow);

	// The sword was looted, but the untouched shield keeps its own entitlement.
	auto sword = candidate();
	auto shield = candidate(2, 102);
	assert(cancel(&sword, 1, reason::claimed) == outcome::applied);
	assert(sword.item_revision == 5);
	assert(collect(&sword, 2, 5, 5, true, 75, sword.collect_at) == outcome::conflict);
	assert(cancel(&sword, 2, reason::claimed) == outcome::conflict);
	assert(shield.status == state::candidate && shield.revision == 1);
	// A later death of the same UID gets a distinct record; the old one stays closed.
	record later;
	assert(enroll(3, "223456789abcdef0123456789abcdef0", 42, sword.uid, 8, 2000, shield.policy,
		      &later) == outcome::applied);
	assert(later.uid == sword.uid && later.status == state::candidate &&
	       sword.status == state::cancelled);

	assert(collect(&shield, 1, 5, 5, true, 75, shield.collect_at - 1) == outcome::not_due);
	assert(collect(&shield, 0, 5, 5, true, 75, shield.collect_at) == outcome::conflict);
	assert(collect(&shield, 1, 5, 6, true, 75, shield.collect_at) == outcome::conflict);
	assert(collect(&shield, 1, 5, 5, false, 75, shield.collect_at) == outcome::conflict);
	assert(shield.revision == 1 && !shield.price_value);
	// Environmental release may advance custody revision without cancelling.
	assert(collect(&shield, 1, 6, 6, true, 75, shield.collect_at) == outcome::applied);
	assert(shield.item_revision == 7 && shield.price_value == 150);
	assert(collect(&shield, 1, 6, 6, true, 1, shield.collect_at) == outcome::conflict);
	assert(shield.price_value == 150);
	assert(activate(&shield, 2, shield.sale_at - 1) == outcome::not_due);
	const uint64_t delayed = shield.sale_at + 5 * 86400;
	assert(activate(&shield, 2, delayed) == outcome::applied);
	assert(shield.available_at == delayed && shield.expires_at == delayed + 604800);
	assert(purchase(&shield, 3, 43, 150, true, delayed) == outcome::forbidden);
	assert(purchase(&shield, 3, 42, 149, true, delayed) == outcome::insufficient_funds);
	assert(purchase(&shield, 3, 42, 150, false, delayed) == outcome::capacity);
	assert(shield.status == state::available && shield.revision == 3);
	assert(purchase(&shield, 3, 42, 150, true, delayed) == outcome::applied);
	assert(purchase(&shield, 3, 42, 150, true, delayed) == outcome::conflict);
	assert(expire(&shield, 4, maximum) == outcome::conflict);
	assert(shield.uid == 102 && shield.beneficiary == 42 && shield.price_value == 150);

	auto expired = saleable();
	assert(expire(&expired, 3, expired.expires_at - 1) == outcome::not_due);
	assert(purchase(&expired, 3, 42, 150, true, expired.expires_at) == outcome::conflict);
	assert(expire(&expired, 3, expired.expires_at) == outcome::applied);
	assert(expired.status == state::expired &&
	       expired.closed_reason == reason::holding_elapsed);
	assert(expire(&expired, 4, maximum) == outcome::conflict);

	auto paused = saleable();
	const auto original_expiry = paused.expires_at;
	assert(pause(&paused, 3, paused.available_at + 60) == outcome::applied);
	assert(purchase(&paused, 4, 42, 150, true, paused.available_at + 61) == outcome::conflict);
	assert(expire(&paused, 4, maximum) == outcome::not_due);
	assert(resume(&paused, 4, paused.paused_at - 1) == outcome::conflict);
	assert(resume(&paused, 4, paused.paused_at + 86400) == outcome::applied);
	assert(paused.expires_at == original_expiry + 86400);
	assert(expire(&paused, 5, paused.expires_at - 1) == outcome::not_due);
	assert(expire(&paused, 5, paused.expires_at) == outcome::applied);

	// An overdue listing must remain due for expiry instead of leaving the queue.
	paused = saleable();
	assert(pause(&paused, 3, paused.expires_at) == outcome::conflict);
	assert(pause(&paused, 3, paused.expires_at + 1) == outcome::conflict);
	assert(!paused.holding_paused && paused.revision == 3);
	assert(expire(&paused, 3, paused.expires_at) == outcome::applied);

	auto invalid_reason = candidate();
	assert(cancel(&invalid_reason, 1, reason::holding_elapsed) == outcome::invalid);
	assert(cancel(&invalid_reason, 1, static_cast<reason>(255)) == outcome::invalid);

	for (auto why : { reason::destroyed, reason::quarantined, reason::excluded,
			  reason::character_deleted, reason::season_reset })
	{
		auto entry = saleable();
		const auto item_revision = entry.item_revision;
		assert(pause(&entry, entry.revision, entry.available_at + 1) == outcome::applied);
		assert(cancel(&entry, entry.revision, why) == outcome::applied);
		assert(entry.closed_reason == why && entry.status == state::cancelled &&
		       entry.item_revision == item_revision + 1 && !entry.holding_paused &&
		       !entry.paused_at);
		assert(purchase(&entry, 5, 42, maximum, true, entry.available_at) ==
		       outcome::conflict);
	}
	auto cancelled_collected = candidate();
	assert(collect(&cancelled_collected, 1, 5, 5, true, 75, cancelled_collected.collect_at) ==
	       outcome::applied);
	assert(cancel(&cancelled_collected, 2, reason::destroyed) == outcome::applied &&
	       cancelled_collected.item_revision == 7);
	auto cancellation_overflow = saleable();
	cancellation_overflow.item_revision = maximum;
	assert(cancel(&cancellation_overflow, 3, reason::destroyed) == outcome::overflow &&
	       cancellation_overflow.status == state::available);

	due_queue queue;
	for (uint64_t index = 1; index <= 100000; ++index)
		assert(queue.update(candidate(index, index)));
	assert(queue.size() == 100000);
	assert(queue.lease_due(44199, 64, 44230).empty());
	assert(queue.lease_due(maximum, 0, maximum).empty());
	assert(queue.lease_due(44200, 64, 44200).empty());
	const auto batch = queue.lease_due(44200, 64, 44230);
	assert(batch.size() == 64 && batch.front() == 1 && batch.back() == 64);

	due_queue fairness;
	for (uint64_t index = 1; index <= 3; ++index)
		assert(fairness.update(candidate(index, index)));
	assert(fairness.lease_due(44200, 1, 44230).front() == 1);
	assert(fairness.lease_due(44200, 1, 44230).front() == 2);
	assert(fairness.lease_due(44200, 1, 44230).front() == 3);
	assert(fairness.lease_due(44229, 1, 44260).empty());
	assert(fairness.lease_due(44230, 1, 44260).front() == 1);
	auto entry = saleable();
	assert(queue.update(entry));
	assert(queue.size() == 100000 && queue.lease_due(44200, 1, 44230).front() == 65);
	assert(pause(&entry, 3, entry.available_at) == outcome::applied);
	assert(queue.update(entry) && queue.size() == 99999);
	assert(resume(&entry, 4, entry.available_at + 1) == outcome::applied);
	assert(queue.update(entry) && queue.size() == 100000);
	assert(purchase(&entry, 5, 42, 150, true, entry.available_at + 1) == outcome::applied);
	assert(queue.update(entry) && queue.size() == 99999);
	auto malformed = candidate(100001, 100001);
	malformed.collect_at++;
	assert(!valid_record(malformed) && !queue.update(malformed) && queue.size() == 99999);
	// Boundaries mutation testing found unchecked (scripts/mutate.py).
	player_item_snapshot item{};
	item.object_uid = 9;
	item.vnum = 3000;
	item.type = ITEM_ARMOR;
	item.wear_flags = ITEM_TAKE;
	item.name = "plate armor";
	assert(collector_death_item_snapshot_eligible(item));
	item.vnum = 0;
	assert(!collector_death_item_snapshot_eligible(item));

	rules even = defaults;
	even.price_percent = 200;
	even.sale_delay = even.collection_delay;
	assert(valid_rules(even));
	even.collection_delay = 0;
	assert(!valid_rules(even) && price(75, even, &gold) == outcome::invalid);
	assert(price(75, defaults, nullptr) == outcome::invalid);
	record unhex;
	assert(enroll(9, "z23456789abcdef0123456789abcdef0", 42, 109, 5, 1000, shield.policy,
		      &unhex) == outcome::invalid);
	assert(enroll(9, "G23456789abcdef0123456789abcdef0", 42, 109, 5, 1000, shield.policy,
		      &unhex) == outcome::invalid);

	// A record that is not valid, or none, is refused before its revision is compared.
	auto damaged = candidate();
	damaged.version = record_version + 1;
	assert(cancel(&damaged, 1, reason::destroyed) == outcome::invalid);
	assert(activate(nullptr, 1, maximum) == outcome::invalid);
	auto closed_but_available = saleable();
	closed_but_available.closed_reason = reason::claimed;
	assert(!valid_record(closed_but_available));
	auto reopened = candidate();
	assert(cancel(&reopened, 1, reason::destroyed) == outcome::applied);
	reopened.closed_reason = reason::none;
	assert(!valid_record(reopened));

	// A terminal record is not cancelled again, for any reason.
	auto finished = saleable();
	assert(expire(&finished, 3, finished.expires_at) == outcome::applied);
	assert(cancel(&finished, 4, reason::destroyed) == outcome::conflict);

	// Holding resumes at the moment it paused.
	auto instant = saleable();
	assert(pause(&instant, 3, instant.available_at + 10) == outcome::applied);
	assert(resume(&instant, 4, instant.paused_at) == outcome::applied);

	// The queue keeps a listing whose deadline did not change, and moves one whose did.
	due_queue steady;
	auto steady_entry = candidate(7, 107);
	assert(steady.update(steady_entry) && steady.update(steady_entry) && steady.size() == 1);
	uint64_t when = 0;
	assert(steady.deadline(7, &when) && when == steady_entry.collect_at);
	assert(steady.lease_due(steady_entry.collect_at, 1, steady_entry.collect_at + 30).front() ==
	       7);
	assert(collect(&steady_entry, 1, 5, 5, true, 75, steady_entry.collect_at) ==
	       outcome::applied);
	assert(steady.update(steady_entry) && steady.deadline(7, &when) &&
	       when == steady_entry.sale_at);
	assert(steady.lease_due(steady_entry.sale_at - 1, 1, maximum).empty());

	// deadline() and defer() refuse no listing, no output and an unknown listing; a deferral
	// to the same or an earlier time changes nothing, a later one moves the listing.
	assert(!steady.deadline(0, &when) && !steady.deadline(7, nullptr) &&
	       !steady.deadline(8, &when));
	assert(!steady.defer(0, when) && !steady.defer(7, 0) && !steady.defer(8, when));
	assert(steady.defer(7, when) && steady.defer(7, when - 1) && steady.deadline(7, &when) &&
	       when == steady_entry.sale_at);
	assert(steady.defer(7, when + 100) && steady.deadline(7, &when) &&
	       when == steady_entry.sale_at + 100);
	assert(steady.lease_due(steady_entry.sale_at + 99, 1, maximum).empty());
	assert(steady.lease_due(steady_entry.sale_at + 100, 1, maximum).front() == 7);

	std::cout
		<< "collector policy: timing, custody conflicts, privacy, prices, pause, terminal "
		   "states and leased 100000-item scheduling passed\n";
}
