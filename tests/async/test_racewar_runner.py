#!/usr/bin/env python3
"""Framing, concurrent draining, credential isolation and roster/account reuse."""
import asyncio
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_racewar_battle as battle


class ProtocolTests(unittest.TestCase):
    def test_selected_spells_have_unspecialized_native_grants(self):
        source = (Path(__file__).resolve().parents[2] / "src/classes/skills.c").read_text()
        blocks = {}
        for block in re.split(r"\bSPELL_CREATE(?:_MSG|_WITH_MESSAGES)?\(", source)[1:]:
            match = re.match(r'"([^\"]+)"', block)
            if match:
                blocks[match[1]] = block
        for cls, spells in battle.SPELL_LOADOUTS.items():
            for spell in spells:
                grant = re.search(r"(?m)^\s*SPELL_ADD\(CLASS_" + cls.upper() + r",\s*(\d+)\)", blocks[spell])
                self.assertIsNotNone(grant, (cls, spell))
                self.assertLessEqual(int(grant[1]), 12, (cls, spell))

    def test_every_byte_boundary(self):
        frame = (b"hi" + bytes((255, 251, 201, 255, 251, 86, 255, 253, 24)) +
                 bytes((255, 250, 201)) + b'Group.Status {"maxSize":20,"members":[]}' +
                 bytes((255, 240, 255, 249)) + b"bye" + bytes((255, 255)))
        for boundary in range(len(frame) + 1):
            decoder = battle.Telnet()
            chunks = [decoder.feed(frame[:boundary]), decoder.feed(frame[boundary:])]
            self.assertEqual(b"".join(c[0] for c in chunks), b"hibye\xff")
            self.assertEqual(b"".join(c[1] for c in chunks), bytes((255,253,201,255,254,86,255,252,24)))
            self.assertEqual([m for c in chunks for m in c[2]], [("Group.Status", {"maxSize":20,"members":[]})])
            self.assertEqual(sum(c[3] for c in chunks), 1)
        decoder = battle.Telnet()
        self.assertEqual(b"".join(decoder.feed(bytes((byte,)))[0] for byte in frame), b"hibye\xff")

    def test_refusal_does_not_loop(self):
        self.assertEqual(battle.Telnet().feed(bytes((255, 252, 201, 255, 254, 24)))[1], b"")

    def test_invalid_gmcp_is_not_read_as_text(self):
        with self.assertRaises(json.JSONDecodeError):
            battle.Telnet().feed(bytes((255,250,201)) + b"Char.Status {bad}" + bytes((255,240)))

    def test_native_menus_and_substitution(self):
        race = "| (h) Human (H for help) | (u) Duergar Dwarf (U for help) |"
        self.assertEqual(battle.choose_menu(race, "Duergar", race=True), ("u", "Duergar Dwarf"))
        classes = "Class Selection\nw) Warrior (W for help)\ns) Sorcerer (S for help)\nz) Return"
        self.assertEqual(battle.choose_menu(classes, "Warrior"), ("w", "Warrior"))
        self.assertEqual(battle.choose_menu(classes, "Monk", alternatives=("Warrior",)), ("w", "Warrior"))
        with self.assertRaises(battle.BattleError):
            battle.choose_menu(classes, "Cleric", alternatives=("Shaman",))

    def test_independent_caps_keep_roles_and_diversity(self):
        for side in ("good", "evil"):
            full = battle.roster(side, 20)
            self.assertEqual(len({b.race for b in full}), 12)
            self.assertEqual(len({b.cls for b in full}), 18)
            self.assertEqual([b.cls for b in battle.roster(side, 3)], ["Warrior", "Cleric", "Sorcerer"])
            self.assertEqual(len(battle.roster(side, 27)), 27)
            with self.assertRaises(battle.BattleError):
                battle.roster(side, 0)

    def test_pool_reuses_accounts_without_overwriting_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            pool = battle.AccountPool(path, "operator@example.invalid")
            first, character = pool.account("good", 0)
            second, another = battle.AccountPool(path, "operator@example.invalid").account("good", 0)
            self.assertEqual(first["account"], second["account"])
            self.assertEqual(first["password"], second["password"])
            self.assertNotEqual(character, another)
            self.assertEqual(second["characters"], [character, another])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            data = json.loads(path.read_text())
            data["evil"] = [data["good"][0]]
            path.write_text(json.dumps(data))
            with self.assertRaises(battle.BattleError):
                battle.AccountPool(path, "operator@example.invalid")


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_readiness_refreshes_group_levels_and_rejects_missing_members(self):
        rows = [{"name": "Lead", "side": "good", "index": 0, "level": 56},
                {"name": "Mate", "side": "good", "index": 1, "level": 56}]
        members = [{"name": row["name"], "level": 56, "isNpc": False, "inRoom": True} for row in rows]
        class Leader:
            def __init__(self):
                self.gmcp = {"Group.Status": {"members": [{"name": "Lead", "level": 1}]}}
                self.live = {"size": 2, "maxSize": 2, "members": members}
            async def command(self, line):
                assert line == "group" and "Group.Status" not in self.gmcp
                self.gmcp["Group.Status"] = self.live
            async def wait_for(self, predicate, description):
                return predicate()
        leader = Leader()
        groups = await battle.refresh_groups({"Lead": leader}, rows, {"good": 2})
        self.assertEqual([m["level"] for m in groups["good"]["members"]], [56, 56])
        leader.live = {"size": 2, "maxSize": 2, "members": members[:1]}
        with self.assertRaisesRegex(battle.BattleError, "no longer full"):
            await battle.refresh_groups({"Lead": leader}, rows, {"good": 2})

    async def test_incomplete_gear_cannot_become_ready(self):
        class Staff:
            async def command(self, line, **kwargs):
                if line.startswith("chaos kit"):
                    return "Chaos equipment restoration queued."
                if line.endswith(" baseline"):
                    return "Battleprep: Actor baseline ready at level 56."
                return "Battleprep: Actor equipment incomplete." if line.endswith(" equip") else ""
        class Player:
            async def command(self, line, **kwargs):
                return "You are carrying: (0/20)" if line == "inventory" else ""
            async def expect(self, *args, **kwargs):
                return "Your starter kit is ready", ""
        rows = [{"name": "Actor", "class": "Warrior", "side": "good", "index": 0}]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(battle.BattleError, "loadout incomplete"):
                await battle.prepare_fighters(Staff(), {"Actor": Player()}, rows, directory)
            record = json.loads((Path(directory) / "preparation.json").read_text())[0]
            self.assertEqual(record["preparation"], "failed")
            self.assertNotIn("prepared_spells", record)

    async def test_paging_uses_native_toggle_and_preserves_an_already_disabled_setting(self):
        class FakeClient:
            def __init__(self, state):
                self.state, self.commands = state, []
            async def command(self, line, **kwargs):
                self.commands.append((line, kwargs.get("expected")))
                return f"Paging : {self.state}" if line == "toggle" else "Paging mode off."
        enabled = FakeClient("ON")
        await battle.disable_paging(enabled)
        self.assertEqual(enabled.commands, [("toggle", "Paging"), ("toggle paging", "Paging mode off.")])
        disabled = FakeClient("OFF")
        await battle.disable_paging(disabled)
        self.assertEqual(disabled.commands, [("toggle", "Paging")])

    async def test_each_leader_supplies_its_own_cap(self):
        class FakeClient:
            async def command(self, line):
                return ""
            async def wait_for(self, predicate, description):
                return predicate()
        async def connect(*args):
            return FakeClient()
        async def create(client, account, name, side, build):
            client.gmcp = {"Group.Status": {"maxSize": 3 if side == "good" else 5}}
            return build
        with tempfile.TemporaryDirectory() as directory:
            pool = battle.AccountPool(Path(directory) / "accounts.json", "operator@example.invalid")
            with patch.object(battle.Client, "connect", connect), patch.object(battle, "create_character", create):
                clients, rows, caps = await battle.connect_roster("any-host", 7777, pool, directory)
            self.assertEqual(caps, {"good": 3, "evil": 5})
            self.assertEqual(len(clients), 8)
            self.assertEqual(sum(row["side"] == "good" for row in rows), 3)
            self.assertEqual(sum(row["side"] == "evil" for row in rows), 5)

    async def test_failed_admission_closes_partial_roster_and_records_no_credentials(self):
        opened = []
        class FakeClient:
            gmcp = {"Group.Status": {"maxSize": 3, "size": 0, "members": []}}
            closed = False
            async def command(self, line):
                return ""
            async def wait_for(self, predicate, description):
                return predicate()
            async def close(self):
                self.closed = True
        async def connect(*args):
            client = FakeClient()
            opened.append(client)
            return client
        async def create(client, account, name, side, build):
            if build.cls == "Cleric":
                raise battle.BattleError("Observed admission rejection")
            await asyncio.sleep(.01)
            return build
        with tempfile.TemporaryDirectory() as directory:
            pool = battle.AccountPool(Path(directory) / "accounts.json", "operator@example.invalid")
            with patch.object(battle.Client, "connect", connect), patch.object(battle, "create_character", create):
                with self.assertRaisesRegex(battle.BattleError, "admission rejection"):
                    await battle.connect_roster("any-host", 7777, pool, directory)
            self.assertTrue(opened and all(client.closed for client in opened))
            text = (Path(directory) / "roster.json").read_text()
            self.assertIn("failed", text)
            for side in pool.data.values():
                for account in side:
                    self.assertNotIn(account["password"], text)
                    self.assertIn(account["account"], text)

    async def test_drain_login_secrecy_and_serial_commands(self):
        seen = []
        async def serve(reader, writer):
            writer.write(b"PRIVATE login echo\xff\xf9")
            await writer.drain()
            try:
                while line := await reader.readline():
                    command = line.decode().strip()
                    seen.append(command)
                    if command == "flood":
                        writer.write(b"x" * 180000 + b"end\xff\xf9")
                    else:
                        for part in (b"\x1b[", b"31m", b"r\xc3", b"\xa9ply ", line, b"\x1b[0m\xff", b"\xf9"):
                            writer.write(part)
                            await writer.drain()
                            await asyncio.sleep(.001)
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        with tempfile.TemporaryDirectory() as directory:
            server = await asyncio.start_server(serve, "127.0.0.1", 0)
            async with server:
                client = await battle.Client.connect("127.0.0.1", server.sockets[0].getsockname()[1], "actor", directory)
                try:
                    await client.expect("PRIVATE login echo")
                    await client.wait_for(lambda: client.prompts, "first prompt")
                    client.begin_gameplay_log()
                    outputs = await asyncio.gather(client.command("one", expected=("réply one", "rejected")), client.command("two"))
                    self.assertEqual(seen, ["one", "two"])
                    self.assertIn("réply one", outputs[0])
                    self.assertIn("réply two", outputs[1])
                    await client.send("flood")
                    await client.expect("end")
                    self.assertLessEqual(len(client.pending), 131072)
                finally:
                    await client.close()
            content = (Path(directory) / "actor.jsonl").read_text()
            self.assertNotIn("PRIVATE", content)
            self.assertNotIn("login", content)
            records = [json.loads(line) for line in content.splitlines()]
            self.assertGreater(sum(len(r["value"]) for r in records if r["kind"] == "output"), 180000)

    async def test_disconnect_releases_waiter_without_login_dump(self):
        async def serve(reader, writer):
            writer.write(b"secret password echo")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        with tempfile.TemporaryDirectory() as directory:
            server = await asyncio.start_server(serve, "127.0.0.1", 0)
            async with server:
                client = await battle.Client.connect("127.0.0.1", server.sockets[0].getsockname()[1], "actor", directory)
                try:
                    with self.assertRaises(battle.BattleError) as caught:
                        await client.expect("account menu")
                    self.assertNotIn("secret", str(caught.exception))
                    self.assertEqual(list(Path(directory).iterdir()), [])
                finally:
                    await client.close()


if __name__ == "__main__":
    unittest.main()
