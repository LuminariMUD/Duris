#include "economy/divine_trade_runtime.h"
#include "economy/divine_trade_repository.h"
#include "economy/currency_transaction.h"
#include "economy/currency_value.h"
#include "economy/divine_boon_runtime.h"
#include "economy/nexus_stones.h"
#include "core/files.h"
#include <cmath>
#include "core/utils.h"
#include "core/prototypes.h"
#include "core/utility.h"
#include "ships/ships.h"
#include "ships/ship_cargo_transaction.h"
#include "player/player_save_pipeline.h"
#include "persistence/critical_command_coordinator.h"
#include "persistence/persistence_mode.h"
#ifndef __NO_MYSQL__
#include "sql/sql.h"
#include "sql/sql_player.h"
#include "persistence/critical_command_repository.h"
#endif
#include "flatfile/flatfile_ship_repository.h"
#include <cstdlib>
#include <atomic>
#include <cerrno>
#include <chrono>
#include "player/player_save_worker.h"
#include <map>
#include <set>
#include <memory>
#include <openssl/sha.h>
extern P_char character_list;
namespace
{
flatfile_ship_crew_record capture_crew(const ShipCrew &crew)
{
	return { crew.index,
		 static_cast<int32_t>(std::lround(crew.sail_skill * 1000)),
		 static_cast<int32_t>(std::lround(crew.guns_skill * 1000)),
		 static_cast<int32_t>(std::lround(crew.rpar_skill * 1000)),
		 crew.sail_chief,
		 crew.guns_chief,
		 crew.rpar_chief };
}

flatfile_ship_slot_record capture_slot(uint8_t index, const ShipSlot &slot)
{
	return { index,	     slot.type,
		 slot.index, slot.position,
		 slot.timer, { slot.val0, slot.val1, slot.val2, slot.val3, slot.val4 } };
}

uint64_t restored_boon = 0;
std::map<uint64_t, divine_trade_book> books;
using ship_account_index = std::map<uint32_t, std::set<uint64_t>>;
using book_dirty_index = std::map<uint64_t, uint32_t>;
ship_account_index ship_accounts;
book_dirty_index dirty_owner;
std::set<uint32_t> retired_ships;
const divine_trade_book empty_book;
struct trade_operation
{
	critical_operation_id id;
	ShipRuntimeRef ship;
	divine_trade_payload after;
	int nexus_bonus = 0;
	bool trader_completed = false;
	bool warship = false, seadog = false, diplomat = false;
	std::string audit;
	std::string receipt;
};
std::unique_ptr<trade_operation> pending;
void index_book(const divine_trade_book &book, ship_account_index &ships, book_dirty_index &dirty)
{
	dirty.try_emplace(book.account, 0);
	for (const auto &lot : book.lots)
		ships[lot.ship_id].insert(book.account);
}

P_char player(uint32_t pid)
{
	for (P_char ch = character_list; ch; ch = ch->next)
		if (!IS_NPC(ch) && static_cast<uint32_t>(GET_PID(ch)) == pid)
			return ch;
	return nullptr;
}
}
bool divine_trade_runtime_boot(uint64_t boon_id)
try
{
	if (pending)
		return false;
	std::vector<divine_trade_book> loaded;
	if (boon_id)
	{
		if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
		{
			const char *root = persistence_mode_flatfile_root();
			if (!root || !divine_trade_flatfile_books(root, boon_id, &loaded))
				return false;
		}
		else
		{
#ifdef __NO_MYSQL__
			return false;
#else
			if (!divine_trade_sql_books(DB, boon_id, &loaded))
				return false;
#endif
		}
	}

	retired_ships.clear();
	if (!loaded.empty())
	{
		std::set<uint32_t> durable_ids;
		if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
		{
			std::vector<flatfile_ship_record> ships;
			std::string error;
			if (flatfile_ship_list(persistence_mode_flatfile_root(), &ships, &error) !=
			    flatfile_ship_result::ok)
				return false;
			for (const auto &ship : ships)
				durable_ids.insert(ship.ship_id);
			uint32_t reserved = 0;
			for (const auto &book : loaded)
			{
				reserved = std::max(reserved, book.first_ship_id);
				for (const auto &lot : book.lots)
					reserved = std::max(reserved, lot.ship_id);
			}
			const auto held = flatfile_ship_reserve_ids(
				persistence_mode_flatfile_root(), reserved, &error);
			if (held != flatfile_ship_result::ok &&
			    held != flatfile_ship_result::unchanged)
				return false;
		}
		else
		{
#ifdef __NO_MYSQL__
			return false;
#else
			if (mysql_query(DB, "SELECT id FROM ships"))
				return false;
			MYSQL_RES *rows = mysql_store_result(DB);
			if (!rows)
				return false;
			while (MYSQL_ROW row = mysql_fetch_row(rows))
				if (row[0])
					durable_ids.insert(std::strtoul(row[0], nullptr, 10));
			mysql_free_result(rows);
			uint32_t reserved = 0;
			for (const auto &book : loaded)
			{
				reserved = std::max(reserved, book.first_ship_id);
				for (const auto &lot : book.lots)
					reserved = std::max(reserved, lot.ship_id);
			}
			sql_reserve_ship_ids(reserved);
#endif
		}
		for (const auto &book : loaded)
			for (const auto &lot : book.lots)
				if (!durable_ids.count(lot.ship_id))
					retired_ships.insert(lot.ship_id);
	}
	std::map<uint64_t, divine_trade_book> restored;
	for (auto &book : loaded)
		if (!restored.emplace(book.account, std::move(book)).second)
			return false;
	ship_accounts.clear();
	dirty_owner.clear();
	for (const auto &[account, book] : restored)
	{
		static_cast<void>(account);
		index_book(book, ship_accounts, dirty_owner);
	}
	books = std::move(restored);
	restored_boon = boon_id;
	divine_trade_runtime_retire_pulse();
	return true;
}
catch (const std::bad_alloc &)
{
	return false;
}
void divine_trade_runtime_ship_deleted(uint32_t ship_id)
{
	if (ship_id)
		retired_ships.insert(ship_id);
}
void divine_trade_runtime_retire_pulse()
{
	if (pending || retired_ships.empty())
		return;
	for (auto &[account, book] : books)
	{
		if (!book.revision)
			continue;
		const size_t old = book.lots.size();
		if (book.revision == UINT64_MAX)
			continue;
		std::erase_if(book.lots,
			      [&](const auto &lot) { return retired_ships.count(lot.ship_id); });
		const auto dirty = dirty_owner.find(account);
		if (old == book.lots.size() &&
		    (dirty == dirty_owner.end() || !retired_ships.count(dirty->second)))
			continue;
		if (old != book.lots.size())
			++book.revision;
		uint32_t owner = UINT32_MAX;
		for (const auto &lot : book.lots)
			if (P_ship ship = find_ship_by_database_id(lot.ship_id))
			{
				owner = lot.ship_id;
				queue_ship_save(ship, "deleted ship cargo proof");
				break;
			}
		dirty_owner[account] = owner;
	}
	for (uint32_t id : retired_ships)
		ship_accounts.erase(id);
	retired_ships.clear();
}

