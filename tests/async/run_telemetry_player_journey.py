#!/usr/bin/env python3
"""Real PostHog gameplay/copyover journey in a disposable native world.

No .env, existing database, live player data or namespace/container is used.
Both backend builds must exist below bin/issue59/<backend> before running.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import http.client
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import threading
import time

import run_copyover_runtime_journey as copyover
import test_flatfile_combat_journey as journey
from telemetry_posthog_http import Receiver

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from persistence_restore import private_database
from telemetry.outage import read_evidence


def mock_binary(backend: str, work: Path) -> tuple[Path, Path]:
    """Relink the real game with only its two worker test seams compiled in."""
    build = ROOT / "bin/issue59" / backend
    env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8"}
    make = ["make", "--no-print-directory", "-C", "src", "-j1",
            "PERSISTENCE_BACKEND=" + backend, "BIN_ROOT=" + str(build)]
    with (work / "build.log").open("w") as log:
        subprocess.run([*make, "all", "telemetry-state"], cwd=ROOT, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    config = subprocess.check_output([
        *make, "-s", "--eval=.PHONY: telemetry-fixture-config",
        "--eval=telemetry-fixture-config:;@echo FIXTURE_CC=$(CC); echo FIXTURE_FLAGS=$(CFLAGS) $(INCLUDES); echo FIXTURE_OBJS=$(DMS_OBJS); echo FIXTURE_LIBS=$(LDFLAGS) $(LIBS)",
        "telemetry-fixture-config"], cwd=ROOT, env=env, text=True)
    fields = dict(line.split("=", 1) for line in config.splitlines() if line.startswith("FIXTURE_"))
    compiler = shlex.split(fields["FIXTURE_CC"])
    flags = shlex.split(fields["FIXTURE_FLAGS"])
    objects = shlex.split(fields["FIXTURE_OBJS"])
    for name in ("telemetry_runtime", "telemetry_posthog"):
        selected = [i for i, value in enumerate(objects) if value.endswith("/telemetry/" + name + ".o")]
        assert len(selected) == 1
        target = work / (name + ".o")
        subprocess.run([*compiler, *flags, "-DTELEMETRY_POSTHOG_TESTING", "-c",
                        "telemetry/" + name + ".c", "-o", str(target)],
                       cwd=ROOT / "src", env=env, check=True)
        objects[selected[0]] = str(target)
    measure = work / "telemetry_gameplay_measure.o"
    subprocess.run([*compiler, *flags, "-c", str(ROOT / "tests/async/telemetry_gameplay_measure.cc"),
                    "-o", str(measure)], cwd=ROOT / "src", env=env, check=True)
    binary = work / "dms_mock"
    subprocess.run([*compiler, "-rdynamic", "-g", "-Wl,--wrap=_Z20latency_trace_recordPKcmm", "-Wl,--wrap=fsync",
                    "-o", str(binary), *objects, str(measure),
                    *shlex.split(fields["FIXTURE_LIBS"])], cwd=ROOT / "src", env=env, check=True)
    return binary, build / "tools/telemetry-state"


def until(predicate, label: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(label)


def verify_performance_pairs(measurements):
    for pair in range(3):
        off = next(row for row in measurements if row["pair"] == pair and not row["enabled"])
        on = next(row for row in measurements if row["pair"] == pair and row["enabled"])
        assert on["save_p99_us"] * 100 <= off["save_p99_us"] * 105, (pair, "save_p99_us", off, on)
        assert on["native"]["total_tick"]["p99_us"] * 100 <= off["native"]["total_tick"]["p99_us"] * 105, (pair, off, on)
        assert on["native"]["total_tick"]["p99_us"] <= 250000
        assert on["native"]["ne_events"]["max_us"] <= 25000, "callback latency upper bound unresolved"


def run(backend: str, performance: bool = False, cloud: bool = False) -> None:
    artifacts = ROOT / "bin/issue59/acceptance"
    artifacts.mkdir(parents=True, exist_ok=True)
    cloud_state = artifacts / "cloud-smoke"
    cloud_key = None
    tag = "issue59-cloud-smoke" if cloud else "native-gameplay-" + backend
    scope = "1001" if backend == "flatfile" else "1002"
    if cloud:
        # Read only the capture settings; never import the host's game/DB environment.
        settings = {}
        for line in (ROOT / ".env").read_text().splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() in ("POSTHOG_API_KEY", "POSTHOG_HOST", "POSTHOG_PROJECT_ID"):
                settings[name.strip()] = value.strip().strip("\"'")
        assert settings.get("POSTHOG_PROJECT_ID") == "678214"
        assert settings.get("POSTHOG_HOST", "").rstrip("/") == "https://us.i.posthog.com"
        cloud_key = settings.get("POSTHOG_API_KEY", "")
        assert cloud_key.startswith("phc_"), "project capture key required"
        cloud_state.mkdir(mode=0o700, exist_ok=True)
        # A fresh fixture cannot restart this campaign or silently reset its allowance.
        with (cloud_state / "campaign.json").open("x") as marker:
            json.dump({"project": 678214, "backend": backend, "scope": scope, "tag": tag,
                       "started_utc": datetime.now(timezone.utc).isoformat()}, marker)
            marker.flush()
            os.fsync(marker.fileno())
        for directory in (cloud_state, artifacts):
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    with tempfile.TemporaryDirectory(prefix=backend + "-", dir=artifacts) as temporary, \
            tempfile.TemporaryDirectory(prefix="duris-telemetry-db-") as database_temporary:
        work = Path(temporary)
        work.chmod(0o700)
        binary, state_tool = mock_binary(backend, work)
        runtime, state = work / "runtime", work / "state"
        ledger = cloud_state / "ledger" if cloud else work / "ledger"
        runtime.mkdir(); state.mkdir(mode=0o700); ledger.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        for name in ("logs/log", "journals/critical", "bin/server"):
            (runtime / name).mkdir(parents=True, mode=0o700)
        for name in ("dms", "dms_new"):
            shutil.copy2(binary, runtime / "bin/server" / name)
        catalog = work / "reviewed-properties.catalog"
        catalog.write_text("6f49b7e9b16055b6c7d48d83f4a9de789d89adeddabbb4bfc1f6d2c86f6b8792 265 265 1\n")
        catalog.chmod(0o600)
        cert, key = work / "capture.crt", work / "capture.key"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1",
                        "-keyout", str(key), "-out", str(cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        received: list[dict] = []
        attempts: list[int] = []
        response = {"status": 200}
        cloud_capture = {"attempts": 0, "rows": [], "repeated": False,
                         "omitted": False, "main_id": None, "expected": {}}
        cloud_lock = threading.Lock()

        def forward(batch):
            """Synthetic-only fault probe; the native worker charged its ledger first."""
            with cloud_lock:
                encoded = json.dumps(batch).lower()
                for private in (journey.CHARACTER, journey.ACCOUNT, "Valerek", "Friendacct",
                                journey.PASSWORD, "127.0.0.1", "@example.invalid"):
                    assert private.lower() not in encoded, "private value refused before cloud capture"
                for row in batch:
                    properties = row["properties"]
                    assert properties["duris_environment_id"] == scope and int(scope) >= 1000
                    assert properties["duris_test_run"] == tag
                    assert properties["$process_person_profile"] is False
                    if row["event"] == "duris_session" and properties["transition"] == "logical_entry":
                        cloud_capture["main_id"] = cloud_capture["main_id"] or properties["duris_character_id"]
                    if row["event"] == "duris_encounter_summary" and properties["row_type"] == "run":
                        cloud_capture["expected"][properties["duris_run_id"]] = properties["participant_rows_expected"]
                transmitted = []
                for row in batch:
                    properties = row["properties"]
                    # Keep owner and pet rows, omit one other player to prove cloud
                    # completeness checks cannot rely on a native-complete flag/HTTP 200.
                    if (not cloud_capture["omitted"] and row["event"] == "duris_encounter_summary"
                            and properties.get("actor_kind") == "player"
                            and properties["duris_character_id"] != cloud_capture["main_id"]
                            and cloud_capture["expected"].get(properties["duris_run_id"], 0) >= 2):
                        cloud_capture["omitted"] = True
                        cloud_capture["omitted_event_id"] = row["uuid"]
                    if row["uuid"] == cloud_capture.get("omitted_event_id"):
                        continue
                    transmitted.append(row)
                cloud_capture["attempts"] += len(transmitted)
                assert cloud_capture["attempts"] <= 100, "cloud campaign allowance exhausted"
                cloud_capture["rows"].extend(transmitted)
                (cloud_state / "attempts.json").write_text(json.dumps(cloud_capture, indent=2))
                connection = http.client.HTTPSConnection("us.i.posthog.com", timeout=2)
                try:
                    connection.request("POST", "/batch/", json.dumps({"api_key": cloud_key, "batch": transmitted}),
                                       {"Content-Type": "application/json"})
                    result = connection.getresponse()
                    status = result.status
                    result.read(1024)
                except (OSError, http.client.HTTPException):
                    return 503
                finally:
                    connection.close()
                if 200 <= status < 300:
                    if not cloud_capture["repeated"]:
                        cloud_capture["repeated"] = True
                        return 503  # Retry the same immutable UUIDs; both attempts are charged.
                    return 200
                return status

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                assert self.path == "/batch/"
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert body["api_key"] == "phc_native_gameplay"
                attempts.append(len(body["batch"]))
                status = response["status"]
                if cloud and status == 200:
                    status = forward(body["batch"])
                if status == 200:
                    received.extend(body["batch"])
                self.send_response(status)
                if status != 200:
                    self.send_header("Retry-After", "1")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

        receiver = Receiver(("127.0.0.1", 0), Handler)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
        receiver.socket = tls.wrap_socket(receiver.socket, server_side=True)
        receiver_thread = threading.Thread(target=receiver.serve_forever,
                                           kwargs={"poll_interval": 0.01}, daemon=True)
        receiver_thread.start()
        # The host's MariaDB confinement permits /tmp, but refuses a datadir in
        # /home. Only the disposable database lives here; build outputs stay in bin/.
        database = Path(database_temporary)
        database_context = private_database(database) if backend == "mariadb" else contextlib.nullcontext({})
        process = output = client = companion = None
        transcripts = []
        port, game_tls, websocket = journey.available_ports()
        copyover_state = work / "copyover-state/copyover.dat"

        def stop():
            nonlocal client, companion, process, output
            if client:
                transcripts.append(bytes(client.transcript[-6000:]).decode(errors="replace"))
                client.close(); client = None
            if companion:
                transcripts.append(bytes(companion.transcript[-6000:]).decode(errors="replace"))
                companion.close(); companion = None
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
                    raise AssertionError("native game did not stop")
            if output:
                output.close(); output = None

        try:
            with contextlib.ExitStack() as cleanup:
                database_env = cleanup.enter_context(database_context)
                cleanup.callback(stop)  # Writers must stop before their disposable DB.
                env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "ENVIRONMENT": "local", **database_env}
                if backend == "mariadb":
                    mysql = ["mysql", "--no-defaults", "--protocol=socket", "--socket=" + env["DB_SOCKET"],
                             "-u" + env["DB_USER"], "-N", "-B", env["DB_NAME"]]

                    def sql(statement):
                        return subprocess.check_output(mysql, input=statement, env=env, text=True).strip()

                    sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
                    for args in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
                        subprocess.run([sys.executable, "scripts/migration_runner.py", *args],
                                       cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
                else:
                    subprocess.run([sys.executable, "tests/async/test_flatfile_player_repository.py",
                                    "--build-inspector", str(journey.INSPECTOR)], cwd=ROOT, check=True)
                    subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
                env.update(PERSISTENCE_MODE=backend + "-primary", PERSISTENCE_BACKEND=backend,
                           FLATFILE_STATE_DIR=str(state), CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                           COPYOVER_STATE_FILE=str(copyover_state), LISTEN_ADDRESS="127.0.0.1",
                           DURIS_TLS_PORT=str(game_tls), DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
                           DURIS_WEBSOCKET_PORT=str(websocket), REDIS="FALSE", CHAOS_MUD="FALSE",
                           TELEMETRY_ENABLED="false", TELEMETRY_BACKEND="posthog", TELEMETRY_ENVIRONMENT_ID=scope,
                           TELEMETRY_SEASON_ID="1", TELEMETRY_INTERVAL_USEC="60000000",
                           TELEMETRY_CHECKPOINT_INTERVAL_USEC="1000000", TELEMETRY_ACTIVE_WINDOW_USEC="3000000",
                           TELEMETRY_CONTEXT_SEGMENTS_PER_MINUTE="64", TELEMETRY_OUTAGE_LEDGER_DIR=str(ledger),
                           TELEMETRY_PROPERTY_CATALOG_FILE=str(catalog), TELEMETRY_IDENTITY_KEY="01" * 32,
                           TELEMETRY_TEST_RUN=tag, POSTHOG_API_KEY="phc_native_gameplay",
                           POSTHOG_HOST="https://us.i.posthog.com", POSTHOG_PROJECT_ID="678214", POSTHOG_SENDER_ID="99",
                           DURIS_TEST_POSTHOG_PORT=str(receiver.server_port), DURIS_TEST_POSTHOG_CA=str(cert))
                subprocess.run([str(state_tool), "initialize", str(ledger), "678214", "99", scope,
                                "1", "100", "90", "10"], env=env, check=True, stdout=subprocess.DEVNULL)

                def boot():
                    nonlocal process, output
                    output = (runtime / "server.out").open("w")
                    process = subprocess.Popen([str(runtime / "bin/server/dms"), "--minimal", "-s", str(port)],
                                               cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                    until(lambda: process.poll() is not None or "Entering game loop." in
                          (runtime / "server.out").read_text(errors="replace"), "game boot timeout", 90)
                    assert process.poll() is None, (runtime / "server.out").read_text(errors="replace")[-6000:]

                companion_name, companion_account = "Valerek", "Friendacct"

                def reconnect(character=journey.CHARACTER, account=journey.ACCOUNT):
                    original = journey.MudClient
                    journey.MudClient = copyover.Client
                    try:
                        connected = journey.reconnect_character(port, expected_room=None,
                                                               character=character, account=account)
                        connected.send("look")
                        connected.expect("The Regression Arena", timeout=30)
                        return connected
                    finally:
                        journey.MudClient = original

                def save():
                    client.send("save")
                    client.expect(f"Save complete for {journey.CHARACTER}.", timeout=30)

                def health():
                    client.send("world telemetry")
                    snapshot = client.expect("coverage gaps=", timeout=30)
                    assert "backend=posthog" in snapshot and "PostHog native_consumed=" in snapshot, snapshot
                    used = re.search(r"used=(\d+)\+(\d+)/100", snapshot)
                    assert used, snapshot
                    return snapshot, int(used[1]) + int(used[2])

                boot()
                client = copyover.Client(port)
                journey.create_character(client)
                save()
                companion = copyover.Client(port)
                journey.create_character(companion, character=companion_name,
                                         account=companion_account, email="companion@example.invalid")
                companion.send("save")
                companion.expect(f"Save complete for {companion_name}.")
                companion.send("quit"); companion.expect("ACCOUNT MENU", timeout=30)
                companion.close(); companion = None
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                stop()
                assert not received, "disabled telemetry exported events"
                print("PASS disabled save/reload fixture", backend, flush=True)
                if backend == "flatfile":
                    journey.make_overlord(state, journey.CHARACTER)
                else:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{journey.CHARACTER}'")
                env["TELEMETRY_ENABLED"] = "true"
                if performance:
                    measurements = []

                    def p99(values):
                        return sorted(values)[(len(values) * 99 + 99) // 100 - 1]

                    for pair in range(3):
                        for enabled in ((False, True) if pair % 2 == 0 else (True, False)):
                            env["TELEMETRY_ENABLED"] = str(enabled).lower()
                            sample_path = work / f"latency-{pair}-{enabled}.txt"
                            env["DURIS_TEST_LATENCY_FILE"] = str(sample_path)
                            boot(); client = reconnect()
                            time.sleep(10)
                            initial_cpu = Path(f"/proc/{process.pid}/stat").read_text().split()
                            workload_started = time.monotonic()
                            command_us, save_us, snapshots, rss = [], [], [], []
                            telemetry_snapshots = []
                            for index in range(40):
                                started = time.monotonic_ns()
                                client.send("look"); client.expect("The Regression Arena")
                                command_us.append((time.monotonic_ns() - started) // 1000)
                                started = time.monotonic_ns()
                                save()
                                save_us.append((time.monotonic_ns() - started) // 1000)
                                status = Path(f"/proc/{process.pid}/status").read_text()
                                rss.append(int(re.search(r"VmHWM:\s+(\d+)", status)[1]))
                                if index % 20 != 19:
                                    continue
                                client.send("world persistence")
                                snapshot = ""
                                while True:
                                    marker, page = client.expect_any(("oldest_save_age_ms=", "[Return to continue"), timeout=30)
                                    snapshot += page
                                    if marker == "oldest_save_age_ms=":
                                        break
                                    client.send("")
                                client.expect("Pos: standing >", timeout=30)
                                critical_age = re.search(r"critical_commands [^\n]*oldest_age_ms=(\d+)", snapshot)
                                assert critical_age and int(critical_age[1]) <= 1000, snapshot
                                snapshots.append(snapshot)
                                if enabled:
                                    snapshot, _ = health()
                                    for clean in ("reduction_refused=0", "quota_error=0", "dropped=0/0",
                                                  "ambiguous=0", "suppressed=0", "expired=0"):
                                        assert clean in snapshot, snapshot
                                    telemetry_snapshots.append(snapshot)
                            if enabled:
                                snapshot, _ = health()
                                assert "reduction_refused=0" in snapshot and "quota_error=0" in snapshot, snapshot
                            usage = Path(f"/proc/{process.pid}/stat").read_text().split()
                            cpu_seconds = (int(usage[13]) + int(usage[14]) - int(initial_cpu[13]) - int(initial_cpu[14])) / os.sysconf("SC_CLK_TCK")
                            workload_seconds = time.monotonic() - workload_started
                            client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                            stop()
                            (artifacts / f"{backend}-latency-{pair}-{enabled}.txt").write_bytes(sample_path.read_bytes())
                            native = {}
                            for line in sample_path.read_text().splitlines():
                                section, overflow, *values = line.split()
                                assert overflow == "0" and (section == "fsync" or len(values) >= 200), line[:100]
                                samples = list(map(int, values))
                                native[section] = {"count": len(samples), "p99_us": p99(samples) if samples else None,
                                                   "max_us": max(samples) if samples else None}
                            measurements.append({"pair": pair, "enabled": enabled, "client_count": 1,
                                                 "save_count": len(save_us), "save_p99_us": p99(save_us),
                                                 "command_count": len(command_us), "command_p99_us": p99(command_us),
                                                 "native": native, "cpu_seconds": cpu_seconds, "workload_seconds": workload_seconds,
                                                 "rss_kib_max": max(rss), "save_samples_us": save_us, "command_samples_us": command_us,
                                                 "telemetry_snapshots": telemetry_snapshots})
                            (artifacts / (backend + "-performance.json")).write_text(json.dumps(measurements, indent=2))
                            print(json.dumps({key: value for key, value in measurements[-1].items()
                                              if key not in ("save_samples_us", "command_samples_us", "telemetry_snapshots")}), flush=True)
                            (artifacts / f"{backend}-persistence-{pair}-{enabled}.txt").write_text("\n".join(snapshots))
                    # Estimate p99 across all three matched runs, retaining each
                    # pair and every raw sample for review of host noise.
                    pooled = {}
                    for enabled in (False, True):
                        selected = [row for row in measurements if row["enabled"] == enabled]
                        pulses = []
                        for pair in range(3):
                            raw = (artifacts / f"{backend}-latency-{pair}-{enabled}.txt").read_text()
                            pulses.extend(int(value) for line in raw.splitlines()
                                          if line.startswith("total_tick ") for value in line.split()[2:])
                        saves = [value for row in selected for value in row["save_samples_us"]]
                        pooled[str(enabled)] = {"pulse_p99_us": p99(pulses), "pulse_count": len(pulses),
                                                "save_p99_us": p99(saves), "save_count": len(saves)}
                    (artifacts / (backend + "-performance-summary.json")).write_text(json.dumps(pooled, indent=2))
                    print(json.dumps({"pooled_three_pairs": pooled}), flush=True)
                    # Pooling is descriptive; each matched pair must meet the gate.
                    verify_performance_pairs(measurements)
                    print("PASS three paired gameplay/save performance comparisons")
                    return
                boot(); client = reconnect()
                client.send("vis 0"); client.expect("You are now visible")
                until(lambda: any(row["event"] == "duris_session" for row in received), "session not captured")
                companion = reconnect(companion_name, companion_account)
                companion.send("wield mace"); companion.expect("You wield")
                companion.send("kill raoul")
                deadline = time.monotonic() + 45
                while True:
                    outcome, _ = companion.expect_any(("is dead! R.I.P.", "You stumble"),
                                                       timeout=max(1, deadline - time.monotonic()))
                    if outcome == "is dead! R.I.P.":
                        break
                    assert time.monotonic() < deadline, "NPC combat did not finish"
                    companion.send("kill raoul")
                print("PASS mortal combat", backend, flush=True)
                client.send("advance " + companion_name + " 10")
                companion.expect("You advance to level 10.")
                companion.send("consent " + journey.CHARACTER)
                companion.expect("consent")
                client.send("group " + companion_name)
                client.expect("is now a member of your group.")
                client.send("wield mace"); client.expect("You wield")
                client.send("load mobile 11"); client.expect("You have created")
                client.send("kill raoul"); client.expect("is dead! R.I.P.", timeout=45)
                client.send("givepet " + journey.CHARACTER + " 22800")
                # setup_pet already adds its follower to the owner's group.
                client.expect("starts following you.")
                client.send("load mobile 11"); client.expect("You have created")
                client.send("order followers kill raoul")
                client.expect("is dead! R.I.P.", timeout=45)
                print("PASS level/group/player/pet gameplay", backend, flush=True)
                response["status"] = 503
                prior_attempts = len(attempts)
                companion.send("save"); companion.expect(f"Save complete for {companion_name}.")
                companion.send("quit"); companion.expect("ACCOUNT MENU", timeout=30)
                companion.close(); companion = None
                until(lambda: len(attempts) > prior_attempts, "outage did not reach capture endpoint")
                save()
                outage_health, before_copyover = health()
                assert "http=503" in outage_health, outage_health
                response["status"] = 200
                # Let the paced retry recover before copyover's 250ms deadline.
                until(lambda: any(row["event"] == "duris_session" and
                                  row["properties"].get("transition") == "logical_exit"
                                  for row in received), "capture did not recover after HTTP outage")
                print("PASS save during capture outage", backend, flush=True)
                client.enable_compression()
                time.sleep(4.2)
                copyover_state.parent.mkdir()
                # Fail at the real exec boundary using only the fixture binary.
                staged_binary = runtime / "bin/server/dms_new"
                staged_binary.write_text("synthetic invalid executable\n")
                staged_binary.chmod(0o700)
                process.send_signal(signal.SIGUSR1)
                client.expect("Copyover FAILED", timeout=60)
                client.send("look"); client.expect("The Regression Arena")
                save()
                until(lambda: any(row["event"] == "duris_encounter_summary" and
                                  row["properties"].get("actor_kind") == "pet"
                                  for row in received) and
                      any(row["event"] == "duris_session" and
                          row["properties"].get("transition") == "logical_exit"
                          for row in received), "capture did not recover after failed copyover")
                shutil.copy2(binary, staged_binary)
                copyover_state.unlink()
                process.send_signal(signal.SIGUSR1)
                client.expect("Copyover complete!", timeout=90)
                client.send("look"); client.expect("The Regression Arena")
                save()
                client.close(); client = None
                time.sleep(2.2)
                client = reconnect(); save()
                _, after_copyover = health()
                assert after_copyover >= before_copyover > 0
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                time.sleep(2.2)
                if cloud:
                    first_sessions = {row["properties"]["duris_session_id"] for row in received
                                      if row["event"] == "duris_session" and
                                      row["properties"]["duris_character_id"] == cloud_capture["main_id"]}
                    assert len(first_sessions) == 1, first_sessions
                    client.close(); client = reconnect(); save()
                    client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                    time.sleep(2.2)
                stop()
                if backend == "mariadb":
                    assert sql("SELECT COUNT(*) FROM telemetry_interval") == "0"
                summaries = [row["properties"] for row in received if row["event"] == "duris_character_summary"]
                sessions = [row["properties"] for row in received if row["event"] == "duris_session"]
                assert summaries and sessions
                main_id = sessions[0]["duris_character_id"]
                main_sessions = [row for row in summaries + sessions if row["duris_character_id"] == main_id]
                assert len({row["duris_session_id"] for row in main_sessions}) == (2 if cloud else 1), [
                    (row.get("transition", "summary"), row["duris_session_id"]) for row in main_sessions]
                assert len({row["uuid"] for row in received}) == len(received)
                encoded = json.dumps(received).lower()
                for private in (journey.CHARACTER, journey.ACCOUNT, companion_name, companion_account,
                                journey.PASSWORD, "127.0.0.1", "@example.invalid"):
                    assert private.lower() not in encoded, "private gameplay value reached capture"
                assert any(row["event"] == "duris_level_change" for row in received)
                encounter_rows = [row["properties"] for row in received if row["event"] == "duris_encounter_summary"]
                pets = [row for row in encounter_rows if row.get("actor_kind") == "pet"]
                assert pets and any(int(row["combat"]["damage_dealt"]) > 0 for row in pets)
                assert all(row["duris_owner_character_id"] == main_id and row["participant_usec"] is None
                           for row in pets)
                assert any(row.get("actor_kind") == "player" for row in encounter_rows), encounter_rows
                assert any(bucket["group_size"] >= 2 for row in summaries for bucket in row["time_allocations"])
                assert len({bucket["level_band"] for row in summaries for bucket in row["time_allocations"]}) >= 2
                assert any(int(row["xp"]["applied_xp"]) > 0 for row in summaries), summaries
                assert any(int(row["xp"]["zero_applied"]) > 0 for row in summaries), summaries
                for row in summaries:
                    for name, total in row["xp"].items():
                        assert int(total) == sum(int(bucket[name]) for bucket in row["xp_allocations"]) + int(row["unattributed_xp"][name])
                    for name, total in row["time"].items():
                        assert int(total) == sum(int(bucket[name]) for bucket in row["time_allocations"]) + int(row["unattributed_time"][name])
                evidence = read_evidence(ledger)
                assert evidence["producer_count"] >= 2
                quota = evidence["quota"]
                reserved = quota["normal_reserved"] + quota["health_reserved"]
                assert sum(attempts) <= reserved <= 100, (attempts, quota)
                totals = {name: sum(int(row["time"][name]) for row in summaries)
                          for name in ("connected_usec", "active_usec", "idle_usec", "unknown_usec", "resident_usec", "linkdead_usec")}
                assert totals["connected_usec"] == totals["active_usec"] + totals["idle_usec"] + totals["unknown_usec"]
                assert totals["resident_usec"] == totals["connected_usec"] + totals["linkdead_usec"]
                assert totals["idle_usec"] > 0 and totals["linkdead_usec"] > 0, totals
                if cloud:
                    with cloud_lock:
                        assert cloud_capture["repeated"] and cloud_capture["omitted"]
                        assert cloud_capture["attempts"] <= reserved <= 100
                        (cloud_state / "submitted.json").write_text(json.dumps(cloud_capture, indent=2))
                (artifacts / (backend + "-events.json")).write_text(json.dumps(received, indent=2))
                print(json.dumps({"backend": backend, "events": len(received), "attempted_events": sum(attempts),
                                  "quota_reserved": reserved, "time": totals}))
                print("PASS native gameplay/save/reload/reconnect/failed-and-successful-copyover")
        except Exception:
            (artifacts / (backend + "-failed-events.json")).write_text(json.dumps(received, indent=2))
            diagnostics = (runtime / "server.out").read_text(errors="replace") if (runtime / "server.out").exists() else ""
            diagnostics += "\n" + "\n".join(transcripts[-2:])
            for connected in (client, companion):
                if connected:
                    diagnostics += "\n" + bytes(connected.transcript[-6000:]).decode(errors="replace")
            (artifacts / (backend + "-failure.log")).write_text(diagnostics + "\n" + journey.runtime_logs(runtime))
            raise
        finally:
            stop()
            receiver.shutdown(); receiver.server_close(); receiver_thread.join(timeout=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), required=True)
    parser.add_argument("--performance", action="store_true", help="Run three paired ordinary-save workloads")
    parser.add_argument("--cloud", action="store_true", help="Send one synthetic campaign, maximum 100 charged attempts; reruns refused")
    args = parser.parse_args()
    if args.cloud and args.performance:
        parser.error("cloud capture and the paired benchmark are separate fixtures")
    run(args.backend, args.performance, args.cloud)
