#!/usr/bin/env python3
"""Auction fees/bids reserve the purse; only durable receipts move money and custody."""

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
static bool refuse_wallet_apply;
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
    return !refuse_trade_reservation && (payment >= 0 || wallet >= -payment) &&
        reserved_trade_payments.emplace(GET_PID(ch),payment).second;
}
void currency_transaction_release_trade(uint32_t pid) { reserved_trade_payments.erase(pid); }
bool currency_transaction_publish_trade(P_char ch, int64_t payment) {
    if(refuse_wallet_apply) return false;
    wallet += payment; ++ch->only.pc->wallet_revision;
    order.push_back("publish:"+std::to_string(payment)); return true;
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

void currency_transaction_save_first(P_char) { order.push_back("save"); }
// The listed source stays carried until the durable receipt allows extraction.
static std::string item_place = "inventory";
void extract_obj(P_obj, int = 0) { item_place = "gone"; order.push_back("item:gone"); }
P_obj find_live_object(P_obj expected, uint64_t uid)
{
    return item_place != "gone" && uid == 200 ? expected : nullptr;
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
    payload.expected_wallet_revision = online_actor ? online_actor->only.pc->wallet_revision : 0;
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

    auto bid = request(auction_action::bid); bid.value=5000;
    wallet=6000;
    assert(submit(&ch,bid,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(wallet==6000 && claim_tagged && claim_tag.payment==-5000);
    assert(reserved_trade_payments.at(42)==-5000 && (order==std::vector<std::string>{"save","command"}));
    std::vector<uint8_t> command_bytes;
    assert(critical_command_encode(queued,&command_bytes)==critical_command_codec_result::ok);
    std::array<uint8_t,32> digest{}; SHA256(command_bytes.data(),command_bytes.size(),digest.data());
    assert(digest==claim_tag.command_hash && claim_tag.operation==queued.operation_id.bytes);
    order.clear();
    complete(&ch,true,-3000); // Own-bid increment or buy-now uses the actual cost.
    assert(wallet==3000 && (order==std::vector<std::string>{"publish:-3000"}));
    assert(!claim_tagged && reserved_trade_payments.empty()); order.clear();

    bid.expected_wallet_revision=pc.wallet_revision;
    wallet=1000;
    assert(!submit(&ch,bid,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(wallet==1000 && order.empty() && pending.empty());

    auto list=request(auction_action::list); list.listing_fee=1020;
    wallet=10000; coordinator_result=critical_submit_result::unavailable;
    assert(!submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(wallet==10000 && pending.empty() && item_place=="inventory");
    assert((!claim_tagged && reserved_trade_payments.empty() && order==std::vector<std::string>{"save","command"}));
    order.clear(); coordinator_result=critical_submit_result::accepted;
    for(bool *refusal : {&refuse_trade_reservation,&refuse_snapshot_reservation}) {
        *refusal=true;
        assert(!submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
        assert(wallet==10000 && pending.empty() && !claim_tagged && reserved_trade_payments.empty() && order.empty());
        *refusal=false;
    }
    assert(submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(item_place=="inventory" && wallet==10000 && claim_tag.payment==-1020);
    complete(&ch,false,0);
    assert(wallet==10000 && item_place=="inventory" && !claim_tagged && reserved_trade_payments.empty());
    order.clear();
    assert(submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    complete(&ch,true,-1020);
    assert(wallet==8980 && item_place=="gone");
    assert((order==std::vector<std::string>{"save","command","publish:-1020","item:gone"})); order.clear();

    // Refused publication retains its exact receipt and original UID until retry.
    item_place="inventory"; list.expected_wallet_revision=pc.wallet_revision;
    assert(submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    refuse_wallet_apply=true;
    complete(&ch,true,-1020,true);
    auction_transaction_player_ready(&ch);
    assert(wallet==8980 && item_place=="inventory" && claim_tagged);
    refuse_wallet_apply=false;
    auction_transaction_publish_outbox(); auction_transaction_player_ready(&ch);
    assert(wallet==7960 && item_place=="gone" && pending.empty());

    ch.carrying=nullptr; list.expected_wallet_revision=pc.wallet_revision; order.clear();
    assert(!submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(wallet==7960 && order.empty() && pending.empty());

    // Linkdead bodies publish once; unloaded bodies recover the SQL purse instead.
    auto claim=request(auction_action::claim_money); claim.value=50;
    assert(submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    character_list=&ch;
    complete(nullptr,true,50);
    assert(wallet==8010 && !claim_tagged && reserved_trade_payments.empty());
    character_list=nullptr; claim.expected_wallet_revision=pc.wallet_revision;
    assert(submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    complete(nullptr,true,50);
    assert(wallet==8010 && !claim_tagged && reserved_trade_payments.empty());
    auction_transaction_player_ready(&ch); assert(wallet==8010);

    // The same unload/replay behavior applies to a debit.
    bid.expected_wallet_revision=pc.wallet_revision;
    assert(submit(&ch,bid,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    auction_command_result result{}; result.action=auction_action::bid;
    result.wallet_value_delta=-3000; result.wallet_revision=pc.wallet_revision+1;
    std::array<uint8_t,AUCTION_RESULT_PAYLOAD_BYTES> encoded{};
    assert(auction_command_encode_result(result,&encoded));
    critical_completion reply{}; reply.operation_id=queued.operation_id;
    reply.outcome=critical_apply_outcome::applied; reply.result_size=encoded.size();
    std::copy(encoded.begin(),encoded.end(),reply.result_payload.begin());
    online_actor=nullptr;
    auction_transaction_handle_completions(&reply,1);
    assert(pending.empty() && wallet==8010 && !claim_tagged && reserved_trade_payments.empty());
    online_actor=&ch;
    reply.outcome=critical_apply_outcome::already_applied;
    auction_transaction_handle_completions(&reply,1); auction_transaction_player_ready(&ch);
    assert(wallet==8010);

    // A free listing still advances the receipt-bound wallet revision exactly once.
    ch.carrying=&listed; item_place="inventory";
    list=request(auction_action::list); auto revision=pc.wallet_revision;
    assert(submit(&ch,list,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(claim_tagged && claim_tag.payment==0);
    complete(&ch,true,0);
    assert(wallet==8010 && pc.wallet_revision==revision+1 && item_place=="gone");

    // Existing chest exclusion and reservation cleanup remain in force.
    claim=request(auction_action::claim_money); claim.value=50;
    assert(submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(!currency_transaction_reserve_chest(&ch));
    auction_transaction_reset_for_tests();
    assert(pending.empty() && !claim_tagged && reserved_trade_payments.empty());
    assert(currency_transaction_reserve_chest(&ch));
    order.clear();
    assert(!submit(&ch,claim,nullptr,critical_source_site::command,critical_deadline_class::interactive));
    assert(pending.empty() && order.empty());
    puts("auction receipts: reservation/refusal, exact cost/custody, linkdead/unloaded and replay pass");
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
