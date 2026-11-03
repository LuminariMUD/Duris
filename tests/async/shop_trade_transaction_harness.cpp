#include "economy/currency_transaction.h"
#include "item/item_ownership_runtime.h"
#include "economy/shop_trade_transaction.h"
#include "core/utils.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot_codec.h"

#include <cassert>
#include <cstdarg>
#include <cstdlib>
#include <cstring>

namespace
{
char_data character = {};
pc_only_data pc = {};
bool player_online = true;
critical_command submitted_command = {};
// The buyer's wallet in memory, and how many saves were queued before a command.
int64_t wallet = 1000;
int saves = 0;
item_transfer_payload published_transfer = {};
item_transfer_result published_transfer_result = {};
bool ownership_published = false;
bool shop_revision_published = false;
// The item offered for sale, and where it is.
obj_data sold = {};
enum class place
{
	inventory,
	held,
	gone
} sold_place = place::inventory;
bool completion_called = false;
int completion_count = 0;
bool batch_ready = false;
bool decline_wallet = false;
int ownership_calls = 0;
bool completion_committed = false;
bool completion_offline = false, ownership_allowed = true;
unsigned int completion_error = 0;

shop_trade_payload trade(shop_trade_action action, uint64_t uid)
{
	shop_trade_payload payload = {};
	payload.action = action;
	payload.player_pid = 42;
	payload.shop_id = 7;
	payload.racewar = 1;
	strcpy(payload.account_name.data(), "shop-account");
	payload.price = 100;
	payload.expected_wallet_revision = pc.wallet_revision;
	payload.expected_bank_revision = 3;
	payload.expected_shop_revision = 4;
	payload.selected_item_uid = uid;
	payload.target_root_item_uid = uid;
	payload.item_count = 1;
	payload.item_blob_size = 1;
	payload.item_blob[0] = 0x5a;
	if (action == shop_trade_action::buy_produced)
	{
		payload.stock_item_uid = 900;
		payload.expected_stock_item_revision = 6;
		payload.stock_vnum = 800;
		payload.items[0] = { uid, uid,
				     0,	  ITEM_TRANSFER_ABSENT_REVISION,
				     800, item_custody_state::absent };
	}
	else if (action == shop_trade_action::buy_existing)
	{
		payload.stock_item_uid = uid;
		payload.expected_stock_item_revision = 5;
		payload.stock_vnum = 800;
		payload.items[0] = { uid, uid, 0, 5, 800, item_custody_state::active };
	}
	else if (action == shop_trade_action::discard_invalid)
	{
		payload.price = 0;
		payload.stock_item_uid = uid;
		payload.expected_stock_item_revision = 5;
		payload.stock_vnum = 800;
		payload.items[0] = { uid, uid, 0, 5, 800, item_custody_state::active };
	}
	else
		payload.items[0] = { uid, uid, 0, 5, 800, item_custody_state::active };
	if (action == shop_trade_action::sell_store || action == shop_trade_action::sell_destroy)
	{
		player_item_snapshot item = {};
		item.object_uid = uid;
		item.vnum = 800;
		item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
		std::vector<uint8_t> blob;
		assert(player_item_snapshot_list_encode({ item }, &blob) ==
		       player_snapshot_codec_result::ok);
		payload.item_blob_size = blob.size();
		std::copy(blob.begin(), blob.end(), payload.item_blob.begin());
	}
	return payload;
}

shop_trade_result result(shop_trade_action action, uint64_t uid, uint64_t player_revision,
			 uint64_t counterparty_revision)
{
	shop_trade_result value = {};
	value.action = action;
	value.wallet = { { 0, 0, 9, 9 } };
	value.bank = { { 0, 0, 0, 0 } };
	value.wallet_revision = 3;
	value.bank_revision = 4;
	value.shop_revision = 5;
	value.player_owner_revision = player_revision;
	value.counterparty_owner_revision = counterparty_revision;
	value.item_count = 1;
	value.item_uids[0] = uid;
	value.item_revisions[0] = action == shop_trade_action::buy_produced ? 1 : 6;
	return value;
}

critical_completion completion(const shop_trade_result &result)
{
	critical_completion value = {};
	value.operation_id = submitted_command.operation_id;
	value.outcome = critical_apply_outcome::applied;
	std::array<uint8_t, SHOP_TRADE_RESULT_BYTES> encoded = {};
	assert(shop_trade_command_encode_result(result, &encoded));
	value.result_size = encoded.size();
	std::copy(encoded.begin(), encoded.end(), value.result_payload.begin());
	return value;
}

void completed(P_char completed_character, bool committed, const shop_trade_result &,
	       unsigned int error_code, const shop_trade_payload &)
{
	assert(!completed_character || completed_character == &character);
	completion_called = true;
	completion_offline = !completed_character;
	++completion_count;
	completion_committed = committed;
	completion_error = error_code;
}
bool prepare_batch(P_char, const shop_trade_payload &, const shop_trade_result &)
{
	return batch_ready;
}
} // namespace

