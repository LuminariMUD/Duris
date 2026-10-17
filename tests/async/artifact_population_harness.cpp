#include "guild/artifact_population.h"
#include "core/defines.h"

#include <algorithm>
#include <cassert>
#include <cerrno>
#include <iostream>

using state = artifact_identity_state;
using reason = artifact_population_reason;
using domain = artifact_payload_domain;
using role = artifact_payload_role;

static const std::vector<artifact_population_template> prototypes = { { 900, ITEM_ARTIFACT },
								      { 901, 0 },
								      { 902, ITEM_ARTIFACT },
								      { 903, 0 } };

static artifact_payload_projection item(uint64_t uid, int vnum = 900, uint64_t player = 12)
{
	artifact_payload_projection row = {};
	row.domain = domain::player;
	row.row_id = uid;
	row.item_uid = uid;
	row.owner_reference = player;
	row.payload_owner = { item_owner_type::player, player, 0 };
	row.vnum = vnum;
	row.extra_flags_present = true;
	row.extra_flags = vnum == 901 ? 0 : ITEM_ARTIFACT;
	row.quantity = 1;
	row.custody_examined = row.custody_found = row.custody_owner_revision_found = true;
	row.custody = { uid, uid, 0, row.payload_owner, 1, 1, vnum, item_custody_state::active };
	return row;
}

static artifact_population_decision
classify(std::vector<artifact_payload_projection> rows,
	 std::vector<artifact_population_identity> previous = {}, bool complete = true,
	 int vnum = 900)
{
	std::vector<artifact_population_decision> output;
	assert(!artifact_population_classify(rows, prototypes, previous, complete, &output));
	const auto found = std::find_if(output.begin(), output.end(), [&](const auto &decision)
					{ return decision.identity.vnum == vnum; });
	assert(found != output.end());
	return *found;
}

static void expect(const artifact_population_decision &decision, state identity, uint64_t uid,
		   size_t sources, reason why = reason::complete)
{
	static unsigned int check = 0;
	++check;
	if (decision.identity.state != identity || decision.identity.canonical_item_uid != uid ||
	    decision.canonical_payloads.size() != sources || decision.reason != why)
		std::cerr << "classification check " << check
			  << " got state=" << static_cast<int>(decision.identity.state)
			  << " uid=" << decision.identity.canonical_item_uid
			  << " sources=" << decision.canonical_payloads.size()
			  << " reason=" << static_cast<int>(decision.reason)
			  << " expected state=" << static_cast<int>(identity) << " uid=" << uid
			  << " sources=" << sources << " reason=" << static_cast<int>(why) << '\n';
	assert(decision.identity.state == identity);
	assert(decision.identity.canonical_item_uid == uid);
	assert(decision.canonical_payloads.size() == sources);
	assert(decision.reason == why);
}

