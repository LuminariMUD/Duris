#!/usr/bin/env python3
"""Real-player racewar runner. Connection/provisioning foundation for issue #405.

The operator entry point and combat loop are the next dependent chunk. Nothing
in this module connects or creates accounts merely by importing it.
"""
from __future__ import annotations

import asyncio
import codecs
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets


IAC, DO, DONT, WILL, WONT, SB, SE, GMCP = 255, 253, 254, 251, 252, 250, 240, 201
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_TAIL = re.compile(r"\x1b(?:\[[0-?]*[ -/]*)?\Z")


class BattleError(RuntimeError):
    """An observed admission, protocol or preparation failure."""


class Telnet:
    """Incremental framing: a TCP read is neither a Telnet frame nor a prompt."""

    def __init__(self):
        self.state = "data"
        self.option_command = 0
        self.subnegotiation = bytearray()

    def feed(self, chunk: bytes):
        text, reply, events = bytearray(), bytearray(), []
        for byte in chunk:
            if self.state == "data":
                if byte == IAC:
                    if text:
                        events.append(("text", bytes(text)))
                        text.clear()
                    self.state = "iac"
                else:
                    text.append(byte)
            elif self.state == "iac":
                if byte == IAC:
                    text.append(byte)
                    self.state = "data"
                elif byte in (WILL, WONT, DO, DONT):
                    self.option_command, self.state = byte, "option"
                elif byte == SB:
                    self.subnegotiation.clear()
                    self.state = "subnegotiation"
                else:
                    if byte in (249, 239):  # GA / EOR
                        events.append(("prompt", None))
                    self.state = "data"
            elif self.state == "option":
                if self.option_command == WILL:
                    # Keep GA enabled; refuse compression and unsupported options.
                    reply.extend((IAC, DO if byte == GMCP else DONT, byte))
                elif self.option_command == DO:
                    reply.extend((IAC, WONT, byte))
                self.state = "data"
            elif self.state == "subnegotiation":
                if byte == IAC:
                    self.state = "subnegotiation_iac"
                else:
                    self.subnegotiation.append(byte)
            elif self.state == "subnegotiation_iac":
                if byte == SE:
                    if self.subnegotiation[:1] == bytes((GMCP,)):
                        payload = self.subnegotiation[1:].decode("utf-8")
                        package, _, value = payload.partition(" ")
                        events.append(("gmcp", (package, json.loads(value) if value else None)))
                    self.subnegotiation.clear()
                    self.state = "data"
                elif byte == IAC:
                    self.subnegotiation.append(IAC)
                    self.state = "subnegotiation"
                else:
                    raise BattleError("Invalid Telnet subnegotiation")
            if len(self.subnegotiation) > 1024 * 1024:
                raise BattleError("Oversized Telnet subnegotiation")
        if text:
            events.append(("text", bytes(text)))
        return events, bytes(reply)


