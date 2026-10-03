/*
 auction_houses.c
 -- torgal april 2006 (torgal@durismud.com)
*/

#include "core/prototypes.h"
#include "core/structs.h"
#include "world/db.h"
#include "cmd/interp.h"
#include "core/utility.h"
#include "economy/auction_houses.h"
#include "economy/auction_room_registry.h"
#include "economy/auction_transaction.h"
#include "economy/currency_transaction.h"
#include "flatfile/flatfile_auction_repository.h"
#include "flatfile/flatfile_offline_message_repository.h"
#include "item/item_ownership_runtime.h"
#include "persistence/persistence_checkpoint.h"
#include "persistence/persistence_mode.h"
#include <algorithm>
#include <cerrno>
#include <climits>
#include <ctime>
#include <openssl/sha.h>
#include <string.h>
#include <string>
#include <unordered_set>
#include <vector>
#include "core/files.h"
#include "magic/spells.h"
#include "sql/sql.h"
#include "sql/sql_player.h"
#include "net/ws_handlers.h"
using namespace std;

extern P_room world;

namespace
{
void install_auction_house_room_procedures()
{
	for (size_t index = 0; index < AUCTION_HOUSE_REGISTERED_ROOM_COUNT; ++index)
	{
		int room_vnum = NOWHERE;
		if (!auction_house_registered_room_vnum(index, &room_vnum))
			continue;
		const int room_rnum = real_room(room_vnum);
		if (room_rnum == NOWHERE)
		{
			logit(LOG_WIZ, "Auction service room %d is not present in the world",
			      room_vnum);
			continue;
		}
		world[room_rnum].funct = auction_house_room_proc;
	}
}
} // namespace

#ifdef __NO_MYSQL__
extern P_obj object_list;

namespace
{
int flat_default_auction_length = 2 * 24 * 60 * 60;
int flat_bid_time_extension = 5 * 60;
int flat_listing_fee = 1000;
float flat_start_price_fee = 0.02f;
float flat_closing_fee = 0.03f;
std::unordered_set<uint32_t> pending_flat_finalizations;

const char *flat_auction_root()
{
	return persistence_mode_flatfile_root();
}

bool copy_auction_text(char *destination, size_t capacity, const char *source)
{
	if (!destination || !capacity || !source || strlen(source) >= capacity)
		return false;
	memcpy(destination, source, strlen(source) + 1);
	return true;
}

bool fill_auction_actor(P_char ch, auction_command_payload *payload)
{
	if (!ch || IS_NPC(ch) || !payload || !ch->only.pc)
		return false;
	const char *account = get_account_name_safe(ch);
	if (!account || !strcmp(account, "Unknown") ||
	    !copy_auction_text(payload->account_name.data(), payload->account_name.size(),
			       account) ||
	    !copy_auction_text(payload->actor_name.data(), payload->actor_name.size(),
			       GET_NAME(ch)))
		return false;
	payload->actor_pid = static_cast<uint32_t>(GET_PID(ch));
	payload->racewar = static_cast<uint8_t>(GET_RACEWAR(ch));
	payload->closing_fee_basis_points =
		static_cast<uint32_t>(std::max(0.0f, std::min(1.0f, flat_closing_fee)) * 10000.0f);
	payload->bid_extension_seconds =
		static_cast<uint32_t>(std::max(0, flat_bid_time_extension));
	return true;
}

bool parse_auction_platinum(const char *text, int64_t *value)
{
	if (!text || !*text || !value)
		return false;
	char *end = nullptr;
	errno = 0;
	const long long platinum = strtoll(text, &end, 10);
	if (errno || !end || *end || platinum < 0 || platinum > INT_MAX / 1000)
		return false;
	*value = platinum * 1000;
	return true;
}

bool text_equal_folded(const std::string &left, const char *right)
{
	if (!right || left.size() != strlen(right))
		return false;
	for (size_t index = 0; index < left.size(); ++index)
		if (tolower(static_cast<unsigned char>(left[index])) !=
		    tolower(static_cast<unsigned char>(right[index])))
			return false;
	return true;
}

bool flat_auction_access_blocked(P_char ch)
{
	if (!affected_by_spell(ch, SPELL_NOAUCTION) || IS_TRUSTED(ch))
		return false;
	send_to_char("&+RAuction House access has been temporarily disabled since you have "
		     "recently &+Yremoved&+R a piece of worn equipment. Please try again in a "
		     "little while.\r\n",
		     ch);
	return true;
}

long auction_seconds_remaining(uint64_t end_time)
{
	const uint64_t now = static_cast<uint64_t>(time(nullptr));
	if (end_time <= now)
		return 0;
	return static_cast<long>(std::min<uint64_t>(end_time - now, LONG_MAX));
}

void flat_money_claim_completed(P_char ch, bool committed, const auction_command_result &result,
				unsigned int, const auction_command_payload &)
{
	if (!ch)
		return;
	if (!committed)
		send_to_char("Your auction money remains available for pickup.\r\n", ch);
	else
		send_to_char_f(ch, "&+WYou pick up &n%s&+W.&n\r\n",
			       coin_stringv(static_cast<int>(result.wallet_value_delta)));
}

void flat_list_completed(P_char ch, bool committed, const auction_command_result &result,
			 unsigned int, const auction_command_payload &payload)
{
	if (!ch)
		return;
	if (!committed)
	{
		send_to_char("The auction was not listed; your item and money are unchanged.\r\n",
			     ch);
		return;
	}
	// The auction took the listed items out of the inventory at submit.
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS |
							  PLAYER_COMPONENT_EQUIPMENT |
							  PLAYER_COMPONENT_INVENTORY);
	send_to_char_f(ch, "&+W%s is now listed as auction %u.&n\r\n", payload.object_short.data(),
		       result.auction_id);
}

void flat_bid_completed(P_char ch, bool committed, const auction_command_result &result,
			unsigned int, const auction_command_payload &)
{
	if (!ch)
		return;
	if (!committed)
		send_to_char("Your bid did not commit; your money is unchanged.\r\n", ch);
	else
		send_to_char_f(ch, "&+WYour bid of &n%s&+W on auction %u committed.&n\r\n",
			       coin_stringv(static_cast<int>(result.final_price)),
			       result.auction_id);
}

void flat_remove_completed(P_char ch, bool committed, const auction_command_result &result,
			   unsigned int, const auction_command_payload &)
{
	if (!ch)
		return;
	if (!committed)
		send_to_char("That auction could not be removed.\r\n", ch);
	else
	{
		send_to_char_f(ch, "&+WAuction %u removed.&n\r\n", result.auction_id);
		logit(LOG_WIZ, "Auction [%u] removed by %s", result.auction_id, GET_NAME(ch));
	}
}

void flat_finalize_completed(P_char, bool, const auction_command_result &, unsigned int,
			     const auction_command_payload &payload)
{
	pending_flat_finalizations.erase(payload.auction_id);
}

void flat_item_claim_completed(P_char ch, bool committed, const auction_command_result &result,
			       unsigned int, const auction_command_payload &payload)
{
	if (!ch)
		return;
	if (!committed)
	{
		send_to_char("Your auction items remain available for pickup.\r\n", ch);
		return;
	}
	for (size_t index = 0; index < result.item_count; ++index)
	{
		P_obj object = read_one_object(const_cast<char *>(
			reinterpret_cast<const char *>(payload.object_blob.data())));
		if (!object)
		{
			persistence_alert(AVATAR, "auction", "player", "unknown", "claim_publish",
					  "deserialize_failed", "auction_id=%u item_uid=%llu",
					  result.auction_id,
					  static_cast<unsigned long long>(result.item_uids[index]));
			continue;
		}
		object->obj_uid = result.item_uids[index];
		obj_to_char(object, ch);
		send_to_char_f(ch, "&+WYou pick up &n%s&+W.&n\r\n", object->short_description);
	}
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS |
							  PLAYER_COMPONENT_EQUIPMENT |
							  PLAYER_COMPONENT_INVENTORY);
}

bool report_flat_query_failure(P_char ch, const std::string &error)
{
	send_to_char(
		"The auction catalog could not be read safely. Please contact an immortal.\r\n",
		ch);
	logit(LOG_WIZ, "Flat auction query failed: %s", error.c_str());
	return true;
}

flatfile_offline_message_id auction_event_message_id(const critical_operation_id &operation_id,
						     uint8_t index)
{
	std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES + 1> input = {};
	std::copy(operation_id.bytes.begin(), operation_id.bytes.end(), input.begin());
	input.back() = index;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(input.data(), input.size(), digest.data());
	flatfile_offline_message_id id = {};
	std::copy_n(digest.begin(), id.size(), id.begin());
	return id;
}

bool stage_auction_event_message(const flatfile_auction_event_projection &event, uint32_t pid,
				 uint8_t index, const std::string &message)
{
	if (!pid)
		return true;
	const char *root = flat_auction_root();
	const auto id = auction_event_message_id(event.operation_id, index);
	std::string error;
	if (!root || flatfile_offline_message_enqueue(root, pid, id, message, &error) !=
			     flatfile_offline_message_result::ok)
	{
		logit(LOG_WIZ, "Could not stage flat auction notification pid=%u auction=%u: %s",
		      pid, event.result.auction_id, error.c_str());
		return false;
	}
	if (send_to_pid(message.c_str(), pid))
	{
		const auto acknowledged =
			flatfile_offline_message_acknowledge(root, pid, id, &error);
		if (acknowledged != flatfile_offline_message_result::ok &&
		    acknowledged != flatfile_offline_message_result::not_found)
			logit(LOG_WIZ,
			      "Flat auction live notification remains in mailbox pid=%u auction=%u: %s",
			      pid, event.result.auction_id, error.c_str());
	}
	return true;
}

bool publish_flat_auction_event(const flatfile_auction_event_projection &event)
{
	char message[MAX_STRING_LENGTH] = {};
	uint8_t message_index = 0;
	if (event.result.event_type == auction_event_type::bid_placed &&
	    event.result.previous_bidder_pid &&
	    event.result.previous_bidder_pid != event.result.winner_pid)
	{
		snprintf(message, sizeof(message),
			 "&+WA voice says in your mind, 'You were outbid in auction [%u] for %s, "
			 "and your bid money is available for pickup.'\r\n",
			 event.result.auction_id, event.listing.object_short.c_str());
		if (!stage_auction_event_message(event, event.result.previous_bidder_pid,
						 message_index++, message))
			return false;
	}
	else if (event.result.event_type == auction_event_type::sold)
	{
		snprintf(message, sizeof(message),
			 "&+WAuction [%u] for %s sold; your proceeds are available for pickup.\r\n",
			 event.result.auction_id, event.listing.object_short.c_str());
		if (!stage_auction_event_message(event, event.result.seller_pid, message_index++,
						 message))
			return false;
		snprintf(message, sizeof(message),
			 "&+WYou won auction [%u] for %s; the item is available for pickup.\r\n",
			 event.result.auction_id, event.listing.object_short.c_str());
		if (!stage_auction_event_message(event, event.result.winner_pid, message_index++,
						 message))
			return false;
	}
	else if (event.result.event_type == auction_event_type::expired ||
		 event.result.event_type == auction_event_type::removed)
	{
		snprintf(message, sizeof(message),
			 "&+WAuction [%u] for %s closed; the item is available for pickup.\r\n",
			 event.result.auction_id, event.listing.object_short.c_str());
		if (!stage_auction_event_message(event, event.result.seller_pid, message_index++,
						 message))
			return false;
		snprintf(message, sizeof(message),
			 "&+WAuction [%u] for %s was removed; your bid money is available for "
			 "pickup.\r\n",
			 event.result.auction_id, event.listing.object_short.c_str());
		if (event.result.event_type == auction_event_type::removed &&
		    !stage_auction_event_message(event, event.result.winner_pid, message_index++,
						 message))
			return false;
	}
	if (event.result.event_type == auction_event_type::listed)
		ws_broadcast_auction_new(event.result.auction_id, event.listing.seller_name.c_str(),
					 event.listing.object_short.c_str(),
					 static_cast<int>(event.listing.current_price),
					 static_cast<int>(event.listing.buy_price),
					 static_cast<int>(event.listing.end_time));
	else if (event.result.event_type == auction_event_type::bid_placed)
		ws_broadcast_auction_bid(event.result.auction_id, event.listing.winner_name.c_str(),
					 static_cast<int>(event.result.final_price),
					 event.result.previous_bidder_pid, "");
	else
		ws_broadcast_auction_close(
			event.result.auction_id, event.listing.winner_name.c_str(),
			event.result.winner_pid, static_cast<int>(event.result.final_price),
			event.result.event_type == auction_event_type::sold    ? "sold" :
			event.result.event_type == auction_event_type::removed ? "removed" :
										 "expired",
			event.result.seller_pid, event.listing.seller_name.c_str());
	return true;
}
} // namespace

string format_time(long seconds)
{
	char result[128] = {};
	if (seconds < 0)
		seconds = 0;
	if (seconds < 60)
		snprintf(result, sizeof(result), "&+R<1m&n");
	else if (seconds < 60 * 60)
		snprintf(result, sizeof(result), "&+R%ldm&n", (seconds / 60) % 60);
	else if (seconds < 6 * 60 * 60)
		snprintf(result, sizeof(result), "&+Y%ldh %ldm&n", seconds / 3600,
			 (seconds / 60) % 60);
	else
		snprintf(result, sizeof(result), "&+W%ldh&n", seconds / 3600);
	return result;
}

void init_auction_houses()
{
	fprintf(stderr, "-- Initializing Flat-File Auctions\r\n");
	install_auction_house_room_procedures();
	flat_default_auction_length = get_property("auctions.defaultLength", 2 * 24 * 60 * 60);
	flat_bid_time_extension = get_property("auctions.bidTimeExtension", 5 * 60);
	flat_listing_fee = get_property("auctions.listingFee", 1000);
	flat_start_price_fee = get_property("auctions.startPricePctFee", 0.02);
	flat_closing_fee = get_property("auctions.closingPctFee", 0.03);
}
void shutdown_auction_houses() {}
void auction_houses_activity()
{
	const char *root = flat_auction_root();
	if (!root)
		return;
	std::vector<flatfile_auction_listing_projection> listings;
	std::string error;
	if (flatfile_auction_list_open(root, &listings, &error) !=
	    flatfile_auction_query_result::ok)
	{
		logit(LOG_WIZ, "Flat auction expiry scan failed: %s", error.c_str());
		return;
	}
	const uint64_t now = static_cast<uint64_t>(time(nullptr));
	for (const auto &listing : listings)
	{
		if (listing.end_time > now || pending_flat_finalizations.size() >= 64 ||
		    !pending_flat_finalizations.insert(listing.auction_id).second)
			continue;
		auction_command_payload payload = {};
		payload.action = auction_action::finalize;
		payload.auction_id = listing.auction_id;
		payload.closing_fee_basis_points = static_cast<uint32_t>(
			std::max(0.0f, std::min(1.0f, flat_closing_fee)) * 10000.0f);
		if (!auction_transaction_submit_background(payload, flat_finalize_completed))
			pending_flat_finalizations.erase(listing.auction_id);
	}
	for (size_t published = 0; published < 16; ++published)
	{
		flatfile_auction_event_projection event;
		const auto found = flatfile_auction_find_pending_event(root, &event, &error);
		if (found == flatfile_auction_query_result::not_found)
			break;
		if (found != flatfile_auction_query_result::ok)
		{
			logit(LOG_WIZ, "Flat auction event scan failed: %s", error.c_str());
			break;
		}
		if (!publish_flat_auction_event(event))
			break;
		if (flatfile_auction_acknowledge_event(root, event.operation_id, &error) !=
		    flatfile_auction_query_result::ok)
		{
			logit(LOG_WIZ, "Flat auction event acknowledgement failed: %s",
			      error.c_str());
			break;
		}
		logit(LOG_DEBUG, "Published flat auction outbox %llu for auction %u",
		      static_cast<unsigned long long>(event.outbox_id), event.result.auction_id);
	}
}

