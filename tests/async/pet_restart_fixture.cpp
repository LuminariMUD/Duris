// Offline encoder for the pet restart journey: the restore state is a real codec payload,
// the rest of the fixture is plain SQL in test_pet_restart_journey.py.
#include "core/structs.h"
#include "core/defines.h"
#include "magic/spells.h"
#include "player/pet_restore_state.h"
#include <cassert>
#include <ctime>
#include <iostream>
#include <string>

int main(int argc, char **argv)
{
	assert(argc >= 2);
	const std::string mode = argv[1];
	pet_restore_state state;
	if (mode == "constants")
	{
		std::cout << "APPLY_HIT=" << APPLY_HIT << " WEAR_BODY=" << WEAR_BODY
			  << " ITEM_ARTIFACT=" << ITEM_ARTIFACT
			  << " TAG_SKILL_TIMER=" << TAG_SKILL_TIMER
			  << " TIMER_FLAGS=" << (AFFTYPE_STORE | AFFTYPE_SHORT | AFFTYPE_OFFLINE)
			  << " TIMER_DURATION=" << 300 * WAIT_SEC << " SPELLS=" << SPELL_STONE_SKIN
			  << ',' << SPELL_CONJURE_ELEMENTAL << ',' << SPELL_INVIGORATE << '\n';
		return 0;
	}
	if (mode == "seed")
	{
		assert(argc == 3);
		const int index = std::stoi(argv[2]);
		state.kind = summoned_pet_kind::undead_first;
		state.name = "skeleton fixture" + std::to_string(index) + " _Taverek_";
		state.short_description = "the skeleton of fixture" + std::to_string(index);
		state.long_description =
			"The skeleton of fixture" + std::to_string(index) + " waits here.\r\n";
		state.level = 21;
		state.race = RACE_SKELETON;
		state.size = SIZE_MEDIUM;
		state.primary_class = CLASS_WARRIOR;
		state.base_stats.fill(95);
		state.base_points = { 1234, 55, 100, -50, 17, 19, 0 };
		state.damage_dice = { 2, 8 };
		state.spell_slots[2] = 7;
		state.act = ACT_ISNPC | ACT_SENTINEL;
		if (index == 1)
		{
			state.charm_expires_at = time(nullptr) + 240;
			state.death_expires_at = time(nullptr) + 300;
		}
	}
	else
	{
		assert(argc == 3);
		assert(pet_restore_state_decode(argv[2], &state));
		if (mode == "cooldowns")
		{
			for (size_t i = 0; i < state.named_set_cooldowns.size(); ++i)
				if (state.named_set_cooldowns[i])
					std::cout << "pet|" << i << '|'
						  << state.named_set_cooldowns[i] << '\n';
			return 0;
		}
		if (mode == "arm-expiry")
		{
			if (!state.death_expires_at)
				return 1;
			state.charm_expires_at = time(nullptr) + 12;
			state.death_expires_at = time(nullptr) + 18;
		}
		else
		{
			assert(mode == "arm-cooldowns");
			state.version = 2;
			state.named_set_cooldowns.fill(time(nullptr) + 300);
		}
	}
	std::string encoded;
	assert(pet_restore_state_encode(state, &encoded));
	std::cout << encoded;
}
