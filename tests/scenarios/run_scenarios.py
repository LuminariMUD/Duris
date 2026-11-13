#!/usr/bin/env python3
"""Run plain-text gameplay scenarios against the real server on disposable MariaDB.

    tests/async/with_disposable_mariadb.sh \
        python3 tests/scenarios/run_scenarios.py --server bin/server/dms_new FILE.scn...

Usually started through scripts/mudtest. Each scenario gets its own schema, its own
copy of the minimal world and a freshly booted server. After every scenario the
server must shut down cleanly and its logs must hold no crash or sanitizer report.

Scenario lines (see tests/scenarios/README.md):

    actor Name [class=MONK] [spec=WAYOFSNAKE] [level=40] [skill=SKILL_BASH:100]...
    staff Name                 a level-62 actor for load/restore/tranquilize
    Name> command              send a command and wait until it has finished
    Name? REGEX                REGEX matches what reached Name since Name's last check
    Name! REGEX                REGEX does NOT match it
    until Name /REGEX/ [max K] command
                               send command again until its output matches (K tries, 20 by default)
    restart                    save everyone, stop, boot again and log everyone back in
"""

from __future__ import annotations

import argparse
import pathlib
import random
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/async"))

import test_mariadb_combat_journey as journey  # noqa: E402
from test_flight_network_journey import command  # noqa: E402

DEFINES = "\n".join((ROOT / path).read_text(errors="replace")
                    for path in ("src/core/defines.h", "src/core/structs.h", "src/magic/spells.h"))
# Text that means the server or a sanitizer reported a defect.
CRASH_MARKERS = ("AddressSanitizer", "UndefinedBehaviorSanitizer", "runtime error:",
                 "LeakSanitizer", "Segmentation fault", "SIGSEGV", "SIGABRT", "core dumped",
                 "panic_corruption", "Assertion `")


class ScenarioError(Exception):
    pass


def define(name: str) -> int:
    match = re.search(rf"^#define {re.escape(name)}\s+(BIT_)?(\d+)\b", DEFINES, re.M)
    if not match:
        raise ScenarioError(f"unknown name {name}")
    return 1 << (int(match[2]) - 1) if match[1] else int(match[2])


@dataclass
class Actor:
    name: str
    classes: int = 0
    spec: int = 0
    level: int = 1
    skills: list[tuple[int, int]] = field(default_factory=list)
    client: object = None
    checked: int = 0

    @property
    def account(self) -> str:
        # Account names follow character-name rules, which the actor name already meets.
        # A prefix would have to drop a letter, and two actors could then share an account.
        return self.name.lower()


