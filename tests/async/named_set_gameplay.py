"""Shared native I/O for the named-set wear and cross-owner journeys."""

import json
import os
import re
import subprocess
import time
import test_flatfile_combat_journey as journey


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
    client.expect("Save complete for " + name + ".", timeout=30)


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


class NamedSetGame:
    def __init__(self, runtime=None, binary=None):
        self.runtime = (runtime or journey.ROOT / "bin/tests/named-set-roster-world").resolve()
        self.binary = (binary or journey.ROOT / "bin/tests/named-set-flatfile-server").resolve()
        self.state = self.runtime / "state"
        assert self.state.is_dir() and (self.runtime / "areas/world.zon").is_file(), (
            "prepare the isolated full-world runtime first"
        )
        self.fixture = journey.ROOT / "bin/tests/named-set-journey-fixture"
        subprocess.run(
            [
                "g++",
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Isrc",
                "tests/async/named_set_journey_fixture.cpp",
                "src/player/player_snapshot_codec.c",
                "src/flatfile/flatfile_player_snapshot_file.c",
                "src/flatfile/flatfile_store.c",
                "-lcrypto",
                "-o",
                str(self.fixture),
            ],
            cwd=journey.ROOT,
            check=True,
        )
        self.port, tls, websocket = journey.available_ports()
        self.env = dict(
            PATH=os.environ.get("PATH", "/usr/bin:/bin"),
            ENVIRONMENT="local",
            PERSISTENCE_MODE="flatfile-primary",
            FLATFILE_STATE_DIR=str(self.state),
            CRITICAL_COMMAND_JOURNAL_DIR=str(self.runtime / "journals/critical"),
            LISTEN_ADDRESS="127.0.0.1",
            DURIS_TLS_PORT=str(tls),
            DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
            DURIS_WEBSOCKET_PORT=str(websocket),
            REDIS="FALSE",
            CHAOS_MUD="FALSE",
        )
        if os.environ.get("LD_LIBRARY_PATH"):
            self.env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        self.process = self.output = None
        self.clients = []
        self.transcripts = []

    def boot(self, label, *, account=journey.ACCOUNT, character=journey.CHARACTER):
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

    def read(self, mode, pid=1):
        return subprocess.check_output(
            [str(self.fixture), str(self.state), mode, str(pid)], text=True
        )

    def items(self, pid=1):
        return [line.split("|", 6) for line in self.read("inspect", pid).splitlines()]

    def inventory(self, pid=1):
        return [
            list(map(int, line.split("|")))
            for line in self.read("inventory", pid).splitlines()
        ]

    def affects(self, spell, pid=1):
        return [
            list(map(int, line.split("|")))
            for line in self.read("affects", pid).splitlines()
            if line.startswith(str(spell) + "|")
        ]

    def pets(self, pid=1):
        return [
            list(map(int, line.split("|")))
            for line in self.read("pets", pid).splitlines()
        ]

    def prepare_mortal(self, pid=1):
        subprocess.run(
            [str(self.fixture), str(self.state), "mortal", str(pid)], check=True
        )
