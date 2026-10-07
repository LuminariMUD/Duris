#ifndef DURIS_FALLING_H
#define DURIS_FALLING_H

#include "core/structs.h"

enum class falling_start_result
{
	not_applicable,
	caught,
	scheduled,
	schedule_rejected
};

enum class falling_step_result
{
	stopped,
	continued,
	landed,
	relocated,
	actor_removed,
	movement_rejected,
	schedule_rejected
};

struct falling_event_payload
{
	int speed;
	int room; // where the faller was when the step was scheduled
};

falling_start_result falling_start(P_char ch);
falling_step_result falling_step(P_char ch, int speed);
bool falling_in_progress(P_char ch);
void event_falling_char(P_char ch, P_char victim, P_obj obj, void *data);

#endif // DURIS_FALLING_H
