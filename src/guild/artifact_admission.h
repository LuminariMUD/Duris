#ifndef DURIS_ARTIFACT_ADMISSION_H
#define DURIS_ARTIFACT_ADMISSION_H

#include "core/structs.h"

// Game-thread fresh creation only. Reserves before constructor procedures run.
// Refusal sets EEXIST (reserved), ENODATA (unresolved), or ENOMEM (unavailable).
// No persistence is queued until successful placement commits the claim.
bool artifact_begin_creation(P_obj object);
struct artifact_payload_projection;
// Materialized player payloads use a consistent source cut plus current custody.
// Zero also covers ordinary objects; a known canonical UID cannot clear its flag.
unsigned int artifact_player_source_error(const artifact_payload_projection &source,
					  P_obj object = nullptr);
// Qualified player or pinned ground payload: saved UID/flags precede procedures.
// Player payloads match current custody; ground payloads match a pinned boot projection.
bool artifact_begin_recovery(P_obj object, const artifact_payload_projection &source);
P_obj read_object_for_recovery(const artifact_payload_projection &source);
// Placement commits the pending purpose or registers a canonical saved UID.
// Recovery and registration preserve timer/soul state.
void artifact_object_placed(P_obj object);
// Pending admission rolls back. Committed physical retirement retains a UID
// tombstone; unloading merely detaches the live pointer.
void artifact_object_extracted(P_obj object, bool physical_retirement);
bool artifact_is_canonical(P_obj object);
// Read-only catalog membership, including unresolved/absent known identities.
// Boot uses this to retain prototype values for later constructor-free queries.
bool artifact_tracks_vnum(int vnum);

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