class Client:
    """One continuously drained connection; one command waiter per character."""

    def __init__(self, reader, writer, label, run_dir):
        self.reader, self.writer = reader, writer
        self.label, self.run_dir = label, Path(run_dir)
        self.telnet = Telnet()
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.ansi_tail = ""
        self.pending = ""
        self.gmcp = {}
        self.prompts = 0
        self.status_prompt = 0
        self.text_received = 0
        self.prompt_end = 0
        self.changed = asyncio.Event()
        self.command_lock = asyncio.Lock()
        self.error = None
        self.log = None
        self.last_receive = asyncio.get_running_loop().time()
        self.read_task = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls, host, port, label, run_dir):
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), 30)
        return cls(reader, writer, label, run_dir)

    def record(self, kind, value):
        if self.log:
            self.log.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                       "kind": kind, "value": value}) + "\n")
            self.log.flush()

    def begin_gameplay_log(self):
        # Login bytes, email, and credentials never enter gameplay transcripts.
        self.pending = ""
        self.log = (self.run_dir / f"{self.label}.jsonl").open("x", encoding="utf-8")

    async def _read(self):
        try:
            while chunk := await self.reader.read(65536):
                self.last_receive = asyncio.get_running_loop().time()
                events, reply = self.telnet.feed(chunk)
                if reply:
                    self.writer.write(reply)
                    await self.writer.drain()
                # Preserve wire order even when a prompt, GMCP and response text
                # share one read. Counters alone cannot associate a GA with text.
                for kind, value in events:
                    if kind == "text":
                        decoded = self.ansi_tail + self.decoder.decode(value)
                        tail = ANSI_TAIL.search(decoded)
                        self.ansi_tail = decoded[tail.start():] if tail else ""
                        text = ANSI.sub("", decoded[:tail.start()] if tail else decoded).replace("\r", "")
                        if text:
                            self.record("output", text)
                        self.text_received += len(text)
                        # All output goes to disk; idle clients retain only a bounded tail.
                        self.pending = (self.pending + text)[-131072:]
                    elif kind == "gmcp":
                        package, message = value
                        self.gmcp[package] = message
                        if package == "Char.Status":
                            self.status_prompt = self.prompts
                        self.record(package, message)
                    else:
                        self.prompts += 1
                        self.prompt_end = self.text_received
                self.changed.set()
            raise BattleError(f"{self.label}: server closed the connection")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.error = error
            self.record("connection_error", str(error))
            self.changed.set()

    async def send(self, line):
        if "\n" in line or "\r" in line:
            raise BattleError("One input line is required")
        if self.error:
            raise BattleError(f"{self.label}: connection unavailable") from self.error
        self.record("command", line)
        self.writer.write(line.encode("utf-8") + b"\n")
        await self.writer.drain()

    async def wait_for(self, predicate, description, timeout=30):
        async def wait():
            while True:
                self.changed.clear()
                value = predicate()
                if value:
                    return value
                if self.error:
                    raise BattleError(f"{self.label}: disconnected while {description}") from self.error
                await self.changed.wait()
        try:
            return await asyncio.wait_for(wait(), timeout)
        except asyncio.TimeoutError as error:
            # Do not include login buffers: an unexpected server echo may contain secrets.
            raise BattleError(f"{self.label}: timed out {description}") from error

    async def expect(self, *needles, timeout=30):
        def match():
            matches = [(self.pending.lower().find(n.lower()), n) for n in needles]
            matches = [(position, needle) for position, needle in matches if position >= 0]
            if not matches:
                return None
            position, needle = min(matches)
            end = position + len(needle)
            output, self.pending = self.pending[:end], self.pending[end:]
            return needle, output
        return await self.wait_for(match, f"waiting for {needles!r}", timeout)

    async def command(self, line, *, expected=None, timeout=30):
        """Preparation commands only; a prompt alone does not confirm a combat action."""
        async with self.command_lock:
            self.pending = ""
            before = self.prompts
            await self.send(line)
            output = ""
            if expected:
                _, output = await self.expect(expected, timeout=timeout)
            response_end = self.text_received - len(self.pending)
            await self.wait_for(lambda: self.prompts > before and self.prompt_end >= response_end,
                                "waiting for a command prompt", timeout)
            output += self.pending
            self.pending = ""
            return output

    async def close(self):
        self.read_task.cancel()
        await asyncio.gather(self.read_task, return_exceptions=True)
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass
        if self.log:
            self.log.close()
            self.log = None


@dataclass(frozen=True)
class Build:
    race: str
    cls: str


