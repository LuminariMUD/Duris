#!/usr/bin/env python3
"""Prepare and drive one watchable racewar battle through real player connections."""
from __future__ import annotations

import asyncio
import argparse
import codecs
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import signal
import sys


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
        self.versions = {}
        self.receipt_text = 0
        self.receipt_prompt = 0
        self.damage_events = 0
        self.observed_damage = 0
        self.dead = False
        self.healing_events = 0
        self.observed_healing = 0
        self.evidence_tail = ""
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
                        evidence = self.evidence_tail + text
                        for healing in re.finditer(r"\[Heal:\s*(\d+)\s*\]", evidence):
                            if healing.end() > len(self.evidence_tail):
                                self.healing_events += 1
                                self.observed_healing += int(healing[1])
                        self.evidence_tail = evidence[-256:]
                        self.text_received += len(text)
                        # All output goes to disk; idle clients retain only a bounded tail.
                        self.pending = (self.pending + text)[-131072:]
                        if "Your wounds claim you at last. Your spirit slips free of your body" in evidence:
                            self.dead = True
                    elif kind == "gmcp":
                        package, message = value
                        self.gmcp[package] = message
                        self.versions[package] = self.versions.get(package, 0) + 1
                        if package == "Char.Input":
                            self.receipt_text = self.text_received
                            self.receipt_prompt = self.prompts
                        if package == "Combat.Update" and message.get("round", {}).get("damage", 0) > 0:
                            self.damage_events += 1
                            self.observed_damage += message["round"]["damage"]
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
        """Serialize input; opt-in receipts bind gameplay output to actual dequeue."""
        async with self.command_lock:
            self.pending = ""
            before = self.prompts
            sequence = self.gmcp.get("Char.Input", {}).get("sequence")
            await self.send(line)
            if sequence is not None:
                await self.wait_for(lambda: self.gmcp["Char.Input"]["sequence"] > sequence,
                                    "waiting for input dequeue", timeout)
                if self.gmcp["Char.Input"]["sequence"] != sequence + 1:
                    raise BattleError(f"{self.label}: unexpected input sequence")
                keep = self.text_received - self.receipt_text
                self.pending = self.pending[-keep:] if keep else ""
                before = self.receipt_prompt
            output = ""
            if expected:
                needles = (expected,) if isinstance(expected, str) else expected
                _, output = await self.expect(*needles, timeout=timeout)
            response_end = self.text_received - len(self.pending)
            await self.wait_for(lambda: self.prompts > before and self.prompt_end >= response_end,
                                "waiting for a command prompt", timeout)
            if sequence is not None and re.search(r"You start chanting|You begin to focus your will", output + self.pending):
                await self.wait_for(lambda: re.search(
                    r"You complete your spell|Your mental manipulations become a reality|"
                    r"You abort your|You lost your concentration|gathers?, then fade|"
                    r"lose your concentration|You don't have a valid target", output + self.pending),
                    "waiting for native cast completion or interruption", timeout=60)
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

    async def enable_receipts(self):
        before = self.versions.get("Char.Input", 0)
        payload = b'Core.Hello {"client":"racewar-runner","commandReceipts":true}'
        self.writer.write(bytes((IAC, SB, GMCP)) + payload + bytes((IAC, SE)))
        await self.writer.drain()
        await self.wait_for(lambda: self.versions.get("Char.Input", 0) > before,
                            "negotiating native input receipts", timeout=10)

    async def action(self, line):
        """One outstanding input; native receipts, not combat prompts, bound the queue."""
        if "Char.Input" not in self.gmcp:
            raise BattleError(f"{self.label}: native input receipts are required")
        started = asyncio.get_running_loop().time()
        output = await self.command(line, timeout=90)
        completed = bool(re.search(r"You complete your spell|Your mental manipulations become a reality", output))
        self.record("action_result", {"command": line, "dequeued": True,
            "spell_completed": completed, "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
            "response_tail": output[-2000:]})
        return output


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

