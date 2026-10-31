#!/usr/bin/env python3
"""Real local bartender-quest journey for MariaDB and flatfile-primary builds.

This is intentionally a ``run_`` script rather than an automatically discovered
regression: it builds/boots the full world, exercises restart, and needs Docker for the
isolated MariaDB authority. It never reads the repository's .env and never uses
the long-running local stack. Every account/database/state root is disposable.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import signal
import random
import socket
import subprocess
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from test_flatfile_combat_journey import MudClient, reconnect_character, create_character


ROOT = pathlib.Path(__file__).resolve().parents[2]
BARTENDER_ROOM = 16633
QUEST_LEVEL = 11
# The migrations verify their schema on MariaDB 10.11 and MySQL 8.0 only.
DB_IMAGE = os.environ.get("DURIS_WORLD_QUEST_DB_IMAGE", "mariadb:10.11")
REQUESTED_BACKEND = os.environ.get("DURIS_WORLD_QUEST_BACKEND", "both")
BINARY_OVERRIDE = os.environ.get("DURIS_WORLD_QUEST_BINARY")
JOURNEY = os.environ.get("DURIS_WORLD_QUEST_JOURNEY", "both")
GAMEPLAY_CASES = tuple(tuple(map(int, case.split(":"))) for case in
                       os.environ.get("DURIS_WORLD_QUEST_GAMEPLAY_CASES",
                                      "11:2,11:1,29:1,29:2,30:1").split(","))
if not GAMEPLAY_CASES or any(case not in {(11, 2), (11, 1), (29, 1), (29, 2), (30, 1)}
                             for case in GAMEPLAY_CASES):
    raise ValueError("unsupported focused gameplay cases")
if JOURNEY not in {"both", "recovery", "gameplay", "audit", "reported", "history"}:
    raise ValueError("DURIS_WORLD_QUEST_JOURNEY must be both, recovery, gameplay, audit, reported, or history")
if REQUESTED_BACKEND not in {"both", "mariadb", "flatfile"}:
    raise ValueError("DURIS_WORLD_QUEST_BACKEND must be both, mariadb, or flatfile")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def available_ports() -> tuple[int, int, int]:
    for _ in range(200):
        probes = [socket.socket() for _ in range(3)]
        try:
            # Below the kernel's ephemeral range, which outgoing connections and
            # Docker's published ports draw from while the server is still booting.
            plain = random.randrange(20000, 32000)
            probes[0].bind(("127.0.0.1", plain))
            probes[1].bind(("127.0.0.1", plain + 1))
            probes[2].bind(("127.0.0.1", plain + 2))
            return plain, plain + 1, plain + 2
        except OSError:
            continue
        finally:
            for probe in probes:
                probe.close()
    raise AssertionError("could not reserve isolated listener ports")


def run(command: list[str], *, env: dict[str, str] | None = None,
        timeout: int = 600, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, env=env, input=input_bytes,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout, check=False)


def build_server(backend: str, build_root: pathlib.Path) -> pathlib.Path:
    if BINARY_OVERRIDE:
        binary = pathlib.Path(BINARY_OVERRIDE).resolve()
        require(binary.is_file() and os.access(binary, os.X_OK),
                f"configured binary override is not executable: {binary}")
        return binary
    backend_root = build_root / backend
    backend_root.mkdir(parents=True, exist_ok=True)
    binary = backend_root / "server" / "dms_new"
    result = run([
        "make", "-C", "src", f"PERSISTENCE_BACKEND={backend}",
        "BUILD_PROFILE=development", f"BIN_ROOT={backend_root}",
        f"OBJDIR={backend_root / 'objects' / 'server'}",
        f"SERVER_BIN_DIR={binary.parent}", f"DMS_BINARY={binary}", "-j2",
    ], timeout=600)
    require(result.returncode == 0,
            f"{backend} server build failed:\n{result.stdout[-12000:].decode(errors='replace')}")
    output = result.stdout.decode(errors="replace")
    if backend == "flatfile":
        require("-D__NO_MYSQL__" in output, "flat build did not define __NO_MYSQL__")
        require("-I/usr/include/mysql" not in output, "flat build used MySQL headers")
        require("-lmysqlclient" not in output, "flat build linked MySQL")
    else:
        require("-D__NO_MYSQL__" not in output, "MariaDB build selected flatfile mode")
    require(binary.is_file() and os.access(binary, os.X_OK),
            f"{backend} build did not create an executable")
    return binary


def wait_for_db(container: str, root_password: str) -> None:
    for _ in range(120):
        result = subprocess.run([
            "docker", "exec", "-e", "MYSQL_PWD=" + root_password,
            container, "mariadb", "-h127.0.0.1", "-uroot", "-N", "-e", "SELECT 1",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if result.returncode == 0:
            return
        time.sleep(1)
    raise AssertionError("isolated MariaDB did not become ready")


def docker_published_port(container: str) -> int:
    result = subprocess.run(
        ["docker", "port", container, "3306/tcp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    require(result.returncode == 0, "could not read disposable MariaDB published port")
    for mapping in result.stdout.splitlines():
        _, separator, port_text = mapping.strip().rpartition(":")
        if not separator:
            continue
        try:
            port = int(port_text)
        except ValueError:
            continue
        if 1024 < port <= 65535:
            return port
    raise AssertionError("disposable MariaDB did not publish a usable host port")


def start_database(database: str) -> tuple[str, int, str, str]:
    container = f"duris-world-quest-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    root_password = "root-" + uuid.uuid4().hex
    db_password = "db-" + uuid.uuid4().hex
    try:
        result = subprocess.run([
            "docker", "run", "--rm", "-d", "--name", container,
            "-e", "MARIADB_DATABASE=" + database,
            "-e", "MARIADB_USER=duris",
            "-e", "MARIADB_PASSWORD=" + db_password,
            "-e", "MARIADB_ROOT_PASSWORD=" + root_password,
            "--publish", "127.0.0.1::3306/tcp", DB_IMAGE,
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        require(result.returncode == 0, "could not start disposable MariaDB")
        host_port = docker_published_port(container)
        wait_for_db(container, root_password)
        bootstrap = (ROOT / "migrations" / "bootstrap_multithread_safe.sql").read_bytes()
        loaded = subprocess.run([
            "docker", "exec", "-i", "-e", "MYSQL_PWD=" + root_password,
            container, "mariadb", "-h127.0.0.1", "-uroot", database,
        ], input=bootstrap, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        require(loaded.returncode == 0,
                "disposable MariaDB bootstrap failed:\n" + loaded.stdout.decode(errors="replace")[-12000:])
        return container, host_port, root_password, db_password
    except BaseException:
        subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
        raise


def migration_environment(port: int, database: str, password: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({
        "ENVIRONMENT": "local",
        "DB_HOST": "127.0.0.1",
        "DB_PORT": str(port),
        "DB_USER": "duris",
        "DB_PASSWD": password,
        "DB_NAME": database,
        "DB_ALLOWED_TARGETS": "127.0.0.1/" + database,
        "DB_TLS": "FALSE",
        "DB_SOCKET": "",
        "REDIS": "FALSE",
    })
    return environment


def prepare_mariadb(database: str) -> tuple[str, int, str, str, dict[str, str]]:
    container, port, root_password, db_password = start_database(database)
    try:
        environment = migration_environment(port, database, db_password)
        adopted = run(["python3", "scripts/migration_runner.py", "adopt", "--kind", "fresh_bootstrap"], env=environment)
        require(adopted.returncode == 0,
                "fresh MariaDB baseline adoption failed:\n" + adopted.stdout.decode(errors="replace")[-12000:])
        migrated = run(["python3", "scripts/migration_runner.py", "run"], env=environment)
        require(migrated.returncode == 0,
                "fresh MariaDB migrations failed:\n" + migrated.stdout.decode(errors="replace")[-12000:])
    except BaseException:
        subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
        raise
    return container, port, root_password, db_password, environment


def setup_run_root(run_root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    for directory in ("areas", "docs"):
        (run_root / directory).symlink_to(ROOT / directory, target_is_directory=True)
    shutil.copytree(ROOT / "lib", run_root / "lib")
    if JOURNEY == "reported":
        # Exercise the supported sharing path without changing repository settings.
        properties = run_root / "lib" / "duris.properties"
        properties.write_text(properties.read_text().replace("world.quest.share.max=0",
                                                             "world.quest.share.max=2"))
    (run_root / "logs" / "log").mkdir(parents=True)
    (run_root / "logs" / "log" / ".gitignore").write_text("*\n!.gitignore\n")
    journals = run_root / "journals"
    player_journal = journals / "players"
    critical_journal = journals / "critical"
    player_journal.mkdir(parents=True, mode=0o700)
    critical_journal.mkdir(mode=0o700)
    certificate = run_root / "duris.crt"
    private_key = run_root / "duris.key"
    generated = run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes",
        "-days", "1", "-subj", "/CN=localhost", "-keyout", str(private_key),
        "-out", str(certificate),
    ], timeout=30)
    require(generated.returncode == 0, "could not create isolated TLS certificate")
    private_key.chmod(0o600)
    return player_journal, critical_journal, run_root / "boot.out"


def runtime_environment(backend: str, state_root: pathlib.Path, player_journal: pathlib.Path,
                        critical_journal: pathlib.Path, plain_port: int, tls_port: int,
                        websocket_port: int, database_environment: dict[str, str] | None) -> dict[str, str]:
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ENVIRONMENT": "local",
        "PERSISTENCE_MODE": "flatfile-primary" if backend == "flatfile" else "mariadb-primary",
        "CRITICAL_COMMAND_JOURNAL_DIR": str(critical_journal),
        "LISTEN_ADDRESS": "127.0.0.1",
        "DURIS_TLS_PORT": str(tls_port),
        "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1",
        "DURIS_WEBSOCKET_PORT": str(websocket_port),
        "REDIS": "FALSE",
        "CHAOS_MUD": "TRUE",
        "CHAOS_TEST_COMMANDS": "TRUE",
        "CHAOS_TEST_ACCOUNT": "Journeyacct",
        "CHAOS_STARTER_BONUSES": "FALSE",
    }
    if backend == "flatfile":
        environment["FLATFILE_STATE_DIR"] = str(state_root)
    else:
        if database_environment is None:
            raise AssertionError("MariaDB runtime environment missing")
        environment.update({key: database_environment[key] for key in (
            "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWD", "DB_NAME",
            "DB_ALLOWED_TARGETS", "DB_TLS", "DB_SOCKET",
        )})
    return environment


def wait_for_boot(process: subprocess.Popen[str], output_path: pathlib.Path) -> str:
    deadline = time.monotonic() + 180
    output = ""
    while time.monotonic() < deadline:
        output = output_path.read_text(errors="replace")
        if "Entering game loop." in output:
            evidence = output + "\n" + collect_logs(output_path.parent)
            require("World quest catalog ready:" in evidence,
                    "server entered the game loop without catalog-ready evidence:\n" + evidence[-12000:])
            return evidence
        if process.poll() is not None:
            break
        time.sleep(0.1)
    raise AssertionError("server did not reach the game loop:\n" + output[-16000:])


def collect_logs(run_root: pathlib.Path) -> str:
    sections = []
    for path in sorted((run_root / "logs" / "log").glob("*")):
        if not path.is_file() or path.name == ".gitignore":
            continue
        text = path.read_text(errors="replace").strip()
        if text:
            sections.append(f"--- {path.name} ---\n{text[-12000:]}")
    return "\n".join(sections)[-50000:]


# Test-only debugger setup and native-state inspection. Recovery closes
# disposable zones; quest transitions, payments, saves and loads use real commands.
RECOVERY_PROBE_PATH = ROOT / "tests/async/world_quest_journey_probe.cpp"
RECOVERY_PROBE_SOURCE = RECOVERY_PROBE_PATH.read_text()

JOURNEY_FIELDS = (
    "active", "replacement_due", "origin", "level", "type", "mob", "zone", "started",
    "receiver", "shares", "kills", "quota", "map_room", "map_bought", "wallet", "xp",
)
snapshot_request = 0


def read_journey_states(run_root: pathlib.Path) -> list[dict]:
    records = []
    for line in (run_root / "quest-journey.tsv").read_text().splitlines():
        label, *values = line.split("\t")
        require(len(values) == len(JOURNEY_FIELDS), "incomplete debugger checkpoint")
        records.append({"label": label, **dict(zip(JOURNEY_FIELDS, map(int, values)))})
    return records


def gameplay_snapshot(client: MudClient, run_root: pathlib.Path) -> dict:
    global snapshot_request
    snapshot_request += 1
    request = f"questprobe_{snapshot_request}"
    path = run_root / "quest-gameplay.json"
    # Consume the preceding command's complete output, then synchronize this
    # explicitly tagged SCORE through its response and following prompt.
    while client._receive():
        pass
    client.pending.clear()
    client.send("score " + request)
    client.expect("Score information for", timeout=30)
    client.expect("Pos:", timeout=30)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if path.exists():
            current = json.loads(path.read_text())
            if current.get("request") == request:
                client._receive()
                return current
        client._receive()
    raise AssertionError("gameplay score checkpoint did not arrive")


def settled_gameplay_snapshot(client: MudClient, run_root: pathlib.Path) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = gameplay_snapshot(client, run_root)
        if not state["items_busy"] and state["remaining"] >= 0 and state["history_done"] >= 0:
            return state
        time.sleep(0.1)
    raise AssertionError(f"gameplay ownership/history did not settle: {state}")


def navigate_quest(client: MudClient, run_root: pathlib.Path, *, returning: bool = False,
                   before_kills: int | None = None) -> tuple[dict, int]:
    steps, route_waits = 0, 0
    for _ in range(150):
        state = gameplay_snapshot(client, run_root)
        state["route_waits"] = route_waits
        require(not state["due"], f"assignment became unavailable during travel: {state}")
        if not returning and (not state["active"] or
                              (before_kills is not None and state["kills"] > before_kills)):
            return state, steps
        if returning and state["room"] == state["route_origin"]:
            return state, steps
        if state["fighting"]:
            for _ in range(60):
                time.sleep(1)
                state = gameplay_snapshot(client, run_root)
                if not returning and (not state["active"] or
                                      (before_kills is not None and state["kills"] > before_kills)):
                    return state, steps
                if not state["fighting"]:
                    break
            else:
                raise AssertionError(f"ordinary combat did not resolve: {state}")
            continue
        if state.get("selector"):
            return state, steps
        path = state["path"]
        if not path and route_waits < 30:
            route_waits += 1
            time.sleep(1)
            continue
        require(path, f"no route to a current routine target after {route_waits} waits: {state}")
        if state["moves"] < 25:
            client.send("rest")
            for _ in range(30):
                time.sleep(1)
                rested = gameplay_snapshot(client, run_root)
                if rested["moves"] >= min(70, rested["max_moves"]):
                    break
            client.send("stand")
            continue
        posture = state["position"]
        batch = path[:8]
        for step in batch:
            if step["crawl"] and posture != 2:
                client.send("kneel")
                posture = 2
            elif not step["crawl"] and posture != 3:
                client.send("stand")
                posture = 3
            if step["closed"]:
                client.send("open " + step["direction"])
            client.send(step["direction"])
        observed = gameplay_snapshot(client, run_root)
        if observed["room"] == batch[-1]["to"]:
            steps += len(batch)
        elif observed["fighting"]:
            prefix = [batch[0]["from"]] + [step["to"] for step in batch]
            require(observed["room"] in prefix,
                    f"combat displaced the journey off its path: {observed}")
            steps += prefix.index(observed["room"])
        else:
            raise AssertionError(f"ordinary commands diverged from {batch[-1]}: {observed}")
    raise AssertionError("target navigation exceeded 1,200 ordinary steps")


def stop_quest_server(process: subprocess.Popen[str], pid_path: pathlib.Path,
                      output_path: pathlib.Path) -> str:
    os.kill(int(pid_path.read_text()), signal.SIGTERM)
    process.wait(timeout=30)
    output = output_path.read_text(errors="replace")
    require(process.returncode == 0 and "Normal termination of game." in output,
            "journey server did not stop normally:\n" + output[-6000:])
    require(output.count("World quest catalog ready:") == 1,
            "catalog was rebuilt during commands")
    return output


def stored_gameplay_history(environment: dict[str, str] | None, state: dict) -> int:
    if environment is None:
        return state["stored_history"]
    query = f"SELECT COUNT(*) FROM world_quest_accomplished WHERE pid={state['player_id']};"
    result = subprocess.run([
        "mysql", "--protocol=tcp", "--ssl=0", "-h", environment["DB_HOST"],
        "-P", environment["DB_PORT"], "-u", environment["DB_USER"], "-N", "-B",
        environment["DB_NAME"], "-e", query,
    ], env={**environment, "MYSQL_PWD": environment["DB_PASSWD"]},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    require(result.returncode == 0, "could not read disposable completion history")
    return int(result.stdout.strip())


def perform_gameplay(client: MudClient, run_root: pathlib.Path, restart,
                     database_environment, *, origin: int = BARTENDER_ROOM,
                     cases=GAMEPLAY_CASES) -> tuple[MudClient, list[dict]]:
    results = []
    partial_persisted = False
    rewards = set()
    for level, kind in cases:
        (run_root / "quest-gameplay-control.txt").write_text(f"{level} {kind} 1 {origin}\n")
        client.send(f"chaos questroom {origin}" if origin == BARTENDER_ROOM else "chaos")
        if origin == BARTENDER_ROOM:
            client.expect("Quest-room test funds committed.", timeout=60)
        before = gameplay_snapshot(client, run_root)
        if before["active"] or before["due"]:
            client.send("ask bartender abandon confirm")
            client.expect("You no longer have a task.", timeout=30)
            client.send("chaos")  # Prepare the now-inactive case's target fixture.
            before = settled_gameplay_snapshot(client, run_root)
        attempts = []
        for _ in range(8):
            client.send("ask bartender quest")
            client.expect_any(("Go kill ", "Go ask "), timeout=30)
            accepted = gameplay_snapshot(client, run_root)
            require(accepted["accepted_level"] == level,
                    f"requested gameplay level was unavailable: {accepted}")
            attempts.append({"mob": accepted["mob"], "zone": accepted["zone"], "quota": accepted["quota"]})
            if (accepted["type"] == kind and
                    (kind != 1 or level != 29 or accepted["quota"] >= 2) and
                    (accepted["path"] or accepted.get("selector"))):
                if kind == 2:
                    require(accepted["target_level"] < level - 4 or
                            accepted["target_level"] > level + 5,
                            "ASK completion fixture did not exercise the restored level range")
                break
            # Only fixture preparation: pay the ordinary abandonment fee before
            # making any progress. The preferred kind can legitimately fall back
            # to the other type in a selected zone; KILL also needs a partial state.
            client.send("ask bartender abandon confirm")
            client.expect("You no longer have a task.", timeout=30)
        else:
            raise AssertionError(f"no qualifying level-{level} type-{kind} task within eight purchases: {attempts}")
        baseline_items = {item["uid"] for item in accepted["items"]}
        history_before = stored_gameplay_history(database_environment, accepted)
        steps, partials = 0, []
        previous = accepted
        for _ in range(40):
            target, travelled = navigate_quest(client, run_root,
                                              before_kills=previous["kills"] if kind == 1 else None)
            steps += travelled
            if not target["active"]:
                completed = target
                break
            if kind == 1 and target["kills"] > previous["kills"]:
                current = target
            elif kind == 2:
                client.send(f"ask {target['selector']} {target['month']}")
                outcome, _ = client.expect_any(("You gain some experience.",
                                                "No-one by that name here..."), timeout=30)
            else:
                client.send(f"kill {target['selector']}")
                # A native rescuer may become our opponent before the target
                # dies. Observe real combat rather than demand quest feedback
                # from every fight or manufacture credit for the rescuer.
                for _ in range(120):
                    time.sleep(1)
                    current = gameplay_snapshot(client, run_root)
                    if (not current["active"] or current["kills"] > previous["kills"] or
                            not current["fighting"]):
                        break
                else:
                    raise AssertionError(f"ordinary target combat did not resolve: {current}")
                if current["active"] and current["kills"] == previous["kills"]:
                    continue
                target = current

            if kind == 2:
                if outcome == "No-one by that name here...":
                    continue
                current = gameplay_snapshot(client, run_root)
            if kind == 1 and current["active"] and current["kills"] == current["quota"]:
                # The final kill stays active while its durable reward is published.
                # History may already be committed; this is not partial progress.
                deadline = time.monotonic() + 30
                while current["active"] and time.monotonic() < deadline:
                    time.sleep(0.1)
                    current = settled_gameplay_snapshot(client, run_root)
                require(not current["active"], "final KILL reward publication did not finish")
            if not current["active"]:
                completed = current
                break
            require(kind == 1 and current["kills"] > previous["kills"],
                    f"combat made no legitimate quest progress: {current}")
            require(current["quota"] == accepted["quota"] and current["history_done"] == 0,
                    "partial combat altered quota or consumed history")
            require(stored_gameplay_history(database_environment, current) == history_before,
                    "partial combat wrote a completion-history entry")
            if current["actor_level"] == previous["actor_level"]:
                require(current["remaining"] == previous["remaining"],
                        "partial combat changed allowance without a level change")
            require(current["progress_xp"] > previous["progress_xp"], "partial combat awarded no actual XP")
            partials.append(current)
            if not partial_persisted and level == 29 and (29, 1) in cases:
                client.send("save")
                client.expect("Save complete for Taverek.", timeout=120)
                saved = gameplay_snapshot(client, run_root)
                require(saved["active"] and saved["kills"] < saved["quota"],
                        "combat completed before the partial checkpoint")
                client = restart(client)
                restored = settled_gameplay_snapshot(client, run_root)
                kept = ("active", "due", "accepted_level", "type", "mob", "zone", "kills",
                        "quota", "map_bought", "map_room", "origin", "receiver", "shares", "started",
                        "wallet", "xp")
                require(all(saved[k] == restored[k] for k in kept),
                        f"partial state did not survive restart: {saved} -> {restored}")
                # Restore only NPC fixture positions after world reload. Keep
                # the reconnected actor's actual level and all saved quest data.
                (run_root / "quest-gameplay-control.txt").write_text(
                    f"{restored['actor_level']} {kind} 1 {origin}\n")
                client.send("chaos")
                pinned = settled_gameplay_snapshot(client, run_root)
                require(all(restored[k] == pinned[k] for k in kept),
                        "NPC fixture preparation changed saved player state")
                (run_root / "quest-gameplay-control.txt").write_text(f"{level} {kind} 1 {origin}\n")
                held_rewards = rewards & {item["uid"] for item in saved["items"]}
                require(not rewards or held_rewards and held_rewards <= {item["uid"] for item in restored["items"]},
                        "held earlier quest rewards did not persist")
                partials.append({"saved": saved, "restored": restored})
                partial_persisted = True
                current = pinned
            previous = current
        else:
            raise AssertionError("quest did not complete within forty real interactions")
        completed = settled_gameplay_snapshot(client, run_root)
        require(not completed["active"] and not completed["due"], f"quest did not complete: {completed}")
        require(completed["history_done"] == 1, f"completion history missing: {completed}")
        require(completed["progress_xp"] > previous["progress_xp"], "real completion awarded no XP")
        require(completed["completion_target"] == accepted["mob"] and
                completed["completion_remaining_at_level"] ==
                max(completed["completion_remaining"] - 1, 0) and
                completed["completion_calls"] == previous["completion_calls"] + 1,
                "completion did not use exactly one allowance at its actual level")
        new_items = [item for item in completed["items"]
                     if item["uid"] == completed["reward_uid"] and item["vnum"] == completed["reward_vnum"]]
        require(completed["reward_uid"] not in baseline_items and len(new_items) == 1,
                f"level {level} kind {kind} mob {accepted['mob']} completion reward missing: {new_items}; state={completed}")
        rewards.add(new_items[0]["uid"])
        client.send("save")
        client.expect("Save complete for Taverek.", timeout=120)
        deadline = time.monotonic() + 30
        while stored_gameplay_history(database_environment, completed) != history_before + 1:
            require(time.monotonic() < deadline, "completion did not persist exactly one history row")
            time.sleep(0.1)
            completed = settled_gameplay_snapshot(client, run_root)
        returned, return_steps = navigate_quest(client, run_root, returning=True)
        results.append({"level": level, "kind": kind, "ordinary_steps": steps,
                        "return_steps": return_steps, "attempts": attempts, "accepted": accepted,
                        "target": target, "partials": partials, "reward": new_items[0],
                        "completed": completed, "returned": returned})
        (run_root / "quest-gameplay-results.json").write_text(json.dumps(results))
    require((29, 1) not in cases or partial_persisted,
            "no real partial-progress restart was qualified")
    return client, results


def perform_reported(client: MudClient, run_root: pathlib.Path, restart,
                     database_environment, port: int) -> tuple[MudClient, dict]:
    results = []
    def place(actor, level, origin):
        (run_root / "quest-gameplay-control.txt").write_text(f"{level} 1 4 {origin}\n")
        (run_root / "quest-reported-setup.txt").write_text("0\n")
        actor.send("chaos")
        return settled_gameplay_snapshot(actor, run_root)

    def setup(action):
        (run_root / "quest-reported-setup.txt").write_text(f"{action}\n")
        client.send("chaos")
        return settled_gameplay_snapshot(client, run_root)

    def purchase(actor):
        actor.send("ask bartender quest")
        actor.expect_any(("Go ask ", "Go kill ", "Please come back later.",
                          "Try one of my colleagues around the world."), timeout=30)
        return settled_gameplay_snapshot(actor, run_root)

    def persist(state):
        nonlocal client
        client.send("save")
        client.expect("Save complete for Taverek.", timeout=120)
        history = stored_gameplay_history(database_environment, state)
        client = restart(client)
        # Chaos entry restores its level-56 floor. Reapply only the requested
        # actor level; saved quest, purse and history are observed unchanged.
        client.send("chaos")
        restored = settled_gameplay_snapshot(client, run_root)
        fields = ("active", "due", "origin", "accepted_level", "type", "mob", "zone",
                  "kills", "quota", "map_bought", "receiver", "shares", "started",
                  "wallet", "remaining", "giver")
        require(all(state[k] == restored[k] for k in fields),
                f"reported-giver state did not persist: {state} -> {restored}")
        require(stored_gameplay_history(database_environment, restored) == history,
                "reported-giver history changed across restart")
        return restored

    observer = MudClient(port, source_host="127.0.0.2")
    try:
        create_character(observer, expected_room=None, account="Observeacct", character="Vimerek",
                         race_name="d", alignment="e", hometown="c")
        for actor, side in ((client, "good"), (observer, "evil")):
            for origin in (1734, 74339, 132560):
                if side == "evil" and origin == 132560:
                    continue  # Tharnadia is a Good hometown; #500's givers are neutral.
                for level in (29, 30):
                    before = place(actor, level, origin)
                    granted = purchase(actor)
                    expected = True  # Both attached regions are valid below 30 too.
                    require(bool(granted["active"]) == expected,
                            f"unexpected {side} giver {origin}/{level} result: {granted}")
                    require(before["wallet"] - granted["wallet"] == (level * 20 if expected else 0),
                            "purchase/refund changed the wrong wallet value")
                    results.append({"side": side, "origin": origin, "level": level,
                                    "before": before, "result": granted})
                    if expected:
                        actor.send("ask bartender abandon")
                        actor.expect("You no longer have a task.", timeout=30)
    finally:
        observer.close()

    # Real consent/share/map commands, with every exit at the giver locked in
    # disposable memory. Both copied and paid state must survive a server restart.
    partner = MudClient(port, source_host="127.0.0.3")
    try:
        create_character(partner, expected_room=None, account="Shareacct", character="Nimerek",
                         hometown="p")
        partner.send("wear all")
        place(partner, 29, 1734)
        place(client, 29, 1734)
        shared_source = purchase(client)
        setup(7)
        partner.send("consent Taverek")
        partner.expect("You attempt to give consent", timeout=30)
        client.expect("has just given you", timeout=30)
        client.send("quest share Nimerek")
        client.expect("You've shared your quest.", timeout=30)
        partner.expect("You receive a quest.", timeout=30)
        shared = settled_gameplay_snapshot(partner, run_root)
        source_after_share = settled_gameplay_snapshot(client, run_root)
        copied = ("origin", "accepted_level", "type", "mob", "zone", "kills", "quota",
                  "giver", "receiver", "started")
        require(all(shared[k] == shared_source[k] for k in copied) and shared["active"] and
                source_after_share["shares"] == shared_source["shares"] - 1 and
                source_after_share["wallet"] == shared_source["wallet"],
                "locked-route share changed copied work, wallet or share count")
        partner.send("ask bartender map")
        partner.expect("will now show you additional information", timeout=30)
        mapped = settled_gameplay_snapshot(partner, run_root)
        require(mapped["map_bought"] and mapped["wallet"] == shared["wallet"] - 290 and
                mapped["remaining"] == shared["remaining"] and not mapped["due"],
                "locked-route map purchase changed entitlement/history or charged incorrectly")
        partner.send("save")
        partner.expect("Save complete for Nimerek.", timeout=120)
        client.send("save")
        client.expect("Save complete for Taverek.", timeout=120)
        partner.close()
        client = restart(client)
        client.send("chaos")  # Reapply current actor level only; no setup action is pending.
        partner = reconnect_character(port, expected_room=None, account="Shareacct",
                                      character="Nimerek", source_host="127.0.0.3")
        partner.expect("Pos:", timeout=60)
        partner.send("chaos")
        restored_share = settled_gameplay_snapshot(partner, run_root)
        restored_source = settled_gameplay_snapshot(client, run_root)
        persisted = (*copied, "map_bought", "map_room", "wallet", "remaining", "shares")
        require(all(restored_share[k] == mapped[k] for k in persisted) and
                all(restored_source[k] == source_after_share[k] for k in persisted),
                "shared quest/map or source share count changed across restart")
        sharing = {"source": shared_source, "shared": shared, "mapped": mapped,
                   "restored": restored_share, "restored_source": restored_source}
        for actor in (client, partner):
            actor.send("ask bartender abandon")
            actor.expect("You no longer have a task.", timeout=30)
    finally:
        partner.close()

    transitions = []
    for origin, level in ((1734, 29), (1734, 30), (74339, 29), (74339, 30),
                          (132560, 29), (132560, 30)):
        before = place(client, level, origin)
        accepted = purchase(client)
        aged = setup(1)
        require(aged["active"] and aged["started"] < time.time() - 24 * 3600,
                "aged task expired before abandonment")
        client.send("ask bartender abandon")
        client.expect("You no longer have a task.", timeout=30)
        abandoned = settled_gameplay_snapshot(client, run_root)
        require(not abandoned["active"] and not abandoned["due"] and
                abandoned["remaining"] == accepted["remaining"] and
                abandoned["wallet"] == aged["wallet"] - int(0.25 * level ** 3 / 100),
                "aged zero-progress abandon changed fee/allowance/state")
        persist(abandoned)
        regrant = purchase(client)
        require(regrant["active"] and regrant["origin"] == origin and
                regrant["wallet"] == abandoned["wallet"] - level * 20,
                "regrant after saved abandonment failed")
        persist(regrant)
        # Both commands enter before either payment response is read.
        client.socket.sendall(b"ask bartender abandon\nask bartender quest\n")
        client.expect("You no longer have a task.", timeout=30)
        client.expect_any(("Go ask ", "Go kill "), timeout=30)
        queued = settled_gameplay_snapshot(client, run_root)
        require(queued["active"] and queued["remaining"] == before["remaining"] and
                stored_gameplay_history(database_environment, queued) == 0,
                "queued zero-progress reroll consumed history/allowance")
        transitions.append({"origin": origin, "level": level, "accepted": accepted,
                            "abandoned": abandoned, "regrant": regrant, "queued": queued})
        client.send("ask bartender abandon")
        client.expect("You no longer have a task.", timeout=30)

    place(client, 30, 132560)
    for _ in range(8):
        accepted = purchase(client)
        if accepted["type"] == 1 and accepted["quota"] > 1:
            break
        # Preferred KILL can legitimately fall back to ASK in a sampled zone.
        client.send("ask bartender abandon")
        client.expect("You no longer have a task.", timeout=30)
    else:
        raise AssertionError("progressed-abandon fixture found no KILL task")
    progressed = setup(2)
    client.send("ask bartender abandon")
    client.expect("abandon confirm", timeout=30)
    unchanged = settled_gameplay_snapshot(client, run_root)
    require(unchanged["wallet"] == progressed["wallet"] and unchanged["active"],
            "unconfirmed progressed abandonment changed work or wallet")
    client.send("ask bartender abandon confirm")
    client.expect("You no longer have a task.", timeout=30)
    abandoned = settled_gameplay_snapshot(client, run_root)
    require(abandoned["remaining"] == progressed["remaining"] - 1 and
            abandoned["history_done"] == 1, "progressed abandonment did not consume history once")
    persist(abandoned)
    accepted = purchase(client)
    require(accepted["active"] and accepted["mob"] != progressed["mob"],
            "progressed-abandon target was issued again")
    setup(3)
    client.send("ask bartender quest")
    client.expect_any(("Go ask ", "Go kill "), timeout=30)
    bound = settled_gameplay_snapshot(client, run_root)
    require(bound["origin"] == 132560 and bound["wallet"] == accepted["wallet"],
            "legacy origin binding charged or lost accepted work")
    client.send("ask bartender map")
    client.expect("will now show you additional information", timeout=30)
    setup(4)
    client.send("quest")
    client.expect("Your task is no longer available.", timeout=30)
    pending = settled_gameplay_snapshot(client, run_root)
    client.send("ask bartender quest")
    client.expect("Your free replacement and earned progress remain yours.", timeout=30)
    waiting = settled_gameplay_snapshot(client, run_root)
    require(waiting["due"] and waiting["wallet"] == pending["wallet"],
            "unavailable replacement was charged or discarded")
    restored = persist(waiting)
    client.send("ask bartender quest")
    client.expect("Here is your free replacement.", timeout=30)
    replacement = settled_gameplay_snapshot(client, run_root)
    require(replacement["active"] and not replacement["due"] and
            all(replacement[k] == restored[k] for k in
                ("type", "accepted_level", "kills", "quota", "map_bought", "wallet", "remaining")),
            "replacement lost progress/map or charged money/allowance")
    persist(replacement)
    client.send("ask bartender abandon confirm")
    client.expect("You no longer have a task.", timeout=30)
    client, gameplay = perform_gameplay(client, run_root, restart, database_environment,
                                       origin=74339, cases=((30, 2), (30, 1)))
    return client, {"matrix": results, "transitions": transitions,
                    "sharing": sharing,
                    "progressed": progressed, "pending": waiting, "replacement": replacement,
                    "bloodstone_gameplay": gameplay}


def perform_history_regrant(client: MudClient, run_root: pathlib.Path, restart,
                            database_environment) -> tuple[MudClient, dict]:
    (run_root / "quest-gameplay-control.txt").write_text("30 1 4 132560\n")
    (run_root / "quest-reported-setup.txt").write_text("0\n")
    client.send("chaos")
    before = settled_gameplay_snapshot(client, run_root)
    client.send("ask bartender quest")
    client.expect_any(("Go ask ", "Go kill "), timeout=30)
    accepted = settled_gameplay_snapshot(client, run_root)
    (run_root / "quest-reported-setup.txt").write_text("1\n")
    client.send("chaos")
    aged = settled_gameplay_snapshot(client, run_root)
    (run_root / "quest-reported-setup.txt").write_text("6\n")
    client.send("chaos")
    deadline = time.monotonic() + 60
    while not (run_root / "quest-history-ready.txt").exists():
        require(time.monotonic() < deadline, "history fixture did not publish")
        client._receive()
    loaded = gameplay_snapshot(client, run_root)
    client.send("ask bartender abandon")
    client.expect("You no longer have a task.", timeout=30)
    abandoned = settled_gameplay_snapshot(client, run_root)
    client.send("ask bartender quest")
    client.expect_any(("Go ask ", "Go kill ", "any more quests"), timeout=30)
    regrant = settled_gameplay_snapshot(client, run_root)
    require(regrant["active"], f"Tharnadia regrant refused with only yesterday's history: {loaded} -> {regrant}")
    require(regrant["remaining"] == before["remaining"] and
            regrant["wallet"] == abandoned["wallet"] - 600,
            "history rollover changed allowance or purchase fee")
    client.send("save")
    client.expect("Save complete for Taverek.", timeout=120)
    client = restart(client)
    client.send("chaos")  # Reapply only the test actor's level after Chaos entry.
    restored = settled_gameplay_snapshot(client, run_root)
    require(all(restored[k] == regrant[k] for k in
                ("active", "due", "mob", "type", "origin", "wallet", "remaining")),
            "history-rollover regrant did not survive restart")
    persisted = (restored["yesterday_history"] if database_environment is None else
                 stored_gameplay_history(database_environment, restored))
    require(persisted == before["remaining"] and restored["retained_history"] == 1,
            "zero-progress abandonment wrote or lost completion history")
    return client, {"before": before, "accepted": accepted, "aged": aged,
                    "loaded": loaded, "abandoned": abandoned, "regrant": regrant,
                    "restored": restored}


def perform_world_audit(client: MudClient, run_root: pathlib.Path, port: int) -> dict:
    def inspect(actor: MudClient, *, place: bool = True) -> dict:
        path = run_root / "quest-world-audit.json"
        path.unlink(missing_ok=True)
        (run_root / "quest-gameplay-control.txt").write_text("29 0 3\n")
        if place:
            actor.send(f"chaos questroom {BARTENDER_ROOM}")
            actor.expect("Quest-room test funds committed.", timeout=60)
        actor.send("score questprobe")
        deadline = time.monotonic() + 120
        while not path.exists():
            require(time.monotonic() < deadline, "loaded-world audit did not arrive")
            actor._receive()
        actor.expect("Score information for", timeout=30)
        actor.expect("Pos:", timeout=30)
        return json.loads(path.read_text())

    good = inspect(client)
    observer = MudClient(port, source_host="127.0.0.2")
    try:
        create_character(observer, expected_room=None, account="Observeacct", character="Vimerek",
                         race_name="d", alignment="e", hometown="c")
        evil = inspect(observer, place=False)
        require(good["racewar"] != evil["racewar"], "observer did not acquire its native Evil side")
        require(any(x["level"] == 11 and x["failure"] == 0 for x in good["origins"]),
                "loaded Good origins lost every usable level-11 target")
        require(any(x["level"] == 29 and x["failure"] == 0 for x in evil["origins"]),
                "loaded Evil origins lost every usable level-29 target")
        require(any(x["level"] == 29 and x["underdark_map_rooms"] > 0 for x in evil["origins"]),
                "no level-29 origin has an attached Underdark region")

        # Disable every sampling/RNG/history breakpoint before timing real commands.
        # The idle debugger performs no stops inside this measurement window.
        (run_root / "quest-gameplay-control.txt").write_text("29 0 2\n")
        client.send(f"chaos questroom {BARTENDER_ROOM}")
        client.expect("Quest-room test funds committed.", timeout=60)

        def timed(actor: MudClient, command: str, replies: tuple[str, ...]) -> float:
            started = time.monotonic()
            actor.send(command)
            actor.expect_any(replies, timeout=30)
            return (time.monotonic() - started) * 1000

        def observe() -> list[float]:
            samples = []
            for _ in range(64):
                samples.append(timed(observer, "score", ("Score information for Vimerek",)))
                observer.expect("Pos:", timeout=30)
            return samples

        commands = []
        with ThreadPoolExecutor(max_workers=1) as executor:
            observed = executor.submit(observe)
            for _ in range(12):
                commands.append({"command": "purchase", "ms": timed(
                    client, "ask bartender quest", ("Go ask ", "Go kill "))})
                commands.append({"command": "quest", "ms": timed(
                    client, "quest", ("Go ask ", "Go kill "))})
                commands.append({"command": "abandon", "ms": timed(
                    client, "ask bartender abandon confirm", ("You no longer have a task.",))})
            observer_samples = observed.result()
        require(max(observer_samples) < 1000,
                f"observer response exceeded one second: {observer_samples}")
        return {"good": good, "evil": evil, "commands": commands,
                "observer_ms": observer_samples}
    finally:
        observer.close()


def perform_quest_journey(binary: pathlib.Path, backend: str, state_root: pathlib.Path,
                          database_environment: dict[str, str] | None) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"world-quest-{backend}-run-", dir=ROOT / "bin/tests") as run_tmp:
        run_root = pathlib.Path(run_tmp)
        player_journal, critical_journal, output_path = setup_run_root(run_root)
        plain_port, tls_port, websocket_port = available_ports()
        environment = runtime_environment(
            backend, state_root, player_journal, critical_journal, plain_port,
            tls_port, websocket_port, database_environment)
        # Chaos creation starts at 56. Set only the disposable actor's level
        # at explicit per-case setup; route policy below 30 ignores travel gear.
        # Leave production commands and content unchanged.
        pid_path = run_root / "inferior.pid"
        gdb_path = run_root / "quest.gdb"
        probe_source = run_root / "recovery_probe.cpp"
        probe_binary = run_root / "recovery_probe.so"
        probe_source.write_text(RECOVERY_PROBE_SOURCE)
        flags = (["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else
                 subprocess.check_output(["mysql_config", "--cflags"], text=True).split())
        built = run(["g++", "-std=c++20", "-g", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror",
                     "-fsanitize=undefined", "-fno-sanitize-recover=all", "-Isrc", *flags,
                     str(probe_source), "-lcjson", "-o", str(probe_binary)], timeout=60)
        require(built.returncode == 0, built.stdout.decode(errors="replace"))


        type_line = next(i + 1 for i, line in enumerate(
            (ROOT / "src/world/world_quest_policy.c").read_text().splitlines())
            if "const int type_attempts =" in line)
        (run_root / "quest-gameplay-control.txt").write_text(f"{QUEST_LEVEL} 0 0\n")

        boot_count = 0

        def launch(restarted: bool = False) -> subprocess.Popen[str]:
            nonlocal boot_count
            boot_count += 1
            # Raw SysV x86-64 entry arguments avoid pre-prologue DWARF values.
            script = f"""