bool auction_offer(P_char ch, char *args)
{
	char item_name[MAX_INPUT_LENGTH] = {}, value_text[MAX_INPUT_LENGTH] = {};
	half_chop(args, item_name, args);
	P_obj object = get_obj_in_list_vis(ch, item_name, ch->carrying);
	if (!object)
	{
		send_to_char("&+WYou don't seem to have that item!\r\n", ch);
		return true;
	}
	if (IS_ARTIFACT(object) || IS_SET(object->extra_flags, ITEM_NODROP) ||
	    IS_SET(object->extra_flags, ITEM_NORENT) || object->condition < 90 || object->contains)
	{
		send_to_char("&+WYou can't sell that item.\r\n", ch);
		return true;
	}
	int64_t start_price = 0, buy_price = 0;
	half_chop(args, value_text, args);
	if (*value_text && !parse_auction_platinum(value_text, &start_price))
	{
		send_to_char("&+WInvalid starting price.\r\n", ch);
		return true;
	}
	half_chop(args, value_text, args);
	if (*value_text && !parse_auction_platinum(value_text, &buy_price))
	{
		send_to_char("&+WInvalid buy-it-now price.\r\n", ch);
		return true;
	}
	if (buy_price && buy_price < start_price)
	{
		send_to_char("&+WInvalid buy-it-now price.\r\n", ch);
		return true;
	}
	half_chop(args, value_text, args);
	const int days = *value_text ? atoi(value_text) : flat_default_auction_length / 86400;
	if (days < 1 || days > 7)
	{
		send_to_char("&+WInvalid auction length: please enter 1 to 7 (days).\r\n", ch);
		return true;
	}
	half_chop(args, value_text, args);
	const int quantity = *value_text ? atoi(value_text) : 1;
	if (quantity < 1 || quantity > static_cast<int>(AUCTION_COMMAND_MAX_ITEMS))
	{
		send_to_char("&+WInvalid auction quantity: please enter 1 to 9 (items).\r\n", ch);
		return true;
	}
	auction_command_payload payload = {};
	payload.action = auction_action::list;
	if (!fill_auction_actor(ch, &payload))
		return report_flat_query_failure(ch, "player auction identity is unavailable");
	payload.start_price = start_price;
	payload.buy_price = buy_price;
	payload.listing_fee =
		flat_listing_fee + static_cast<int64_t>(start_price * flat_start_price_fee);
	if (GET_MONEY(ch) < payload.listing_fee)
	{
		send_to_char("&+WYou don't have enough money to list the item.\r\n", ch);
		return true;
	}
	payload.end_time = static_cast<uint64_t>(time(nullptr)) + days * UINT64_C(86400);
	P_obj current = object;
	for (int index = 0; index < quantity; ++index)
	{
		if (!current || current->R_num != object->R_num)
		{
			send_to_char("You do not have enough of that item.\r\n", ch);
			return true;
		}
		// The seller holds it in memory; the listing claims it from whatever the
		// ownership record still says.
		if (!current->obj_uid)
		{
			send_to_char("&+WYou can't sell that item.\r\n", ch);
			return true;
		}
		payload.items[index] = { current->obj_uid, 0,
					 static_cast<int32_t>(OBJ_VNUM(current)) };
		current = current->next_content;
	}
	payload.item_count = quantity;
	char serialized[AUCTION_BLOB_MAX_BYTES] = {};
	const int serialized_size = write_one_object(object, serialized);
	if (serialized_size <= 0 ||
	    serialized_size >= static_cast<int>(payload.object_blob.size()) ||
	    !object->short_description ||
	    !copy_auction_text(payload.object_short.data(), payload.object_short.size(),
			       object->short_description) ||
	    !copy_auction_text(payload.id_keywords.data(), payload.id_keywords.size(),
			       object->name ? object->name : ""))
		return report_flat_query_failure(ch, "auction item could not be encoded safely");
	memcpy(payload.object_blob.data(), serialized, serialized_size + 1);
	payload.object_blob_size = serialized_size + 1;
	if (!auction_transaction_submit(ch, payload, flat_list_completed))
		send_to_char("The auction house is busy; nothing was changed.\r\n", ch);
	else
		send_to_char("Your auction listing is being committed.\r\n", ch);
	return true;
}

bool auction_bid(P_char ch, char *args)
{
	char id_text[MAX_INPUT_LENGTH] = {}, bid_text[MAX_INPUT_LENGTH] = {};
	half_chop(args, id_text, args);
	half_chop(args, bid_text, args);
	char *end = nullptr;
	errno = 0;
	const unsigned long parsed = strtoul(id_text, &end, 10);
	int64_t bid = 0;
	if (errno || !end || *end || !parsed || parsed > UINT_MAX ||
	    !parse_auction_platinum(bid_text, &bid) || bid <= 0)
	{
		send_to_char("&+WUsage: auction bid <auction id> <positive value in plat>.&n\r\n",
			     ch);
		return true;
	}
	auction_command_payload payload = {};
	payload.action = auction_action::bid;
	payload.auction_id = static_cast<uint32_t>(parsed);
	payload.value = bid;
	if (!fill_auction_actor(ch, &payload))
		return report_flat_query_failure(ch, "player auction identity is unavailable");
	// The bid leaves the wallet until the auction settles it.
	if (GET_MONEY(ch) < bid)
	{
		send_to_char_f(ch, "&+WYou don't have enough money!\r\nYou need: &n%s\r\n",
			       coin_stringv(static_cast<int>(bid)));
		return true;
	}
	if (!auction_transaction_submit(ch, payload, flat_bid_completed))
		send_to_char("The auction house is busy; your money is unchanged.\r\n", ch);
	else
		send_to_char("Your bid is being committed.\r\n", ch);
	return true;
}

bool auction_remove(P_char ch, char *args)
{
	if (!IS_TRUSTED(ch))
		return auction_help(ch, "");
	char id_text[MAX_INPUT_LENGTH] = {};
	half_chop(args, id_text, args);
	char *end = nullptr;
	errno = 0;
	const unsigned long parsed = strtoul(id_text, &end, 10);
	if (errno || !end || *end || !parsed || parsed > UINT_MAX)
	{
		send_to_char("&+WThere is no auction with that id!\r\n", ch);
		return true;
	}
	auction_command_payload payload = {};
	payload.action = auction_action::remove;
	payload.auction_id = static_cast<uint32_t>(parsed);
	if (!fill_auction_actor(ch, &payload))
		return report_flat_query_failure(ch, "player auction identity is unavailable");
	if (!auction_transaction_submit(ch, payload, flat_remove_completed))
		send_to_char("The auction house is busy; nothing was changed.\r\n", ch);
	else
		send_to_char("The auction removal is being committed.\r\n", ch);
	return true;
}

bool auction_list(P_char ch, char *args)
{
	const char *root = flat_auction_root();
	if (!root)
		return report_flat_query_failure(ch, "flat-file state root is not configured");
	char mode[MAX_INPUT_LENGTH] = {};
	half_chop(args, mode, args);
	char player_name[MAX_INPUT_LENGTH] = {};
	std::vector<std::string> keywords;
	if (!*mode || isname(mode, "all a"))
		send_to_char("&+WAuctions closing soon:\r\n", ch);
	else if (isname(mode, "player p"))
	{
		half_chop(args, player_name, args);
		if (!*player_name)
		{
			send_to_char("&+WPlease enter the name of a player.\r\n", ch);
			return true;
		}
		send_to_char_f(ch, "&+WAuctions by &n%.100s&+W:\r\n", player_name);
	}
	else if (isname(mode, "sort s"))
	{
		char keyword[MAX_INPUT_LENGTH] = {};
		while (*args)
		{
			half_chop(args, keyword, args);
			keywords.emplace_back(keyword);
		}
		if (keywords.empty())
		{
			send_to_char("&+WPlease enter one or more item keywords.\r\n", ch);
			return true;
		}
		send_to_char("&+WAuctions matching those item keywords:&n\r\n", ch);
	}
	else
	{
		send_to_char("&+WAuction list syntax:\r\nauction list\r\n"
			     "auction list sort <keyword list>\r\n"
			     "auction list player <playername>\r\n",
			     ch);
		return true;
	}
	std::vector<flatfile_auction_listing_projection> listings;
	std::string error;
	if (flatfile_auction_list_open(root, &listings, &error) !=
	    flatfile_auction_query_result::ok)
		return report_flat_query_failure(ch, error);
	size_t shown = 0;
	for (const auto &listing : listings)
	{
		if (*player_name && !text_equal_folded(listing.seller_name, player_name))
			continue;
		bool matches = true;
		for (const auto &keyword : keywords)
			if (listing.id_keywords.find(keyword) == std::string::npos)
				matches = false;
		if (!matches)
			continue;
		const char mine = GET_PID(ch) == static_cast<int>(listing.seller_pid) ||
						  GET_PID(ch) ==
							  static_cast<int>(listing.winner_pid) ?
					  '*' :
					  ' ';
		const size_t quantity = listing.items.size();
		if (listing.buy_price > 0)
			send_to_char_f(
				ch,
				"&+W%u)&+W%c&n %zu %s&n [%s&n] &+WBid: &n%lldp&+W Buy: &n%lldp\r\n",
				listing.auction_id, mine, quantity, listing.object_short.c_str(),
				format_time(auction_seconds_remaining(listing.end_time)).c_str(),
				static_cast<long long>(listing.current_price / 1000),
				static_cast<long long>(listing.buy_price / 1000));
		else
			send_to_char_f(
				ch, "&+W%u)&+W%c&n %zu %s&n [%s&n] &+WBid: &n%lldp\r\n",
				listing.auction_id, mine, quantity, listing.object_short.c_str(),
				format_time(auction_seconds_remaining(listing.end_time)).c_str(),
				static_cast<long long>(listing.current_price / 1000));
		++shown;
	}
	if (!shown)
		send_to_char("&+yNo auctions found!\r\n", ch);
	return true;
}

bool auction_info(P_char ch, char *args)
{
	char id_text[MAX_INPUT_LENGTH] = {};
	half_chop(args, id_text, args);
	char *end = nullptr;
	errno = 0;
	const unsigned long parsed = strtoul(id_text, &end, 10);
	if (errno || !*id_text || !end || *end || !parsed || parsed > UINT_MAX)
	{
		send_to_char("&+WPlease enter a valid auction id.\r\n", ch);
		return true;
	}
	const char *root = flat_auction_root();
	if (!root)
		return report_flat_query_failure(ch, "flat-file state root is not configured");
	flatfile_auction_listing_projection listing;
	std::string error;
	const auto found =
		flatfile_auction_find_open(root, static_cast<uint32_t>(parsed), &listing, &error);
	if (found == flatfile_auction_query_result::not_found)
	{
		send_to_char("&+WThere is no open auction with that id!\r\n", ch);
		return true;
	}
	if (found != flatfile_auction_query_result::ok)
		return report_flat_query_failure(ch, error);
	send_to_char_f(ch, "&+WAuction &+W%u\r\n", listing.auction_id);
	send_to_char_f(ch, "&+WSeller: &n%s\r\n", listing.seller_name.c_str());
	send_to_char_f(ch, "&+WTime left: &n%s\r\n",
		       format_time(auction_seconds_remaining(listing.end_time)).c_str());
	if (!listing.winner_pid)
		send_to_char_f(ch, "&+WNo bids received. Starting bid: &n%lldp\r\n",
			       static_cast<long long>(listing.current_price / 1000));
	else
		send_to_char_f(ch, "&+WHigh bid: &n%lldp&+W by &n%s\r\n",
			       static_cast<long long>(listing.current_price / 1000),
			       listing.winner_name.c_str());
	if (listing.buy_price > 0)
		send_to_char_f(ch, "&+WBuy-it-now price: &n%lldp\r\n",
			       static_cast<long long>(listing.buy_price / 1000));
	if (!listing.object_info.empty())
	{
		send_to_char("&+WItem information:&n\r\n", ch);
		send_to_char(listing.object_info.c_str(), ch);
		if (listing.object_info.back() != '\n')
			send_to_char("\r\n", ch);
	}
	return true;
}

bool auction_pickup(P_char ch, char *args)
{
	if (args && *args)
	{
		send_to_char(
			"Auction pickup no longer accepts an id; committed claims are authoritative.\r\n",
			ch);
		return true;
	}
	if (auction_transaction_player_busy(ch))
	{
		send_to_char("Your previous auction request is still being committed.\r\n", ch);
		return true;
	}
	const char *root = flat_auction_root();
	if (!root)
		return report_flat_query_failure(ch, "flat-file state root is not configured");
	flatfile_auction_pickup_projection pickup;
	std::string error;
	if (flatfile_auction_find_pickup(root, static_cast<uint32_t>(GET_PID(ch)), &pickup,
					 &error) != flatfile_auction_query_result::ok)
		return report_flat_query_failure(ch, error);
	auction_command_payload payload = {};
	if (!fill_auction_actor(ch, &payload))
		return report_flat_query_failure(ch, "player auction identity is unavailable");
	if (pickup.money > 0)
	{
		payload.action = auction_action::claim_money;
		if (!auction_transaction_submit(ch, payload, flat_money_claim_completed))
			send_to_char("The auction house is busy; your money remains staged.\r\n",
				     ch);
		else
			send_to_char("Your auction money pickup is being committed.\r\n", ch);
		return true;
	}
	if (!pickup.has_item_claim || pickup.item_claim.items.empty())
	{
		send_to_char("&+WYou have no items or money to pickup!&n\r\n", ch);
		return true;
	}
	if (pickup.item_claim.object_blob.empty() || pickup.item_claim.object_blob.back() != 0 ||
	    pickup.item_claim.object_blob.size() > payload.object_blob.size() ||
	    pickup.item_claim.items.size() > payload.items.size())
		return report_flat_query_failure(ch, "pending auction item blob is invalid");
	payload.action = auction_action::claim_item;
	payload.auction_id = pickup.item_claim.auction_id;
	payload.object_blob_size = pickup.item_claim.object_blob.size();
	std::copy(pickup.item_claim.object_blob.begin(), pickup.item_claim.object_blob.end(),
		  payload.object_blob.begin());
	for (const auto &item : pickup.item_claim.items)
		payload.items[payload.item_count++] = { item.item_uid, item.item_revision,
							item.vnum };
	if (!auction_transaction_submit(ch, payload, flat_item_claim_completed))
		send_to_char("The auction house is busy; your items remain staged.\r\n", ch);
	else
		send_to_char("Your auction item pickup is being committed.\r\n", ch);
	return true;
}

