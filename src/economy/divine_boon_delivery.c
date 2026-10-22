#include "economy/divine_boon_delivery.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "guild/artifact_guild_transaction.h"
#include "persistence/persistence_checkpoint.h"
#include "world/epic.h"

#include <algorithm>
#include <limits>
#include <map>
#include <new>

namespace
{
std::map<uint32_t, std::map<uint64_t, divine_epic_delivery>> pending;

bool apply(P_char ch, const divine_epic_delivery &delivery)
{
	if (!ch || IS_NPC(ch) || GET_PID(ch) != static_cast<int>(delivery.pid) ||
	    !divine_epic_delivery_valid(delivery))
		return false;
	auto *pc = ch->only.pc;
	if (delivery.sequence <= pc->divine_boon_delivery_seq)
		return true;
	if (delivery.previous != pc->divine_boon_delivery_seq ||
	    pc->epics > std::numeric_limits<int64_t>::max() - delivery.amount)
		return false;
	// Level/achievement hooks can request saves while publishing. Hold those
	// captures until the balance, watermark and all recipient effects agree.
	pc->divine_boon_delivery_applying = true;
	// This receipt is committed before completion delivery or login recovery.
	// Defer the artifact/guild effect alongside its epic award.
	if (!artifact_guild_transaction_submit(ch, delivery.operation_id,
					       static_cast<int>(delivery.amount), EPIC_PVP))
		logit(LOG_STATUS,
		      "Divine epic receipt committed, but artifact/guild effect unavailable.");
	pc->epics += delivery.amount;
	pc->epic_revision = std::max(pc->epic_revision, delivery.sequence);
	pc->divine_boon_delivery_seq = delivery.sequence;
	epic_publish_pvp_award(ch, static_cast<int>(delivery.amount));
	if (delivery.spill_blood)
		if (auto *task = get_epic_task(ch);
		    task && (task->modifier == SPILL_BLOOD || task->modifier == -SPILL_BLOOD))
			affect_remove(ch, task);
	pc->divine_boon_delivery_applying = false;
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS |
							  PLAYER_COMPONENT_AFFECTS |
							  PLAYER_COMPONENT_SKILLS);
	if (pc->divine_boon_delivery_ready)
		writeCharacter(ch, 1, NOWHERE);
	return true;
}

void publish_pending(P_char ch)
{
	if (!ch || IS_NPC(ch) || !ch->only.pc->divine_boon_delivery_ready)
		return;
	auto found = pending.find(static_cast<uint32_t>(GET_PID(ch)));
	if (found == pending.end())
		return;
	while (!found->second.empty())
	{
		auto next = found->second.begin();
		if (!apply(ch, next->second))
			break; // An older receipt must arrive or be recovered first.
		found->second.erase(next);
	}
	if (found->second.empty())
		pending.erase(found);
}
}

void divine_boon_delivery_completed(const divine_epic_delivery &delivery)
{
	if (!divine_epic_delivery_valid(delivery))
		return;
	P_char ch = find_player_by_pid(delivery.pid);
	if (!ch || IS_NPC(ch))
		return; // The durable parent receipt is read by the next login.
	if (delivery.sequence <= ch->only.pc->divine_boon_delivery_seq)
		return;
	try
	{
		auto &waiting = pending[delivery.pid];
		if (waiting.size() >= DIVINE_EPIC_RECOVERY_MAX)
		{
			logit(LOG_STATUS,
			      "Divine epic delivery retained for reconnect: pending limit reached.");
			return;
		}
		waiting.emplace(delivery.sequence, delivery);
	}
	catch (const std::bad_alloc &)
	{
		logit(LOG_STATUS,
		      "Divine epic delivery retained for reconnect: insufficient memory.");
		return;
	}
	publish_pending(ch);
}

bool divine_boon_delivery_recover(P_char ch, const std::vector<divine_epic_delivery> &deliveries)
{
	if (!ch || IS_NPC(ch) || deliveries.size() > DIVINE_EPIC_RECOVERY_MAX)
		return false;
	uint64_t previous = ch->only.pc->divine_boon_delivery_seq;
	int64_t balance = ch->only.pc->epics;
	for (const auto &delivery : deliveries)
	{
		if (!divine_epic_delivery_valid(delivery) ||
		    delivery.pid != static_cast<uint32_t>(GET_PID(ch)))
			return false;
		if (delivery.sequence <= previous)
			continue;
		if (delivery.previous != previous || balance > INT64_MAX - delivery.amount)
			return false;
		previous = delivery.sequence;
		balance += delivery.amount;
	}
	for (const auto &delivery : deliveries)
		if (!apply(ch, delivery))
			return false;
	return true;
}

void divine_boon_delivery_player_ready(P_char ch)
{
	if (!ch || IS_NPC(ch))
		return;
	ch->only.pc->divine_boon_delivery_ready = true;
	publish_pending(ch);
}
