#!/usr/bin/env python3
"""Command-codec, route, schema, and publication contracts for auction cutover."""

from _paths import SRC, extract_function
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include "economy/auction_command.h"
#include <cassert>
#include <cstring>

int main()
{
    auction_command_payload payload = {};
    payload.action = auction_action::list;
    payload.actor_pid = 42;
    payload.racewar = 1;
    memcpy(payload.account_name.data(), "auction-test", 12);
    memcpy(payload.actor_name.data(), "Seller", 6);
    payload.expected_wallet_revision = 7;
    payload.expected_bank_revision = 9;
    payload.start_price = 1000;
    payload.buy_price = 5000;
    payload.listing_fee = 1020;
    payload.closing_fee_basis_points = 300;
    payload.bid_extension_seconds = 300;
    payload.end_time = 2000000000;
    payload.item_count = 2;
    payload.items[0] = {101, 3, 77};
    payload.items[1] = {102, 4, 77};
    memcpy(payload.object_blob.data(), "blob", 5);
    payload.object_blob_size = 5;
    memcpy(payload.object_short.data(), "a blade", 7);

    critical_operation_id id = {};
    assert(critical_operation_id_generate(&id));
    critical_command command = {};
    assert(auction_command_build(&command, id, payload, critical_source_site::command,
                                 critical_deadline_class::interactive));
    auction_command_payload decoded = {};
    assert(auction_command_decode_payload(command, &decoded));
    assert(decoded.item_count == 2 && decoded.items[1].item_uid == 102);
    assert(decoded.closing_fee_basis_points == 300);
    assert(command.keys.size() == 5);

    auction_command_result full_result = {};
    full_result.action = auction_action::list;
    full_result.event_type = auction_event_type::listed;
    full_result.item_count = AUCTION_COMMAND_MAX_ITEMS;
    for (size_t index = 0; index < full_result.item_count; ++index)
    {
        full_result.item_uids[index] = 1000 + index;
        full_result.item_revisions[index] = 10 + index;
    }
    std::array<uint8_t, AUCTION_RESULT_PAYLOAD_BYTES> encoded_result = {};
    assert(auction_command_encode_result(full_result, &encoded_result));
    auction_command_result decoded_result = {};
    assert(auction_command_decode_result(encoded_result.data(), encoded_result.size(),
                                         &decoded_result));
    assert(decoded_result.item_count == AUCTION_COMMAND_MAX_ITEMS);

    critical_command tampered = command;
    tampered.expected_revisions.pop_back();
    assert(!auction_command_decode_payload(tampered, &decoded));
    tampered = command;
    tampered.keys.back().id = 999;
    assert(!auction_command_decode_payload(tampered, &decoded));

    payload.item_count = AUCTION_COMMAND_MAX_ITEMS + 1;
    assert(!auction_command_build(&command, id, payload, critical_source_site::command,
                                  critical_deadline_class::interactive));
    return 0;
}
'''


def section(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


class AuctionTransactionalCutoverTests(unittest.TestCase):
    def test_bounded_codec_and_exact_fences(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "auction_codec.cpp"
            binary = Path(directory) / "auction_codec"
            harness.write_text(HARNESS)
            subprocess.run(
                ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", f"-I{SRC}",
                 str(harness), str(SRC / "critical_command.c"),
                 str(SRC / "currency_command.c"), str(SRC / "auction_command.c"),
                 "-lcrypto", "-o", str(binary)],
                check=True,
            )
            subprocess.run([str(binary)], check=True)

    def test_live_routes_submit_commands_and_publish_after_ack(self):
        source = (SRC / "auction_houses.c").read_text()
        source = source[source.index("#else", source.index("#ifdef __NO_MYSQL__")) :]
        routes = {
            "bool auction_offer(P_char": "static void auction_list_row(",
            "bool auction_bid(P_char": "static void auction_pickup_claim(",
            "static void auction_pickup_claim(P_char": "bool auction_help(",
            "bool auction_remove(P_char": "// syntax: auction bid",
            "bool finalize_auction(int": "bool insert_money_pickup(",
        }
        for start, end in routes.items():
            body = section(source, start, end)
            self.assertIn("auction_transaction_submit", body)
            self.assertNotIn("SUB_MONEY", body)
            self.assertNotIn("sql_begin_transaction", body)
        # The listed items leave the inventory at submit and are extracted when the
        # listing commits (auction_transaction.c); the callback only reports it.
        offer_callback = section(source, "void auction_list_completed(",
                                 "void auction_bid_completed(")
        self.assertNotIn("obj_from_char", offer_callback)
        transaction = (SRC / "auction_transaction.c").read_text()
        submit = transaction[transaction.index("bool submit(P_char character"):]
        self.assertLess(submit.index("obj_from_char(object)"),
                        submit.index("currency_transaction_save_first(character)"))
        self.assertLess(submit.index("currency_transaction_save_first(character)"),
                        submit.index("critical_command_coordinator_submit"))
        self.assertNotIn("ws_broadcast_auction_new", offer_callback)
        publication = section(source, "static void auction_publish_event(",
                              "// syntax: auction offer")
        self.assertIn("ws_broadcast_auction_new", publication)
        self.assertIn("ws_broadcast_auction_bid", publication)
        self.assertIn("ws_broadcast_auction_close", publication)
        transaction = (SRC / "auction_transaction.c").read_text()
        self.assertIn("auction_transaction_outbox_delivery", transaction)
        self.assertIn("outbox_publication_state::published", transaction)

    def test_outbox_waits_for_async_publication_callback(self):
        transaction = (SRC / "auction_transaction.c").read_text()
        declarations = transaction[transaction.index("enum class outbox_publication_state"):
                                   transaction.index("std::string operation_key(")]
        houses = (SRC / "auction_houses.c").read_text()
        houses = houses[houses.index("#else", houses.index("#ifdef __NO_MYSQL__")):]
        producer = section(houses, "bool auction_publish_committed_event(",
                           "// syntax: auction offer")
        harness = r'''