bool auction_help(P_char ch, const char *)
{
	send_to_char("&+WAuction commands: offer, list, info, bid, pickup, remove (immortal).\r\n",
		     ch);
	return true;
}

void new_ah_call(P_char ch, char *arguments, int cmd)
{
	if (cmd != CMD_AUCTION || !IS_ALIVE(ch) || IS_NPC(ch))
		return;
	if (IS_FIGHTING(ch))
	{
		send_to_char("&+yYou're too busy fighting for your life to participate in an "
			     "auction!&n\r\n",
			     ch);
		return;
	}
	char command[MAX_INPUT_LENGTH] = {};
	char args[MAX_STRING_LENGTH] = {};
	half_chop(arguments, command, args);
	if (isname(command, "offer o"))
	{
		if (!flat_auction_access_blocked(ch))
			auction_offer(ch, args);
	}
	else if (isname(command, "list l"))
		auction_list(ch, args);
	else if (isname(command, "info i"))
		auction_info(ch, args);
	else if (isname(command, "bid b"))
	{
		if (!flat_auction_access_blocked(ch))
			auction_bid(ch, args);
	}
	else if (isname(command, "pickup p"))
		auction_pickup(ch, args);
	else if (isname(command, "remove r"))
		auction_remove(ch, args);
	else
		auction_help(ch, arguments);
}

int auction_house_room_proc(int, P_char ch, int cmd, char *arguments)
{
	if (cmd != CMD_AUCTION || !IS_PC(ch))
		return FALSE;
	new_ah_call(ch, arguments, cmd);
	return TRUE;
}
bool finalize_auction(int /*auction_id*/, P_char /*to_ch*/)
{
	return false;
}
bool insert_money_pickup(int /*pid*/, int /*money*/)
{
	return false;
}
bool auction_publish_committed_event(const auction_command_result & /*result*/,
				     unsigned long long /*outbox_id*/)
{
	return false;
}
#else
#include <mysql.h>
#include "sql/sql_async.h"

// auction status values (match DB column)
#define AUCTION_STATUS_OPEN 1
#define AUCTION_STATUS_CLOSED 2
#define AUCTION_STATUS_REMOVED 3

extern P_room world;
extern P_index obj_index;
extern P_desc descriptor_list;
extern P_obj object_list;

// externs for build_obj_info_text
extern const flagDef affected1_bits[];
extern const flagDef affected2_bits[];
extern const flagDef affected3_bits[];
extern const flagDef affected4_bits[];
extern const flagDef affected5_bits[];
extern const char *apply_types[];
extern const char *spells[];

char buff[MAX_STRING_LENGTH];

int DEFAULT_AUCTION_LENGTH;
int BID_TIME_EXTENSION;
int AUCTION_LIST_LIMIT;
int AUCTION_LISTING_FEE;
float AUCTION_START_PRICE_PCT_FEE;
float AUCTION_CLOSING_PCT_FEE;

#define STR_TOLOWER(str)                                            \
	{                                                           \
		for (int _str_i = 0; _str_i < str.size(); _str_i++) \
			str[_str_i] = tolower(str[_str_i]);         \
	}

extern MYSQL *DB;

EqSort *sorter;

// forward declarations
bool check_db_active();

// backfill state - static so it persists between calls
static int backfill_state = 0; // 0=pending, 1=done, -1=skip (no column)
static int backfill_total = 0;

struct auction_money_pickup_context
{
	int money;
};

// Legacy one-time backfill retained for migration tooling only. It is deliberately
// disconnected from recurring gameplay; new listings populate obj_info_text at write time.
#define BACKFILL_BATCH_SIZE 5

[[maybe_unused]] static void backfill_auction_info_text_tick()
{
	// already done or skipped
	if (backfill_state != 0)
		return;

	if (!check_db_active())
		return;

	// first time - check if column exists
	static bool column_checked = false;
	if (!column_checked)
	{
		column_checked = true;
		if (!qry("SELECT obj_info_text FROM auctions LIMIT 1"))
		{
			// only skip permanently if its a missing column error (1054)
			// transient errors (network, etc) should retry next tick
			unsigned int err = mysql_errno(DB);
			if (err == 1054)
			{ // ER_BAD_FIELD_ERROR
				logit(LOG_DEBUG,
				      "auction: obj_info_text column not found, skipping backfill");
				backfill_state = -1;
			}
			else
			{
				column_checked = false; // retry next tick
			}
			return;
		}
		mysql_free_result(mysql_store_result(DB));
	}

	// grab a small batch of auctions missing obj_info_text
	if (!qry("SELECT id, obj_blob_str FROM auctions WHERE obj_info_text IS NULL AND status = %d LIMIT %d",
		 AUCTION_STATUS_OPEN, BACKFILL_BATCH_SIZE))
		return;

	MYSQL_RES *res = mysql_store_result(DB);
	if (!res)
		return;

	int row_count = mysql_num_rows(res);
	if (row_count == 0)
	{
		// all done
		mysql_free_result(res);
		backfill_state = 1;
		if (backfill_total > 0)
			logit(LOG_STATUS, "auction backfill complete: %d items processed",
			      backfill_total);
		return;
	}

	MYSQL_ROW row;
	while ((row = mysql_fetch_row(res)))
	{
		int auction_id = atoi(row[0]);
		char *blob_str = row[1];

		if (!blob_str || !*blob_str)
			continue;

		// deserialize object from blob
		P_obj tmp_obj = read_one_object(blob_str);
		if (!tmp_obj)
			continue;

		// generate info text
		char obj_info_buf[MAX_STRING_LENGTH * 2];
		build_obj_info_text(tmp_obj, obj_info_buf, sizeof(obj_info_buf));

		// escape for sql
		char obj_info_escaped[MAX_STRING_LENGTH * 4];
		mysql_real_escape_string(DB, obj_info_escaped, obj_info_buf, strlen(obj_info_buf));

		// update the auction
		qry("UPDATE auctions SET obj_info_text = '%s' WHERE id = %d", obj_info_escaped,
		    auction_id);

		// cleanup
		extract_obj(tmp_obj);
		backfill_total++;
	}

	mysql_free_result(res);
}

void init_auction_houses()
{
	fprintf(stderr, "-- Initializing Auctions\r\n");
	install_auction_house_room_procedures();

	sorter = new EqSort();

	DEFAULT_AUCTION_LENGTH = get_property("auctions.defaultLength", (2 * 24 * 60 * 60));
	BID_TIME_EXTENSION = get_property("auctions.bidTimeExtension", (5 * 60));
	AUCTION_LIST_LIMIT = get_property("auctions.auctionListLimit", 100);
	AUCTION_LISTING_FEE = get_property("auctions.listingFee", 1000);
	AUCTION_START_PRICE_PCT_FEE = get_property("auctions.startPricePctFee", 0.02);
	AUCTION_CLOSING_PCT_FEE = get_property("auctions.closingPctFee", 0.03);
}

void shutdown_auction_houses()
{
	if (sorter)
	{
		delete sorter;
		sorter = NULL;
	}
}

bool check_db_active()
{
#ifdef __NO_MYSQL__
	return FALSE;
#endif

	if (!DB)
		return FALSE;
	else
		return TRUE;
}

