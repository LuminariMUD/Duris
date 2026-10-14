# Production update inventory

An update from `origin/master` can require a server build, pending immutable
migrations, content imports, configuration changes, and updates to installed
services. Pulling the repository alone performs none of those operations. Use
the changed files and the database's recorded migration history to select the
steps below; do not run every script or SQL file in the repository.

This inventory covers the native production MUD and its integration points.
DurisWeb has its own repository and deployment procedure. The current host uses
`systemctl --user`, as recorded in [Production deployment](PRODUCTION_DEPLOYMENT.md).
This is a catalog for selecting required update work, not an instruction to run
every tool or enter maintenance. It does not itself authorize production changes.

For assisted execution, use the repository's
[`deploy-production` skill](../../.agents/skills/deploy-production/SKILL.md).
It completes preparation with services running and hands the user the in-game
REBOOT command. The user activates the release. Copyover applies only when
explicitly requested. Service outages require a separate maintenance task.

## Historical inspection before the 2026-10-12 deployment

The following snapshot predates the completed release preparation. It is not
current production state or a pending-work list; inspect live processes, artifacts
and migration history for each deployment.

| Item | Read-only observation |
| --- | --- |
| Production checkout | `/home/staging/duris`, branch `master`, commit `6b9845556ea6fcd7e3ef29b911c83906933de181` |
| Remote master | `2f8cafbe6351b698685ce2d2824f367e1c2d48c1`; the additional commit changes only two documentation files |
| Running service | User unit `duris-mud-production.service`, active, with this checkout as its working directory |
| Persistence role | `ENVIRONMENT=production`, `PERSISTENCE_MODE=mariadb-primary` |
| Recorded database baseline | `duris-schema-2026-08-27-session11`, adopted as `fresh_bootstrap` |
| Recorded database head | `0038_learned_flight_stops`, applied count 38 |
| Required repository head | `0039_level_cap_sides`, 39 migrations, 198 runtime tables |
| Runtime compatibility check | Failed against the current checkout: metadata fingerprint, migration head, and migration state differ |

At this inspection, migration 0039 was pending before starting the new code. It adds
`level_cap.level_good` and `level_cap.level_evil`, both defaulting to zero, so
existing caps remain unchanged until a side unlocks another level. The same
release changes `lib/frag_cap.cfg` and the server code. Deploy those together.
The running process's source revision was not established by the checkout SHA.

The additional documentation-only remote commit created no new deployment
requirement, but it did not remove the then-pending 0039 requirement.
Recheck the database head and remote SHA before the actual update.

The migration manifest, compiled compatibility contract, epic-zone seed, and
racial innate help source checks passed. No production migration, import,
backup, rebuild, service restart, or configuration change was performed for
this inventory.

## Steps to evaluate on every update

| Trigger | Required action | Automation and limits |
| --- | --- | --- |
| Every release | Record the deployed revision, inspect the incoming diff, preserve unrelated local changes, and update with a fast-forward pull | There is no native production deploy command that coordinates all steps below |
| Before production mutation | Preserve the running executable and matching build stamp; take a verified full persistence backup | `scripts/backup_pfiles.sh`; use the actual live schema contract. Restore/qualification drills are separate work |
| `src/`, its Makefile, compiler flags, linked dependencies, or compatibility header changed | `make -C src PERSISTENCE_BACKEND=mariadb BUILD_PROFILE=production` | Stages `bin/server/dms_new` and its `mariadb/production` stamp |
| `areas/src/` or generator build inputs changed | `make -C areas/src` | The launcher only rebuilds generators when an executable is missing; existing binaries can otherwise remain stale |
| Area sources, `areas/AREA`, generation scripts, or lookup inputs changed | Build matching generators and prepare the complete world/lookups before the handoff | Normal boot runs `m_slow` again; install matching generators so it reproduces the prepared world |
| New immutable migration IDs | Select a supported runner path, back up, apply pending steps, then run `migrations/verify_runtime_compatibility.sh` | Check supported online paths before declaring an outage necessary. Production startup verifies but does not migrate |
| Help, news, MOTD, or other imported information changed | Preview and run `scripts/import_help_to_prod.sh`; use `--news-only` when appropriate | A Git pull or restart does not import database-backed content |
| `.env.example`, runtime config, properties, feature catalogs, or security requirements changed | Review the difference against the protected production settings and preserve intentional overrides | Git does not update ignored `.env`; feature activation and credentials are separate from schema migration |
| Service or timer definitions changed | Review/update installed user units, validate them, and run `systemctl --user daemon-reload` as appropriate | Pulling a template does not update installed copies. A required MUD/website restart or new launcher is outside the skill's pre-reboot boundary |
| Dependency manifest changed | Review `packaging/duris-build-deps.equivs` and provision the needed packages or host-compatible equivalents before building | Package installation on the shared host may require its owner; it is not part of every pull |
| Release preparation is ready | Install the verified next-boot binary last, verify readiness and hand the user `shutdown reboot <reason>` | In the current launcher, ordinary reboot executes `dms`; `dms_new` is promoted only on exits 53/57. The skill does not reboot or wait for activation |

