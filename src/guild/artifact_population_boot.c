#include "guild/artifact_population_boot.h"

#include "guild/artifact_identity.h"
#include "persistence/copyover.h"
#include "persistence/persistence_mode.h"
#include "redis/redis_world_runtime.h"
#include "sql/sql.h"

#include <algorithm>
#include <cerrno>
#include <map>
#include <memory>
#include <new>
#include <set>

namespace
{
bool prepared = false;
artifact_population_boot_snapshot evidence;

bool append_recovery(artifact_recovery_population &source,
		     std::vector<artifact_payload_projection> *items, bool retained)
{
	if (source.items.size() > ARTIFACT_IDENTITY_MAX_RECORDS - items->size())
		return false;
	if (retained)
		for (auto &row : source.items)
			row.source_quarantined = true; // inspected, but not selected for restore
	items->insert(items->end(), source.items.begin(), source.items.end());
	// Preserve the hints, but they cannot establish physical identity or absence.
	return std::none_of(source.items.begin(), source.items.end(), [](const auto &row)
			    { return row.role == artifact_payload_role::reconstruction; });
}

bool inspect_native(const std::string &path, std::vector<artifact_payload_projection> *items)
{
	copyover_boot_snapshot image;
	const auto read = copyover_read_file(path, &image);
	if (read == copyover_boot_result::absent)
		return true;
	artifact_recovery_population population;
	return read == copyover_boot_result::ready &&
	       !artifact_population_read_copyover(image, &population) &&
	       append_recovery(population, items, true);
}

// A selected native handoff captures live authority after writer drains. It may
// be ahead of durable custody. Never overwrite a newer/terminal/quarantined
// durable fact, or accept equal-revision disagreement as an ordinary lag.
void apply_selected_custody(const std::map<uint64_t, item_ownership_runtime_entry> &selected,
			    std::vector<artifact_payload_projection> *items)
{
	std::set<uint64_t> conflicts;
	for (const auto &row : *items)
	{
		const auto found = selected.find(row.item_uid);
		if (found == selected.end())
			continue;
		const auto &incoming = found->second;
		const auto &stored = row.custody;
		const bool same_owner = item_owner_identity_equal(incoming.owner, stored.owner);
		if (row.source_quarantined ||
		    (row.custody_found &&
		     (!row.custody_owner_revision_found ||
		      stored.state != item_custody_state::active || stored.vnum != incoming.vnum ||
		      stored.item_revision > incoming.item_revision ||
		      (same_owner && stored.owner_revision > incoming.owner_revision) ||
		      (stored.item_revision == incoming.item_revision &&
		       (!same_owner || stored.root_item_uid != incoming.root_item_uid ||
			stored.parent_item_uid != incoming.parent_item_uid)))))
			conflicts.insert(row.item_uid);
	}
	for (auto &row : *items)
	{
		const auto found = selected.find(row.item_uid);
		if (found == selected.end())
			continue;
		if (conflicts.count(row.item_uid))
			row.source_quarantined = true;
		else
		{
			row.custody_examined = row.custody_found =
				row.custody_owner_revision_found = true;
			row.custody = found->second;
		}
	}
}
} // namespace

const artifact_population_boot_snapshot &artifact_population_prepare_boot(bool native_copyover)
{
	if (prepared)
		return evidence;
	prepared = true;
	try
	{
		artifact_population_boot_snapshot staged;
		bool complete = true;
		std::vector<artifact_payload_projection> recovery;
		std::map<uint64_t, item_ownership_runtime_entry> selected;
		const std::string native_path = copyover_state_file();
		if (native_copyover)
		{
			const auto *image = copyover_boot_evidence();
			artifact_recovery_population population;
			if (!image || artifact_population_read_copyover(*image, &population))
			{
				complete = false;
				staged.unavailable_sources += "selected native handoff; ";
			}
			else
			{
				for (const auto &row : population.items)
					if (row.custody_found)
						selected.emplace(row.item_uid, row.custody);
				complete = append_recovery(population, &recovery, false);
				if (!complete)
					staged.unavailable_sources +=
						"native reconstruction or projection limit; ";
			}
		}
		else if (!inspect_native(native_path + ".recovering", &recovery))
		{
			complete = false;
			staged.unavailable_sources += "retained native claim; ";
		}
		// On a warm boot the original should be absent after the exclusive claim.
		// A newly published original remains separate evidence, never consumed here.
		if (!inspect_native(native_path, &recovery))
		{
			complete = false;
			staged.unavailable_sources += "native publication; ";
		}

		const auto redis = redis_world_prepare_boot();
		if (redis == redis_world_boot_result::failed)
		{
			complete = false;
			staged.unavailable_sources += "Redis recovery; ";
		}
		else if (redis == redis_world_boot_result::ready)
		{
			const auto *image = redis_world_boot_evidence();
			artifact_recovery_population population;
			if (!image || artifact_population_read_recovery(*image, &population))
			{
				complete = false;
				staged.unavailable_sources += "Redis projection; ";
			}
			else
			{
				// Redis mobs have no stable equipment identities. Until their
				// reconstruction is qualified, they cannot prove artifact absence.
				if (!native_copyover && !population.mobs.empty())
				{
					complete = false;
					staged.unavailable_sources += "Redis NPC reconstruction; ";
				}
				// -C selects the claimed native handoff. Its preceding Redis
				// generation is history, not a competing selected world image.
				if (native_copyover)
					for (auto &row : population.items)
						row.role = artifact_payload_role::history;
				if (!append_recovery(population, &recovery, false))
				{
					complete = false;
					staged.unavailable_sources += "Redis projection limit; ";
				}
			}
		}

		unsigned int failed = 0;
		if (persistence_mode_requires_mysql())
		{
#ifndef __NO_MYSQL__
			std::unique_ptr<MYSQL, decltype(&mysql_close)> connection(
				sql_open_configured_connection(0), mysql_close);
			failed = connection ? artifact_population_read_sql_payloads(
						      connection.get(), &staged.items, &recovery) :
					      ENOTCONN;
#else
			failed = ENOTSUP;
#endif
		}
		else
		{
			const char *root = persistence_mode_flatfile_root();
			std::string error;
			failed = artifact_population_read_flat_payloads(
				root ? root : "", &staged.items, &error, &recovery);
		}
		if (failed)
		{
			complete = false;
			staged.unavailable_sources +=
				"durable payload/custody error=" + std::to_string(failed) + "; ";
			staged.items = std::move(recovery);
		}
		apply_selected_custody(selected, &staged.items);
		for (const auto &row : staged.items)
			if (row.item_uid && (row.role == artifact_payload_role::stored ||
					     row.role == artifact_payload_role::delivery))
				staged.retained_uids.push_back(row.item_uid);
		std::sort(staged.retained_uids.begin(), staged.retained_uids.end());
		staged.retained_uids.erase(std::unique(staged.retained_uids.begin(),
						       staged.retained_uids.end()),
					   staged.retained_uids.end());
		staged.complete = complete;
		evidence = std::move(staged);
	}
	catch (const std::bad_alloc &)
	{
		evidence = {};
	}
	return evidence;
}

const artifact_population_boot_snapshot &artifact_population_boot_evidence()
{
	return evidence;
}

void artifact_population_boot_clear()
{
	evidence = {};
	prepared = false;
}
