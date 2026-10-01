#!/usr/bin/env python3
"""Source and schema contracts for transactional player/account currency."""

from _paths import SRC
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
class CurrencyTransactionContractTests(unittest.TestCase):
    def test_schema_baselines_and_operator_tools_are_wired(self):
        migration = (ROOT / "migrations/currency_ledger.sql").read_text()
        bootstrap = (ROOT / "migrations/bootstrap_multithread_safe.sql").read_text()
        runner = (ROOT / "migrations/run_migration.sh").read_text()
        for token in (
            "wallet_revision",
            "bank_revision",
            "currency_wallet_baseline",
            "currency_bank_baseline",
            "currency_ledger",
            "uq_currency_wallet_revision",
            "uq_currency_bank_revision",
            "currency_ledger_operation_fk",
        ):
            self.assertIn(token, migration)
            self.assertIn(token, bootstrap)
        self.assertIn("currency_ledger.sql", runner)
        self.assertIn("verify_currency_ledger_schema.sh", runner)
        for script in (
            "baseline_currency_balances.sh",
            "reconcile_currency_balances.sh",
            "verify_currency_ledger_schema.sh",
        ):
            self.assertTrue((ROOT / "migrations" / script).stat().st_mode & 0o111)

    def test_command_is_fixed_typed_bounded_and_revisioned(self):
        header = (SRC / "currency_command.h").read_text()
        implementation = (SRC / "currency_command.c").read_text()
        self.assertIn("CURRENCY_COMMAND_PAYLOAD_BYTES = 136", header)
        self.assertIn("std::array<int64_t, CURRENCY_DENOMINATION_COUNT>", header)
        self.assertIn("atm_deposit", header)
        self.assertIn("auction_pickup", header)
        self.assertIn("ship_insurance", header)
        self.assertIn("std::numeric_limits<int64_t>::min()", implementation)
        self.assertIn("command.expected_revisions.size() == 2", implementation)

    def test_atm_and_audited_producers_use_the_ack_boundary(self):
        atm = (SRC / "actoth.c").read_text()
        utility = (SRC / "utility.c").read_text()
        auction = (SRC / "auction_houses.c").read_text()
        boon = (SRC / "boon.c").read_text()
        ship = (SRC / "ships/ship_base.c").read_text()
        self.assertNotIn("deposit_carried_coin", atm)
        self.assertIn("currency_reason_type::atm_deposit", atm)
        self.assertIn("currency_reason_type::atm_withdraw", atm)
        deposit_all = atm[atm.index('if (strstr("all", argument))') : atm.index("half_chop", atm.index('if (strstr("all", argument))'))]
        self.assertEqual(1, deposit_all.count("currency_transaction_submit("))
        self.assertIn("currency_transaction_submit_bank_payment", utility)
        self.assertIn("currency_transaction_submit_wallet_value", utility)
        self.assertIn("currency_reason_type::auction_pickup",
                      (SRC / "auction_transaction.c").read_text())
        self.assertIn("currency_reason_type::boon_reward", boon)
        self.assertIn("currency_reason_type::ship_insurance", ship)

    def test_transactions_apply_in_memory_and_complete_at_once(self):
        transaction = (SRC / "currency_transaction.c").read_text()
        self.assertNotIn("critical_command_coordinator_submit", transaction)
        self.assertNotIn("pending", transaction)
        self.assertIn("completion(character, true, result, 0, bytes, context_size);", transaction)
        self.assertIn("completion(character, false, {}, ENOSPC, bytes, context_size);", transaction)
        self.assertIn("mark_player_dirty_components(GET_PID(character), PLAYER_COMPONENT_STATUS);",
                      transaction)

    def test_the_save_writes_the_wallet(self):
        capture = (SRC / "player_snapshot_capture.c").read_text()
        replay = (SRC / "player_snapshot_repository.c").read_text()
        flatfile = (SRC / "flatfile_player_repository.c").read_text()
        apply_status = replay[replay.index("query_result apply_status("):
                              replay.index("template <typename Row, typename Append>")]
        # The save writes the wallet, epic points and frags memory holds.
        for field in ("copper", "silver", "gold", "platinum", "epics", "frags", "old_frags"):
            self.assertIn(f"ADD_STATUS({field},", capture)
            self.assertNotIn(f"row.field == player_status_field::{field}", apply_status)
        self.assertIn("flatfile_player_domain_prepare_saved_balances(", flatfile)

    def test_no_legacy_bank_delta_helper_remains_in_gameplay(self):
        call = re.compile(r"sql_account_bank_(?:deposit|withdraw)(?:_balances|_value)?\s*\(")
        violations = []
        for path in SRC.rglob("*.c"):
            if path.name == "sql_player.c":
                continue
            for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if call.search(line):
                    violations.append(f"{path.relative_to(ROOT)}:{number}:{line.strip()}")
        self.assertEqual([], violations)

    def test_player_currency_mutations_are_centralized(self):
        assignment = re.compile(
            r"GET_(?:COPPER|SILVER|GOLD|PLATINUM)\([^)]*\)\s*(?:[+\-]=|=(?!=))"
        )
        allowed = {
            "currency_transaction.c",  # game-thread ACK publication
            "files.c",                 # format-compatible import parsing
            "nanny.c",                 # new-character initialization
            "sql_player.c",            # authoritative hydration
            "player_load_materialize.c",  # authoritative worker snapshot hydration
            "utility.c",               # NPC fallback in central adapters
            "mobconv.c",               # NPC construction
            "db.c",                    # NPC construction
            "copyover.c",              # NPC restoration
            "generated_npc_runtime.c",  # generated NPC restoration
            "smagic.c",                # summoned NPC setup
            "necromancy.c",            # summoned NPC setup
            "random.mob.c",            # NPC construction
            "actnew.c",                # NPC construction
            "nexus_stones.c",           # NPC construction
            "guildhall_rooms.c",       # NPC construction
            "specs.mobile.c",           # NPC vendor/undead balances
            "training_dummy.c",          # training NPC construction
        }
        generated_npc_restoration = {
            "GET_COPPER(pet) = wallet[0];",
            "GET_SILVER(pet) = wallet[1];",
            "GET_GOLD(pet) = wallet[2];",
            "GET_PLATINUM(pet) = wallet[3];",
        }
        violations = []
        for path in SRC.rglob("*.c"):
            if path.name in allowed:
                continue
            relative = path.relative_to(SRC).as_posix()
            for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if line.lstrip().startswith("//"):
                    continue
                if (
                    relative == "world/generated_npc_runtime.c"
                    and line.strip() in generated_npc_restoration
                ):
                    continue
                if assignment.search(line):
                    violations.append(f"{path.relative_to(ROOT)}:{number}:{line.strip()}")
        self.assertEqual([], violations)

    def test_bank_changes_reach_every_online_character_and_the_writer(self):
        transaction = (SRC / "currency_transaction.c").read_text()
        utility = (SRC / "utility.c").read_text()
        comm = (SRC / "comm.c").read_text()
        nanny = (SRC / "nanny.c").read_text()
        worker = (SRC / "player_save_worker.h").read_text()
        self.assertIn("publish_account_bank_balances_revision", transaction)
        self.assertIn("for (P_desc desc = descriptor_list", utility)
        self.assertIn("persistence_writer_submit(persistence_job_kind::bank", transaction)
        self.assertIn("bank,", worker)
        # The save of the side the money leaves is queued first.
        apply = transaction[transaction.index("bool apply(P_char character"):]
        self.assertLess(apply.index("if (bank_loses)\n\t\tqueue_bank_delta"),
                        apply.index("currency_transaction_save_first(character);"))
        self.assertLess(apply.index("currency_transaction_save_first(character);"),
                        apply.index("if (!bank_loses)\n\t\t\tqueue_bank_delta"))
        self.assertNotIn("currency_transaction_handle_completions", comm)
        self.assertNotIn("currency_transaction_player_ready", nanny)

    def test_world_status_reports_in_memory_counts(self):
        world_status = (SRC / "cmd/actinf.c").read_text()
        self.assertFalse((SRC / "economy/currency_publication.h").exists())
        self.assertIn("currency_transactions state=ready submitted=%llu committed=%llu "
                      "rejected=%llu \"\n\t\t \"bank_deltas=%llu", world_status)


if __name__ == "__main__":
    unittest.main()