ROSTERS = {
    "good": [Build(*pair) for pair in (
        ("Mountain Dwarf", "Warrior"), ("Barbarian", "Berserker"), ("Human", "Paladin"),
        ("Centaur", "Ranger"), ("Thri-kreen", "Warrior"), ("Human", "Monk"),
        ("Halfling", "Rogue"), ("Minotaur", "Mercenary"), ("Grey Elf", "Bard"),
        ("Githzerai", "Psionicist"), ("Mountain Dwarf", "Cleric"), ("Human", "Cleric"),
        ("Firbolg", "Shaman"), ("Grey Elf", "Druid"), ("Gnome", "Sorcerer"),
        ("Human", "Conjurer"), ("Halfling", "Illusionist"), ("Githzerai", "Ethermancer"),
        ("Grey Elf", "Summoner"), ("Tiefling", "Dragoon"))],
    "evil": [Build(*pair) for pair in (
        ("Thri-kreen", "Warrior"), ("Duergar", "Berserker"), ("Troll", "Mercenary"),
        ("Orc", "Anti-Paladin"), ("Githyanki", "Monk"), ("Drow Elf", "Rogue"),
        ("Goblin", "Reaver"), ("Kobold", "Bard"), ("Drow Elf", "Cleric"),
        ("Duergar", "Cleric"), ("Ogre", "Shaman"), ("Githyanki", "Psionicist"),
        ("Drider", "Blighter"), ("Kobold", "Sorcerer"), ("Drow Elf", "Necromancer"),
        ("Githyanki", "Conjurer"), ("Goblin", "Illusionist"), ("Tiefling", "Ethermancer"),
        ("Drow Elf", "Summoner"), ("Minotaur", "Mercenary"))],
}


def roster(side, count):
    if not isinstance(count, int) or count < 1:
        raise BattleError(f"Invalid {side} group cap: {count!r}")
    candidates = ROSTERS[side]
    if count < len(candidates):
        core = [0, 10, 14] if side == "good" else [0, 8, 13]
        order = core + [i for i in range(len(candidates)) if i not in core]
        return [candidates[i] for i in order[:count]]
    return [candidates[i % len(candidates)] for i in range(count)]


def normalized(value):
    return re.sub(r"[^a-z]", "", value.lower())


def choose_menu(menu, desired, *, race=False, alternatives=()):
    pattern = r"\(([a-z0-9])\)\s*([^\r\n|()]+)" if race else r"(?m)^\s*([a-z0-9])\)\s*([^\r\n()]+)"
    choices = [(key, label.strip()) for key, label in re.findall(pattern, menu)]
    for wanted in (desired, *alternatives):
        for key, label in choices:
            if normalized(label).startswith(normalized(wanted)):
                return key, label
    raise BattleError(f"No offered choice for {desired}; available: {', '.join(label for _, label in choices)}")


def fresh_name():
    return "Ra" + "".join(secrets.choice("bdfgklmnprstv") + secrets.choice("aeiou") for _ in range(4))


class AccountPool:
    """Reusable dedicated accounts; every invocation records fresh characters."""

    def __init__(self, path, email):
        self.path, self.email = Path(path), email
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"good": [], "evil": []}
        seen = set()
        for side in ROSTERS:
            for entry in self.data[side]:
                name = entry["account"].casefold()
                if not name or not entry["password"] or name in seen:
                    raise BattleError("Dedicated accounts must have credentials and distinct names")
                seen.add(name)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(self.data, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, self.path)

    def account(self, side, index):
        while len(self.data[side]) <= index:
            self.data[side].append({"account": fresh_name(), "password": "Rw7!" + secrets.token_hex(10),
                                    "email": self.email, "characters": []})
        entry = self.data[side][index]
        character = fresh_name()
        entry.setdefault("characters", []).append(character)
        self.save()  # credentials and intent survive a failure during registration
        return entry, character


async def account_login(client, account, *, create):
    match, _ = await client.expect("term type", "account name")
    if match == "term type":
        await client.send("9")
        await client.expect("account name")
    await client.send(account["account"])
    match, _ = await client.expect("is this correct?", "enter your password")
    if match == "is this correct?":
        if not create:
            raise BattleError("The configured staff account does not exist")
        await client.send("y")
        await client.expect("email address")
        await client.send(account["email"])
        await client.expect("is this correct?")
        await client.send("y")
        await client.expect("enter your password")
        await client.send(account["password"])
        await client.expect("re-enter the same password")
        await client.send(account["password"])
        await client.expect("information correct?")
        await client.send("y")
    else:
        await client.send(account["password"])
    match, output = await client.expect("PRESS RETURN", "Please enter the confirmation code shown above:")
    if match != "PRESS RETURN":
        code = re.search(r"Your confirmation code is:\s*(\S+)", output)
        if not code:
            raise BattleError(f"{client.label}: account confirmation needs operator input")
        await client.send(code[1])
        await client.expect("PRESS RETURN")
    await client.send("")
    await client.expect("Please select an option")


