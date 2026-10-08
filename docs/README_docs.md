# Documentation Index

Setup and first boot live in the root [README](../README.md); its Quick start is the
onboarding path. This directory holds the development, architecture, operations,
database, and builder references. Open work lives in the
[GitLab work items](https://gitlab.com/max757/duris/-/work_items), not here.

```
docs/
  reference/     how the server works          persistence/  durability and data lifecycle
  guides/        daily development             operations/   running and operating it
  content/       builders and world content    telemetry/    the telemetry pipeline
  testing/       regression journeys           gates/        readiness gates
  design/        feature designs               network/      game-loop contract
  records/       standing records              adr/          decision records
  diagrams/      architecture diagrams         assets/       images and audio
  examples/      versioned configuration samples and transcripts
  data/          generated inputs and evidence that tools read
  lib/           runtime game data (not documentation)
```

## reference/ - how the server works

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](reference/ARCHITECTURE.md) | Process model, boot gate, game loop, typed persistence, recovery, and networking. |
| [CODEBASE.md](reference/CODEBASE.md) | Module-by-module map of the server sources. |
| [DATABASE.md](reference/DATABASE.md) | Database authority, typed reads/writes, schema, reconciliation, and migrations. |
| [EVENTS.md](reference/EVENTS.md) | The `nevent` deferred-work scheduler: the timer wheel, scheduling, cancellation, the per-pulse budget, and catch-up. |
| [SHIPS.md](reference/SHIPS.md) | Ship subsystem engineering reference: lifecycle, heartbeat, movement, crews, combat, NPC ships, persistence, GMCP, and extending it. |
| [SHIP_GAMEPLAY.md](reference/SHIP_GAMEPLAY.md) | Ship commands, shipyards and crew halls, hull/weapon/equipment/crew catalogues, the cargo economy, costs, timings, and properties. |
| [BATCH_ITEM_COMMANDS.md](reference/BATCH_ITEM_COMMANDS.md) | Batch get, put, drop, wear, and remove syntax, the GET parser, and what their saves record. |
| [CHAOS_MODE.md](reference/CHAOS_MODE.md) | Chaos configuration, new-character grants, equipment catalogs, and craft-pouch behavior. |
| [CHAOS_KIT_CATALOG.md](reference/CHAOS_KIT_CATALOG.md) | Generated Chaos starter-kit catalog policy (`scripts/chaos_eq_catalog.py`; not edited by hand). |
| [LEGACY_STARTER_KITS.md](reference/LEGACY_STARTER_KITS.md) | How the legacy newbie kit is planned off the game loop. |
| [EXPERIENCE_TROPHIES.md](reference/EXPERIENCE_TROPHIES.md) | In-memory PvE XP observation per zone and its checkpoint persistence. |
| [DIVINE_REFUSAL.md](reference/DIVINE_REFUSAL.md) | The default-off refusal roll for ordered cleric pets. |
| [ITEM_ACTIONS.md](reference/ITEM_ACTIONS.md) | The default-off shared runtime for telegraphed item abilities. |
| [WEAPON_ACTIONS.md](reference/WEAPON_ACTIONS.md), [DEVICE_ACTIONS.md](reference/DEVICE_ACTIONS.md) | The weapon-proc adapters, and wand, staff, and scroll channels. |
| [ARTIFACT_MANA.md](reference/ARTIFACT_MANA.md) | Per-item mana: the resource, its storage, and the crash window. |
| [NATIVE_ARTIFACT_PILOTS.md](reference/NATIVE_ARTIFACT_PILOTS.md) | The five migrated native artifacts and the [source inventory](reference/artifact_source_inventory.json). |
| [STUDIO_ITEM_ABILITIES.md](reference/STUDIO_ITEM_ABILITIES.md) | The typed `itemability` Studio action, its catalog, and its [schema](reference/studio-item-abilities.schema.json). |
| [ZONE_STORY_QUEST_TRACKING_CONTRACT.md](reference/ZONE_STORY_QUEST_TRACKING_CONTRACT.md) | What a zone-story quest completion records. |
| [ZONE_STORY_QUEST_CATALOG.md](reference/ZONE_STORY_QUEST_CATALOG.md) | The generated quest catalog and its [snapshot](reference/ZONE_STORY_QUEST_PRODUCTION_CATALOG.json). |
| [ZONE_STORY_QUEST_DAILY.md](reference/ZONE_STORY_QUEST_DAILY.md) | Daily zone-story quests, shipped disabled. |
| [api/health.md](reference/api/health.md) | The health endpoint contract. |
| [api/durisweb.md](reference/api/durisweb.md) | DurisWeb transport, challenge authentication, authorization, and privacy contract. |
| [api/donation-events.md](reference/api/donation-events.md) | The signed donation event envelope read from Redis. |

