/****************************************************************************
 *
 *  File: collector_death_enrollment.c                          Part of Duris
 *  Usage: enrolls a player's death into collector intake
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "economy/collector_death_enrollment.h"

#include "classes/necromancy.h"
#include "core/defines.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "economy/collector_catalog_cache.h"
#include "economy/collector_config.h"
#include "economy/collector_notification.h"

#include <new>
#include <unordered_map>

namespace
{
constexpr size_t PENDING_DEATH_MAX = 1024;

std::unordered_map<uint64_t, collector_death_snapshot> pending;

uint64_t death_key(P_obj corpse)
{
	if (!corpse || GET_ITEM_TYPE(corpse) != ITEM_CORPSE ||
	    !IS_SET(corpse->value[CORPSE_FLAGS], PC_CORPSE) || corpse->value[CORPSE_PID] <= 0 ||
	    corpse->value[CORPSE_SAVEID] <= 0)
		return 0;
	return item_corpse_owner_id(static_cast<uint32_t>(corpse->value[CORPSE_PID]),
				    static_cast<uint32_t>(corpse->value[CORPSE_SAVEID]));
}
}

void collector_death_enrollment_begin(P_char character, P_obj corpse)
{
	const uint64_t key = death_key(corpse);
	if (!key || !character || !IS_PC(character) ||
	    corpse->value[CORPSE_PID] != GET_PID(character))
		return;
	const collector_feature_config *config = collector_config_get();
	if (!config->policy.enabled)
		return;
	if (pending.size() >= PENDING_DEATH_MAX && !pending.contains(key))
	{
		logit(LOG_STATUS,
		      "Collector death intake saturated; corpse %llu will not be enrolled.",
		      static_cast<unsigned long long>(corpse->obj_uid));
		return;
	}
	collector_death_snapshot death;
	if (!critical_operation_id_generate(&death.operation_id))
		return;
	death.beneficiary_pid = static_cast<uint32_t>(GET_PID(character));
	death.death_time = static_cast<uint64_t>(corpse->value[CORPSE_SAVEID]);
	death.policy = config->policy;
	try
	{
		pending[key] = death;
	}
	catch (const std::bad_alloc &)
	{
		logit(LOG_STATUS,
		      "Collector death intake allocation failed; corpse %llu will not be enrolled.",
		      static_cast<unsigned long long>(corpse->obj_uid));
	}
}

bool collector_death_enrollment_for(P_obj corpse, collector_death_snapshot *death)
{
	const auto found = pending.find(death_key(corpse));
	if (found == pending.end())
		return false;
	*death = found->second;
	return true;
}

void collector_death_enrollment_saved(uint64_t corpse_owner_id, unsigned int refused)
{
	const auto found = pending.find(corpse_owner_id);
	if (found == pending.end())
		return;
	if (refused)
		logit(LOG_STATUS, "Collector death intake refused for pid %u: error %u.",
		      found->second.beneficiary_pid, refused);
	pending.erase(found);
	collector_catalog_cache_invalidate();
	collector_notification_death_enrolled();
}

void collector_death_enrollment_reset_for_tests(void)
{
	pending.clear();
}
