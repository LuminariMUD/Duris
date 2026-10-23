#!/usr/bin/env python3
"""Source-contract checks for transaction ownership and commit ordering fixes."""
from _paths import SRC, extract_function
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
locker = (SRC / "storage_lockers.c").read_text()
auction = (SRC / "auction_houses.c").read_text()
auction_repository = (SRC / "auction_repository.c").read_text()
critical_repository = (SRC / "critical_command_repository.c").read_text()
auction_transaction = (SRC / "auction_transaction.c").read_text()
copyover = (SRC / "copyover.c").read_text()
ships = (SRC / "ships/ship_base.c").read_text()

# LockerSave moves inventory via LockerToPFile then hands public SQL to
# the async worker. Sync SQL txn ownership is no longer in this function.
# Private chests still write inside LockerToPFile; public items are queued.
locker_save = locker[locker.index("static int save_locker_char") : locker.index("bool StorageLocker::LockerToPFile")]
assert "LockerToPFile()" in locker_save
assert "locker_async_mark_dirty" in locker_save
assert "save_locker_char-nonterminal" in locker_save
# A save the worker refuses is the caller's failure; nothing saves on the loop instead.
assert "the async locker writer refused the save" in locker_save
assert "writeCharacter" not in locker_save

# Active offer/bid commands submit immutable typed requests without destroying
# live objects. Durable database mutation, inbox/result, and outbox publication
# share one coordinator-owned transaction.
offer_start = auction.rindex("bool auction_offer(")
offer = auction[offer_start : auction.index("static void auction_list_row(", offer_start)]
assert "payload.action = auction_action::list" in offer
assert "auction_transaction_submit" in offer
assert "obj_from_char" not in offer and "extract_obj" not in offer

bid_start = auction.rindex("bool auction_bid(")
bid = auction[bid_start : auction.index("static void auction_pickup_claim(", bid_start)]
assert "payload.action = auction_action::bid" in bid
assert "auction_transaction_submit" in bid

apply_start = critical_repository.index("critical_apply_result critical_command_repository_apply")
apply = critical_repository[apply_start:]
auction_execute = apply.index("auction_repository_execute")
auction_commit = apply.index('execute(connection, "COMMIT")', auction_execute)
assert apply.index('execute(connection, "START TRANSACTION")') < auction_execute
assert auction_execute < apply.index("insert_outbox", auction_execute) < auction_commit

repository_bid = auction_repository[
    auction_repository.index("else if (payload.action == auction_action::bid)"):
    auction_repository.index("else if (payload.action == auction_action::finalize")
]
# The bid locks the auction; the wallet is memory's, so the bid only reports what it charged.
assert "lock_auction" in repository_bid and "apply_wallet_delta" not in repository_bid
assert "wallet_value_delta = -to_pay" in repository_bid

# Live inventory destruction and external broadcast/notification happen only
# after a committed completion or a committed outbox delivery.
list_completion = auction[
    auction.rindex("void auction_list_completed"):
    auction.rindex("void auction_bid_completed")
]
# The listed items leave the inventory at submit; the committed completion extracts them.
assert "obj_from_char" not in list_completion and "extract_obj" not in list_completion
settle = auction_transaction[auction_transaction.index("bool publish(std::unordered_map"):]
assert settle.index("const bool committed") < settle.index("extract_obj(object)")
assert "critical_apply_outcome::applied" in auction_transaction
assert "auction_transaction_publish_outbox" in auction_transaction
publisher = auction[
    auction.rindex("static void auction_publish_event("):
    auction.rindex("// syntax: auction offer")
]
assert "ws_broadcast_auction_bid" in publisher
assert "send_to_pid" in publisher

# Copyover uses a forced drain which ignores retry_after and aborts on failure.
drain = ships[ships.index("bool drain_pending_ship_saves") : ships.index("int read_ships()")]
assert "save_retry_after" not in drain
assert "if (!write_ship(ship))" in drain
assert "drained = false;" in drain
assert "if (!drain_pending_ship_saves())" in copyover
assert "notify_copyover_failure" in copyover[copyover.index("if (!drain_pending_ship_saves())") :]
assert "locker_async_drain" in copyover

