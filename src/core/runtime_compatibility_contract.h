/****************************************************************************
 *
 *  File: runtime_compatibility_contract.h                      Part of Duris
 *  Usage: the schema and store set the runtime requires
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef RUNTIME_COMPATIBILITY_CONTRACT_H
#define RUNTIME_COMPATIBILITY_CONTRACT_H

#include <cstddef>

constexpr unsigned RUNTIME_COMPATIBILITY_MANIFEST_VERSION = 1;
constexpr const char *RUNTIME_BASELINE_ID = "duris-schema-2026-08-27-session11";
constexpr const char *RUNTIME_BASELINE_FINGERPRINT =
	"db13d7a42bf82bcbd32bac8d83224913c755fefd000ade6d4e798b1bd4f494dd";
constexpr unsigned RUNTIME_BASELINE_TABLE_COUNT = 170;
constexpr unsigned RUNTIME_CURRENT_TABLE_COUNT = 200;
constexpr const char *RUNTIME_TABLE_SQL_LIST =
	"'account_banks','account_bound_reward_pwipe_state','account_bound_reward_summons',"
	"'account_bound_rewards','account_characters','account_erasure_evidence',"
	"'account_erasure_requests','account_erasure_stores','account_erasure_tombstones','account_ips',"
	"'account_locker_access','account_locker_item_affects','account_locker_item_extra_descr',"
	"'account_locker_items','account_lockers','accounts','alliances','artifact_bind',"
	"'artifact_delta_ledger','artifact_domain_baseline','artifact_domain_state',"
	"'artifact_guild_outcome','artifact_guild_outcome_delta','artifact_mana','artifacts',"
	"'artifacts_mortal','associations','auction_bid_history','auction_item_custody',"
	"'auction_item_pickups','auction_ledger','auction_money_pickups',"
	"'auction_reconciliation_quarantine','auctions','boon_reward_outcome',"
	"'boon_reward_outcome_entry','boons','boons_progress','boons_shop','categories','changes',"
	"'classes','collector_catalog_state','collector_deaths','collector_ledger','collector_listings',"
	"'collector_reconciliation_quarantine','combat_frag_baseline','combat_frag_ledger',"
	"'combat_outcome','combat_outcome_participant','corpse_catalog_state','corpse_item_affects',"
	"'corpse_item_extra_descr','corpse_items','corpses','critical_operation_inbox','critical_outbox',"
	"'critical_outbox_delivery_dedupe','critical_test_state','ctf_data','currency_bank_baseline',"
	"'currency_ledger','currency_wallet_baseline','divine_boon_state','divine_trade_state','epic_balance_baseline','epic_bonus','epic_gain',"
	"'epic_ledger','epic_stone_claim','eq_drop','frag_leaderboard','guild_members',"
	"'guild_outcome_ledger','guild_ranks','guild_transactions','guildhall_rooms','guildhalls',"
	"'guilds','ip_info','item_current_owner','item_owner_audit','item_owner_revision',"
	"'item_ownership_baseline','item_ownership_ledger','item_ownership_quarantine',"
	"'item_uid_allocator','items','kingdom_garrison','kingdom_land','kingdom_realms','level_cap',"
	"'lifecycle_archive_batches','lifecycle_archive_evidence','lifecycle_archive_jobs',"
	"'lifecycle_archive_rows','locker_access','locker_activity_log','locker_chests',"
	"'locker_item_affects','locker_item_extra_descr','locker_items','locker_kickouts',"
	"'locker_session_state','lockers','log_entries','lookup_dataset_state','mud_info',"
	"'mud_schema_baselines','mud_schema_history','mud_schema_migration_state',"
	"'mud_schema_migrations','multiplay_whitelist','nexus_stones','offline_message_receipts',"
	"'offline_messages','outposts','pages','persistence_item_events','persistence_scalar_events',"
	"'personal_data_export_audit','personal_data_export_requests','personal_data_export_sections',"
	"'ping','pkill_event','pkill_info','player_affects','player_data','player_forged_items',"
	"'player_granted_cmds','player_intros','player_item_affects','player_item_extra_descr',"
	"'player_items','player_languages','player_pet_item_affects','player_pet_item_extra_descr',"
	"'player_pet_items','player_pets','player_recipes','player_shapechanges','player_skills',"
	"'player_spellbooks','player_timers','player_undead_slots','player_witnesses','poll_options',"
	"'poll_votes','polls','prepstatement_duris_sql','private_chest_log','private_chests','progress',"
	"'quest_trophy','races','racewar_stat_mods','saved_item_affects','saved_item_extra_descr',"
	"'saved_item_recovery_handoff','saved_items','season_reset_state','server_reboots',"
	"'session_audit_outcome','ship_armor','ship_cargo_market_mods','ship_cargo_prices','ship_crew',"
	"'ship_slots','ships','shop_trophy','shopkeeper_affects','shopkeeper_item_affects',"
	"'shopkeeper_item_extra_descr','shopkeeper_items','shopkeepers','siege_item_affects',"
	"'siege_item_extra_descr','siege_items','statistics','telemetry_cohort_day',"
	"'telemetry_cohort_member','telemetry_config','telemetry_interval','telemetry_player_day',"
	"'telemetry_quarantine','telemetry_reward_projection','telemetry_reward_projection_state',"
	"'telemetry_rollup_session','telemetry_rollup_state','telemetry_session','timers','towns',"
	"'world_quest_accomplished','zone_story_quest_state','zone_touch_outcome',"
	"'zone_touch_outcome_participant','zone_touches','zone_trophy','zones'";
constexpr const char *RUNTIME_MYSQL8_METADATA_FINGERPRINT =
	"f545ac6424f6db7b203c8467ff7f7d4995ece2f2ad1f13ebbc091a7f08d7938c";
constexpr const char *RUNTIME_MARIADB10_11_METADATA_FINGERPRINT =
	"0fb89abdc5bee80b7da76783d3d02167ec694bdedbe28402690ddfbc99f7ff5c";
/* Includes the six telemetry stores introduced by migration 0014, the two
 * rollup stores introduced by migration 0017, the five Collector authority
 * stores introduced by migration 0018, corpse catalog authority introduced by
 * migration 0019, restitution receipt/runtime stores introduced by migration
 * 0020, identity-stable Collector notification receipt/outbox state introduced
 * by migration 0021, additive progression fields introduced by migration
 * 0022, committed reward projection/reconciliation state introduced by
 * migration 0023, bounded encounter lifecycle facts introduced by migration
 * migration 0024, the durable zone-story quest state introduced by migration 0026, and
 * the saved-item recovery receipt introduced by migration 0027, and the durable
 * telemetry quarantine introduced by migration 0030. Migration 0029 adds the
 * additive critical-operation failure stage; it changes no runtime table count.
 * Migration 0033 adds the item owner audit a save writes when it takes an item, and
 * migration 0034 drops the death custody, restitution and economy accounting tables
 * (including those 0011, 0020, 0031 and 0032 added). Migration 0035 backfills the bank
 * opening baselines bank deltas did not write; it changes no table. Migration 0036 widens
 * log_entries.ip_address to VARCHAR(45) for IPv6 addresses. Migration 0037 adds
 * immutable account identity and staff status to session audit outcomes. Migration 0038
 * adds the learned flight stops mask to player status. Migration 0039 adds
 * level_cap.level_good and level_evil, the levels unlocked by each side.
 * Migration 0040 records the killer-side ally count on combat outcomes.
 * Migration 0041 widens legacy pkill_info.log columns for full public combat logs.
 * Migration 0042 widens all ten player base stats to signed shorts.
 * Migration 0044 adds canonical artifact UID/state without replacing the custody FK.
 * Migration 0045 adds nullable capture permission to PvP participant snapshots.
 * Migration 0046 seeds two Nexus catalogue rows; structural fingerprints are unchanged.
 * Migration 0047 retains rejected artifact UIDs across canonical generations.
 * Migration 0048 adds revision-checked Divine Boon rotation state.
 * Migration 0049 checkpoints prepared Divine award delivery with player status.
 * Migration 0050 stores exact Divine trade manifests and the market generation.
 * Fingerprints are measured on MySQL 8 and MariaDB 10.11. */