#include "economy/auction_transaction.h"
#include "sql/sql_async.h"
#include <cassert>
#include <mutex>
#include <unordered_map>
static std::function<void(bool, const sql_rows &)> done;
static bool accept_read = true;
static unsigned int broadcasts = 0, resumes = 0, reads = 0;
void logit(const char *, const char *, ...) {}
std::string sql_format(const char *, ...) { return "auction lookup"; }
bool sql_read_at(persistence_query_site, std::string,
                 std::function<void(bool, const sql_rows &)> callback) {
    ++reads;
    if (!accept_read) return false;
    assert(!done); done = std::move(callback); return true;
}
void critical_outbox_resume() { ++resumes; }
critical_outbox_delivery_result critical_outbox_test_destination(const critical_outbox_record &, void *) {
    return critical_outbox_delivery_result::terminal_failure;
}
bool auction_command_decode_result(const uint8_t *, size_t, auction_command_result *result) {
    result->auction_id = 7; result->event_type = auction_event_type::listed; return true;
}
static void auction_publish_event(const auction_command_result &, unsigned long long,
                                  const sql_row &) { ++broadcasts; }
''' + declarations + producer + \
            extract_function("auction_transaction.c", "critical_outbox_delivery_result\nauction_transaction_outbox_delivery(") + \
            extract_function("auction_transaction.c", "void auction_transaction_outbox_published(") + \
            extract_function("auction_transaction.c", "void auction_transaction_publish_outbox(") + r'''
