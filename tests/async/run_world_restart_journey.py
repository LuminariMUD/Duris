#!/usr/bin/env python3
"""What a restart leaves with world recovery on (the review of MR !10).

A real server on a disposable MariaDB and Redis, the mini world with a zone-loaded banana on
the arena floor, and the shipped settings (REDIS_WORLD_STATE=TRUE and nothing else). One
scenario a run:

crash     the lease is renewed while the server runs. A boot after a crash consumes the
          generation it restored, with the crashed writer's lease still running, and
          publishes its own within two minutes. A second crash restores that one: the
          banana a player took after the first is not back on the floor.
copyover  the image a copyover starts holds the lease at once and publishes a generation; a
          crash after it restores that generation, not the one from before the copyover.
restart   a clean stop takes one last capture, with the players gone, and the next boot
          restores it: the banana a player took after the periodic capture is not back on
          the floor.
taken     a player takes the banana after the capture and saves, and the server crashes.
          The boot leaves the banana's tree out of what it restores; nobody else can take a
          second one, and one character's save holds the uid. A mace the player took, saved
          and dropped again before the capture is restored: its ownership record still
          named the character, whose save no longer held it, and the boot reaped it (#11)
          with the records of the starter kit the character dropped (transient items
          dissolve when dropped); the login after the boot counts no such record, and the
          saves wrote no unowned_object line, both without DURIS_PERSISTENCE_TRACE.
handover  a character takes the banana after the capture and a checkpoint saves it, gives it
          to a second one, who saves, drops it and saves again; the server crashes before
          the giver's next checkpoint. The boot keeps the banana's record, which names the
          second character, since the giver's save still holds the banana: the record is
          what makes that older copy load as stale. The floor copy is restored, the giver
          loads without it, and only one character holds it after both save (the review of
          MR !13).
midcapture  a banana is taken out of a basket on the floor and dropped while a capture of
          12,000 more objects runs. The capture meets it twice and the drop is journaled as
          well; the generation holds it once, in the basket, and the boot restores it.
slowread  Redis answers every other read of the current sequence in 300 ms, past the 100 ms
          the game loop's connection allows, as on a busy host. The boot asks again each
          time, and restores and consumes the generation.

Run it through with_disposable_mariadb.sh (make test-db).
"""
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import test_flatfile_combat_journey as journey

ROOT = Path(__file__).resolve().parents[2]
SECRET = "local-development-only-world-state-hmac-change-before-shared-use"
ACKNOWLEDGED = r"world recovery generation and floor handoff acknowledged sequence=(\d+)"
BANANA = "O 0 15 1 22800 100 0 0 0 * a banana on the floor"
MACE = "O 0 677 1 22800 100 0 0 0 * a mace on the floor"
# A capture walks the objects newest first: the basket is the newest, the banana the oldest,
# and the maces in another room keep the capture busy between them.
BUSY = [BANANA] + ["O 0 677 99999 10 100 0 0 0"] * 12000 + ["O 0 387 1 22800 100 0 0 0"]


class SlowReads(threading.Thread):
    """A proxy before Redis that, while `slow`, holds back every other read of the current
    sequence for 300 ms."""

    def __init__(self, redis_port: int) -> None:
        super().__init__(daemon=True)
        self.redis_port = redis_port
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.slow = False
        self.reads = 0
        self.start()

    def run(self) -> None:
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            redis = socket.create_connection(("127.0.0.1", self.redis_port))
            threading.Thread(target=self.pipe, args=(client, redis, True), daemon=True).start()
            threading.Thread(target=self.pipe, args=(redis, client, False), daemon=True).start()

    def pipe(self, source: socket.socket, sink: socket.socket, requests: bool) -> None:
        try:
            while data := source.recv(65536):
                if requests and b"GET\r\n" in data and b"world_state:current\r\n" in data:
                    self.reads += 1
                    if self.slow and self.reads % 2:
                        time.sleep(.3)
                sink.sendall(data)
        except OSError:
            pass
        finally:
            source.close()
            sink.close()