int main()
{
	// A nested artifact survives even while its real owner is offline.
	auto bag = item(100, 901);
	auto artifact = item(101);
	artifact.parent_row_id = bag.row_id;
	artifact.parent_item_uid = bag.item_uid;
	artifact.custody.root_item_uid = bag.item_uid;
	artifact.custody.parent_item_uid = bag.item_uid;
	expect(classify({ artifact, bag }), state::present, 101, 1);
	for (auto bad : { 0, 1, 2, 3 })
	{
		auto broken = artifact;
		if (bad == 0)
			broken.parent_row_id = 999;
		if (bad == 1)
			broken.parent_item_uid = 999;
		if (bad == 2)
			broken.custody.root_item_uid = 999;
		if (bad == 3)
			broken.parent_owner_disagrees = true;
		expect(classify({ bag, broken }), state::unresolved, 0, 0,
		       reason::unqualified_payload);
	}
	for (int variant = 0; variant < 4; ++variant)
	{
		auto broken_parent = bag;
		if (variant == 0)
			broken_parent.source_quarantined = true;
		if (variant == 1)
			broken_parent.custody.state = item_custody_state::destroyed;
		if (variant == 2)
			broken_parent.custody.owner.id = 99;
		if (variant == 3)
			broken_parent.extra_flags_present = false;
		expect(classify({ broken_parent, artifact }), state::unresolved, 0, 0,
		       reason::unqualified_payload);
	}
	auto conflicting_bag = bag;
	conflicting_bag.domain = domain::locker;
	conflicting_bag.vnum = conflicting_bag.custody.vnum = 903;
	expect(classify({ bag, artifact, conflicting_bag }), state::unresolved, 0, 0,
	       reason::unqualified_payload);
	auto cycle = bag;
	cycle.parent_row_id = artifact.row_id;
	cycle.parent_item_uid = artifact.item_uid;
	expect(classify({ cycle, artifact }), state::unresolved, 0, 0, reason::unqualified_payload);
	expect(classify({ bag, bag, artifact }), state::unresolved, 0, 0,
	       reason::unqualified_payload);

	// One UID in two domains is one identity only with agreeing current custody.
	auto current = item(111);
	auto projection = current;
	projection.domain = domain::locker;
	expect(classify({ current, projection }), state::present, 111, 2);
	// Different row IDs do not make repeated UIDs in one physical source safe.
	auto repeated = current;
	repeated.row_id += 1;
	for (const auto &rows :
	     { std::vector{ current, repeated }, std::vector{ repeated, current } })
	{
		expect(classify(rows), state::unresolved, 0, 0, reason::unqualified_payload);
		expect(classify(rows, { { 900, 111, state::present } }), state::present, 111, 0,
		       reason::unqualified_payload);
	}
	auto repeated_bag = bag;
	repeated_bag.row_id += 10;
	expect(classify({ bag, repeated_bag, artifact }), state::unresolved, 0, 0,
	       reason::unqualified_payload);
	auto stale = current;
	stale.owner_reference = 13;
	stale.payload_owner.id = 13;
	auto chosen = classify({ stale, current });
	expect(chosen, state::present, 111, 1);
	assert(chosen.canonical_payloads[0] == 1);
	stale.custody.owner = stale.payload_owner;
	expect(classify({ current, stale }), state::unresolved, 0, 0, reason::unqualified_payload);
	projection.extra_flags |= ITEM_NODROP;
	expect(classify({ current, projection }), state::unresolved, 0, 0,
	       reason::unqualified_payload);
	projection = current;
	projection.domain = domain::locker;
	projection.vnum = 901;
	projection.extra_flags = 0;
	projection.custody.vnum = 901;
	expect(classify({ current, projection }), state::unresolved, 0, 0,
	       reason::unqualified_payload);

	// Distinct legacy UIDs have no first/last winner. An established canonical
	// UID can isolate an extra copy, but must not be reassigned to that copy.
	auto extra = item(222);
	for (const auto &rows : { std::vector{ current, extra }, std::vector{ extra, current } })
	{
		expect(classify(rows), state::unresolved, 0, 0, reason::conflicting_identities);
		expect(classify(rows, { { 900, 111, state::present } }), state::present, 111, 1);
	}
	expect(classify({ extra }, { { 900, 111, state::present } }), state::present, 111, 0,
	       reason::conflicting_identities);
	expect(classify({ current }, { { 902, 111, state::present } }), state::unresolved, 0, 0,
	       reason::unqualified_payload);

	// Missing evidence never becomes absence; retained identities are not erased.
	expect(classify({}, {}, false), state::unresolved, 0, 0, reason::incomplete);
	expect(classify({ current }, { { 900, 111, state::present } }, false), state::present, 111,
	       1, reason::incomplete);
	expect(classify({}, { { 900, 111, state::present } }, false), state::present, 111, 0,
	       reason::incomplete);
	expect(classify({ current, extra }, { { 900, 111, state::present } }, false),
	       state::present, 111, 1, reason::incomplete);
	expect(classify({}, { { 900, 111, state::retired } }, false), state::retired, 111, 0,
	       reason::incomplete);
	for (int variant = 0; variant < 8; ++variant)
	{
		auto bad = current;
		if (variant == 0)
			bad.item_uid = 0;
		if (variant == 1)
			bad.quantity = 2;
		if (variant == 2)
			bad.custody_examined = false;
		if (variant == 3)
			bad.custody_found = false;
		if (variant == 4)
			bad.source_quarantined = true;
		if (variant == 5)
			bad.custody.state = item_custody_state::quarantined;
		if (variant == 6)
			bad.custody.state = item_custody_state::destroyed;
		if (variant == 7)
			bad.custody_owner_revision_found = false;
		expect(classify({ bad }), state::unresolved, 0, 0, reason::unqualified_payload);
	}
	auto zero_revision = current;
	zero_revision.custody.owner_revision = 0;
	expect(classify({ zero_revision }), state::present, 111, 1);
	// Unclaimed ground has a physical UID without invented persistent custody.
	auto ground = current;
	ground.domain = domain::redis_generation;
	ground.payload_owner = { item_owner_type::room, 2300, 0 };
	ground.custody_found = false;
	expect(classify({ ground }), state::present, 111, 1);
	ground.custody_required = true;
	expect(classify({ ground }), state::unresolved, 0, 0, reason::unqualified_payload);

	// Effective saved flags, including explicit zero and a newly flagged ordinary
	// prototype, take precedence over the current prototype's flag.
	auto ordinary = current;
	ordinary.extra_flags = 0;
	expect(classify({ ordinary }), state::absent, 0, 0);
	ordinary.extra_flags_present = false;
	expect(classify({ ordinary }), state::unresolved, 0, 0, reason::unqualified_payload);
	auto changed = item(333, 903);
	expect(classify({ changed }, {}, true, 903), state::present, 333, 1);
	changed.vnum = changed.custody.vnum = 904;
	expect(classify({ changed }, {}, true, 904), state::unresolved, 0, 0,
	       reason::unqualified_payload);

	// Retained history does not become a second physical copy. Active history
	// without a current payload must not silently grant a new creation.
	auto history = current;
	history.role = role::history;
	expect(classify({ history }), state::unresolved, 0, 0, reason::unqualified_payload);
	expect(classify({ history, current }), state::present, 111, 1);
	history.custody.state = item_custody_state::destroyed;
	expect(classify({ history }), state::absent, 0, 0);
	history.custody_found = false;
	history.custody_examined = false;
	expect(classify({ history }), state::unresolved, 0, 0, reason::unqualified_payload);
	history.item_uid = 0; // old listing template, no physical identity
	expect(classify({ history }), state::absent, 0, 0);

	// Latest inbound bytes supply pending flat delivery; old receipts/history do
	// not change flags or choose a second copy. Source order is not event order.
	auto delivery = current;
	delivery.domain = domain::delivery;
	delivery.role = role::delivery;
	delivery.delivery_ordinal = 2;
	auto old = delivery;
	old.delivery_ordinal = 1;
	old.extra_flags = 0;
	expect(classify({ delivery, old }), state::present, 111, 1);

	// NPC hints are fresh requests. Only a complete absence decision can later
	// admit one; neither zero UID nor repeated vnum hints count as physical data.
	auto request = current;
	request.domain = domain::copyover_reconstruction;
	request.role = role::reconstruction;
	request.item_uid = 0;
	request.extra_flags_present = false;
	expect(classify({ request, request }), state::absent, 0, 0);
	expect(classify({ request, current }), state::present, 111, 1);
	expect(classify({ request }, {}, false), state::unresolved, 0, 0, reason::incomplete);

	expect(classify({}, { { 900, 111, state::retired } }), state::retired, 111, 0);
	expect(classify({ current }, { { 900, 111, state::retired } }), state::retired, 111, 0,
	       reason::retired_payload);
	expect(classify({ extra }, { { 900, 111, state::retired } }), state::retired, 111, 0,
	       reason::conflicting_identities);
	expect(classify({}, { { 900, 111, state::present } }), state::absent, 0, 0);

	// No invalid input publishes even a prefix over the previous output.
	std::vector<artifact_population_decision> output = { classify({ current }) };
	assert(artifact_population_classify({}, prototypes, { { 900, 0, state::present } }, true,
					    &output) == EINVAL);
	assert(output.size() == 1 && output[0].identity.canonical_item_uid == 111);
	assert(artifact_population_classify({}, { { 900, 0 }, { 900, ITEM_ARTIFACT } }, {}, true,
					    &output) == EINVAL);
	assert(output[0].identity.canonical_item_uid == 111);
	assert(artifact_population_classify({}, prototypes,
					    { { 900, 111, state::present },
					      { 902, 111, state::retired } },
					    true, &output) == EINVAL);
	assert(output[0].identity.canonical_item_uid == 111);
	for (const int invalid_vnum : { -1, 0 })
	{
		assert(artifact_population_classify({}, { { invalid_vnum, ITEM_ARTIFACT } }, {},
						    true, &output) == EINVAL);
		assert(artifact_population_classify({}, prototypes,
						    { { invalid_vnum, 0, state::unresolved } },
						    true, &output) == EINVAL);
		auto invalid = current;
		invalid.vnum = invalid_vnum;
		assert(artifact_population_classify({ invalid }, prototypes, {}, true, &output) ==
		       EINVAL);
		assert(output.size() == 1 && output[0].identity.canonical_item_uid == 111);
	}
	std::cout << "artifact population classification: PASS\n";
}