# Small explicit loadouts, validated by native memorize/pray admission. Resource
# models that cast from mana or circle slots need no prepared-copy inventory.
SPELL_LOADOUTS = {
    "paladin": ("armor", "heal"),
    "antipaladin": ("cause critical", "harm"),
    "cleric": ("full heal", "harm"),
    "shaman": ("greater mending", "scathing wind"),
    "sorcerer": ("magic missile", "prismatic ray"),
    "conjurer": ("magic missile", "fireball"),
    "summoner": ("magic missile", "prismatic ray"),
    "illusionist": ("magic missile", "stunning visions"),
    "necromancer": ("slashing darkness", "energy drain"),
    "reaver": ("magic missile", "chill touch"),
    "psionicist": ("ego whip", "psychic crush"),
    "druid": ("barkskin", "lightning bolt"),
    "ranger": ("barkskin",),
    "ethermancer": ("ice missile", "ice storm"),
    "blighter": ("acid blast", "harm"),
}
BOOK_CLASSES = {"sorcerer", "conjurer", "necromancer", "illusionist", "bard", "summoner", "reaver"}
PRAYING_CLASSES = {"cleric", "paladin", "antipaladin"}
SLOT_RECOVERY = {"ranger": "commune", "druid": "commune", "dragoon": "commune",
                 "blighter": "deforest", "ethermancer": "tupor"}


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
    # Alternating letters avoid doubled-consonant filter words; omitting p also
    # prevents the remaining rude substring observed in a generated name.
    return "Ra" + "".join(secrets.choice("bdfgklmnrstv") + secrets.choice("aeiou") for _ in range(4))


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
    match, _ = await client.expect("is this correct?", "enter your password", "Illegal account name")
    if match == "Illegal account name":
        raise BattleError(f"{client.label}: server rejected the dedicated account name")
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
    match, _ = await client.expect("Is this correct?", "maximum number of characters",
        "Illegal character name", "name has been declined", "Name is in use already",
        "not allowing creation", "New characters have been banned", "Game is temporarily full")
    if match == "maximum number of characters":
        raise BattleError(f"Account {account['account']} is full; supply another dedicated account")
    if match != "Is this correct?":
        raise BattleError(f"{character}: character admission rejected: {match}")
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
    await client.expect("Your starter kit is ready", "Your Chaos Equipment has been prepared!!", timeout=60)
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
        # Native rank commands currently return without changing ranks. Preserve
        # the server's default ranks; don't revive that disabled game mechanic.
    await refresh_groups(clients, rows, caps)
    return room


async def refresh_groups(clients, rows, caps):
    """Read live membership; level changes alone do not refresh cached Group.Status."""
    groups = {}
    for side in caps:
        party = [row for row in rows if row["side"] == side]
        leader = clients[next(row["name"] for row in party if row["index"] == 0)]
        leader.gmcp.pop("Group.Status", None)
        await leader.command("group")
        group = await leader.wait_for(lambda: leader.gmcp.get("Group.Status"), "reading live group membership")
        members = group.get("members", [])
        if (group.get("size") != caps[side] or group.get("maxSize") != caps[side] or
            {m["name"].casefold() for m in members} != {row["name"].casefold() for row in party} or
            not all(not m["isNpc"] and m["inRoom"] for m in members)):
            raise BattleError(f"The {side} group is no longer full and present")
        expected_levels = {row["name"].casefold(): row["level"] for row in party if "level" in row}
        if any(m["name"].casefold() in expected_levels and m["level"] != expected_levels[m["name"].casefold()]
               for m in members):
            raise BattleError(f"The {side} group's live levels differ from preparation")
        groups[side] = group
    return groups


