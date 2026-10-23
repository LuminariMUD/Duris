#ifndef DIVINE_TRADE_REPOSITORY_H
#define DIVINE_TRADE_REPOSITORY_H

#include "economy/divine_trade_command.h"
#include "persistence/critical_command_completion.h"
#include <mysql/mysql.h>

// Caller owns the SQL transaction. for_update serializes whole-market captures
// and prepared settlement; boot reads once to restore the memory generation.
bool divine_trade_sql_generation(MYSQL *connection, uint64_t *generation, bool for_update);
bool divine_trade_sql_execute(MYSQL *connection, const critical_command &command,
			      divine_trade_result *result, unsigned int *result_code,
			      bool *mutated);
// Boot only; load active account/boon manifests into game-thread memory.
bool divine_trade_sql_books(MYSQL *connection, uint64_t boon_id,
			    std::vector<divine_trade_book> *books);
critical_apply_result divine_trade_flatfile_apply(const std::string &root,
						  const critical_command &command);
bool divine_trade_flatfile_books(const std::string &root, uint64_t boon_id,
				 std::vector<divine_trade_book> *books);

#endif
