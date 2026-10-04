#!/usr/bin/env python3
"""World recovery is a switch: off it does nothing, and on it says when it stops working,
comes back by itself and restores what its interval lets a generation age to (persistence
plan phase 8).

A real server on a disposable MariaDB and Redis, with the mini world:
- with the switch off, as the template ships it, a player drops an item and the first
  capture's time passes: nothing is captured, Redis holds no world or floor key, and no
  alert is raised;
- with it on and a capture every five seconds, Redis is stopped once a generation is
  published. The third attempt in a row that leaves no generation raises one alert, naming
  the reason, the last published sequence and its age; the failures after it raise no
  other;
- Redis comes back empty, so the writer's lease is gone with it. The next capture publishes
  and holds the lease again, with no restart;
- the server is killed, and booted when its last generation is older than the maximum age
  it was configured with (60 seconds). That setting is below the interval plus 600, so it
  was raised, and the boot restores the generation;
- with no interval set, captures are 600 seconds apart and a generation is accepted for
  1,200.
Run it through with_disposable_mariadb.sh (make test-db).
"""
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
SECRET = "local-development-only-world-state-hmac-change-before-shared-use"
ACKNOWLEDGED = r"world recovery generation and floor handoff acknowledged sequence=(\d+)"
ALERT = (r"domain=world_recovery action=(\w+) outcome=alert detail=failures=(\d+) "
         r"last_ack_sequence=(\d+) last_ack_age_secs=(-?\d+)")


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def run(binary: Path) -> None:
    sql_host, sql_port = os.environ["TEST_DB_HOST"], os.environ["TEST_DB_PORT"]
    assert sql_host == "127.0.0.1", "use a disposable loopback database"
    database = "world_recovery_" + uuid.uuid4().hex[:12]
    namespace = "duris:local:recovery_" + uuid.uuid4().hex[:8]
    redis_port = free_port()
    env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
               DB_HOST=sql_host, DB_PORT=sql_port, DB_NAME=database,
               DB_USER=os.environ["TEST_DB_USER"], DB_PASSWD=os.environ["TEST_DB_PASSWORD"],
               MYSQL_PWD=os.environ["TEST_DB_PASSWORD"],
               DB_ALLOWED_TARGETS=sql_host + "/" + database,
               PERSISTENCE_MODE="mariadb-primary", DB_TLS="FALSE",
               REDIS="TRUE", REDIS_HOST="127.0.0.1", REDIS_PORT=str(redis_port),
               REDIS_DB="0", REDIS_NAMESPACE=namespace, REDIS_TLS="FALSE",
               REDIS_ALLOWED_TARGETS=f"127.0.0.1:{redis_port}/0",
               REDIS_WORLD_STATE_SECRET=SECRET, REDIS_DONATION_SUBSCRIBER="FALSE",
               CHAOS_MUD="FALSE", LISTEN_ADDRESS="127.0.0.1",
               DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1")
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    mysql = ["mysql", "--protocol=tcp", "-h", sql_host, "-P", sql_port, "-u", env["DB_USER"],
             "-N", "-B"]

    def sql(statement: str, selected: bool = True) -> str:
        return subprocess.check_output(mysql + ([database] if selected else []),
                                       input=statement, text=True, env=env).strip()

    with tempfile.TemporaryDirectory(prefix="world-recovery-") as temporary:
        root = Path(temporary)
        game = root / "game"
        game.mkdir()
        (game / "logs/log").mkdir(parents=True)
        journey.make_fixture(game)
        journey.generate_certificate(game)
        (game / "journals" / "critical").mkdir(parents=True, mode=0o700)
        env["CRITICAL_COMMAND_JOURNAL_DIR"] = str(game / "journals/critical")
        output_path = game / "server.out"
        redis = None
        server = None
        booted = 0.0

        def start_redis() -> subprocess.Popen:
            process = subprocess.Popen(
                ["redis-server", "--bind", "127.0.0.1", "--port", str(redis_port),
                 "--save", "", "--appendonly", "no", "--dir", str(root)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                assert process.poll() is None, "the disposable Redis exited"
                if subprocess.run(["redis-cli", "-h", "127.0.0.1", "-p", str(redis_port),
                                   "PING"], capture_output=True, text=True).stdout.strip() \
                        == "PONG":
                    return process
                time.sleep(.1)
            raise AssertionError("the disposable Redis did not start")

        def redis_cli(*arguments: str) -> str:
            return subprocess.check_output(
                ["redis-cli", "--raw", "-h", "127.0.0.1", "-p", str(redis_port), *arguments],
                text=True).strip()

        def boot(**settings: str):
            nonlocal booted
            for name in ("sys", "file", "status"):
                (game / "logs/log" / name).unlink(missing_ok=True)
            port, tls, websocket = journey.available_ports()
            with output_path.open("w") as output:
                process = subprocess.Popen(
                    [str(binary), "--minimal", "-s", "-d", str(game), str(port)], cwd=game,
                    env=dict(env, DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                             **settings),
                    stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 60
            while "Entering game loop." not in output_path.read_text(errors="replace"):
                assert process.poll() is None and time.monotonic() < deadline, \
                    output_path.read_text(errors="replace")[-2000:]
                time.sleep(.1)
            booted = time.monotonic()
            return process, port

        def stop() -> None:
            server.terminate()
            assert server.wait(timeout=60) == 0, log("sys")[-2000:]

        def log(name: str) -> str:
            path = game / "logs/log" / name
            return path.read_text(errors="replace") if path.exists() else ""

        def wait_for(what: str, seconds: float, found):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                assert server.poll() is None, "the server exited: " + log("sys")[-2000:]
                result = found()
                if result:
                    return result
                time.sleep(.5)
            raise AssertionError(what + "\n" + log("sys")[-2500:] + log("file")[-1500:])

        def acknowledged(after: int = 0):
            return [int(sequence) for sequence in re.findall(ACKNOWLEDGED, log("sys"))
                    if int(sequence) > after]

        sql("CREATE DATABASE " + database, False)
        try:
            sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
            for args in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
                subprocess.run(["python3", "scripts/migration_runner.py", *args], cwd=ROOT,
                               env=env, check=True, capture_output=True)
            redis = start_redis()
            fence = namespace + ":season:1:world_state:writer_fence"
            current = namespace + ":season:1:world_state:current"

            # Off: the first capture would start 30 seconds after the boot.
            server, port = boot(REDIS_WORLD_STATE="FALSE")
            client = journey.MudClient(port)
            journey.create_character(client)
            client.send("drop all")
            client.expect("You drop", timeout=20)
            time.sleep(max(0, 40 - (time.monotonic() - booted)))
            client.close()
            assert "world state enabled" not in log("sys"), log("sys")[-1500:]
            assert "world recovery" not in log("sys"), log("sys")[-1500:]
            assert redis_cli("KEYS", namespace + ":*world_state*") == ""
            assert redis_cli("KEYS", namespace + ":*floor*") == ""
            assert "domain=world_recovery" not in log("file"), log("file")[-1500:]
            stop()
            print("off: a dropped item and the first capture's time left no capture, no "
                  "Redis key and no alert", flush=True)

            on = dict(REDIS_WORLD_STATE="TRUE", REDIS_WORLD_STATE_INTERVAL="5",
                      REDIS_WORLD_STATE_MAX_AGE="60")
            server, _ = boot(**on)
            wait_for("the maximum age did not follow the interval", 10, lambda:
                     "redis world state enabled: interval=5s, max_age=605s" in log("sys"))
            first = wait_for("no generation was published", 60, acknowledged)[-1]
            assert not re.search(ALERT, log("file")), log("file")[-1500:]

            # Redis stops: the third attempt in a row that publishes nothing raises the
            # run's one alert.
            redis.terminate()
            redis.wait(timeout=10)
            stopped = time.monotonic()
            alert = wait_for("three failed captures raised no alert", 60,
                             lambda: re.search(ALERT, log("file")))
            reason, failures, sequence, age = alert.groups()
            assert reason == "publish_failed" and failures == "3", alert.group(0)
            last = acknowledged()[-1]
            assert int(sequence) == last >= first, (alert.group(0), last)
            assert 0 <= int(age) <= time.monotonic() - stopped + 10, alert.group(0)
            time.sleep(12)  # two more attempts fail
            assert len(re.findall(ALERT, log("file"))) == 1, log("file")[-2000:]
            print(f"outage: the third failed capture raised one alert ({alert.group(0)})",
                  flush=True)

            # Redis comes back empty: the writer's lease went with it. The next capture
            # publishes and holds the lease again.
            redis = start_redis()
            assert redis_cli("EXISTS", fence) == "0"
            later = wait_for("no generation was published after the outage", 60,
                             lambda: acknowledged(last))[-1]
            assert int(redis_cli("GET", current)) >= later
            assert len(redis_cli("GET", fence)) == 32
            assert len(re.findall(ALERT, log("file"))) == 1
            print(f"recovery: generation {later} was published with the lease taken again, "
                  "with no restart", flush=True)

            # A crash, and a boot when the last generation is older than the configured
            # maximum age: the age that counts follows the interval, so it is restored.
            server.kill()
            server.wait()
            killed = time.monotonic()
            last = int(redis_cli("GET", current))
            time.sleep(65)
            server, _ = boot(**on)
            wait_for("the generation was not restored", 10, lambda:
                     f"redis: restored world recovery generation sequence={last} "
                     in log("sys") and "Crash recovery complete" in log("status"))
            print(f"crash: generation {last} was restored {time.monotonic() - killed:.0f} s "
                  "after the kill, past the 60 s it was configured with", flush=True)
            stop()

            server, _ = boot(REDIS_WORLD_STATE="TRUE")
            wait_for("the defaults changed", 10, lambda:
                     "redis world state enabled: interval=600s, max_age=1200s" in log("sys"))
            print("defaults: a capture every 600 s, accepted at boot for 1,200", flush=True)
        finally:
            if server and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
            if redis and redis.poll() is None:
                redis.terminate()
                redis.wait(timeout=10)
            sql("DROP DATABASE " + database, False)
    print("world recovery journey passed")


if __name__ == "__main__":
    if not os.getenv("TEST_DB_HOST"):
        print("world recovery journey skipped: run it through with_disposable_mariadb.sh")
    else:
        run(Path(sys.argv[1]).resolve(strict=True))
