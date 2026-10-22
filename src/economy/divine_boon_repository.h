#ifndef DIVINE_BOON_REPOSITORY_H
#define DIVINE_BOON_REPOSITORY_H

#include "economy/divine_boon.h"

#include <mysql/mysql.h>
#include <string>

enum class divine_boon_store_result
{
	ok,
	not_found,
	already_applied,
	conflict,
	invalid,
	io_error,
};

// Read at boot, before admitting gameplay. Save on the existing persistence
// writer, then publish the confirmed snapshot. Expected revision zero creates
// the initial state; every subsequent save advances exactly one revision. SQL
// calls use an autocommit connection, outside any enclosing transaction.
divine_boon_store_result divine_boon_sql_load(MYSQL *connection, divine_boon_state *state);
divine_boon_store_result divine_boon_sql_save(MYSQL *connection, uint64_t expected_revision,
					      const divine_boon_state &state);
divine_boon_store_result divine_boon_flatfile_load(const std::string &root,
						   divine_boon_state *state);
divine_boon_store_result divine_boon_flatfile_save(const std::string &root,
						   uint64_t expected_revision,
						   const divine_boon_state &state);

#endif
