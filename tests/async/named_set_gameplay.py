"""Shared native I/O and disposable MariaDB qualification for named-set journeys."""

import json
import os
import re
import subprocess
import time
import test_mariadb_combat_journey as journey


# Required cases: generation room, maximum tier, primary native name and spell ID.
WEAR_CASES = {
    1325: (132500, 5, "armor", 1),
    740: (74000, 5, "battletide", 395),
    827: (82701, 3, "protection from animals", 383),
    13: (1300, 3, "phantom armor", 400),
    44: (4401, 3, "globe of darkness", 302),
    204: (20400, 3, "sense life", 44),
    808: (80800, 3, "enhance agility", 177),
    811: (81100, 3, "protection from animals", 383),
    814: (81400, 3, "vapor strike", 467),
    990: (99001, 3, "scent of the bloodhound", 517),
    300: (30000, 3, "globe of darkness", 302),
    1350: (135001, 3, "phantom armor", 400),
    87: (8700, 5, "spirit ward", 220),
    370: (37000, 3, "endurance", 355),
    676: (67600, 4, "endurance", 355),
    824: (82400, 6, "vitality", 56),
}

def enable_items(client):
    client.socket.sendall(b"\xff\xfd\xc9")
    gmcp(
        client,
        'Core.Supports.Set ["Duris.Capabilities 1","Duris.Session 1","Char.Items 1"]',
    )
    gmcp(client, 'Duris.Subscribe ["Char.Items 1"]')


def gmcp(client, payload):
    client.socket.sendall(b"\xff\xfa\xc9" + payload.encode() + b"\xff\xf0")


def selectors(client, uids):
    wanted = set(uids)
    # The automatic stream replaces both locations after each mutation.
    # Get [] resets scopes and can race already queued pages from older scopes.
    score(client)
    ready_after = time.monotonic() + 0.6  # Stream flushes occur every 500 ms.
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        found = {}
        completed = set()
        revision = None
        for packet in re.findall(
            rb"\xff\xfa\xc9(.*?)\xff\xf0", bytes(client.raw_transcript), re.S
        ):
            if not packet.startswith(b"Char.Items.List "):
                continue
            page = json.loads(packet.split(b" ", 1)[1])
            if page["location"] not in ("inv", "eq"):
                continue
            current_revision = (
                page["context"],
                page["process"],
                page["generation"],
                page["bodyRevision"],
                page["revision"],
            )
            if current_revision != revision:
                found.clear()
                completed.clear()
                revision = current_revision
            if page["complete"]:
                completed.add(page["location"])
            for item in page["items"]:
                token = item.get("selector")
                if not token:
                    continue
                uid = int(token.rsplit(":", 1)[1])
                if uid in wanted:
                    found[uid] = token
        if (
            time.monotonic() >= ready_after
            and completed == {"inv", "eq"}
            and wanted <= found.keys()
        ):
            return found
        client._receive()
    raise AssertionError("no current GMCP selectors for " + str(wanted))


def selector(client, uid):
    return selectors(client, [uid])[uid]


def put(client, uid, bag):
    tokens = selectors(client, [uid, bag])
    client.send("put " + tokens[uid] + " " + tokens[bag])
    client.expect("Ok.", timeout=30)
    score(client)


def get_from_container(client, uid, bag):
    container = selector(client, bag)
    offset = len(client.raw_transcript)
    gmcp(client, "Char.Items.Get " + json.dumps([container]))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        client._receive()
        for packet in re.findall(
            rb"\xff\xfa\xc9(.*?)\xff\xf0", bytes(client.raw_transcript[offset:]), re.S
        ):
            if not packet.startswith(b"Char.Items.List "):
                continue
            page = json.loads(packet.split(b" ", 1)[1])
            if page["location"] != container or not page["complete"]:
                continue
            token = next(
                (
                    item["selector"]
                    for item in page["items"]
                    if item.get("selector")
                    and item["selector"].endswith(":" + str(uid))
                ),
                None,
            )
            assert token, (uid, page)
            client.send("get " + token + " " + container)
            client.expect("You get", timeout=30)
            score(client)
            return
    raise AssertionError("no completed contents for " + str(bag))


def score(client):
    client.send("score")
    text = client.expect("Score information for")
    text += client.expect("Pos:") + client.expect(">")
    match = re.search(r"Hit points:\s*\d+\((\d+)\)", text)
    assert match, text
    return int(match[1]), text


