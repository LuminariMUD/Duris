#ifndef DURIS_FRAG_CAP_REPOSITORY_H
#define DURIS_FRAG_CAP_REPOSITORY_H

#include "combat/frag_cap.h"
#include "combat/combat_outcome_command.h"

#include <mysql/mysql.h>
#include <string>

enum class frag_cap_store_result
{
	ok,
	not_found,
	invalid,
	io_error,
};

bool frag_cap_apply_combat(frag_cap_state *state, const critical_command &command,
			   const combat_outcome_payload &payload, int64_t now,
			   const frag_cap_policy &policy = {});

// SQL mutations borrow the caller's transaction. Load with FOR UPDATE, prepare
// using the common engine, then save before committing the parent receipt.
// These functions never start, commit or roll back a SQL transaction.
frag_cap_store_result frag_cap_sql_load(MYSQL *connection, frag_cap_state *state,
					bool for_update = false);
frag_cap_store_result frag_cap_sql_save(MYSQL *connection, const frag_cap_state &state);
// Activation only: reads the locked legacy row if snapshot is NULL, otherwise
// returns the saved snapshot unchanged. Missing/corrupt singleton is an error.
frag_cap_store_result frag_cap_sql_adopt(MYSQL *connection, int legacy_floor, int legacy_maximum,
					 int64_t now, frag_cap_state *state,
					 const frag_cap_policy &policy = {});
// The caller locks season_reset_state in the same transaction and supplies its
// persisted reset_started_at. Repeated/resumed resets keep the original clock.
frag_cap_store_result frag_cap_sql_reset_season(MYSQL *connection, int64_t reset_started_at,
						const frag_cap_policy &policy = {});

#endif