async def prepare_fighters(staff, clients, rows, run_dir):
    """Prepare fresh PCs using existing grant/equip/book/restoration commands."""
    path = Path(run_dir) / "preparation.json"
    for row in rows:
        name = row["name"]
        player = clients[name]
        cls = normalized(row["class"])
        row["preparation"] = "preparing"
        try:
            # Only these newly created identities are reconciled. Ordinary drops
            # preserve native starter-item and ownership behavior; no purge/wipe.
            # Grant before advancement: its asynchronous achievement rewards
            # must not race the Chaos grant's empty-inventory admission check.
            await player.command("remove all", expected=("You stop using", "You are quite naked"))
            await player.command("drop all", expected=("You drop", "You do not seem to have anything", "You can't drop"))
            deadline = asyncio.get_running_loop().time() + 30
            while True:
                inventory = await player.command("inventory", expected="You are carrying:")
                count = re.search(r"You are carrying:\s*\((\d+)/", inventory)
                if count and int(count[1]) == 0:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise BattleError(f"{name}: starting inventory did not clear through normal drops")
                await asyncio.sleep(.25)
            player.pending = ""
            grant = await staff.command(f"chaos kit {name}", expected=("Chaos equipment restoration queued.",
                "Chaos equipment could not be restored", "That character has items", "already has equipment"))
            if "Chaos equipment restoration queued." not in grant:
                raise BattleError(f"{name}: CHAOS grant rejected: {grant.strip()}")
            await player.expect("Your Chaos Equipment has been prepared!!", timeout=60)
            baseline = await staff.command(f"battleprep {name} baseline", expected=f"{name} baseline ready")
            cap = re.search(r"baseline ready at level (\d+)", baseline)
            if not cap:
                raise BattleError(f"{name}: native baseline did not report its level")
            checked = await staff.command(f"battleprep {name} equip", expected=f"Battleprep: {name} equipment")
            if f"{name} equipment ready." not in checked:
                raise BattleError(f"{name}: CHAOS loadout incomplete: {checked.strip()}")
            row["equipment"] = await player.command("equipment")
            if cls in BOOK_CLASSES:
                inventory = await player.command("inventory", expected="You are carrying:")
                if "master spellbook" not in inventory:
                    await staff.command("load obj 7", expected="master spellbook")
                    await staff.command(f"give master {name}")
                    inventory = await player.command("inventory", expected="master spellbook")
                row["master_book"] = "master spellbook" in inventory
            spells = SPELL_LOADOUTS.get(cls, ())
            row["selected_spells"] = list(spells)
            if spells and (cls in BOOK_CLASSES or cls == "shaman" or cls in PRAYING_CLASSES):
                recovery = "pray" if cls in PRAYING_CLASSES else "memorize"
                await player.command("rest")
                for _ in range(2):
                    for spell in spells:
                        output = await player.command(f"{recovery} {spell}")
                        if not re.search(rf"You are (?:memorizing|praying for) {re.escape(spell)}\b", output):
                            raise BattleError(f"{name}: {spell} was not queued: {output.strip()}")
                await staff.command(f"battleprep {name} spells", expected="newly prepared spells.")
                listing = await player.command(recovery, expected="You have memorized")
                if any(not re.search(rf"\b2 - {re.escape(spell)}\b", listing) for spell in spells):
                    raise BattleError(f"{name}: selected prepared spell counts did not match")
                row["prepared_spells"] = {spell: 2 for spell in spells}
                await player.command("stand")
            await player.command("toggle wimpy 0")
            await staff.command(f"restore {name}", expected="Done.")
            if cls in SLOT_RECOVERY:
                listing = await player.command(SLOT_RECOVERY[cls], expected="spell slots available:")
                slots = re.findall(r"(\d+)(?:st|nd|rd|th) circle:\s*(\d+) of\s*(\d+)", listing)
                if len(slots) != 12 or any(current != maximum for _, current, maximum in slots):
                    raise BattleError(f"{name}: native spell slots are not full")
                row["spell_slots"] = {circle: int(current) for circle, current, _ in slots}
            score = await player.command("score", expected="Hit points:")
            level = re.search(r"Level:\s*(\d+)", score)
            if not level or level[1] != cap[1]:
                raise BattleError(f"{name}: score does not match the prepared level")
            row["level"] = int(level[1])
            resources = re.findall(r"(Hit points|Mana|Moves):\s*(\d+)\s*\(\s*(\d+)\)", score)
            if not resources or any(current != maximum for _, current, maximum in resources):
                raise BattleError(f"{name}: native score does not show full starting resources")
            row["starting_resources"] = {resource: int(current) for resource, current, _ in resources}
            row["vitals"] = player.gmcp["Char.Vitals"]
            await player.command("save", expected=f"Save complete for {name}.")
            row["preparation"] = "ready"
            print(f"Prepared {row['side']} {row['index'] + 1}: {row['race']} {row['class']} ({name})", flush=True)
        except Exception as error:
            row["preparation"] = "failed"
            row["error"] = str(error)
            raise
        finally:
            path.write_text(json.dumps(rows, indent=2))


