// Weak stubs for the server functions that native harnesses most often do not link.
//
// Compile this file with a harness instead of copying a stub into it. Every definition is
// weak: the real source, when the harness links it, or a harness's own definition (one
// that counts calls, keeps the output or returns a value) replaces it at link time. A
// harness therefore keeps a local stub only where it must behave differently.
#include "core/prototypes.h"
#include "account/account.h"
#include "economy/boon_reward_transaction.h"
#include "economy/shop_trade_transaction.h"
#include "guild/artifact_admission.h"
#include "guild/artifact_guild_delivery.h"
#include "guild/artifact_guild_state.h"
#include "persistence/persistence_log.h"
#include "player/player_save_worker.h"
#include "economy/divine_boon_activity.h"
#include "economy/divine_boon_delivery.h"
#include "sql/sql_async.h"
#include "economy/divine_trade_runtime.h"

#include <cstdlib>
#include <cerrno>

#define HARNESS_STUB __attribute__((weak))
HARNESS_STUB bool shop_trade_transaction_blocks_commands(P_char)
{
	return false;
}
// Isolated affect/abort fixtures have no shoreline movement callback to execute.
HARNESS_STUB void event_water_crossing(P_char, P_char, P_obj, void *) {}
// Isolated terminal-save fixtures have no account projection or departure state.
// Account lifecycle tests link the real implementation or supply their own boundary.
HARNESS_STUB int sync_account_character_projection(P_char, int, int)
{
	return 1;
}
HARNESS_STUB bool save_account_character_departure(P_char)
{
	return true;
}
// Ordinary NPC fixtures use their own race. Tutorial profile/parity coverage
// links the real lookup, including the full-world read_mobile_probe comparison.
HARNESS_STUB int tutorial_mobile_mechanics_race(char_data *ch)
{
	return ch->player.race;
}
HARNESS_STUB bool divine_trade_runtime_save_busy(const ShipData *)
{
	return false;
}

// Legacy-only load/transaction fixtures carry no prepared Divine receipts.
// Dedicated delivery tests link the real publication and recovery implementation.
HARNESS_STUB void divine_boon_delivery_completed(const divine_epic_delivery &) {}
HARNESS_STUB bool divine_boon_delivery_recover(char_data *,
					       const std::vector<divine_epic_delivery> &deliveries)
{
	return deliveries.empty();
}
HARNESS_STUB void divine_boon_delivery_player_ready(char_data *) {}
HARNESS_STUB bool critical_command_coordinator_is_fenced(const critical_entity_key &,
							 critical_operation_id *)
{
	return false;
}

// Input-queue fixtures do not collect population. The focused Divine activity
// harness links the real observer in place of these no-op boundaries.
HARNESS_STUB divine_boon_input_activity divine_boon_activity_begin(char_data *, int)
{
	return {};
}
HARNESS_STUB void divine_boon_activity_end(const divine_boon_input_activity &) {}
HARNESS_STUB void divine_boon_runtime_pulse() {}
HARNESS_STUB bool divine_boon_runtime_pending()
{
	return false;
}
HARNESS_STUB int ordered_command_number(const char *)
{
	return 0;
}

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
HARNESS_STUB bool sql_read_at(persistence_query_site, std::string,
			      std::function<void(bool, const sql_rows &)>)
{
	return false;
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

// sql_async.h supplies the backend's MYSQL type; the pool has C linkage.
extern "C"
{
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

// Unrelated harnesses have no hydrated prepared-effect service. Focused tests
// link the real delivery module or explicitly control its projection boundary.
HARNESS_STUB bool artifact_guild_delivery_boot()
{
	return false;
}
HARNESS_STUB bool artifact_guild_delivery_reserve(const std::vector<critical_command> &commands)
{
	return commands.empty();
}
HARNESS_STUB void artifact_guild_delivery_complete(const std::vector<critical_command> &, bool) {}
HARNESS_STUB void artifact_guild_delivery_pulse() {}
HARNESS_STUB size_t artifact_guild_delivery_pending()
{
	return 0;
}
HARNESS_STUB bool artifact_guild_delivery_holds(uint64_t)
{
	return false;
}
HARNESS_STUB critical_outbox_delivery_result
artifact_guild_delivery_outbox(const critical_outbox_record &)
{
	return critical_outbox_delivery_result::terminal_failure;
}
HARNESS_STUB artifact_guild_capture_status artifact_guild_state_prepare_delivery(
	P_char, int, int, const critical_operation_id &, critical_command *)
{
	return artifact_guild_capture_status::unavailable;
}

// Ordinary-container fixtures have no live locker registry. The private-chest
// regression links production access and audit routing instead of these boundaries.
HARNESS_STUB bool locker_container_access_allowed(P_char, P_obj)
{
	return true;
}
HARNESS_STUB void locker_record_movement(P_char, P_obj, P_obj, bool, const char *) {}
HARNESS_STUB bool currency_transaction_chest_busy(P_char)
{
	return false;
}

HARNESS_STUB bool locker_object_is_private_chest(P_obj)
{
	return false;
}
HARNESS_STUB bool sql_chest_log_available(void)
{
	return true;
}

HARNESS_STUB bool auction_transaction_player_busy(P_char)
{
	return false;
}

HARNESS_STUB bool collector_transaction_player_busy(P_char)
{
	return false;
}

HARNESS_STUB bool shop_trade_transaction_player_busy(P_char)
{
	return false;
}