static void complete(bool ok, const sql_rows &rows) {
    assert(done); auto callback = std::move(done); done = {}; callback(ok, rows);
}
int main() {
    auction_command_result result = {};
    result.auction_id = 7; result.event_type = auction_event_type::listed;
    critical_outbox_record record = {};
    record.outbox_id = 11; record.destination = 5; record.event_type = 1; record.payload_version = 1;
    assert(auction_transaction_outbox_delivery(record, nullptr) == critical_outbox_delivery_result::publication_pending);
    auction_transaction_publish_outbox();
    assert(done && !broadcasts && !resumes);
    assert(outbox_publications.at(11).state == outbox_publication_state::publishing);
    // The read may be delayed past any worker retry or lifecycle deadline.
    auction_transaction_publish_outbox(); assert(reads == 1 && !resumes);
    for (unsigned int i = 0; i < 10; ++i)
        assert(auction_transaction_outbox_delivery(record, nullptr) == critical_outbox_delivery_result::publication_pending);
    auto retry_after_failure = [&] {
        // The worker observes a real failure and records normal durable backoff.
        assert(auction_transaction_outbox_delivery(record, nullptr) == critical_outbox_delivery_result::retryable_failure);
        // This visit represents the next due attempt, not a progress callback retry.
        assert(auction_transaction_outbox_delivery(record, nullptr) == critical_outbox_delivery_result::publication_pending);
    };
    complete(false, {});
    assert(outbox_publications.at(11).state == outbox_publication_state::failed);
    auction_transaction_publish_outbox(); assert(!done); // No read storm before the worker retries.
    retry_after_failure();
    auction_transaction_publish_outbox(); complete(true, {}); // Missing auction is also failure.
    assert(!resumes && outbox_publications.at(11).state == outbox_publication_state::failed);
    retry_after_failure();
    accept_read = false; auction_transaction_publish_outbox();
    assert(!done && outbox_publications.at(11).state == outbox_publication_state::failed);
    retry_after_failure();
    accept_read = true; auction_transaction_publish_outbox();
    complete(true, sql_rows{sql_row{}});
    assert(broadcasts == 1 && resumes == 1);
    assert(outbox_publications.at(11).state == outbox_publication_state::published);
    assert(auction_transaction_outbox_delivery(record, nullptr) == critical_outbox_delivery_result::delivered);
    auction_transaction_publish_outbox(); assert(broadcasts == 1);
    result.event_type = auction_event_type::money_claimed;
    outbox_publications.emplace(12, pending_outbox_publication{result, outbox_publication_state::queued});
    auction_transaction_publish_outbox();
    assert(!done && resumes == 2 && outbox_publications.at(12).state == outbox_publication_state::published);
}
'''
        (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="auction-outbox-callback-", dir=ROOT / "bin/tests") as directory:
            path = Path(directory)
            (path / "test.cpp").write_text(harness)
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
                            "-Isrc", "-I/usr/include/libxml2", str(path / "test.cpp"),
                            "-o", str(path / "test")], cwd=ROOT, check=True)
            subprocess.run([str(path / "test")], check=True)

    def test_mysql_reads_and_bookkeeping_leave_the_game_loop(self):
        # Step 8: the listings, an auction's details, what waits for pickup, the resort and
        # the committed event's row are read on the writer; money pickups are queued there.
        source = (SRC / "auction_houses.c").read_text()
        source = source[source.index("#else", source.index("#ifdef __NO_MYSQL__")) :]
        routes = {
            "static void auction_publish_event(": "// syntax: auction offer",
            "static void auction_list_row(P_char": "// syntax: auction remove",
            "static void auction_pickup_claim(P_char": "bool auction_help(",
            "// syntax: auction resort": "namespace\n{\nbool auction_copy_text",
            "bool insert_money_pickup(int": "string format_time(",
        }
        for start, end in routes.items():
            body = section(source, start, end)
            for forbidden in ("qry(", "mysql_store_result", "db_query"):
                self.assertNotIn(forbidden, body)
        self.assertIn("sql_read(", section(source, "bool auction_publish_committed_event(",
                                           "// syntax: auction offer"))
        self.assertIn("sql_read_for(", section(source, "bool auction_list(P_char",
                                               "// syntax: auction info"))
        self.assertIn("sql_read_for(", section(source, "bool auction_info(P_char",
                                               "// syntax: auction remove"))
        self.assertIn("sql_read_work_for(", section(source, "bool auction_pickup(P_char",
                                                    "bool auction_help("))
        self.assertIn("sql_queue_statements(", section(source, "// syntax: auction resort",
                                                       "namespace\n{\nbool auction_copy_text"))
        self.assertIn("sql_queue(", section(source, "bool insert_money_pickup(int",
                                            "string format_time("))

    def test_client_free_read_and_pickup_routes_use_flat_catalog(self):
        source = (SRC / "auction_houses.c").read_text()
        no_mysql = section(source, "#ifdef __NO_MYSQL__", "#else")
        self.assertNotIn("Auctions are disabled", no_mysql)
        list_route = section(no_mysql, "bool auction_list(P_char", "bool auction_info(P_char")
        info_route = section(no_mysql, "bool auction_info(P_char", "bool auction_pickup(P_char")
        pickup_route = section(no_mysql, "bool auction_pickup(P_char", "bool auction_help(P_char")
        self.assertIn("flatfile_auction_list_open", list_route)
        self.assertIn("flatfile_auction_find_open", info_route)
        self.assertIn("flatfile_auction_find_pickup", pickup_route)
        self.assertIn("auction_transaction_submit", pickup_route)
        for route in (list_route, info_route, pickup_route):
            self.assertNotIn("qry(", route)
            self.assertNotIn("MYSQL_", route)

    def test_client_free_mutations_and_expiry_use_typed_commands(self):
        source = (SRC / "auction_houses.c").read_text()
        no_mysql = section(source, "#ifdef __NO_MYSQL__", "#else")
        expiry = section(no_mysql, "void auction_houses_activity()", "bool auction_offer(P_char")
        offer = section(no_mysql, "bool auction_offer(P_char", "bool auction_bid(P_char")
        bid = section(no_mysql, "bool auction_bid(P_char", "bool auction_remove(P_char")
        remove = section(no_mysql, "bool auction_remove(P_char", "bool auction_list(P_char")
        self.assertIn("flatfile_auction_list_open", expiry)
        self.assertIn("pending_flat_finalizations", expiry)
        self.assertIn("auction_transaction_submit_background", expiry)
        self.assertIn("flatfile_auction_find_pending_event", expiry)
        self.assertIn("publish_flat_auction_event", expiry)
        self.assertIn("flatfile_auction_acknowledge_event", expiry)
        # The seller holds the item in memory; the listing claims it in the repository.
        self.assertNotIn("item_ownership_runtime_lookup", offer)
        self.assertNotIn("ownership is still being synchronized", offer)
        self.assertIn("write_one_object", offer)
        for route in (offer, bid, remove):
            self.assertIn("auction_transaction_submit", route)
            self.assertNotIn("SUB_MONEY", route)
            self.assertNotIn("qry(", route)
        publisher = section(no_mysql, "bool publish_flat_auction_event(", "} // namespace")
        self.assertIn("stage_auction_event_message", publisher)
        self.assertIn("ws_broadcast_auction_new", publisher)
        self.assertIn("ws_broadcast_auction_bid", publisher)
        self.assertIn("ws_broadcast_auction_close", publisher)
        self.assertIn("flatfile_offline_message_enqueue", no_mysql)

    def test_repository_owns_settlement_claims_ledgers_and_outbox(self):
        repository = (SRC / "auction_repository.c").read_text()
        generic = (SRC / "critical_command_repository.c").read_text()
        for token in (
            "FOR UPDATE", "transition_items", "stage_money",
            "stage_items", "auction_item_custody", "auction_ledger",
            "claim_operation_id", "claimed_at=CURRENT_TIMESTAMP(6)",
        ):
            self.assertIn(token, repository)
        # The wallet is memory's: the repository reports what it charged or paid.
        for token in ("UPDATE player_data", "account_banks", "currency_ledger"):
            self.assertNotIn(token, repository)
        self.assertIn("wallet_value_delta", repository)
        auction_branch = generic[generic.index("if (auction_command)"):]
        self.assertLess(auction_branch.index("insert_outbox"),
                        auction_branch.index('execute(connection, "COMMIT")'))
        self.assertLess(auction_branch.index("finish_inbox"),
                        auction_branch.index('execute(connection, "COMMIT")'))

    def test_schema_tools_are_additive_guarded_and_bootstrapped(self):
        migration = (ROOT / "migrations/auction_transactional_cutover.sql").read_text()
        bootstrap = (ROOT / "migrations/bootstrap_multithread_safe.sql").read_text()
        runner = (ROOT / "migrations/run_migration.sh").read_text()
        for token in (
            "auction_revision", "custody_state", "listing_operation_id",
            "auction_item_custody", "auction_ledger",
            "auction_reconciliation_quarantine", "claim_revision",
        ):
            self.assertIn(token, migration)
            self.assertIn(token, bootstrap)
        self.assertNotIn("DELETE FROM auctions", migration)
        self.assertIn("auction_transactional_cutover.sql", runner)
        for script in ("apply_auction_transactional_cutover.sh",
                       "reconcile_auction_transactions.sh"):
            path = ROOT / "migrations" / script
            self.assertTrue(path.stat().st_mode & 0o111)
            text = path.read_text()
            self.assertIn("development/local/test", text)


if __name__ == "__main__":
    unittest.main()
