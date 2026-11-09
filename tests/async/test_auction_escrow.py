#!/usr/bin/env python3
"""A listing fee or a bid leaves the wallet at submit; the completion gives back the rest.

Extracts the production auction submit and publication from auction_transaction.c and
links them with the real command codec, a recorded wallet, save and coordinator.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC, rel


def function(source, signature):
    start = source.index(signature)
    depth = 0
    for index in range(source.index("{", start), len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("unbalanced function")


source = (SRC / "auction_transaction.c").read_text()
declarations = source[source.index("struct pending_auction"):
                      source.index("std::string operation_key(")]
harness = r'''
#include "economy/auction_transaction.h"
#include "economy/currency_transaction.h"
#include "item/item_ownership_runtime.h"
#include "player/player_save_pipeline.h"
#include "core/utils.h"
#include <algorithm>
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <mutex>
#include <chrono>
#include <openssl/sha.h>
#include <unordered_map>
#include <vector>

[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { abort(); }
// Everything the submit and the completion do, in order.
static std::vector<std::string> order;
static int64_t wallet = 0;
static critical_command queued;
static critical_submit_result coordinator_result = critical_submit_result::accepted;
static bool refuse_wallet_submit, refuse_wallet_apply, refuse_credit;
static P_char online_actor;
P_char find_player_by_pid(int pid) { return online_actor && GET_PID(online_actor)==pid ? online_actor : nullptr; }
bool auction_publish_committed_event(const auction_command_result &, unsigned long long) { std::abort(); }
void auction_transaction_outbox_published(unsigned long long, bool) { std::abort(); }
static uint32_t reserved_chest_pid;
static std::unordered_map<uint32_t, int64_t> reserved_trade_payments;
static std::string reserved_chest_account;
static int reserved_chest_racewar;
P_char character_list = nullptr;
static bool refuse_trade_reservation, refuse_snapshot_reservation, claim_tagged;
static player_pending_trade_snapshot claim_tag;
bool currency_transaction_reserve_trade(P_char ch, int64_t payment) {
    return !refuse_trade_reservation && reserved_trade_payments.emplace(GET_PID(ch),payment).second;
}
void currency_transaction_release_trade(uint32_t pid) { reserved_trade_payments.erase(pid); }
bool currency_transaction_publish_trade(P_char ch, int64_t payment) {
    if(refuse_wallet_apply || refuse_credit) return false;
    wallet += payment; ++ch->only.pc->wallet_revision; return true;
}
bool player_save_pipeline_reserve_trade(uint32_t pid, const player_pending_trade_snapshot &tag) {
    assert(pid==42);
    if(refuse_snapshot_reservation) return false;
    claim_tag=tag; claim_tagged=true; return true;
}
void player_save_pipeline_release_trade(uint32_t pid) { assert(pid==42); claim_tagged=false; }
bool currency_transaction_chest_busy(P_char ch) { return ch && reserved_chest_pid && GET_PID(ch)==static_cast<int>(reserved_chest_pid); }
bool currency_transaction_wallet_busy(P_char ch) { return currency_transaction_chest_busy(ch); }
bool collector_transaction_player_busy(P_char) { return false; }
bool player_account(P_char ch, std::string *name) { *name="fixture";return ch && GET_PID(ch)>0; }

bool currency_transaction_submit_wallet_value(P_char ch, int64_t value, currency_reason_type,
    int64_t, critical_source_site, critical_deadline_class, currency_completion_fn,
    const void *, size_t)
{
    if (refuse_wallet_submit) return false;
    if (currency_transaction_chest_busy(ch)) return false;
    if (value < 0 && wallet < -value)
        return false;
    if (refuse_wallet_apply || (value > 0 && refuse_credit)) return true;
    wallet += value;
    ++ch->only.pc->wallet_revision;
    order.push_back("wallet:" + std::to_string(value));
    return true;
}
void currency_transaction_save_first(P_char) { order.push_back("save"); }
// Where the listed item is: in the seller's inventory, held by the auction, or gone.
static std::string item_place = "inventory";
void obj_from_char(P_obj) { item_place = "held"; order.push_back("item:held"); }
bool obj_to_char(P_obj, P_char) { item_place = "inventory"; order.push_back("item:back"); return true; }
void extract_obj(P_obj, int = 0) { item_place = "gone"; order.push_back("item:gone"); }
P_obj find_live_object(P_obj expected, uint64_t uid)
{
    return item_place == "held" && uid == 200 ? expected : nullptr;
}
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
    queued = command;
    order.push_back("command");
    return coordinator_result;
}
''' + declarations + function(source, "std::string operation_key(") + \
    function(source, "bool publish(std::unordered_map<std::string, pending_auction>::iterator") + \
    function(source, "P_obj carried_item(P_char character, uint64_t item_uid)") + \
    function(source, "bool submit(P_char character, const auction_command_payload &payload,") + \
    function(source, "bool auction_transaction_player_busy(") + \
    function(source, "void auction_transaction_player_ready(") + \
    function(source, "void auction_transaction_handle_completions(") + \
    function(source, "void auction_transaction_publish_outbox(") + \
    function(source, "void auction_transaction_reset_for_tests(") + \
    function((SRC / "currency_transaction.c").read_text(), "bool currency_transaction_reserve_chest(") + r'''

static auction_command_payload request(auction_action action)
{
    auction_command_payload payload = {};
    payload.action = action;
    payload.actor_pid = 42;
    payload.auction_id = action == auction_action::list ? 0 : 7;
    snprintf(payload.account_name.data(), payload.account_name.size(), "escrow_account");
    if (action == auction_action::list)
    {
        payload.item_count = 1;
        payload.items[0] = {200, 0, 391};
        payload.object_blob_size = 1;
    }
    return payload;
}

// Deliver the queued command's completion to the publication.
static void complete(P_char character, bool committed, int64_t wallet_value_delta, bool retained=false)
{
    auction_command_result result = {};
    auction_command_payload payload = {};
    assert(auction_command_decode_payload(queued, &payload));
    result.action = payload.action;
    result.auction_id = 7;
    result.wallet_value_delta = wallet_value_delta;
    auction_command_payload submitted{};
    assert(auction_command_decode_payload(queued,&submitted));
    result.wallet_revision = submitted.expected_wallet_revision + 1;
    std::array<uint8_t, AUCTION_RESULT_PAYLOAD_BYTES> bytes;
    assert(auction_command_encode_result(result, &bytes));
    auto found = pending.find(operation_key(queued.operation_id));
    assert(found != pending.end());
    found->second.completed.outcome = committed ? critical_apply_outcome::applied :
                                                  critical_apply_outcome::terminal_failure;
    found->second.completion_ready = true;
    found->second.completed.result_size = bytes.size();
    std::copy(bytes.begin(), bytes.end(), found->second.completed.result_payload.begin());
    assert(publish(found, character) == (committed && !retained));
    assert(pending.empty() != retained);
}

int main()
{
    char_data ch = {};
    pc_only_data pc = {};
    ch.only.pc = &pc;
    pc.pid = 42;
    online_actor = &ch;
    obj_data listed = {};
    listed.obj_uid = 200;
    ch.carrying = &listed;

    // A bid leaves the wallet before the command, and the player's save goes first.
    wallet = 6000;
    auction_command_payload bid = request(auction_action::bid);
    bid.value = 5000;
    assert(submit(&ch, bid, nullptr, critical_source_site::command,
                  critical_deadline_class::interactive));
    assert(wallet == 1000);
    assert((order == std::vector<std::string>{"wallet:-5000", "save", "command"}));
    order.clear();
    // The auction charged 3000 of it (a buy-now price, or the difference over the
    // bidder's own last bid): the rest comes back.
    complete(&ch, true, -3000);
    assert(wallet == 3000 && (order == std::vector<std::string>{"wallet:2000"}));
    order.clear();

    // A bid the wallet cannot cover is refused before anything is queued.
    wallet = 1000;
    assert(!submit(&ch, bid, nullptr, critical_source_site::command,
                   critical_deadline_class::interactive));
    assert(wallet == 1000 && order.empty() && pending.empty());

    // A listing the coordinator cannot take gives its fee straight back.
    auction_command_payload list = request(auction_action::list);
    list.listing_fee = 1020;
    wallet = 10000;
    coordinator_result = critical_submit_result::unavailable;
    assert(!submit(&ch, list, nullptr, critical_source_site::command,
                   critical_deadline_class::interactive));
    assert(wallet == 10000 && pending.empty() && item_place == "inventory");
    assert((order == std::vector<std::string>{"wallet:-1020", "item:held", "save", "command",
                                              "wallet:1020", "item:back"}));
    order.clear();
    coordinator_result = critical_submit_result::accepted;

    // The listed item leaves the inventory before the seller's save, so no save can
    // claim it back from the auction. A refused listing gives item and fee back; a
    // committed one extracts the item and keeps the fee.
    assert(submit(&ch, list, nullptr, critical_source_site::command,
                  critical_deadline_class::interactive));
    assert(item_place == "held");
    complete(&ch, false, 0);
    assert(wallet == 10000 && item_place == "inventory");
    order.clear();
    assert(submit(&ch, list, nullptr, critical_source_site::command,
                  critical_deadline_class::interactive));
    complete(&ch, true, -1020);
    assert(wallet == 8980 && item_place == "gone");
    assert((order == std::vector<std::string>{"wallet:-1020", "item:held", "save", "command",
                                              "item:gone"}));
    order.clear();
    // An item extracted while it was held is not given back.
    item_place = "inventory";
    assert(submit(&ch, list, nullptr, critical_source_site::command,
                  critical_deadline_class::interactive));
    item_place = "gone";
    order.clear();
    complete(&ch, false, 0);
    assert(wallet == 8980 && (order == std::vector<std::string>{"wallet:1020"}));
    order.clear();
    // A listing of an item the seller no longer carries is refused before anything moves.
    ch.carrying = nullptr;
    assert(!submit(&ch, list, nullptr, critical_source_site::command,
                   critical_deadline_class::interactive));
    assert(wallet == 8980 && order.empty() && pending.empty());

    // A money claim takes nothing at submit and brings its money at completion.
    auction_command_payload claim = request(auction_action::claim_money);
    assert(submit(&ch, claim, nullptr, critical_source_site::command,
                  critical_deadline_class::interactive));
    assert((order == std::vector<std::string>{"command"}));
    complete(&ch, true, 4500);
    assert(wallet == 13480);
    // The real pending-claim predicate prevents the real chest reservation
    // until its committed payout is published. Reverse overlap is refused
    // before the auction command can clear another durable pickup row.
    order.clear();
    assert(submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(!currency_transaction_reserve_chest(&ch) && !reserved_chest_pid);
    complete(&ch,true,4500);assert(wallet==17980);
    assert(currency_transaction_reserve_chest(&ch));order.clear();
    assert(!submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(pending.empty() && order.empty() && wallet==17980);
    reserved_chest_pid=0;reserved_chest_account.clear();
    assert(submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    complete(&ch,true,4500);assert(wallet==22480);

    // Admitted-but-refused debits cannot submit a bid or detach a listing.
    ch.carrying = &listed;
    item_place = "inventory";
    for (bool *refusal : {&refuse_wallet_submit, &refuse_wallet_apply}) {
        *refusal = true; wallet = 6000; order.clear();
        assert(!submit(&ch,bid,nullptr,critical_source_site::command,critical_deadline_class::interactive));
        assert(!submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
        assert(wallet == 6000 && item_place == "inventory" && pending.empty() && order.empty());
        *refusal = false;
    }

    // A refused payout retains its receipt; retry credits exactly once.
    for (bool *refusal : {&refuse_wallet_submit, &refuse_credit}) {
        wallet = 6000;
        assert(submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
        *refusal = true;
        complete(&ch,true,4500,true);
        auction_transaction_player_ready(&ch);
        assert(wallet == 6000 && !pending.empty());
        *refusal = false;
        auction_transaction_publish_outbox();
        auction_transaction_player_ready(&ch);
        assert(wallet == 10500 && pending.empty());
    }

    // Refused coordinator admission must retain a refused refund and held UID too.
    coordinator_result = critical_submit_result::unavailable;
    refuse_credit = true;
    assert(!submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(wallet == 9480 && item_place == "held" && !pending.empty());
    refuse_credit = false;
    auction_transaction_player_ready(&ch);
    auction_transaction_player_ready(&ch);
    assert(wallet == 10500 && item_place == "inventory" && pending.empty());

    // A committed result arriving after unload waits for a replacement session.
    coordinator_result = critical_submit_result::accepted;
    assert(submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    auction_command_result result{};
    result.action = auction_action::claim_money; result.auction_id = 7; result.wallet_value_delta = 4500;
    std::array<uint8_t, AUCTION_RESULT_PAYLOAD_BYTES> encoded{};
    assert(auction_command_encode_result(result,&encoded));
    critical_completion reply{}; reply.operation_id = queued.operation_id;
    reply.outcome = critical_apply_outcome::applied; reply.result_size = encoded.size();
    std::copy(encoded.begin(),encoded.end(),reply.result_payload.begin());
    online_actor = nullptr;
    auction_transaction_handle_completions(&reply,1);
    reply.outcome = critical_apply_outcome::already_applied;
    auction_transaction_handle_completions(&reply,1);
    auction_transaction_publish_outbox();
    assert(wallet == 10500 && !pending.empty());
    char_data replacement{}; pc_only_data replacement_pc{};
    replacement.only.pc = &replacement_pc; replacement_pc.pid = 42;
    online_actor = &replacement;
    auction_transaction_player_ready(&replacement);
    assert(wallet == 15000 && pending.empty());
    auction_transaction_handle_completions(&reply,1);
    auction_transaction_publish_outbox();
    assert(wallet == 15000 && pending.empty());

    // New claims reserve their exact future credit and attach the existing save receipt.
    auto durable_claim = claim;
    durable_claim.value = 50;
    durable_claim.expected_wallet_revision = pc.wallet_revision;
    for(bool *refusal : {&refuse_trade_reservation,&refuse_snapshot_reservation}) {
        *refusal=true; order.clear();
        assert(!submit(&ch,durable_claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
        assert(pending.empty() && reserved_trade_payments.empty() && !claim_tagged && order.empty());
        *refusal=false;
    }
    coordinator_result = critical_submit_result::unavailable;
    assert(!submit(&ch,durable_claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(pending.empty() && reserved_trade_payments.empty() && !claim_tagged && wallet==15000);
    coordinator_result = critical_submit_result::accepted;
    assert(submit(&ch,durable_claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(claim_tagged && claim_tag.payment==50 && claim_tag.wallet_revision==pc.wallet_revision);
    assert(claim_tag.operation==queued.operation_id.bytes);
    complete(&ch,false,0);
    assert(wallet==15000 && !claim_tagged && reserved_trade_payments.empty());
    assert(submit(&ch,durable_claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    character_list=&ch; // A retained linkdead body receives the credit once.
    complete(nullptr,true,50);
    assert(wallet==15050 && !claim_tagged && reserved_trade_payments.empty());
    character_list=nullptr;
    durable_claim.expected_wallet_revision=pc.wallet_revision;
    assert(submit(&ch,durable_claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    complete(nullptr,true,50); // An unloaded body is recovered from the SQL wallet.
    assert(wallet==15050 && !claim_tagged && reserved_trade_payments.empty());
    auction_transaction_player_ready(&replacement);
    assert(wallet==15050);
    assert(submit(&ch,durable_claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    auction_transaction_reset_for_tests();
    assert(pending.empty() && !claim_tagged && reserved_trade_payments.empty());
    puts("auction escrow and chest-reservation interlock preserve committed payouts");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="auction-escrow-", dir=ROOT / "bin/tests") as temporary:
    cpp = Path(temporary) / "escrow.cpp"
    binary = Path(temporary) / "escrow"
    cpp.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
        "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all",
        "-D__NO_MYSQL__", "-Isrc", "-Isrc/no_mysql", str(cpp),
        rel("auction_command.c"), rel("currency_command.c"),
        rel("critical_command.c"), rel("item_transfer_command.c"),
        rel("item_ownership_runtime.c"), rel("player_snapshot_codec.c"),
        "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