## persistence/ - durability, lifecycle, and privacy

| Document | Purpose |
|----------|---------|
| [PLAYER_SAVE_PIPELINE.md](persistence/PLAYER_SAVE_PIPELINE.md) | The one writer, what a save writes, what a load reads, terminal saves, and persistence reporting. |
| [CRITICAL_COMMAND_PIPELINE.md](persistence/CRITICAL_COMMAND_PIPELINE.md) | Operation identity, domains, the inbox/outbox transaction, failure behavior, and money and epics in memory. |
| [WORLD_RECOVERY_PIPELINE.md](persistence/WORLD_RECOVERY_PIPELINE.md), [WORLD_RECOVERY_FORMAT.md](persistence/WORLD_RECOVERY_FORMAT.md) | Optional Redis world generations: capture, publication, restore, and the wire format. |
| [CHARACTER_DELETION.md](persistence/CHARACTER_DELETION.md) | Deletion outcomes, the transaction, and what memory forgets. |
| [IMMUTABLE_MIGRATIONS.md](persistence/IMMUTABLE_MIGRATIONS.md) | Baseline adoption and the checksummed ordered migration history. |
| [RUNTIME_COMPATIBILITY.md](persistence/RUNTIME_COMPATIBILITY.md) | Pre-write schema verification; states the current migration head and table count. |
| [DATA_LIFECYCLE.md](persistence/DATA_LIFECYCLE.md) | Complete store inventory and the pending-policy boundary. |
| [LIFECYCLE_ARCHIVE.md](persistence/LIFECYCLE_ARCHIVE.md) | Bounded archive state machine; its scheduler slot is disabled. |
| [PERSONAL_DATA_EXPORT.md](persistence/PERSONAL_DATA_EXPORT.md) | Authenticated export package contract; not enabled. |
| [ACCOUNT_ERASURE.md](persistence/ACCOUNT_ERASURE.md) | Live account deletion, and the disabled erasure/tombstone contract. |
| [LEGACY_DUMP_IMPORT.md](persistence/LEGACY_DUMP_IMPORT.md) | Importing a legacy production dump into a development database. |
| [EXCEPTIONAL_TARGET_WINS_MERGE.md](persistence/EXCEPTIONAL_TARGET_WINS_MERGE.md) | Account-collision dispositions and preflight for an owner-approved merge. |
| [LEGACY_ITEM_QUARANTINE.md](persistence/LEGACY_ITEM_QUARANTINE.md) | Classifying and planning recovery of ambiguous legacy items. |
| [LEGACY_MEMBERSHIP_RECONCILIATION.md](persistence/LEGACY_MEMBERSHIP_RECONCILIATION.md) | Classifying and rehearsing repair of legacy association and guild state. |
| [LEGACY_STARTER_GRANTS.md](persistence/LEGACY_STARTER_GRANTS.md) | The deferred legacy starter-kit grant and its queue. |

## guides/ - daily development