def save(client, name=journey.CHARACTER):
    client.send("save")
    client.expect("Saving " + name + ".", timeout=30)


def expect_max_hp(client, expected):
    deadline = time.monotonic() + 25
    while True:
        actual, text = score(client)
        if actual == expected:
            return text
        assert time.monotonic() < deadline, ("maximum HP", expected, actual, text)
        time.sleep(0.5)


def inventory_graph(rows):
    return {
        str(row[0]): [row[1], rows[row[2]][0] if row[2] >= 0 else 0, row[3]]
        for row in rows
    }


def dump_authority(environment):
    """Freeze only the stopped, disposable named-set SQL authority."""
    assert environment["DB_HOST"] in ("127.0.0.1", "localhost")
    assert re.fullmatch(r"journey_[a-f0-9]{12}", environment["DB_NAME"])
    return subprocess.check_output([
        "mysqldump", "--protocol=tcp", "-h", environment["DB_HOST"],
        "-P", environment["DB_PORT"], "-u", environment["DB_USER"],
        "--single-transaction", "--skip-comments", "--skip-dump-date", "--hex-blob",
        "--order-by-primary", environment["DB_NAME"]], env=environment)


class NamedSetGame:
    def __init__(self, runtime=None, binary=None, environment=None):
        self.runtime = (runtime or journey.ROOT / os.environ.get(
            "NAMED_SET_RUNTIME", "bin/tests/named-set-roster-world")).resolve()
        self.binary = (binary or journey.ROOT / os.environ.get(
            "NAMED_SET_SERVER", "bin/server/dms_new")).resolve()
        assert self.runtime.is_relative_to((journey.ROOT / "bin/tests").resolve())
        assert (self.runtime / "areas/world.zon").is_file(), "prepare the isolated full world first"
        supplied = environment if environment is not None else os.environ
        self.env = {key: supplied[key] for key in (
            "PATH", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWD", "MYSQL_PWD",
            "DB_ALLOWED_TARGETS")}
        assert self.env["DB_HOST"] in ("127.0.0.1", "localhost")
        assert re.fullmatch(r"journey_[a-f0-9]{12}", self.env["DB_NAME"]), "use the disposable named-set qualifier"
        assert self.env["DB_ALLOWED_TARGETS"] == self.env["DB_HOST"] + "/" + self.env["DB_NAME"]
        self.port, tls, websocket = journey.available_ports()
        self.env.update(
            ENVIRONMENT="local", PERSISTENCE_MODE="mariadb-primary", DB_TLS="FALSE",
            CRITICAL_COMMAND_JOURNAL_DIR=str(self.runtime / "journals/critical"),
            LISTEN_ADDRESS="127.0.0.1", DURIS_TLS_PORT=str(tls),
            DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1", DURIS_WEBSOCKET_PORT=str(websocket),
            REDIS="FALSE", CHAOS_MUD="FALSE",
        )
        if supplied.get("LD_LIBRARY_PATH"):
            self.env["LD_LIBRARY_PATH"] = supplied["LD_LIBRARY_PATH"]
        self.process = self.output = None
        self.clients = []
        self.transcripts = []

    def sql(self, statement):
        return subprocess.check_output([
            "mysql", "--protocol=tcp", "-h", self.env["DB_HOST"], "-P", self.env["DB_PORT"],
            "-u", self.env["DB_USER"], "-N", "-B", self.env["DB_NAME"]],
            input=statement, text=True, env=self.env).strip()

    def make_overlord(self, character=journey.CHARACTER):
        assert character in (journey.CHARACTER, "Meranen")
        self.sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + character + "'")

    def start(self, label):
        log = self.runtime / (label + ".out")
        self.output = log.open("w")
        self.process = subprocess.Popen(
            [
                str(self.binary),
                "-d",
                str(self.runtime),
                str(self.port),
            ],
            cwd=self.runtime,
            env=self.env,
            stdout=self.output,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 120
        while "Entering game loop." not in log.read_text(errors="replace"):
            assert self.process.poll() is None, label + " boot failed"
            assert time.monotonic() < deadline, label + " boot deadline"
            time.sleep(0.1)

    def boot(self, label, *, account=journey.ACCOUNT, character=journey.CHARACTER):
        self.start(label)
        return self.login(account=account, character=character)

    def login(
        self, *, account=journey.ACCOUNT, character=journey.CHARACTER, source_host=None
    ):
        client = journey.reconnect_character(
            self.port,
            expected_room=None,
            account=account,
            character=character,
            source_host=source_host,
        )
        self.clients.append(client)
        client.send("")
        client.expect("Pos:", timeout=30)
        client.expect(">")
        enable_items(client)
        return client

    def stop(self):
        for client in self.clients:
            self.transcripts.append(bytes(client.transcript))
            client.close()
        self.clients.clear()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.output:
            self.output.close()
            self.output = None

    def require_player(self, pid):
        assert pid in (1, 2)
        expected = journey.CHARACTER if pid == 1 else "Meranen"
        assert self.sql("SELECT name FROM player_data WHERE pid=" + str(pid)) == expected

    def items(self, pid=1):
        inventory = {row[0]: row for row in self.inventory(pid)}
        # SQL intentionally restores permanent item state, not transient item
        # affects. Reject durable HP/Constitution and built-in spell modifiers.
        rows = self.sql(
            "SELECT i.obj_uid,e.description,i.equip_slot,COALESCE(i.wear_flags,0),"
            "(NOT EXISTS(SELECT 1 FROM player_item_affects a WHERE a.item_id=i.id "
            "AND a.location IN (13,5,35,45)) AND (COALESCE(i.bitvector1,0) & 528)=0 "
            "AND (COALESCE(i.bitvector4,0) & 393216)=0),COALESCE(i.short_descr,'') "
            "FROM player_items i JOIN player_item_extra_descr e ON e.item_id=i.id "
            "AND e.keyword='DURIS_NAMED_SET_ORIGIN_V1' WHERE i.pid=" + str(pid) + " ORDER BY i.id")
        return [parts[:5] + [str(inventory[int(parts[0])][2]), parts[5]]
                for line in rows.splitlines() if (parts := line.split('\t', 5))]

    def inventory(self, pid=1):
        self.require_player(pid)
        rows = self.sql("SELECT i.obj_uid,i.vnum,COALESCE(parent.obj_uid,0),i.equip_slot "
                        "FROM player_items i LEFT JOIN player_items parent ON parent.id=i.container_id "
                        "WHERE i.pid=" + str(pid) + " ORDER BY i.id")
        values = [list(map(int, line.split('\t'))) for line in rows.splitlines()]
        indices = {row[0]: index for index, row in enumerate(values)}
        for row in values:
            assert not row[2] or row[2] in indices, ("missing persisted parent", row)
            row[2] = indices[row[2]] if row[2] else -1
        return values

    def affects(self, spell, pid=1):
        self.require_player(pid)
        rows = self.sql("SELECT type,duration,flags,modifier FROM player_affects WHERE pid=" +
                        str(pid) + " AND type=" + str(int(spell)) + " ORDER BY id")
        return [list(map(int, line.split('\t'))) for line in rows.splitlines()]

    def pets(self, pid=1):
        self.require_player(pid)
        result = []
        pets = self.sql("SELECT id,COALESCE(pet_uid,0),mob_vnum,hold_reason FROM player_pets WHERE owner_pid=" +
                        str(pid) + " ORDER BY pet_order,id")
        for index, line in enumerate(pets.splitlines()):
            pet_id, uid, vnum, hold = map(int, line.split('\t'))
            result.append([index, uid, vnum, 0, 0, -1, 0, hold])
            rows = self.sql("SELECT i.id,i.obj_uid,COALESCE(e.description,0),"
                            "COALESCE(i.container_id,0),i.equip_slot FROM player_pet_items i "
                            "LEFT JOIN player_pet_item_extra_descr e ON e.item_id=i.id "
                            "AND e.keyword='DURIS_NAMED_SET_ORIGIN_V1' WHERE i.pet_id=" +
                            str(pet_id) + " ORDER BY i.id")
            items = [list(map(int, row.split('\t'))) for row in rows.splitlines()]
            indices = {row[0]: number for number, row in enumerate(items)}
            for item in items:
                assert not item[3] or item[3] in indices, ("missing pet item parent", item)
                result.append([index, uid, vnum, item[1], item[2],
                               indices[item[3]] if item[3] else -1, item[4], hold])
        return result

    def prepare_mortal(self, pid=1):
        self.require_player(pid)
        self.sql("UPDATE player_data SET level=56,highest_level=56,base_hit=1000 WHERE pid=" + str(pid))
        # FIRST_TAG=2001; retain achievements, receipts and cooldowns.
        self.sql("DELETE FROM player_affects WHERE pid=" + str(pid) +
                 " AND (type<2001 OR type IN (2107,2108))")


def main():
    import argparse
    import hashlib
    from pathlib import Path
    import sys
    import tempfile

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compatibility_server", type=Path, help="current MariaDB build with the pinned 115-row catalog")
    parser.add_argument("--resume", type=Path, help="resume a stopped attempt's saved SQL fixture")
    options = parser.parse_args()
    compat = options.compatibility_server.resolve()
    assert compat.is_file(), compat
    if not os.environ.get("TEST_DB_HOST"):
        wrapper = journey.ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(wrapper, [str(wrapper), sys.executable, str(Path(__file__).resolve()), str(compat),
                          *(["--resume", str(options.resume.resolve())] if options.resume else [])])
    runtime = options.resume.resolve() if options.resume else Path(tempfile.mkdtemp(
        prefix="named-set-mariadb-sequence-", dir=journey.ROOT / "bin/tests"))
    assert runtime.is_relative_to((journey.ROOT / "bin/tests").resolve())
    print("Named-set artifacts: " + str(runtime), flush=True)
    if not options.resume:
        journey.make_fixture(runtime)
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
    with journey.mariadb_authority() as (environment, sql):
        environment.update({key: os.environ[key] for key in (
            "TEST_DB_HOST", "TEST_DB_PORT", "TEST_DB_USER", "TEST_DB_PASSWORD")})
        environment.update(NAMED_SET_RUNTIME=str(runtime), NAMED_SET_SERVER=str(journey.ROOT / "bin/server/dms_new"))
        game = NamedSetGame(runtime=runtime, environment=environment)
        evidence = {"binary_sha256": hashlib.sha256(game.binary.read_bytes()).hexdigest(),
                    "compat_binary_sha256": hashlib.sha256(compat.read_bytes()).hexdigest(),
                    "completed": []}
        if options.resume:
            previous = json.loads((runtime / "sequence.json").read_text())
            assert previous["binary_sha256"] == evidence["binary_sha256"]
            assert previous["compat_binary_sha256"] == evidence["compat_binary_sha256"]
            frozen = (runtime / "authority.sql").read_bytes()
            assert hashlib.sha256(frozen).hexdigest() == previous["authority_sha256"]
            sql(frozen.decode())
            evidence["completed"] = previous["completed"]
            evidence["reused"] = list(previous["completed"])
        try:
            if not options.resume:
                game.start("initial-account")
                client = journey.MudClient(game.port)
                game.clients.append(client)
                journey.create_character(client, expected_room=None)
                save(client)
                client.send("quit"); client.expect("ACCOUNT MENU", timeout=30)
                game.stop()
                assert sql("SELECT CONCAT(pid,':',name) FROM player_data") == "1:" + journey.CHARACTER
                game.make_overlord()
            cases = [
                ("transfer", "run_named_set_transfer_journey.py", [str(runtime)]),
                ("edit-clone", "run_named_set_edit_clone_journey.py", []),
                ("pet", "run_named_set_pet_journey.py", []),
                ("shop", "run_named_set_shop_journey.py", []),
                *(("wear-" + str(zone), "run_named_set_wear_journey.py", [str(zone)]) for zone in WEAR_CASES),
                ("rollback", "run_named_set_rollback_journey.py", [str(compat)]),
                ("chest", "run_named_set_mariadb_chest_journey.py", []),
                ("report", "run_named_set_report_journey.py", []),
            ]
            for label, script, arguments in cases:
                if label in evidence["completed"]:
                    continue
                print("Named-set case: " + label, flush=True)
                subprocess.run([sys.executable, str(journey.ROOT / "tests/async" / script), *arguments],
                               cwd=journey.ROOT, env=environment, check=True)
                evidence["completed"].append(label)
                (runtime / "sequence.json").write_text(json.dumps(evidence, indent=2))
            evidence["passed"] = True
            print("Complete named-set SQL sequence passed", flush=True)
        finally:
            game.stop()
            frozen = dump_authority(environment)
            (runtime / "authority.sql").write_bytes(frozen)
            (runtime / "authority.sql").chmod(0o600)
            evidence["authority_sha256"] = hashlib.sha256(frozen).hexdigest()
            (runtime / "sequence.json").write_text(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