def parse(path: pathlib.Path) -> tuple[dict[str, Actor], list[tuple[int, str, str, str]]]:
    actors: dict[str, Actor] = {}
    steps = []
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.split(" #", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if not line:
            continue
        where = f"{path.name}:{number}"
        words = line.split()
        if words[0] in ("actor", "staff"):
            if steps:
                raise ScenarioError(f"{where}: declare actors before the first step")
            name = words[1]
            if not re.fullmatch(r"[A-Z][a-z]{2,11}", name):
                raise ScenarioError(f"{where}: actor names are one capitalised word of 3-12 letters")
            actor = Actor(name, level=62 if words[0] == "staff" else 1)
            for option in words[2:]:
                key, _, value = option.partition("=")
                if key == "class":
                    actor.classes = define("CLASS_" + value.upper())
                elif key == "spec":
                    actor.spec = int(value) if value.isdigit() else define("SPEC_" + value.upper())
                elif key == "level":
                    actor.level = int(value)
                elif key == "skill":
                    skill, _, learned = value.partition(":")
                    actor.skills.append((define(skill.upper()), int(learned or 100)))
                else:
                    raise ScenarioError(f"{where}: unknown actor option {key}")
            actors[name] = actor
            continue
        if line == "restart":
            steps.append((number, "restart", "", ""))
            continue
        if words[0] == "until":
            match = re.fullmatch(r"until ([A-Z][a-z]+) /((?:[^/\\]|\\.)+)/(?: max (\d+))? (.+)", line)
            if not match or match[1] not in actors:
                raise ScenarioError(f"{where}: expected 'until Name /REGEX/ [max K] command'")
            steps.append((number, "until", match[1], (re.compile(match[2].replace("\\/", "/"), re.M),
                                                       int(match[3] or 20), match[4])))
            continue
        match = re.fullmatch(r"([A-Z][a-z]+)([>?!])\s?(.*)", line)
        if not match or match[1] not in actors:
            raise ScenarioError(f"{where}: expected 'Name> command', 'Name? text', 'Name! text' or 'restart'")
        steps.append((number, match[2], match[1], re.compile(match[3], re.M) if match[2] != ">" else match[3]))
    if not actors:
        raise ScenarioError(f"{path.name}: no actors")
    return actors, steps


def seed(sql, actors: dict[str, Actor]) -> None:
    stats = ",".join(f"base_{stat}=100" for stat in ("str", "dex", "agi", "con", "pow", "int", "wis", "luk"))
    for actor in actors.values():
        pid = sql(f"SELECT pid FROM player_data WHERE name='{actor.name}'")
        statements = [f"UPDATE player_data SET level={actor.level},highest_level={actor.level},{stats}"
                      + (f",m_class={actor.classes}" if actor.classes else "")
                      + (f",spec={actor.spec}" if actor.spec else "")
                      + f" WHERE pid={pid}"]
        statements += [f"REPLACE INTO player_skills(pid,skill_id,learned,taught) VALUES({pid},{skill},{learned},{learned})"
                       for skill, learned in actor.skills]
        sql(";".join(statements))


def unchecked(actor: Actor) -> str:
    """What reached the actor since its last check. Offsets count bytes, so slice before decoding."""
    return bytes(actor.client.transcript[actor.checked:]).decode(errors="replace")


def run_scenario(binary: pathlib.Path, path: pathlib.Path, rng_seed: int) -> None:
    actors, steps = parse(path)
    with tempfile.TemporaryDirectory(prefix="scenario-", dir=ROOT / "bin/tests") as temporary, \
            journey.mariadb_authority() as (authority, sql):
        runtime = pathlib.Path(temporary)
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True, exist_ok=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        (runtime / "journals/players").mkdir(mode=0o700)
        plain, tls, websocket = journey.available_ports()
        # A server that supports it fixes its rolls from this seed, so a failure replays.
        environment = dict(authority, CRITICAL_COMMAND_JOURNAL_DIR=str(critical),
                           DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket),
                           DURIS_TEST_RNG_SEED=str(rng_seed))
        output_path = runtime / "server.out"
        process = None

        def boot() -> None:
            nonlocal process
            offset = output_path.stat().st_size if output_path.exists() else 0
            output = output_path.open("a")
            process = subprocess.Popen([str(binary), "--minimal", "-s", "-d", str(runtime), str(plain)],
                                       cwd=runtime, env=environment, stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 120
            while "Entering game loop." not in output_path.read_text(errors="replace")[offset:]:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise ScenarioError("server did not boot:\n" + output_path.read_text(errors="replace")[-3000:])
                time.sleep(.1)

        def stop() -> None:
            nonlocal process
            for actor in actors.values():
                if actor.client is not None:
                    actor.client.close()
                    actor.client = None
            if process is None:
                return
            server, process = process, None  # report each server's exit once
            if server.poll() is None:
                server.send_signal(signal.SIGTERM)
                try:
                    server.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    # Never release the schema or runtime directory under a live server.
                    server.kill()
                    server.wait()
                    raise ScenarioError("server ignored SIGTERM for 60s and was killed")
            # Also catches a server that died on its own before this point.
            if server.returncode != 0:
                raise ScenarioError(f"server exited {server.returncode}")

        def login(actor: Actor) -> None:
            actor.client = journey.reconnect_character(plain, expected_room=None,
                                                       account=actor.account, character=actor.name)
            actor.client.expect_any(("Pos: standing >", "<>"), timeout=30)
            command(actor.client, "toggle paging no")
            actor.checked = len(actor.client.transcript)

        def save_all() -> None:
            for actor in actors.values():
                actor.client.send("save")
                actor.client.expect("Saving " + actor.name + ".", timeout=30)

        try:
            boot()
            for actor in actors.values():
                client = journey.MudClient(plain)
                journey.create_character(client, expected_room=None, account=actor.account,
                                         character=actor.name,
                                         email=actor.name.lower() + "@example.invalid")
                client.send("save")
                client.expect("Saving " + actor.name + ".", timeout=30)
                client.close()
            stop()
            seed(sql, actors)
            boot()
            for actor in actors.values():
                login(actor)

            for number, kind, name, text in steps:
                where = f"{path.name}:{number}"
                if kind == "restart":
                    save_all()
                    stop()
                    boot()
                    for actor in actors.values():
                        login(actor)
                    continue
                actor = actors[name]
                if kind == ">":
                    command(actor.client, text)
                    continue
                if kind == "until":
                    pattern, tries, line = text
                    for _ in range(tries):
                        actor.checked = len(actor.client.transcript)
                        command(actor.client, line)
                        if pattern.search(unchecked(actor)):
                            break
                    else:
                        raise ScenarioError(f"{where}: {line!r} never produced /{pattern.pattern}/ "
                                            f"in {tries} tries. Last output:\n" + unchecked(actor)[-1500:])
                    continue  # the matching attempt is what the next checks read
                elif kind == "?":
                    deadline = time.monotonic() + 15
                    while not text.search(unchecked(actor)):
                        if time.monotonic() > deadline:
                            raise ScenarioError(f"{where}: {name} never saw /{text.pattern}/. Last output:\n"
                                                + unchecked(actor)[-1500:])
                        actor.client._receive()
                else:
                    command(actor.client, "score")  # drain anything still in flight
                    seen = unchecked(actor)
                    if found := text.search(seen):
                        raise ScenarioError(f"{where}: {name} saw /{text.pattern}/, which must not appear:\n"
                                            + seen[max(0, found.start() - 700):found.start() + 300])
                actor.checked = len(actor.client.transcript)
            save_all()
        finally:
            try:
                stop()
            finally:
                logs = output_path.read_text(errors="replace") if output_path.exists() else ""
                logs += journey.runtime_logs(runtime)
                found = [marker for marker in CRASH_MARKERS if marker in logs]
                if found:
                    raise ScenarioError(f"server logs report {', '.join(found)}:\n" + logs[-3000:])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--server", type=pathlib.Path, required=True)
    parser.add_argument("--seed", type=int, help="replay a run: the seed a result line printed")
    parser.add_argument("scenarios", type=pathlib.Path, nargs="+")
    args = parser.parse_args()
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    failed = 0
    for path in args.scenarios:
        started = time.monotonic()
        rng_seed = args.seed or random.randrange(1, 2**63)
        try:
            run_scenario(args.server.resolve(), path, rng_seed)
            print(f"PASS {path} ({time.monotonic() - started:.0f}s, seed {rng_seed})", flush=True)
        except Exception as error:  # report every scenario, then fail the run
            failed += 1
            print(f"FAIL {path} ({time.monotonic() - started:.0f}s, seed {rng_seed})\n{error}\n"
                  f"replay: scripts/mudtest scenario --seed {rng_seed} {path}", flush=True)
    print(f"{len(args.scenarios) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