| Document | Purpose |
|----------|---------|
| [BUILDING.md](guides/BUILDING.md) | Build entry points, compile flags, warning profile, sanitizers, area generation, and finding unreachable code. |
| [TESTING.md](guides/TESTING.md) | Focused tests, the gates, the journeys, and what each proves. |
| [CONVENTIONS.md](guides/CONVENTIONS.md) | Repository conventions and their precedence against `AGENTS.md`. |
| [formatting.md](guides/formatting.md) | Style, changed-line formatting, and editor setup. |
| [MEMORY_CHECKING.md](guides/MEMORY_CHECKING.md), [valgrind.md](guides/valgrind.md) | Which memory detector to use and when; the Valgrind wrapper. |
| [VERSIONING.md](guides/VERSIONING.md) | Semantic versioning and the canonical version marker. |
| [GITHUB_PAGES.md](guides/GITHUB_PAGES.md) | The project website: catalog, build, and the publishing recipe. |
| [TERMINAL_MODES.md](guides/TERMINAL_MODES.md) | The terminal type codes and what MSP mode frames. |
| [epic-stone-recovery.md](guides/epic-stone-recovery.md) | How a stone touch commits its reward and its claim. |

Colorization:

| Document | Purpose |
|----------|---------|
| [COLOR_COMMAND.md](guides/COLOR_COMMAND.md) | The player's `toggle color` command. |
| [OUTPUT_WORD_STYLING.md](guides/OUTPUT_WORD_STYLING.md) | Completed-message rendering, authored-style protection, and output boundaries. |
| [OUTPUT_PROFILES.md](guides/OUTPUT_PROFILES.md) | Versioned channel profiles, recipe validation, recipient resolution, and snapshot lifetime. |
| [OUTPUT_PREFERENCES.md](guides/OUTPUT_PREFERENCES.md) | Per-character preferences and how they are saved. |
| [CHAT_COLORIZATION.md](guides/CHAT_COLORIZATION.md), [STRUCTURED_CHAT_COLORIZATION.md](guides/STRUCTURED_CHAT_COLORIZATION.md) | Recipient chat colors on the terminal and in the structured web client. |
| [WORLD_COLORIZATION.md](guides/WORLD_COLORIZATION.md), [SCENERY_COLORIZATION.md](guides/SCENERY_COLORIZATION.md) | World output channels, and scenery recipes and animation. |
| [COMBAT_PROMPT_COLORIZATION.md](guides/COMBAT_PROMPT_COLORIZATION.md) | Combat, prompt, and feedback color roles. |
| [COLORIZATION_RELEASE.md](guides/COLORIZATION_RELEASE.md) | The release validation: walkthrough, measured cost, client evidence, and rollback. |

## operations/ - running and operating it

| Document | Purpose |
|----------|---------|
| [RUNBOOK.md](operations/RUNBOOK.md) | Startup, migration, backup, restore, recovery, reconciliation, and the release boundary. |
| [CONFIGURATION.md](operations/CONFIGURATION.md) | Runtime variables, Redis, listeners, proxy handling, and diagnostics. |
| [BACKUPS.md](operations/BACKUPS.md) | Backup policy, generations, off-host copies, and isolated restore qualification. |
| [DOCKER.md](operations/DOCKER.md) | Local Compose deployment, persistent data, upgrades, and reset boundaries. |
| [PRODUCTION_DEPLOYMENT.md](operations/PRODUCTION_DEPLOYMENT.md) | The `newduris.com` production host as last verified on 2026-09-14. |
| [SECURITY_BASELINE.md](operations/SECURITY_BASELINE.md) | Dependency inventory, SBOM, and the security workflow recipe. |
| [incident-response.md](operations/incident-response.md) | Incident handling procedure. |
| [help-cache.md](operations/help-cache.md), [information-cache.md](operations/information-cache.md) | The help catalog and the credits/FAQ/wizlist snapshot: refresh, limits, and validation. |
| [locker-identification.md](operations/locker-identification.md) | Paid locker identification receipts, recovery, and backup. |
| [legacy-personal-locker-access-repair.md](operations/legacy-personal-locker-access-repair.md) | The guarded visitor-grant repair for one imported locker. |
| [PET_CUSTODY.md](operations/PET_CUSTODY.md) | Raised followers: custody, lifetime, saved state, and holds ([review query](operations/pet-recovery-review.sql)). |
| [SAVED_ITEM_RECOVERY_HANDOFF.md](operations/SAVED_ITEM_RECOVERY_HANDOFF.md) | How saved ground items are restored and their legacy rows retired. |
| [WORLD_SINGLETON_RECOVERY.md](operations/WORLD_SINGLETON_RECOVERY.md) | Keeping one shopkeeper and one flight dragon across recovery. |
| [ITEM_ABILITY_ROLLOUT.md](operations/ITEM_ABILITY_ROLLOUT.md) | Enabling, observing, and rolling back item abilities. |
| [EPIC_ZONE_SEED.md](operations/EPIC_ZONE_SEED.md) | The source-derived epic-zone payout seed and its SQL artifact. |