const divine_trade_book &divine_trade_runtime_book(uint64_t account, uint64_t boon_id)
{
	if (restored_boon != boon_id)
	{
		// New hourly boon IDs never inherit another opportunity's paid inventory.
		if (pending)
			return empty_book;
		books.clear();
		ship_accounts.clear();
		dirty_owner.clear();
		restored_boon = boon_id;
	}
	const auto found = books.find(account);
	return found == books.end() ? empty_book : found->second;
}
bool divine_trade_runtime_busy(const ShipData *ship)
{
	if (!ship)
		return pending != nullptr;
	if (!IS_NPC_SHIP(ship) && IS_SET(ship->flags, TO_DELETE | CUSTOMS_PENDING))
		return true;
	const auto id = static_cast<uint32_t>(ship->db_id);
	const auto participants = ship_accounts.find(id);
	if (participants != ship_accounts.end())
		for (uint64_t account : participants->second)
		{
			const auto dirty = dirty_owner.find(account);
			if (dirty != dirty_owner.end() && dirty->second && dirty->second != id)
				return true;
			if (pending && pending->after.book_after.account == account)
				return true;
		}
	return pending && pending->after.ship_id == id;
}

bool divine_trade_runtime_submit(P_char ch, P_ship ship, critical_operation_id operation,
				 divine_trade_payload payload)