HEALS = {"cleric": "full heal", "shaman": "greater mending", "paladin": "heal"}
BUFFS = {"paladin": "armor", "ranger": "barkskin", "druid": "barkskin"}
PHYSICAL = {"warrior": "bash", "berserker": "berserk", "monk": "kick",
            "mercenary": "kick", "rogue": "circle", "ranger": "kick", "dragoon": "kick"}
DEPLETED = re.compile(r"don't have that spell memorized|must commune with nature more|"
                      r"don't have the energy left|lucidity is not sufficient enough|"
                      r"power reserves are not sufficient|illumination is not sufficient", re.I)
REJECTED = re.compile(r"You (?:can't|cannot|don't|aren't|are unable)|not here|no one|"
                      r"Nobody|not permitted|not allowed|can't do|peaceful|harmful magic|"
                      r"haven't regained|Uh oh|lost your concentration|You abort", re.I)


def room_identity(player):
    info = player.gmcp.get("Room.Info", {})
    # Wilderness VNUMs can be hidden; coordinates still identify the location.
    return {key: info.get(key) for key in ("num", "name", "coords")}


async def prepare_actions(staff, clients, rows, directory):
    for row in rows:
        player, cls = clients[row["name"]], normalized(row["class"])
        if cls in HEALS or cls == "bard":
            settings = await player.action("toggle")
            state = re.search(r"\bHeal\s*:\s*(ON|OFF)", settings)
            if not state:
                raise BattleError(f"{player.label}: cannot read healing-output setting")
            if state[1] == "OFF":
                await player.action("toggle heal")
        if cls == "bard":
            # Support items are inside the native Chaos bag. Both profiles' lyres
            # can be held; the standard one cannot be attached to a belt.
            result = await player.action("get lyre illithids")
            if "You get" not in result:
                raise BattleError(f"{player.label}: could not retrieve the kit's healing lyre")
            await player.action("remove shield")
            result = await player.action("hold lyre")
            if "You hold" not in result:
                raise BattleError(f"{player.label}: could not hold the kit's healing lyre")
            checked = await staff.command(f"battleprep {player.label} equipment", expected=f"{player.label} equipment")
            if "equipment ready." not in checked:
                raise BattleError(f"{player.label}: instrument setup left the kit incomplete")
            row["equipment"] = await player.action("equipment")
            row["support"] = "play healing"
        if cls in BUFFS:
            result = await player.action(f"cast '{BUFFS[cls]}' {player.label}")
            if "You complete your spell" not in result:
                raise BattleError(f"{player.label}: pre-fight {BUFFS[cls]} did not complete")
            row["buff"] = BUFFS[cls]
        row["battle_room"] = room_identity(player)
    # One agreed restoration after buffs, never during combat. Prepared copies
    # retain native consumption; the attack/healing loadout was not spent here.
    for row in rows:
        await staff.command(f"restore {row['name']}", expected="Done.")
        await clients[row["name"]].command("save", expected=f"Save complete for {row['name']}.")
    (Path(directory) / "preparation.json").write_text(json.dumps(rows, indent=2))