## telemetry/ - the telemetry pipeline

Off unless `TELEMETRY_ENABLED` is set. These documents name each module by the number of
the work item it was built under; [CONTRACT.md](telemetry/CONTRACT.md) maps the numbers.

| Document | Purpose |
|----------|---------|
| [CONTRACT.md](telemetry/CONTRACT.md) | Version 1 record contract, module ownership, and fixtures. |
| [STORAGE_DESIGN.md](telemetry/STORAGE_DESIGN.md) | The design review the modules were built from. |
| [DATABASE.md](telemetry/DATABASE.md) | Tables, roles, and repository behavior. |
| [TRANSPORT.md](telemetry/TRANSPORT.md) | The bounded in-process queue and writer handoff. |
| [OUTAGE_STORAGE.md](telemetry/OUTAGE_STORAGE.md) | The bounded outage record the writer keeps on disk, and its offline export. |
| [CONFIG_CONTEXT.md](telemetry/CONFIG_CONTEXT.md) | Effective configuration identity. |
| [SESSION_STATE.md](telemetry/SESSION_STATE.md), [SESSION_LIFECYCLE.md](telemetry/SESSION_LIFECYCLE.md) | Session state, and the gameplay hooks that feed it. |
| [ACTIVITY.md](telemetry/ACTIVITY.md) | Activity classification and contextual intervals. |
| [PROGRESSION.md](telemetry/PROGRESSION.md), [ENCOUNTERS.md](telemetry/ENCOUNTERS.md), [COMBAT_METRICS.md](telemetry/COMBAT_METRICS.md) | Progression, encounter, and combat facts. |
| [ROLLUPS.md](telemetry/ROLLUPS.md), [REPORTS.md](telemetry/REPORTS.md) | The external rollup job and administrator reports. |
| [REWARD_PROJECTION.md](telemetry/REWARD_PROJECTION.md) | The projection of committed rewards. |
| [PERFORMANCE_GATE.md](telemetry/PERFORMANCE_GATE.md) | The offline performance and degradation gate. |
| [playtime-compatibility.md](telemetry/playtime-compatibility.md) | What the saved playtime total measures. |
| [studies/rested-bonus.md](telemetry/studies/rested-bonus.md) | The rested-bonus study protocol. |
| [balance/SHADOW_POLICY.md](telemetry/balance/SHADOW_POLICY.md), [balance/APPLICATION.md](telemetry/balance/APPLICATION.md) | Report-only balance recommendations and the reviewed application contract. |

## content/ - builders and world content

