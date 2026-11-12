#!/usr/bin/env python3
"""Import copied help and exercise the player navigation path on disposable MariaDB.

Run with with_disposable_mariadb.sh and --server bin/server/dms_new.
No checkout environment, account, player data or running game is used.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Helpscholar", "Helpacct"
OWNER, OWNER_ACCOUNT = "Helpmirror", "Mirroracct"
GOD, GOD_ACCOUNT = "Helpwarden", "Helpstaff"
DESTINATIONS = (
    "Exits", "Look", "Consider", "Flee", "Death", "Corpse", "Get", "Equipment",
    "Inventory", "Wear", "Wield", "COMMUNICATIONS UTILITIES CHANNELS", "Nchat",
    "Say", "Practice", "Cast", "Memorize", "Policies", "rules", "Innate", "Innates",
    "Class", "Race", "Skills", "Spells", "LAWS RULES",
)


def run(binary):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="help-navigation-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        shutil.copytree(ROOT / "help", runtime / "help")
        # Sorted before the exact title by the real SQL loader; no production data.
        with (runtime / "help/duris_help_parsed.hlp").open("a") as fixture:
            for title in [f"A capstone {i:03}" for i in range(150)] + ["Capstone"]:
                body = "Late exact help article." if title == "Capstone" else "Alternative fixture."
                fixture.write(f"\n{title}\n{title} - Last Edited: 2026-11-12\n"
                              f"============================================================\n{body}\n#0\n")
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        process = None
        clients = []
        output_path = runtime / "server.out"
        evidence = {"server": str(binary), "destinations": len(DESTINATIONS)}
        with authority("mariadb", runtime) as (env, sql), output_path.open("w") as output:
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot():
                start = output_path.stat().st_size
                proc = subprocess.Popen([str(binary), "--minimal", "-d", str(runtime), str(plain)],
                                        cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in output_path.read_bytes()[start:]:
                    assert proc.poll() is None and time.monotonic() < deadline, "boot failed"
                    time.sleep(.1)
                return proc

            def stop():
                for client in clients:
                    client.close()
                clients.clear()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
                assert process.returncode == 0

            def login(name, account):
                client = journey.reconnect_character(plain, expected_room=None, account=account, character=name)
                clients.append(client)
                client.expect("Welcome to Duris", timeout=60)
                client.expect_any(("Pos: standing >", "<>"), timeout=20)
                command(client, "toggle paging no")
                return client

            def saved_ability_state(client, name):
                # The native "Saving" receipt follows the writer's revision ack.
                client.send("save")
                client.expect("Saving " + name + ".", timeout=30)
                client.expect(">", timeout=20)
                pid = sql(f"SELECT pid FROM player_data WHERE name='{name}'")
                header = (ROOT / "src/magic/spells.h").read_text()
                types = [re.search(r"^#define " + key + r" (\d+)", header, re.M)[1]
                         for key in ("TAG_INNATE_TIMER", "SPELL_REFLECTION", "SPELL_MIRROR_IMAGE")]
                return sql(f"SELECT type,location,modifier,flags FROM player_affects WHERE pid={pid} "
                           f"AND type IN ({','.join(types)}) ORDER BY type,location,modifier,flags")

            try:
                evidence["catalog_pages"] = int(sql("SELECT COUNT(*) FROM pages"))
                assert sql("SELECT COUNT(*) FROM pages WHERE title='Capstone'") == "1"
                assert sql("SELECT COUNT(*) FROM pages WHERE title LIKE '%capstone%'") == "151"
                assert "help firball" in sql("SELECT text FROM pages WHERE title='Help'")
                process = boot()
                for name, account in ((PLAYER, ACCOUNT), (OWNER, OWNER_ACCOUNT), (GOD, GOD_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, account=account, character=name,
                                             email=name.lower() + "@example.invalid", class_name="w")
                    client.send("save")
                    client.expect("Saving " + name + ".", timeout=30)
                stop()
                sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                # Gnome racial reflection unlocks at 31; the ordinary human lacks it.
                sql(f"UPDATE player_data SET race=8,level=31,highest_level=31 WHERE name='{OWNER}'")
                process = boot()
                god = login(GOD, GOD_ACCOUNT)
                player = login(PLAYER, ACCOUNT)
                owner = login(OWNER, OWNER_ACCOUNT)
                deadline = time.monotonic() + 20
                while "Find instructions" not in command(player, "help"):
                    assert time.monotonic() < deadline, "catalog never became ready"
                for query, marker in (("help", "==Start here=="), ("help index", "==Combat and escape=="),
                                      ("help newbie", "==Your first session==")):
                    text = command(player, query)
                    assert marker in text and "innate info reflection" in text, text
                for title in DESTINATIONS:
                    text = command(player, "help " + title)
                    assert "no help topics" not in text and "Last Edited:" in text, (title, text)
                for verb in ("help", "info"):
                    text = command(player, verb + "   CaPsToNe   ")
                    assert text.index("Late exact help article.") < text.index("also matched"), text
                    assert "A capstone 099" in text and "A capstone 100" not in text, text
                    assert "More topics matched; use a longer name" in text, text
                    alternatives = text.split("also matched your search:", 1)[1]
                    assert len(re.findall(r"(?m)^ A capstone", alternatives)) == 100, alternatives
                assert "A capstone 099" in command(player, "help Caps_one")
                # Generic output remains readable and does not contain MXP controls.
                command(player, "toggle terminal gen")
                raw_start = len(player.raw_transcript)
                typo = command(player, "help firball")
                assert "Did you mean:" in typo and "Fireball" in typo, typo
                assert b"<SEND" not in player.raw_transcript[raw_start:]
                # Negotiate MXP on the same connection, then follow the returned target.
                command(player, "toggle terminal ansi")
                player.socket.sendall(bytes((255, 251, 91)))  # IAC WILL MXP
                raw_start = len(player.raw_transcript)
                command(player, "help firball")
                raw = bytes(player.raw_transcript[raw_start:])
                target = re.search(rb'<SEND HREF="(help Fireball)">', raw)
                assert target, raw
                opened = command(player, target[1].decode())
                assert "Area of effect" in opened and "Did you mean:" not in opened, opened
                # Use a plain connection for a real pager-enabled hub request.
                command(owner, "toggle paging yes")
                owner.send("help index")
                owner.expect("Movement and looking")
                owner.expect("[Return to continue", timeout=20)
                owner.send("r")
                owner.expect("Movement and looking")
                owner.expect("[Return to continue", timeout=20)
                owner.send("q")
                owner.expect(">", timeout=20)
                command(owner, "toggle paging no")
                for query, marker in (
                    ("class info warrior", "BASE CLASS"), ("class specs warrior", "Guardian"),
                    ("race info grey elf", "Valid classes"), ("skills warrior", "bash"),
                    ("skills info bash", "Your progress"), ("spells cleric", "Circle"),
                    ("spells info fireball", "Area of effect"),
                ):
                    assert marker in command(player, query), query
                unavailable = command(player, "innate info reflection")
                assert "Not available to your race" in unavailable and "Uses: 1" in unavailable, unavailable
                available = command(owner, "innate info reflection")
                assert "You have it" in available and "Status: ready" in available, available
                # The info request must leave the first use available.
                activated = command(owner, "innate reflection")
                assert "into many images!" in activated, activated
                before = saved_ability_state(owner, OWNER)
                assert before, "the active innate produced no saved effects"
                for _ in range(3):
                    text = command(owner, "innate info reflection")
                    assert "Status: resting" in text, text
                after = saved_ability_state(owner, OWNER)
                assert after == before, (before, after)
                before = saved_ability_state(player, PLAYER)
                command(player, "innate info reflection")
                assert saved_ability_state(player, PLAYER) == before
                # No publication is inferred from a queued refresh: observe a new
                # generation and then the changed suggestion and article.
                status = command(god, "page help status")
                generation = int(re.search(r"generation (\d+)", status)[1])
                sql("INSERT INTO pages(title,text,category_id,last_update,last_update_by) "
                    "VALUES('Firball','Refreshed exact article.',0,NOW(),'fixture')")
                command(god, "page help")
                deadline = time.monotonic() + 20
                while True:
                    status = command(god, "page help status")
                    match = re.search(r"generation (\d+)", status)
                    if match and int(match[1]) > generation:
                        break
                    assert time.monotonic() < deadline, status
                assert "Refreshed exact article." in command(player, "help firball")
                changed = command(player, "help firbll")
                assert 'HREF="help Firball"' in changed, changed
                # Ordinary commands on another connection during repeated misses.
                def sample(client, query, count):
                    durations = []
                    for _ in range(count):
                        start = time.monotonic()
                        command(client, query)
                        durations.append((time.monotonic() - start) * 1000)
                    return durations
                baseline = sample(owner, "look", 8)
                with ThreadPoolExecutor(max_workers=1) as workers:
                    load = workers.submit(sample, player, "help firbll", 16)
                    loaded = sample(owner, "look", 16)
                    misses = load.result(timeout=30)
                assert max(loaded) < max(baseline) + 750, (baseline, loaded)
                def timing(values):
                    ordered = sorted(values)
                    return {"samples": len(values), "median_ms": statistics.median(values),
                            "p95_ms": ordered[int(.95 * (len(ordered) - 1))], "max_ms": max(values)}
                evidence.update(catalog_generation=int(match[1]), baseline=timing(baseline),
                                concurrent_look=timing(loaded), repeated_misses=timing(misses))
                (ROOT / "bin/tests/help-navigation-evidence.json").write_text(json.dumps(evidence, indent=2))
                print(json.dumps(evidence, indent=2), flush=True)
                print("PASS: MariaDB import, hubs/destinations, late exact/wildcard/info, plain/MXP "
                      "suggestion follow, paging, reference commands, read-only innate owner/non-owner, "
                      "published refresh and two-client responsiveness", flush=True)
            except BaseException:
                print(output_path.read_text(errors="replace")[-5000:])
                for client in clients:
                    print(bytes(client.transcript[-4000:]).decode(errors="replace"))
                raise
            finally:
                for client in clients:
                    client.close()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=60)
                    assert process.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve())