def active(row, clients):
    player = clients[row["name"]]
    return not player.dead and not player.error and room_identity(player) == row["battle_room"]


def choose_enemy(row, rows, clients):
    player = clients[row["name"]]
    available = {entry["name"].casefold(): entry.get("target")
                 for entry in player.gmcp.get("Room.Info", {}).get("players", [])}
    enemies = [r for r in rows if r["side"] != row["side"] and active(r, clients)
               and available.get(r["name"].casefold())]
    current = player.gmcp.get("Char.Vitals", {}).get("fighting")
    if not enemies:
        return None
    target = next((r for r in enemies if r["name"] == current), enemies[row["index"] % len(enemies)])
    return target, available[target["name"].casefold()]


async def fight_one(row, rows, clients, stop):
    player, cls = clients[row["name"]], normalized(row["class"])
    spent, turn = set(), 0
    row["actions"] = {"attempted": 0, "dequeued": 0, "spells_completed": 0, "rejected": 0}
    while not stop.is_set() and active(row, clients):
        enemy = choose_enemy(row, rows, clients)
        if not enemy:
            await asyncio.sleep(.25)
            continue
        _, selector = enemy
        vitals = player.gmcp.get("Char.Vitals", {})
        if vitals.get("hp", 0) <= 0:
            await asyncio.sleep(.5)
            continue
        heal = HEALS.get(cls)
        injured = [r for r in rows if r["side"] == row["side"] and active(r, clients)
                   and 0 < clients[r["name"]].gmcp.get("Char.Vitals", {}).get("hp", 0)
                   < .85 * clients[r["name"]].gmcp.get("Char.Vitals", {}).get("maxHp", 0)]
        spell = None
        if vitals.get("position") != "standing":
            command = "stand"
        elif heal and heal not in spent and injured:
            target = min(injured, key=lambda r: clients[r["name"]].gmcp["Char.Vitals"]["hp"] /
                         max(1, clients[r["name"]].gmcp["Char.Vitals"]["maxHp"]))
            spell = heal
            command = f"cast '{heal}' {target['name']}"
        elif cls == "bard" and turn % 3 == 0:
            command = "play healing"
        else:
            attacks = [s for s in SPELL_LOADOUTS.get(cls, ())
                       if s not in spent and s != heal and s != BUFFS.get(cls)]
            if attacks:
                spell = attacks[turn % len(attacks)]
                verb = "will" if cls == "psionicist" else "cast"
                command = f"{verb} '{spell}' {selector}"
            elif not vitals.get("fighting"):
                command = f"kill {selector}"
            elif cls in PHYSICAL or cls == "bard":
                skill = PHYSICAL.get(cls, "kick")
                command = skill if skill == "berserk" else f"{skill} {selector}"
            else:
                # The third caster choice is native melee after exhaustion;
                # don't grow an extra ability rotation beyond the small loadout.
                await asyncio.sleep(1)
                continue
        row["actions"]["attempted"] += 1
        output = await player.action(command)
        row["actions"]["dequeued"] += 1
        if "You complete your spell" in output or "Your mental manipulations become a reality" in output:
            row["actions"]["spells_completed"] += 1
        if REJECTED.search(output):
            row["actions"]["rejected"] += 1
        if spell and DEPLETED.search(output):
            spent.add(spell)
            player.record("resource_exhausted", spell)
        turn += 1
        await asyncio.sleep(.5)


