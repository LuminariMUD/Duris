
#include "core/utils.h"
#include "economy/currency_transaction.h"
#include "persistence/persistence_mode.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot_repository.h"
#include "flatfile/flatfile_player_repository.h"
#include "sql/sql_player.h"

#include <cassert>
#include <cerrno>
#include <cstdlib>
#include <string>
#include <vector>

static room_data rooms[1]{};
P_room world = rooms;
// Everything queued, in order: "save:<pid>" and "bank:<copper delta>", plus
// "completion" when a completion runs.
static std::vector<std::string> order;
static int dirty = 0;

[[noreturn]] int panic_corruption_int(const char *, const char *, ...)
{
	abort();
}
void logit(const char *, const char *, ...) {}
void persistence_alert(int, const char *, const char *, const char *, const char *, const char *,
		       const char *, ...)
{
}
void gmcp_char_vitals(P_char) {}
void mark_player_dirty_components(int, player_component_mask_t)
{
	++dirty;
}
const char *get_account_name_safe(P_char ch)
{
	return ch && GET_PID(ch) == 45 ? "other_account" : "money_account";
}
persistence_mode persistence_mode_get(void)
{
	return PERSISTENCE_MODE_MARIADB_PRIMARY;
}
const char *persistence_mode_flatfile_root(void)
{
	return nullptr;
}
player_save_apply_result flatfile_bank_delta_apply(const std::string &, const std::string &, int8_t,
						   const std::array<int64_t, 4> &,
						   flatfile_authority_operation *, std::string *)
{
	return { player_save_apply_outcome::applied, 0, 0 };
}
player_save_apply_result bank_delta_repository_apply_from_pool(const bank_delta_snapshot &)
{
	return { player_save_apply_outcome::applied, 0, 0 };
}
player_save_submit_result persistence_writer_submit(persistence_job_kind kind, uint64_t, size_t,
						    persistence_job_write_fn)
{
	assert(kind == persistence_job_kind::bank);
	order.push_back("bank");
	return player_save_submit_result::accepted;
}
player_save_pipeline_result player_save_pipeline_request(P_char ch, player_component_mask_t, int,
							 int)
{
	order.push_back("save:" + std::to_string(GET_PID(ch)));
	return player_save_pipeline_result::queued;
}

// The online characters of one account and side share the bank.
static P_char online[2] = {};
void publish_account_bank_balances_revision(const char *account, int racewar,
					    const AccountBankBalances *balances, uint64_t revision)
{
	for (P_char ch : online)
		if (ch && std::string(get_account_name_safe(ch)) == account &&
		    GET_RACEWAR(ch) == racewar)
		{
			GET_BALANCE_COPPER(ch) = balances->copper;
			GET_BALANCE_SILVER(ch) = balances->silver;
			GET_BALANCE_GOLD(ch) = balances->gold;
			GET_BALANCE_PLATINUM(ch) = balances->platinum;
			ch->only.pc->bank_revision = revision;
		}
}

struct player
{
	char_data ch = {};
	pc_only_data pc = {};
	explicit player(int pid)
	{
		ch.only.pc = &pc;
		pc.pid = pid;
		ch.player.racewar = 1;
		ch.in_room = NOWHERE;
	}
};

static bool last_committed = false;
static unsigned int last_error = 0;
static void completion(P_char, bool committed, const currency_command_result &,
		       unsigned int error_code, const uint8_t *, size_t)
{
	last_committed = committed;
	last_error = error_code;
	order.push_back("completion");
}

static std::array<int64_t, 4> wallet(P_char ch)
{
	return { GET_COPPER(ch), GET_SILVER(ch), GET_GOLD(ch), GET_PLATINUM(ch) };
}