try
{
	if (!ch || IS_NPC(ch) || !ship || pending ||
	    (ship->save_pending && !ship->save_saved_signature) ||
	    !cargo_trade_market_available() || payload.pid != static_cast<uint32_t>(GET_PID(ch)) ||
	    payload.ship_id != static_cast<uint32_t>(ship->db_id) ||
	    payload.wallet_revision != ch->only.pc->wallet_revision ||
	    payload.generation != cargo_trade_generation())
		return false;
	const auto dirty = dirty_owner.find(payload.book_after.account);
	if (dirty != dirty_owner.end() && dirty->second &&
	    dirty->second != static_cast<uint32_t>(ship->db_id))
		return false;
	if (divine_trade_runtime_busy(ship) ||
	    ((ship->save_pending || (dirty != dirty_owner.end() && dirty->second)) &&
	     !write_ship(ship)))
		return false;

	if (auto linked = ship_accounts.find(static_cast<uint32_t>(ship->db_id));
	    linked != ship_accounts.end())
		for (uint64_t account : linked->second)
			if (auto dirty = dirty_owner.find(account);
			    dirty != dirty_owner.end() && dirty->second)
				return false;
	currency_vector before, expected;
	before.amount = { GET_COPPER(ch), GET_SILVER(ch), GET_GOLD(ch), GET_PLATINUM(ch) };
	if (!currency_wallet_after_value(before, payload.payment, &expected) ||
	    expected.amount != payload.wallet_after.amount)
		return false;
	critical_command command;
	if (!divine_trade_command_build(&command, operation, payload))
		return false;
	player_pending_trade_snapshot tag;
	tag.operation = operation.bytes;
	tag.payment = payload.payment;
	tag.wallet_revision = payload.wallet_revision;
	tag.has_cargo_effect = payload.has_cargo_effect;
	tag.cargo_effect = payload.cargo_effect;
	std::vector<uint8_t> encoded;
	if (critical_command_encode(command, &encoded) != critical_command_codec_result::ok)
		return false;
	SHA256(encoded.data(), encoded.size(), tag.command_hash.data());
	auto next = std::make_unique<trade_operation>();
	next->id = operation;
	next->ship = ship->runtime_ref;
	next->after = std::move(payload);
	const auto &prepared = next->after;
	const auto &market = prepared.market_after.front();
	const bool cargo = market.goods == divine_trade_goods::cargo;
	next->warship = prepared.action == divine_trade_action::sale && IS_WARSHIP(ship);
	next->seadog = prepared.action == divine_trade_action::sale && cargo &&
		       has_innate(ch, INNATE_SEADOG);
	next->diplomat = prepared.action == divine_trade_action::sale && cargo &&
			 has_eq_diplomat(ship);
	char operation_hex[CRITICAL_COMMAND_ID_HEX_SIZE];
	critical_operation_id_to_hex(operation, operation_hex, sizeof(operation_hex));
	char record[320];
	snprintf(record, sizeof(record),
		 "%s: %s %s pid=%u ship=%u port=%u payment=%lld qualified=%u Divine settlement=%s",
		 cargo ? "CARGO" : "CONTRABAND", GET_NAME(ch),
		 prepared.action == divine_trade_action::purchase ? "bought" : "sold", prepared.pid,
		 prepared.ship_id, static_cast<unsigned>(market.port),
		 static_cast<long long>(prepared.payment), prepared.qualifying_quantity,
		 operation_hex);
	next->audit = record;
	for (const auto &after : prepared.slots_after)
	{
		const auto &before = ship->slot[after.slot_index];
		const bool buying = prepared.action == divine_trade_action::purchase;
		const int64_t quantity =
			buying ? static_cast<int64_t>(after.values[0]) -
					 (before.type == SLOT_CARGO ||
							  before.type == SLOT_CONTRABAND ?
						  before.val0 :
						  0) :
				 before.val0;
		snprintf(record, sizeof(record), " slot=%u commodity=%d crates=%lld basis=%lld",
			 static_cast<unsigned>(after.slot_index),
			 buying ? after.item_index : before.index, static_cast<long long>(quantity),
			 static_cast<long long>(buying ? -prepared.payment : before.val1));
		next->audit += record;
		if (buying)
		{
			snprintf(record, sizeof(record), "You buy %lld crates of %s for %s.\r\n",
				 static_cast<long long>(quantity),
				 cargo ? cargo_type_name(after.item_index) :
					 contra_type_name(after.item_index),
				 coin_stringv(static_cast<int>(-prepared.payment)));
			next->receipt += record;
		}
	}
	// Allocate the publication destination before handing the immutable command off.
	books.try_emplace(next->after.book_after.account);
	auto indexed_ships = ship_accounts;
	auto indexed_dirty = dirty_owner;
	index_book(next->after.book_after, indexed_ships, indexed_dirty);
	if (!currency_transaction_reserve_trade(ch, next->after.payment))
		return false;
	if (!player_save_pipeline_reserve_trade(static_cast<uint32_t>(GET_PID(ch)), tag))
	{
		currency_transaction_release_trade(GET_PID(ch));
		return false;
	}
	pending = std::move(next);
	const auto submitted = critical_command_coordinator_submit(std::move(command));
	if (!critical_submit_result_keeps_operation(submitted))
	{
		player_save_pipeline_release_trade(GET_PID(ch));
		currency_transaction_release_trade(GET_PID(ch));
		pending.reset();
		return false;
	}
	ship_accounts.swap(indexed_ships);
	dirty_owner.swap(indexed_dirty);
	ch->only.pc->divine_trade_payment_pending = true;
	send_to_char("The merchants are settling your cargo trade.\r\n", ch);
	return true;
}
catch (const std::bad_alloc &)
{
	// Coordinator identity allocation can throw before it admits this operation.
	if (pending && pending->id.bytes == operation.bytes)
	{
		player_save_pipeline_release_trade(pending->after.pid);
		currency_transaction_release_trade(pending->after.pid);
		pending.reset();
	}
	return false;
}
void divine_trade_runtime_completions(const critical_completion *results, size_t count)
{
	for (size_t i = 0; i < count; ++i)
	{
		const auto &completion = results[i];
		if (!pending || completion.type != critical_command_type::divine_trade ||
		    completion.operation_id.bytes != pending->id.bytes)
			continue;
		if (completion.outcome == critical_apply_outcome::retryable_failure ||
		    completion.outcome == critical_apply_outcome::ambiguous_commit)
			continue;
		auto &p = pending->after;
		const bool committed = completion.outcome == critical_apply_outcome::applied ||
				       completion.outcome ==
					       critical_apply_outcome::already_applied;
		divine_trade_result result;
		if (committed &&
		    (!divine_trade_result_decode(completion.result_payload.data(),
						 completion.result_size, &result) ||
		     result.pid != p.pid || result.ship_id != p.ship_id ||
		     result.generation != p.generation + 1 ||
		     result.wallet_revision != p.wallet_revision + 1 ||
		     result.book_revision != p.book_after.revision || result.payment != p.payment ||
		     result.qualifying_quantity != p.qualifying_quantity))
		{
			logit(LOG_SHIP, "Divine trade result mismatch pid=%u ship=%u", p.pid,
			      p.ship_id);
			continue;
		}
		P_char ch = player(p.pid);
		if (committed && cargo_trade_generation() != p.generation)
		{
			logit(LOG_SHIP, "Divine market generation mismatch ship=%u", p.ship_id);
			continue;
		}
		player_save_pipeline_release_trade(p.pid);
		currency_transaction_release_trade(p.pid);
		if (committed)
		{
			if (!cargo_trade_publish(p.generation, p.market_after))
			{
				logit(LOG_SHIP, "Divine market publication mismatch ship=%u",
				      p.ship_id);
				continue;
			}
			books[p.book_after.account] = std::move(p.book_after);
			if (P_ship ship = find_ship_by_runtime_ref(pending->ship);
			    ship && static_cast<uint32_t>(ship->db_id) == p.ship_id)
			{
				for (const auto &slot : p.slots_after)
				{
					auto &live = ship->slot[slot.slot_index];
					live.type = slot.slot_type;
					live.index = slot.item_index;
					live.position = slot.position;
					live.timer = slot.timer;
					live.val0 = slot.values[0];
					live.val1 = slot.values[1];
					live.val2 = slot.values[2];
					live.val3 = slot.values[3];
					live.val4 = slot.values[4];
				}
				ship->crew.sail_skill = p.crew_after.sail_skill_milli / 1000.0f;
				ship->crew.guns_skill = p.crew_after.guns_skill_milli / 1000.0f;
				ship->crew.rpar_skill = p.crew_after.repair_skill_milli / 1000.0f;
				update_crew(ship);
				update_ship_status(ship);
			}
			statuslog(56, "%s", pending->audit.c_str());
			logit(LOG_SHIP, "%s", pending->audit.c_str());
			if (ch && ch->only.pc->divine_trade_payment_pending)
			{
				ch->only.pc->divine_trade_payment_pending = false;
				if (!currency_transaction_publish_trade(ch, p.payment))
					logit(LOG_SHIP, "Divine wallet publication mismatch pid=%u",
					      p.pid);
				if (p.has_cargo_effect)
				{
					auto *effect =
						get_spell_from_char(ch, PLAYER_TRADE_CARGO_AFFECT);
					if (effect)
						effect->modifier = p.cargo_effect.modifier;
					else
					{
						affected_type added{};
						added.type = p.cargo_effect.type;
						added.duration = p.cargo_effect.duration;
						added.flags = p.cargo_effect.flags;
						added.modifier = p.cargo_effect.modifier;
						added.location = p.cargo_effect.location;
						affect_to_char(ch, &added);
					}
					player_save_pipeline_mark(GET_PID(ch),
								  PLAYER_COMPONENT_AFFECTS);
				}
				if (pending->seadog)
					send_to_char(
						"Your &+csea&+Cfaring&n heritage has earned you a &+Ybonus&n in your sale...&n\r\n",
						ch);
				if (pending->diplomat)
					send_to_char(
						"Your diplomat's cut reduced the sale proceeds by 10%.\r\n",
						ch);
				if (pending->warship)
					send_to_char(
						p.has_cargo_effect ?
							"&+gBecause your cargo is obviosly stolen, local merchants bargain the price down.&n\n" :
							"&+gBecause your contraband is obviosly stolen, local merchants bargain the price down.&n\n",
						ch);
				if (pending->trader_completed)
					send_to_char(
						"&+rCon&+Rgra&+Wtula&+Rtio&+rns! You have completed the &+RTrader&+r achievement!&n\n",
						ch);
				if (pending->nexus_bonus > 0)
					send_to_char_f(
						ch, "&+yEnlil&n grants you an additional %s&n.\r\n",
						coin_stringv(pending->nexus_bonus));
				player_save_pipeline_request(
					ch,
					PLAYER_COMPONENT_STATUS |
						(p.has_cargo_effect ?
							 static_cast<player_component_mask_t>(
								 PLAYER_COMPONENT_AFFECTS) :
							 player_component_mask_t{ 0 }),
					RENT_CRASH, NOWHERE);
				send_to_char(pending->receipt.c_str(), ch);
				send_to_char_f(ch, "Your cargo trade is complete: %s %s.\r\n",
					       p.payment < 0 ? "paid" : "received",
					       coin_stringv(static_cast<int>(
						       p.payment < 0 ? -p.payment : p.payment)));
			}
		}
		else if (ch)
		{
			ch->only.pc->divine_trade_payment_pending = false;
			send_to_char(
				"The cargo trade could not settle. Your money and goods are unchanged.\r\n",
				ch);
		}
		pending.reset();
	}
}

