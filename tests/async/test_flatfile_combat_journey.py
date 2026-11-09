#!/usr/bin/env python3
"""End-to-end combat, death, corpse-loot, save, and reconnect regression.

The journey boots the real server against a disposable MariaDB schema and a
small deterministic world fixture.  It deliberately crosses protocol parsing,
account and character creation, command dispatch, combat pulses, NPC and player
death, both corpse types, item movement, terminal saves, and player reload.
"""

from __future__ import annotations

import server_build_artifacts

import argparse
import contextlib
import os
import fcntl
import pathlib
import random
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import uuid


ROOT = pathlib.Path(__file__).resolve().parents[2]
ACCOUNT = "Journeyacct"
PASSWORD = "Qz7!mN4@"
CHARACTER = "Taverek"
EMAIL = "journey@example.invalid"
INSPECTOR = ROOT / "bin/tests/coin-death-inspector"
ANSI = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_TAIL = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*)?\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


_port_lock = None
_reserved_ports: set[int] = set()


@contextlib.contextmanager
def mariadb_authority():
    """A freshly migrated schema on the with_disposable_mariadb.sh server.

    Yields (env, sql): env is the base server environment for that schema, and
    sql(statement, selected=True) runs a statement and returns its stripped output.
    """
    host = os.environ["TEST_DB_HOST"]
    require(host in ("127.0.0.1", "localhost"), "use a disposable loopback database")
    database = "journey_" + uuid.uuid4().hex[:12]
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "ENVIRONMENT": "local",
        "REDIS": "FALSE", "CHAOS_MUD": "FALSE", "LISTEN_ADDRESS": "127.0.0.1",
        "DURIS_WEBSOCKET_LISTEN_ADDRESS": "127.0.0.1",
        "PERSISTENCE_MODE": "mariadb-primary", "DB_TLS": "FALSE", "DB_HOST": host,
        "DB_PORT": os.environ.get("TEST_DB_PORT", "3306"), "DB_NAME": database,
        "DB_USER": os.environ["TEST_DB_USER"], "DB_PASSWD": os.environ["TEST_DB_PASSWORD"],
        "DB_ALLOWED_TARGETS": host + "/" + database, "MYSQL_PWD": os.environ["TEST_DB_PASSWORD"],
    }
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    mysql = ["mysql", "--protocol=tcp", "-h", host, "-P", env["DB_PORT"], "-u", env["DB_USER"], "-N", "-B"]
    mysql.append("--ssl-mode=DISABLED" if "--ssl-mode" in subprocess.check_output(
        ["mysql", "--help"], text=True, stderr=subprocess.STDOUT) else "--skip-ssl")

    def sql(statement: str, selected: bool = True) -> str:
        return subprocess.check_output(mysql + ([database] if selected else []),
                                       input=statement, text=True, env=env).strip()

    sql(f"CREATE DATABASE {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    try:
        sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
        for step in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
            subprocess.run(["python3", "scripts/migration_runner.py", *step], cwd=ROOT, env=env,
                           check=True, capture_output=True)
        # Published news, as a provisioned world has; the prompt's "(news)" marker depends on it.
        sql("INSERT INTO mud_info(name,content) VALUES('news','Journey news.')")
        yield env, sql
    finally:
        sql(f"DROP DATABASE {database}", False)


def import_help(runtime: pathlib.Path, environment: dict[str, str]) -> None:
    """Load the real help catalogue into the disposable schema (a provisioned world has it)."""
    if not (runtime / "help").exists():
        (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
    (runtime / "scripts").mkdir()
    importer = runtime / "scripts/import_help_to_prod.sh"
    shutil.copy2(ROOT / "scripts/import_help_to_prod.sh", importer)
    imported = subprocess.run(["bash", str(importer), "--local"], input="yes\n", text=True,
                              env=environment, capture_output=True, timeout=90)
    require(imported.returncode == 0, imported.stdout[-2000:] + imported.stderr[-2000:])


def available_ports() -> tuple[int, int, int]:
    """Reserve a non-privileged plain/TLS/WebSocket port set.

    The server binds the set only after its boot, so a free probe alone races every
    other journey picking ports meanwhile, in this gate or another one beside it. The
    set is also locked in a shared file until this process exits, and other journeys
    skip a locked port.
    """
    global _port_lock
    if _port_lock is None:
        _port_lock = open(os.path.join(tempfile.gettempdir(), "duris-test-ports.lock"), "a")
    for _ in range(200):
        # Below the kernel's ephemeral range, which outgoing connections and
        # Docker's published ports draw from while the server is still booting.
        plain = random.randrange(20000, 32000)
        if _reserved_ports & {plain, plain + 1, plain + 2}:
            continue
        try:
            fcntl.lockf(_port_lock, fcntl.LOCK_EX | fcntl.LOCK_NB, 3, plain)
        except OSError:
            continue
        probes = [socket.socket() for _ in range(3)]
        try:
            probes[0].bind(("127.0.0.1", plain))
            probes[1].bind(("127.0.0.1", plain + 1))
            probes[2].bind(("127.0.0.1", plain + 2))
            _reserved_ports.update((plain, plain + 1, plain + 2))
            return plain, plain + 1, plain + 2
        except OSError:
            fcntl.lockf(_port_lock, fcntl.LOCK_UN, 3, plain)
            continue
        finally:
            for probe in probes:
                probe.close()
    raise AssertionError("could not reserve isolated listener ports")


class MudClient:
    ansi_tail = b""  # an escape sequence the end of the last read cut off

    def __init__(self, port: int, *, source_host: str | None = None) -> None:
        deadline = time.monotonic() + 30
        while True:
            try:
                self.socket = socket.create_connection(
                    ("127.0.0.1", port), timeout=1,
                    source_address=(source_host, 0) if source_host else None,
                )
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
        self.socket.settimeout(0.25)
        self.pending = bytearray()
        self.transcript = bytearray()
        self.raw_transcript = bytearray()

    def close(self) -> None:
        self.socket.close()

    def send(self, line: str) -> None:
        self.socket.sendall(line.encode("ascii") + b"\n")

    def _clean(self, data: bytes) -> bytes:
        """Strip ANSI escapes, holding back one that the end of a read cut off."""
        data = self.ansi_tail + data
        tail = ANSI_TAIL.search(data)
        self.ansi_tail = data[tail.start():] if tail else b""
        return ANSI.sub(b"", data[: tail.start()] if tail else data)

    def _receive(self) -> bool:
        try:
            chunk = self.socket.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            raise AssertionError("server closed the gameplay connection")
        self.raw_transcript.extend(chunk)
        cleaned = self._clean(chunk)
        self.pending.extend(cleaned)
        self.transcript.extend(cleaned)
        return True

    def expect(self, needle: str, timeout: float = 15) -> str:
        matched, output = self.expect_any((needle,), timeout)
        require(matched == needle, f"unexpected match {matched!r}")
        return output

    def expect_any(self, needles: tuple[str, ...], timeout: float = 15) -> tuple[str, str]:
        targets = tuple((needle, needle.encode("ascii")) for needle in needles)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            cleaned = bytes(self.pending)
            for needle, target in targets:
                position = cleaned.find(target)
                if position >= 0:
                    # Login output is ASCII apart from Telnet negotiation. Consume
                    # through the last target byte while retaining a readable slice.
                    consumed = cleaned[: position + len(target)]
                    del self.pending[: position + len(target)]
                    return needle, consumed.decode("utf-8", errors="replace")
            self._receive()
        readable = bytes(self.pending).decode("utf-8", errors="replace")
        raise AssertionError(f"timed out waiting for {needles!r}; received:\n{readable[-6000:]}")

def make_fixture(run_root: pathlib.Path, reset_coins: bool = False) -> None:
    for directory in ("areas", "docs"):
        (run_root / directory).symlink_to(ROOT / directory, target_is_directory=True)

    runtime_lib = run_root / "lib"
    shutil.copytree(ROOT / "lib", runtime_lib)
    properties_path = runtime_lib / "duris.properties"
    properties = properties_path.read_text()
    require("camp.timer=9.000" in properties, "camp timer fixture changed")
    properties_path.write_text(properties.replace("camp.timer=9.000", "camp.timer=2.000"))

    mini = run_root / "areas_mini"
    shutil.copytree(ROOT / "areas_mini", mini)

    mobile_path = mini / "mini.mob"
    mobiles = mobile_path.read_text()
    # Exercise both wallet-created and reset-created piles without prior custody.
    # A nonempty reset prototype must not add coins to later wallet conversions.
    start = mobiles.index("#11\n")
    end = mobiles.index("#12\n", start)
    raoul = mobiles[start:end]
    if reset_coins:
        raoul = raoul.replace("raoul~", "raoul _nomoney_~", 1)
    require("0.0.0.0 0" in raoul, "Raoul wallet fixture changed")
    mobiles = mobiles[:start] + raoul + mobiles[end:]
    objects_path = mini / "mini.obj"
    objects = objects_path.read_text()
    start = objects.index("#3\n")
    end = objects.index("#4\n", start)
    coins = objects[start:end]
    require("0 0 0 0 0 0 0 0" in coins, "money object fixture changed")
    objects = objects[:start] + coins.replace(
        "0 0 0 0 0 0 0 0", "0 3 0 0 0 0 0 0" if reset_coins else "0 0 0 0 0 0 0 0") + objects[end:]
    # End the low-HP NPC fight on a landed hit instead of depending on many
    # random attack/dodge rolls while Raoul is wounded. Keep real combat and
    # death handling; the executioner's 51,000 HP still safely exceeds this.
    start = objects.index("#677\n")
    end = objects.index("#678\n", start)
    mace = objects[start:end]
    require("6 1 6 7 0 0 0 0" in mace, "starter mace fixture changed")
    objects_path.write_text(objects[:start] + mace.replace(
        "6 1 6 7 0 0 0 0", "6 100 1 7 0 0 0 0") + objects[end:])
    executioner = """#22800
regression executioner~
the regression executioner~
The regression executioner waits here to test the player death path.
~
~
10 0 0 0 0 0 0 0 S
PH 0 0 -1
60 0 -250 1000d1+50000 10d10+200
0.0.0.0 0
8 8 0
"""
    require(mobiles.count("$~") == 1, "minimal mobile terminator changed")
    mobile_path.write_text(mobiles.replace("$~", executioner + "$~"))

    world_path = mini / "mini.wld"
    world = world_path.read_text()
    fixture_room = """#22800
The Regression Arena~
This quiet stone arena exists to prove the complete combat journey.\n~
1 0 0
S
"""
    require(world.count("$~") == 1, "minimal world terminator changed")
    world_path.write_text(world.replace("$~", fixture_room + "$~"))

    zone_path = mini / "mini.zon"
    zone = zone_path.read_text()
    require("1299 0 0 6 11 1" in zone, "minimal zone header changed")
    require(zone.count("\nS\n") == 1, "minimal zone terminator changed")
    zone = zone.replace("1299 0 0 6 11 1", "29999 0 0 6 11 1")
    reset = (
        "M 0 11 1 22800 100 0 0 0 * deterministic combat target\n"
        "G 1 15 1 0 100 0 0 0 * corpse-loot marker\n"
        + ("G 1 3 1 0 100 0 0 0 * reset-created coins\n" if reset_coins else "")
        +         "M 0 22800 1 22800 100 0 0 0 * deterministic player-death target\n"
    )
    zone_path.write_text(zone.replace("\nS\n", "\n" + reset + "S\n"))


def inspect_authority(sql, character: str = CHARACTER) -> dict:
    """The character's saved wallet, bank, counters and item custody, read from the schema."""
    row = sql("SELECT pid,copper,silver,gold,platinum,wallet_revision,numb_deaths,exp,level,"
              f"racewar,account_name FROM player_data WHERE name='{character}'").split("\t")
    pid, racewar, account = row[0], row[9], row[10]
    # An account has no bank row before its first deposit; that reads as an empty bank.
    bank = sql("SELECT bank_copper,bank_silver,bank_gold,bank_platinum,bank_revision FROM account_banks "
               f"WHERE account_name='{account}' AND racewar={racewar}").split()
    items = sql("SELECT item_uid,vnum,root_item_uid,parent_item_uid,item_revision,owner_type "
                "FROM item_current_owner WHERE state=1 AND "
                f"((owner_type=1 AND owner_id={pid}) OR owner_type=3) ORDER BY item_uid")
    rows = [line.split("\t") for line in items.splitlines()]
    custody = [(row[5], {"uid": int(row[0]), "vnum": int(row[1]), "root": int(row[2]),
                         "parent": int(row[3]) if row[3] != "NULL" else None,
                         "revision": int(row[4])}) for row in rows]
    return {
        "pid": int(pid),
        "wallet": [int(value) for value in row[1:5]],
        "wallet_revision": int(row[5]),
        "death_count": int(row[6]),
        "experience": int(row[7]),
        "level": int(row[8]),
        "bank": [int(value) for value in bank[:4]] if bank else [0, 0, 0, 0],
        "bank_revision": int(bank[4]) if bank else 0,
        "player_items": [item for owner, item in custody if owner == "1"],
        "room_items": [item for owner, item in custody if owner == "3"],
        "snapshot_uids": [int(uid) for uid in sql(
            f"SELECT obj_uid FROM player_items WHERE pid={pid} ORDER BY obj_uid").split()],
    }


def add_ghost_record(sql, pid: int, parent_uid: int) -> int:
    """Add one ownership row with no payload item under the player's root."""
    ghost = 9000000000000000000 + pid
    sql("INSERT INTO item_current_owner(item_uid,root_item_uid,parent_item_uid,owner_type,owner_id,"
        f"item_revision,vnum,state) VALUES({ghost},{parent_uid},{parent_uid},1,{pid},1,15,1)")
    return ghost


def attack_until_death(client: MudClient) -> None:
    """A fumbled initial hit can leave both combatants standing; try again."""
    deadline = time.monotonic() + 45
    client.send("hit executioner")
    while True:
        remaining = deadline - time.monotonic()
        require(remaining > 0, "executioner did not kill the fixture player")
        outcome, _ = client.expect_any((
            "Your wounds claim you at last",
            "You stumble, but recover in time!",
            "You stumble in your attack, and jab at",
            "You stumble in your attack, and hit yourself!",
        ), timeout=remaining)
        if outcome == "Your wounds claim you at last":
            return
        client.send("hit executioner")


def ghost_ownership_record(port: int, sql, run_root: pathlib.Path) -> int:
    """An ownership record whose payload item is gone is only counted at load.

    Memory is the authority: the character loads every payload item the catalog
    gives it, saves what it holds and leaves at once. Nothing is read-only and
    nothing is refused over the record. Returns the record's uid.
    """
    client = reconnect_character(port)
    try:
        client.send("save")
        client.expect(f"Saving {CHARACTER}.")
        before = inspect_authority(sql)
        banana = next(item["uid"] for item in before["player_items"] if item["vnum"] == 15)
        client.send("quit")
        client.expect("ACCOUNT MENU", timeout=30)
        client.send("0")
        client.close()
        ghost = add_ghost_record(sql, before["pid"], banana)
        require(any(item["uid"] == ghost and item["parent"] == banana
                    for item in inspect_authority(sql)["player_items"]),
                "ghost ownership record was not installed")
        client = reconnect_character(port)
        client.send("inventory")
        client.expect("a banana", timeout=15)
        deadline = time.monotonic() + 15
        while "outcome=missing_payload_rows" not in runtime_logs(run_root):
            require(time.monotonic() < deadline, "missing payload row was not reported at load")
            time.sleep(0.01)
        client.send("save")
        client.expect(f"Saving {CHARACTER}.")
        after = inspect_authority(sql)
        require(any(item["uid"] == banana for item in after["player_items"]),
                "the save after the load dropped a held item")
        require(after["wallet"] == before["wallet"], "the load changed the wallet")
        started = time.monotonic()
        client.send("quit")
        client.expect("ACCOUNT MENU", timeout=30)
        elapsed = time.monotonic() - started
        print(f"mariadb-primary ghost-record camp-to-account-menu (n=1, isolated): {elapsed:.3f}s",
              flush=True)
        client.send("0")
        return ghost
    finally:
        client.close()


def generate_certificate(run_root: pathlib.Path) -> None:
    generated = subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-keyout",
            str(run_root / "duris.key"),
            "-out",
            str(run_root / "duris.crt"),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    require(generated.returncode == 0, "certificate generation failed:\n" + generated.stdout)
    (run_root / "duris.key").chmod(0o600)


def runtime_logs(run_root: pathlib.Path) -> str:
    """Collect bounded synthetic-server logs for actionable journey failures."""
    sections = []
    for path in sorted((run_root / "logs/log").glob("*")):
        if not path.is_file() or path.name == ".gitignore":
            continue
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        if content:
            sections.append(f"--- {path.name} ---\n{content[-8000:]}")
    return "\n".join(sections)[-30000:]


def create_character(client: MudClient, expected_room: str | None = "The Regression Arena",
                     class_name: str = "w", *, account: str = ACCOUNT,
                     character: str = CHARACTER, email: str = EMAIL,
                     hometown: str | None = None, race_name: str = "h",
                     existing_account: bool = False, alignment: str = "g",
                     hardcore: bool = False, expected_hometown: str | None = None) -> None:
    entry, _ = client.expect_any(("term type", "account name"))
    if entry == "term type":
        client.send("9")
        client.expect("account name")
    client.send(account)
    if existing_account:
        client.expect("enter your password")
        client.send(PASSWORD)
    else:
        client.expect("is this correct?")
        client.send("y")
        client.expect("email address")
        client.send(email)
        client.expect("is this correct?")
        client.send("y")
        client.expect("enter your password")
        client.send(PASSWORD)
        client.expect("Please re-enter the same password to confirm:  ")
        client.send(PASSWORD)
        client.expect("information correct?")
        client.send("y")
    client.expect("PRESS RETURN")
    client.send("")
    client.expect("Please select an option")
    client.send("2")
    client.expect("Enter your new name")
    client.send(character)
    client.expect("Is this correct?")
    client.send("y")
    client.expect("meet these criteria?")
    client.send("y")
    client.expect("Your selection")
    client.send(race_name)
    client.expect("Male or Female")
    client.send("m")
    prompt, warning = client.expect_any(("Please select either H", "Class Selection"))
    if prompt == "Please select either H":
        if hardcore:
            require("Hardcore char can only die 3 times" in warning,
                    "Hardcore creation did not warn about three counted deaths")
        client.send("h" if hardcore else "n")
        client.expect("Class Selection")
    else:
        require(not hardcore, "Hardcore creation was not offered")
    client.send(class_name)
    stat_prompt_seen = False
    prompt, _ = client.expect_any(("Alignment Selection", "Hometown Selection", "Your stat rolling system [D]:"))
    if prompt == "Alignment Selection":
        client.expect("Your selection")
        client.send(alignment)
        prompt, _ = client.expect_any(("Hometown Selection", "Your stat rolling system [D]:"))
    if prompt == "Hometown Selection":
        menu = client.expect("Your selection")
        if expected_hometown:
            require(f"{hometown}) {expected_hometown}" in menu, menu)
        if hometown is None:
            # Keep the existing preference for the optional first introduction,
            # using the actual offered key (Life can be L; Chaos uses C).
            choices = re.findall(r"(?m)^\s*([A-Za-z0-9])\)([^\r\n]+)", menu)
            require(bool(choices), "hometown menu had no selectable choices")
            hometown = next((key for key, name in choices if "Beginner Introduction" in name), choices[0][0])
        client.send(hometown)
    else:
        stat_prompt_seen = True
    if not stat_prompt_seen:
        client.expect("Your stat rolling system [D]:")
    client.send("")
    for label, stat in zip(("first bonus", "second bonus", "third bonus", "fourth bonus"), "sdal"):
        client.expect(label)
        client.send(stat)
    client.expect("swap stats")
    client.send("n")
    summary = client.expect("keep this character")
    if expected_hometown:
        require(f"HOMETOWN: {expected_hometown}" in summary.splitlines(), summary)
    client.send("y")
    client.expect("Please select an option")
    client.send("1")
    client.expect(character)
    client.send(character)
    client.expect("(Y/N)")
    client.send("y")
    client.expect("PRESS RETURN")
    client.send("")
    if expected_room:
        client.expect(expected_room, timeout=30)
    client.expect_any(("Your starter kit is ready", "Your Chaos Equipment has been prepared"),
                      timeout=30)


def complete_npc_combat_journey(client: MudClient, reset_coins: bool = False) -> None:
    client.send("wield mace")
    client.expect("You wield", timeout=10)
    client.send("drop all")
    client.expect("You drop a steel long sword.", timeout=20)
    client.send("look")
    room = client.expect("The Regression Arena", timeout=10)
    occupants = client.expect("Pos: standing >", timeout=10)
    require("Regression Arena" in room, "look did not render the fixture room")
    require("Raoul" in occupants, "combat target was not in the fixture room")
    require(
        "regression executioner" in occupants,
        "player-death target was not in the fixture room",
    )

    client.send("kill raoul")
    combat_deadline = time.monotonic() + 45
    while True:
        remaining = combat_deadline - time.monotonic()
        require(remaining > 0, "Raoul survived the combat journey timeout")
        outcome, _ = client.expect_any(
            (
                "is dead! R.I.P.",
                "You stumble, but recover in time!",
                "You stumble in your attack, and jab at",
                "You stumble in your attack, and hit yourself!",
            ),
            timeout=remaining,
        )
        if outcome == "is dead! R.I.P.":
            break
        # A fumble can intentionally stop combat before the initial hit engages
        # either participant, or during a later round. Resume the journey just as
        # a player would instead of waiting for a fight that is no longer active.
        client.send("kill raoul")
    client.send("look")
    client.expect("corpse of raoul", timeout=10)
    client.send("look in corpse")
    corpse = client.expect("banana", timeout=10)
    require("corpse" in corpse.lower(), "loot marker was not inside the corpse")

    # The coins move into the wallet in memory, at once.
    client.send("get coins corpse")
    client.expect("There were: 3 silver coins." if reset_coins else
                  "There were: 1 copper coin.", timeout=15)

    client.send("get banana corpse")
    client.expect("get a banana", timeout=10)
    client.send("inventory")
    client.expect("a banana", timeout=10)

    client.send("save")
    client.expect(f"Saving {CHARACTER}.", timeout=15)
    client.send("quit")
    client.expect("ACCOUNT MENU", timeout=30)
    client.send("0")


def reconnect_character(
    port: int,
    return_message: str | None = None,
    expected_room: str | None = "The Regression Arena",
    *,
    account: str = ACCOUNT,
    character: str = CHARACTER,
    source_host: str | None = None,
) -> MudClient:
    client = MudClient(port, source_host=source_host)
    try:
        entry, _ = client.expect_any(("term type", "account name"))
        if entry == "term type":
            client.send("9")
            client.expect("account name")
        client.send(account)
        client.expect("enter your password")
        client.send(PASSWORD)
        client.expect("PRESS RETURN")
        client.send("")
        client.expect("Please select an option")
        client.send("1")
        client.expect(character)
        client.send("1")
        entry, _ = client.expect_any(("Play as", "Reconnecting...", "Overriding old connection..."))
        if entry == "Play as":
            client.send("y")
        if return_message:
            client.expect(return_message, timeout=30)
        if expected_room:
            client.expect(expected_room, timeout=30)
        return client
    except Exception:
        client.close()
        raise


def make_overlord(sql, name: str) -> None:
    """Raise character `name` to OVERLORD while no server runs.

    Character creation refuses god_list names, the one way a new character
    ever started as an OVERLORD, so a journey that needs a god promotes an
    ordinary character here, as staff must after a wipe.
    """
    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{name}'")


def verify_npc_loot_and_die(port: int) -> None:
    client = reconnect_character(port)
    try:
        client.send("inventory")
        client.expect("a banana", timeout=15)
        attack_until_death(client)
        client.expect("ACCOUNT MENU", timeout=45)
        client.send("0")
    finally:
        client.close()


def recover_player_corpse(port: int, sql, reset_coins: bool = False) -> None:
    # MariaDB keeps no last-exit reason, so the login after a death prints the normal text.
    client = reconnect_character(port, "Welcome to Duris")
    try:
        client.send("look")
        client.expect("The corpse of a Human is lying here.", timeout=10)
        client.send(f"look in {CHARACTER}")
        corpse = client.expect("a banana", timeout=10)
        require(CHARACTER in corpse, "player corpse did not contain the saved loot marker")
        # A player's coins go into the corpse at death, and the death saved the empty
        # wallet (persistence reset phase 2 step 4).
        require(inspect_authority(sql)["wallet"] == [0, 0, 0, 0],
                "the death did not save an empty wallet")
        client.send(f"get coins {CHARACTER}")
        client.expect("There were: 3 silver coins." if reset_coins else
                      "There were: 1 copper coin.", timeout=15)

        client.send(f"get banana {CHARACTER}")
        client.expect("get a banana", timeout=15)
        client.send("save")
        client.expect(f"Saving {CHARACTER}.", timeout=15)
        client.send("quit")
        client.expect("ACCOUNT MENU", timeout=30)
        client.send("0")
    finally:
        client.close()


def verify_recovered_loot(port: int) -> None:
    client = reconnect_character(port)
    try:
        client.send("inventory")
        client.expect("a banana", timeout=15)
        client.send("quit")
        client.expect("ACCOUNT MENU", timeout=30)
        client.send("0")
    finally:
        client.close()


def build_flatfile_server(build_root: pathlib.Path, *, real_clock: bool = False) -> pathlib.Path:
    """Acquire the shared artifact while retaining journey-owned runtime state."""
    return server_build_artifacts.build_flatfile_server(build_root, real_clock=real_clock)


def run_journey(binary: pathlib.Path, reset_coins: bool = False,
                first_session_only: bool = False, populated_bank: bool = False,
                boons_enabled: bool = False) -> None:
    print(f"combat journey: reset_coins={reset_coins} boons_enabled={boons_enabled}", flush=True)
    with tempfile.TemporaryDirectory(prefix="duris-combat-run-") as run_tmp:
        with mariadb_authority() as (environment, sql):
            run_root = pathlib.Path(run_tmp)
            (run_root / "logs/log").mkdir(parents=True)
            (run_root / "logs/log/.gitignore").write_text("*\n!.gitignore\n")
            make_fixture(run_root, reset_coins)
            if first_session_only:
                zone = run_root / "areas_mini/mini.zon"
                # This fixture needs no combatants (or NPC scavengers).
                zone.write_text(re.sub(r"^[MG] .*\n", "", zone.read_text(), flags=re.M).replace(
                    "\nS\n", "\nO 0 3 10 22800 100 0 0 0 * first-session coins\nS\n"))
            generate_certificate(run_root)

            journal_root = run_root / "journals"
            (journal_root / "players").mkdir(parents=True, mode=0o700)
            (journal_root / "critical").mkdir(mode=0o700)
            plain_port, tls_port, websocket_port = available_ports()
            output_path = run_root / "server.out"
            environment.update({
                "CRITICAL_COMMAND_JOURNAL_DIR": str(journal_root / "critical"),
                "DURIS_TLS_PORT": str(tls_port),
                "DURIS_WEBSOCKET_PORT": str(websocket_port),
                "DURIS_NEVENT_TRACE_PLAYER": "1",
                # The ghost record's missing_payload_rows line is a trace (#11).
                "DURIS_PERSISTENCE_TRACE": "1",
            })

            with output_path.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(
                    [str(binary), "--minimal", "-s", "-d", str(run_root), str(plain_port)],
                    cwd=run_root,
                    env=environment,
                    text=True,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
                client: MudClient | None = None
                try:
                    deadline = time.monotonic() + 120
                    boot_output = ""
                    while time.monotonic() < deadline:
                        output.flush()
                        boot_output = output_path.read_text(errors="replace")
                        if "Entering game loop." in boot_output:
                            break
                        if process.poll() is not None:
                            break
                        time.sleep(0.1)
                    require(
                        "Entering game loop." in boot_output,
                        "isolated combat server did not boot:\n" + boot_output[-8000:],
                    )

                    if populated_bank:
                        # The account already has money on the character's side. The row
                        # is inserted after the boot, whose currency checks want a baseline.
                        sql("SET FOREIGN_KEY_CHECKS=0;"
                            "INSERT INTO account_banks(account_name,racewar,bank_copper,bank_silver,"
                            f"bank_gold,bank_platinum,bank_revision) VALUES('{ACCOUNT}',1,19,23,31,47,2)")
                    client = MudClient(plain_port)
                    create_character(client)
                    if first_session_only:
                        from test_flatfile_first_session_currency import verify_first_session
                        verify_first_session(client, plain_port, sql, populated_bank)
                        return
                    if not boons_enabled:
                        client.send("toggle boon")
                        client.expect("Divine Boons apply automatically. Your stored legacy setting is preserved.")
                    complete_npc_combat_journey(client, reset_coins)
                    client.close()
                    client = None
                    coin_balance = [0, 3, 0, 0] if reset_coins else [1, 0, 0, 0]
                    require(inspect_authority(sql)["wallet"] == coin_balance,
                            "NPC pickup/save did not conserve coins")
                    verify_npc_loot_and_die(plain_port)
                    recover_player_corpse(plain_port, sql, reset_coins)
                    verify_recovered_loot(plain_port)
                    require(inspect_authority(sql)["wallet"] == coin_balance,
                            "reconnect or corpse recovery changed the coin total")
                    ghost = ghost_ownership_record(plain_port, sql, run_root)

                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    output.flush()
                    server_output = output_path.read_text(errors="replace")
                    require(
                        process.returncode == 0,
                        f"server shutdown failed ({process.returncode}):\n{server_output[-8000:]}",
                    )
                    require(
                        "Normal termination of game." in server_output,
                        "combat journey did not reach normal server shutdown",
                    )
                    require(
                        "FATAL:" not in server_output and "assert:" not in server_output,
                        "combat journey logged a fatal/assertion failure:\n" + server_output[-8000:],
                    )
                    # Boot again with the same schema. Compare the wallet and the
                    # rest after re-entry and another save. The boot reaps every player
                    # record with no payload (#11): the ghost, and the starter kit that
                    # dissolved when the character dropped it. The login after it counts
                    # nothing.
                    before_restart = inspect_authority(sql)
                    require(any(item["uid"] == ghost for item in before_restart["player_items"]),
                            "the ghost record was not in place before the restart")
                    before_restart["player_items"] = [
                        item for item in before_restart["player_items"]
                        if item["uid"] in before_restart["snapshot_uids"]]
                    gaps = runtime_logs(run_root).count("outcome=missing_payload_rows")
                    # With the switch on, each save of the looted banana named it (#11).
                    require(re.search(r"outcome=unowned_object uid=\d+ vnum=15", runtime_logs(run_root)),
                            "the looted banana was not traced on its saves")
                    offset = output_path.stat().st_size
                    process = subprocess.Popen(
                        [str(binary), "--minimal", "-s", "-d", str(run_root), str(plain_port)],
                        cwd=run_root, env=environment, text=True,
                        stdout=output, stderr=subprocess.STDOUT)
                    deadline = time.monotonic() + 120
                    while b"Entering game loop." not in output_path.read_bytes()[offset:]:
                        require(process.poll() is None and time.monotonic() < deadline,
                                "combat server did not restart")
                        time.sleep(0.1)
                    client = reconnect_character(plain_port)
                    client.send("save")
                    client.expect(f"Saving {CHARACTER}.")
                    client.send("quit")
                    client.expect("ACCOUNT MENU", timeout=30)
                    client.send("0")
                    client.close()
                    client = None
                    after_restart = inspect_authority(sql)
                    for field in ("wallet", "wallet_revision", "player_items",
                                  "death_count", "experience", "level"):
                        require(after_restart[field] == before_restart[field],
                                f"restart/re-entry changed {field}")
                    require(after_restart["snapshot_uids"] == before_restart["snapshot_uids"],
                            "restart/re-entry changed the inventory")
                    require(runtime_logs(run_root).count("outcome=missing_payload_rows") == gaps,
                            "the login after the reap still counted the ghost")
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    require(process.returncode == 0, "restarted server shutdown failed")
                except Exception as error:
                    output.flush()
                    server_output = output_path.read_text(errors="replace")
                    logs = runtime_logs(run_root)
                    raise AssertionError(
                        f"{error}\n\n--- isolated server output ---\n{server_output[-12000:]}"
                        f"\n\n--- isolated runtime logs ---\n{logs}"
                    ) from error
                finally:
                    if client is not None:
                        client.close()
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


VARIANTS = {"default": {}, "reset-coins": {"reset_coins": True},
            "boons": {"boons_enabled": True}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=pathlib.Path, required=True)
    args = parser.parse_args()
    # The variants share one disposable server and its instance-wide migration lock.
    for options in VARIANTS.values():
        run_journey(args.server.resolve(), **options)
    print("combat, player death, corpse recovery, save, and reconnect journey passed")
