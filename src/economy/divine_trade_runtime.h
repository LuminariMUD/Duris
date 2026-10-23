#ifndef DIVINE_TRADE_RUNTIME_H
#define DIVINE_TRADE_RUNTIME_H
#include "economy/divine_trade_command.h"
#include "persistence/critical_command_completion.h"
struct char_data;
struct ShipData;
// Boot restoration only; gameplay thereafter reads these account books in memory.
bool divine_trade_runtime_boot(uint64_t boon_id);
const divine_trade_book &divine_trade_runtime_book(uint64_t account, uint64_t boon_id);
bool divine_trade_runtime_busy(const ShipData *ship = nullptr);
bool divine_trade_runtime_submit(char_data *ch, ShipData *ship, critical_operation_id operation,
				 divine_trade_payload payload);
// True means this qualifying purchase was handled (queued or refused).
bool divine_trade_runtime_purchase(char_data *ch, ShipData *ship, int slot, int port, int quantity,
				   int cost, divine_trade_goods goods);
bool divine_trade_runtime_sale(char_data *ch, ShipData *ship, int slot, int port,
			       divine_trade_goods goods);
void divine_trade_runtime_completions(const critical_completion *results, size_t count);
#endif
