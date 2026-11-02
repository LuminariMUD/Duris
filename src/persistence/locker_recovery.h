#ifndef LOCKER_RECOVERY_H
#define LOCKER_RECOVERY_H

#include "player/player_snapshot_repository.h"

// Public contents use the normal named-locker save; private contents retain their
// chest identity. An incomplete image is evidence for staff, never a replacement.
struct locker_recovery_entry
{
	locker_snapshot contents;
	int32_t locker_id = 0;
	int32_t chest_id = 0; // zero: public chest
};

// Boot, before custody cleanup or any live loads. Refuse boot on unresolved data.
bool locker_recovery_boot(void);
// Shutdown only: freeze memory, then publish on a child with no database access.
// The finish uses the writer's existing monotonic deadline, never a new wait.
void locker_recovery_begin(void);
void locker_recovery_finish(uint64_t deadline_usec);

// Implemented beside the live locker representation. Never moves objects or
// invokes LockerToPFile, private saves, purchase callbacks, or departure hooks.
bool locker_shutdown_capture(std::vector<locker_recovery_entry> *entries,
			     std::vector<player_snapshot> *players);

#endif