bool divine_trade_runtime_purchase(P_char ch, P_ship ship, int slot, int port, int quantity,
				   int cost, divine_trade_goods goods)
try
{
	if (divine_trade_runtime_busy())
	{
		send_to_char(
			"The merchants are settling another trade. Please try again shortly.\r\n",
			ch);
		return true;
	}
	const auto *state = divine_boon_runtime_state();
	if (!state || state->mode != divine_boon_mode::divine || !ch || IS_NPC(ch))
		return false;
	const int64_t now = time(nullptr);
	const divine_boon_slot *boon = nullptr;
	for (const auto &candidate : state->slots)
		if (candidate.category == divine_boon_category::cargo &&
		    divine_boon_active(candidate, now))
		{
			boon = &candidate;
			break;
		}
	if (!boon || now <= boon->starts_at || port != boon->source_port || cost <= 0 ||
	    port != (goods == divine_trade_goods::cargo ? boon->cargo_commodity :
							  boon->contraband_commodity))
		return false;
	if (divine_trade_runtime_busy() || divine_boon_runtime_pending() ||
	    !cargo_trade_market_available())
	{
		send_to_char(
			"The merchants are settling another trade. Please try again shortly.\r\n",
			ch);
		return true;
	}
	critical_entity_key account;
	critical_operation_id operation;
	if (!currency_account_key(get_account_name_safe(ch), 0, &account) ||
	    !critical_operation_id_generate(&operation))
	{
		send_to_char("The merchants cannot settle this trade right now.\r\n", ch);
		return true;
	}

	if (auto dirty = dirty_owner.find(account.id);
	    dirty != dirty_owner.end() && dirty->second == UINT32_MAX)
	{
		ship_accounts[ship->db_id].insert(account.id);
		dirty->second = ship->db_id;
		queue_ship_save(ship, "retired cargo proof");
		send_to_char("Your crew is recording retired cargo. Please try again shortly.\r\n",
			     ch);
		return true;
	}
	for (const auto &[owner, book] : books)
		if (owner != account.id &&
		    std::any_of(book.lots.begin(), book.lots.end(),
				[&](const auto &lot) {
					return lot.ship_id == static_cast<uint32_t>(ship->db_id) &&
					       lot.slot == slot;
				}))
		{
			if (divine_trade_runtime_invalidate(ship, slot))
				queue_ship_save(ship, "transferred cargo proof");
			send_to_char(
				"Your crew is recording transferred cargo. Please try again shortly.\r\n",
				ch);
			return true;
		}
	const auto &before = divine_trade_runtime_book(account.id, boon->id);
	divine_trade_payload payload;
	payload.pid = payload.ship_owner_pid = GET_PID(ch);
	payload.ship_id = ship->db_id;
	payload.generation = cargo_trade_generation();
	payload.book_revision = before.revision;
	payload.wallet_revision = ch->only.pc->wallet_revision;
	payload.admitted_at = now;
	payload.payment = -static_cast<int64_t>(cost);
	currency_vector purse;
	purse.amount = { GET_COPPER(ch), GET_SILVER(ch), GET_GOLD(ch), GET_PLATINUM(ch) };
	const auto &live = ship->slot[slot];
	divine_trade_purchase buy;
	buy.operation = operation;
	buy.account = account.id;
	buy.ship_id = ship->db_id;
	buy.full_hold = SHIP_MAX_CARGO(ship);
	buy.slot = slot;
	buy.goods = goods;
	buy.source_port = port;
	buy.at = now;
	buy.quantity = quantity;
	buy.paid = cost;
	buy.slot_quantity_before = live.type == SLOT_EMPTY ? 0 : live.val0;
	buy.slot_basis_before = live.type == SLOT_EMPTY ? 0 : live.val1;
	if (buy.slot_quantity_before > static_cast<uint32_t>(INT32_MAX - quantity) ||
	    buy.slot_basis_before > INT32_MAX - cost ||
	    !currency_wallet_after_value(purse, payload.payment, &payload.wallet_after) ||
	    !divine_trade_prepare_purchase(before, *boon, buy, &payload.book_after))
	{
		send_to_char("The merchants cannot settle this trade right now.\r\n", ch);
		return true;
	}
	payload.slots_before.push_back(capture_slot(static_cast<uint8_t>(slot), live));
	payload.slots_after.push_back(
		{ static_cast<uint8_t>(slot),
		  goods == divine_trade_goods::cargo ? SLOT_CARGO : SLOT_CONTRABAND,
		  port,
		  SLOT_HOLD,
		  live.timer,
		  { static_cast<int32_t>(buy.slot_quantity_before + quantity),
		    static_cast<int32_t>(buy.slot_basis_before + cost), live.val2, live.val3,
		    live.val4 } });
	payload.crew_before = capture_crew(ship->crew);
	payload.crew_after = payload.crew_before;
	payload.market_after.push_back(cargo_trade_prepare_cell(
		goods == divine_trade_goods::cargo ? BOUGHT_CARGO : BOUGHT_CONTRA, port, port,
		quantity));
	if (!divine_trade_runtime_submit(ch, ship, operation, std::move(payload)))
		send_to_char("The merchants cannot settle this trade right now.\r\n", ch);
	return true;
}
catch (const std::bad_alloc &)
{
	return true;
}

