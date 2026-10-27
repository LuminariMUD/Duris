#!/usr/bin/env python3
"""Framing, concurrent draining, credential isolation and roster/account reuse."""
import asyncio
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_racewar_battle as battle


class ProtocolTests(unittest.TestCase):
    def test_enemy_selection_refreshes_ordinals_and_keeps_deaths_out(self):
        room = {"num": 1200, "name": "Field", "coords": {"x": 0}}
        rows = [{"name": name, "side": side, "index": 0, "battle_room": room}
                for name, side in (("Ally", "good"), ("Enemy", "evil"), ("Other", "evil"))]
        clients = {r["name"]: SimpleNamespace(dead=False, error=None,
                   gmcp={"Room.Info": dict(room), "Char.Vitals": {"fighting": None}}) for r in rows}
        view = clients["Ally"].gmcp["Room.Info"]
        view["players"] = [{"name": "Enemy", "target": "3.human"}, {"name": "Other", "target": "4.human"}]
        self.assertEqual(battle.choose_enemy(rows[0], rows, clients)[1], "3.human")
        clients["Enemy"].dead = True
        # The dead PC may have respawned in the same room; it stays out.
        view["players"][1]["target"] = "2.human"
        self.assertEqual(battle.choose_enemy(rows[0], rows, clients)[1], "2.human")
        clients["Other"].gmcp["Room.Info"]["num"] = 1201
        self.assertIsNone(battle.choose_enemy(rows[0], rows, clients))

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
            events = [event for chunk in chunks for event in chunk[0]]
            self.assertEqual(b"".join(value for kind, value in events if kind == "text"), b"hibye\xff")
            self.assertEqual(b"".join(c[1] for c in chunks), bytes((255,253,201,255,254,86,255,252,24)))
            self.assertEqual([(kind, value) for kind, value in events if kind != "text"],
                             [("gmcp", ("Group.Status", {"maxSize":20,"members":[]})), ("prompt", None)])
            prompt = events.index(("prompt", None))
            self.assertEqual(b"".join(value for kind, value in events[:prompt] if kind == "text"), b"hi")
            self.assertEqual(b"".join(value for kind, value in events[prompt + 1:] if kind == "text"), b"bye\xff")
        decoder = battle.Telnet()
        events = [event for byte in frame for event in decoder.feed(bytes((byte,)))[0]]
        self.assertEqual(b"".join(value for kind, value in events if kind == "text"), b"hibye\xff")

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
    async def test_full_roster_stop_is_one_native_command(self):
        rows = [{"name": f"Battler{i:03}"} for i in range(40)]
        calls = []
        class Staff:
            async def command(self, command, **kwargs):
                calls.append(command)
                return "\n".join(f"Battleprep status {row['name']} quiet." for row in rows)
        with patch.object(battle.asyncio, "sleep", new_callable=AsyncMock):
            result = await battle.stop_fighters(Staff(), rows)
        self.assertTrue(result["confirmed"])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(len(call.encode()) <= battle.MAX_INPUT_BYTES for call in calls))
        self.assertTrue(all(row["name"] in calls[0] for row in rows))

    async def test_immediate_operator_stop_has_zero_actions_and_saves_survivors(self):
        room = {"num": 1200, "name": "Field", "coords": {"x": 0}}
        rows = [{"name": name, "side": side, "index": 0, "class": "Warrior", "battle_room": room}
                for name, side in (("One", "good"), ("Two", "evil"))]
        clients = {row["name"]: SimpleNamespace(dead=False, returned_to_menu=False, error=None,
                   gmcp={"Room.Info": room, "Char.Input": {"sequence": 4}},
                   damage_events=0, observed_damage=0, healing_events=0, observed_healing=0,
                   command=AsyncMock()) for row in rows}
        stop = asyncio.Event(); stop.set()
        with patch.object(battle, "stop_fighters", new_callable=AsyncMock, return_value={"confirmed": True}):
            result = await battle.run_combat(None, clients, rows, {"good": 1, "evil": 1}, stop, 120)
        self.assertEqual(result["outcome"], "operator_stop")
        self.assertEqual(result["save_failures"], [])
        self.assertEqual(result["totals"]["actions_attempted"], 0)
        self.assertEqual(result["totals"]["participants"], 2)
        self.assertTrue(all(row["actions"]["attempted"] == row["actions"]["dequeued"] == 0 for row in rows))
        self.assertTrue(all(row["final_save"] == "acknowledged" for row in rows))

    async def test_native_name_refusal_is_reported_without_a_timeout(self):
        client = SimpleNamespace(send=AsyncMock(), expect=AsyncMock(side_effect=[
            ("Enter your new name", ""), ("Illegal character name", "")]))
        with patch.object(battle, "account_login", new_callable=AsyncMock):
            with self.assertRaisesRegex(battle.BattleError, "character admission rejected: Illegal character name"):
                await battle.create_character(client, {"account": "Dedicated"}, "Rejected", "good", battle.Build("Human", "Warrior"))

    async def test_stop_requires_every_named_status_and_a_settling_recheck(self):
        calls = []
        class Staff:
            async def command(self, command, **kwargs):
                calls.append(command)
                return "Battleprep status one quiet.\nBattleprep status two quiet."
        with patch.object(battle.asyncio, "sleep", new_callable=AsyncMock):
            result = await battle.stop_fighters(Staff(), [{"name": "One"}, {"name": "Two"}])
        self.assertTrue(result["confirmed"])
        self.assertEqual(calls, ["battleprep stop One Two", "battleprep status One Two", "battleprep status One Two"])
        class Disconnected:
            async def command(self, *args, **kwargs):
                raise battle.BattleError("controller disconnected")
        with patch.object(battle.asyncio, "sleep", new_callable=AsyncMock):
            result = await battle.stop_fighters(Disconnected(), [{"name": "One"}])
        self.assertFalse(result["confirmed"])
        self.assertIn("disconnected", result["error"])
        class Missing:
            async def command(self, *args, **kwargs):
                return "Battleprep status one missing."
        with patch.object(battle.asyncio, "sleep", new_callable=AsyncMock):
            unknown = await battle.stop_fighters(Missing(), [{"name": "One"}])
            dead = await battle.stop_fighters(Missing(), [{"name": "One"}], {"One"})
        self.assertFalse(unknown["confirmed"])
        self.assertTrue(dead["confirmed"])
        self.assertEqual(dead["statuses"], {"One": "dead_absent"})
        player = SimpleNamespace(gmcp={"Char.Vitals": {"hp": 10, "maxHp": 10}}, damage_events=0, healing_events=0)
        class ResidualEffect:
            calls = 0
            async def command(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 3:
                    player.gmcp["Char.Vitals"]["hp"] = 9
                return "Battleprep status one quiet."
        with patch.object(battle.asyncio, "sleep", new_callable=AsyncMock):
            result = await battle.stop_fighters(ResidualEffect(), [{"name": "One"}], clients={"One": player})
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["unresolved"][0]["state"], "activity_after_stop")

    async def test_stop_allows_native_maximum_changes_and_overheal_decay(self):
        for before, after in (({"hp": 233, "maxHp": 847}, {"hp": 230, "maxHp": 841}),
                              ({"hp": 943, "maxHp": 738}, {"hp": 941, "maxHp": 738})):
            player = SimpleNamespace(gmcp={"Char.Vitals": before}, damage_events=0, healing_events=0)
            class Staff:
                calls = 0
                async def command(self, *args, **kwargs):
                    self.calls += 1
                    if self.calls == 3:
                        player.gmcp["Char.Vitals"] = after
                    return "Battleprep status one quiet."
            with patch.object(battle.asyncio, "sleep", new_callable=AsyncMock):
                result = await battle.stop_fighters(Staff(), [{"name": "One"}], clients={"One": player})
            self.assertTrue(result["confirmed"], result)

    async def test_native_death_menu_ends_a_pending_gameplay_wait(self):
        async def serve(reader, writer):
            await reader.readline()
            writer.write(b"Your wounds claim you at last. Your spirit slips free of your body...\n")
            await writer.drain()
            await asyncio.sleep(.01)
            writer.write(b"ACCOUNT MENU\nPlease select an option:")
            await writer.drain()
            await reader.read()
            writer.close()
            await writer.wait_closed()
        with tempfile.TemporaryDirectory() as directory:
            server = await asyncio.start_server(serve, "127.0.0.1", 0)
            async with server:
                client = await battle.Client.connect("127.0.0.1", server.sockets[0].getsockname()[1], "actor", directory)
                try:
                    with self.assertRaisesRegex(battle.BattleError, "native death returned"):
                        await client.command("stand")
                    self.assertTrue(client.dead and client.returned_to_menu)
                finally:
                    await client.close()

    async def test_combat_prompts_do_not_dequeue_input_or_complete_a_spell(self):
        seen, release = [], asyncio.Event()
        def receipt(sequence, command=None):
            body = {"sequence": sequence}
            if command:
                body["command"] = command
            return b"\xff\xfa\xc9Char.Input " + json.dumps(body).encode() + b"\xff\xf0"
        async def serve(reader, writer):
            writer.write(receipt(0))
            await writer.drain()
            first = await reader.readline()
            seen.append(first.decode().strip())
            writer.write(b"Old combat prompt\xff\xf9")
            await writer.drain()
            await release.wait()
            writer.write(receipt(1, "cast") + b"You start chanting...\xff\xf9")
            await writer.drain()
            await asyncio.sleep(.04)
            self.assertEqual(len(seen), 1)
            writer.write(b"You complete your spell...\xff\xf9")
            await writer.drain()
            second = await reader.readline()
            seen.append(second.decode().strip())
            writer.write(receipt(2, "kick") + b"You kick your opponent.\xff\xf9")
            await writer.drain()
            await reader.read()
            writer.close()
            await writer.wait_closed()
        with tempfile.TemporaryDirectory() as directory:
            server = await asyncio.start_server(serve, "127.0.0.1", 0)
            async with server:
                client = await battle.Client.connect("127.0.0.1", server.sockets[0].getsockname()[1], "actor", directory)
                try:
                    await client.wait_for(lambda: "Char.Input" in client.gmcp, "initial receipt")
                    client.begin_gameplay_log()
                    cast = asyncio.create_task(client.action("cast 'magic missile' 1.human"))
                    kick = asyncio.create_task(client.action("kick 1.human"))
                    await asyncio.sleep(.04)
                    self.assertFalse(cast.done())
                    self.assertEqual(seen, ["cast 'magic missile' 1.human"])
                    release.set()
                    output, followup = await asyncio.gather(cast, kick)
                    self.assertIn("You complete your spell", output)
                    self.assertNotIn("Old combat prompt", output)
                    self.assertIn("You kick", followup)
                    records = [json.loads(line) for line in (Path(directory) / "actor.jsonl").read_text().splitlines()]
                    results = [r["value"] for r in records if r["kind"] == "action_result"]
                    self.assertEqual([r["spell_completed"] for r in results], [True, False])
                finally:
                    release.set()
                    await client.close()

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

    async def test_command_requires_a_prompt_after_its_expected_response(self):
        async def serve(reader, writer):
            try:
                await reader.readline()
                # A delayed earlier GA and the beginning of the new response
                # can arrive in one read; that GA must not complete this reply.
                writer.write(b"\xff\xf9\x1b[31mPaging")
                await writer.drain()
                await asyncio.sleep(.02)
                writer.write(b" : OFF\x1b[0m\r\n>\xff\xef")
                await writer.drain()
                await reader.readline()
                # The matching response and its prompt can also arrive together.
                writer.write(b"Room: [1200]\r\n>\xff\xf9")
                await writer.drain()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
        with tempfile.TemporaryDirectory() as directory:
            server = await asyncio.start_server(serve, "127.0.0.1", 0)
            async with server:
                client = await battle.Client.connect("127.0.0.1", server.sockets[0].getsockname()[1], "actor", directory)
                try:
                    output = await client.command("toggle", expected="Paging", timeout=1)
                    self.assertEqual(output, "Paging : OFF\n>")
                    self.assertEqual(await client.command("stat room", expected="Room:", timeout=1), "Room: [1200]\n>")
                finally:
                    await client.close()

    async def test_both_entry_paths_wait_for_the_game_prompt_before_paging(self):
        account = {"account": "Controller", "password": "private", "character": "Actor"}
        creation = [("2", "Enter your new name"), ("Actor", "Is this correct?"),
                    ("y", "meet these criteria?"), ("y", "(h) Human (H for help)\nYour selection"),
                    ("h", "Male or Female"), ("m", "Hardcore"),
                    ("n", "w) Warrior (W for help)\nYour selection"),
                    ("w", "Your stat rolling system [D]:"), ("", "first bonus"),
                    ("s", "second bonus"), ("d", "third bonus"), ("a", "fourth bonus"),
                    ("l", "swap stats"), ("n", "keep this character"), ("y", "PRESS RETURN")]
        for entry in ("staff", "reconnect", "override", "create"):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as directory:
                premature = []
                finished = asyncio.get_running_loop().create_future()
                async def serve(reader, writer):
                    try:
                        if entry == "create":
                            dialogue, last = creation, ""
                        else:
                            response = {"staff": "Play as", "reconnect": "Reconnecting...",
                                        "override": "Overriding old connection..."}[entry]
                            dialogue = [("1", "Actor"), ("Actor", response)]
                            last = "y" if entry == "staff" else None
                        for command, response in dialogue:
                            self.assertEqual((await reader.readline()).decode().strip(), command)
                            writer.write(response.encode())
                            await writer.drain()
                        if last is not None:
                            self.assertEqual((await reader.readline()).decode().strip(), last)
                        # A menu GA before Char.Status cannot count as game entry.
                        writer.write(b"\xff\xf9\xff\xfa\xc9Char.Status " +
                                     json.dumps({"name": "Actor", "level": 65}).encode() + b"\xff\xf0" +
                                     (b"Your starter kit is ready" if entry == "create" else b"PRIVATE entry banner"))
                        await writer.drain()
                        try:
                            premature.append(await asyncio.wait_for(reader.readline(), .03))
                        except asyncio.TimeoutError:
                            pass
                        writer.write(b"\r\n>\xff\xf9")
                        await writer.drain()
                        command = premature[0] if premature else await reader.readline()
                        self.assertEqual(command, b"toggle\n")
                        writer.write(b"Paging : OFF\r\n>\xff\xf9")
                        await writer.drain()
                        finished.set_result(None)
                        await reader.read()
                    except Exception as error:
                        if not finished.done():
                            finished.set_exception(error)
                    finally:
                        writer.close()
                        await writer.wait_closed()
                server = await asyncio.start_server(serve, "127.0.0.1", 0)
                async with server:
                    client = await battle.Client.connect("127.0.0.1", server.sockets[0].getsockname()[1], "actor", directory)
                    try:
                        with patch.object(battle, "account_login"):
                            if entry == "create":
                                await asyncio.wait_for(battle.create_character(client, account, "Actor", "good",
                                                                               battle.Build("Human", "Warrior")), 2)
                            else:
                                await asyncio.wait_for(battle.staff_login(client, account), 2)
                        await asyncio.wait_for(finished, 1)
                        self.assertEqual(premature, [], "paging was sent before the entry prompt")
                    finally:
                        await client.close()
                self.assertNotIn("PRIVATE", (Path(directory) / "actor.jsonl").read_text())

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