# Execute the real lifecycle guards and the game-thread publication wiring.
# The SQL harness separately runs the actual worker concurrently with a draining
# game thread; this probe proves which publishers and caller policies it reaches.
comm = (SRC / "comm.c").read_text()
assert "critical_gameplay_drain_outbox);" in comm
runtime = r'''
#include <cassert>
#include <cstdint>
#include <string>
static bool outbox_empty = false;
static unsigned int resumed = 0, saved = 0, alerts = 0, published = 0, pumped = 0;
static int _pwipe = 0;
static const char *AVATAR = "test", *LOG_STATUS = "test";
void maintenance_scheduler_quiesce() {}
void critical_command_coordinator_quiesce() {}
void critical_outbox_quiesce() {}
void player_save_pipeline_quiesce() {}
void player_save_pipeline_resume() { ++resumed; }
void critical_outbox_resume() { ++resumed; }
void critical_command_coordinator_resume() { ++resumed; }
void maintenance_scheduler_resume() { ++resumed; }
bool maintenance_scheduler_drain(uint64_t) { return true; }
bool critical_command_coordinator_drain(uint64_t) { return true; }
bool critical_outbox_drain(uint64_t timeout) { assert(timeout == 3000); return outbox_empty; }
bool persistence_flush_all_character_saves() { ++saved; return true; }
bool player_save_pipeline_drain(uint64_t) { return true; }
bool locker_async_drain(uint64_t) { return true; }
bool artifact_save_drain(uint64_t) { return true; }
void logit(const char *, const char *) {}
void notify_copyover_failure(const char *) { ++resumed; }
void persistence_alert(const char *, const char *, const char *, const char *,
                       const char *, const char *, const char *policy) {
    assert(std::string(policy) == "shutdown_cancelled=0"); ++alerts;
}
void auction_transaction_publish_outbox() { published |= 1; }
void collector_transaction_publish_outbox() { published |= 2; }
void combat_outcome_transaction_publish_outbox() { published |= 4; }
void artifact_guild_transaction_publish_outbox() { published |= 8; }
void sql_async_pulse() { ++pumped; }
''' + extract_function("account.c", "class account_deletion_drain_guard") + ";\n" + \
    extract_function("comm.c", "static void critical_gameplay_publish_outbox(") + \
    extract_function("comm.c", "static void critical_gameplay_drain_outbox(") + \
    "\nbool copyover_gate() {\n" + extract_function("copyover.c", "if (!critical_outbox_drain(3000))") + \
    "\nreturn true; }\nvoid shutdown_gate() {\n" + \
    comm[comm.index("if (!_pwipe && !critical_outbox_drain(3000))"):
         comm.index("\n\tif (!_pwipe)\n", comm.index("if (!_pwipe && !critical_outbox_drain(3000))"))] + r'''
}
int main() {
    critical_gameplay_drain_outbox(); assert(published == 15 && pumped == 1);
    { account_deletion_drain_guard guard; assert(!guard.drain()); }
    assert(saved == 0 && resumed == 3);
    assert(!copyover_gate()); assert(resumed == 4);
    shutdown_gate(); assert(alerts == 1);
    outbox_empty = true;
    { account_deletion_drain_guard guard; assert(guard.drain()); }
    assert(saved == 1 && resumed == 8);
    assert(copyover_gate()); shutdown_gate(); assert(alerts == 1);
}
'''
(root / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="outbox-lifecycle-", dir=root / "bin/tests") as directory:
    path = Path(directory)
    (path / "probe.cpp").write_text(runtime)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    str(path / "probe.cpp"), "-o", str(path / "probe")], check=True)
    subprocess.run([str(path / "probe")], check=True)

print("transaction ordering, all four outbox publishers, and copyover/account/shutdown drain policies passed")
