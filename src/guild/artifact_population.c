#include "guild/artifact_population.h"

#include "core/defines.h"

#include <algorithm>
#include <cerrno>
#include <map>
#include <new>
#include <set>
#include <tuple>

namespace
{
// Row IDs are local to the actual source/owner/operation. Retain ordinary
// ancestors so an artifact nested inside an ordinary bag gets its physical root.
using row_key = std::tuple<artifact_payload_domain, int64_t, uint64_t,
			   std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES>, uint64_t, uint64_t>;
row_key key(const artifact_payload_projection &row, uint64_t id)
{
	return { row.domain,	       row.owner_reference,
		 row.owner_context,    row.source_operation.bytes,
		 row.delivery_ordinal, id };
}

bool qualified(const artifact_payload_projection &row, uint64_t root)
{
	if (!root || row.quantity != 1 || !row.extra_flags_present || row.source_quarantined ||
	    !row.custody_examined || !item_owner_identity_valid(row.payload_owner) ||
	    row.payload_owner.type == item_owner_type::destruction)
		return false;
	if (!row.custody_found)
		// A genuinely unclaimed ground tree may have no persistent owner yet.
		return !row.custody_required && row.payload_owner.type == item_owner_type::room;
	const auto &custody = row.custody;
	return row.custody_owner_revision_found && custody.state == item_custody_state::active &&
	       custody.item_uid == row.item_uid && custody.vnum == row.vnum &&
	       custody.root_item_uid == root && custody.parent_item_uid == row.parent_item_uid &&
	       item_owner_identity_equal(custody.owner, row.payload_owner);
}

std::vector<uint64_t> physical_roots(const std::vector<artifact_payload_projection> &items,
				     const std::set<uint64_t> &conflicting_uids)
{
	std::map<row_key, size_t> rows;
	for (size_t index = 0; index < items.size(); ++index)
		if (items[index].row_id && items[index].role != artifact_payload_role::history &&
		    items[index].role != artifact_payload_role::reconstruction)
		{
			auto [found, inserted] =
				rows.emplace(key(items[index], items[index].row_id), index);
			if (!inserted)
				found->second = items.size(); // ambiguous source-local ID
		}
	std::vector<uint64_t> roots(items.size());
	std::vector<uint8_t> visited(items.size());
	std::vector<size_t> path;
	for (size_t index = 0; index < items.size(); ++index)
	{
		if (visited[index])
			continue;
		path.clear();
		size_t cursor = index;
		uint64_t root = 0;
		while (!visited[cursor])
		{
			visited[cursor] = 1;
			path.push_back(cursor);
			const auto &row = items[cursor];
			const auto own = rows.find(key(row, row.row_id));
			if (!row.item_uid || conflicting_uids.count(row.item_uid) ||
			    row.parent_missing || row.parent_owner_disagrees || own == rows.end() ||
			    own->second != cursor)
				break;
			if (!row.parent_row_id)
			{
				if (!row.parent_item_uid)
					root = row.item_uid;
				break;
			}
			const auto parent = rows.find(key(row, row.parent_row_id));
			if (parent == rows.end() || parent->second == items.size() ||
			    !row.parent_item_uid ||
			    items[parent->second].item_uid != row.parent_item_uid)
				break;
			cursor = parent->second;
			if (visited[cursor] == 2)
				root = roots[cursor];
		}
		for (auto entry = path.rbegin(); entry != path.rend(); ++entry)
		{
			const auto &row = items[*entry];
			if ((row.payload_root_item_uid && row.payload_root_item_uid != root) ||
			    !qualified(row, root))
				root = 0;
			roots[*entry] = root;
			visited[*entry] = 2;
		}
	}
	return roots;
}

struct vnum_evidence
{
	artifact_population_identity previous;
	std::vector<size_t> payloads;
};
} // namespace