P_room world = nullptr;
static bool reserved = false;
bool currency_transaction_reserve_trade(P_char buyer, int64_t payment)
{
	assert(buyer == &character);
	if (reserved || decline_wallet || (payment < 0 && wallet < -payment))
		return false;
	reserved = true;
	return true;
}
void currency_transaction_release_trade(uint32_t pid)
{
	assert(pid == 42);
	reserved = false;
}
bool currency_transaction_publish_trade(P_char buyer, int64_t payment)
{
	assert(buyer == &character && reserved);
	if (decline_wallet)
		return false;
	wallet += payment;
	++pc.wallet_revision;
	return true;
}
bool player_save_pipeline_reserve_trade(uint32_t pid, const player_pending_trade_snapshot &tag)
{
	assert(pid == 42 && tag.wallet_revision == pc.wallet_revision);
	return true;
}
void player_save_pipeline_release_trade(uint32_t pid)
{
	assert(pid == 42);
}
player_save_pipeline_result player_save_pipeline_request(P_char buyer, player_component_mask_t, int,
							 int)
{
	assert(buyer == &character && (!character.carrying || sold_place == place::inventory));
	++saves;
	return player_save_pipeline_result::queued;
}

critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	submitted_command = std::move(command);
	return critical_submit_result::accepted;
}

bool currency_transaction_submit_wallet_value(P_char buyer, int64_t value, currency_reason_type,
					      int64_t, critical_source_site,
					      critical_deadline_class, currency_completion_fn,
					      const void *, size_t)
{
	assert(buyer == &character);
	if (decline_wallet)
		return true; // synchronous range/reservation refusal without a revision change
	if (value < 0 && wallet < -value)
		return false;
	wallet += value;
	++buyer->only.pc->wallet_revision;
	return true;
}

void currency_transaction_save_first(P_char buyer)
{
	assert(buyer == &character);
	++saves;
}

void obj_from_char(P_obj object)
{
	assert(object == &sold && sold_place == place::inventory);
	sold_place = place::held;
	character.carrying = nullptr;
}

void obj_to_char(P_obj object, P_char seller)
{
	assert(object == &sold && seller == &character && sold_place == place::held);
	sold_place = place::inventory;
	character.carrying = &sold;
}

void extract_obj(P_obj object, int)
{
	assert(object == &sold && sold_place == place::held);
	sold_place = place::gone;
}

P_obj find_live_object(P_obj expected, uint64_t uid)
{
	return expected == &sold && uid == sold.obj_uid && sold_place != place::gone ? expected :
										       nullptr;
}

P_char find_player_by_pid(int pid)
{
	return player_online && pid == 42 ? &character : nullptr;
}