#include "economy/divine_trade_runtime.h"
#include "economy/divine_boon_runtime.h"
#include "economy/divine_trade_repository.h"
#include "persistence/critical_command_coordinator.h"
#include "ships/ships.h"
#include "player/player_snapshot_codec.h"
#include <cstdarg>
#include <ctime>
P_char character_list = nullptr;
MYSQL *DB = nullptr;
static divine_boon_state schedule;
static critical_command retained;
static critical_submit_result admission = critical_submit_result::accepted;
static uint64_t market_generation = 0;
static P_ship live_ship = nullptr;
static player_pending_trade_snapshot captured_trade;
static bool capture_reserved = false;
const ShipTypeData ship_type_data[MAXSHIPCLASS] = { { ._mxcargo = 10 } };
const divine_boon_state *divine_boon_runtime_state()
{
	return &schedule;
}
bool divine_boon_runtime_pending()
{
	return false;
}
bool divine_trade_sql_books(MYSQL *, uint64_t, std::vector<divine_trade_book> *)
{
	return true;
}
bool divine_trade_flatfile_books(const std::string &, uint64_t, std::vector<divine_trade_book> *)
{
	return true;
}
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	retained = std::move(command);
	return admission;
}
bool player_save_pipeline_reserve_trade(uint32_t, const player_pending_trade_snapshot &tag)
{
	assert(!capture_reserved);
	captured_trade = tag;
	capture_reserved = true;
	return true;
}
void player_save_pipeline_release_trade(uint32_t)
{
	capture_reserved = false;
}
bool player_save_pipeline_mark(int, player_component_mask_t)
{
	return true;
}
uint64_t cargo_trade_generation()
{
	return market_generation;
}
bool cargo_trade_market_available()
{
	return true;
}
bool cargo_trade_publish(uint64_t expected, const std::vector<divine_trade_market_cell> &)
{
	if (expected != market_generation)
		return false;
	++market_generation;
	return true;
}
divine_trade_market_cell cargo_trade_prepare_cell(int transaction, int port, int type, int, float)
{
	return { static_cast<uint8_t>(port), static_cast<uint8_t>(type),
		 transaction == BOUGHT_CONTRA || transaction == SOLD_CONTRA ?
			 divine_trade_goods::contraband :
			 divine_trade_goods::cargo,
		 1, 120 };
}
P_ship find_ship_by_runtime_ref(ShipRuntimeRef)
{
	return live_ship;
}
float ShipCrew::get_maxcargo_mod() const
{
	return 1;
}
void ShipCrew::sail_skill_raise(float amount)
{
	sail_skill += amount;
}
void ShipCrew::rpar_skill_raise(float amount)
{
	rpar_skill += amount;
}
void update_crew(P_ship) {}
void update_ship_status(P_ship, P_ship) {}
bool has_eq_diplomat(const ShipData *)
{
	return false;
}
bool has_innate(P_char, int)
{
	return false;
}
int cargo_buy_price(int, int, bool)
{
	return 120;
}
int contra_buy_price(int, int)
{
	return 120;
}
double check_nexus_bonus_precise(P_char, double amount, int, bool)
{
	return amount;
}
void send_to_char(const char *, P_char) {}
void send_to_char_f(P_char, const char *, ...) {}
char *coin_stringv(int, int)
{
	static char coins[] = "coins";
	return coins;
}
affected_type *get_spell_from_char(P_char ch, int type, void *, int)
{
	for (auto *af = ch->affected; af; af = af->next)
		if (af->type == type)
			return af;
	return nullptr;
}
affected_type *affect_to_char(P_char ch, affected_type *af)
{
	auto *copy = new affected_type(*af);
	copy->next = ch->affected;
	ch->affected = copy;
	return copy;
}
static divine_trade_payload prepared()
{
	divine_trade_payload p;
	assert(divine_trade_command_decode(retained, &p));
	return p;
}
static void complete(bool committed = true)
{
	const auto p = prepared();
	critical_completion completion{};
	completion.operation_id = retained.operation_id;
	completion.type = critical_command_type::divine_trade;
	completion.outcome = committed ? critical_apply_outcome::applied :
					 critical_apply_outcome::terminal_failure;
	divine_trade_result result{ p.pid,
				    p.ship_id,
				    p.generation + 1,
				    p.wallet_revision + 1,
				    p.book_after.revision,
				    p.payment,
				    p.qualifying_quantity };
	std::array<uint8_t, DIVINE_TRADE_RESULT_BYTES> bytes;
	assert(divine_trade_result_encode(result, &bytes));
	completion.result_size = bytes.size();
	std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
	divine_trade_runtime_completions(&completion, 1);
	divine_trade_runtime_completions(&completion, 1); // duplicate publication is harmless
}
int main()
{
	struct player alice(44);
	character_list = &alice.ch;
	GET_COPPER(&alice.ch) = 1000;
	ShipData ship{};
	live_ship = &ship;
	ship.db_id = 1;
	ship.crew.index = 0;
	ship.slot[0].type = SLOT_CARGO;
	ship.slot[0].index = 2;
	ship.slot[0].val0 = 9;
	ship.slot[0].val1 = 900;
	schedule.mode = divine_boon_mode::divine;
	auto &boon = schedule.slots[0];
	boon.id = 17;
	boon.category = divine_boon_category::cargo;
	boon.starts_at = time(nullptr) - 10;
	boon.expires_at = boon.starts_at + 14400;
	boon.source_port = boon.cargo_commodity = boon.contraband_commodity = 2;
	boon.destination_port = 4;
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(divine_trade_runtime_busy(&ship) && capture_reserved && ship.slot[0].val0 == 9 &&
	       GET_COPPER(&alice.ch) == 1000);
	auto buy = prepared();
	assert(buy.book_after.lots.size() == 1 && buy.book_after.first_full_hold == 10);
	assert(captured_trade.operation == retained.operation_id.bytes &&
	       captured_trade.payment == -100);
	critical_completion retry{};
	retry.operation_id = retained.operation_id;
	retry.type = critical_command_type::divine_trade;
	retry.outcome = critical_apply_outcome::retryable_failure;
	divine_trade_runtime_completions(&retry, 1);
	assert(divine_trade_runtime_busy() && capture_reserved);
	assert(currency_transaction_submit_wallet_value(
		&alice.ch, 20, currency_reason_type::wallet_reward, 0,
		critical_source_site::command, critical_deadline_class::interactive, completion,
		nullptr, 0));
	complete();
	assert(!divine_trade_runtime_busy() && !capture_reserved && ship.slot[0].val0 == 10 &&
	       ship.slot[0].val1 == 1000);
	assert(GET_MONEY(&alice.ch) == 920 && alice.pc.wallet_revision == 2 &&
	       market_generation == 1);
	assert(wallet(&alice.ch) == (std::array<int64_t, 4>{ 0, 2, 9, 0 }));
	assert(divine_trade_runtime_sale(&alice.ch, &ship, -1, 4, divine_trade_goods::cargo));
	auto sale = prepared();
	assert(sale.payment == 1230 && sale.qualifying_quantity == 1 && sale.has_cargo_effect);
	assert(ship.slot[0].val0 == 10 && GET_MONEY(&alice.ch) == 920);
	complete();
	assert(ship.slot[0].type == SLOT_EMPTY && GET_MONEY(&alice.ch) == 2150 &&
	       market_generation == 2);
	assert(get_spell_from_char(&alice.ch, PLAYER_TRADE_CARGO_AFFECT, nullptr, 0)->modifier ==
	       10);
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	complete(false);
	assert(!divine_trade_runtime_busy() && ship.slot[0].type == SLOT_EMPTY &&
	       GET_MONEY(&alice.ch) == 2150);
	admission = critical_submit_result::unavailable;
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(!divine_trade_runtime_busy() && !capture_reserved &&
	       !alice.pc.divine_trade_payment_pending);
	admission = critical_submit_result::accepted;
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	const auto last = prepared();
	struct player restored(44);
	character_list = &restored.ch;
	GET_COPPER(&restored.ch) = last.wallet_after.amount[0];
	GET_SILVER(&restored.ch) = last.wallet_after.amount[1];
	GET_GOLD(&restored.ch) = last.wallet_after.amount[2];
	GET_PLATINUM(&restored.ch) = last.wallet_after.amount[3];
	restored.pc.wallet_revision = last.wallet_revision + 1;
	const auto restored_money = GET_MONEY(&restored.ch);
	complete();
	assert(GET_MONEY(&restored.ch) == restored_money &&
	       restored.pc.wallet_revision == last.wallet_revision + 1);
	// A new opportunity never inherits old cargo proof; contraband uses the
	// same full-hold allowance and receives the same additive 25 percent.
	boon.id = 18;
	ship.slot[1].type = SLOT_EMPTY;
	const auto contra_opening = GET_MONEY(&restored.ch);
	assert(divine_trade_runtime_purchase(&restored.ch, &ship, 1, 2, 1, 100,
					     divine_trade_goods::contraband));
	complete();
	assert(divine_trade_runtime_sale(&restored.ch, &ship, 1, 4,
					 divine_trade_goods::contraband));
	assert(prepared().payment == 150 && !prepared().has_cargo_effect);
	complete();
	assert(GET_MONEY(&restored.ch) == contra_opening + 50);
	while (alice.ch.affected)
	{
		auto *af = alice.ch.affected;
		alice.ch.affected = af->next;
		delete af;
	}
}