constexpr const char *RUNTIME_MIGRATION_HEAD_ID = "0050_divine_trade_state";
constexpr unsigned RUNTIME_MIGRATION_HEAD_SEQUENCE = 51;
constexpr const char *RUNTIME_MIGRATION_APPLY_CHECKSUM =
	"3657f30c78faea6b728e456220c62737aceea2e44968d0e1b88d27e57674861c";
constexpr const char *RUNTIME_MIGRATION_VERIFY_CHECKSUM =
	"6e580109ffc73d3e1e82493c1b6b9b4df5dad38fbb9a244de1c7b2e1f53b9508";
constexpr const char *RUNTIME_MIGRATION_HISTORY_CHECKSUM =
	"905d1c505fc3d2f41e5eb26e6835e5f56a169a2b7825e09ef126ceef03a170d8";
constexpr const char *LOOKUP_DATASET_NAME = "race_class";
constexpr unsigned LOOKUP_DATASET_VERSION = 1;
constexpr const char *RUNTIME_DB_CHARACTER_SET = "utf8mb4";
constexpr const char *RUNTIME_DB_TIME_ZONE = "+00:00";
constexpr const char *RUNTIME_DB_ISOLATION = "READ-COMMITTED";
constexpr const char *RUNTIME_DB_SQL_MODE =
	"STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION";
constexpr unsigned RUNTIME_DB_TIMEOUT_SECONDS = 10;
constexpr bool RUNTIME_DB_REMOTE_TLS_REQUIRED = true;
constexpr size_t RUNTIME_METADATA_MAX_BYTES = 4 * 1024 * 1024;

#endif