Plain `make`, `make build-server`, and `make test-db` stage a development server.
`make build-production` builds a separate validation executable under
`bin/server/production/dms_new`; the launcher does not promote that path.
Use the explicit `make -C src ... BUILD_PROFILE=production` command above for
the production staging path, after any tests that overwrite that path.

`scripts/start_mud.sh` prefers the local `duris-mud.service`, then falls back to
`nohup`. Operate the existing production user service directly instead of
starting a second launcher.

## Production preparation sequence

1. Record the currently deployed source revision, executable bytes and stamp,
   configuration, database head, and enabled jobs. Fetch and inspect the
   release diff, including deleted files. Preserve the executable and live
   schema contract in private recovery storage outside `bin/`.
2. Integrate the pinned release in a preparation workspace, preserving unrelated
   edits. Prepare the production binary/stamp, area tools, full world/lookups,
   callback map, help/news, configuration and required job updates. Reuse evidence
   for unchanged inputs. Broad tests, synthetic databases and restore drills are
   outside the deployment workflow; do not wait for CI.
3. Take a verified full backup under the actual live contract before schema or
   content mutation. Complete required migrations through a supported online path
   when its prerequisites hold. Verify ordered history/state and the new runtime
   contract. Coordinate backup jobs around DDL and restore their schedules.
   A genuine stopped-client or new-launcher requirement must be reported before
   promising reboot readiness; the skill does not take over maintenance.
4. Publish the reviewed checkout, configuration, required content and jobs,
   generated world/lookups, tools and callback map. Verify stored help/news bytes
   and installed file hashes. Keep the news clear about rules awaiting reboot.
5. After prerequisites pass, install the candidate at the actual next-boot path
   last. For ordinary reboot, atomically replace `bin/server/dms` while preserving
   its running inode, permissions and matching production stamp. Preserve and
   withdraw obsolete promotion candidates. Verify the installed candidate and
   unchanged running PID/executable separately.
6. Verify production configuration, live schema, backups, schedules and local/
   public health. After schema/content changes, verify a new full backup under
   the new contract too. Hand the user the in-game reboot command and finish.
   Activation verification is a separate follow-up after the user's reboot.

For a separately requested outage, consult [RUNBOOK.md](RUNBOOK.md) and the host
deployment record. Those stop/start procedures do not extend the skill's scope.

An executable rollback also needs a compatible database. Older binaries can
reject a newer schema even when the SQL change was additive, because the boot
contract checks the exact head and metadata. The runner provides no automatic
down-migration. Preserve compatible schema and executable recovery evidence;
do not automatically restore an old executable against an upgraded database.

### Backup contract during an upgrade

`scripts/backup_pfiles.sh` calls `scripts/persistence_backup.py` and defaults to
the `backup` command. It captures full policy-governed generations, including
`database.sql.gz`, runtime schema identity, and configured filesystem evidence.
The wrapper's `status --require-drill`, `schedule`, `finalize`, `restore`, and
`drill` commands serve different purposes; restore and drill create isolated
candidates rather than promoting production.

The backup verifies the live database against the selected runtime schema
manifest before and after capture. **After pulling a new schema contract, a
pre-migration backup needs the old deployed contract.** Supply a preserved,
owner-only copy through:

