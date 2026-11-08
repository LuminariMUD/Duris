#ifndef DURIS_FORCED_MOVEMENT_H
#define DURIS_FORCED_MOVEMENT_H

#include "core/structs.h"
#include <functional>
#include <string>
#include <utility>
#include <vector>

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

using forced_departure_message = std::pair<uint64_t, std::string>;
// Render names before anyone leaves; deliver only after departure hooks allow movement.
std::vector<forced_departure_message>
snapshot_forced_departure(P_char actor, P_char victim, const char *actor_text,
			  const char *victim_text, const char *room_text, P_obj object = nullptr);
void deliver_forced_departure(const std::vector<forced_departure_message> &messages, P_char actor,
			      P_char victim, int source, bool paired);
forced_move_result move_forced_mounted(P_char rider, P_char victim, int direction,
				       const std::function<void()> &departure);

forced_block map_entry_barrier(P_char ch, int source, int destination);
forced_move_result move_forced(P_char actor, P_char victim, int direction,
			       const std::function<void()> &departure);
forced_move_result move_forced_pair(P_char first, P_char second, int direction,
				    const std::function<void()> &departure);

#endif
