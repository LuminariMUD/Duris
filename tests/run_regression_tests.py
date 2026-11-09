#!/usr/bin/env python3
"""Discover and run Duris' plain-Python regression tests."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEST_DIRECTORY = ROOT / "tests" / "async"
MAX_AUTOMATIC_JOBS = 16
# A test still running at its deadline is ended with its process group and counted as a
# failure. A pooled test may first build a server artifact (about three minutes).
# Long gameplay journeys have a deadline of their own.
POOLED_DEADLINE_SECONDS = 900
JOURNEY_DEADLINE_SECONDS = 1800
# How often a line names the tests still running.
PROGRESS_SECONDS = 60
RESOURCE_INTENSIVE_TEST_NAMES = frozenset(
    {
        "test_account_recovery_journey.py",
        "test_assassin_combat_journey.py",
        "test_artifact_owner_restart_journey.py",
        "test_castle_key_reset_journey.py",
        "test_character_stat_choice_journey.py",
        "test_coin_denomination_journey.py",
        "test_conjurer_gameplay_journey.py",
        "test_connection_limit_journey.py",
        "test_corpse_trap_restart_journey.py",
        "test_legacy_trap_journey.py",
        "test_creation_deferred_play_journey.py",
        "test_creation_prompt_journey.py",
        "test_divine_boon_zone_journey.py",
        "test_game_loop_session_journey.py",
        "test_area_coin_pickup.py",
        "test_flatfile_auction_coin_put_journey.py",
        "test_flatfile_boot_preflight.py",
        "test_flatfile_chaos_new_character_kit.py",
        "test_flatfile_combat_journey.py",
        "test_flatfile_collector_intake_journey.py",
        "test_flatfile_death_restart_journey.py",
        "test_flatfile_locker_journey.py",
        "test_flatfile_newbie_regrant_journey.py",
        "test_flatfile_first_session_currency.py",
        "test_flatfile_full_world_boot.py",
        "test_flatfile_hardcore_death_journey.py",
        "test_flight_network_journey.py",
        "test_frag_cap_journey.py",
        "test_generated_npc_journey.py",
        "test_gith_monk_journey.py",
        "test_hostname_files_journey.py",
        "test_log_hygiene_journey.py",
        "test_mob_gold_dial_runtime.py",
        "test_pet_restart_journey.py",
        "test_ranged_kill_xp_journey.py",
        "test_shambler_reflection_journey.py",
        "test_websocket_session_guard_journey.py",
        "test_kept_character_journey.py",
        "test_kept_character_approval_journey.py",
        "test_kept_character_competition.py",
        "test_kept_character_matrix.py",
        "test_kept_character_recovery_journey.py",
        "test_kept_starter_grant_journey.py",
        "test_minor_creation_instrument_journey.py",
        "test_shop_multi_buy_journey.py",
        "test_studioproc_duplicate_record.py",
        "test_item_movement_prompt_runtime.py",
        "test_information_cache_journey.py",
        "test_mysql_combat_journey.py",
    }
)

# The MySQL playtime and account recovery journeys need a disposable database and --server.
# The playtime journey invokes its repository probe with that database's environment.
# make test-db runs them; the generic
# test-all runner invokes every discovered script with no arguments.
# The Discord game journey similarly needs an external Node checkout via --node-driver.
# The artifact population reader requires the disposable SQL fixture in test-db.
MANUAL_ONLY_TEST_NAMES = frozenset(
    {
        "test_account_recovery_mysql_journey.py",
        "test_artifact_population_repository.py",
        "test_discord_game_journey.py",
        "test_epic_task_catalog_mysql.py",
        "test_epic_task_recovery_journey.py",
        # This journey drops a real SQL COMMIT reply and has no flat-file leg.
        "test_kept_character_ambiguous_commit.py",
        "test_mysql_playtime_journey.py",
        "test_mysql_coin_denomination_journey.py",
        "test_mysql_locker_grant_journey.py",
        "test_mysql_nexus_journey.py",
        "test_playtime_mysql_repository.py",
        "test_staff_poof_journey.py",
    }
)

# Tests the flat-file backend removal broke and has not converted yet. Each conversion
# removes its entry; the removal is not finished until this is empty. See
# docs/ongoing-projects/flatfile-backend-removal-fast-plan.md.
FLATFILE_REMOVAL_DEFERRED_TEST_NAMES = frozenset(
    {
        "test_account_bound_reward_access.py",
        "test_account_character_delete_runtime.py",
        "test_account_character_projection_contract.py",
        "test_account_deletion_contract.py",
        "test_account_recovery_contract.py",
        "test_account_recovery_journey.py",
        "test_alliances_save_txn.py",
        "test_area_coin_pickup.py",
        "test_artifact_creation_admission.py",
        "test_artifact_guild_rewards_runtime.py",
        "test_artifact_guild_snapshots.py",
        "test_artifact_mana_game.py",
        "test_artifact_mana_restore.py",
        "test_artifact_mana_runtime.py",
        "test_artifact_offline_owner_loads.py",
        "test_artifact_owner_restart_journey.py",
        "test_artifact_population_boot.py",
        "test_assassin_combat_journey.py",
        "test_auction_artifact_claim.py",
        "test_auction_room_registry.py",
        "test_auction_transactional_cutover.py",
        "test_boon_reward_zone_transactional_cutover.py",
        "test_boot_log_hygiene.py",
        "test_castle_key_reset_journey.py",
        "test_character_persistence_gap.py",
        "test_character_stat_choice_journey.py",
        "test_class_command.py",
        "test_coin_denomination_journey.py",
        "test_coin_transfers.py",
        "test_collector_death_enrollment.py",
        "test_collector_listing_pipeline.py",
        "test_collector_service.py",
        "test_combat_artifact_persistence.py",
        "test_conjurer_gameplay_journey.py",
        "test_connection_limit_journey.py",
        "test_copyover_custody.py",
        "test_corpse_save_routing.py",
        "test_corpse_trap_restart_journey.py",
        "test_corpses_in_memory.py",
        "test_creation_deferred_play_journey.py",
        "test_creation_prompt_journey.py",
        "test_critical_command_admission.py",
        "test_critical_transaction_contract.py",
        "test_ctf_writer_contract.py",
        "test_currency_in_memory.py",
        "test_currency_transaction_contract.py",
        "test_device_actions_runtime.py",
        "test_difficulty_dials.py",
        "test_divine_boon_repository.py",
        "test_divine_boon_runtime.py",
        "test_divine_boon_zone_journey.py",
        "test_divine_trade_runtime.py",
        "test_epic_gain_runtime.py",
        "test_epic_stone_runtime.py",
        "test_flatfile_auction_coin_put_journey.py",
        "test_flatfile_boot_preflight.py",
        "test_flatfile_chaos_new_character_kit.py",
        "test_flatfile_collector_intake_journey.py",
        "test_flatfile_combat_journey.py",
        "test_flatfile_death_restart_journey.py",
        "test_flatfile_first_session_currency.py",
        "test_flatfile_full_world_boot.py",
        "test_flatfile_hardcore_death_journey.py",
        "test_flatfile_help_catalog.py",
        "test_flatfile_ip_activity.py",
        "test_flatfile_kingdom_repository.py",
        "test_flatfile_locker_journey.py",
        "test_flatfile_newbie_regrant_journey.py",
        "test_flatfile_player_repository.py",
        "test_flight_network.py",
        "test_flight_network_journey.py",
        "test_flight_transport_runtime.py",
        "test_frag_cap_config_contract.py",
        "test_frag_cap_journey.py",
        "test_frag_cap_repository.py",
        "test_frag_cap_runtime.py",
        "test_game_loop_phase_contract.py",
        "test_game_loop_session_journey.py",
        "test_gate_lightning_item_runtime.py",
        "test_generated_npc_journey.py",
        "test_gith_monk_journey.py",
        "test_gmcp_control_journey.py",
        "test_headbutt_feedback_journey.py",
        "test_health_endpoint_contract.py",
        "test_help_cache.py",
        "test_hostname_files_journey.py",
        "test_information_cache.py",
        "test_information_cache_journey.py",
        "test_item_extra_descr_codec.py",
        "test_item_ownership_contract.py",
        "test_items_move_in_memory.py",
        "test_kept_character_approval_journey.py",
        "test_kept_character_competition.py",
        "test_kept_character_journey.py",
        "test_kept_character_matrix.py",
        "test_kept_character_recovery_journey.py",
        "test_kept_starter_grant_journey.py",
        "test_kingdom_contract.py",
        "test_last_command.py",
        "test_legacy_trap_journey.py",
        "test_live_item_movement_contract.py",
        "test_locker_async_pipeline.py",
        "test_locker_callback_visit.py",
        "test_locker_idle_lifecycle.py",
        "test_locker_leave_during_save.py",
        "test_locker_named_entry_runtime.py",
        "test_locker_ownership_cutover.py",
        "test_locker_saved_with_occupant.py",
        "test_log_hygiene_journey.py",
        "test_maintenance_scheduler.py",
        "test_minor_creation_instrument_journey.py",
        "test_mob_gold_dial_runtime.py",
        "test_new_player_bank_hydration.py",
        "test_news_publication.py",
        "test_nexus_runtime.py",
        "test_nexus_stones_empty_table.py",
        "test_norent_key_rent_journey.py",
        "test_npc_ship_deletion.py",
        "test_orphan_item_session_regressions.py",
        "test_outposts_in_memory.py",
        "test_persistence_job_latency_runtime.py",
        "test_persistence_status_contract.py",
        "test_pet_restart_journey.py",
        "test_player_item_snapshot_codec.py",
        "test_player_load_offline.py",
        "test_player_load_pipeline.py",
        "test_player_load_topology.py",
        "test_player_revision_state.py",
        "test_player_save_claim.py",
        "test_playtime_flatfile.py",
        "test_private_chest_lifecycle.py",
        "test_private_chest_regressions.py",
        "test_pwipe_quiescence.py",
        "test_racewar_admission.py",
        "test_ranged_kill_xp_journey.py",
        "test_reward_producer_replay.py",
        "test_runtime_boot_compatibility.py",
        "test_saved_item_flatfile_routing.py",
        "test_set_based_gameplay_reads.py",
        "test_shaman_totems.py",
        "test_shambler_reflection_journey.py",
        "test_ship_altitude_and_market_bounds.py",
        "test_ship_boot_room_pool_full.py",
        "test_ship_salvage.py",
        "test_ship_save_guards.py",
        "test_shop_multi_buy_journey.py",
        "test_shop_multi_buy_sequence.py",
        "test_shop_trade_live_route.py",
        "test_shopkeeper_copyover_compat.py",
        "test_shutdown_broadcast.py",
        "test_shutdown_writer_bound.py",
        "test_siege_kingdom_removal_contract.py",
        "test_spells_command.py",
        "test_sql_pool_worker_gate.py",
        "test_sql_worker_thread_init.py",
        "test_starter_arrow_journey.py",
        "test_storage_chest_crash_journey.py",
        "test_studio_abilities_runtime.py",
        "test_studioproc_duplicate_record.py",
        "test_take_coins.py",
        "test_telemetry_gameplay_adapters.py",
        "test_telemetry_repository.py",
        "test_telemetry_runtime_exhaustion.py",
        "test_telemetry_runtime_integration.py",
        "test_telemetry_runtime_outage.py",
        "test_telemetry_transport_integration.py",
        "test_terminal_account_projection.py",
        "test_terminal_save_safety.py",
        "test_timers_queued.py",
        "test_websocket_session_guard_journey.py",
        "test_whitelist_in_memory.py",
        "test_wonder_actions_runtime.py",
        "test_world_quest_reward_publication.py",
        "test_world_recovery_pipeline.py",
        "test_world_singletons.py",
        "test_zone_story_erase_disabled.py",
        "test_zone_story_state_queued.py",
    }
)


@dataclass(frozen=True)
class TestResult:
    path: Path
    returncode: int
    output: str
    elapsed: float
    timed_out: bool = False

    @property
    def status(self) -> str:
        if self.timed_out:
            return "TIMEOUT"
        if self.returncode < 0:
            try:
                return signal.Signals(-self.returncode).name
            except ValueError:
                return f"SIGNAL {-self.returncode}"
        return "PASS" if self.returncode == 0 else "FAIL"


def discover_tests(match: str | None) -> list[Path]:
    tests = sorted(
        path for path in TEST_DIRECTORY.glob("test_*.py")
        if path.name not in MANUAL_ONLY_TEST_NAMES | FLATFILE_REMOVAL_DEFERRED_TEST_NAMES
    )
    if match:
        tests = [path for path in tests if match in path.name]
    return tests


def longest_first(tests: list[Path]) -> list[Path]:
    """Order tests by their last time in bin/test-history, longest first, so that a long test
    does not start late and hold the run open alone. A test with no time goes first."""
    seconds: dict[str, float] = {}
    for record in sorted((ROOT / "bin/test-history").glob("*.json")):
        try:
            for test in json.loads(record.read_text())["tests"]:
                seconds[test["path"]] = test["seconds"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(tests, key=lambda path: -seconds.get(relative(path), float("inf")))


def automatic_jobs() -> int:
    return min(MAX_AUTOMATIC_JOBS, max(1, os.cpu_count() or 1))


def deadline_for(path: Path) -> float:
    if path.name in RESOURCE_INTENSIVE_TEST_NAMES:
        return JOURNEY_DEADLINE_SECONDS
    return POOLED_DEADLINE_SECONDS


# The tests now running, so that a runner that is stopped can end them too; once it is
# stopping, a test that a worker starts anyway is ended at once.
running: set[subprocess.Popen] = set()
running_lock = threading.Lock()
stopping = False


def end_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def stop_running_tests() -> None:
    global stopping
    with running_lock:
        stopping = True
        for process in running:
            end_group(process)


def run_test(path: Path, deadline: float) -> TestResult:
    started = time.monotonic()
    # A file, not a pipe: reading it does not wait on a process that outlives the test.
    with tempfile.TemporaryFile() as output:
        environment = dict(os.environ)
        # subprocess closes Make's jobserver descriptors. Keep compiler overrides,
        # but let each test's independent Make own its parallelism.
        environment["MAKEFLAGS"] = re.sub(r"--jobserver-(?:auth|fds)=\S+", "",
                                          environment.get("MAKEFLAGS", ""))
        process = subprocess.Popen(
            [sys.executable, str(path)],
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=environment,
        )
        with running_lock:
            running.add(process)
            if stopping:
                end_group(process)
        timed_out = False
        try:
            process.wait(timeout=deadline)
        except subprocess.TimeoutExpired:
            timed_out = True
        # Whatever the test started goes with it, however it ended: a crashed journey's
        # server would keep its port and its CPU while later tests run.
        end_group(process)
        process.wait()
        with running_lock:
            running.discard(process)
        output.seek(0)
        text = output.read().decode(errors="replace")
    return TestResult(
        path=path,
        returncode=process.returncode,
        output=text,
        elapsed=time.monotonic() - started,
        timed_out=timed_out,
    )


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jobs",
        type=int,
        default=0,
        help="parallel workers (0: automatic, capped at 16)",
    )
    parser.add_argument(
        "--match",
        metavar="TEXT",
        help="only run tests whose filename contains TEXT",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list discovered tests without running them",
    )
    args = parser.parse_args()
    if args.jobs < 0:
        parser.error("--jobs must be zero or greater")
    return args


def write_history(results: list[TestResult], started: str, match: str | None,
                  jobs: int) -> None:
    """Keep this run's results in bin/test-history/ for scripts/test_history.py, which finds
    the flaky tests and the ones that grow slower. bin/ is ignored: the history is local.
    A run is dirty with any changed or untracked file: the runner finds untracked tests, the
    build takes untracked sources, and tests read migrations/, docs/ and the rest."""
    def git(*arguments: str) -> str:
        return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    try:
        commit = git("rev-parse", "HEAD")
        dirty = bool(git("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError):
        return
    directory = ROOT / "bin/test-history"
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "commit": commit, "dirty": dirty, "started": started, "finished": time.time(),
        "match": match, "jobs": jobs,
        "tests": [{"path": relative(result.path), "status": result.status,
                   "seconds": round(result.elapsed, 3)} for result in results],
    }
    # Two runs can start in the same second on the same commit; the pid tells them apart.
    with open(directory / f"{started}-{commit[:12]}-{os.getpid()}.json", "x") as history:
        history.write(json.dumps(record, indent=1) + "\n")


def main() -> int:
    args = parse_args()
    tests = discover_tests(args.match)

    if args.list:
        for path in tests:
            print(relative(path))
        print(f"{len(tests)} test(s)")
        return 0

    if not tests:
        print("error: no regression tests matched", file=sys.stderr)
        return 2

    os.environ.setdefault("DURIS_REGRESSION_BUILD_CACHE", str(ROOT / "bin/regression-artifacts"))
    # Nearly every harness compiles its sources and links in one g++ command, which ccache
    # cannot cache: most of the suite's time went to compiling the same sources again.
    # scripts/mutate/g++ splits such a command into a cached compile per source and a link,
    # with the flags and diagnostics unchanged. Coverage's g++ has to see every compile.
    if "COVERAGE_DATA" not in os.environ:
        os.environ["PATH"] = f"{ROOT / 'scripts/mutate'}{os.pathsep}{os.environ.get('PATH', '')}"
        if "CCACHE_DIR" not in os.environ:
            # Size only the runner's own cache; never trim a developer's.
            os.environ["CCACHE_DIR"] = str(ROOT / "bin/test-ccache")
            os.environ.setdefault("CCACHE_MAXSIZE", "10G")
        # Harnesses are written to random directories. Their path reaches only __FILE__
        # (assertion text) and debug information, so it must not defeat the cache.
        os.environ.setdefault("CCACHE_SLOPPINESS", "file_macro")
        os.environ.setdefault("CCACHE_NOHASHDIR", "1")
    jobs = args.jobs or automatic_jobs()
    # One pool, longest first: the long journeys start at once and the short tests fill
    # the workers around them, where a separate journey phase ran after the last short test.
    ordered = longest_first(tests)
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    failures: list[TestResult] = []
    results: list[TestResult] = []
    completed_count = 0
    print(f"Running {len(tests)} Python regression tests with {jobs} worker(s), longest first")
    print(f"Excluded {len(FLATFILE_REMOVAL_DEFERRED_TEST_NAMES)} test(s) deferred by the "
          "flat-file backend removal")

    def report(result: TestResult) -> None:
        nonlocal completed_count
        completed_count += 1
        results.append(result)
        print(
            f"[{completed_count:>{len(str(len(tests)))}}/{len(tests)}] "
            f"{result.status} {relative(result.path)} ({result.elapsed:.2f}s)",
            flush=True,
        )
        builds = re.findall(r"SERVER_BUILD (built|reused) build=([0-9.]+)s lookup=([0-9.]+)s", result.output)
        if builds:
            build_time = sum(float(build) for _, build, _ in builds)
            lookup_time = sum(float(lookup) for _, _, lookup in builds)
            print(f"    server artifacts: {', '.join(status for status, _, _ in builds)}; "
                  f"build {build_time:.3f}s; validation {lookup_time:.3f}s; "
                  f"journey/other {max(0, result.elapsed - build_time - lookup_time):.3f}s", flush=True)
        if result.status != "PASS":
            failures.append(result)
            print(f"--- {relative(result.path)} output ---")
            print(result.output.rstrip() or "(no output)", flush=True)

    def run_all(paths: list[Path], workers: int) -> None:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            try:
                futures: dict[Future[TestResult], Path] = {
                    executor.submit(run_test, path, deadline_for(path)): path for path in paths
                }
                pending = set(futures)
                last_progress = time.monotonic()
                while pending:
                    done, pending = wait(pending, timeout=PROGRESS_SECONDS, return_when=FIRST_COMPLETED)
                    for future in done:
                        report(future.result())
                    if pending and time.monotonic() - last_progress >= PROGRESS_SECONDS:
                        names = sorted(relative(futures[future]) for future in pending if future.running())
                        print(f"    still running: {', '.join(names)}", flush=True)
                        last_progress = time.monotonic()
            except BaseException:
                # Ctrl-C or SIGTERM: start nothing more, and end what is running.
                executor.shutdown(wait=False, cancel_futures=True)
                stop_running_tests()
                raise

    run_all(ordered, jobs)

    write_history(results, started_utc, args.match, jobs)
    if failures:
        print("\nFailed:")
        for result in failures:
            print(f"    {result.status} {relative(result.path)}")
    elapsed = time.monotonic() - started
    timeouts = sum(result.timed_out for result in failures)
    signals = sum(not result.timed_out and result.returncode < 0 for result in failures)
    passed = len(tests) - len(failures)
    print(
        f"\n{passed} passed, {len(failures)} failed "
        f"({timeouts} timed out, {signals} ended by a signal) in {elapsed:.2f}s"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    # A SIGTERM (a supervisor, `timeout`) unwinds like Ctrl-C, which ends the running tests.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(128 + signal.SIGTERM))
    raise SystemExit(main())
