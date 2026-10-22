// Weak stubs for the server functions that native harnesses most often do not link.
//
// Compile this file with a harness instead of copying a stub into it. Every definition is
// weak: the real source, when the harness links it, or a harness's own definition (one
// that counts calls, keeps the output or returns a value) replaces it at link time. A
// harness therefore keeps a local stub only where it must behave differently.
#include "core/prototypes.h"
#include "economy/boon_reward_transaction.h"
#include "guild/artifact_admission.h"
#include "persistence/persistence_log.h"
#include "player/player_save_worker.h"
#include "economy/divine_boon_activity.h"

#include <cstdlib>
#include <cerrno>

#define HARNESS_STUB __attribute__((weak))

// Input-queue fixtures do not collect population. The focused Divine activity
// harness links the real observer in place of these no-op boundaries.
HARNESS_STUB divine_boon_input_activity divine_boon_activity_begin(char_data *)
{
	return {};
}
HARNESS_STUB void divine_boon_activity_end(const divine_boon_input_activity &) {}

// Legacy-only fixtures have no Divine runtime. Divine integration harnesses
// link the real gate and exercise draining/unavailable states explicitly.
HARNESS_STUB bool divine_boon_legacy_admissions_allowed()
{
	return true;
}

HARNESS_STUB boon_reward_health boon_reward_transaction_health_copy()
{
	return {};
}

// Fixtures that do not link the artifact authority have no artifact state to
// checkpoint. Focused admission tests and server builds use the real methods.
HARNESS_STUB artifact_restore_scope::artifact_restore_scope()
	: active_(true)
{
}
HARNESS_STUB artifact_restore_scope::~artifact_restore_scope() {}
HARNESS_STUB void artifact_restore_scope::commit()
{
	active_ = false;
}

// Fixtures without artifact state still exercise their ordinary item lifecycle.
HARNESS_STUB void artifact_object_placed(P_obj) {}
HARNESS_STUB bool artifact_reconcile_player_owner(P_obj, const item_ownership_runtime_entry *)
{
	return false;
}
HARNESS_STUB void artifact_object_extracted(P_obj, bool) {}

HARNESS_STUB void logit(const char *, const char *, ...) {}
HARNESS_STUB bool sql_async_booting(void)
{
	return true;
}
HARNESS_STUB player_save_submit_result persistence_writer_submit(persistence_job_kind, uint64_t,
								 size_t, persistence_job_write_fn)
{
	errno = ESHUTDOWN;
	return player_save_submit_result::unavailable;
}
HARNESS_STUB void gmcp_char_vitals(P_char) {}
HARNESS_STUB void debug(const char *, ...) {}
HARNESS_STUB void wizlog(int, const char *, ...) {}
HARNESS_STUB void statuslog(int, const char *, ...) {}
HARNESS_STUB bool persistence_log_submit(const char *)
{
	return true;
}
HARNESS_STUB void sql_log(P_char, const char *, const char *, ...) {}
HARNESS_STUB void persistence_alert(int, const char *, const char *, const char *, const char *,
				    const char *, const char *, ...)
{
}
HARNESS_STUB bool persistence_trace_enabled(void)
{
	return false;
}
HARNESS_STUB void panic_corruption(const char *, const char *, ...)
{
	std::abort();
}
HARNESS_STUB int panic_corruption_int(const char *, const char *, ...)
{
	std::abort();
}

HARNESS_STUB void send_to_char(const char *, P_char) {}
HARNESS_STUB void send_to_char(const char *, P_char, int) {}
HARNESS_STUB void act(const char *, int, P_char, P_obj, void *, int) {}
HARNESS_STUB void update_pos(P_char) {}
HARNESS_STUB void updateShortAffects(P_char) {}
// Snapshot fixtures without short affects only need these symbols to link.
// Tests that exercise scheduled expiry supply their own implementations.
HARNESS_STUB void event_short_affect(P_char, P_char, P_obj, void *)
{
	std::abort();
}
HARNESS_STUB void event_poison(P_char, P_char, P_obj, void *)
{
	std::abort();
}
HARNESS_STUB int ne_event_time(P_nevent)
{
	std::abort();
}
// Scheduler fixtures identify this callback but do not run mana regeneration.
HARNESS_STUB void event_mana_regen(P_char, P_char, P_obj, void *)
{
	std::abort();
}
HARNESS_STUB int process_proxy_protocol(P_desc)
{
	return 0;
}
HARNESS_STUB P_char get_linked_char(P_char, ush_int)
{
	return nullptr;
}
HARNESS_STUB bool has_innate(P_char, int)
{
	return false;
}
HARNESS_STUB bool notch_skill(P_char, int, float)
{
	return false;
}
HARNESS_STUB bool affected_by_spell(P_char, int)
{
	return false;
}
HARNESS_STUB bool isname(const char *, const char *)
{
	return false;
}

// sql/sql_pool.h needs <mysql.h>; the pool's functions have C linkage, so these need not.
extern "C"
{
	typedef struct st_mysql MYSQL;
	HARNESS_STUB MYSQL *sql_pool_acquire(void)
	{
		return nullptr;
	}
	HARNESS_STUB void sql_pool_release(MYSQL *) {}
	HARNESS_STUB MYSQL *sql_pool_replace_connection(MYSQL *)
	{
		return nullptr;
	}
}
