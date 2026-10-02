#!/usr/bin/env python3
"""Source contracts for the live ownership ACK boundary."""

from _paths import SRC, extract_function
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
class LiveItemMovementContractTests(unittest.TestCase):
    def test_runtime_hydrates_authoritative_rows_not_relative_events(self):
        sql = (SRC / "sql.c").read_text()
        owner_check = sql[sql.index("static bool sql_persistence_owner_row_matches"):]
        owner_check = owner_check[:owner_check.index("bool sql_hydrate_item_owner_revisions")]
        header = (SRC / "sql.h").read_text()
        select = header[header.index("#define SQL_ITEM_OWNER_COLUMNS"):]
        select = select[:select.index("bool sql_persistence_item_owner_fields_match")]
        self.assertIn("SQL_ITEM_OWNER_SELECT", owner_check)
        self.assertIn("FROM item_current_owner", select)
        self.assertIn("item_owner_revision", select)
        self.assertNotIn("persistence_item_events", owner_check + select)
        self.assertIn("item_ownership_runtime_hydrate", owner_check)

    def test_pending_adapter_retains_scalars_and_publishes_after_commit(self):
        movement = (SRC / "item_movement_transaction.c").read_text()
        pending = movement[movement.index("struct pending_movement"):]
        pending = pending[:pending.index("};")]
        self.assertNotIn("P_obj", pending)
        self.assertNotIn("P_char", pending)
        self.assertIn("critical_command_coordinator_submit", movement)
        self.assertIn("critical_command_coordinator_is_fenced", movement)
        self.assertIn("item_ownership_runtime_apply", movement)
        batch = extract_function("item_movement_transaction.c", "bool submit_grant_batch(")
        self.assertLess(batch.index("movement_conflicts(system_owner_identity, owner)"),
                        batch.index("submit_transfer("))
        self.assertLess(movement.index("const bool committed"),
                        movement.index("item_ownership_runtime_apply"))

    def test_transfer_captures_exact_snapshot_before_submission(self):
        grant = extract_function("item_movement_transaction.c", "bool submit_grant(")
        self.assertLess(grant.index("player_item_snapshot_tree_capture"),
                        grant.index("submit_transfer("))
        transfer = extract_function("item_movement_transaction.c", "bool submit_transfer(")
        encode = transfer.index("player_item_snapshot_list_encode")
        build = transfer.index("item_transfer_command_build")
        submit = transfer.index("critical_command_coordinator_submit")
        self.assertLess(encode, build)
        self.assertLess(build, submit)
        self.assertIn("payload.item_blob_size", transfer)

    def test_death_puts_the_items_in_the_corpse_in_memory(self):
        fight = (SRC / "fight.c").read_text()
        make_corpse = fight[fight.index("P_obj make_corpse"):]
        make_corpse = make_corpse[:make_corpse.index("\nvoid make_bloodstain")]
        self.assertNotIn("submit_next_corpse_item", fight)
        self.assertIn("corpse->contains = ch->carrying;", make_corpse)
        self.assertIn("corpse->weight = GET_WEIGHT(ch);", make_corpse)
        self.assertNotIn("sql_delete_player_items", make_corpse)

    def test_corpse_identity_and_floor_hints_are_non_authoritative(self):
        migration = (ROOT / "migrations/live_item_movement_cutover.sql").read_text()
        baseline = (ROOT / "migrations/baseline_item_ownership.sh").read_text()
        self.assertIn("c.save_id", migration)
        self.assertIn("CAST(pd.pid AS UNSIGNED) << 32", baseline)
        self.assertIn("CAST(c.save_id AS UNSIGNED)", baseline)
        actobj = (SRC / "actobj.c").read_text()
        self.assertNotIn("redis_check_floor_pickup", actobj)
        self.assertNotIn("redis_check_floor_drop", actobj)
        recovery = (SRC / "world_recovery_pipeline.c").read_text()
        self.assertIn("sql_persistence_reconcile_world_recovery_items", recovery)
        self.assertIn("item_ownership_runtime_hydrate_many_atomic", recovery)
        self.assertNotIn("redis_check_floor_pickup", recovery)
        self.assertNotIn("redis_check_floor_drop", recovery)

    def test_reconnect_replays_retained_completion(self):
        for name in ("nanny.c", "account.c"):
            self.assertIn("item_movement_transaction_player_ready", (SRC / name).read_text())

    def test_linkdead_actor_completion_publishes_while_character_is_live(self):
        movement = (SRC / "item_movement_transaction.c").read_text()
        helper = movement[movement.index("P_char find_live_player(uint32_t pid)") :]
        helper = helper[: helper.index("bool creation_grant_request_valid")]
        self.assertIn("character_list", helper)
        completions = movement[
            movement.index("void item_movement_transaction_handle_completions") :
        ]
        completions = completions[
            : completions.index("void item_movement_transaction_player_ready")
        ]
        self.assertIn("find_live_player(found->second.actor_pid)", completions)
        self.assertNotIn("find_player_by_pid(found->second.actor_pid)", completions)

    def test_same_owner_reparenting_is_authoritative(self):
        command = (SRC / "item_transfer_command.c").read_text()
        repository = (SRC / "item_transfer_repository.c").read_text()
        movement = (SRC / "item_movement_transaction.c").read_text()
        self.assertIn("target_root_item_uid", command)
        self.assertIn("target_parent_item_uid", command)
        self.assertIn("const bool same_owner", repository)
        self.assertIn("SET root_item_uid=?", repository)
        self.assertIn("target_container", movement)

    def test_flat_room_grants_are_composite(self):
        repository = (SRC / "flatfile_item_repository.c").read_text()
        world = (SRC / "flatfile_world_item_repository.c").read_text()
        artifact = (SRC / "flatfile_artifact_repository.c").read_text()
        self.assertIn("flatfile_world_item_prepare_room_transfer", world)
        self.assertIn("bool flatfile_artifact_room_transfer_allowed", artifact)
        supported = repository[repository.index("bool generic_transfer_supported") :]
        supported = supported[:supported.index("\n}\n")]
        self.assertIn("room_transfer(payload)", supported)
        apply = repository[repository.index(
            "critical_apply_result flatfile_item_repository_apply") :]
        allowed = apply.index("flatfile_artifact_room_transfer_allowed(payload)")
        prepare = apply.index("flatfile_world_item_prepare_room_transfer", allowed)
        image = apply.index("room.after_image", prepare)
        commit = apply.index("flatfile_authority_transaction_commit", image)
        self.assertLess(image, commit)

    def test_unpublished_commit_is_retained_not_erased(self):
        publish = extract_function("item_movement_transaction.c", "void publish(")
        registry = publish[publish.index("if (committed && !entry.registry_applied)\n\t{"):]
        registry = registry[:registry.index("return;")]
        self.assertIn("++health.stale_publications", registry)
        self.assertNotIn("pending.erase", registry)
        retained = publish[publish.index("if (committed)\n\t{"):]
        self.assertLess(retained.index("queue_found->second.publication_failed"),
                        retained.index("pending.erase(pending_key)"))

if __name__ == "__main__":
    unittest.main()