bool divine_trade_runtime_sale(P_char ch, P_ship ship, int selected, int port,
			       divine_trade_goods goods)
try
{
	if (divine_trade_runtime_busy())
	{
		send_to_char(
			"The merchants are settling another trade. Please try again shortly.\r\n",
			ch);
		return true;
	}
	const auto *state = divine_boon_runtime_state();
	if (!state || state->mode != divine_boon_mode::divine || !ch || IS_NPC(ch))
		return false;
	const int64_t now = time(nullptr);
	const divine_boon_slot *boon = nullptr;
	for (const auto &candidate : state->slots)
		if (candidate.category == divine_boon_category::cargo &&
		    divine_boon_active(candidate, now))
		{
			boon = &candidate;
			break;
		}
	if (!boon)
		return false;
	critical_entity_key account;
	if (!currency_account_key(get_account_name_safe(ch), 0, &account))
		return false;
	const auto &before = divine_trade_runtime_book(account.id, boon->id);
	// Old/mixed manifests cannot each claim the same physical crates. Record
	// their invalidation before pricing an otherwise qualifying financial sale.
	if (auto linked = ship_accounts.find(ship->db_id);
	    linked != ship_accounts.end() && linked->second.size() > 1)
	{
		bool recording = false;
		for (int index = 0; index < MAXSLOTS; ++index)
		{
			if ((selected >= 0 && selected != index) ||
			    ship->slot[index].type != (goods == divine_trade_goods::cargo ?
							       SLOT_CARGO :
							       SLOT_CONTRABAND))
				continue;
			unsigned owners = 0;
			for (uint64_t owner : linked->second)
				if (auto found = books.find(owner);
				    found != books.end() &&
				    std::any_of(found->second.lots.begin(),
						found->second.lots.end(),
						[&](const auto &lot) {
							return lot.ship_id ==
								       static_cast<uint32_t>(
									       ship->db_id) &&
							       lot.slot == index;
						}))
					++owners;
			if (owners > 1)
			{
				if (!divine_trade_runtime_invalidate(ship, index))
				{
					if (recording)
						queue_ship_save(ship, "mixed cargo proof");
					send_to_char(
						"Your crew is recording mixed cargo. Please try again shortly.\r\n",
						ch);
					return true;
				}
				recording = true;
			}
		}
		if (recording)
		{
			queue_ship_save(ship, "mixed cargo proof");
			send_to_char(
				"Your crew is recording mixed cargo. Please try again shortly.\r\n",
				ch);
			return true;
		}
	}

	const bool tracked =
		std::any_of(before.lots.begin(), before.lots.end(),
			    [&](const auto &lot)
			    {
				    return lot.ship_id == static_cast<uint32_t>(ship->db_id) &&
					   lot.goods == goods &&
					   (selected < 0 || lot.slot == selected);
			    });
	if (!tracked)
		return false;
	if (divine_trade_runtime_busy() || divine_boon_runtime_pending() ||
	    !cargo_trade_market_available())
	{
		send_to_char(
			"The merchants are settling another trade. Please try again shortly.\r\n",
			ch);
		return true;
	}
	divine_trade_payload payload;
	payload.action = divine_trade_action::sale;
	payload.pid = payload.ship_owner_pid = GET_PID(ch);
	payload.ship_id = ship->db_id;
	payload.generation = cargo_trade_generation();
	payload.book_revision = before.revision;
	payload.book_after = before;
	payload.wallet_revision = ch->only.pc->wallet_revision;
	payload.admitted_at = now;
	double ordinary = 0, extra = 0;
	std::string receipt;
	int64_t receipt_total = 0;
	uint64_t cargo_count = 0;
	for (int slot = 0; slot < MAXSLOTS; ++slot)
	{
		const auto &live = ship->slot[slot];
		if ((selected >= 0 && selected != slot) ||
		    live.type !=
			    (goods == divine_trade_goods::cargo ? SLOT_CARGO : SLOT_CONTRABAND))
			continue;
		if (live.index < 0 || live.index >= NUM_PORTS || live.val0 <= 0 || live.val1 < 0)
			return true;
		divine_trade_removal removal;
		removal.account = account.id;
		removal.ship_id = ship->db_id;
		removal.slot = slot;
		removal.goods = goods;
		removal.source_port = live.index;
		removal.destination_port = port;
		removal.at = now;
		removal.slot_quantity_before = removal.quantity = live.val0;
		removal.slot_basis_before = live.val1;
		divine_trade_consumption consumed;
		divine_trade_book next;
		if (!divine_trade_prepare_removal(payload.book_after, *boon, removal, &next,
						  &consumed))
		{
			send_to_char("The merchants cannot verify this cargo load.\r\n", ch);
			return true;
		}
		payload.book_after = std::move(next);
		payload.qualifying_quantity += consumed.qualifying_quantity;
		auto cell = std::find_if(payload.market_after.begin(), payload.market_after.end(),
					 [&](const auto &value)
					 { return value.commodity == live.index; });
		const int unit = cell == payload.market_after.end() ?
					 (goods == divine_trade_goods::cargo ?
						  cargo_buy_price(port, live.index) :
						  contra_buy_price(port, live.index)) :
					 (port == live.index ? static_cast<int>(cell->price * .5) :
							       cell->price);
		const double penalty =
			(goods == divine_trade_goods::cargo && has_eq_diplomat(ship) ? .9 : 1.0) *
			(IS_WARSHIP(ship) ? .6 : 1.0);
		const double base = static_cast<double>(live.val0) * unit;
		ordinary += base * penalty *
			    (goods == divine_trade_goods::cargo && has_innate(ch, INNATE_SEADOG) ?
				     1.1 :
				     1.0);
		extra += static_cast<double>(consumed.qualifying_quantity) * unit * .25 * penalty;
		const double cumulative = std::floor(
			check_nexus_bonus_precise(ch, ordinary, NEXUS_BONUS_CARGO, false) + extra);
		if (!std::isfinite(cumulative) || cumulative < 0 || cumulative > INT32_MAX)
			return true;
		const int64_t proceeds = static_cast<int64_t>(cumulative) - receipt_total;
		receipt_total = static_cast<int64_t>(cumulative);
		const int64_t profit = live.val1 > 0 ? (proceeds - live.val1) * 100 / live.val1 : 0;
		char line[512];
		snprintf(line, sizeof(line),
			 "You sell %d crates of %s for %s, making %lld%% profit.\r\n", live.val0,
			 goods == divine_trade_goods::cargo ? cargo_type_name(live.index) :
							      contra_type_name(live.index),
			 coin_stringv(static_cast<int>(proceeds)), static_cast<long long>(profit));
		receipt += line;

		const auto adjusted = cargo_trade_prepare_cell(
			goods == divine_trade_goods::cargo ? SOLD_CARGO : SOLD_CONTRA, port,
			live.index, live.val0,
			cell == payload.market_after.end() ? -1 : cell->modifier);
		if (cell == payload.market_after.end())
			payload.market_after.push_back(adjusted);
		else
			*cell = adjusted;
		payload.slots_before.push_back(capture_slot(static_cast<uint8_t>(slot), live));
		payload.slots_after.push_back({ static_cast<uint8_t>(slot),
						SLOT_EMPTY,
						-1,
						-1,
						0,
						{ -1, -1, -1, -1, -1 } });
		cargo_count += live.val0;
	}
	const double normal =
		ordinary > 0 ? check_nexus_bonus_precise(ch, ordinary, NEXUS_BONUS_CARGO, false) :
			       0;
	const double credit = std::floor(normal + extra);
	if (!std::isfinite(credit) || credit < 0 || credit > INT32_MAX)
	{
		send_to_char("The merchants cannot settle a payment of that size.\r\n", ch);
		return true;
	}
	payload.payment = static_cast<int64_t>(credit);
	currency_vector purse;
	purse.amount = { GET_COPPER(ch), GET_SILVER(ch), GET_GOLD(ch), GET_PLATINUM(ch) };
	if (!currency_wallet_after_value(purse, payload.payment, &payload.wallet_after))
	{
		send_to_char("Your purse cannot hold that payment.\r\n", ch);
		return true;
	}
	payload.crew_before = capture_crew(ship->crew);
	ShipCrew crew = ship->crew;
	const auto normal_payment = static_cast<int64_t>(std::floor(normal));
	if (normal_payment > 0)
	{
		crew.sail_skill_raise((static_cast<float>(normal_payment) / 1000000.0) *
				      (goods == divine_trade_goods::cargo ? 1.5 : 1.0));
		crew.rpar_skill_raise((static_cast<float>(normal_payment) / 1000000.0) /
				      (goods == divine_trade_goods::cargo ? 2.0 : 3.0));
	}
	payload.crew_after = capture_crew(crew);
	bool trader_completed = false;
	if (goods == divine_trade_goods::cargo)
	{
		const auto *effect = get_spell_from_char(ch, PLAYER_TRADE_CARGO_AFFECT);
		const int32_t old = effect ? effect->modifier : 0;
		if (old < 0 || cargo_count > static_cast<uint64_t>(INT32_MAX - old))
		{
			send_to_char("The merchants cannot update your trading record.\r\n", ch);
			return true;
		}
		payload.has_cargo_effect = true;
		payload.cargo_effect.type = PLAYER_TRADE_CARGO_AFFECT;
		payload.cargo_effect.duration = -1;
		payload.cargo_effect.modifier = old + static_cast<int32_t>(cargo_count);
		trader_completed = old < 10000 && payload.cargo_effect.modifier >= 10000;
		payload.cargo_effect.flags = AFFTYPE_NOSHOW | AFFTYPE_PERM | AFFTYPE_NODISPEL;
	}
	critical_operation_id operation;
	if (!critical_operation_id_generate(&operation) ||
	    !divine_trade_runtime_submit(ch, ship, operation, std::move(payload)))
		send_to_char("The merchants cannot settle this trade right now.\r\n", ch);
	else
	{
		pending->receipt = std::move(receipt);
		pending->trader_completed = trader_completed;
		pending->nexus_bonus =
			static_cast<int>(std::max(0.0, std::floor(normal) - std::floor(ordinary)));
	}
	return true;
}
catch (const std::bad_alloc &)
{
	return true;
}

