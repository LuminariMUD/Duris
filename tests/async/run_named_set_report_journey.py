#!/usr/bin/env python3
"""Full-world reports on disposable MariaDB and live Redis; use its DB wrapper.

Flat-file builds have no SQL season epoch and use the disabled-Redis report path.
"""

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from named_set_gameplay import score, save
from test_flight_network_journey import authority

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Reportwarden", "Reportstaff"
expected_ids = set(map(int, re.findall(
    r"^\s*\{\s*(\d+),\s*\{\s*\{", (ROOT / "src/item/named_sets.c").read_text(), re.M)))
assert len(expected_ids) == 298


def semantic(text):
    text = text.replace("\r\n", "\n")
    # The byte-limited pager can split a row mid-spell. Remove its added
    # prompt/newlines while retaining the report's own row separators.
    text = re.sub(r"\n\n\[Return to continue[^\]]*\]\n\n", "", text)
    text = re.sub(r"&[+-][A-Za-z]|&[nN]", "", text)
    rows = [" ".join(row.split()) for row in re.findall(r"(?m)^\s*#\d+[^\r\n]*", text)]
    ids = [int(re.match(r"#(\d+)", row)[1]) for row in rows]
    assert len(ids) == 298 and set(ids) == expected_ids, (len(ids), expected_ids - set(ids))
    normalized = " ".join(text.split())
    for note in (
        "Guardian Spirits requires a Shaman wearer.",
        "Virtue helps good wearers against non-good targets and evil",
        "wearers against non-evil targets; neutral wearers gain no bonus.",
        "Globe of Darkness excludes Holy Light and Mage Flame.",
    ):
        assert note in normalized, note
    return rows


