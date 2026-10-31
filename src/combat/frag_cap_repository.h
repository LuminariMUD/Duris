#ifndef DURIS_FRAG_CAP_REPOSITORY_H
#define DURIS_FRAG_CAP_REPOSITORY_H

#include "combat/frag_cap.h"
#include "flatfile/flatfile_authority_transaction.h"

#include <mysql/mysql.h>
#include <string>

enum class frag_cap_store_result
{
	ok,
	not_found,
	invalid,
	io_error,
};

// SQL mutations borrow the caller's transaction. Load with FOR UPDATE, prepare
// using the common engine, then save before committing the parent receipt.
// These functions never start, commit or roll back a SQL transaction.
frag_cap_store_result frag_cap_sql_load(MYSQL *connection, frag_cap_state *state,
					bool for_update = false);
frag_cap_store_result frag_cap_sql_save(MYSQL *connection, const frag_cap_state &state);
// Activation only: reads the locked legacy row if snapshot is NULL, otherwise
// returns the saved snapshot unchanged. Missing/corrupt singleton is an error.
frag_cap_store_result frag_cap_sql_adopt(MYSQL *connection, int legacy_floor, int64_t now,
					 frag_cap_state *state, const frag_cap_policy &policy = {});

// Borrow the already recovered authority lock; append the after-image to the
// parent's operation vector. No nested lock or standalone cap commit is allowed.
frag_cap_store_result frag_cap_flatfile_load_locked(const std::string &root,
						    const flatfile_authority_lock &lock,
						    frag_cap_state *state);
frag_cap_store_result
frag_cap_flatfile_prepare(const std::string &root, const flatfile_authority_lock &lock,
			  const frag_cap_state &state,
			  std::vector<flatfile_authority_operation> *operations);
// Boot, observation and timer callers without a parent lock use these paths.
frag_cap_store_result frag_cap_flatfile_load(const std::string &root, frag_cap_state *state);
frag_cap_store_result frag_cap_flatfile_adopt(const std::string &root, int legacy_floor,
					      int64_t now, frag_cap_state *state,
					      const frag_cap_policy &policy = {});
frag_cap_store_result frag_cap_flatfile_tick(const std::string &root, int64_t now,
					     const frag_cap_policy &policy = {});

#endif