| Document | Purpose |
|----------|---------|
| [HELP_SYSTEM.md](content/HELP_SYSTEM.md) | Help sources, database import, and rendering. |
| [HELP_STYLE_GUIDE.md](content/HELP_STYLE_GUIDE.md) | House style for help entries. |
| [AREA_OBJECT_FORMAT.md](content/AREA_OBJECT_FORMAT.md) | Area object file format and bitvector compatibility. |
| [area_writing.txt](content/area_writing.txt) | The inherited area-writing manual: the `.wld`, `.mob`, `.obj`, `.zon`, `.shp` and `.qst` formats, ANSI codes, and common object numbers. It says itself that it is outdated. |
| [STUDIOPROC.md](content/STUDIOPROC.md) | Studio proc design and the reasoning behind it. |
| [howto_trg.txt](content/howto_trg.txt) | The builder's grammar for `areas/world.trg`. |
| [classes_and_races.txt](content/classes_and_races.txt) | Class and race reference table. |

## testing/, gates/, network/, design/

| Document | Purpose |
|----------|---------|
| [testing/REGRESSIONS.md](testing/REGRESSIONS.md) | Per fixed defect: the rule, the tests that hold it, and what they do not cover. |
| [testing/ITEM_ABILITY_ROLLOUT.md](testing/ITEM_ABILITY_ROLLOUT.md) | Item ability verification record and its [evidence](testing/item-ability-rollout-evidence.json). |
| [gates/PHASE03_READINESS.md](gates/PHASE03_READINESS.md) | The 200-player readiness gate: inputs, procedure, and current state. |
| [network/GAME_LOOP_PHASES.md](network/GAME_LOOP_PHASES.md) | The order of a pulse's phases and the session-input decision. |
| [design/COLLECTOR_OF_ANTIQUITIES.md](design/COLLECTOR_OF_ANTIQUITIES.md) | Collector policy, authorities, runtime publication, and what to run before enabling it. |
| [design/COMMUNITY_SPELLUP.md](design/COMMUNITY_SPELLUP.md) | The `newbsa` spell-up controls and the boot-lifetime repeat job. |

## records/ - standing records

| Document | Purpose |
|----------|---------|
| [SECURITY-COMPLIANCE.md](records/SECURITY-COMPLIANCE.md) | Cumulative security posture and GDPR compliance record. |
| [COMMUNITY_DURIS_TRACKING.md](records/COMMUNITY_DURIS_TRACKING.md) | The split from Community-Duris, their changes since (bug fixes and everything else), and what we adopted, adapted or rejected. |
| [CREDITS.md](records/CREDITS.md) | Credits for moshehbenavraham's foundation work, 2026-08-25 to 2026-09-23, counted from the Git history. |
| [HISTORY.md](records/HISTORY.md) | The history of Duris from Sojourn (1993) to 2026: eras, staff, addresses, wipes, lore and culture, with sources. |
| [story-of-outcast3.md](records/story-of-outcast3.md) | How the Outcast III Beta snapshot resurfaced, the Sojourn/Duris/Outcast family tree it proves, and what its code settles. |

The `.spec_system/` tracking tree these began in was retired after Phase 03; its contents
are in Git history at commit `212592e3`.

## Decisions and diagrams

- [Architecture decision template](adr/0000-template.md)
- [Refactor investigations #343-#347](adr/0001-refactor-investigation-343-347.md): the
  alternatives considered for the persistence, combat, networking and item-command
  refactors; all four landed, and 0002 superseded its persistence design.
- [Persistence reset: memory is the authority](adr/0002-persistence-reset-memory-is-the-authority.md):
  why saves never refuse and one writer applies them, what a crash costs, and what was
  deliberately left out.
- [Server architecture diagram](diagrams/duris-server-architecture.html) and
  [database model](diagrams/duris-database-model.html)

## Runtime-data tree

- `lib/` is **not documentation**. `lib/information/` is read by the server at runtime
  (`src/cmd/wikihelp.c`, `src/account/nanny.c`) and by `scripts/import_help_to_prod.sh`; moving it
  breaks the running game.
