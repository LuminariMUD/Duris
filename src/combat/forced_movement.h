#ifndef DURIS_FORCED_MOVEMENT_H
#define DURIS_FORCED_MOVEMENT_H

#include "core/structs.h"
#include <functional>

enum class forced_block
{
	none,
	mountain,
	cavern_wall,
	door,
	barrier,
	private_room,
	invalid_room
};

enum class forced_move_status
{
	arrived,
	blocked,
	interrupted
};

struct forced_move_result
{
	forced_move_status status;
	forced_block reason = forced_block::none;
};

forced_block map_entry_barrier(P_char ch, int source, int destination);
forced_move_result move_forced(P_char actor, P_char victim, int direction,
			       const std::function<void()> &departure);
forced_move_result move_forced_pair(P_char first, P_char second, int direction,
				    const std::function<void()> &departure);

#endif