// lazy helper macro for build_obj_info_text
#define APPEND_INFO(fmt, ...)                                                            \
	do                                                                               \
	{                                                                                \
		int _w = checked_snprintf(buf + pos, bufsize - pos, fmt, ##__VA_ARGS__); \
		if (_w > 0)                                                              \
			pos += MIN(static_cast<size_t>(_w), bufsize - pos - 1);          \
	} while (0)

// builds item info text for db storage / web display
// no inaccuracy, no player-specific junk, just raw item stats
int build_obj_info_text(P_obj obj, char *buf, size_t bufsize)
{
	if (!obj || !buf || bufsize < 1)
		return 0;

	size_t pos = 0;
	char tmpbuf[MAX_STRING_LENGTH];
	char tmpbuf2[MAX_STRING_LENGTH];
	int i;
	bool found;

	// weight and value
	APPEND_INFO("%s weighs %d pounds and is worth roughly %s.\n", obj->short_description,
		    GET_OBJ_WEIGHT(obj), coin_stringv(obj->cost));

	// abilities from bitvectors (haste, fly, sanctuary, etc)
	if (obj->bitvector || obj->bitvector2 || obj->bitvector3 || obj->bitvector4 ||
	    obj->bitvector5)
	{
		APPEND_INFO("Abilities: ");

		tmpbuf[0] = '\0';
		if (obj->bitvector)
			sprintbitde(obj->bitvector, affected1_bits, tmpbuf);
		if (obj->bitvector2)
		{
			sprintbitde(obj->bitvector2, affected2_bits, tmpbuf2);
			APPENDF(tmpbuf, "%s", tmpbuf2);
		}
		if (obj->bitvector3)
		{
			sprintbitde(obj->bitvector3, affected3_bits, tmpbuf2);
			APPENDF(tmpbuf, "%s", tmpbuf2);
		}
		if (obj->bitvector4)
		{
			sprintbitde(obj->bitvector4, affected4_bits, tmpbuf2);
			APPENDF(tmpbuf, "%s", tmpbuf2);
		}
		if (obj->bitvector5)
		{
			sprintbitde(obj->bitvector5, affected5_bits, tmpbuf2);
			APPENDF(tmpbuf, "%s", tmpbuf2);
		}
		APPEND_INFO("%s\n", tmpbuf);
	}

	// item flags - build comma separated list
	tmpbuf[0] = '\0';
	if (IS_SET(obj->extra2_flags, ITEM2_MAGIC))
		strcat(tmpbuf, "magical, ");
	if (IS_SET(obj->extra_flags, ITEM_ARTIFACT))
		strcat(tmpbuf, "artifact, ");
	if (IS_SET(obj->extra_flags, ITEM_NOSLEEP))
		strcat(tmpbuf, "nosleep, ");
	if (IS_SET(obj->extra_flags, ITEM_NOCHARM))
		strcat(tmpbuf, "nocharm, ");
	if (IS_SET(obj->extra_flags, ITEM_NOSUMMON))
		strcat(tmpbuf, "nosummon, ");
	if (IS_SET(obj->extra_flags, ITEM_FLOAT))
		strcat(tmpbuf, "float, ");
	if (IS_SET(obj->extra_flags, ITEM_LEVITATES))
		strcat(tmpbuf, "levitate, ");
	if (IS_SET(obj->extra_flags, ITEM_TWOHANDS))
		strcat(tmpbuf, "two-handed, ");
	if (IS_SET(obj->extra_flags, ITEM_WHOLE_BODY))
		strcat(tmpbuf, "whole-body, ");
	if (IS_SET(obj->extra_flags, ITEM_WHOLE_HEAD))
		strcat(tmpbuf, "whole-head, ");
	if (IS_SET(obj->extra_flags, ITEM_NODROP))
		strcat(tmpbuf, "cursed, ");
	if (IS_SET(obj->extra2_flags, ITEM2_BLESS))
		strcat(tmpbuf, "blessed, ");
	if (IS_SET(obj->extra_flags, ITEM_LIT))
		strcat(tmpbuf, "lit, ");
	if (IS_SET(obj->extra_flags, ITEM_NOLOCATE))
		strcat(tmpbuf, "nolocate, ");
	if (IS_SET(obj->extra_flags, ITEM_CAN_THROW1) || IS_SET(obj->extra_flags, ITEM_CAN_THROW2))
		strcat(tmpbuf, "throwable, ");
	if (IS_SET(obj->extra_flags, ITEM_RETURNING))
		strcat(tmpbuf, "returning, ");

	// trim trailing comma
	size_t len = strlen(tmpbuf);
	if (len > 2 && tmpbuf[len - 2] == ',')
		tmpbuf[len - 2] = '\0';

	if (tmpbuf[0])
		APPEND_INFO("Flags: %s\n", tmpbuf);

	// item type specific stuff
	switch (GET_ITEM_TYPE(obj))
	{
	case ITEM_WEAPON:
		APPEND_INFO("Damage: '%dD%d'\n", obj->value[1], obj->value[2]);
		break;
	case ITEM_MISSILE:
		APPEND_INFO("Damage: '%dD%d'\n", obj->value[1], obj->value[2]);
		break;
	case ITEM_FIREWEAPON:
		APPEND_INFO("Rate of fire: %d, Range: %d\n", obj->value[0], obj->value[1]);
		break;
	case ITEM_WAND:
	case ITEM_STAFF:
		APPEND_INFO("Charges: %d/%d\n", obj->value[2], obj->value[1]);
		if (obj->value[3] >= 1 && obj->value[3] <= LAST_SPELL)
		{
			sprinttype(obj->value[3], (const char **)spells, tmpbuf);
			APPEND_INFO("Spell: %s (level %d)\n", tmpbuf, obj->value[0]);
		}
		break;
	case ITEM_SCROLL:
	case ITEM_POTION:
		APPEND_INFO("Level %d spells: ", obj->value[0]);
		if (obj->value[1] >= 1 && obj->value[1] <= LAST_SPELL)
		{
			sprinttype(obj->value[1], (const char **)spells, tmpbuf);
			APPEND_INFO("%s ", tmpbuf);
		}
		if (obj->value[2] >= 1 && obj->value[2] <= LAST_SPELL)
		{
			sprinttype(obj->value[2], (const char **)spells, tmpbuf);
			APPEND_INFO("%s ", tmpbuf);
		}
		if (obj->value[3] >= 1 && obj->value[3] <= LAST_SPELL)
		{
			sprinttype(obj->value[3], (const char **)spells, tmpbuf);
			APPEND_INFO("%s", tmpbuf);
		}
		APPEND_INFO("\n");
		break;
	default:
		break;
	}

	// stat affects
	found = FALSE;
	for (i = 0; i < MAX_OBJ_AFFECT; i++)
	{
		if (obj->affected[i].location != APPLY_NONE && obj->affected[i].modifier != 0)
		{
			if (!found)
			{
				APPEND_INFO("Affects:\n");
				found = TRUE;
			}
			sprinttype(obj->affected[i].location, apply_types, tmpbuf);
			APPEND_INFO("  %s by %+d\n", tmpbuf, obj->affected[i].modifier);
		}
	}

	// item value score
	APPEND_INFO("Item value: %d\n", itemvalue(obj));

	return (int)pos;
}

#undef APPEND_INFO

void auction_error(P_char ch)
{
	if (!check_db_active())
	{
		send_to_char("&+WUnfortunately, auctions aren't active right now. Please "
			     "try again later.\r\n",
			     ch);
	}
	else
	{
		send_to_char("&+WAn error occurred processing your auction request. Please "
			     "try again or contact an immortal if the problem persists.\r\n",
			     ch);
		logit(LOG_DEBUG,
		      "auction_error: Database is active but auction operation failed for %s",
		      ch->player.name);
	}
}

// Returns TRUE iff ch is affected by SPELL_NOAUCTION. So much cleaner.
bool check_no_auction(P_char ch)
{
	if (!affected_by_spell(ch, SPELL_NOAUCTION))
		return FALSE;
	// Gods can circumvent !auction flag.
	if (IS_TRUSTED(ch))
		return FALSE;

	send_to_char("&+RAuction House access has been temporarily disabled since you "
		     "have recently &+Yremoved&+R a piece of worn equipment. Please try "
		     "again in a little while.\r\n",
		     ch);
	return TRUE;
}

void new_ah_call(P_char ch, char *arguments, int cmd)
{
	if (cmd != CMD_AUCTION || !IS_ALIVE(ch) || IS_NPC(ch))
		return;

	if (IS_FIGHTING(ch))
	{
		send_to_char("&+yYou're too busy fighting for your life to participate "
			     "in an auction!&n\r\n",
			     ch);
		return;
	}

	/* Some auction commands not disabled via SPELL_NOAUCTION.
	  if( check_no_auction( ch ) )
	    return;
	*/

	if (!check_db_active())
	{
		auction_error(ch);
		return;
	}

	char command[MAX_STRING_LENGTH];
	char args[MAX_STRING_LENGTH];

	half_chop(arguments, command, args);

	bool success = false;

	if (isname(command, "offer o"))
	{
		if (check_no_auction(ch))
			return;
		success = auction_offer(ch, args);
	}
	else if (isname(command, "list l"))
		success = auction_list(ch, args);
	else if (isname(command, "info i"))
		success = auction_info(ch, args);
	else if (isname(command, "bid b"))
	{
		if (check_no_auction(ch))
			return;
		success = auction_bid(ch, args);
	}
	else if (isname(command, "pickup p"))
		success = auction_pickup(ch, args);
	else if (isname(command, "resort"))
		success = auction_resort(ch, args);
	else if (isname(command, "remove r"))
		success = auction_remove(ch, args);
	else
		success = auction_help(ch, arguments);

	if (!success)
		auction_error(ch);
}

int auction_house_room_proc(int /*room_num*/, P_char ch, int cmd, char *arguments)
{
	if (cmd != CMD_AUCTION)
		return FALSE;

	if (!IS_PC(ch))
		return FALSE;

	if (IS_FIGHTING(ch))
	{
		send_to_char("&+yYou're too busy fighting for your life to participate "
			     "in an auction!&n\r\n",
			     ch);
		return TRUE;
	}

	if (!check_db_active())
	{
		auction_error(ch);
		return TRUE;
	}

	char command[MAX_STRING_LENGTH];
	char args[MAX_STRING_LENGTH];

	half_chop(arguments, command, args);

	bool success = false;

	if (isname(command, "offer o"))
		success = auction_offer(ch, args);
	else if (isname(command, "list l"))
		success = auction_list(ch, args);
	else if (isname(command, "info i"))
		success = auction_info(ch, args);
	else if (isname(command, "bid b"))
		success = auction_bid(ch, args);
	else if (isname(command, "pickup p"))
		success = auction_pickup(ch, args);
	else if (isname(command, "resort"))
		success = auction_resort(ch, args);
	else if (isname(command, "remove r"))
		success = auction_remove(ch, args);
	else
		success = auction_help(ch, arguments);

	if (!success)
		auction_error(ch);

	return TRUE;
}

// syntax: auction resort
bool auction_resort(P_char ch, char *args)
{
	if (!IS_TRUSTED(ch))
		return auction_help(ch, args);

	if (!sorter)
	{
		send_to_char("Sorter not initialized.\r\n", ch);
		return TRUE;
	}

	// Read on the writer; the new keywords are queued back there.
	return sql_read_for(
		ch, "SELECT id, obj_short, obj_blob_str FROM auctions",
		[](P_char viewer, const sql_rows &rows)
		{
			if (rows.empty())
			{
				send_to_char("No auctions to resort!\r\n", viewer);
				return;
			}
			std::vector<std::string> updates;
			int count = 0;
			for (const sql_row &row : rows)
			{
				P_obj tmp_obj =
					row[2] ? read_one_object(const_cast<char *>(row[2])) :
						 nullptr;
				if (!tmp_obj)
					continue;

				string keywords = sorter->getSortFlagsString(tmp_obj);
				snprintf(buff, MAX_STRING_LENGTH, "%s: %s\r\n",
					 row[1] ? row[1] : "", keywords.c_str());
				send_to_char(buff, viewer);

				if (keywords.length() > 0)
					updates.push_back(sql_format(
						"UPDATE auctions SET id_keywords = '%s' WHERE id = '%d'",
						keywords.c_str(), atoi(row[0])));

				extract_obj(tmp_obj);
				count++;
			}
			if (!updates.empty())
				sql_queue_statements(std::move(updates));

			snprintf(buff, MAX_STRING_LENGTH, "&+W%d items resorted.", count);
			send_to_char(buff, viewer);
		});
}

namespace
{
bool auction_copy_text(char *destination, size_t capacity, const char *source)
{
	if (!destination || !capacity || !source || strlen(source) >= capacity)
		return false;
	memcpy(destination, source, strlen(source) + 1);
	return true;
}

bool auction_parse_platinum(const char *text, int64_t *value)
{
	if (!text || !*text || !value)
		return false;
	char *end = nullptr;
	errno = 0;
	const long long platinum = strtoll(text, &end, 10);
	if (errno || !end || *end || platinum < 0 || platinum > INT_MAX / 1000)
		return false;
	*value = platinum * 1000;
	return true;
}

bool auction_fill_actor(P_char ch, auction_command_payload *payload)
{
	if (!ch || IS_NPC(ch) || !payload || !ch->only.pc)
		return false;
	const char *account = get_account_name_safe(ch);
	if (!account || !strcmp(account, "Unknown") ||
	    !auction_copy_text(payload->account_name.data(), payload->account_name.size(),
			       account) ||
	    !auction_copy_text(payload->actor_name.data(), payload->actor_name.size(),
			       GET_NAME(ch)))
		return false;
	payload->actor_pid = static_cast<uint32_t>(GET_PID(ch));
	payload->racewar = static_cast<uint8_t>(GET_RACEWAR(ch));
	payload->closing_fee_basis_points = static_cast<uint32_t>(
		std::max(0.0f, std::min(1.0f, AUCTION_CLOSING_PCT_FEE)) * 10000.0f);
	payload->bid_extension_seconds = static_cast<uint32_t>(std::max(0, BID_TIME_EXTENSION));
	return true;
}

void auction_list_completed(P_char ch, bool committed, const auction_command_result &result,
			    unsigned int, const auction_command_payload &payload)
{
	if (!ch)
		return;
	if (!committed)
	{
		send_to_char("The auction was not listed; your item and money are unchanged.\r\n",
			     ch);
		return;
	}
	// The auction took the listed items out of the inventory at submit.
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS |
							  PLAYER_COMPONENT_EQUIPMENT |
							  PLAYER_COMPONENT_INVENTORY);
	send_to_char_f(ch, "&+W%s is now listed as auction %u.&n\r\n", payload.object_short.data(),
		       result.auction_id);
}

void auction_bid_completed(P_char ch, bool committed, const auction_command_result &result,
			   unsigned int, const auction_command_payload &)
{
	if (!ch)
		return;
	if (!committed)
	{
		send_to_char("Your bid did not commit; your money is unchanged.\r\n", ch);
		return;
	}
	send_to_char_f(ch, "&+WYour bid of &n%s&+W on auction %u committed.&n\r\n",
		       coin_stringv(static_cast<int>(result.final_price)), result.auction_id);
}

void auction_finalize_completed(P_char, bool, const auction_command_result &, unsigned int,
				const auction_command_payload &)
{
}

void auction_remove_completed(P_char ch, bool committed, const auction_command_result &result,
			      unsigned int, const auction_command_payload &)
{
	if (!ch)
		return;
	if (!committed)
		send_to_char("That auction could not be removed.\r\n", ch);
	else
	{
		send_to_char_f(ch, "&+WAuction %u removed.&n\r\n", result.auction_id);
		logit(LOG_WIZ, "Auction [%u] removed by %s", result.auction_id, GET_NAME(ch));
	}
}

void auction_money_claim_completed(P_char ch, bool committed, const auction_command_result &result,
				   unsigned int, const auction_command_payload &)
{
	if (!ch)
		return;
	if (!committed)
		send_to_char("Your auction money remains available for pickup.\r\n", ch);
	else
		send_to_char_f(ch, "&+WYou pick up &n%s&+W.&n\r\n",
			       coin_stringv(static_cast<int>(result.wallet_value_delta)));
}

void auction_item_claim_completed(P_char ch, bool committed, const auction_command_result &result,
				  unsigned int, const auction_command_payload &payload)
{
	if (!ch)
		return;
	if (!committed)
	{
		send_to_char("Your auction items remain available for pickup.\r\n", ch);
		return;
	}
	for (size_t index = 0; index < result.item_count; ++index)
	{
		P_obj object = read_one_object(const_cast<char *>(
			reinterpret_cast<const char *>(payload.object_blob.data())));
		if (!object)
		{
			persistence_alert(AVATAR, "auction", "player", "unknown", "claim_publish",
					  "deserialize_failed", "auction_id=%u item_uid=%llu",
					  result.auction_id,
					  static_cast<unsigned long long>(result.item_uids[index]));
			continue;
		}
		object->obj_uid = result.item_uids[index];
		obj_to_char(object, ch);
		send_to_char_f(ch, "&+WYou pick up &n%s&+W.&n\r\n", object->short_description);
	}
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS |
							  PLAYER_COMPONENT_EQUIPMENT |
							  PLAYER_COMPONENT_INVENTORY);
}
} // namespace

// Broadcasts a committed auction event and tells the players it concerns, from the
// auction's row.
static void auction_publish_event(const auction_command_result &result,
				  unsigned long long outbox_id, const sql_row &row)
{
	const string seller_name = row[0] ? row[0] : "";
	const string object_short = row[1] ? row[1] : "item";
	const string winner_name = row[2] ? row[2] : "";
	const int end_time = row[3] ? atoi(row[3]) : 0;
	const int current_price = row[4] ? atoi(row[4]) : 0;
	const int buy_price = row[5] ? atoi(row[5]) : 0;
	if (result.event_type == auction_event_type::listed)
		ws_broadcast_auction_new(result.auction_id, seller_name.c_str(),
					 object_short.c_str(), current_price, buy_price, end_time);
	else if (result.event_type == auction_event_type::bid_placed)
		ws_broadcast_auction_bid(result.auction_id, winner_name.c_str(),
					 static_cast<int>(result.final_price),
					 result.previous_bidder_pid, "");
	else
		ws_broadcast_auction_close(
			result.auction_id, winner_name.c_str(), result.winner_pid,
			static_cast<int>(result.final_price),
			result.event_type == auction_event_type::sold	 ? "sold" :
			result.event_type == auction_event_type::removed ? "removed" :
									   "expired",
			result.seller_pid, seller_name.c_str());
	char message[MAX_STRING_LENGTH];
	if (result.event_type == auction_event_type::bid_placed && result.previous_bidder_pid &&
	    result.previous_bidder_pid != result.winner_pid)
	{
		snprintf(
			message, sizeof(message),
			"&+WA voice says in your mind, 'You were outbid in auction [%u] for %s, and your bid money is available for pickup.'\r\n",
			result.auction_id, object_short.c_str());
		if (!send_to_pid(message, result.previous_bidder_pid))
			send_to_pid_offline(message, result.previous_bidder_pid);
	}
	else if (result.event_type == auction_event_type::sold)
	{
		snprintf(message, sizeof(message),
			 "&+WAuction [%u] for %s sold; your proceeds are available for pickup.\r\n",
			 result.auction_id, object_short.c_str());
		if (!send_to_pid(message, result.seller_pid))
			send_to_pid_offline(message, result.seller_pid);
		snprintf(message, sizeof(message),
			 "&+WYou won auction [%u] for %s; the item is available for pickup.\r\n",
			 result.auction_id, object_short.c_str());
		if (!send_to_pid(message, result.winner_pid))
			send_to_pid_offline(message, result.winner_pid);
	}
	else if (result.event_type == auction_event_type::expired ||
		 result.event_type == auction_event_type::removed)
	{
		snprintf(message, sizeof(message),
			 "&+WAuction [%u] for %s closed; the item is available for pickup.\r\n",
			 result.auction_id, object_short.c_str());
		if (!send_to_pid(message, result.seller_pid))
			send_to_pid_offline(message, result.seller_pid);
		if (result.event_type == auction_event_type::removed && result.winner_pid)
		{
			snprintf(message, sizeof(message),
				 "&+WAuction [%u] for %s was removed; your bid money is available "
				 "for pickup.\r\n",
				 result.auction_id, object_short.c_str());
			if (!send_to_pid(message, result.winner_pid))
				send_to_pid_offline(message, result.winner_pid);
		}
	}
	logit(LOG_DEBUG, "Published auction outbox %llu for auction %u", outbox_id,
	      result.auction_id);
}

// The auction's row is read on the writer, behind the command that committed the event,
// and the event is published on a later pulse.
bool auction_publish_committed_event(const auction_command_result &result,
				     unsigned long long outbox_id)
{
	if (result.event_type == auction_event_type::money_claimed ||
	    result.event_type == auction_event_type::item_claimed)
		return true;
	if (!result.auction_id)
		return false;
	return sql_read(
		sql_format("SELECT seller_name,obj_short,winning_bidder_name,"
			   "UNIX_TIMESTAMP(end_time),cur_price,buy_price FROM auctions "
			   "WHERE id=%u LIMIT 1",
			   result.auction_id),
		[result, outbox_id](bool ok, const sql_rows &rows)
		{
			if (ok && !rows.empty())
				auction_publish_event(result, outbox_id, rows.front());
			else
				logit(LOG_DEBUG,
				      "Auction outbox %llu for auction %u was not published: "
				      "the auction could not be read",
				      outbox_id, result.auction_id);
		});
}