def run():
    runtime = Path(tempfile.mkdtemp(prefix="named-report-mariadb-", dir=ROOT / "bin/tests"))
    print("Artifacts: " + str(runtime), flush=True)
    (runtime / "areas").symlink_to(Path(os.environ.get("NAMED_SET_RUNTIME", ROOT / "bin/tests/named-set-roster-world")) / "areas", target_is_directory=True)
    (runtime / "docs").symlink_to(ROOT / "docs", target_is_directory=True)
    archive = subprocess.Popen(["git", "archive", "HEAD", "lib", "help"], cwd=ROOT, stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(runtime)], stdin=archive.stdout, check=True)
    archive.stdout.close()
    assert archive.wait() == 0
    for directory in ("logs", "log", "journals/critical"):
        (runtime / directory).mkdir(parents=True, exist_ok=True)
    journey.generate_certificate(runtime)
    plain, tls, websocket = journey.available_ports()
    redis_port = journey.available_ports()[0]
    namespace = "duris:local:named-report"
    clients, transcripts = [], []
    process = output = None
    evidence = {"namespace": namespace, "checks": []}

    def cli(*args):
        return subprocess.check_output(["redis-cli", "--raw", "-p", str(redis_port), *args], text=True).strip()

    def check(label):
        evidence["checks"].append(label)
        (runtime / "evidence.json").write_text(json.dumps(evidence, indent=2))
        print("PASS " + label, flush=True)

    def stop():
        nonlocal process, output
        for client in clients:
            transcripts.append(bytes(client.transcript))
            client.close()
        clients.clear()
        if process and process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=60)
            assert process.returncode == 0, "unclean native shutdown"
        process = None
        if output:
            output.close()
            output = None

    def report(client, label):
        offset = len(client.transcript)
        client.send("namedreport")
        client.expect("Current listing of spells granted by named sets by zone.", timeout=30)
        pages = 0
        for _ in range(60):
            match, _ = client.expect_any(("Return to continue", "Pos:"), timeout=30)
            if match == "Pos:":
                client.expect(">")
                break
            pages += 1
            client.send("")
        else:
            raise AssertionError("namedreport did not finish pagination")
        wire = re.sub(rb"\xff\xfa.*?\xff\xf0", b"", bytes(client.transcript[offset:]), flags=re.S)
        wire = wire.replace(b"\xff\xf9", b"")  # Telnet go-ahead after each page.
        text = wire.decode(errors="replace")
        (runtime / (label + ".txt")).write_text(text)
        evidence[label + "_pages"] = pages
        return semantic(text)

    def generations():
        return (runtime / "logs/log/sys").read_text(errors="replace").count("redis: cached named report")

    with authority("mariadb", runtime) as (env, sql):
        env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                   DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                   MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

        def boot(label, create=False):
            nonlocal process, output
            log = runtime / (label + ".log")
            output = log.open("w")
            process = subprocess.Popen([str(ROOT / "bin/server/dms_new"), "-d", str(runtime), str(plain)],
                                       cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 150
            while "Entering game loop." not in log.read_text(errors="replace"):
                assert process.poll() is None and time.monotonic() < deadline, str(log)
                time.sleep(.1)
            if create:
                client = journey.MudClient(plain)
                clients.append(client)
                journey.create_character(client, expected_room=None, account=ACCOUNT, character=PLAYER,
                                         email="named-report@example.invalid")
            else:
                client = journey.reconnect_character(plain, expected_room=None, account=ACCOUNT, character=PLAYER)
                clients.append(client)
            client.send("")
            client.expect("Pos:", timeout=30)
            client.expect(">")
            client.send("toggle paging no")
            score(client)
            return client

        redis = subprocess.Popen([
            "redis-server", "--bind", "127.0.0.1", "--port", str(redis_port),
            "--save", "", "--appendonly", "no", "--dir", str(runtime),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 10
            while subprocess.run(["redis-cli", "-p", str(redis_port), "PING"], capture_output=True,
                                 text=True).stdout.strip() != "PONG":
                assert redis.poll() is None and time.monotonic() < deadline
                time.sleep(.1)
            actor = boot("create", create=True)
            save(actor, PLAYER)
            stop()
            sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{PLAYER}'")
            env.update(REDIS="TRUE", REDIS_HOST="127.0.0.1", REDIS_PORT=str(redis_port),
                       REDIS_DB="0", REDIS_NAMESPACE=namespace, REDIS_TLS="FALSE",
                       REDIS_ALLOWED_TARGETS=f"127.0.0.1:{redis_port}/0",
                       REDIS_WORLD_STATE="FALSE", REDIS_DONATION_SUBSCRIBER="FALSE")
            actor = boot("live-boot")
            key, = cli("--scan", "--pattern", namespace + ":season:*:cache:named").splitlines()
            evidence["key"] = key
            boot_rows = semantic(cli("GET", key))
            ttl = int(cli("TTL", key))
            assert 86000 < ttl <= 86400, ttl
            evidence["boot_ttl"] = ttl
            before = generations()
            assert report(actor, "warm") == boot_rows
            assert report(actor, "warm-repeat") == boot_rows and generations() == before
            check("boot warms all 298 native rows with one-day TTL; repeated warm reads do not regenerate")

            actor.send("redis clear named")
            actor.expect("Queued: named", timeout=30)
            score(actor)
            deadline = time.monotonic() + 10
            while cli("EXISTS", key) != "0":
                assert time.monotonic() < deadline, "staff invalidation was not published"
                time.sleep(.1)
            assert report(actor, "cold-after-staff-clear") == boot_rows
            assert generations() == before + 1 and semantic(cli("GET", key)) == boot_rows
            check("native staff clear invalidates local/Redis copies; a cold read regenerates the identical catalog")
            save(actor, PLAYER)
            stop()
            cli("SET", key, "STALE OLD ROSTER", "EX", "86400")
            actor = boot("stale-boot")
            assert "STALE" not in cli("GET", key) and semantic(cli("GET", key)) == boot_rows
            assert report(actor, "after-stale-boot") == boot_rows
            check("normal reboot replaces a stale one-day report before player reads")

            redis.terminate()
            redis.wait(timeout=5)
            actor.send("redis clear named")
            actor.expect("Queued: named", timeout=30)
            score(actor)
            assert report(actor, "redis-unavailable") == boot_rows
            check("report remains complete and identical after Redis loss and local invalidation")
            save(actor, PLAYER)
            stop()
            env["REDIS"] = "FALSE"
            actor = boot("disabled-boot")
            actor.send("toggle paging yes")
            score(actor)
            assert report(actor, "redis-disabled-paged") == boot_rows
            assert evidence["redis-disabled-paged_pages"] > 1
            check("Redis-disabled native fallback paginates all 298 rows in the same order with conditional notes")
            save(actor, PLAYER)
        finally:
            stop()
            if redis.poll() is None:
                redis.terminate()
                redis.wait(timeout=5)
            (runtime / "transcript.txt").write_bytes(b"\n\n".join(transcripts))
            (runtime / "evidence.json").write_text(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    run()
