#include "persistence/deferred_save_policy.h"

int deferred_save_next_retry_delay(int current)
{
	if (current < PERSISTENCE_DEFERRED_RETRY_INITIAL)
		return PERSISTENCE_DEFERRED_RETRY_INITIAL;
	if (current >= PERSISTENCE_DEFERRED_RETRY_MAX / 2)
		return PERSISTENCE_DEFERRED_RETRY_MAX;
	return current * 2;
}