class Rig:
    """One server directory, one database and one Redis."""

    def __init__(self, binary: Path, zone_lines: list[str], mobs: bool = True,
                 proxy: bool = False) -> None:
        host, port = os.environ["TEST_DB_HOST"], os.environ["TEST_DB_PORT"]
        assert host == "127.0.0.1", "use a disposable loopback database"
        self.database = "world_restart_" + uuid.uuid4().hex[:12]
        self.namespace = "duris:local:restart_" + uuid.uuid4().hex[:8]
        self.temporary = tempfile.TemporaryDirectory(prefix="world-restart-")
        self.root = Path(self.temporary.name)
        # Redis takes a port below the kernel's ephemeral range and binds it at once. A
        # port probed in that range and bound after the database setup was handed out
        # again in between, to another journey's listener or an outgoing connection.
        self.redis_port = journey.available_ports()[0]
        self.redis = subprocess.Popen(
            ["redis-server", "--bind", "127.0.0.1", "--port", str(self.redis_port),
             "--save", "", "--appendonly", "no", "--dir", str(self.root)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 10
        while subprocess.run(["redis-cli", "-p", str(self.redis_port), "PING"],
                             capture_output=True, text=True).stdout.strip() != "PONG":
            assert time.monotonic() < deadline, "the disposable Redis did not start"
            time.sleep(.1)
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "logs/log").mkdir(parents=True)
        journey.make_fixture(self.game)
        journey.generate_certificate(self.game)
        (self.game / "journals/critical").mkdir(parents=True, mode=0o700)
        # A copyover execs bin/server/dms below the directory the server runs in.
        (self.game / "bin/server").mkdir(parents=True)
        shutil.copy2(binary, self.game / "bin/server/dms")
        (self.root / "copyover-state").mkdir()
        zone = self.game / "areas_mini/mini.zon"
        kept = zone.read_text().split("\n")
        if not mobs:  # the fixture's mobs pick up what lies in their room
            kept = [line for line in kept
                    if "deterministic" not in line and "corpse-loot marker" not in line]
        zone.write_text("\n".join(kept).replace("\nS\n", "\n" + "\n".join(zone_lines) + "\nS\n"))
        self.port, tls, websocket = journey.available_ports()
        # With a proxy the server reaches Redis through it; the journey reads Redis directly.
        self.proxy = SlowReads(self.redis_port) if proxy else None
        server_port = self.proxy.port if proxy else self.redis_port
        self.env = dict(
            PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
            DB_HOST=host, DB_PORT=port, DB_NAME=self.database,
            DB_USER=os.environ["TEST_DB_USER"], DB_PASSWD=os.environ["TEST_DB_PASSWORD"],
            MYSQL_PWD=os.environ["TEST_DB_PASSWORD"],
            DB_ALLOWED_TARGETS=host + "/" + self.database,
            PERSISTENCE_MODE="mariadb-primary", DB_TLS="FALSE",
            REDIS="TRUE", REDIS_HOST="127.0.0.1", REDIS_PORT=str(server_port),
            REDIS_DB="0", REDIS_NAMESPACE=self.namespace, REDIS_TLS="FALSE",
            REDIS_ALLOWED_TARGETS=f"127.0.0.1:{server_port}/0",
            REDIS_WORLD_STATE="TRUE", REDIS_WORLD_STATE_SECRET=SECRET,
            REDIS_DONATION_SUBSCRIBER="FALSE", CHAOS_MUD="FALSE", LISTEN_ADDRESS="127.0.0.1",
            DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1", DURIS_TLS_PORT=str(tls),
            DURIS_WEBSOCKET_PORT=str(websocket),
            CRITICAL_COMMAND_JOURNAL_DIR=str(self.game / "journals/critical"),
            COPYOVER_STATE_FILE=str(self.root / "copyover-state/copyover.dat"))
        if "LD_LIBRARY_PATH" in os.environ:
            self.env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        self.mysql = ["mysql", "--protocol=tcp", "-h", host, "-P", port, "-u",
                      self.env["DB_USER"], "-N", "-B"]
        self.output = self.game / "server.out"
        self.output.write_text("")
        self.server = None
        self.booted = 0.0
        self.marks = {}
        self.sql("CREATE DATABASE " + self.database, False)
        self.sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        for args in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
            subprocess.run(["python3", "scripts/migration_runner.py", *args], cwd=ROOT,
                           env=self.env, check=True, capture_output=True)

    def sql(self, statement: str, selected: bool = True) -> str:
        return subprocess.check_output(self.mysql + ([self.database] if selected else []),
                                       input=statement, text=True, env=self.env).strip()

    def redis_cli(self, *arguments: str) -> str:
        return subprocess.check_output(
            ["redis-cli", "--raw", "-p", str(self.redis_port), *arguments],
            text=True, errors="replace").strip()

    def key(self, suffix: str) -> str:
        return f"{self.namespace}:season:1:world_state:{suffix}"

    def log(self, name: str) -> str:
        """What this boot has logged."""
        path = self.game / "logs/log" / name
        text = path.read_text(errors="replace") if path.exists() else ""
        return text[self.marks.get(name, 0):]

    def boot(self) -> None:
        self.marks = {}
        self.marks = {name: len(self.log(name)) for name in ("sys", "status", "debug")}
        loops = self.output.read_text(errors="replace").count("Entering game loop.")
        with self.output.open("a") as output:
            self.server = subprocess.Popen(
                [str(self.game / "bin/server/dms"), "--minimal", "-s", str(self.port)],
                cwd=self.game, env=self.env, stdout=output, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 90
        while self.output.read_text(errors="replace").count("Entering game loop.") == loops:
            assert self.server.poll() is None and time.monotonic() < deadline, \
                self.output.read_text(errors="replace")[-3000:]
            time.sleep(.1)
        self.booted = time.monotonic()

    def kill(self) -> None:
        self.server.kill()
        self.server.wait()

    def stop(self) -> None:
        self.server.terminate()
        assert self.server.wait(timeout=90) == 0, self.log("sys")[-2000:]

    def wait_for(self, what: str, seconds: float, found):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            assert self.server.poll() is None, "the server exited:\n" + self.log("sys")[-2000:]
            result = found()
            if result:
                return result
            time.sleep(.1)
        raise AssertionError("\n".join([what] + [self.log(name)[-2000:]
                                                for name in ("sys", "status", "debug")]))

    def generation(self, seconds: float = 60) -> int:
        """The first generation this boot publishes."""
        return int(self.wait_for("no generation was published", seconds, lambda: re.search(
            ACKNOWLEDGED, self.log("sys"))).group(1))

    def restored(self, sequence: int, kind: str = "Crash") -> None:
        """The boot restored the generation and then consumed it."""
        self.wait_for(f"generation {sequence} was not restored and consumed", 15, lambda:
                      f"restored world recovery generation sequence={sequence} "
                      in self.log("sys") and f"{kind} recovery complete" in self.log("status")
                      and self.redis_cli("EXISTS", self.key("current")) == "0")

    def close(self) -> None:
        if self.server and self.server.poll() is None:
            self.server.kill()
            self.server.wait()
        if self.proxy:
            self.proxy.listener.close()
        if self.redis:
            self.redis.terminate()
            self.redis.wait(timeout=10)
        self.sql("DROP DATABASE IF EXISTS " + self.database, False)
        self.temporary.cleanup()


def screen(client: journey.MudClient, command: str, wait: float = 1.5) -> str:
    client.pending.clear()
    client.send(command)
    time.sleep(wait)
    while client._receive():
        pass
    return bytes(client.pending).decode(errors="replace")


def enter(rig: Rig) -> journey.MudClient:
    """A new character in the arena, carrying nothing."""
    client = journey.MudClient(rig.port)
    journey.create_character(client)
    client.send("drop all")
    client.expect("You drop a steel long sword.", timeout=20)
    return client


def save(client: journey.MudClient) -> None:
    client.send("save")
    client.expect("Save", timeout=20)
    time.sleep(2)


def take_banana(client: journey.MudClient) -> None:
    assert "You get a banana" in screen(client, "get banana")
    save(client)


def bananas(rig: Rig) -> tuple[bool, int]:
    """Whether the arena floor has a banana, and how many the character carries."""
    client = journey.reconnect_character(rig.port, expected_room=None)
    try:
        return ("banana lies here" in screen(client, "look"),
                screen(client, "inventory").count("banana"))
    finally:
        client.close()


def crash(rig: Rig) -> None:
    rig.boot()
    assert "redis world state enabled: interval=600s, max_age=1200s" in rig.log("sys")
    # The boot's claim is 60 seconds long and the first capture is 30 seconds away: only a
    # renewal leaves the lease more than 40 seconds at this point.
    time.sleep(max(0, 27 - (time.monotonic() - rig.booted)))
    left = int(rig.redis_cli("PTTL", rig.key("writer_fence")))
    assert 40000 < left <= 60000, left
    first = rig.generation()
    holder = rig.redis_cli("GET", rig.key("writer_fence"))
    rig.kill()

    rig.boot()
    rig.restored(first)
    assert rig.redis_cli("GET", rig.key("writer_fence")) == holder, "the lease did not run on"
    client = enter(rig)
    assert "banana lies here" in screen(client, "look")
    take_banana(client)
    client.close()
    second = rig.generation(150)
    assert second > first and rig.redis_cli("GET", rig.key("writer_fence")) != holder
    waited = time.monotonic() - rig.booted
    rig.kill()

    rig.boot()
    rig.restored(second)
    assert bananas(rig) == (False, 1), "the first crash's generation was restored again"
    print(f"crash: the lease had {left / 1000:.0f} s left 27 s after the boot; the boot "
          f"after a crash consumed generation {first} and published generation {second} "
          f"{waited:.0f} s later; a second crash restored that one", flush=True)


def copyover(rig: Rig) -> None:
    rig.boot()
    client = enter(rig)
    first = rig.generation()
    holder = rig.redis_cli("GET", rig.key("writer_fence"))
    rig.marks["sys"] += len(rig.log("sys"))
    rig.server.send_signal(signal.SIGUSR1)
    client.expect("Copyover complete!", timeout=90)
    copied = time.monotonic()
    taken = rig.redis_cli("GET", rig.key("writer_fence"))
    assert len(taken) == 32 and taken != holder, "the new image does not hold the lease"
    take_banana(client)
    client.close()
    second = rig.generation()
    assert second > first
    waited = time.monotonic() - copied
    rig.kill()

    rig.boot()
    rig.restored(second)
    assert bananas(rig) == (False, 1), "the generation from before the copyover was restored"
    print(f"copyover: the new image held the lease at once and published generation "
          f"{second} {waited:.0f} s later; a crash after it restored that one", flush=True)


def restart(rig: Rig) -> None:
    rig.boot()
    client = enter(rig)
    first = rig.generation()
    take_banana(client)
    client.send("quit")
    client.expect("ACCOUNT MENU", timeout=40)
    client.close()
    rig.stop()
    last = int(re.findall(ACKNOWLEDGED, rig.log("sys"))[-1])
    assert last > first, "the shutdown took no capture"
    assert rig.redis_cli("EXISTS", rig.key("writer_fence")) == "0", "the lease was kept"

    rig.boot()
    rig.restored(last, "Clean restart")
    assert bananas(rig) == (False, 1), "the periodic capture's floor was restored"
    print(f"restart: the clean stop published generation {last} with the players gone, and "
          "the boot restored it", flush=True)


def taken(rig: Rig) -> None:
    rig.boot()
    client = enter(rig)
    assert "You get a small wooden mace" in screen(client, "get mace")
    save(client)
    client.send("drop mace")
    client.expect("You drop a small wooden mace", timeout=10)
    save(client)
    assert time.monotonic() - rig.booted < 27, "the character entered too late"
    assert rig.sql("SELECT owner_type, state FROM item_current_owner WHERE vnum=677") \
        == "1\t1" and rig.sql("SELECT COUNT(*) FROM player_items WHERE vnum=677") == "0"
    assert "outcome=unowned_object" not in rig.log("debug"), rig.log("debug")[-1500:]
    first = rig.generation()
    take_banana(client)
    client.close()
    rig.kill()

    rig.boot()
    assert rig.sql("SELECT COUNT(*) FROM item_current_owner WHERE vnum=677 AND owner_type=1") \
        == "0", "the boot did not reap the dropped mace's record"
    assert rig.sql("SELECT COUNT(*) FROM item_current_owner own WHERE own.owner_type=1 AND "
                   "own.state=1 AND NOT EXISTS (SELECT 1 FROM player_items held WHERE "
                   "held.obj_uid=own.item_uid AND held.pid=own.owner_id)") == "0", \
        "a player's record with no payload row survived the boot"
    reaped = re.search(r"Item ownership reap: records of items no player holds deleted=(\d+)",
                       rig.log("status"))
    assert reaped and int(reaped.group(1)) > 1, rig.log("status")[:1500]
    rig.restored(first)
    assert "left out 1 object trees that have an owner" in rig.log("sys"), \
        rig.log("sys")[-1500:]
    client = journey.reconnect_character(rig.port, expected_room=None)
    floor, carried = screen(client, "look"), screen(client, "inventory")
    client.close()
    assert "outcome=missing_payload_rows" not in rig.log("debug"), rig.log("debug")[-1500:]
    assert "banana lies here" not in floor and carried.count("banana") == 1, \
        "the banana a character holds is back on the floor"
    assert "small mace, lies here" in floor, "the mace a character dropped is gone"
    other = journey.MudClient(rig.port)
    journey.create_character(other, account="Otheracct", character="Brannoc",
                             email="other@example.invalid")
    assert "You get a banana" not in screen(other, "get banana")
    other.close()
    assert rig.sql("SELECT COUNT(*), COUNT(DISTINCT pid) FROM player_items WHERE vnum=15") \
        == "1\t1"
    print(f"taken: the boot restored generation {first} with the mace a character had "
          "dropped and without the banana it took and saved after the capture", flush=True)


def handover(rig: Rig) -> None:
    rig.boot()
    taverek = enter(rig)
    brannoc = journey.MudClient(rig.port)
    journey.create_character(brannoc, account="Otheracct", character="Brannoc",
                             email="other@example.invalid")
    brannoc.send("drop all")
    brannoc.expect("You drop a steel long sword.", timeout=20)
    first = rig.generation()
    assert "You get a banana" in screen(taverek, "get banana")
    # The next player checkpoint saves Taverek with the banana; the one after it is 30
    # seconds of game time away, far beyond the hand-over.
    giver = rig.sql("SELECT pid FROM player_data WHERE name='Taverek'")
    rig.wait_for("no checkpoint saved Taverek with the banana", 45, lambda: rig.sql(
        f"SELECT COUNT(*) FROM player_items WHERE vnum=15 AND pid={giver}") == "1")
    taverek.send("give banana brannoc")
    brannoc.expect("gives you a banana", timeout=10)
    save(brannoc)
    brannoc.send("drop banana")
    brannoc.expect("You drop a banana", timeout=10)
    save(brannoc)
    taker = rig.sql("SELECT pid FROM player_data WHERE name='Brannoc'")
    assert rig.sql("SELECT owner_type, owner_id FROM item_current_owner WHERE vnum=15") \
        == f"1\t{taker}" and rig.sql("SELECT pid FROM player_items WHERE vnum=15") == giver, \
        "a checkpoint saved Taverek after the hand-over"
    uid = rig.sql("SELECT item_uid FROM item_current_owner WHERE vnum=15")
    rig.kill()
    taverek.close()
    brannoc.close()

    rig.boot()
    assert rig.sql("SELECT owner_type, owner_id FROM item_current_owner WHERE vnum=15") \
        == f"1\t{taker}", "the boot reaped the record that keeps Taverek's copy out"
    rig.restored(first)
    taverek = journey.reconnect_character(rig.port, expected_room=None)
    floor, carried = screen(taverek, "look"), screen(taverek, "inventory")
    assert "banana lies here" in floor and "banana" not in carried, floor + carried
    assert f"load_skipped uid={uid} vnum=15 lost_by=player:{giver}:0 held_by=player:{taker}:0" \
        in (rig.game / "logs/log/dupes").read_text(errors="replace")
    brannoc = journey.reconnect_character(rig.port, expected_room=None, account="Otheracct",
                                          character="Brannoc")
    screen(brannoc, "look", 3)  # the load finishes after the login
    assert "You get a banana" in screen(brannoc, "get banana")
    save(taverek)
    save(brannoc)
    taverek.close()
    brannoc.close()
    assert rig.sql("SELECT GROUP_CONCAT(pid) FROM player_items WHERE vnum=15") == taker, \
        "two characters hold the banana"
    print(f"handover: generation {first} restored the banana Brannoc dropped; the boot kept "
          "its record, so Taverek's older copy stayed out and only Brannoc holds it",
          flush=True)


def midcapture(rig: Rig) -> None:
    rig.boot()
    client = enter(rig)
    # Between the player checkpoints 5 and 35 seconds after the boot, so that no save finds
    # the banana in the character's hands and records it as the character's.
    time.sleep(max(0, 7 - (time.monotonic() - rig.booted)))
    client.send("get banana")
    client.send("put banana basket")
    client.expect("You get a banana", timeout=10)
    client.expect("Ok.", timeout=10)
    assert time.monotonic() - rig.booted < 27, "the character entered too late"
    rig.wait_for("no capture started", 60, lambda:
                 "starting bounded world recovery capture" in rig.log("sys"))
    client.send("get banana basket")
    client.send("drop banana")
    client.expect("You drop a banana", timeout=10)
    assert not re.search(ACKNOWLEDGED, rig.log("sys")), "the capture ended before the drop"
    first = rig.generation()
    floor_drops = f"{rig.namespace}:season:1:floor_drops"
    rig.wait_for("the drop was not journaled", 45, lambda:
                 rig.redis_cli("HLEN", floor_drops) == "1")
    client.close()
    rig.kill()

    rig.boot()
    rig.restored(first)
    assert "left out 1 floor records" in rig.log("sys"), rig.log("sys")[-1500:]
    client = journey.reconnect_character(rig.port, expected_room=None)
    floor, basket = screen(client, "look"), screen(client, "look in basket")
    client.close()
    assert "banana lies here" not in floor and "banana" in basket, floor + basket
    print(f"midcapture: generation {first} held the banana once, in the basket it left "
          "while the capture ran; the boot restored it and left the journaled drop out",
          flush=True)


def slowread(rig: Rig) -> None:
    rig.boot()
    first = rig.generation()
    rig.kill()

    rig.proxy.reads = 0
    rig.proxy.slow = True
    rig.boot()
    rig.restored(first)
    rig.proxy.slow = False
    # The boot's check, its restore and its consume each read the sequence: twice each.
    assert rig.proxy.reads >= 6, rig.proxy.reads
    print(f"slowread: the boot read the current sequence {rig.proxy.reads} times, every "
          f"other one answered past its deadline, and restored generation {first}",
          flush=True)


# A scenario, its zone lines, whether the fixture's mobs are kept, and the proxy.
SCENARIOS = {"crash": (crash, [BANANA], True, False),
             "copyover": (copyover, [BANANA], True, False),
             "restart": (restart, [BANANA], True, False),
             "taken": (taken, [BANANA, MACE], False, False),
             "handover": (handover, [BANANA], False, False),
             "midcapture": (midcapture, BUSY, False, False),
             "slowread": (slowread, [BANANA], True, True)}

if __name__ == "__main__":
    if not os.getenv("TEST_DB_HOST"):
        print("world restart journey skipped: run it through with_disposable_mariadb.sh")
    else:
        scenario, *settings = SCENARIOS[sys.argv[2]]
        rig = Rig(Path(sys.argv[1]).resolve(strict=True), *settings)
        try:
            scenario(rig)
        finally:
            rig.close()
        print(f"world restart journey passed: {sys.argv[2]}")