unsigned int
artifact_population_classify(const std::vector<artifact_payload_projection> &items,
			     const std::vector<artifact_population_template> &prototypes,
			     const std::vector<artifact_population_identity> &previous,
			     bool complete, std::vector<artifact_population_decision> *decisions)
{
	if (!decisions)
		return EINVAL;
	if (items.size() > ARTIFACT_IDENTITY_MAX_RECORDS ||
	    prototypes.size() > ARTIFACT_IDENTITY_MAX_RECORDS ||
	    previous.size() > ARTIFACT_IDENTITY_MAX_RECORDS)
		return E2BIG;
	try
	{
		std::map<int32_t, uint64_t> flags;
		std::map<int32_t, vnum_evidence> evidence;
		for (const auto &prototype : prototypes)
		{
			if (prototype.vnum <= 0 ||
			    !flags.emplace(prototype.vnum, prototype.extra_flags).second)
				return EINVAL;
			if (prototype.extra_flags & ITEM_ARTIFACT)
				evidence[prototype.vnum].previous.vnum = prototype.vnum;
		}
		std::set<int32_t> prior_vnums;
		std::map<uint64_t, int32_t> prior_uids;
		for (const auto &identity : previous)
		{
			if (identity.vnum <= 0 ||
			    !artifact_identity_valid(identity.canonical_item_uid, identity.state) ||
			    !prior_vnums.insert(identity.vnum).second ||
			    (identity.canonical_item_uid &&
			     !prior_uids.emplace(identity.canonical_item_uid, identity.vnum).second))
				return EINVAL;
			evidence[identity.vnum].previous = identity;
		}
		// A UID used for different current vnums cannot qualify either object.
		std::map<uint64_t, int32_t> uid_vnums;
		std::map<uint64_t, bool> uid_artifacts;
		std::map<std::pair<int64_t, uint64_t>, uint64_t> latest_delivery;
		for (const auto &row : items)
			if (row.role == artifact_payload_role::delivery)
				latest_delivery[{ row.owner_reference, row.item_uid }] = std::max(
					latest_delivery[{ row.owner_reference, row.item_uid }],
					row.delivery_ordinal);
		const auto superseded = [&](const artifact_payload_projection &row)
		{
			return row.role == artifact_payload_role::delivery &&
			       row.delivery_ordinal <
				       latest_delivery.at({ row.owner_reference, row.item_uid });
		};
		std::set<row_key> source_uids;
		std::set<uint64_t> conflicting_uids;
		for (size_t index = 0; index < items.size(); ++index)
		{
			const auto &row = items[index];
			if (row.vnum <= 0 ||
			    row.domain > artifact_payload_domain::copyover_reconstruction ||
			    row.role > artifact_payload_role::reconstruction)
				return EINVAL;
			if (row.item_uid && row.role != artifact_payload_role::history &&
			    row.role != artifact_payload_role::reconstruction && !superseded(row))
			{
				if (!source_uids.insert(key(row, row.item_uid)).second)
					conflicting_uids.insert(row.item_uid);
				const auto [found, inserted] =
					uid_vnums.emplace(row.item_uid, row.vnum);
				const auto prior = prior_uids.find(row.item_uid);
				if ((!inserted && found->second != row.vnum) ||
				    (prior != prior_uids.end() && prior->second != row.vnum))
					conflicting_uids.insert(row.item_uid);
				if (row.extra_flags_present)
				{
					const bool artifact = (row.extra_flags & ITEM_ARTIFACT) !=
							      0;
					const auto [prior_flags, new_flags] =
						uid_artifacts.emplace(row.item_uid, artifact);
					if (!new_flags && prior_flags->second != artifact)
						conflicting_uids.insert(row.item_uid);
				}
			}
			const bool artifact = !row.extra_flags_present ||
					      (row.extra_flags & ITEM_ARTIFACT) != 0;
			if (artifact || evidence.count(row.vnum))
			{
				auto &entry = evidence[row.vnum];
				entry.previous.vnum = row.vnum;
				entry.payloads.push_back(index);
			}
		}
		if (evidence.size() > ARTIFACT_IDENTITY_MAX_RECORDS)
			return E2BIG;
		const auto roots = physical_roots(items, conflicting_uids);
		std::vector<artifact_population_decision> staged;
		staged.reserve(evidence.size());
		for (const auto &[vnum, entry] : evidence)
		{
			artifact_population_decision decision;
			decision.identity = entry.previous;
			std::map<uint64_t, std::vector<size_t>> candidates;
			bool uncertain = false, retired_payload = false;
			std::set<uint64_t> unqualified_uids;
			for (const auto index : entry.payloads)
			{
				const auto &row = items[index];
				if (row.role == artifact_payload_role::reconstruction ||
				    superseded(row))
					continue;
				if (row.role == artifact_payload_role::history)
				{
					// Retained templates/history do not prove physical presence.
					// Active/quarantined custody without a current body is still
					// contradictory evidence, handled after candidate correlation.
					continue;
				}
				if (entry.previous.state == artifact_identity_state::retired &&
				    row.item_uid == entry.previous.canonical_item_uid)
				{
					retired_payload = true;
					continue;
				}
				const auto prototype = flags.find(vnum);
				const bool artifact = !row.extra_flags_present ||
						      (row.extra_flags & ITEM_ARTIFACT) != 0;
				if (!artifact)
				{
					// A saved explicit zero overrides today's prototype. It is
					// ordinary, unless it contradicts an established identity.
					uncertain =
						uncertain ||
						(row.item_uid &&
						 row.item_uid == entry.previous.canonical_item_uid);
					continue;
				}
				if (prototype == flags.end() || !roots[index])
				{
					if (row.item_uid)
						unqualified_uids.insert(row.item_uid);
					else
						uncertain = true;
					continue;
				}
				candidates[row.item_uid].push_back(index);
			}
			// Two qualified projections may describe one identity, but they must
			// agree about its current owner, topology and effective flags. Never
			// pick between incompatible same-UID images by traversal order.
			for (auto candidate = candidates.begin(); candidate != candidates.end();)
			{
				const auto &first = items[candidate->second.front()];
				const bool conflict = std::any_of(
					candidate->second.begin(), candidate->second.end(),
					[&](size_t index)
					{
						const auto &row = items[index];
						return !item_owner_identity_equal(
							       first.payload_owner,
							       row.payload_owner) ||
						       roots[candidate->second.front()] !=
							       roots[index] ||
						       first.parent_item_uid !=
							       row.parent_item_uid ||
						       (first.extra_flags_present &&
							row.extra_flags_present &&
							first.extra_flags != row.extra_flags);
					});
				if (conflict)
				{
					uncertain = true;
					candidate = candidates.erase(candidate);
				}
				else
					++candidate;
			}
			for (const auto index : entry.payloads)
			{
				const auto &row = items[index];
				if (row.role == artifact_payload_role::history &&
				    (row.source_quarantined ||
				     (row.item_uid && !row.custody_examined) ||
				     (row.custody_found &&
				      (row.custody.state == item_custody_state::active ||
				       row.custody.state == item_custody_state::quarantined))) &&
				    !candidates.count(row.item_uid))
					uncertain = true;
			}
			for (const auto uid : unqualified_uids)
				uncertain = uncertain || !candidates.count(uid);
			const auto known = candidates.find(entry.previous.canonical_item_uid);
			if (entry.previous.state == artifact_identity_state::present &&
			    known != candidates.end())
			{
				decision.reason = complete ? artifact_population_reason::complete :
							     artifact_population_reason::incomplete;
				decision.canonical_payloads = known->second;
			}
			else if (!complete)
			{
				// Unknown sources block absence and new selection. A qualified
				// established UID above can still hydrate from its exact source.
				if (!decision.identity.canonical_item_uid)
					decision.identity.state =
						artifact_identity_state::unresolved;
			}
			else if (!uncertain && candidates.size() == 1 && !retired_payload &&
				 (entry.previous.state == artifact_identity_state::unresolved ||
				  entry.previous.state == artifact_identity_state::absent))
			{
				decision.identity.canonical_item_uid = candidates.begin()->first;
				decision.identity.state = artifact_identity_state::present;
				decision.reason = artifact_population_reason::complete;
				decision.canonical_payloads = candidates.begin()->second;
			}
			else if (!uncertain && candidates.empty() && !retired_payload)
			{
				if (entry.previous.state != artifact_identity_state::retired)
				{
					decision.identity.canonical_item_uid = 0;
					decision.identity.state = artifact_identity_state::absent;
				}
				decision.reason = artifact_population_reason::complete;
			}
			else
			{
				if (!decision.identity.canonical_item_uid)
					decision.identity.state =
						artifact_identity_state::unresolved;
				decision.reason =
					(candidates.size() > 1 ||
					 ((entry.previous.state ==
						   artifact_identity_state::present ||
					   entry.previous.state ==
						   artifact_identity_state::retired) &&
					  !candidates.empty())) ?
						artifact_population_reason::conflicting_identities :
					retired_payload ?
						artifact_population_reason::retired_payload :
						artifact_population_reason::unqualified_payload;
			}
			staged.push_back(std::move(decision));
		}
		*decisions = std::move(staged);
		return 0;
	}
	catch (const std::bad_alloc &)
	{
		return ENOMEM;
	}
}