async def staff_login(client, account):
    await account_login(client, account, create=False)
    await client.send("1")
    await client.expect(account["character"])
    await client.send(account["character"])
    match, _ = await client.expect("Play as", "Reconnecting...", "Overriding old connection...")
    if match == "Play as":
        await client.send("y")
    await client.wait_for(lambda: client.gmcp.get("Char.Status", {}).get("name", "").lower() == account["character"].lower()
                          and client.prompts > client.status_prompt,
                          "waiting for staff entry")
    if client.gmcp["Char.Status"].get("level", 0) < 62:
        raise BattleError("The controller must be an Overlord for battleprep")
    client.begin_gameplay_log()
    await disable_paging(client)


async def disable_paging(client):
    settings = await client.command("toggle", expected="Paging")
    state = re.search(r"Paging\s*:\s*(ON|OFF)", settings)
    if not state:
        raise BattleError(f"{client.label}: cannot read paging state")
    if state[1] == "ON":
        await client.command("toggle paging", expected="Paging mode off.")


async def create_character(client, account, character, side, build):
    await account_login(client, account, create=True)
    await client.send("2")
    await client.expect("Enter your new name")
    await client.send(character)
    match, _ = await client.expect("Is this correct?", "maximum number of characters")
    if match != "Is this correct?":
        raise BattleError(f"Account {account['account']} is full; supply another dedicated account")
    await client.send("y")
    await client.expect("meet these criteria?")
    await client.send("y")
    _, menu = await client.expect("Your selection")
    alternatives = [entry.race for entry in ROSTERS[side]]
    key, race = choose_menu(menu, build.race, race=True, alternatives=alternatives)
    await client.send(key)
    await client.expect("Male or Female")
    await client.send("m")
    await client.expect("Hardcore")
    await client.send("n")
    _, menu = await client.expect("Your selection")
    role_alternatives = ("Cleric", "Shaman") if build.cls in ("Cleric", "Shaman") else ("Warrior", "Sorcerer")
    key, cls = choose_menu(menu, build.cls, alternatives=role_alternatives)
    await client.send(key)
    match, text = await client.expect("Alignment only affects", "Hometown Selection", "Your stat rolling system [D]:")
    if match == "Alignment only affects":
        _, tail = await client.expect("Your selection")
        choices = text + tail
        # Neutral races choose their initial side through the native alignment flow.
        alignment = "g" if side == "good" else "e"
        if not re.search(rf"(?i)\b{alignment}\)", choices):
            alignment = "n"
        await client.send(alignment)
        match, _ = await client.expect("Hometown Selection", "Your stat rolling system [D]:")
    if match == "Hometown Selection":
        _, menu = await client.expect("Your selection")
        homes = re.findall(r"(?m)^\s*([A-Za-z0-9])\)([^\r\n]+)", menu)
        if not homes:
            raise BattleError(f"{character}: no hometown offered")
        key = next((key for key, name in homes if "Beginner Introduction" in name), homes[0][0])
        await client.send(key)
        await client.expect("Your stat rolling system [D]:")
    await client.send("")
    for label, stat in zip(("first bonus", "second bonus", "third bonus", "fourth bonus"), "sdal"):
        await client.expect(label)
        await client.send(stat)
    await client.expect("swap stats")
    await client.send("n")
    await client.expect("keep this character")
    await client.send("y")
    await client.expect("PRESS RETURN")
    await client.send("")
    await client.expect("Your starter kit is ready", timeout=60)
    await client.wait_for(lambda: client.gmcp.get("Char.Status", {}).get("name", "").lower() == character.lower()
                          and client.prompts > client.status_prompt,
                          "waiting for character entry")
    client.begin_gameplay_log()
    await disable_paging(client)
    return Build(race, cls)


