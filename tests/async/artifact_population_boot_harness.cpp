#include "guild/artifact_population_boot.h"
#include "guild/artifact_population.h"
#include "persistence/copyover.h"
#include "persistence/persistence_mode.h"
#include "redis/redis_world_runtime.h"
#include "core/defines.h"

#include <cassert>
#include <cerrno>
#include <iostream>
#include <map>
#include <set>

namespace
{
std::map<std::string, copyover_boot_result> paths;
std::map<uint64_t, std::vector<artifact_payload_projection>> native_rows;
std::vector<artifact_payload_projection> redis_rows, durable_rows;
std::vector<artifact_recovery_mob_projection> redis_mobs;
std::map<uint64_t, item_ownership_runtime_entry> custody;
std::set<uint64_t> quarantined, missing_revisions;
copyover_boot_snapshot selected_image;
redis_world_boot_snapshot redis_image;
redis_world_boot_result redis_result = redis_world_boot_result::disabled;
unsigned int durable_error = 0, reads = 0;

artifact_payload_projection item(uint64_t uid, artifact_payload_domain domain)
{
	artifact_payload_projection row = {};
	row.domain = domain;
	row.row_id = row.item_uid = row.payload_root_item_uid = uid;
	row.owner_reference = 2300;
	row.payload_owner = { item_owner_type::room, 2300, 0 };
	row.vnum = 900;
	row.extra_flags = ITEM_ARTIFACT;
	row.extra_flags_present = true;
	row.quantity = 1;
	return row;
}

void reset()
{
	artifact_population_boot_clear();
	paths.clear();
	native_rows.clear();
	redis_rows.clear();
	redis_mobs.clear();
	missing_revisions.clear();
	durable_rows.clear();
	custody.clear();
	quarantined.clear();
	durable_error = reads = 0;
	redis_result = redis_world_boot_result::disabled;
	selected_image = {};
	selected_image.identity.st_ino = 2;
}

artifact_population_decision classify(const artifact_population_boot_snapshot &snapshot)
{
	std::vector<artifact_population_decision> decisions;
	assert(!artifact_population_classify(snapshot.items, { { 900, ITEM_ARTIFACT } }, {},
					     snapshot.complete, &decisions));
	assert(decisions.size() == 1);
	return decisions.front();
}
} // namespace

bool persistence_mode_requires_mysql()
{
	return false;
}
const char *persistence_mode_flatfile_root()
{
	return "fixture";
}
const char *copyover_state_file()
{
	return "copyover.dat";
}
const copyover_boot_snapshot *copyover_boot_evidence()
{
	return &selected_image;
}
copyover_boot_result copyover_read_file(const std::string &path, copyover_boot_snapshot *image)
{
	++reads;
	const auto result = paths.contains(path) ? paths.at(path) : copyover_boot_result::absent;
	if (result == copyover_boot_result::ready)
		image->identity.st_ino = path.ends_with(".recovering") ? 2 : 1;
	return result;
}
unsigned int artifact_population_read_copyover(const copyover_boot_snapshot &image,
					       artifact_recovery_population *population)
{
	population->items = native_rows[image.identity.st_ino];
	return 0;
}
redis_world_boot_result redis_world_prepare_boot()
{
	return redis_result;
}
const redis_world_boot_snapshot *redis_world_boot_evidence()
{
	return &redis_image;
}
unsigned int artifact_population_read_recovery(const redis_world_boot_snapshot &,
					       artifact_recovery_population *population)
{
	population->items = redis_rows;
	population->mobs = redis_mobs;
	return 0;
}
unsigned int artifact_population_read_flat_payloads(
	const std::string &, std::vector<artifact_payload_projection> *items, std::string *,
	const std::vector<artifact_payload_projection> *additional)
{
	++reads;
	if (durable_error)
		return durable_error;
	*items = *additional;
	items->insert(items->end(), durable_rows.begin(), durable_rows.end());
	for (auto &row : *items)
	{
		row.custody_examined = true;
		row.custody_found = custody.contains(row.item_uid);
		row.custody_owner_revision_found = row.custody_found &&
						   !missing_revisions.contains(row.item_uid);
		row.custody = row.custody_found ? custody.at(row.item_uid) :
						  item_ownership_runtime_entry{};
		row.source_quarantined = row.source_quarantined ||
					 quarantined.contains(row.item_uid);
	}
	return 0;
}