// syntax: auction offer item [starting price] [buy it now price]
bool auction_offer(P_char ch, char *args)
{
	char item_name[MAX_STRING_LENGTH], value_text[MAX_STRING_LENGTH];
	half_chop(args, item_name, args);
	P_obj object = get_obj_in_list_vis(ch, item_name, ch->carrying);
	if (!object)
	{
		send_to_char("&+WYou don't seem to have that item!\r\n", ch);
		return true;
	}
	if (IS_ARTIFACT(object) || IS_SET(object->extra_flags, ITEM_NODROP) ||
	    IS_SET(object->extra_flags, ITEM_NORENT) || object->condition < 90 || object->contains)
	{
		send_to_char("&+WYou can't sell that item.\r\n", ch);
		return true;
	}
	int64_t start_price = 0, buy_price = 0;
	half_chop(args, value_text, args);
	if (*value_text && !auction_parse_platinum(value_text, &start_price))
	{
		send_to_char("&+WInvalid starting price.\r\n", ch);
		return true;
	}
	half_chop(args, value_text, args);
	if (*value_text && !auction_parse_platinum(value_text, &buy_price))
	{
		send_to_char("&+WInvalid buy-it-now price.\r\n", ch);
		return true;
	}
	if (buy_price && buy_price < start_price)
	{
		send_to_char("&+WInvalid buy-it-now price.\r\n", ch);
		return true;
	}
	half_chop(args, value_text, args);
	const int days = *value_text ? atoi(value_text) : DEFAULT_AUCTION_LENGTH / 86400;
	if (days < 1 || days > 7)
	{
		send_to_char("&+WInvalid auction length: please enter 1 to 7 (days).\r\n", ch);
		return true;
	}
	half_chop(args, value_text, args);
	const int quantity = *value_text ? atoi(value_text) : 1;
	if (quantity < 1 || quantity > static_cast<int>(AUCTION_COMMAND_MAX_ITEMS))
	{
		send_to_char("&+WInvalid auction quantity: please enter 1 to 9 (items).\r\n", ch);
		return true;
	}
	auction_command_payload payload = {};
	payload.action = auction_action::list;
	if (!auction_fill_actor(ch, &payload))
		return false;
	payload.start_price = start_price;
	payload.buy_price = buy_price;
	payload.listing_fee = AUCTION_LISTING_FEE +
			      static_cast<int64_t>(start_price * AUCTION_START_PRICE_PCT_FEE);
	if (GET_MONEY(ch) < payload.listing_fee)
	{
		send_to_char("&+WYou don't have enough money to list the item.\r\n", ch);
		return true;
	}
	payload.end_time = static_cast<uint64_t>(time(nullptr) + days * 86400);
	P_obj current = object;
	for (int index = 0; index < quantity; ++index)
	{
		if (!current || current->R_num != object->R_num)
		{
			send_to_char("You do not have enough of that item.\r\n", ch);
			return true;
		}
		// The seller holds it in memory; the listing claims it from whatever the
		// ownership record still says.
		if (!current->obj_uid)
		{
			send_to_char("&+WYou can't sell that item.\r\n", ch);
			return true;
		}
		payload.items[index] = { current->obj_uid, 0,
					 static_cast<int32_t>(OBJ_VNUM(current)) };
		current = current->next_content;
	}
	payload.item_count = quantity;
	char serialized[AUCTION_BLOB_MAX_BYTES] = {};
	const int serialized_size = write_one_object(object, serialized);
	if (serialized_size <= 0 || serialized_size >= static_cast<int>(payload.object_blob.size()))
		return false;
	memcpy(payload.object_blob.data(), serialized, serialized_size + 1);
	payload.object_blob_size = serialized_size + 1;
	if (!auction_copy_text(payload.object_short.data(), payload.object_short.size(),
			       object->short_description))
		return false;
	const string keywords = sorter ? sorter->getSortFlagsString(object) : "";
	if (!auction_copy_text(payload.id_keywords.data(), payload.id_keywords.size(),
			       keywords.c_str()))
		return false;
	build_obj_info_text(object, payload.object_info.data(), payload.object_info.size());
	if (!auction_transaction_submit(ch, payload, auction_list_completed))
	{
		send_to_char("The auction house is busy; nothing was changed.\r\n", ch);
		return true;
	}
	send_to_char("Your auction listing is being committed.\r\n", ch);
	return true;
}

// One line of `auction list`.
static void auction_list_row(P_char ch, const sql_row &row)
{
	const char *auction_id = row[0];
	long secs_remaining = atol(row[2]);
	int cur_price = atoi(row[3]);
	int buy_price = atoi(row[4]);
	const char *obj_short = row[5];
	int obj_vnum = atoi(row[6]);
	int winning_bidder_pid = row[7] ? atoi(row[7]) : 0;
	int seller_pid = atoi(row[9]);
	int quantity = atoi(row[10]);

	// if( cur_price < 1 ) cur_price = 1;
	if (cur_price < 1000)
		cur_price = 1000; // change to copper

	char buf[128];
	snprintf(buf, 128, "&+W%dp", (int)(cur_price / 1000));
	string cur_price_str(buf);

	snprintf(buf, 128, "&+W%dp", (int)(buy_price / 1000));
	string buy_price_str(buf);

	char mine_flag[] = " ";
	if (GET_PID(ch) == seller_pid || GET_PID(ch) == winning_bidder_pid)
		strcpy(mine_flag, "*");

	// Only display Buy it now price if there is one.
	if (buy_price > 0)
	{
		// Display vnum for gods.
		if (IS_TRUSTED(ch))
			snprintf(
				buff, MAX_STRING_LENGTH,
				"&+W%s)&+W%s&n[&+B%6d&n] %d &n%s&n [%s&n] &+WBid: &n%s&+W Buy: &n%s\r\n",
				auction_id, mine_flag, obj_vnum, quantity,
				pad_ansi(obj_short, 45, TRUE).c_str(),
				format_time(secs_remaining).c_str(),
				pad_ansi(cur_price_str.c_str(), 7).c_str(),
				pad_ansi(buy_price_str.c_str(), 7).c_str());
		else
			snprintf(buff, MAX_STRING_LENGTH,
				 "&+W%s)&+W%s&n %d %s&n [%s&n] &+WBid: &n%s&+W Buy: &n%s\r\n",
				 auction_id, mine_flag, quantity,
				 pad_ansi(obj_short, 45, TRUE).c_str(),
				 format_time(secs_remaining).c_str(),
				 pad_ansi(cur_price_str.c_str(), 6).c_str(),
				 pad_ansi(buy_price_str.c_str(), 6).c_str());
	}
	else
	{
		if (IS_TRUSTED(ch))
			snprintf(buff, MAX_STRING_LENGTH,
				 "&+W%s)&+W%s&n[&+B%6d&n] %d &n%s&n [%s&n] &+WBid: &n%s&+W\r\n",
				 auction_id, mine_flag, obj_vnum, quantity,
				 pad_ansi(obj_short, 45, TRUE).c_str(),
				 format_time(secs_remaining).c_str(),
				 pad_ansi(cur_price_str.c_str(), 6).c_str());
		else
			snprintf(buff, MAX_STRING_LENGTH,
				 "&+W%s)&+W%s&n %d %s&n [%s&n] &+WBid: &n%s&+W\r\n", auction_id,
				 mine_flag, quantity, pad_ansi(obj_short, 45, TRUE).c_str(),
				 format_time(secs_remaining).c_str(),
				 pad_ansi(cur_price_str.c_str(), 6).c_str());
	}

	send_to_char(buff, ch);
}

// syntax: auction list
bool auction_list(P_char ch, char *args)
{
	char list_arg[MAX_STRING_LENGTH];
	char where_str[MAX_STRING_LENGTH];
	int i, count;
	// Shown with the rows, which come on a later pulse.
	string heading;

	half_chop(args, list_arg, args);
	*where_str = '\0';

	if (isname(list_arg, "all a") || strlen(list_arg) < 1)
		heading = "&+WAuctions closing soon:\r\n";
	else if (isname(list_arg, "player p"))
	{
		half_chop(args, list_arg, args);

		if (!list_arg[0])
		{
			send_to_char("&+WPlease enter the name of a player.\r\n", ch);
			return TRUE;
		}

		list_arg[0] = toupper(list_arg[0]);

		snprintf(buff, MAX_STRING_LENGTH, "&+WAuctions by &n%.100s&+W:\r\n", list_arg);
		heading = buff;

		mysql_real_escape_string(DB, buff, list_arg, strlen(list_arg));

		snprintf(where_str, MAX_STRING_LENGTH, " and seller_name like '%.100s'", buff);
	}
	else if (isname(list_arg, "sort s"))
	{
		vector<string> list_args;

		if (!*args)
		{
			count = snprintf(buff, MAX_STRING_LENGTH, "&+WValid keywords: &+Y%s",
					 sorter->getKeyword(0).c_str());
			for (i = 1; i < sorter->getSize(); i++)
			{
				count += snprintf(buff + count, MAX_STRING_LENGTH, ", %s",
						  sorter->getKeyword(i).c_str());
			}
			snprintf(buff + count, MAX_STRING_LENGTH, ".\n\r");
			send_to_char(buff, ch);
			return TRUE;
		}

		while (strlen(args) > 0)
		{
			half_chop(args, list_arg, args);
			list_args.push_back(string(list_arg));

			if (!sorter->isKeyword(list_arg))
			{
				snprintf(buff, MAX_STRING_LENGTH,
					 "&+W'&+Y%.100s&+W' is an invalid keyword!\r\n", list_arg);
				send_to_char(buff, ch);
				return TRUE;
			}

			snprintf(buff, MAX_STRING_LENGTH, "&+WAuctions for items &+y%s&+W:&n\n",
				 sorter->getDescString(list_arg).c_str());
			heading += buff;

			mysql_real_escape_string(DB, buff, list_arg, strlen(list_arg));
			list_args.back() = string(buff);
		}

		for (size_t list_index = 0; list_index < list_args.size(); list_index++)
		{
			snprintf(buff, MAX_STRING_LENGTH, " and id_keywords like '%% %s,%%'",
				 list_args[list_index].c_str());
			strcat(where_str, buff);
		}

		heading += "\r\n";
	}
	else
	{
		send_to_char("&+WAuction list syntax:\r\nauction list - show all auctions\n\r"
			     "auction list sort <keyword list> - show only auctions for items"
			     " with the specified attributes (like lockers)\n\r"
			     "auction list player <playername> - show all auctions by a player\n\r",
			     ch);
		count = snprintf(buff, MAX_STRING_LENGTH, "&+WValid keywords: &+Y%s",
				 sorter->getKeyword(0).c_str());
		for (i = 1; i < sorter->getSize(); i++)
		{
			count += snprintf(buff + count, MAX_STRING_LENGTH, ", %s",
					  sorter->getKeyword(i).c_str());
		}
		snprintf(buff + count, MAX_STRING_LENGTH, ".\n\r");
		send_to_char(buff, ch);
		return TRUE;
	}

	const bool filtered = *list_arg;
	return sql_read_for(
		ch,
		sql_format(
			"SELECT id, seller_name, UNIX_TIMESTAMP(end_time) - UNIX_TIMESTAMP() as secs_remaining, cur_price, buy_price, obj_short, obj_vnum, winning_bidder_pid, winning_bidder_name, seller_pid, "
			"quantity from auctions where status = %d %s order by secs_remaining asc",
			AUCTION_STATUS_OPEN, where_str),
		[heading, filtered](P_char viewer, const sql_rows &rows)
		{
			send_to_char(heading.c_str(), viewer);
			if (rows.empty())
				send_to_char(filtered ? "&+yNo auctions found!\r\n" :
							"&+yNo auctions to list!\r\n",
					     viewer);
			for (const sql_row &row : rows)
				auction_list_row(viewer, row);
		});
}

// The answer to `auction info`, from the auction's row.
static void auction_info_show(P_char ch, int auction_id, const sql_row &row)
{
	string seller_name(row[0] ? row[0] : "");
	long secs_remaining = atol(row[1]);
	int cur_price = atoi(row[2]);
	int buy_price = atoi(row[3]);
	string obj_short(row[4] ? row[4] : "");
	int obj_vnum = atoi(row[5]);
	int winning_bidder_pid = row[6] ? atoi(row[6]) : 0;
	string winning_bidder_name(row[7] ? row[7] : "");
	const char *obj_str = row[8];
	int quantity = atoi(row[9]);

	string cur_price_str(coin_stringv(cur_price));
	string buy_price_str(coin_stringv(buy_price));

	P_obj tmp_obj = obj_str ? read_one_object(const_cast<char *>(obj_str)) : nullptr;

	if (!tmp_obj)
	{
		logit(LOG_DEBUG, "auction_info(): problem retrieving item in auction [%d].\r\n",
		      auction_id);
		auction_error(ch);
		return;
	}

	snprintf(buff, MAX_STRING_LENGTH, "&+WAuction &+W%d\r\n", auction_id);
	send_to_char(buff, ch);

	snprintf(buff, MAX_STRING_LENGTH, "&+WSeller: &n%s\r\n", seller_name.c_str());
	send_to_char(buff, ch);

	snprintf(buff, MAX_STRING_LENGTH, "&+WTime left: &n%s\r\n",
		 format_time(secs_remaining).c_str());
	send_to_char(buff, ch);

	if (winning_bidder_pid == 0)
	{
		snprintf(buff, MAX_STRING_LENGTH, "&+WNo bids received. Starting bid: &n%s\r\n",
			 cur_price_str.c_str());
		send_to_char(buff, ch);
	}
	else
	{
		snprintf(buff, MAX_STRING_LENGTH, "&+WHigh bid: &n%s&+W by &n%s\r\n",
			 cur_price_str.c_str(), winning_bidder_name.c_str());
		send_to_char(buff, ch);
	}

	if (buy_price > 0)
	{
		snprintf(buff, MAX_STRING_LENGTH, "&+WBuy-it-now price: &n%s\r\n",
			 buy_price_str.c_str());
		send_to_char(buff, ch);
	}

	snprintf(buff, MAX_STRING_LENGTH, "&+WQuantity:&n %d\r\n", quantity);
	send_to_char(buff, ch);

	send_to_char("\r\n", ch);

	if (IS_TRUSTED(ch))
	{
		snprintf(buff, MAX_STRING_LENGTH, "[&+B%d&n]\r\n", obj_vnum);
		send_to_char(buff, ch);
	}

	spell_identify(60, ch, NULL, 0, 0, tmp_obj);

	if (can_char_use_item(ch, tmp_obj))
	{
		send_to_char("&+WYour race and class is permitted to use this item.\r\n", ch);
	}
	else
	{
		send_to_char("&=LRYOU ARE UNABLE TO USE THIS ITEM.\r\n", ch);
	}

	extract_obj(tmp_obj);
}