async def connect_roster(host, port, pool, run_dir):
    """Create both full rosters, reading independent caps from their live leaders.

    The caller owns all returned connections. Failure closes every connection and
    preserves the pool; it never reports a partial roster as ready.
    """
    clients, rows, caps = {}, {}, {}
    admission = asyncio.Semaphore(4)  # below the native eight simultaneous login limit

    def record_roster():
        (Path(run_dir) / "roster.json").write_text(json.dumps([rows[key] for key in sorted(rows)], indent=2))

    async def create(side, index, build):
        async with admission:
            account, name = pool.account(side, index)
            rows[(side, index)] = {"name": name, "account": account["account"], "side": side,
                                   "index": index, "requested_race": build.race,
                                   "requested_class": build.cls, "status": "creating"}
            record_roster()
            try:
                client = await Client.connect(host, port, name, run_dir)
                clients[name] = client
                actual = await create_character(client, account, name, side, build)
                rows[(side, index)].update(race=actual.race, **{"class": actual.cls, "status": "connected"})
                await client.command("group")
                group = await client.wait_for(lambda: client.gmcp.get("Group.Status"), "reading group cap")
                if index == 0:
                    caps[side] = group["maxSize"]
            except Exception as error:
                rows[(side, index)].update(status="failed", error=str(error))
                raise
            finally:
                record_roster()

    async def batch(jobs):
        tasks = [asyncio.create_task(job) for job in jobs]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    try:
        await batch(create(side, 0, ROSTERS[side][0]) for side in ROSTERS)
        await batch(create(side, index, build) for side in ROSTERS
                    for index, build in enumerate(roster(side, caps[side])) if index)
        return clients, [rows[key] for key in sorted(rows)], caps
    except BaseException:
        await asyncio.gather(*(client.close() for client in clients.values()), return_exceptions=True)
        raise


async def current_room(staff):
    # Room.Info intentionally hides wilderness VNUMs even from this normal
    # protocol. Existing staff stat supplies the actual configurable location.
    output = await staff.command("stat room", expected="Room: [")
    match = re.search(r"Room:\s*\[(\d+)\]", output)
    if not match:
        raise BattleError("Could not read the controller's room VNUM")
    return int(match[1])


async def place_groups(staff, clients, rows, caps, room):
    """Transfer named participants, check actual sides, and group by consent."""
    if await current_room(staff) != room:
        await staff.command(f"goto {room}")
        if await current_room(staff) != room:
            raise BattleError(f"The controller could not enter room {room}")
    for row in rows:
        name = row["name"]
        await staff.command(f"transfer {name}")
        output = await staff.command(f"stat char {name}", expected="In room:")
        location = re.search(r"In room:\s*\[(\d+)\]", output)
        side = re.search(r"Racewar:\s*(\w+)", output)
        if not location or int(location[1]) != room or not side or side[1].lower() != row["side"]:
            raise BattleError(f"{name}: location or racewar side differs from the requested roster")
    for side in ROSTERS:
        party = sorted((row for row in rows if row["side"] == side), key=lambda row: row["index"])
        leader_name = party[0]["name"]
        leader = clients[leader_name]
        for row in party[1:]:
            await clients[row["name"]].command(f"consent {leader_name}")
            await leader.command(f"group {row['name']}", expected="is now a member of your group")
        await leader.command("group")
        expected_names = {row["name"].casefold() for row in party}

        def complete():
            group = leader.gmcp.get("Group.Status", {})
            members = group.get("members", [])
            return (group.get("size") == caps[side] and group.get("maxSize") == caps[side]
                    and {m["name"].casefold() for m in members} == expected_names
                    and all(not m["isNpc"] and m["inRoom"] for m in members))

        await leader.wait_for(complete, f"verifying full {side} group")
        # Native rank commands currently return without changing ranks. Preserve
        # the server's default ranks; don't revive that disabled game mechanic.
    return room
