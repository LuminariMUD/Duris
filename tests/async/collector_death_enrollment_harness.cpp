#include "economy/collector_config.h"
#include "economy/collector_death_enrollment.h"
#include "economy/collector_eligibility.h"

#include "classes/necromancy.h"
#include "core/prototypes.h"
#include "core/utils.h"

#include <cassert>
#include <cstdarg>
#include <cstdlib>

namespace
{
collector_feature_config config;
int invalidations = 0;
int notifications = 0;

player_item_snapshot item(uint64_t uid)
{
	player_item_snapshot value = {};
	value.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	value.object_uid = uid;
	value.vnum = static_cast<int32_t>(500 + uid);
	value.type = ITEM_WEAPON;
	value.name = "ancient blade";
	value.wear_flags = ITEM_TAKE;
	return value;
}
}

const collector_feature_config *collector_config_get(void)
{
	return &config;
}

void collector_catalog_cache_invalidate(void)
{
	++invalidations;
}

void collector_notification_death_enrolled(void)
{
	++notifications;
}

int main()
{
	// What the collector may take from a corpse.
	auto eligible = item(1);
	assert(collector_death_item_snapshot_eligible(eligible));
	auto permitted_unique = item(2);
	permitted_unique.name = "ancient powerunique blade";
	assert(collector_death_item_snapshot_eligible(permitted_unique));
	for (int excluded = 0; excluded < 9; ++excluded)
	{
		auto value = item(3);
		switch (excluded)
		{
		case 0:
			value.type = ITEM_MONEY;
			break;
		case 1:
			value.type = ITEM_CORPSE;
			break;
		case 2:
			value.extra_flags = ITEM_ARTIFACT;
			break;
		case 3:
			value.name = "ancient unique blade";
			break;
		case 4:
			value.extra_flags = ITEM_TRANSIENT;
			break;
		case 5:
			value.extra_flags = ITEM_NORENT;
			break;
		case 6:
			value.extra_flags = ITEM_NOSELL;
			break;
		case 7:
			value.extra2_flags = ITEM2_ACCOUNT_BOUND;
			break;
		default:
			value.wear_flags = 0;
			break;
		}
		assert(!collector_death_item_snapshot_eligible(value));
	}

	char_data character = {};
	pc_only_data player = {};
	obj_data corpse = {};
	character.only.pc = &player;
	player.pid = 42;
	corpse.obj_uid = 900;
	corpse.type = ITEM_CORPSE;
	corpse.value[CORPSE_FLAGS] = PC_CORPSE;
	corpse.value[CORPSE_PID] = 42;
	corpse.value[CORPSE_SAVEID] = 1700000000;
	const uint64_t owner = item_corpse_owner_id(42, 1700000000);
	collector_death_snapshot death;

	// With the collector off, a death does not enter intake.
	collector_death_enrollment_reset_for_tests();
	collector_death_enrollment_begin(&character, &corpse);
	assert(!collector_death_enrollment_for(&corpse, &death));

	// On, the death takes the policy as it stands, and every save of the corpse carries
	// the same death until one is written.
	config.policy.enabled = true;
	config.policy.collection_delay = 10;
	config.policy.sale_delay = 20;
	config.policy.holding_duration = 30;
	config.policy.price_percent = 250;
	config.policy.minimum_value = 7;
	collector_death_enrollment_begin(&character, &corpse);
	config.policy.collection_delay = 999;
	assert(collector_death_enrollment_for(&corpse, &death));
	assert(!critical_operation_id_is_zero(death.operation_id) && death.beneficiary_pid == 42 &&
	       death.death_time == 1700000000 && death.policy.collection_delay == 10 &&
	       death.policy.sale_delay == 20 && death.policy.minimum_value == 7);
	collector_death_snapshot again;
	assert(collector_death_enrollment_for(&corpse, &again) &&
	       critical_operation_id_equal(again.operation_id, death.operation_id));

	// Another corpse's save leaves it waiting; its own completes it once.
	collector_death_enrollment_saved(owner + 1, 0);
	assert(collector_death_enrollment_for(&corpse, &again) && !invalidations);
	collector_death_enrollment_saved(owner, 0);
	assert(!collector_death_enrollment_for(&corpse, &again));
	assert(invalidations == 1 && notifications == 1);
	collector_death_enrollment_saved(owner, 0);
	assert(invalidations == 1 && notifications == 1);

	// Only a player's own corpse enters intake.
	corpse.value[CORPSE_PID] = 43;
	collector_death_enrollment_begin(&character, &corpse);
	assert(!collector_death_enrollment_for(&corpse, &death));
	corpse.value[CORPSE_PID] = 42;
	corpse.value[CORPSE_FLAGS] = 0;
	collector_death_enrollment_begin(&character, &corpse);
	assert(!collector_death_enrollment_for(&corpse, &death));
	return 0;
}