std::vector<divine_trade_book> divine_trade_runtime_ship_books(uint32_t ship_id)
{
	std::vector<divine_trade_book> captured;
	const auto found = ship_accounts.find(ship_id);
	if (found != ship_accounts.end())
		for (uint64_t account : found->second)
		{
			const auto book = books.find(account);
			const auto dirty = dirty_owner.find(account);
			if (book != books.end() && book->second.revision &&
			    (dirty == dirty_owner.end() || !dirty->second ||
			     dirty->second == ship_id))
				captured.push_back(book->second);
		}
	return captured;
}
uint64_t divine_trade_runtime_ship_revision(uint32_t ship_id)
{
	uint64_t revision = 0;
	const auto found = ship_accounts.find(ship_id);
	if (found != ship_accounts.end())
		for (uint64_t account : found->second)
		{
			const auto book = books.find(account);
			if (book != books.end())
				revision ^= book->second.revision + account +
					    0x9e3779b97f4a7c15ULL + (revision << 6) +
					    (revision >> 2);
		}
	return revision;
}
bool divine_trade_runtime_invalidate(P_ship ship, int slot)
try
{
	if (!ship || IS_NPC_SHIP(ship) || ship->db_id <= 0)
		return true;
	if (divine_trade_runtime_busy(ship))
		return false;
	auto affected = divine_trade_runtime_ship_books(ship->db_id);
	for (auto &book : affected)
	{
		divine_trade_book after;
		if (!divine_trade_prepare_invalidation(book, ship->db_id, slot, &after))
			return false;
		book = std::move(after);
	}
	for (auto &book : affected)
	{
		if (books[book.account].revision != book.revision)
			dirty_owner[book.account] = ship->db_id;
		books[book.account] = std::move(book);
	}
	return true;
}
catch (const std::bad_alloc &)
{
	return false;
}
bool divine_trade_runtime_loss(P_ship ship, int slot, int quantity)
try
{
	if (!ship || IS_NPC_SHIP(ship) || ship->db_id <= 0)
		return true;
	if (divine_trade_runtime_busy(ship) || slot < 0 || slot >= MAXSLOTS)
		return false;
	auto &live = ship->slot[slot];
	if (live.type != SLOT_CARGO && live.type != SLOT_CONTRABAND)
		return true;
	if (quantity <= 0 || live.val0 <= 0 || quantity > live.val0)
		return false;
	int64_t removed_basis = static_cast<int64_t>(std::max(0, live.val1)) * quantity / live.val0;
	auto affected = divine_trade_runtime_ship_books(ship->db_id);
	size_t owners = 0;
	for (const auto &book : affected)
		if (std::any_of(book.lots.begin(), book.lots.end(),
				[&](const auto &lot) {
					return lot.ship_id == static_cast<uint32_t>(ship->db_id) &&
					       lot.slot == slot;
				}))
			++owners;
	for (auto &book : affected)
	{
		const auto tracked = std::find_if(
			book.lots.begin(), book.lots.end(),
			[&](const auto &lot) {
				return lot.ship_id == static_cast<uint32_t>(ship->db_id) &&
				       lot.slot == slot;
			});
		if (tracked == book.lots.end())
			continue;
		divine_trade_book after;
		const auto goods = live.type == SLOT_CARGO ? divine_trade_goods::cargo :
							     divine_trade_goods::contraband;
		if (owners > 1 || live.val1 < 0 || tracked->goods != goods ||
		    tracked->source_port != live.index)
		{
			if (!divine_trade_prepare_invalidation(book, ship->db_id, slot, &after))
				return false;
		}
		else
		{
			divine_trade_removal loss;
			loss.ship_id = ship->db_id;
			loss.slot = slot;
			loss.goods = goods;
			loss.source_port = live.index;
			loss.at = time(nullptr);
			loss.slot_quantity_before = live.val0;
			loss.slot_basis_before = live.val1;
			loss.quantity = quantity;
			divine_trade_consumption consumed;
			if (!divine_trade_prepare_removal(book, {}, loss, &after, &consumed))
			{
				if (!divine_trade_prepare_invalidation(book, ship->db_id, slot,
								       &after))
					return false;
			}
			else
				removed_basis = consumed.removed_basis;
		}
		book = std::move(after);
	}
	for (auto &book : affected)
	{
		if (books[book.account].revision != book.revision)
			dirty_owner[book.account] = ship->db_id;
		books[book.account] = std::move(book);
	}
	live.val1 = std::max(0, live.val1) - static_cast<int32_t>(removed_basis);
	return true;
}
catch (const std::bad_alloc &)
{
	return false;
}

void divine_trade_runtime_restore_books(std::vector<divine_trade_book> before, uint32_t dirty_ship)
{
	for (auto &book : before)
	{
		dirty_owner[book.account] = dirty_ship;
		books[book.account] = std::move(book);
	}
}

void divine_trade_runtime_ship_saved(uint32_t ship_id)
{
	for (auto &[account, owner] : dirty_owner)
	{
		static_cast<void>(account);
		if (owner == ship_id)
			owner = 0;
	}
}
