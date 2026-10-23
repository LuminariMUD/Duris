#include <cstdarg>
#include <new>
#include <cmath>
#include "flatfile/flatfile_ship_repository.h"
#include <set>
#include "player/player_save_worker.h"
#include "economy/divine_trade_repository.h"
#include "economy/divine_boon.h"
bool route_open = true;
bool divine_boon_cargo_eligible(const divine_boon_slot &)
{
	return route_open;
}

#include "core/utils.h"
#include "net/comm.h"
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
const WeaponData weapon_data[MAXWEAPON] = {};
const EquipmentData equipment_data[MAXEQUIPMENT] = {};
int eq_ram_weight(const ShipData *)
{
	return 0;
}
int eq_levistone_weight(const ShipData *)
{
	return 0;
}
const PortData ports[NUM_PORTS] = { { 111, "Customs Port", 0 } };
static int inspection_rolls = 0;
int number(int, int)
{
	++inspection_rolls;
	return 0;
}
float get_property(const char *key, double value)
{
	return std::string(key) == "ship.contraband.baseConfiscationChance" ? 100 : value;
}
void debug(const char *, ...) {}
char buf[MAX_STRING_LENGTH];

void act_to_all_in_ship(P_ship, const char *) {}
void act_to_all_in_ship_f(P_ship, const char *, ...) {}
std::string strip_ansi(const char *value)
{
	return value;
}
P_room world = rooms;
// Everything queued, in order: "save:<pid>" and "bank:<copper delta>", plus
// "completion" when a completion runs.
static std::vector<std::string> order;
static int dirty = 0;
static std::string trade_messages;
static double nexus_multiplier = 1;
static float last_sail_raise = 0, last_repair_raise = 0;
static bool seadog = false, diplomat = false, throw_submission = false;
static int audited_trades = 0;
void statuslog(int, const char *format, ...)
{
	char text[2048];
	va_list args;
	va_start(args, format);
	vsnprintf(text, sizeof(text), format, args);
	va_end(args);
	if (strstr(text, "Divine settlement="))
		++audited_trades;
}

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
static persistence_mode fixture_mode = PERSISTENCE_MODE_MARIADB_PRIMARY;
persistence_mode persistence_mode_get(void)
{
	return fixture_mode;
}
const char *persistence_mode_flatfile_root(void)
{
	return "fixture";
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
		ch.player.name = const_cast<char *>("Trader");
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
const ShipTypeData ship_type_data[MAXSHIPCLASS] = { { ._mxcargo = 10 },
						    { ._mxcargo = 10, ._kind = SHK_WARSHIP } };
const divine_boon_state *divine_boon_runtime_state()
{
	return &schedule;
}
bool divine_boon_runtime_pending()
{
	return false;
}

static std::vector<divine_trade_book> boot_books;
static std::set<uint32_t> durable_ship_ids;
static uint32_t reserved_ship_id = 0;
void sql_reserve_ship_ids(uint32_t id)
{
	reserved_ship_id = id;
}
flatfile_ship_result flatfile_ship_list(const std::string &,
					std::vector<flatfile_ship_record> *ships, std::string *)
{
	ships->clear();
	for (uint32_t id : durable_ship_ids)
	{
		flatfile_ship_record s;
		s.ship_id = id;
		ships->push_back(s);
	}
	return flatfile_ship_result::ok;
}
flatfile_ship_result flatfile_ship_reserve_ids(const std::string &, uint32_t id, std::string *)
{
	reserved_ship_id = id;
	return flatfile_ship_result::ok;
}
bool divine_trade_sql_books(MYSQL *, uint64_t, std::vector<divine_trade_book> *)
{
	return true;
}
bool divine_trade_flatfile_books(const std::string &, uint64_t,
				 std::vector<divine_trade_book> *books)
{
	*books = boot_books;
	return true;
}
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	if (throw_submission)
		throw std::bad_alloc();

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
static bool physical_ship_exists = true;
static P_ship physical_ship = nullptr;
P_ship find_ship_by_database_id(uint32_t id)
{
	return physical_ship_exists && physical_ship &&
			       id == static_cast<uint32_t>(physical_ship->db_id) ?
		       physical_ship :
		       nullptr;
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
	last_sail_raise = amount;
}
void ShipCrew::rpar_skill_raise(float amount)
{
	rpar_skill += amount;
	last_repair_raise = amount;
}
void update_crew(P_ship) {}
void update_ship_status(P_ship, P_ship) {}
bool has_eq_diplomat(const ShipData *)
{
	return diplomat;
}
bool has_innate(P_char, int)
{
	return seadog;
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
	return amount * nexus_multiplier;
}
void send_to_char(const char *text, P_char)
{
	trade_messages += text;
}
void send_to_char_f(P_char, const char *format, ...)
{
	char text[2048];
	va_list args;
	va_start(args, format);
	vsnprintf(text, sizeof(text), format, args);
	va_end(args);
	trade_messages += text;
}
const char *cargo_type_name(int)
{
	return "test cargo";
}
const char *contra_type_name(int)
{
	return "test contraband";
}
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
const char *cargo_type_name(int)
{
	return "cargo";
}
const char *contra_type_name(int)
{
	return "contraband";
}
int jettison_crates(P_ship, int, int, int)
{
	return TRUE;
}
void queue_ship_save(P_ship ship, const char *)
{
	ship->save_pending = true;
}
int write_ship(P_ship ship)
{
	ship->save_pending = false;
	divine_trade_runtime_ship_saved(static_cast<uint32_t>(ship->db_id));
	return TRUE;
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
bool ac_can_see(P_char, P_char, bool)
{
	return true;
}
int IS_MORPH(P_char)
{
	return false;
}
void ADD_MONEY(P_char, int)
{
	abort();
}
int SUB_MONEY(P_char, int, int)
{
	abort();
}
void act(const char *, int, P_char, P_obj, void *, int) {}
void half_chop(char *argument, char *first, char *second)
{
	sscanf(argument, "%s %s", first, second);
}
int coin_type(char *name)
{
	return !strcmp(name, "copper") ? 0 : -1;
}
extern const char *coin_names[];
const char *coin_names[] = { "copper", "silver", "gold", "platinum" };

// SPLIT_FUNCTIONS

static void split_reservation_case()
{
	currency_transaction_reset_for_tests();
	struct player donor(44), recipient(45);
	group_list members[2] = { { &donor.ch, &members[1] }, { &recipient.ch, nullptr } };
	donor.ch.group = members;
	donor.ch.in_room = recipient.ch.in_room = 1;
	GET_COPPER(&donor.ch) = 150;
	GET_COPPER(&recipient.ch) = 10;
	assert(currency_transaction_reserve_trade(&donor.ch, -100));
	char command[] = "150 copper";
	do_split(&donor.ch, command, 0);
	assert(GET_MONEY(&donor.ch) == 150 && GET_MONEY(&recipient.ch) == 10);
	currency_transaction_release_trade(44);
	do_split(&donor.ch, command, 0);
	assert(GET_MONEY(&donor.ch) == 75 && GET_MONEY(&recipient.ch) == 85);
	// A recipient's reserved sale can refuse an otherwise valid credit.
	GET_COPPER(&donor.ch) = 150;
	GET_SILVER(&donor.ch) = GET_GOLD(&donor.ch) = GET_PLATINUM(&donor.ch) = 0;
	GET_COPPER(&recipient.ch) = GET_SILVER(&recipient.ch) = GET_GOLD(&recipient.ch) =
		GET_PLATINUM(&recipient.ch) = INT_MAX;
	assert(currency_transaction_reserve_trade(&recipient.ch, 0));
	do_split(&donor.ch, command, 0);
	assert(GET_MONEY(&donor.ch) == 150);
	currency_transaction_release_trade(45);
}

int main()
{
	split_reservation_case();
	struct player alice(44);
	character_list = &alice.ch;
	GET_COPPER(&alice.ch) = 1000;
	ShipData ship{};
	physical_ship = &ship;
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
	// A load-normalized crew must reach the writer before a prepared trade.
	ship.save_pending = true;
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(!divine_trade_runtime_busy() && !capture_reserved && ship.slot[0].val0 == 9 &&
	       GET_COPPER(&alice.ch) == 1000);
	ship.save_saved_signature = 1;
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(divine_trade_runtime_busy(&ship) && capture_reserved && ship.slot[0].val0 == 9 &&
	       GET_COPPER(&alice.ch) == 1000);
	assert(trade_messages.find("You buy") == std::string::npos);

	const int initial_rolls = inspection_rolls;
	check_contraband(&ship, 0);
	assert(IS_SET(ship.flags, CUSTOMS_PENDING) && inspection_rolls == initial_rolls);
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
	assert(trade_messages.find("You buy 1 crates of test cargo") != std::string::npos);

	REMOVE_BIT(ship.flags, CUSTOMS_PENDING);
	rooms[0].number = 111;
	ship.slot[1].type = SLOT_CONTRABAND;
	ship.slot[1].index = 2;
	ship.slot[1].val0 = 1;
	ship.slot[1].val1 = 1;
	check_contraband(&ship, 0);
	assert(ship.slot[1].type == SLOT_EMPTY && inspection_rolls > initial_rolls);
	affected_type progress{};
	progress.type = PLAYER_TRADE_CARGO_AFFECT;
	progress.modifier = 9995;
	affect_to_char(&alice.ch, &progress);
	trade_messages.clear();
	nexus_multiplier = 1.1;
	assert(divine_trade_runtime_sale(&alice.ch, &ship, -1, 4, divine_trade_goods::cargo));
	assert(trade_messages.find("Trader") == std::string::npos &&
	       trade_messages.find("Enlil") == std::string::npos);
	assert(std::abs(last_sail_raise - .00198f) < 1e-9 &&
	       std::abs(last_repair_raise - .00066f) < 1e-9);
	auto sale = prepared();
	assert(sale.payment == 1350 && sale.qualifying_quantity == 1 && sale.has_cargo_effect);
	assert(ship.slot[0].val0 == 10 && GET_MONEY(&alice.ch) == 920);
	complete();
	assert(ship.slot[0].type == SLOT_EMPTY && GET_MONEY(&alice.ch) == 2270 &&
	       market_generation == 2);
	assert(get_spell_from_char(&alice.ch, PLAYER_TRADE_CARGO_AFFECT, nullptr, 0)->modifier ==
	       10005);
	assert(trade_messages.find("Trader") != std::string::npos &&
	       trade_messages.find("Enlil") != std::string::npos);
	assert(trade_messages.find("You sell 10 crates of test cargo") != std::string::npos &&
	       trade_messages.find("35% profit") != std::string::npos);
	const auto paid_messages = trade_messages;
	complete();
	assert(trade_messages == paid_messages);
	nexus_multiplier = 1;
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	complete(false);
	assert(!divine_trade_runtime_busy() && ship.slot[0].type == SLOT_EMPTY &&
	       GET_MONEY(&alice.ch) == 2270);
	admission = critical_submit_result::unavailable;
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(!divine_trade_runtime_busy() && !capture_reserved &&
	       !alice.pc.divine_trade_payment_pending);
	admission = critical_submit_result::accepted;
	throw_submission = true;
	const auto audits_before_throw = audited_trades;
	assert(divine_trade_runtime_purchase(&alice.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(!divine_trade_runtime_busy() && !capture_reserved &&
	       !alice.pc.divine_trade_payment_pending && audited_trades == audits_before_throw);
	throw_submission = false;
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
	// All price modifiers remain quiet until the same committed sale.
	struct player modifiers(45);
	character_list = &modifiers.ch;
	GET_COPPER(&modifiers.ch) = 1000;
	boon.id = 98;
	const int prior_class = ship.m_class;
	ship.m_class = 1;
	seadog = diplomat = true;
	ship.slot[0].type = SLOT_EMPTY;
	ship.slot[0].index = -1;
	ship.slot[0].val0 = ship.slot[0].val1 = 0;
	const auto audits_before_modifiers = audited_trades;
	assert(divine_trade_runtime_purchase(&modifiers.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(audited_trades == audits_before_modifiers);
	complete();
	trade_messages.clear();
	assert(divine_trade_runtime_sale(&modifiers.ch, &ship, 0, 4, divine_trade_goods::cargo));
	assert(prepared().payment == 87);
	assert(trade_messages.find("heritage") == std::string::npos &&
	       trade_messages.find("diplomat") == std::string::npos &&
	       trade_messages.find("stolen") == std::string::npos);
	complete();
	assert(audited_trades == audits_before_modifiers + 2 &&
	       trade_messages.find("heritage") != std::string::npos &&
	       trade_messages.find("diplomat") != std::string::npos &&
	       trade_messages.find("stolen") != std::string::npos);
	while (modifiers.ch.affected)
	{
		auto *af = modifiers.ch.affected;
		modifiers.ch.affected = af->next;
		delete af;
	}
	ship.m_class = prior_class;
	seadog = diplomat = false;
	character_list = &restored.ch;
	boon.id = 18;
	// Old stock is lost first, then exact paid basis; a different ship cannot
	// publish this shared account book before the changed inventory is saved.
	boon.id = 19;
	ship.slot[0].type = SLOT_CARGO;
	ship.slot[0].index = 2;
	ship.slot[0].val0 = 2;
	ship.slot[0].val1 = 200;
	assert(divine_trade_runtime_purchase(&restored.ch, &ship, 0, 2, 3, 300,
					     divine_trade_goods::cargo));
	complete();
	auto before_loss = divine_trade_runtime_ship_books(1);
	assert(before_loss.size() == 1 && before_loss[0].lots[0].remaining_quantity == 3);
	assert(jettison_cargo(&restored.ch, &ship, 2));
	assert(ship.slot[0].val1 == 300 &&
	       divine_trade_runtime_ship_books(1)[0].lots[0].remaining_quantity == 3);
	const auto intact_revision = divine_trade_runtime_ship_revision(1);
	assert(jettison_cargo(&restored.ch, &ship, 1));
	auto lost = divine_trade_runtime_ship_books(1);
	assert(lost[0].lots[0].remaining_quantity == 2 && lost[0].lots[0].remaining_basis == 200 &&
	       !lost[0].consumed);
	assert(ship.slot[0].val1 == 200 &&
	       divine_trade_runtime_ship_revision(1) != intact_revision);
	ShipData other{};
	other.db_id = 2;
	other.crew.index = 0;
	other.slot[0].type = SLOT_EMPTY;
	assert(divine_trade_runtime_purchase(&restored.ch, &other, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(!divine_trade_runtime_busy() && other.slot[0].type == SLOT_EMPTY);
	// The current ship's save precedes its next financial command.
	ship.save_pending = true;
	assert(divine_trade_runtime_purchase(&restored.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(divine_trade_runtime_busy() && !ship.save_pending);
	complete();
	auto retained_proof = divine_trade_runtime_ship_books(1);
	assert(divine_trade_runtime_invalidate(&ship));
	assert(divine_trade_runtime_ship_books(1)[0].lots.empty());
	divine_trade_runtime_restore_books(retained_proof);
	assert(divine_trade_runtime_ship_books(1)[0] == retained_proof[0]);
	clear_cargo(&ship);
	assert(ship.slot[0].type == SLOT_EMPTY);
	divine_trade_runtime_ship_saved(1);
	auto retired = divine_trade_runtime_ship_books(1);
	assert(retired[0].lots.empty() && retired[0].first_full_hold == 10 && !retired[0].consumed);

	ShipData salvage{};
	salvage.db_id = 2;
	assert(add_crate(&salvage, 2, 1));
	assert(salvage.slot[0].val1 == 0 &&
	       !divine_trade_runtime_sale(&restored.ch, &salvage, 0, 4, divine_trade_goods::cargo));
	boon.id = 20;
	ship.slot[2].type = SLOT_CONTRABAND;
	ship.slot[2].index = 2;
	ship.slot[2].val0 = 1;
	ship.slot[2].val1 = 0;
	assert(divine_trade_runtime_purchase(&restored.ch, &ship, 2, 2, 2, 101,
					     divine_trade_goods::contraband));
	complete();
	assert(jettison_contraband(&restored.ch, &ship, INT_MAX));
	assert(ship.slot[2].type == SLOT_EMPTY &&
	       divine_trade_runtime_ship_books(1)[0].lots.empty() &&
	       !divine_trade_runtime_ship_books(1)[0].consumed);
	// A later unverifiable slot must not discard the earlier completed removal's
	// save request when an all-slot jettison stops part way through the hold.
	divine_trade_runtime_ship_saved(1);
	ship.save_pending = false;
	ship.slot[3].type = SLOT_CARGO;
	ship.slot[3].index = 2;
	ship.slot[3].val0 = 1;
	ship.slot[3].val1 = 0;
	ship.slot[4].type = SLOT_CARGO;
	ship.slot[4].index = 2;
	ship.slot[4].val0 = 1;
	ship.slot[4].val1 = -1;
	assert(jettison_cargo(&restored.ch, &ship, INT_MAX));
	assert(ship.slot[3].type == SLOT_EMPTY && ship.slot[4].type == SLOT_EMPTY &&
	       ship.save_pending);

	SET_BIT(ship.flags, TO_DELETE);
	assert(divine_trade_runtime_busy(&ship));
	REMOVE_BIT(ship.flags, TO_DELETE);

	// A refused first purchase on a different ship publishes no associations.
	ShipData rejected = ship;
	rejected.db_id = 100;
	admission = critical_submit_result::unavailable;
	assert(divine_trade_runtime_purchase(&restored.ch, &rejected, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(divine_trade_runtime_ship_books(100).empty() &&
	       !divine_trade_runtime_busy(&rejected));
	admission = critical_submit_result::accepted;

	// Ownership transfer cannot merge a new account's paid lot into an old
	// account's proof. The old proof is saved away before any new charge.
	fixture_mode = PERSISTENCE_MODE_FLATFILE_PRIMARY;
	boon.id = 17;
	auto transferred = buy.book_after;
	transferred.account += 1;
	transferred.consumed = 5;
	transferred.lots[0].purchased_quantity = transferred.lots[0].remaining_quantity = 2;
	transferred.lots[0].invoice_basis = transferred.lots[0].remaining_basis = 200;
	boot_books = { transferred };
	durable_ship_ids = { 1 };
	assert(divine_trade_runtime_boot(17));
	ship.slot[0].type = SLOT_CARGO;
	ship.slot[0].index = 2;
	ship.slot[0].val0 = 2;
	ship.slot[0].val1 = 200;
	const auto old_money = GET_MONEY(&restored.ch);
	assert(divine_trade_runtime_purchase(&restored.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(!divine_trade_runtime_busy() && ship.save_pending &&
	       GET_MONEY(&restored.ch) == old_money);
	assert(divine_trade_runtime_book(transferred.account, 17).lots.empty());
	write_ship(&ship);
	assert(divine_trade_runtime_purchase(&restored.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	complete();
	assert(divine_trade_runtime_book(transferred.account, 17).consumed == 5 &&
	       divine_trade_runtime_book(buy.book_after.account, 17).lots.size() == 1);

	fixture_mode = PERSISTENCE_MODE_FLATFILE_PRIMARY;
	boon.id = 17;
	auto mixed_a = buy.book_after;
	auto mixed_b = mixed_a;
	mixed_a.revision = 20;
	mixed_a.consumed = 4;
	mixed_a.lots[0].purchased_quantity = mixed_a.lots[0].remaining_quantity = 3;
	mixed_a.lots[0].invoice_basis = mixed_a.lots[0].remaining_basis = 300;
	mixed_b.account = mixed_a.account + 1;
	mixed_b.revision = 30;
	mixed_b.consumed = 5;
	mixed_b.lots[0].purchase.bytes[0] ^= 0x55;
	mixed_b.lots[0].purchased_quantity = mixed_b.lots[0].remaining_quantity = 2;
	mixed_b.lots[0].invoice_basis = mixed_b.lots[0].remaining_basis = 200;
	boot_books = { mixed_a, mixed_b };
	durable_ship_ids = { 1 };
	assert(divine_trade_runtime_boot(17));
	ship.slot[0].type = SLOT_CARGO;
	ship.slot[0].index = 2;
	ship.slot[0].val0 = 5;
	ship.slot[0].val1 = 500;
	const auto mixed_money = GET_MONEY(&restored.ch);
	assert(divine_trade_runtime_sale(&restored.ch, &ship, 0, 4, divine_trade_goods::cargo));
	assert(!divine_trade_runtime_busy() && GET_MONEY(&restored.ch) == mixed_money &&
	       ship.slot[0].val0 == 5);
	assert(divine_trade_runtime_book(mixed_a.account, 17).lots.empty() &&
	       divine_trade_runtime_book(mixed_b.account, 17).lots.empty());
	assert(divine_trade_runtime_boot(17));
	assert(divine_trade_runtime_loss(&ship, 0, 4));
	ship.slot[0].val0 -= 4;
	assert(ship.slot[0].val0 == 1 && ship.slot[0].val1 == 100);
	assert(divine_trade_runtime_book(mixed_a.account, 17).lots.empty() &&
	       divine_trade_runtime_book(mixed_a.account, 17).consumed == 4);
	assert(divine_trade_runtime_book(mixed_b.account, 17).lots.empty() &&
	       divine_trade_runtime_book(mixed_b.account, 17).consumed == 5);
	divine_trade_runtime_ship_saved(1);

	auto orphan = buy.book_after;
	orphan.revision = 40;
	orphan.consumed = 4;
	auto absent = orphan.lots[0];
	absent.ship_id = 999;
	absent.purchase.bytes[0] ^= 0x22;
	auto unplaced = orphan.lots[0];
	unplaced.ship_id = 700;
	unplaced.purchase.bytes[0] ^= 0x33;
	orphan.lots.push_back(absent);
	orphan.lots.push_back(unplaced);
	boot_books = { orphan };
	durable_ship_ids = { 1, 700 };
	assert(divine_trade_runtime_boot(17) && reserved_ship_id == 999);
	auto recovered = divine_trade_runtime_book(orphan.account, 17);
	assert(recovered.lots.size() == 2 && recovered.revision == 41 &&
	       recovered.first_full_hold == 10 && recovered.consumed == 4);
	for (const auto &lot : recovered.lots)
		assert(lot.ship_id != 999);
	assert(ship.save_pending);
	divine_trade_runtime_ship_saved(1);
	// A committed runtime-only deletion retires proof, without leaving a dead
	// dirty owner. Unplaced but durable ships keep their legitimate paid lots.
	physical_ship_exists = false;
	divine_trade_runtime_ship_deleted(1);
	divine_trade_runtime_retire_pulse();
	recovered = divine_trade_runtime_book(orphan.account, 17);
	assert(recovered.lots.size() == 1 && recovered.lots[0].ship_id == 700 &&
	       recovered.consumed == 4);
	physical_ship_exists = true;
	ship.db_id = 2;
	ship.slot[0].clear();
	ship.save_pending = false;
	assert(divine_trade_runtime_purchase(&restored.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	assert(!divine_trade_runtime_busy() && ship.save_pending); // Records cleanup before buying.
	write_ship(&ship);
	assert(divine_trade_runtime_purchase(&restored.ch, &ship, 0, 2, 1, 100,
					     divine_trade_goods::cargo));
	complete();
	assert(divine_trade_runtime_book(orphan.account, 17).first_full_hold == 10 &&
	       divine_trade_runtime_book(orphan.account, 17).consumed == 4);

	while (alice.ch.affected)
	{
		auto *af = alice.ch.affected;
		alice.ch.affected = af->next;
		delete af;
	}
}
