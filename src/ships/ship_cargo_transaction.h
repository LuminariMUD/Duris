#ifndef SHIP_CARGO_TRANSACTION_H
#define SHIP_CARGO_TRANSACTION_H

#include "economy/divine_trade_command.h"

divine_trade_market_cell cargo_trade_prepare_cell(int transaction, int location, int type,
						  int volume, float before = -1);
uint64_t cargo_trade_generation();
bool cargo_trade_market_available();
bool cargo_trade_reconcile(uint64_t committed_generation,
			   const std::vector<divine_trade_market_cell> &cells);
bool cargo_trade_publish(uint64_t expected_generation,
			 const std::vector<divine_trade_market_cell> &cells);

#endif
