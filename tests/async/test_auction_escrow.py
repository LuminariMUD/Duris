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
                      source.index("enum class outbox_publication_state")]
harness = r'''
#include "economy/auction_transaction.h"
#include "economy/currency_transaction.h"
#include "item/item_ownership_runtime.h"
#include "core/utils.h"
#include <algorithm>
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <unordered_map>
#include <vector>

[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { abort(); }
// Everything the submit and the completion do, in order.
static std::vector<std::string> order;
static int64_t wallet = 0;
static critical_command queued;
static critical_submit_result coordinator_result = critical_submit_result::accepted;

bool currency_transaction_submit_wallet_value(P_char, int64_t value, currency_reason_type,
    int64_t, critical_source_site, critical_deadline_class, currency_completion_fn,
    const void *, size_t)
{
    if (value < 0 && wallet < -value)
        return false;
    wallet += value;
    order.push_back("wallet:" + std::to_string(value));
    return true;
}
void currency_transaction_save_first(P_char) { order.push_back("save"); }
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
    queued = command;
    order.push_back("command");
    return coordinator_result;
}
''' + declarations + function(source, "std::string operation_key(") + \
    function(source, "bool publish(std::unordered_map<std::string, pending_auction>::iterator") + \
    function(source, "bool submit(P_char character, const auction_command_payload &payload,") + r'''

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
static void complete(P_char character, bool committed, int64_t wallet_value_delta)
{
    auction_command_result result = {};
    auction_command_payload payload = {};
    assert(auction_command_decode_payload(queued, &payload));
    result.action = payload.action;
    result.auction_id = 7;
    result.wallet_value_delta = wallet_value_delta;
    std::array<uint8_t, AUCTION_RESULT_PAYLOAD_BYTES> bytes;
    assert(auction_command_encode_result(result, &bytes));
    auto found = pending.find(operation_key(queued.operation_id));
    assert(found != pending.end());
    found->second.completed.outcome = committed ? critical_apply_outcome::applied :
                                                  critical_apply_outcome::terminal_failure;
    found->second.completed.result_size = bytes.size();
    std::copy(bytes.begin(), bytes.end(), found->second.completed.result_payload.begin());
    assert(publish(found, character) == committed);
    assert(pending.empty());
}

int main()
{
    char_data ch = {};
    pc_only_data pc = {};
    ch.only.pc = &pc;
    pc.pid = 42;

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
    assert(wallet == 10000 && pending.empty());
    assert((order == std::vector<std::string>{"wallet:-1020", "save", "command",
                                              "wallet:1020"}));
    order.clear();
    coordinator_result = critical_submit_result::accepted;

    // A refused listing gives the whole fee back; a committed one keeps it.
    assert(submit(&ch, list, nullptr, critical_source_site::command,
                  critical_deadline_class::interactive));
    complete(&ch, false, 0);
    assert(wallet == 10000);
    order.clear();
    assert(submit(&ch, list, nullptr, critical_source_site::command,
                  critical_deadline_class::interactive));
    complete(&ch, true, -1020);
    assert(wallet == 8980 && (order == std::vector<std::string>{"wallet:-1020", "save", "command"}));
    order.clear();

    // A money claim takes nothing at submit and brings its money at completion.
    auction_command_payload claim = request(auction_action::claim_money);
    assert(submit(&ch, claim, nullptr, critical_source_site::command,
                  critical_deadline_class::interactive));
    assert((order == std::vector<std::string>{"command"}));
    complete(&ch, true, 4500);
    assert(wallet == 13480);
    puts("auction escrow: taken at submit, the rest given back at completion");
}
'''

with tempfile.TemporaryDirectory(prefix="auction-escrow-") as temporary:
    cpp = Path(temporary) / "escrow.cpp"
    binary = Path(temporary) / "escrow"
    cpp.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
        "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
        "-D__NO_MYSQL__", "-Isrc", "-Isrc/no_mysql", str(cpp),
        rel("auction_command.c"), rel("currency_command.c"),
        rel("critical_command.c"), rel("item_transfer_command.c"),
        rel("item_ownership_runtime.c"), rel("player_snapshot_codec.c"),
        "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