int main()
{
	using state = artifact_identity_state;
	using domain = artifact_payload_domain;
	reset();
	durable_rows = { item(111, domain::room) };
	const auto &cold = artifact_population_prepare_boot(false);
	assert(cold.complete && reads == 3 && cold.retained_uids == std::vector<uint64_t>{ 111 });
	assert(classify(cold).identity.canonical_item_uid == 111);
	durable_rows.clear();
	assert(&artifact_population_prepare_boot(false) == &cold && reads == 3 &&
	       cold.items.size() == 1);

	reset();
	paths["copyover.dat"] = paths["copyover.dat.recovering"] = copyover_boot_result::ready;
	native_rows[1] = { item(777, domain::copyover_ground) };
	native_rows[2] = { item(888, domain::copyover_ground) };
	const auto &retained = artifact_population_prepare_boot(false);
	assert(retained.complete && retained.items.size() == 2 && reads == 3);
	assert(retained.retained_uids == (std::vector<uint64_t>{ 777, 888 }));
	assert(retained.items[0].source_quarantined && retained.items[1].source_quarantined);
	assert(classify(retained).identity.state == state::unresolved);

	for (int failure = 0; failure < 3; ++failure)
	{
		reset();
		durable_rows = { item(111, domain::room) };
		if (failure == 0)
			paths["copyover.dat.recovering"] = copyover_boot_result::failed;
		if (failure == 1)
			redis_result = redis_world_boot_result::failed;
		if (failure == 2)
			durable_error = EIO;
		const auto &unknown = artifact_population_prepare_boot(false);
		assert(!unknown.complete && classify(unknown).identity.state == state::unresolved);
	}

	reset();
	redis_result = redis_world_boot_result::ready;
	redis_rows = { item(555, domain::redis_generation) };
	assert(artifact_population_prepare_boot(false).complete);
	assert(classify(artifact_population_boot_evidence()).identity.canonical_item_uid == 555);

	// Redis mob records omit equipment identity. Source decoding alone cannot
	// establish artifact absence while their reset reconstruction is unresolved.
	reset();
	redis_result = redis_world_boot_result::ready;
	redis_mobs.push_back({ 2000, 42, 2300, 2300, -1 });
	const auto &npc = artifact_population_prepare_boot(false);
	assert(!npc.complete && npc.unavailable_sources.find("NPC") != std::string::npos &&
	       classify(npc).identity.state == state::unresolved);
	reset();
	redis_result = redis_world_boot_result::ready;
	assert(artifact_population_prepare_boot(false).complete &&
	       classify(artifact_population_boot_evidence()).identity.state == state::absent);

	// Native NPC hints carry vnums, not physical UIDs. Neither selected nor
	// retained hints may release an established identity as proven absent.
	for (const bool selected : { false, true })
	{
		reset();
		auto hint = item(0, domain::copyover_reconstruction);
		hint.role = artifact_payload_role::reconstruction;
		hint.row_id = 1;
		hint.extra_flags_present = false;
		native_rows[selected ? 2 : 1] = { hint };
		if (!selected)
			paths["copyover.dat"] = copyover_boot_result::ready;
		const auto &native = artifact_population_prepare_boot(selected);
		assert(!native.complete && classify(native).identity.state == state::unresolved);
		std::vector<artifact_population_decision> held;
		assert(!artifact_population_classify(native.items, { { 900, ITEM_ARTIFACT } },
						     { { 900, 111, state::present } },
						     native.complete, &held));
		assert(held.size() == 1 && held[0].identity.state == state::present &&
		       held[0].identity.canonical_item_uid == 111 &&
		       held[0].canonical_payloads.empty());
	}

	// Native handoff authority supersedes an older durable owner. It is never
	// overwritten by that older SQL/flat projection, nor confused with history.
	for (int conflict = 0; conflict < 7; ++conflict)
	{
		reset();
		auto live = item(700, domain::copyover_ground);
		live.payload_owner = { item_owner_type::corpse, (77ULL << 32) | 12, 0 };
		live.custody_examined = live.custody_found = live.custody_required =
			live.custody_owner_revision_found = true;
		live.custody = { 700, 700, 0,	live.payload_owner,
				 3,   3,   900, item_custody_state::active };
		native_rows[2] = { live };
		auto old = item(700, domain::player);
		old.payload_owner = { item_owner_type::player, 55, 0 };
		old.owner_reference = 55;
		durable_rows = { old };
		custody[700] = { 700, 700, 0,	old.payload_owner,
				 2,   2,   900, item_custody_state::active };
		if (conflict == 1)
			custody[700].item_revision = 4;
		if (conflict == 2)
			custody[700].item_revision = 3;
		if (conflict == 3)
			custody[700].state = item_custody_state::destroyed;
		if (conflict == 4)
			quarantined.insert(700);
		if (conflict == 5)
		{
			custody[700] = live.custody;
			custody[700].owner_revision =
				9; // unrelated owner saves do not change this item
		}
		redis_result = redis_world_boot_result::ready;
		redis_rows = { item(999, domain::redis_generation) };
		redis_mobs.push_back({ 2000, 42, 2300, 2300, -1 }); // superseded by selected native
		if (conflict == 6)
			missing_revisions.insert(700);
		const auto &warm = artifact_population_prepare_boot(true);
		assert(warm.complete && warm.items.size() == 3 && reads == 2);
		assert(warm.retained_uids == std::vector<uint64_t>{ 700 });
		const auto decision = classify(warm);
		assert(warm.items[1].role == artifact_payload_role::history);
		if (conflict && conflict != 5)
			assert(decision.identity.state == state::unresolved &&
			       decision.canonical_payloads.empty());
		else
		{
			assert(decision.identity.state == state::present &&
			       decision.identity.canonical_item_uid == 700);
			assert(decision.canonical_payloads == std::vector<size_t>{ 0 });
			assert(warm.items[2].custody.owner.type == item_owner_type::corpse);
			assert(warm.items[0].custody.owner_revision == (conflict == 5 ? 9 : 3));
		}
	}
	// A newly saved legacy-created object may have durable custody without a
	// live cache entry. Selected native ground is physical handoff, not a Redis
	// floor claim: independent current custody supplies its logical owner.
	for (int conflict = 0; conflict < 6; ++conflict)
	{
		reset();
		native_rows[2] = { item(700, domain::copyover_ground) };
		custody[700] = { 700, 700, 0,	{ item_owner_type::player, 55, 0 },
				 3,   3,   900, item_custody_state::active };
		if (conflict == 1)
			custody[700].state = item_custody_state::destroyed;
		if (conflict == 2)
			quarantined.insert(700);
		if (conflict == 3)
			custody[700].vnum = 901;
		if (conflict == 4)
			custody[700].root_item_uid = 701;
		if (conflict == 5)
			custody[700].parent_item_uid = 701;
		const auto &handoff = artifact_population_prepare_boot(true);
		const auto decision = classify(handoff);
		if (!conflict)
		{
			assert(decision.identity.state == state::present &&
			       decision.identity.canonical_item_uid == 700 &&
			       decision.canonical_payloads == std::vector<size_t>{ 0 });
			assert(handoff.items[0].payload_owner.type == item_owner_type::player);
		}
		else
			assert(decision.identity.state == state::unresolved &&
			       decision.canonical_payloads.empty());
	}
	reset();
	redis_result = redis_world_boot_result::ready;
	redis_rows = { item(700, domain::redis_generation) };
	custody[700] = { 700, 700, 0,	{ item_owner_type::player, 55, 0 },
			 3,   3,   900, item_custody_state::active };
	assert(classify(artifact_population_prepare_boot(false)).identity.state ==
	       state::unresolved);
	reset();
	paths["copyover.dat.recovering"] = copyover_boot_result::ready;
	native_rows[2] = { item(700, domain::copyover_ground) };
	custody[700] = { 700, 700, 0,	{ item_owner_type::player, 55, 0 },
			 3,   3,   900, item_custody_state::active };
	assert(classify(artifact_population_prepare_boot(false)).identity.state ==
	       state::unresolved);

	reset();
	auto live = item(700, domain::copyover_ground);
	live.custody_examined = live.custody_found = live.custody_required =
		live.custody_owner_revision_found = true;
	live.custody = { 700, 700, 0, live.payload_owner, 3, 3, 900, item_custody_state::active };
	native_rows[2] = { live };
	custody[700] = live.custody;
	paths["copyover.dat"] = copyover_boot_result::failed;
	const auto &partial = artifact_population_prepare_boot(true);
	std::vector<artifact_population_decision> decisions;
	assert(!partial.complete &&
	       !artifact_population_classify(partial.items, { { 900, ITEM_ARTIFACT } },
					     { { 900, 700, state::present } }, partial.complete,
					     &decisions));
	assert(decisions.size() == 1 &&
	       decisions[0].canonical_payloads == std::vector<size_t>{ 0 } &&
	       decisions[0].identity.canonical_item_uid == 700 &&
	       decisions[0].reason == artifact_population_reason::incomplete);
	std::cout << "boot population source policy and selected custody: PASS\n";
}