set pagination off
set confirm off
set startup-with-shell off
handle SIGTERM nostop noprint pass
handle SIGPIPE nostop noprint pass
set $journey_invalidate = {0 if restarted else 1}
define apply_journey_mode
if quest_gameplay_stage > 0
disable $checkpoint_break
disable $invalidate_break
end
if quest_gameplay_stage == 1 || quest_gameplay_stage == 3 || quest_gameplay_stage == 4
enable $plan_break
else
disable $plan_break
end
if quest_gameplay_stage == 1 || quest_gameplay_stage == 4
enable $kind_break
enable $history_break
else
disable $kind_break
disable $history_break
end
if quest_gameplay_stage == 1
enable $fixture_zone_break
enable $fixture_suggest_break
else
disable $fixture_zone_break
disable $fixture_suggest_break
end
end
tbreak main
commands
silent
python open({str(pid_path)!r}, 'w').write(str(gdb.selected_inferior().pid))
set $probe=(void*)dlopen("{probe_binary}",2)
set quest_gameplay_passive_mobile=(void*)&'(anonymous namespace)::passive_quest_mobile_proc'
call (void)quest_gameplay_read_control()
apply_journey_mode
continue
end
break *do_chaos
commands
silent
call (void)quest_gameplay_setup((char_data*)$rdi)
if quest_gameplay_stage == 1
call (void)quest_gameplay_prepare_mobiles((char_data*)$rdi,(void*)&'(anonymous namespace)::routine_source(char_data*)')
call (void)quest_gameplay_choose_fixture((char_data*)$rdi,(void*)&'(anonymous namespace)::routine_source(char_data*)')
end
apply_journey_mode
continue
end
break *do_quest
set $invalidate_break=$bpnum
commands
silent
if $journey_invalidate
set $journey_invalidate=0
call (void)quest_journey_invalidate((char_data*)$rdi)
end
continue
end
break *world_quest_describe
set $checkpoint_break=$bpnum
commands
silent
call (void)quest_journey_checkpoint((char_data*)$rdi,"{"restart" if restarted else "first"}")
continue
end
break *do_score
set $plan_break=$bpnum
commands
silent
if (int)strncmp((char*)$rsi,"questprobe",10) == 0
if quest_gameplay_stage == 3
call (void)quest_gameplay_setup((char_data*)$rdi)
call (void)quest_world_audit((char_data*)$rdi)
else
call (void)quest_gameplay_plan((char_data*)$rdi,(void*)&'(anonymous namespace)::routine_source(char_data*)',(char*)$rsi)
end
end
continue
end
break *sql_world_quest_finish_async
set $history_break=$bpnum
commands
silent
call (void)quest_gameplay_history((char_data*)$rdi,(obj_data*)$rsi)
continue
end
break world/world_quest_policy.c:{type_line}
set $kind_break=$bpnum
commands
silent
if required_type == 0 && quest_gameplay_kind > 0
set first_type=quest_gameplay_kind
end
continue
end
break *world_quest_policy_select_zone
set $fixture_zone_break=$bpnum
commands
silent
if quest_gameplay_fixture_selected == 0 && quest_gameplay_fixture_zone >= 0
set quest_gameplay_fixture_selected=1
return quest_gameplay_fixture_zone
end
continue
end
break '(anonymous namespace)::quest_target_request::suggest(int, int, int)'
set $fixture_suggest_break=$bpnum
commands
silent
if quest_gameplay_fixture_suggested == 0 && quest_gameplay_fixture_vnum > 0
set quest_gameplay_fixture_suggested=1
return quest_gameplay_fixture_vnum
end
continue
end
run
"""
            gdb_path.write_text(script)
            with output_path.open("w") as output:
                return subprocess.Popen(
                    ["gdb", "--batch", "--return-child-result", "-x", str(gdb_path),
                     "--args", str(binary), "-d", str(run_root), str(plain_port)],
                    cwd=run_root, env=environment, stdout=output, stderr=subprocess.STDOUT,
                    text=True,
                )

        process = launch()
        client = None

        def restart_gameplay(current: MudClient) -> MudClient:
            nonlocal process, client
            current.close()
            client = None
            stop_quest_server(process, pid_path, output_path)
            process = launch(restarted=True)
            wait_for_boot(process, output_path)
            client = reconnect_character(plain_port, expected_room=None)
            client.expect("Pos:", timeout=60)  # Complete async entry, regardless of saved room.
            return client

        try:
            boot_output = wait_for_boot(process, output_path)
            binary_path = binary.resolve()
            running_path = pathlib.Path(os.readlink(f"/proc/{int(pid_path.read_text())}/exe")).resolve()
            require(running_path == binary_path,
                    f"running executable mismatch: expected {binary_path}, got {running_path}")
            client = MudClient(plain_port)
            create_character(client, expected_room=None, hometown="p")
            # The starter kit arrives in inventory; use normal equipment commands
            # before setting the lower accepted level for the gameplay journey.
            client.send("wield mace")
            client.expect("You wield", timeout=30)
            client.send("wear all")
            client.send(f"chaos questroom {BARTENDER_ROOM}")
            client.expect("Quest-room test move complete.", timeout=15)
            client.expect("Quest-room test funds committed.", timeout=60)
            client.send("save")
            client.expect("Save complete for Taverek.", timeout=120)
            client.send("look")
            client.expect("Mathorn's Bar", timeout=15)
            if JOURNEY == "history":
                client, history = perform_history_regrant(client, run_root, restart_gameplay,
                                                           database_environment)
                client.close()
                client = None
                stop_quest_server(process, pid_path, output_path)
                return {"backend": backend, "journey": "history", "history": history,
                        "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest()}
            if JOURNEY == "reported":
                client, reported = perform_reported(client, run_root, restart_gameplay,
                                                     database_environment, plain_port)
                client.close()
                client = None
                stop_quest_server(process, pid_path, output_path)
                return {"backend": backend, "journey": "reported", "reported": reported,
                        "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest()}
            if JOURNEY == "audit":
                audit = perform_world_audit(client, run_root, plain_port)
                client.close()
                client = None
                output = stop_quest_server(process, pid_path, output_path)
                logs = collect_logs(run_root)
                native_slow = [line for line in (output + "\n" + logs).splitlines()
                               if "COMMAND OP SLOW:" in line and
                               ("operation=ask " in line or "operation=quest " in line)]
                return {
                    "backend": backend, "journey": "audit", "audit": audit,
                    "native_slow_quest_commands": native_slow,
                    "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
                    "catalog_ready_count": boot_count,
                }
            if JOURNEY == "gameplay":
                client, gameplay = perform_gameplay(client, run_root, restart_gameplay, database_environment)
                client.close()
                client = None
                stop_quest_server(process, pid_path, output_path)
                return {
                    "backend": backend, "journey": "gameplay", "gameplay": gameplay,
                    "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
                    "catalog_ready_count": boot_count,
                }
            client.send("ask bartender quest")
            first_result, _ = client.expect_any(("Go kill ", "Go ask "), timeout=30)
            transcript_after_first = bytes(client.transcript).decode("utf-8", errors="replace")
            require("unable to help" not in transcript_after_first.lower(),
                    "bartender returned its generic failure after quest command")
            require("Unable to find" not in transcript_after_first,
                    "bartender quest path reported an internal selection failure")
            require("The Great Realm of Duris" not in transcript_after_first,
                    "explicitly denied zone was assigned")

            # Deliberately type the paid abandon and the next paid quest before
            # either response is read.  This is the real-client version of the
            # regression: the second command must remain behind the first
            # wallet debit instead of observing the pre-abandon quest state.
            client.socket.sendall(
                b"ask bartender abandon confirm\nask bartender quest\n"
            )
            client.expect("You no longer have a task.", timeout=30)
            second_result, _ = client.expect_any(("Go kill ", "Go ask "), timeout=30)
            transcript_after_second = bytes(client.transcript).decode("utf-8", errors="replace")
            require("Unable to find" not in transcript_after_second,
                    "repeated bartender quest path reported an internal selection failure")
            require(output_path.read_text(errors="replace").count("World quest catalog ready:") == 1,
                    "catalog was rebuilt during repeated quest/abandon commands")
            client.send("save")
            client.expect("Save complete for Taverek.", timeout=120)
            player_state = None
            if database_environment is not None:
                player_state = verify_mariadb_player_state(database_environment)

            client.send("ask bartender map")
            client.expect("will now show you additional information", timeout=30)
            # This first explicit QUEST closes every eligible target zone in the
            # disposable process, proving both invalidation and a no-candidate wait.
            client.send("quest")
            client.expect("Your task is no longer available.", timeout=30)
            states = read_journey_states(run_root)
            accepted = next(x for x in states if x["label"] == "before-invalidation")
            pending = states[-1]
            preserved = ("origin", "level", "type", "mob", "zone", "started", "receiver",
                         "shares", "kills", "quota", "map_bought", "wallet", "xp")
            require(accepted["map_bought"] == 1, "map purchase did not precede invalidation")
            require(pending["active"] == 0 and pending["replacement_due"] == 1,
                    "world-invalid work did not become a replacement entitlement")
            require(all(pending[k] == accepted[k] for k in preserved),
                    "invalidation changed paid or earned state")
            client.send("ask bartender quest")
            client.expect("Your free replacement and earned progress remain yours.", timeout=30)
            client.send("save")
            client.expect("Save complete for Taverek.", timeout=120)
            if database_environment is not None:
                verify_mariadb_player_state(database_environment, active=0, map_bought=1,
                                            replacement_due=1)
            # Mortals rent at an inn; the bartender's city room cannot camp.
            # Follow authored ordinary exits from Mathorn's Bar to the inn.
            for direction in ("down", "south", "west", "west", "south", "south",
                              "down", "down", "down", "down", "south", "south",
                              "south", "east", "east", "east", "east", "east",
                              "south", "up"):
                client.send(direction)
            client.expect("The Quivering Leaf Inn", timeout=60)
            client.send("rent")
            client.expect("ACCOUNT MENU", timeout=30)
            client.send("0")
            client.close()
            client = reconnect_character(plain_port, expected_room="The Quivering Leaf Inn")
            client.send("quest")
            client.expect("Your task is no longer available.", timeout=30)
            relogged = read_journey_states(run_root)[-1]
            require(all(relogged[k] == pending[k] for k in JOURNEY_FIELDS),
                    "pending entitlement changed on relogin")
            client.send("save")
            client.expect("Save complete for Taverek.", timeout=120)
            client.send("rent")
            client.expect("ACCOUNT MENU", timeout=30)
            client.send("0")
            client.close()
            client = None
            os.kill(int(pid_path.read_text()), signal.SIGTERM)
            process.wait(timeout=30)
            require(process.returncode == 0, "first recovery server did not stop cleanly")
            first_output = output_path.read_text(errors="replace")
            require("Normal termination of game." in first_output, "first shutdown was not normal")
            # Zone closures were an in-memory fixture. A fresh boot restores
            # authored content while retaining the player's durable entitlement.
            process = launch(restarted=True)
            wait_for_boot(process, output_path)
            client = reconnect_character(plain_port, expected_room="The Quivering Leaf Inn")
            client.send("quest")
            client.expect("Your task is no longer available.", timeout=30)
            restarted = read_journey_states(run_root)[-1]
            require(all(restarted[k] == pending[k] for k in JOURNEY_FIELDS),
                    "pending entitlement changed across server restart")
            # Placement/funds are explicit fixture setup, separate from the free
            # replacement wallet comparison immediately afterwards.
            client.send(f"chaos questroom {BARTENDER_ROOM}")
            client.expect("Quest-room test funds committed.", timeout=60)
            client.send("quest")
            client.expect("Your task is no longer available.", timeout=30)
            before_replacement = read_journey_states(run_root)[-1]
            client.send("ask bartender quest")
            client.expect("Here is your free replacement.", timeout=30)
            client.expect_any(("Go kill ", "Go ask "), timeout=30)
            replacement = read_journey_states(run_root)[-1]
            require(replacement["active"] == 1 and replacement["replacement_due"] == 0,
                    "entitlement did not redeem exactly once")
            kept = ("level", "type", "started", "receiver", "shares", "kills", "quota",
                    "map_bought", "wallet", "xp")
            require(all(replacement[k] == before_replacement[k] for k in kept),
                    "free replacement changed wallet, XP or accepted work")
            require(replacement["origin"] == BARTENDER_ROOM and replacement["map_room"] > 0,
                    "replacement lost its current verified origin/entrance")
            client.send("save")
            client.expect("Save complete for Taverek.", timeout=120)
            if database_environment is not None:
                verify_mariadb_player_state(database_environment, map_bought=1)
            if JOURNEY != "recovery":
                client, gameplay = perform_gameplay(client, run_root, restart_gameplay, database_environment)
            else:
                gameplay = []
            client.close()
            client = None
            os.kill(int(pid_path.read_text()), signal.SIGTERM)
            process.wait(timeout=30)
            require(process.returncode == 0, "restarted recovery server did not stop cleanly")
            final_output = output_path.read_text(errors="replace")
            require("Normal termination of game." in final_output, "final shutdown was not normal")
            recovery = {"accepted": accepted, "pending": pending, "relogged": relogged,
                        "restarted": restarted, "before_replacement": before_replacement,
                        "replacement": replacement}
            logs = collect_logs(run_root)
            return {
                "backend": backend,
                "binary_path": str(binary_path),
                "running_executable": str(running_path),
                "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
                "pid": int(pid_path.read_text()),
                "fixture_level": QUEST_LEVEL,
                "quest_first_result": first_result,
                "quest_second_result": second_result,
                "catalog_ready_count": boot_count,
                "player_state": player_state,
                "recovery": recovery,
                "gameplay": gameplay,
                "server_output_tail": final_output[-4000:],
                "log_tail": logs[-8000:],
            }
        except Exception as error:
            output = output_path.read_text(errors="replace")
            logs = collect_logs(run_root)
            checkpoints = read_journey_states(run_root) if (run_root / "quest-journey.tsv").exists() else []
            gameplay_path = run_root / "quest-gameplay.json"
            gameplay_state = gameplay_path.read_text() if gameplay_path.exists() else ""
            completed_path = run_root / "quest-gameplay-results.json"
            completed_cases = completed_path.read_text() if completed_path.exists() else "[]"
            audit_path = run_root / "quest-world-audit.json"
            audit_origins = json.loads(audit_path.read_text())["origins"] if audit_path.exists() else []
            transcript = bytes(client.transcript).decode(errors="replace")[-6000:] if client else ""
            raise AssertionError(
                f"{backend} bartender journey failed: {error}\n"
                f"--- quest checkpoints ---\n{json.dumps(checkpoints)}\n"
                f"--- completed gameplay cases ---\n{completed_cases}\n"
                f"--- loaded-world audit origins ---\n{json.dumps(audit_origins)}\n"
                f"--- gameplay state ---\n{gameplay_state}\n--- client ---\n{transcript}\n"
                f"--- server output ---\n{output[-16000:]}\n"
                f"--- runtime logs ---\n{logs}"
            ) from error
        finally:
            if client is not None:
                client.close()
            if process.poll() is None:
                if pid_path.exists():
                    try:
                        os.kill(int(pid_path.read_text()), signal.SIGTERM)
                    except ProcessLookupError:
                        pass  # The debugger's inferior already exited.
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def verify_mariadb_zone_flag(container: str, root_password: str, database: str) -> dict:
    query = "SELECT COUNT(*), COALESCE(SUM(quest_zone <> 0), 0) FROM zones;"
    result = subprocess.run([
        "docker", "exec", "-e", "MYSQL_PWD=" + root_password, container,
        "mariadb", "-h127.0.0.1", "-uroot", "-N", "-B", database, "-e", query,
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    require(result.returncode == 0, "could not read disposable MariaDB zone flags")
    fields = result.stdout.strip().split()
    require(len(fields) == 2, "unexpected MariaDB zone flag result")
    return {"zone_rows": int(fields[0]), "quest_enabled_rows": int(fields[1])}


def verify_mariadb_player_state(environment: dict[str, str], *, active: int = 1,
                               map_bought: int = 0, replacement_due: int = 0) -> dict[str, int | str]:
    query = (
        "SELECT name, account_name, quest_active, quest_mob_vnum, quest_type, "
        "quest_started, quest_zone_number, quest_giver, quest_level, quest_receiver, "
        "quest_shares_left, quest_kill_how_many, quest_kill_original, quest_map_room, "
        "quest_map_bought, quest_origin_room, quest_replacement_due FROM player_data "
        "WHERE name='Taverek' AND account_name='Journeyacct' LIMIT 1;"
    )
    result = subprocess.run([
        "mysql", "--protocol=tcp", "--ssl=0", "-h", environment["DB_HOST"],
        "-P", environment["DB_PORT"], "-u", environment["DB_USER"], "-N", "-B",
        environment["DB_NAME"], "-e", query,
    ], env={**environment, "MYSQL_PWD": environment["DB_PASSWD"]},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    require(result.returncode == 0,
            "could not read MariaDB player quest state:\n" + result.stderr[-4000:])
    fields = result.stdout.strip().split("\t")
    require(len(fields) == 17, "unexpected MariaDB player quest-state result")
    quest_active = int(fields[2])
    quest_mob_vnum = int(fields[3])
    quest_started = int(fields[5])
    quest_zone_number = int(fields[6])
    quest_giver = int(fields[7])
    quest_level = int(fields[8])
    state: dict[str, int | str] = {
        "name": fields[0],
        "account_name": fields[1],
        "quest_active": quest_active,
        "quest_mob_vnum": quest_mob_vnum,
        "quest_type": int(fields[4]),
        "quest_started": quest_started,
        "quest_zone_number": quest_zone_number,
        "quest_giver": quest_giver,
        "quest_level": quest_level,
        "quest_receiver": int(fields[9]),
        "quest_shares_left": int(fields[10]),
        "quest_kill_how_many": int(fields[11]),
        "quest_kill_original": int(fields[12]),
        "quest_map_room": int(fields[13]),
        "quest_map_bought": int(fields[14]),
        "quest_origin_room": int(fields[15]),
        "quest_replacement_due": int(fields[16]),
    }
    detail = "raw quest fields=" + repr(fields[2:])
    require(quest_active == active, "MariaDB row has wrong active quest state; " + detail)
    require(quest_giver == 16553, "MariaDB player row has the wrong bartender giver; " + detail)
    require(quest_mob_vnum > 0, "MariaDB player row has no quest target; " + detail)
    require(quest_started > 0, "MariaDB player row has no quest start time; " + detail)
    require(quest_level == QUEST_LEVEL, "MariaDB player row has the wrong accepted quest level; " + detail)
    require(int(fields[15]) == BARTENDER_ROOM, "MariaDB row lost the accepted origin; " + detail)
    require(int(fields[16]) == replacement_due, "wrong replacement entitlement; " + detail)
    require((int(fields[13]) > 0) == bool(active), "wrong verified map state; " + detail)
    require(int(fields[14]) == map_bought, "wrong purchased-map entitlement; " + detail)
    require(quest_zone_number not in {0, 292, 536},
            "MariaDB player row persisted an explicitly denied quest zone")
    return state


def run_backend(backend: str, build_root: pathlib.Path) -> dict:
    database_environment = None
    database = None
    container = None
    root_password = None
    state_tmp = tempfile.TemporaryDirectory(prefix=f"world-quest-{backend}-state-")
    state_root = pathlib.Path(state_tmp.name)
    try:
        if backend == "mariadb":
            database = "duris_world_quest_" + uuid.uuid4().hex[:10]
            container, port, root_password, db_password, database_environment = prepare_mariadb(database)
            if container is None or root_password is None or database_environment is None:
                raise AssertionError("MariaDB setup returned incomplete authority")
        binary = build_server(backend, build_root)
        result = perform_quest_journey(binary, backend, state_root, database_environment)
        if backend == "mariadb":
            if container is None or root_password is None or database is None:
                raise AssertionError("MariaDB verification authority is incomplete")
            result["database_zone_flags"] = verify_mariadb_zone_flag(container, root_password, database)
            require(result["database_zone_flags"]["quest_enabled_rows"] == 0,
                    "MariaDB fixture unexpectedly needed quest_zone=1 for successful quest")
        else:
            result["flatfile_state_root_created"] = state_root.is_dir()
        return result
    finally:
        if container:
            subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)
        state_tmp.cleanup()


def main() -> None:
    world = run(["make", "world"], timeout=600)
    require(world.returncode == 0,
            "full-world data generation failed:\n" + world.stdout.decode(errors="replace")[-12000:])
    build_parent = ROOT / "bin" / "tests"
    build_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="world-quest-build-", dir=build_parent) as build_tmp:
        build_root = pathlib.Path(build_tmp)
        backends = ("mariadb", "flatfile") if REQUESTED_BACKEND == "both" else (REQUESTED_BACKEND,)
        results = [run_backend(backend, build_root) for backend in backends]
    print(json.dumps({"status": "passed", "results": results}, indent=2))


if __name__ == "__main__":
    main()