async def stop_fighters(staff, rows):
    """Stop exact identities and observe them again after native callbacks settle."""
    result = {"confirmed": False, "statuses": {}, "settle_seconds": 6}
    try:
        for operation, delay in (("stop", 0), ("status", 1), ("status", 5)):
            await asyncio.sleep(delay)
            for offset in range(0, len(rows), 8):
                names = [row["name"] for row in rows[offset:offset + 8]]
                if not names:
                    continue
                output = await staff.command(f"battleprep {operation} {' '.join(names)}",
                                             expected=f"Battleprep status {names[-1]}")
                statuses = {name.casefold(): state for name, state in
                            re.findall(r"Battleprep status (\w+) (\w+)\.", output)}
                for name in names:
                    state = statuses.get(name.casefold(), "unconfirmed")
                    result["statuses"][name] = state
                    if state != "quiet":
                        result.setdefault("unresolved", []).append({"name": name, "operation": operation, "state": state})
        result["confirmed"] = not result.get("unresolved")
    except Exception as error:
        result["error"] = str(error)
    return result


async def run_combat(staff, clients, rows, caps, stop, duration):
    started = asyncio.get_running_loop().time()
    tasks = [asyncio.create_task(fight_one(row, rows, clients, stop)) for row in rows]
    result = {"outcome": "time_limit", "caps": caps}
    response_times = []

    async def responsiveness():
        while True:
            before = asyncio.get_running_loop().time()
            await current_room(staff)
            elapsed = round(1000 * (asyncio.get_running_loop().time() - before), 2)
            response_times.append(elapsed)
            staff.record("controller_response_ms", elapsed)
            await asyncio.sleep(2)

    probe = asyncio.create_task(responsiveness())
    try:
        while asyncio.get_running_loop().time() - started < duration:
            if stop.is_set():
                result["outcome"] = "operator_stop"
                break
            for task in tasks:
                if task.done() and not task.cancelled() and task.exception():
                    raise task.exception()
            if probe.done() and probe.exception():
                raise probe.exception()
            if any(not any(r["side"] == side and active(r, clients) for r in rows) for side in caps):
                result["outcome"] = "side_eliminated_or_withdrawn"
                break
            await asyncio.sleep(.25)
    except Exception as error:
        result.update(outcome="interrupted", error=str(error))
    finally:
        for task in tasks:
            task.cancel()
        probe.cancel()
        await asyncio.gather(*tasks, probe, return_exceptions=True)
        result["duration_seconds"] = round(asyncio.get_running_loop().time() - started, 2)
        result["controller_response_ms"] = {"samples": response_times,
            "max": max(response_times, default=None),
            "median": sorted(response_times)[len(response_times) // 2] if response_times else None,
            "measurement": "end-to-end staff stat-room response, includes network and scheduling"}
        result["stop"] = await stop_fighters(staff, rows)
        for row in rows:
            player = clients[row["name"]]
            row.update(dead=player.dead, disconnected=bool(player.error),
                       left_battlefield=room_identity(player) != row["battle_room"],
                       damage_events=player.damage_events, observed_damage=player.observed_damage,
                       healing_events=player.healing_events, observed_healing=player.observed_healing)
            row["final_save"] = "not attempted: disconnected or stop unconfirmed"
            if not player.error and result["stop"]["confirmed"]:
                try:
                    await player.command("save", expected=f"Save complete for {row['name']}.")
                    row["final_save"] = "acknowledged"
                except Exception as error:
                    row["final_save"] = str(error)
        result["rows"] = rows
    return result


async def operate(config, accounts, directory, room, duration, commands):
    """One invocation, one fresh roster, explicit start, then a verified stop."""
    staff = await Client.connect(config["host"], config["port"], "controller", directory)
    clients, rows, caps = {}, [], {}
    stop, start = asyncio.Event(), asyncio.Event()
    phase = "connecting"
    result = {"outcome": "preparation_failed"}

    async def control():
        while True:
            command = (await commands.get()).strip().lower()
            if command == "start":
                start.set()
            elif command == "stop":
                stop.set()
                return
            elif command == "status":
                print(json.dumps({"phase": phase, "caps": caps, "connected": len(clients),
                                  "dead": sum(p.dead for p in clients.values())}), flush=True)
            else:
                print("Controls: start, status, stop", flush=True)

    controls = asyncio.create_task(control())
    stopping = asyncio.create_task(stop.wait())

    async def until_stop(work):
        task = asyncio.create_task(work)
        try:
            done, _ = await asyncio.wait((task, stopping), return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                # Retain ownership of a roster that finished at the same moment
                # as stop, so the outer cleanup can stop and close its clients.
                return await task
            raise BattleError("Operator stopped before combat")
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    try:
        await until_stop(staff_login(staff, config["staff"]))
        await until_stop(staff.enable_receipts())
        captured_room = await current_room(staff)
        selected_room = captured_room if room is None else room
        phase = "provisioning"
        pool = AccountPool(accounts, config["registration_email"])
        clients, rows, caps = await until_stop(connect_roster(config["host"], config["port"], pool, directory))
        for player in clients.values():
            await until_stop(player.enable_receipts())
        phase = "preparing"
        await until_stop(place_groups(staff, clients, rows, caps, selected_room))
        await until_stop(prepare_fighters(staff, clients, rows, directory))
        await until_stop(prepare_actions(staff, clients, rows, directory))
        groups = await until_stop(refresh_groups(clients, rows, caps))
        phase = "ready"
        (Path(directory) / "ready.json").write_text(json.dumps({"room": selected_room, "caps": caps,
                                                                 "groups": groups}, indent=2))
        print(f"READY: {caps}, room {selected_room}. Log in on a separate observer account. Type start to fight.", flush=True)
        await until_stop(start.wait())
        phase = "fighting"
        print(f"STARTED: maximum {duration:g} seconds. Type status or stop at any time.", flush=True)
        result = await run_combat(staff, clients, rows, caps, stop, duration)
        result["room"] = selected_room
    except Exception as error:
        result["error"] = str(error)
    finally:
        phase = "stopping"
        controls.cancel(); stopping.cancel()
        await asyncio.gather(controls, stopping, return_exceptions=True)
        if rows and "stop" not in result:
            result["stop"] = await stop_fighters(staff, rows)
        await asyncio.gather(*(p.close() for p in clients.values()), return_exceptions=True)
        await staff.close()
        result.setdefault("rows", rows)
        (Path(directory) / "summary.json").write_text(json.dumps(result, indent=2))
        print(f"{result['outcome']}; stop confirmed: {result.get('stop', {}).get('confirmed', False)}. Evidence: {directory}", flush=True)
        if rows and not result.get("stop", {}).get("confirmed"):
            print("STOP UNCONFIRMED: connect staff and use battleprep stop for the participant names in summary.json.", flush=True)
    return result


async def main(args):
    config = json.loads(args.config.read_text())
    directory = args.output
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    commands = asyncio.Queue()
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    transport, _ = await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

    async def read_commands():
        while line := await reader.readline():
            await commands.put(line.decode().strip())
        await commands.put("stop")

    input_task = asyncio.create_task(read_commands())
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, commands.put_nowait, "stop")
    try:
        result = await operate(config, args.accounts, directory, args.room, args.duration, commands)
        return 0 if result.get("stop", {}).get("confirmed") and result["outcome"] not in ("preparation_failed", "interrupted") else 1
    finally:
        input_task.cancel()
        await asyncio.gather(input_task, return_exceptions=True)
        transport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Private JSON: host, port, staff (account/password/character), registration_email")
    parser.add_argument("--accounts", type=Path, default=Path("bin/racewar-battles/accounts.json"))
    parser.add_argument("--output", type=Path, default=Path("bin/racewar-battles") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--room", type=int, help="Battlefield VNUM; defaults to the controller's captured room")
    parser.add_argument("--duration", type=float, default=180, help="Visible maximum combat seconds (default 180)")
    options = parser.parse_args()
    if options.duration <= 0:
        parser.error("--duration must be positive")
    sys.exit(asyncio.run(main(options)))