// syntax: auction info <auction id>
bool auction_info(P_char ch, char *args)
{
	char arg[MAX_STRING_LENGTH];

	half_chop(args, arg, args);

	int auction_id = atoi(arg);

	return sql_read_for(
		ch,
		sql_format(
			"SELECT seller_name, UNIX_TIMESTAMP(end_time) - UNIX_TIMESTAMP() as secs_remaining, cur_price, buy_price, obj_short, obj_vnum, winning_bidder_pid, winning_bidder_name, obj_blob_str, "
			"quantity FROM auctions WHERE id = '%d' and status = %d",
			auction_id, AUCTION_STATUS_OPEN),
		[auction_id](P_char viewer, const sql_rows &rows)
		{
			if (rows.empty())
			{
				send_to_char("&+WThere is no auction with that id!\r\n", viewer);
				return;
			}
			auction_info_show(viewer, auction_id, rows.front());
		});
}

// syntax: auction remove <auction id>
bool auction_remove(P_char ch, char *args)
{
	if (!IS_TRUSTED(ch))
		return auction_help(ch, "");
	char id_text[MAX_STRING_LENGTH];
	half_chop(args, id_text, args);
	if (!strcmp(id_text, "all"))
	{
		send_to_char("Remove auctions one at a time so each removal is acknowledged.\r\n",
			     ch);
		return true;
	}
	char *end = nullptr;
	errno = 0;
	const unsigned long parsed = strtoul(id_text, &end, 10);
	if (errno || !end || *end || !parsed || parsed > UINT_MAX)
	{
		send_to_char("&+WThere is no auction with that id!\r\n", ch);
		return true;
	}
	auction_command_payload payload = {};
	payload.action = auction_action::remove;
	payload.auction_id = static_cast<uint32_t>(parsed);
	if (!auction_fill_actor(ch, &payload))
		return false;
	if (!auction_transaction_submit(ch, payload, auction_remove_completed))
		send_to_char("The auction house is busy; nothing was changed.\r\n", ch);
	else
		send_to_char("The auction removal is being committed.\r\n", ch);
	return true;
}

// syntax: auction bid <auction id> <bid value in plat>
bool auction_bid(P_char ch, char *args)
{
	char id_text[MAX_STRING_LENGTH], bid_text[MAX_STRING_LENGTH];
	half_chop(args, id_text, args);
	half_chop(args, bid_text, args);
	char *end = nullptr;
	errno = 0;
	const unsigned long parsed = strtoul(id_text, &end, 10);
	int64_t bid = 0;
	if (errno || !end || *end || !parsed || parsed > UINT_MAX ||
	    !auction_parse_platinum(bid_text, &bid) || bid <= 0)
	{
		send_to_char("&+WUsage: auction bid <auction id> <positive value in plat>.&n\r\n",
			     ch);
		return true;
	}
	auction_command_payload payload = {};
	payload.action = auction_action::bid;
	payload.auction_id = static_cast<uint32_t>(parsed);
	payload.value = bid;
	if (!auction_fill_actor(ch, &payload))
		return false;
	// The bid leaves the wallet until the auction settles it.
	if (GET_MONEY(ch) < bid)
	{
		send_to_char_f(ch, "&+WYou don't have enough money!\r\nYou need: &n%s\r\n",
			       coin_stringv(static_cast<int>(bid)));
		return true;
	}
	if (!auction_transaction_submit(ch, payload, auction_bid_completed))
		send_to_char("The auction house is busy; your money is unchanged.\r\n", ch);
	else
		send_to_char("Your bid is being committed.\r\n", ch);
	return true;
}

// Submits the claim for what the writer found waiting for ch: its money first, else the
// items of its oldest auction.
static void auction_pickup_claim(P_char ch, const sql_rows &rows)
{
	if (auction_transaction_player_busy(ch))
	{
		send_to_char("Your previous auction request is still being committed.\r\n", ch);
		return;
	}
	auction_command_payload payload = {};
	if (!auction_fill_actor(ch, &payload))
	{
		auction_error(ch);
		return;
	}
	if (!rows.empty() && rows.front()[0] && !strcmp(rows.front()[0], "money"))
	{
		payload.action = auction_action::claim_money;
		if (!auction_transaction_submit(ch, payload, auction_money_claim_completed))
			send_to_char("The auction house is busy; your money remains staged.\r\n",
				     ch);
		else
			send_to_char("Your auction money pickup is being committed.\r\n", ch);
		return;
	}
	payload.action = auction_action::claim_item;
	for (const sql_row &row : rows)
	{
		if (payload.item_count >= payload.items.size())
			break;
		if (!row[1] || !row[2] || !row[3] || !row[4] || !row[5])
			continue;
		if (!payload.auction_id)
		{
			const std::string &blob = *row.fields[5];
			if (blob.size() >= payload.object_blob.size())
			{
				auction_error(ch);
				return;
			}
			payload.auction_id = static_cast<uint32_t>(strtoul(row[1], nullptr, 10));
			memcpy(payload.object_blob.data(), blob.data(), blob.size());
			payload.object_blob_size = blob.size();
		}
		payload.items[payload.item_count++] = { strtoull(row[2], nullptr, 10),
							strtoull(row[3], nullptr, 10),
							atoi(row[4]) };
	}
	if (!payload.item_count)
	{
		send_to_char("&+WYou have no items or money to pickup!&n\r\n", ch);
		return;
	}
	if (!auction_transaction_submit(ch, payload, auction_item_claim_completed))
		send_to_char("The auction house is busy; your items remain staged.\r\n", ch);
	else
		send_to_char("Your auction item pickup is being committed.\r\n", ch);
}

// syntax: auction pickup
bool auction_pickup(P_char ch, char *args)
{
	if (args && *args)
	{
		send_to_char(
			"Auction pickup no longer accepts an id; committed claims are authoritative.\r\n",
			ch);
		return true;
	}
	if (auction_transaction_player_busy(ch))
	{
		send_to_char("Your previous auction request is still being committed.\r\n", ch);
		return true;
	}
	// What waits for ch is read on the writer: its money, or else its oldest auction's items.
	const int pid = GET_PID(ch);
	return sql_read_work_for(
		ch,
		[pid](MYSQL *connection, sql_rows *rows) -> unsigned int
		{
			if (const unsigned int error_code = sql_select(
				    connection,
				    sql_format("SELECT 'money' FROM auction_money_pickups "
					       "WHERE pid=%d AND money>0 LIMIT 1",
					       pid),
				    rows))
				return error_code;
			if (!rows->empty())
				return 0;
			return sql_select(
				connection,
				sql_format(
					"SELECT 'item',auction_id,item_uid,item_revision,vnum,obj_blob FROM "
					"auction_item_custody WHERE claim_pid=%d AND claimed_at IS NULL AND "
					"auction_id=(SELECT claim_auction FROM (SELECT MIN(auction_id) AS "
					"claim_auction FROM auction_item_custody WHERE claim_pid=%d AND "
					"claimed_at IS NULL) pending) ORDER BY slot LIMIT %d",
					pid, pid, static_cast<int>(AUCTION_COMMAND_MAX_ITEMS)),
				rows);
		},
		auction_pickup_claim);
}

bool auction_help(P_char ch, const char * /*arg*/)
{
	send_to_char(
		"&+WAuction syntax:\r\n- auction list [help]\r\n"
		"- auction offer <item from your inventory> [starting price in plat] [buy-it-now price in plat] [length of auction in days] [quantity]\r\n"
		"- auction bid <auction id> <value in plat>\r\n"
		"- auction info <auction id>\r\n- auction pickup\r\n",
		ch);
	if (IS_TRUSTED(ch))
	{
		send_to_char("- auction resort\r\n- auction remove\r\n", ch);
	}
	return TRUE;
}

bool finalize_auction(int auction_id, P_char /*to_ch*/)
{
	if (auction_id <= 0)
		return false;
	auction_command_payload payload = {};
	payload.action = auction_action::finalize;
	payload.auction_id = static_cast<uint32_t>(auction_id);
	payload.closing_fee_basis_points = static_cast<uint32_t>(
		std::max(0.0f, std::min(1.0f, AUCTION_CLOSING_PCT_FEE)) * 10000.0f);
	return auction_transaction_submit_background(payload, auction_finalize_completed);
}

// Queued on the writer, behind whatever was queued before it.
bool insert_money_pickup(int pid, int money)
{
	if (!sql_queue(
		    "INSERT INTO auction_money_pickups (pid, money) VALUES ('%d', '%d') ON DUPLICATE KEY UPDATE money = money + VALUES(money)",
		    pid, money))
		return FALSE;

	logit(LOG_STATUS, "PID %d picked up %d", pid, money);

	return TRUE;
}

string format_time(long seconds)
{
	char tmp[128];

	if (seconds < 0)
		seconds = 0;

	if (seconds < 60)
	{
		snprintf(tmp, 128, "&+R<1m&n");
	}
	else if (seconds < (60 * 60))
	{
		snprintf(tmp, 128, "&+R%ldm&n", (seconds / 60) % 60);
	}
	else if (seconds < (6 * 60 * 60))
	{
		snprintf(tmp, 128, "&+Y%ldh %ldm&n", (seconds / 3600) % (60 * 60),
			 (seconds / 60) % 60);
	}
	else
	{
		snprintf(tmp, 128, "&+W%ldh&n", (seconds / 3600) % (60 * 60));
	}

	return string(tmp);
}