bool item_ownership_runtime_apply(const item_transfer_payload &payload,
				  const item_transfer_result &result,
				  const uint64_t *item_revisions)
{
	assert(item_revisions);
	for (size_t index = 0; index < payload.item_count; ++index)
		assert(item_revisions[index] ==
		       (payload.from_owner.type == item_owner_type::system ? 1 : 6));
	published_transfer = payload;
	published_transfer_result = result;
	ownership_published = ownership_allowed;
	++ownership_calls;
	return ownership_allowed;
}

bool shop_trade_runtime_can_advance(uint32_t shop_id, uint64_t expected_revision,
				    uint64_t new_revision)
{
	return shop_id == 7 && expected_revision == 4 && new_revision == 5;
}

bool shop_trade_runtime_advance(uint32_t shop_id, uint64_t expected_revision, uint64_t new_revision)
{
	shop_revision_published =
		shop_trade_runtime_can_advance(shop_id, expected_revision, new_revision);
	return shop_revision_published;
}

int main()
{
	character.only.pc = &pc;
	pc.pid = 42;
	pc.wallet_revision = 2;
	character.in_room = NOWHERE;

	shop_trade_payload produced = trade(shop_trade_action::buy_produced, 300);
	produced.target_root_item_uid = 700;
	produced.target_parent_item_uid = 700;
	produced.expected_target_parent_revision = 5;
	// Funds are reserved at submit and paid only at committed publication.
	assert(shop_trade_transaction_submit(&character, produced, completed));
	assert(wallet == 1000 && saves == 1);
	assert(shop_trade_transaction_player_busy(&character));
	assert(!shop_trade_transaction_submit(&character, produced, completed));
	critical_completion produced_completion =
		completion(result(shop_trade_action::buy_produced, 300, 8, 6));
	shop_trade_transaction_handle_completions(&produced_completion, 1);
	assert(wallet == 900 && ownership_published && shop_revision_published &&
	       completion_called && completion_committed && completion_error == 0 &&
	       published_transfer.from_owner.type == item_owner_type::system &&
	       published_transfer.to_owner.type == item_owner_type::player &&
	       published_transfer.target_root_item_uid == 700 &&
	       published_transfer.target_parent_item_uid == 700 &&
	       published_transfer.expected_target_parent_revision == 5 &&
	       published_transfer_result.from_owner_revision == 6 &&
	       published_transfer_result.to_owner_revision == 8 &&
	       !shop_trade_transaction_player_busy(&character));

	// A refused purchase never debits the price.
	completion_called = completion_committed = false;
	assert(shop_trade_transaction_submit(
		&character, trade(shop_trade_action::buy_existing, 303), completed));
	assert(wallet == 900);
	critical_completion refused =
		completion(result(shop_trade_action::buy_existing, 303, 8, 6));
	refused.outcome = critical_apply_outcome::terminal_failure;
	shop_trade_transaction_handle_completions(&refused, 1);
	assert(wallet == 900 && completion_called && !completion_committed);
	// A purchase the wallet cannot cover is refused before anything is queued.
	wallet = 50;
	assert(!shop_trade_transaction_submit(
		&character, trade(shop_trade_action::buy_existing, 304), completed));
	assert(wallet == 50 && !shop_trade_transaction_player_busy(&character));
	wallet = 900;

	// A sale takes its item out of the inventory at submit, after the seller's save is
	// queued; a refused sale gives it back before the callback.
	sold.obj_uid = 301;
	character.carrying = &sold;
	completion_called = false;
	saves = 0;
	const shop_trade_payload destroyed = trade(shop_trade_action::sell_destroy, 301);
	assert(shop_trade_transaction_submit(&character, destroyed, completed));
	assert(sold_place == place::held && saves == 1);
	player_snapshot held_capture = {};
	held_capture.pid = 42;
	held_capture.components = PLAYER_COMPONENT_INVENTORY;
	assert(shop_trade_transaction_capture_items(&character, &held_capture));
	assert(held_capture.items.size() == 1 && held_capture.items[0].object_uid == 301);
	critical_completion refused_sale =
		completion(result(shop_trade_action::sell_destroy, 301, 9, 2));
	refused_sale.outcome = critical_apply_outcome::terminal_failure;
	shop_trade_transaction_handle_completions(&refused_sale, 1);
	assert(sold_place == place::inventory && character.carrying == &sold && wallet == 900 &&
	       completion_called && !completion_committed);
	// An item extracted while it was held is not given back.
	completion_called = false;
	assert(shop_trade_transaction_submit(&character, destroyed, completed));
	sold_place = place::gone;
	refused_sale.operation_id = submitted_command.operation_id;
	shop_trade_transaction_handle_completions(&refused_sale, 1);
	assert(sold_place == place::gone && !character.carrying && completion_called);
	sold_place = place::inventory;
	character.carrying = &sold;
	// An item the seller no longer carries cannot be sold.
	assert(!shop_trade_transaction_submit(
		&character, trade(shop_trade_action::sell_destroy, 399), completed));
	assert(sold_place == place::inventory && !shop_trade_transaction_player_busy(&character));

	ownership_published = shop_revision_published = completion_called = completion_committed =
		false;
	assert(shop_trade_transaction_submit(&character, destroyed, completed));
	critical_completion destroyed_completion =
		completion(result(shop_trade_action::sell_destroy, 301, 9, 2));
	player_online = false;
	shop_trade_transaction_handle_completions(&destroyed_completion, 1);
	assert(!shop_trade_transaction_player_busy(&character) && wallet == 900 &&
	       ownership_published && completion_called && completion_offline);
	player_online = true;
	// Login reads the compound purse; completion must not pay it twice.
	wallet = 1000;
	++pc.wallet_revision;
	shop_trade_transaction_player_ready(&character);
	assert(wallet == 1000 && ownership_published && shop_revision_published &&
	       completion_called && completion_committed && sold_place == place::held &&
	       published_transfer.from_owner.type == item_owner_type::player &&
	       published_transfer.to_owner.type == item_owner_type::destruction &&
	       published_transfer_result.from_owner_revision == 9 &&
	       published_transfer_result.to_owner_revision == 2 &&
	       !shop_trade_transaction_player_busy(&character));

	ownership_published = shop_revision_published = completion_called = completion_committed =
		false;
	const shop_trade_payload cleanup = trade(shop_trade_action::discard_invalid, 302);
	assert(shop_trade_transaction_submit(&character, cleanup, completed));
	critical_completion cleanup_completion =
		completion(result(shop_trade_action::discard_invalid, 302, 10, 3));
	shop_trade_transaction_handle_completions(&cleanup_completion, 1);
	assert(wallet == 1000 && ownership_published && shop_revision_published &&
	       completion_called && completion_committed &&
	       published_transfer.from_owner.type == item_owner_type::shopkeeper &&
	       published_transfer.to_owner.type == item_owner_type::destruction &&
	       published_transfer_result.from_owner_revision == 10 &&
	       published_transfer_result.to_owner_revision == 3 &&
	       !shop_trade_transaction_player_busy(&character));

	// A publication refusal retains the obligation; a later retry pays once.
	sold.obj_uid = 350;
	sold_place = place::inventory;
	character.carrying = &sold;
	const auto retry_sale = trade(shop_trade_action::sell_store, 350);
	const int callbacks_before_retry = completion_count,
		  ownership_before_retry = ownership_calls;
	assert(shop_trade_transaction_submit(&character, retry_sale, completed));
	const auto retry_completion = completion(result(shop_trade_action::sell_store, 350, 11, 4));
	decline_wallet = true;
	shop_trade_transaction_handle_completions(&retry_completion, 1);
	assert(wallet == 1000 && completion_count == callbacks_before_retry &&
	       ownership_calls == ownership_before_retry &&
	       shop_trade_transaction_player_busy(&character));
	decline_wallet = false;
	shop_trade_transaction_player_ready(&character);
	assert(wallet == 1100 && completion_count == callbacks_before_retry + 1);
	shop_trade_transaction_handle_completions(&retry_completion, 1);
	assert(wallet == 1100 && completion_count == callbacks_before_retry + 1);
	wallet = 1000;
	// A committed forest waits for every live root before applying ownership or
	// crediting the keeper. Reconnect retries it once; duplicate completions do not.
	auto batch = trade(shop_trade_action::buy_produced, 400);
	batch.multi_root = true;
	batch.item_count = 50;
	batch.price = 500;
	batch.target_root_item_uid = batch.target_parent_item_uid = 700;
	batch.expected_target_parent_revision = 5;
	for (size_t index = 0; index < batch.item_count; ++index)
		batch.items[index] = { 400 + index, 400 + index,
				       0,	    ITEM_TRANSFER_ABSENT_REVISION,
				       800,	    item_custody_state::absent };
	decline_wallet = true;
	assert(!shop_trade_transaction_submit(&character, batch, completed, prepare_batch));
	assert(wallet == 1000 && !shop_trade_transaction_player_busy(&character));
	decline_wallet = false;
	assert(shop_trade_transaction_submit(&character, batch, completed, prepare_batch));
	assert(wallet == 1000 && shop_trade_transaction_blocks_commands(&character));
	auto batch_result = result(shop_trade_action::buy_produced, 400, 11, 4);
	batch_result.item_count = 50;
	for (size_t index = 0; index < batch_result.item_count; ++index)
	{
		batch_result.item_uids[index] = 400 + index;
		batch_result.item_revisions[index] = 1;
	}
	const auto batch_completion = completion(batch_result);
	const int previous_callbacks = completion_count, previous_ownership = ownership_calls;
	shop_trade_transaction_handle_completions(&batch_completion, 1);
	shop_trade_transaction_player_ready(&character);
	assert(completion_count == previous_callbacks && ownership_calls == previous_ownership &&
	       shop_trade_transaction_player_busy(&character) && wallet == 1000);
	batch_ready = true;
	shop_trade_transaction_player_ready(&character);
	assert(completion_count == previous_callbacks + 1 &&
	       ownership_calls == previous_ownership + 1 && published_transfer.multi_root &&
	       published_transfer.item_count == 50 && published_transfer.selected_item_uid == 0 &&
	       published_transfer.target_parent_item_uid == 700 &&
	       !shop_trade_transaction_blocks_commands(&character) && wallet == 500);
	shop_trade_transaction_handle_completions(&batch_completion, 1);
	assert(completion_count == previous_callbacks + 1 &&
	       ownership_calls == previous_ownership + 1);
	batch.price = 0;
	saves = 0;
	assert(shop_trade_transaction_submit(&character, batch, completed, prepare_batch));
	assert(saves == 1 && wallet == 500);
	const auto free_completion = completion(batch_result);
	shop_trade_transaction_handle_completions(&free_completion, 1);
	assert(wallet == 500 && !shop_trade_transaction_player_busy(&character));
	// An absent actor's durable forest must relinquish its live copies even
	// when optional cache publication fails, so login cannot duplicate them.
	batch.price = 100;
	batch.expected_wallet_revision = pc.wallet_revision;
	assert(shop_trade_transaction_submit(&character, batch, completed, prepare_batch));
	const int before_offline = completion_count;
	const auto offline_batch = completion(batch_result);
	player_online = false;
	ownership_allowed = false;
	shop_trade_transaction_handle_completions(&offline_batch, 1);
	assert(!shop_trade_transaction_player_busy(&character) && completion_offline &&
	       completion_count == before_offline + 1 && wallet == 500);
	player_online = true;
	ownership_allowed = true;
	shop_trade_transaction_reset_for_tests();
}
