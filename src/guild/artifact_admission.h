#ifndef DURIS_ARTIFACT_ADMISSION_H
#define DURIS_ARTIFACT_ADMISSION_H

#include "core/structs.h"

// Game-thread fresh creation only. Reserves before constructor procedures run.
// Refusal sets EEXIST (reserved), ENODATA (unresolved), or ENOMEM (unavailable).
// No persistence is queued until successful placement commits the claim.
bool artifact_begin_creation(P_obj object);
// Placement commits a fresh claim or registers an already canonical saved UID.
void artifact_object_placed(P_obj object);
// Pending creation rolls back. Committed physical retirement retains a UID
// tombstone; unloading merely detaches the live pointer.
void artifact_object_extracted(P_obj object, bool physical_retirement);
bool artifact_is_canonical(P_obj object);

// Native/Redis restoration is a group: defer artifact captures and restore the
// existing maps if any later world step fails. One game-thread scope at a time.
class artifact_restore_scope
{
    public:
	artifact_restore_scope();
	~artifact_restore_scope();
	artifact_restore_scope(const artifact_restore_scope &) = delete;
	artifact_restore_scope &operator=(const artifact_restore_scope &) = delete;
	explicit operator bool() const { return active_; }
	void commit();

    private:
	bool active_ = false;
};

#endif