```bash
RUNTIME_COMPATIBILITY_MANIFEST=/absolute/private/deployed-runtime-schema.json \
  ./scripts/backup_pfiles.sh
```

For example, a checkout requiring 0039 cannot validate a database still at 0038.
Do not edit the new contract to make it pass. Scheduled backups using the
new default manifest are subject to the same mismatch until the upgrade is
completed or their selected contract is explicitly managed.

`PREBOOT_BACKUP=1` enables launcher backups; the default is off. Hourly timers
are not proof that a fresh pre-change backup succeeded. The recorded host follow-ups
include an off-host replica, restore drill, and a connected failure alert whose mail
was blocked by Plesk; see the [deployment tracker](PRODUCTION_DEPLOYMENT.md#host-follow-ups)
and [Backup operations](BACKUPS.md#separateoff-host-storage). Completion of those
follow-ups has not been verified in this inventory.

### Supported production migration invocation

The Python runner reads exported environment variables; it does not load
`.env` itself. `MIGRATION_ENV_FILE` belongs to selected shell tools and is not
an environment-file option for this runner. In an authorized window, after
loading the protected production configuration, its default production path
requires zero other database connections:

```bash
set -a
source .env
set +a
python3 scripts/migration_runner.py run \
  --confirm-production-target "$DB_HOST/$DB_NAME" \
  --production-backup /absolute/private/verified-generation/database.sql.gz
./migrations/verify_runtime_compatibility.sh
```

The confirmation is the exact `HOST/DB` pair; `DB_PORT` separately selects the
port. The same pair must be in `DB_ALLOWED_TARGETS`. The backup must be an
absolute, owner-only regular gzip file, owned by the invoking user, no older
than two hours, and identify the configured database and core Duris tables.
Isolated restore qualification is separate work, not a requirement for the
skill's pre-reboot handoff.

For the reviewed 0039 addition, the runner also supports
`run --online-level-cap-sides` with the same target and backup flags. It requires
the exact sealed manifest ending at 0039, MariaDB 11.8/InnoDB, compatible running
writers and coordinated backup jobs; it enforces instant DDL, bounded lock waits
and a held advisory lock. Follow
[IMMUTABLE_MIGRATIONS.md](../persistence/IMMUTABLE_MIGRATIONS.md).
Check the current runner and history before selecting this path. A pending
migration alone is not evidence that services must stop; the default path's
zero-client guard still applies where no supported online path exists.

`python3 scripts/migration_runner.py inspect` validates and summarizes the
checked-in manifest without connecting. It does **not** report pending live
migrations. Determine pending IDs from `mud_schema_history` and
`mud_schema_migration_state`; `run` validates the applied prefix and applies
only the remainder. Do not execute immutable SQL by hand: that omits the
verification and history recording needed by the boot gate.

Production baseline adoption is not supported by the runner. A production
database without the adopted baseline needs a separately rehearsed migration
plan; neither `adopt` nor the legacy runner is a routine escape hatch.

## Complete immutable migration inventory

Each ID below has an apply `.sql` and a verifier `.sh` under
[`migrations/immutable/`](../../migrations/immutable/). The authoritative order
and checksums are in [migration_manifest.json](../../migrations/migration_manifest.json).
Use the runner for every pending ID, including intermediate steps that a later
migration supersedes.

| ID | Change |
| --- | --- |
| `0001_lookup_dataset_state` | Atomic race/class lookup dataset state |
| `0002_player_item_metadata_uniqueness` | Deduplicate and constrain item descriptions and affects |
| `0003_season_reset_state` | Durable season epoch and reset fence |
| `0004_server_reboots` | Reboot records; converts the older launcher table when present |
| `0005_level_cap_singleton` | Required level-cap singleton |
| `0006_kingdom_realms` | Guild territory/upkeep table and legacy collation convergence |
| `0007_pkill_event_stamp_contract` | Portable timestamp default and old zero-date normalization |
| `0008_statistics_date_index` | Population time-series index |
| `0009_kingdom_garrison` | Purchased guard roster |
| `0010_coin_custody_payload` | Committed coin-pile payloads |
| `0011_player_death_disposition` | Death disposition/custody evidence, later retired by 0034 |
| `0012_epic_stone_claim` | Atomic stone reward claims |
| `0013_pet_restore_state` | Generated pet restore state |
| `0014_telemetry_storage` | Telemetry facts, projections, and rollup stores |
| `0015_output_preferences` | Saved character color and reduced-motion preferences |
| `0016_artifact_mana` | Independent per-item mana persistence |
| `0017_telemetry_rollup_support` | Session/cohort rollup support |
| `0018_collector_catalog` | Collector catalog custody and audit |
| `0019_corpse_lifecycle_authority` | Corpse lifecycle revision authority |
| `0020_player_death_restitution` | Restitution receipts/fences, later retired by 0034 |
| `0021_collector_notification_identity` | Stable notification identity and recovery |
| `0022_telemetry_progression` | XP/level progression facts |
| `0023_telemetry_reward_projection` | Committed reward projections/reconciliation |
| `0024_telemetry_encounters` | Encounter lifecycle and participant effort |
| `0025_telemetry_combat_summaries` | Combat contribution and casting summaries |
| `0026_zone_story_quest_state` | Quest completion and daily state |
| `0027_saved_item_recovery_handoff` | Saved-item recovery handoff and nested-key lookup |
| `0028_pet_custody` | Durable pet UID and custody owner type |
| `0029_critical_failure_stage` | Terminal failure stage on critical receipts |
| `0030_telemetry_quarantine` | Record-specific telemetry failure quarantine |
| `0031_economy_accounting` | Economic evidence/identity tables, later retired by 0034 |
| `0032_economic_baseline` | Economic baseline witness/reservation tables, later retired by 0034 |
| `0033_item_owner_audit` | Audit records when saves change item ownership |
| `0034_retire_death_custody_and_accounting` | Drops 18 retired tables and an accounting index; data-destructive |
| `0035_backfill_bank_baselines` | Insert missing account-bank opening baselines without replacing existing ones |
| `0036_log_entries_ipv6` | Widen stored log IP addresses to 45 characters |
| `0037_session_audit_identity` | Capture account identity/staff status in session outcomes |
| `0038_learned_flight_stops` | Persist character flight discoveries |
| `0039_level_cap_sides` | Independent good/evil unlocked level caps; pending at inspection |
| `0040_combat_outcome_allies` | Record killer-side ally counts for level-cap eligibility; required before the updated server boots |
| `0041_pkill_log_capacity` | Widen legacy PvP logs to MEDIUMTEXT; preserve history and require the new migration head before boot |

Migration 0041 uses the normal offline migration path; the narrowly scoped 0040
online option does not authorize it. Qualify the legacy upgrade on a disposable
database, then apply 0041 with stopped writers and the usual production target and
backup safeguards before installing the updated server.

Migration 0040 is additive and rerunnable. Its reviewed
`run --online-combat-outcome-allies` path applies only to a manifest ending at
0040, not the current 0041 head. Use the offline path above for this release.
See [IMMUTABLE_MIGRATIONS.md](../persistence/IMMUTABLE_MIGRATIONS.md).
Existing outcomes keep count 0 (unknown) and cannot unlock a
level; new outcomes retain the count so maintenance can apply the current share
threshold. The separate online 0039 option does not cover 0040.

The two additional files `0031_economy_accounting_mariadb_11_8.sh` and
`0032_economic_baseline_mariadb_11_8.sh` are engine-specific verifiers selected
by the manifest/runner. They are not extra migrations. Do not run every old
verifier against the final schema: 0034 intentionally removes structures that
earlier verifiers expected.

## Content and configuration outside schema migrations

| Surface | Script or action | When it applies |
| --- | --- | --- |
| Help and information | `scripts/import_help_to_prod.sh --local --dry-run`, followed by the reviewed `--local` import | Changes to imported `lib/information/*`, `lib/information/help_index`, or `help/duris_help_parsed.hlp` |
| News only | Same importer with `--news-only --dry-run`, then `--news-only` | Only `lib/information/news` needs publication; plain in-game `page` reloads news/MOTD/wizmotd |
| Help/info caches | In-game `page help` and `page info`; inspect their status/generation | After import when immediate visibility is needed; these caches also refresh periodically |
| Full help replacement | Importer's `--clean` option | Explicit replacement only; it deletes existing help entries inside the import transaction and is not a normal default |
| Racial innate help | `scripts/sync_race_innate_help.py --check`; generator without `--check` updates tracked help | Source preparation when racial innates change; publish through the help importer afterward |
| Help parser | `scripts/parse_help_index.py` | Parser/source inspection helper; despite its docstring, its current CLI prints parsed entries and does not import them |
| Epic-zone payouts | `scripts/epic_zone_seed.py check`, `sql-audit`, and reviewed `sql-apply --database ... --server-stopped` | Fresh setup or proven missing/default payout data; generated SQL must then be explicitly executed |
| Properties and gameplay configuration | Review `lib/duris.properties`, `lib/*.cfg`, `lib/item_abilities.json`, and relevant `lib/creation/*`/`lib/misc/*` | Load by restart or the subsystem's documented reload; preserve production balance and feature choices |
| Environment and dependencies | Review `.env.example`, `docs/operations/CONFIGURATION.md`, `packaging/duris-build-deps.equivs` | New required variables, TLS/ACL identities, credentials, paths, libraries, or listener behavior |
| Race/class lookup rows | Normal boot publication | The server checks the compiled dataset and transactionally publishes changes; no separate lookup SQL replay |
| Zone metadata | Normal world load | Boot updates zone metadata; this does not substitute for the payout seed |
| Callback names | `scripts/event_names.sh` | Launcher generates `lib/misc/event_names` from the active executable; match it when deploying code through another path |
| Area tooling | `areas/m_slow` invokes `make_all`, `moveall`, `make_lookup`; `areas/m_quick` is a builder alternative | Normal full-world boot already uses `m_slow` |

For the help importer, `--local` means a direct database connection using this
checkout's configuration. It does not mean a development target: on this host
it reaches production.

The epic seed is independent of migration history. It inserts known missing
zones or repairs exact default `(epic_payout=0, suggested_group_size=1)` pairs,
preserves other overrides, and leaves unresolved/disabled zones alone. An
intentional default-shaped exclusion needs operator review. Do not replay
`migrations/epic-zone-payout.sql`, which has broader historical update semantics.
See [Epic-zone seed](EPIC_ZONE_SEED.md).

Feature schemas do not imply feature activation. Item abilities, telemetry,
donations, Redis world recovery, SMTP, and similar integrations may require
their own configuration, identities, grants, or rollout steps. Follow the
owning guide, including [Item ability rollout](ITEM_ABILITY_ROLLOUT.md) and
[Configuration](CONFIGURATION.md).

## Installed jobs and host integration

| Component | Inventory and update requirement |
| --- | --- |
| MUD supervisor | `scripts/cycle_mud.sh`, `deploy/systemd/duris-mud-production.service.in`, `scripts/install-production-service.sh`. The installer targets `/etc/systemd/system`; the current host instead uses its adapted user unit. Preserve that distinction when updating it. |
| Persistence backup jobs | `deploy/systemd/duris-backup-{backup,health,drill}.{service,timer}` and `scripts/backup_policy.example.json`. The templates use a dedicated system account and `/opt/duris`; preserve the shared host's user-unit paths and supported options. Pulling the policy example does not update the active policy. |
| Daily login statistics | `scripts/login_stats_export.py` and `deploy/systemd/duris-login-stats.{service,timer}`. Requires migration 0037, protected `LOGIN_STATS_DB_*` credentials, SELECT access to `session_audit_outcome`, and the output directory served by DurisWeb. Install/update units and enable the timer if this feature is being deployed; it is not launched by MUD boot. See [Login statistics](LOGIN_STATS.md). |
| Telemetry rollups | `scripts/telemetry/rollup.py` exposes `run`, `publish`, and report operations; `reward_projection.py` has a separate projection job. These require dedicated roles/configuration and scheduling when used. Schema migrations alone do not provision users/grants or run the jobs. |
| Telemetry reporting/support | `scripts/telemetry/report.py`, `outage.py`, `studies/rested_bonus.py`, `balance/recommend.py`, `balance/application.py`, `benchmark_272.py`, and the definition/engine/DB modules. Reporting, analysis, and reviewed balance work; no blanket post-pull invocation. |
| Website, tunnel, watchdog, TLS renewal | Managed outside this repository's MUD install script. Coordinate shared database downtime with DurisWeb. Do not replace the production certificate with `scripts/generate_localhost_cert.sh`. |
| Static project website | `site/` and `.github/workflows/pages.yml` build/publish the GitHub Pages documentation site. They are separate from the production MUD and the DurisWeb application. |
| Docker | `scripts/init_docker_env.sh`, `deploy/docker/entrypoint.sh`, Compose/Docker build files. The local Docker entrypoint imports fresh help, adopts the baseline, and runs immutable migrations; this is not the native production deployment path. |
| Older monitoring | `scripts/duris_players` is an inherited Munin plugin with a hard-coded development target. It is not a required production update job. |

## Legacy schema and conversion inventory

These files are for fresh provisioning, legacy convergence, or specific
historical conversions. They are not a second list to run after the immutable
runner on an already-adopted production database.

| Files under `migrations/` | Purpose and boundary |
| --- | --- |
| `bootstrap_multithread_safe.sql` | Authoritative sealed fresh schema; empty database only, followed by baseline adoption and immutable migrations |
| `run_migration.sh`, `adopt_migration_baseline.sh` | Legacy convergence with 145 declared progress steps, then adoption/current-head handling; rehearse on an isolated clone |
| `bootstrap_legacy_baseline.sql`, `pfile_to_db_initial_schema.sql`, `pfile_to_db_combined_migration.sql`, `legacy_schema_convergence.sql`, `schema_lookup_tables.sql` | Legacy schema/import foundations and metadata convergence |
| `schema_migration_v2.sql`, `schema_migration_v3_lockers.sql`, `schema_migration_v4_accounts.sql`, `schema_migration_v7_player_fixes.sql`, `schema_migration_v8_hardcore.sql`, `schema_migration_v8_unique.sql`, `schema_migration_v9_dirty_saves.sql`, `schema_migration_v10_pets.sql`, `schema_migration_v11_obj_uid.sql`, `schema_migration_v11_remove_players_core.sql`, `schema_migration_v13_locker_sort.sql`, `schema_migration_v14_locker_bitvectors.sql`, `schema_migration_v15.sql` | Historical versioned changes; names are not the current deployment ordering contract |
| `retired/schema_migration_v5_ships.sql`, `retired/schema_migration_v6_guilds.sql` | Explicitly retired migrations |
| `player_save_revision.sql`, `account_bound_rewards.sql`, `persistence_contract.sql`, `corpse_persistence_state.sql`, `critical_command_inbox_outbox.sql` | Baseline persistence/reward/receipt schema |
| `item_ownership_ledger.sql`, `shopkeeper_item_owner.sql`, `collector_item_owner.sql`, `live_item_movement_cutover.sql`, `locker_ownership_cutover.sql`, `auction_transactional_cutover.sql` | Baseline item custody, ownership, and auction contracts |
| `epic_ledger_balance.sql`, `currency_ledger.sql`, `combat_outcome.sql`, `artifact_guild_outcome.sql`, `boon_reward_zone_outcome.sql`, `session_audit_outcome.sql` | Baseline balance and domain outcome contracts |
| `lifecycle_archive_execution.sql`, `personal_data_export.sql`, `account_erasure.sql`, `immutable_migration_ledger.sql`, `create_polls_tables.sql` | Baseline lifecycle/history/poll schemas; creating tables does not enable lifecycle mutation |
| `epic-zone-payout.sql`, `seeds/epic_zone_payouts.json` | Historical payout input and current source-derived seed manifest; use the guarded seed workflow above |
| `migration_manifest.json`, `runtime_compatibility_manifest.json`, `data_lifecycle_manifest.json` | Migration history, runtime schema, and lifecycle contracts; not executable migrations |
| `tools/Makefile` and `tools/migrate_*.c`/`.h` | Build `bin/migrations/migrate_pfiles` and `migrate_locker_affects` for explicitly selected legacy data conversions |
| `tools/pfile_converter.c` | Build `bin/migrations/pfile_converter` for historical endian conversion |

**The legacy runner does not enforce a production-role/target refusal before
its first SQL statements.** Its help describes a local development operation,
but the script loads configured credentials and executes SQL before reaching
the guarded adoption helper. A late refusal does not undo the earlier DDL.
Do not use it as a production updater or test its safety by running it there.
Its final Redis cleanup is also a local-only tool.

Similarly, a historical SQL comment saying “safe for production” is not proof
that it is compatible with the current ledger or approved for replay.

## Conditional data repair and diagnostics

Run these only when a specific upgrade rehearsal or incident demonstrates the
matching data condition. Preserve their target guards and evidence requirements.

| Tool | When it is relevant |
| --- | --- |
| `migrations/apply_persistence_contract.sh` | Explicit legacy persistence contract application, with an exact database confirmation; not a modern recurring update |
| `migrations/apply_live_item_movement_cutover.sh`, `apply_locker_ownership_cutover.sh`, `apply_auction_transactional_cutover.sh` | Historical custody cutovers; wrappers restrict the environment/database to development/local/test |
| `migrations/baseline_item_ownership.sh`, `baseline_currency_balances.sh`, `baseline_combat_frags.sh`, `baseline_artifact_guild_state.sh` | Initial ownership/domain baselines on eligible development clones; not rebasing live ledgers |
| `migrations/baseline_epic_balances.sh --apply` | Initial epic balances only when no epic ledger/revision activity exists; unlike several neighboring helpers, it has no environment-role guard |
| `migrations/repair_missing_combat_baselines.sh` | Classify exact missing openings and rehearse a reviewed repair with backup/rollback evidence; apply refuses production |
| `migrations/reconcile_coin_custody_pair.sh` | Classify and rehearse one proven old-custody/new-payload UID mismatch; apply is restricted to explicit non-production clone targets |
| `migrations/repair_item_nesting.sh` | Specific historical nesting drift; `--check` inspects, but the default mode writes; restricted to development/local/test |
| `migrations/repair_stale_pet_custody.sh --check/--apply` | One identified pending pet/owner room mismatch; exact identities, backup, and production acknowledgment required |
| `migrations/repair_legacy_personal_locker_access.sh --check/--apply` | One identified imported personal-locker visitor grant; exact target/count, backup, and production acknowledgment required |
| `scripts/character_materialization_readiness.py` | Audit character materialization; apply requires an exact reviewed repair manifest, hashes, backup, database confirmation, and explicit production-repair authorization when relevant |
| `scripts/item_ownership_audit.sh`, `scripts/classify_item_topology.py` | Read-only item payload/custody diagnostics; detailed artifacts may contain player/item identifiers |
| `scripts/classify_legacy_item_quarantine.py`, `scripts/reconcile_legacy_membership.py`, `scripts/verify_target_wins_account_merge.py` | Frozen evidence classification, repair planning, or verification for an explicit legacy import/merge |
| `migrations/check_character_baseline_readiness.sh`, `check_flatfile_account_locker_conversion.sh` | Baseline coverage or flat-file/account-locker conversion diagnostics |
| `migrations/reconcile_artifact_guild_outcomes.sh`, `reconcile_boon_reward_zone.sh`, `reconcile_auction_transactions.sh`, `reconcile_phase02_domains.sh` | Historical domain reconciliation; follow their environment and schema prerequisites rather than running them indiscriminately on the current head |
| `scripts/import_legacy_dump.py` | Guarded replacement of an allow-listed non-production database, including backup, migration layers, and rollback; not production deployment |
| `scripts/convert_all_pfiles.sh` | Historical endian conversion of `Players/`, with dry-run/rollback options; not needed for every binary update |
| `scripts/migrate_players_to_accounts.sh` | Old flat-file character/account attachment with a hard-coded developer path; not the SQL migration workflow |
| `scripts/change_password.sh` | Account administration, not schema or release migration |
| `scripts/clear-redis.sh`, `scripts/clear-duris-redis-keys.sh` | Explicit scoped local Redis cleanup; production is refused. No routine Redis flush is required after a pull |
| `scripts/delete_corpses.sh` | Retired; exits without cleanup |
| `Players/wipers/wipe_it_all` and the in-game `pwipe` path | Destructive season/player reset; never an ordinary update step |

The individual schema verifiers are:
`verify_account_bound_rewards.sh`, `verify_account_erasure_schema.sh`,
`verify_artifact_guild_outcome_schema.sh`, `verify_boon_reward_zone_schema.sh`,
`verify_collector_item_owner.sh`, `verify_combat_outcome_schema.sh`,
`verify_critical_command_schema.sh`, `verify_currency_ledger_schema.sh`,
`verify_epic_ledger_schema.sh`, `verify_immutable_migration_ledger.sh`,
`verify_item_ownership_schema.sh`, `verify_lifecycle_archive_schema.sh`,
`verify_persistence_contract.sh`, `verify_personal_data_export_schema.sh`,
`verify_session_audit_schema.sh`, and `verify_runtime_compatibility.sh`, all
under `migrations/`. They are validation tools, not an apply queue. The current
runtime compatibility verifier is the main pre-start schema check; use narrower
historical checks only where their schema assumptions still apply.

## Remaining tooling that is not a production update step

| Group | Inventory |
| --- | --- |
| Recovery implementation | `scripts/persistence_restore.py`, `qualify_database_restore.py`, `qualify_service_restore.py`, `qualify_flatfile_restore.cpp`, `build_restore_qualifier.py`, `restore_flatfile_backup.sh`; used by the managed isolated restore/drill workflow |
| Isolated database transport | `scripts/mysql_socket_bin/mysql`; routes helper invocations to an explicitly configured Unix socket during isolated migration/restore work |
| Lifecycle policy tools | `scripts/lifecycle_archive.py`, `personal_data_export.py`, `account_erasure.py`, `validate_data_lifecycle.py`; inspection/planning or policy-controlled workflows, not automatic release cleanup |
| Source catalogs | `scripts/artifact_source_inventory.py`, `chaos_eq_analyze.py`, `chaos_eq_catalog.py`, `chaos_eq_report.py`, `chaos_eq_validate.py`, `zone_story_quest_catalog.py`, `zone_story_quest_daily_report.py`; generate/validate reviewed content evidence before release |
| Studio and presentation | `scripts/studio_ability_editor_stub.py`, `studio_ability_validator.cpp`, `audit_scenery_palette.py`, `preview_scenery_palette.py`, `preview_colorization_client.mjs`, `validate_colorization_journey.py`; authoring or isolated validation |
| Build and debugging | `scripts/build-san.sh`, `valgrind_mud.sh`, `valgrind.supp`, `gdbdms`, `warning-inventory.sh`, `tidy.sh`, `scan-append-bounds.py`; development diagnostics |
| Testing and review | `scripts/coverage.sh`, `coverage/g++`, `fuzz.sh`, `mutate.py`, `mutate/g++`, `check_tests_catch.sh`, `test_history.py`, `session14_gate.py`, `validate_runtime_compatibility.py`; local source checks or isolated qualification |
| Formatting and hooks | `scripts/format.sh`, `install-hooks.sh`, `git-hooks/pre-commit`; repository maintenance |
| Dependency/security reports | `scripts/generate_security_sbom.py`, `security_source_check.py`; release validation, not live migration |
| Telemetry support modules | `scripts/telemetry/db_access.py`, `rollup_definitions.py`, `rollup_engine.py`, `encounter_definitions.py`, `reward_projection_definitions.py`; supporting modules, not independent rollout commands |
| Builder maintenance | `areas/add_area.sh`, `commit_zone`, `edit`, `reexit`, `renumber`, `resector`, `de/src/pull.sh`, `mob/extra.pl`, and the conversion scripts under `areas/obj/`; edit/import world sources only for specific content tasks |
| Tests | `tests/async/`, `tests/run_regression_tests.py`, `tests/run_db_tests.sh`, and top-level migration replay/bootstrap tests; run selected tests or the release gate in isolation, never point destructive test harnesses at production |

The migration runner and runtime verifier are the source of truth for schema
requirements. In particular, the older prose in
`docs/persistence/IMMUTABLE_MIGRATIONS.md` calls artifact mana migration 0015;
the manifest correctly identifies `0015_output_preferences` and
`0016_artifact_mana`. Follow the manifest rather than copying a stale numeric
reference from prose.