EqSort::EqSort()
{
	flags.push_back(new EqSlotFlag("horns", "worn on horns", ITEM_WEAR_HORN));
	flags.push_back(new EqSlotFlag("nose", "worn on nose", ITEM_WEAR_NOSE));
	flags.push_back(new EqSlotFlag("tail", "worn on tail", ITEM_WEAR_TAIL));
	flags.push_back(new EqSlotFlag("horse", "worn on a horses body", ITEM_HORSE_BODY));
	flags.push_back(new EqSlotFlag("back", "worn on a spider body", ITEM_SPIDER_BODY));
	flags.push_back(new EqSlotFlag("back", "worn on back", ITEM_WEAR_BACK));
	flags.push_back(new EqSlotFlag("badge", "worn as a badge", ITEM_GUILD_INSIGNIA));
	flags.push_back(new EqSlotFlag("quiver", "worn as a quiver", ITEM_WEAR_QUIVER));
	flags.push_back(new EqSlotFlag("ear", "worn on or in ear", ITEM_WEAR_EARRING));
	flags.push_back(new EqSlotFlag("face", "worn on face", ITEM_WEAR_FACE));
	flags.push_back(new EqSlotFlag("eyes", "worn on or over eyes", ITEM_WEAR_EYES));
	flags.push_back(new EqSlotFlag("wield", "used as a weapon or wielded", ITEM_WIELD));
	flags.push_back(new EqSlotFlag("wrist", "worn around wrist", ITEM_WEAR_WRIST));
	flags.push_back(new EqSlotFlag("waist", "worn about waist", ITEM_WEAR_WAIST));
	flags.push_back(new EqSlotFlag("about", "worn about body", ITEM_WEAR_ABOUT));
	flags.push_back(new EqSlotFlag("shield", "worn as a shield", ITEM_WEAR_SHIELD));
	flags.push_back(new EqSlotFlag("arms", "worn on arms", ITEM_WEAR_ARMS));
	flags.push_back(new EqSlotFlag("hands", "worn on hands", ITEM_WEAR_HANDS));
	flags.push_back(new EqSlotFlag("feet", "worn on feet", ITEM_WEAR_FEET));
	flags.push_back(new EqSlotFlag("legs", "worn on legs", ITEM_WEAR_LEGS));
	flags.push_back(new EqSlotFlag("head", "worn on head", ITEM_WEAR_HEAD));
	flags.push_back(new EqSlotFlag("body", "worn on body", ITEM_WEAR_BODY));
	flags.push_back(new EqSlotFlag("neck", "worn around neck", ITEM_WEAR_NECK));
	flags.push_back(new EqSlotFlag("finger", "worn on finger", ITEM_WEAR_FINGER));

	flags.push_back(new EqClassFlag("warrior", "usable by a warrior", CLASS_WARRIOR));
	flags.push_back(new EqClassFlag("ranger", "usable by a ranger", CLASS_RANGER));
	flags.push_back(new EqClassFlag("psionicist", "usable by a psionicist", CLASS_PSIONICIST));
	flags.push_back(new EqClassFlag("paladin", "usable by a paladin", CLASS_PALADIN));
	flags.push_back(
		new EqClassFlag("antipaladin", "usable by an antipaladin", CLASS_ANTIPALADIN));
	flags.push_back(new EqClassFlag("cleric", "usable by a cleric", CLASS_CLERIC));
	flags.push_back(new EqClassFlag("monk", "usable by a monk", CLASS_MONK));
	flags.push_back(new EqClassFlag("druid", "usable by a druid", CLASS_DRUID));
	flags.push_back(new EqClassFlag("shaman", "usable by a shaman", CLASS_SHAMAN));
	flags.push_back(new EqClassFlag("sorcerer", "usable by a sorcerer", CLASS_SORCERER));
	flags.push_back(
		new EqClassFlag("necromancer", "usable by a necromancer", CLASS_NECROMANCER));
	flags.push_back(new EqClassFlag("conjurer", "usable by a conjurer", CLASS_CONJURER));
	flags.push_back(new EqClassFlag("assassin", "usable by an assassin", CLASS_ASSASSIN));
	flags.push_back(new EqClassFlag("mercenary", "usable by a mercenary", CLASS_MERCENARY));
	flags.push_back(new EqClassFlag("bard", "usable by a bard", CLASS_BARD));
	flags.push_back(new EqClassFlag("thief", "usable by a thief", CLASS_THIEF));
	flags.push_back(new EqClassFlag("alchemist", "usable by an alchemist", CLASS_ALCHEMIST));
	flags.push_back(new EqClassFlag("berserker", "usable by a berserker", CLASS_BERSERKER));
	flags.push_back(new EqClassFlag("reaver", "usable by a reaver", CLASS_REAVER));
	flags.push_back(
		new EqClassFlag("illusionist", "usable by an illusionist", CLASS_ILLUSIONIST));
	flags.push_back(new EqClassFlag("dreadlord", "usable by a dreadlord", CLASS_DREADLORD));
	flags.push_back(
		new EqClassFlag("ethermancer", "usable by an ethermancer", CLASS_ETHERMANCER));

	flags.push_back(new EqTypeFlag("totems", "used as totems", ITEM_TOTEM));
	flags.push_back(
		new EqTypeFlag("instruments", "playable as bard instruments", ITEM_INSTRUMENT));
	flags.push_back(new EqTypeFlag("potions", "quaffable or used as potions", ITEM_POTION));
	flags.push_back(new EqTypeFlag("spellbooks", "used as spellbooks", ITEM_SPELLBOOK));
	flags.push_back(new EqTypeFlag("scrolls", "used as scrolls", ITEM_SCROLL));
	flags.push_back(new EqTypeFlag("containers", "that are containers", ITEM_CONTAINER));

	flags.push_back(new EqApplyFlag("hitpoints", "that affect hitpoints", APPLY_HIT));
	flags.push_back(new EqApplyFlag("mana", "that affect mana", APPLY_MANA));
	flags.push_back(new EqApplyFlag("moves", "that affect moves", APPLY_MOVE));
	flags.push_back(new EqApplyFlag("hitroll", "that affect hitroll", APPLY_HITROLL));
	flags.push_back(new EqApplyFlag("damroll", "that affect damroll", APPLY_DAMROLL));
	flags.push_back(new EqApplyFlag("save_para", "that affect save_para", APPLY_SAVING_PARA));
	flags.push_back(new EqApplyFlag("save_rod", "that affect save_rod", APPLY_SAVING_ROD));
	flags.push_back(new EqApplyFlag("save_fear", "that affect save_fear", APPLY_SAVING_FEAR));
	flags.push_back(
		new EqApplyFlag("save_breath", "that affect save_breath", APPLY_SAVING_BREATH));
	flags.push_back(
		new EqApplyFlag("save_spell", "that affect save_spell", APPLY_SAVING_SPELL));
	flags.push_back(new EqApplyFlag("str", "that affect strength", APPLY_STR));
	flags.push_back(new EqApplyFlag("dex", "that affect dexterity", APPLY_DEX));
	flags.push_back(new EqApplyFlag("int", "that affect intelligence", APPLY_INT));
	flags.push_back(new EqApplyFlag("wis", "that affect wisdom", APPLY_WIS));
	flags.push_back(new EqApplyFlag("con", "that affect constitution", APPLY_CON));
	flags.push_back(new EqApplyFlag("agi", "that affect agility", APPLY_AGI));
	flags.push_back(new EqApplyFlag("pow", "that affect power", APPLY_POW));
	flags.push_back(new EqApplyFlag("cha", "that affect charisma", APPLY_CHA));
	flags.push_back(new EqApplyFlag("luck", "that affect luck", APPLY_LUCK));
	flags.push_back(new EqApplyFlag("karma", "that affect karma", APPLY_KARMA));
	flags.push_back(new EqApplyFlag("str_max", "that affect maximum strength (str_max)",
					APPLY_STR_MAX));
	flags.push_back(new EqApplyFlag("dex_max", "that affect maximum dexterity (dex_max)",
					APPLY_DEX_MAX));
	flags.push_back(new EqApplyFlag("int_max", "that affect maximum intelligence (int_max)",
					APPLY_INT_MAX));
	flags.push_back(
		new EqApplyFlag("wis_max", "that affect maximum wisdom (wis_max)", APPLY_WIS_MAX));
	flags.push_back(new EqApplyFlag("con_max", "that affect maximum constitution (con_max)",
					APPLY_CON_MAX));
	flags.push_back(
		new EqApplyFlag("agi_max", "that affect maximum agility (agi_max)", APPLY_AGI_MAX));
	flags.push_back(
		new EqApplyFlag("pow_max", "that affect maximum power (pow_max)", APPLY_POW_MAX));
	flags.push_back(new EqApplyFlag("cha_max", "that affect maximum charisma (cha_max)",
					APPLY_CHA_MAX));
	flags.push_back(
		new EqApplyFlag("luck_max", "that affect maximum luck (luck_max)", APPLY_LUCK_MAX));
	flags.push_back(new EqApplyFlag("karma_max", "that affect maximum karma (karma_max)",
					APPLY_KARMA_MAX));

	flags.push_back(new EqExtraFlag("glow", "that glow", ITEM_GLOW));
	flags.push_back(new EqExtraFlag("noshow", "that don't show", ITEM_NOSHOW));
	flags.push_back(new EqExtraFlag("buried", "that are buried", ITEM_BURIED));
	flags.push_back(new EqExtraFlag("nosell", "that can't be sold", ITEM_NOSELL));
	flags.push_back(
		new EqExtraFlag("throw2", "that can be thrown from offhand", ITEM_CAN_THROW2));
	flags.push_back(new EqExtraFlag("invisible", "that are invisible", ITEM_INVISIBLE));
	flags.push_back(new EqExtraFlag("norepair", "that can't be repaired", ITEM_NOREPAIR));
	flags.push_back(new EqExtraFlag("cursed", "that are cursed", ITEM_NODROP));
	flags.push_back(new EqExtraFlag("boomerang", "that return after throwing", ITEM_RETURNING));
	flags.push_back(new EqExtraFlag("allowed_races", "that reverse the races can-use list",
					ITEM_ALLOWED_RACES));
	flags.push_back(new EqExtraFlag("allowed_classes", "that reverse the classes can-use list",
					ITEM_ALLOWED_CLASSES));
	flags.push_back(new EqExtraFlag("proclib", "that use the old proc format", ITEM_PROCLIB));
	flags.push_back(new EqExtraFlag("hidden", "that are hidden", ITEM_SECRET));
	flags.push_back(new EqExtraFlag("float", "that float on water", ITEM_FLOAT));
	flags.push_back(
		new EqExtraFlag("noreset", "who knows what it did, now unused", ITEM_NORESET));
	flags.push_back(
		new EqExtraFlag("nolocate", "that block the locate object spell", ITEM_NOLOCATE));
	flags.push_back(
		new EqExtraFlag("noidentify", "that block the identify spell", ITEM_NOIDENTIFY));
	flags.push_back(new EqExtraFlag("nosummon", "that block the summon spell", ITEM_NOSUMMON));
	flags.push_back(new EqExtraFlag("lit", "that illuminate the room when worn", ITEM_LIT));
	flags.push_back(new EqExtraFlag("transient", "that dissolve when dropped", ITEM_TRANSIENT));
	flags.push_back(new EqExtraFlag("nosleep", "that block the sleep spell", ITEM_NOSLEEP));
	flags.push_back(new EqExtraFlag("nocharm", "that block charming spells", ITEM_NOCHARM));
	flags.push_back(
		new EqExtraFlag("twohands", "that require two hands for use", ITEM_TWOHANDS));
	flags.push_back(new EqExtraFlag("norent", "that disappear when renting", ITEM_NORENT));
	flags.push_back(
		new EqExtraFlag("throw1", "that can be thrown from primary hand", ITEM_CAN_THROW1));
	flags.push_back(new EqExtraFlag("humming", "that hum", ITEM_HUM));
	flags.push_back(
		new EqExtraFlag("levitates", "that don't fall when dropped", ITEM_LEVITATES));
	flags.push_back(new EqExtraFlag("ignore", "that skip tauto-weight/cost", ITEM_IGNORE));
	flags.push_back(new EqExtraFlag(
		"artifact", "that are artifacts and should not be auctionable", ITEM_ARTIFACT));
	flags.push_back(new EqExtraFlag("wholebody", "that cover the whole body", ITEM_WHOLE_BODY));
	flags.push_back(new EqExtraFlag("wholehead", "that cover the whole head", ITEM_WHOLE_HEAD));
	flags.push_back(
		new EqExtraFlag("encrusted", "that have a gem encrusted on them", ITEM_ENCRUSTED));

	flags.push_back(
		new EqExtra2Flag("silver", "that hit monsters vunerable to silver", ITEM2_SILVER));
	flags.push_back(new EqExtra2Flag("bless", "that are blessed", ITEM2_BLESS));
	flags.push_back(
		new EqExtra2Flag("slay_good", "that hit good alignment hard", ITEM2_SLAY_GOOD));
	flags.push_back(
		new EqExtra2Flag("slay_evil", "that hit evil alignment hard", ITEM2_SLAY_EVIL));
	flags.push_back(new EqExtra2Flag("slay_undead", "that hit undead hard", ITEM2_SLAY_UNDEAD));
	flags.push_back(
		new EqExtra2Flag("slay_living", "that hit the living hard", ITEM2_SLAY_LIVING));
	flags.push_back(new EqExtra2Flag("magic", "that are magical", ITEM2_MAGIC));
	flags.push_back(new EqExtra2Flag("linkable", "that can be hitched", ITEM2_LINKABLE));
	flags.push_back(new EqExtra2Flag("noproc", "that are random items", ITEM2_NOPROC));
	flags.push_back(new EqExtra2Flag("notimer", "that are random items", ITEM2_NOTIMER));
	flags.push_back(
		new EqExtra2Flag("noloot", "that can not be taken from a corpse", ITEM2_NOLOOT));
	flags.push_back(
		new EqExtra2Flag("crumbleloot", "that crumble when taken", ITEM2_CRUMBLELOOT));
	flags.push_back(
		new EqExtra2Flag("storeitem", "that were bought in a store", ITEM2_STOREITEM));
	flags.push_back(new EqExtra2Flag("soulbound", "that were soulbound", ITEM2_SOULBIND));
	flags.push_back(new EqExtra2Flag("crafted", "that were crafted", ITEM2_CRAFTED));

	flags.push_back(new EqAffFlag("blind", "that make the wearer blind", AFF_BLIND));
	flags.push_back(
		new EqAffFlag("invisibility", "that make the wearer invisible", AFF_INVISIBLE));
	flags.push_back(new EqAffFlag("farsee", "that grant farsee", AFF_FARSEE));
	flags.push_back(new EqAffFlag("det_invis", "that detect invisible", AFF_DETECT_INVISIBLE));
	flags.push_back(new EqAffFlag("haste", "that grant haste", AFF_HASTE));
	flags.push_back(new EqAffFlag("sense_life", "that sense lifeforms", AFF_SENSE_LIFE));
	flags.push_back(new EqAffFlag("minor_globe", "that provide some magical protection",
				      AFF_MINOR_GLOBE));
	flags.push_back(
		new EqAffFlag("stone_skin", "that grant the wearer stone skin", AFF_STONE_SKIN));
	flags.push_back(new EqAffFlag("ud_vision", "that grant underdark vision", AFF_UD_VISION));
	flags.push_back(new EqAffFlag("armor", "that block armor spells", AFF_ARMOR));
	flags.push_back(
		new EqAffFlag("wraithform", "that grant wraithform and fall off", AFF_WRAITHFORM));
	flags.push_back(new EqAffFlag("waterbreath", "that grant waterbreathing", AFF_WATERBREATH));
	flags.push_back(new EqAffFlag("ko", "that knock the wearer out", AFF_KNOCKED_OUT));
	flags.push_back(
		new EqAffFlag("prot_evil", "that grant protection from evil", AFF_PROTECT_EVIL));
	flags.push_back(new EqAffFlag("bound", "that bind the wearer", AFF_BOUND));
	flags.push_back(
		new EqAffFlag("slow_poison", "that delay the effects of poison", AFF_SLOW_POISON));
	flags.push_back(
		new EqAffFlag("prot_good", "that grant protection from good", AFF_PROTECT_GOOD));
	flags.push_back(new EqAffFlag("sleep", "that used to put the wearer to sleep", AFF_SLEEP));
	flags.push_back(new EqAffFlag("skill_aware", "that shouldn't exist", AFF_SKILL_AWARE));
	flags.push_back(new EqAffFlag("sneak", "that grant sneak to the wearer", AFF_SNEAK));
	flags.push_back(new EqAffFlag("hide", "that used to grant the user hide", AFF_HIDE));
	flags.push_back(new EqAffFlag("fear", "that look really scary", AFF_FEAR));
	flags.push_back(new EqAffFlag("charm", "that look really sweet", AFF_CHARM));
	flags.push_back(new EqAffFlag("meditate", "that look tranquilizing", AFF_MEDITATE));
	flags.push_back(new EqAffFlag("barkskin", "that grant the wearer barkskin", AFF_BARKSKIN));
	flags.push_back(
		new EqAffFlag("infravision", "that grant the wearer infravision", AFF_INFRAVISION));
	flags.push_back(new EqAffFlag("levitate", "that levitate the wearer", AFF_LEVITATE));
	flags.push_back(new EqAffFlag("fly", "that make the wearer fly", AFF_FLY));
	flags.push_back(new EqAffFlag(
		"aware", "that make the wearer more aware of their surroundings", AFF_AWARE));
	flags.push_back(
		new EqAffFlag("prot_fire", "that grant protection from fire", AFF_PROT_FIRE));
	flags.push_back(new EqAffFlag("camping", "that look like tent poles", AFF_CAMPING));
	flags.push_back(
		new EqAffFlag("biofeedback", "that grant the wearer biofeedback", AFF_BIOFEEDBACK));

	flags.push_back(
		new EqAff2Flag("fireshield", "that grant the wearer fireshield", AFF2_FIRESHIELD));
	flags.push_back(
		new EqAff2Flag("ultra", "that grant the wearer ultravision", AFF2_ULTRAVISION));
	flags.push_back(
		new EqAff2Flag("det_evil", "that help the wearer sense evil", AFF2_DETECT_EVIL));
	flags.push_back(
		new EqAff2Flag("det_good", "that help the wearer snse good", AFF2_DETECT_GOOD));
	flags.push_back(
		new EqAff2Flag("det_magic", "that help the wearer sense magic", AFF2_DETECT_MAGIC));
	flags.push_back(
		new EqAff2Flag("maj_phys", "that look big and physical", AFF2_MAJOR_PHYSICAL));
	flags.push_back(
		new EqAff2Flag("prot_cold", "that grant protection from cold", AFF2_PROT_COLD));
	flags.push_back(new EqAff2Flag("prot_light", "that grant protection from lightning",
				       AFF2_PROT_LIGHTNING));
	flags.push_back(new EqAff2Flag("minor_para", "that used to paralyze the wearer",
				       AFF2_MINOR_PARALYSIS));
	flags.push_back(new EqAff2Flag("major_para", "that used to permenantly paralyze the wearer",
				       AFF2_MAJOR_PARALYSIS));
	flags.push_back(new EqAff2Flag("slow", "that slow the wearer", AFF2_SLOW));
	flags.push_back(new EqAff2Flag("globe", "that provide magical protection from most spells",
				       AFF2_GLOBE));
	flags.push_back(
		new EqAff2Flag("prot_gas", "that grant protection from gas", AFF2_PROT_GAS));
	flags.push_back(
		new EqAff2Flag("prot_acid", "that grant protection from acid", AFF2_PROT_ACID));
	flags.push_back(new EqAff2Flag("poisoned", "that poison the wearer", AFF2_POISONED));
	flags.push_back(new EqAff2Flag("soulshield", "that grant soulshield", AFF2_SOULSHIELD));
	flags.push_back(new EqAff2Flag("silenced", "that silence the wearer", AFF2_SILENCED));
	flags.push_back(new EqAff2Flag("concealment", "that grant concealment", AFF2_CONCEALMENT));
	flags.push_back(new EqAff2Flag("vamp", "that grant vampiric touch", AFF2_VAMPIRIC_TOUCH));
	flags.push_back(new EqAff2Flag("stunned", "that look absolutely stunning", AFF2_STUNNED));
	flags.push_back(new EqAff2Flag("earth_aura", "that grant earth aura", AFF2_EARTH_AURA));
	flags.push_back(new EqAff2Flag("water_aura", "that grant water aura", AFF2_WATER_AURA));
	flags.push_back(new EqAff2Flag("fire_aura", "that grant fire aura", AFF2_FIRE_AURA));
	flags.push_back(new EqAff2Flag("air_aura", "that grant air aura", AFF2_AIR_AURA));
	flags.push_back(
		new EqAff2Flag("hold_breath", "that are breath taking", AFF2_HOLDING_BREATH));
	flags.push_back(new EqAff2Flag("memming", "that are mesmorizing", AFF2_MEMORIZING));
	flags.push_back(
		new EqAff2Flag("drowning", "that make you want to choke", AFF2_IS_DROWNING));
	flags.push_back(new EqAff2Flag("passdoor", "that grant the ability to walk through doors",
				       AFF2_PASSDOOR));
	flags.push_back(new EqAff2Flag("flurry", "that grant flurry", AFF2_FLURRY));
	flags.push_back(
		new EqAff2Flag("casting", "that invoke feelings of casting a spell", AFF2_CASTING));
	flags.push_back(new EqAff2Flag("scribing", "that make you want to write", AFF2_SCRIBING));
	flags.push_back(new EqAff2Flag("hunter", "that make you want to kill", AFF2_HUNTER));

	flags.push_back(new EqAff3Flag("tensors", "that make you wonder", AFF3_TENSORS_DISC));
	flags.push_back(new EqAff3Flag("tracking", "that make you want to search", AFF3_TRACKING));
	flags.push_back(
		new EqAff3Flag("singing", "that make you think you can sing", AFF3_SINGING));
	flags.push_back(
		new EqAff3Flag("ecto", "that grant ecotplasmic form", AFF3_ECTOPLASMIC_FORM));
	flags.push_back(new EqAff3Flag("absorbing", "that make you feel fat", AFF3_ABSORBING));
	flags.push_back(new EqAff3Flag("prot_animal", "that grant protection from animals",
				       AFF3_PROT_ANIMAL));
	flags.push_back(new EqAff3Flag("sp_ward", "that grant spirit ward", AFF3_SPIRIT_WARD));
	flags.push_back(new EqAff3Flag("gr_sp_ward", "that grant greater spirit ward",
				       AFF3_GR_SPIRIT_WARD));
	flags.push_back(new EqAff3Flag("mindblank", "that grant the wearer mindblank status",
				       AFF3_NON_DETECTION));
	flags.push_back(new EqAff3Flag("silver", "that can cut lycanthropes", AFF3_SILVER));
	flags.push_back(
		new EqAff3Flag("plusone", "that can hit slightly magical creatures", AFF3_PLUSONE));
	flags.push_back(
		new EqAff3Flag("plustwo", "that can hit some magical creatures", AFF3_PLUSTWO));
	flags.push_back(
		new EqAff3Flag("plusthree", "that can hit most magical creatures", AFF3_PLUSTHREE));
	flags.push_back(
		new EqAff3Flag("plusfour", "that can hit really magical creatures", AFF3_PLUSFOUR));
	flags.push_back(new EqAff3Flag("plusfive", "that can hit all creatures", AFF3_PLUSFIVE));
	flags.push_back(new EqAff3Flag("enlarge", "that make the wearer bigger", AFF3_ENLARGE));
	flags.push_back(new EqAff3Flag("reduce", "that make the wearer smaller", AFF3_REDUCE));
	flags.push_back(new EqAff3Flag("cover", "that make the wearer harder to hit via range",
				       AFF3_COVER));
	flags.push_back(new EqAff3Flag("fourarms", "that grant the wearer four arms to fight with",
				       AFF3_FOUR_ARMS));
	flags.push_back(new EqAff3Flag("inertial", "that grant the wearer inertial barrier",
				       AFF3_INERTIAL_BARRIER));
	flags.push_back(new EqAff3Flag("lightningshield", "that grant the wearer lightningshield",
				       AFF3_LIGHTNINGSHIELD));
	flags.push_back(
		new EqAff3Flag("coldshield", "that grant the wearer coldshield", AFF3_COLDSHIELD));
	flags.push_back(new EqAff3Flag("cannibalize", "that feed the wearer mana from spelldamage",
				       AFF3_CANNIBALIZE));
	flags.push_back(
		new EqAff3Flag("swimming", "that make the wearer want a tan", AFF3_SWIMMING));
	flags.push_back(new EqAff3Flag("toiw", "that grant the wearer a tower of iron will",
				       AFF3_TOWER_IRON_WILL));
	flags.push_back(new EqAff3Flag("underwater", "that make the wearer feel bankrupt",
				       AFF3_UNDERWATER));
	flags.push_back(new EqAff3Flag("blur", "that grant the wearer blur", AFF3_BLUR));
	flags.push_back(new EqAff3Flag("healing", "that grant the wearer enhanced healing",
				       AFF3_ENHANCE_HEALING));
	flags.push_back(
		new EqAff3Flag("elemental_form", "that block elemental form", AFF3_ELEMENTAL_FORM));
	flags.push_back(new EqAff3Flag("pwt", "that prevent the wearer from leaving tracks",
				       AFF3_PASS_WITHOUT_TRACE));
	flags.push_back(
		new EqAff3Flag("pal_aura", "that make you feel more holy", AFF3_PALADIN_AURA));
	flags.push_back(new EqAff3Flag("famine", "that make you hungry", AFF3_FAMINE));

	flags.push_back(new EqAff4Flag("looter", "that mark you as a corpse looter", AFF4_LOOTER));
	flags.push_back(new EqAff4Flag("plague", "that make you really sick", AFF4_CARRY_PLAGUE));
	flags.push_back(new EqAff4Flag("sacking", "that make you feel unemployed", AFF4_SACKING));
	flags.push_back(new EqAff4Flag("sense_follower",
				       "that grants the wearer awareness of invisible followers",
				       AFF4_SENSE_FOLLOWER));
	flags.push_back(
		new EqAff4Flag("stornogs", "that block stornogs spheres", AFF4_STORNOGS_SPHERES));
	flags.push_back(new EqAff4Flag("stornogs_gr", "that block greater stornogs spheres",
				       AFF4_STORNOGS_GREATER_SPHERES));
	flags.push_back(new EqAff4Flag("vamp_form", "that make you a vampire", AFF4_VAMPIRE_FORM));
	flags.push_back(new EqAff4Flag("no_unmorph", "that keep you morphed", AFF4_NO_UNMORPH));
	flags.push_back(
		new EqAff4Flag("holy_sac", "that grant holy sacrifice", AFF4_HOLY_SACRIFICE));
	flags.push_back(
		new EqAff4Flag("battle_ecs", "that grant battle ecstasy", AFF4_BATTLE_ECSTASY));
	flags.push_back(new EqAff4Flag("dazzle", "that grant dazzle", AFF4_DAZZLER));
	flags.push_back(
		new EqAff4Flag("phan_form", "that grant phantasmal form", AFF4_PHANTASMAL_FORM));
	flags.push_back(new EqAff4Flag("nofear", "that make the wearer immune to fear-based magic",
				       AFF4_NOFEAR));
	flags.push_back(new EqAff4Flag("regen", "that grant regeneration", AFF4_REGENERATION));
	flags.push_back(new EqAff4Flag("deaf", "that make you hard of hearing", AFF4_DEAF));
	flags.push_back(new EqAff4Flag("battletide", "heals group members when wearer does damage",
				       AFF4_BATTLETIDE));
	flags.push_back(new EqAff4Flag("epic_increase", "that grant an bonus to earned epics",
				       AFF4_EPIC_INCREASE));
	flags.push_back(new EqAff4Flag("mage_flame", "that grant a magical flame for vision",
				       AFF4_MAGE_FLAME));
	flags.push_back(new EqAff4Flag("globe_dark",
				       "that grant a globe of darkness to avoid the sun",
				       AFF4_GLOBE_OF_DARKNESS));
	flags.push_back(
		new EqAff4Flag("deflect", "that grant perm deflect to the wearer", AFF4_DEFLECT));
	flags.push_back(new EqAff4Flag("hawkvision", "that grant hawkvision", AFF4_HAWKVISION));
	flags.push_back(
		new EqAff4Flag("multiclass", "that really screw things up", AFF4_MULTI_CLASS));
	flags.push_back(new EqAff4Flag("sanctuary", "that grant sanctuary", AFF4_SANCTUARY));
	flags.push_back(new EqAff4Flag("hellfire", "that grant hellfire", AFF4_HELLFIRE));
	flags.push_back(new EqAff4Flag("sense_holy", "that sense holiness", AFF4_SENSE_HOLINESS));
	flags.push_back(new EqAff4Flag("prot_living", "that grant protection from the living",
				       AFF4_PROT_LIVING));
	flags.push_back(new EqAff4Flag("det_illusion", "that grant awareness to illusions",
				       AFF4_DETECT_ILLUSION));
	flags.push_back(new EqAff4Flag("ice_aura", "that grant ice aura", AFF4_ICE_AURA));
	flags.push_back(new EqAff4Flag("reverse_polarity", "that make you hate shaman heals",
				       AFF4_REV_POLARITY));
	flags.push_back(
		new EqAff4Flag("neg_shield", "that grant a negative shield", AFF4_NEG_SHIELD));
	flags.push_back(new EqAff4Flag("tupor", "that make you sleepy", AFF4_TUPOR));
	flags.push_back(new EqAff4Flag("wildmagic", "that grant wildmagic status", AFF4_WILDMAGIC));

	flags.push_back(new EqAff5Flag("dazzlee", "that make the world sparkle", AFF5_DAZZLEE));
	flags.push_back(new EqAff5Flag("mental_anguish", "that make it really hard to focus",
				       AFF5_MENTAL_ANGUISH));
	flags.push_back(new EqAff5Flag("memory_block", "that make it really hard to cast",
				       AFF5_MEMORY_BLOCK));
	flags.push_back(new EqAff5Flag("vines", "that make you one with the earth", AFF5_VINES));
	flags.push_back(new EqAff5Flag("ethereal_alliance", "that make you one with the ether",
				       AFF5_ETHEREAL_ALLIANCE));
	flags.push_back(
		new EqAff5Flag("blood_scent", "that make you smell blood", AFF5_BLOOD_SCENT));
	flags.push_back(new EqAff5Flag("flesh_armor", "that grant immunity to flesh armor",
				       AFF5_FLESH_ARMOR));
	flags.push_back(new EqAff5Flag("wet", "that make you all wet", AFF5_WET));
	flags.push_back(new EqAff5Flag("holy_dharma", "that prevent holy dharma from working",
				       AFF5_HOLY_DHARMA));
	flags.push_back(
		new EqAff5Flag("enhanced_hide", "that make you really hidden", AFF5_ENH_HIDE));
	flags.push_back(new EqAff5Flag("listen", "that make the birds really loud", AFF5_LISTEN));
	flags.push_back(new EqAff5Flag("prot_undead", "that grant protection from undead",
				       AFF5_PROT_UNDEAD));
	flags.push_back(new EqAff5Flag("imprison", "that make you feel like your wearing stripes",
				       AFF5_IMPRISON));
	flags.push_back(new EqAff5Flag("titan_form", "that make you really big", AFF5_TITAN_FORM));
	flags.push_back(new EqAff5Flag("delirium", "that make you really confused", AFF5_DELIRIUM));
	flags.push_back(new EqAff5Flag("shade_movement",
				       "that allow you to remain hidden where there are shadows",
				       AFF5_SHADE_MOVEMENT));
	flags.push_back(
		new EqAff5Flag("noblind", "that prevent blindness stopping you", AFF5_NOBLIND));
	flags.push_back(new EqAff5Flag("magic_glow", "that make you feel like you've just had sex",
				       AFF5_MAGICAL_GLOW));
	flags.push_back(new EqAff5Flag("refreshing_glow",
				       "that make you feel like you just showered",
				       AFF5_REFRESHING_GLOW));
	flags.push_back(new EqAff5Flag("mine", "that grant miner's sight", AFF5_MINE));
	flags.push_back(new EqAff5Flag("stance_offensive", "that make you more offensive",
				       AFF5_STANCE_OFFENSIVE));
	flags.push_back(new EqAff5Flag("stance_defensive", "that make you more defensive",
				       AFF5_STANCE_DEFENSIVE));
	flags.push_back(new EqAff5Flag("obscuring_mist",
				       "that surround the wearer in a concealing mist",
				       AFF5_OBSCURING_MIST));
	flags.push_back(
		new EqAff5Flag("not_offensive", "that make you very peaceful", AFF5_NOT_OFFENSIVE));
	flags.push_back(new EqAff5Flag("decaying_flesh", "that make your flesh decay",
				       AFF5_DECAYING_FLESH));
	flags.push_back(
		new EqAff5Flag("dreadnaught", "that make you feel sturdier", AFF5_DREADNAUGHT));
	flags.push_back(
		new EqAff5Flag("forest_sight", "that make the forests open up", AFF5_FOREST_SIGHT));
	flags.push_back(new EqAff5Flag("thornskin", "that grant thornskin", AFF5_THORNSKIN));
	flags.push_back(new EqAff5Flag("following", "that screws with your ability to follow",
				       AFF5_FOLLOWING));
}

string EqSort::getSortFlagsString(P_obj obj)
{
	string keywords;

	if (!obj)
	{
		return keywords;
	}

	for (size_t i = 0; i < flags.size(); i++)
	{
		if (flags[i] && flags[i]->match(obj))
		{
			keywords += " ";
			keywords += flags[i]->gKey();
			keywords += ",";
		}
	}

	return keywords;
}

string EqSort::getDescString(const char *keyword)
{
	if (strlen(keyword) < 1)
		return string();

	for (size_t i = 0; i < flags.size(); i++)
	{
		if (flags[i] && !strcmp(keyword, flags[i]->gKey()))
		{
			return flags[i]->gDesc();
		}
	}

	return string();
}

string EqSort::getKeyword(const int num)
{
	if (num < 0 || static_cast<size_t>(num) >= flags.size())
	{
		return "NULL";
	}

	return flags[num]->gKey();
}

bool EqSort::isKeyword(const char *keyword)
{
	if (strlen(keyword) < 1)
		return false;

	for (size_t i = 0; i < flags.size(); i++)
	{
		if (flags[i] && !strcmp(keyword, flags[i]->gKey()))
		{
			return true;
		}
	}

	return false;
}
#endif // #ifdef __NO_MYSQL__
