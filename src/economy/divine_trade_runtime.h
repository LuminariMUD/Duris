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
// Persist deferred inspection intent while still fencing financial work/deletion.
bool divine_trade_runtime_save_busy(const ShipData *ship);

bool divine_trade_runtime_submit(char_data *ch, ShipData *ship, critical_operation_id operation,
				 divine_trade_payload payload);
// True means this qualifying purchase was handled (queued or refused).
bool divine_trade_runtime_purchase(char_data *ch, ShipData *ship, int slot, int port, int quantity,
				   int cost, divine_trade_goods goods);
bool divine_trade_runtime_sale(char_data *ch, ShipData *ship, int slot, int port,
			       divine_trade_goods goods);
// Game thread, before ordinary cargo loss. Updates exact remaining invoice basis
// and prepares book after-images for the same subsequent ship save.
bool divine_trade_runtime_loss(ShipData *ship, int slot, int quantity);
bool divine_trade_runtime_invalidate(ShipData *ship, int slot = -1);
std::vector<divine_trade_book> divine_trade_runtime_ship_books(uint32_t ship_id);
uint64_t divine_trade_runtime_ship_revision(uint32_t ship_id);
void divine_trade_runtime_ship_deleted(uint32_t ship_id);
void divine_trade_runtime_retire_pulse();
void divine_trade_runtime_ship_saved(uint32_t ship_id);
// Only when an ordinary ship deletion was refused before its writer accepted it.
void divine_trade_runtime_restore_books(std::vector<divine_trade_book> before,
					uint32_t dirty_ship = 0);
// Game-thread pulse: verify the original operation/hash on the ordered writer,
// then reinstall its committed prepared projection before releasing reservations.
void divine_trade_runtime_reconcile();
void divine_trade_runtime_completions(const critical_completion *results, size_t count);
#endif
