#!/usr/bin/env python3
"""Exercise the class dispatcher, production definitions/help and pager on isolated authority."""
import argparse
from pathlib import Path
import re
import signal
import shutil
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command

ROOT = journey.ROOT
PLAYER, ACCOUNT = "Pathscholar", "Pathacct"
GOD, GOD_ACCOUNT = "Pathwarden", "Pathstaff"


def run(binary, backend):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="class-journey-", dir=ROOT / "bin/tests") as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        shutil.copytree(ROOT / "help", runtime / "help")
        # Only disposable help is changed: exercise redirect, missing prose and
        # the legacy/spec name collision against the actual help catalogs.
        for path, separator in ((runtime / "help/duris_help_parsed.hlp", "#0"),
                                (runtime / "lib/information/help_index", "#")):
            topics = re.split(r"(?m)^" + separator + r"[ \t]*$", path.read_text())
            kept = []
            for topic in topics:
                lines = topic.strip().splitlines()
                title = re.sub(r'\s+\([^)]*\)$', '', lines[0]).strip('"').lower() if lines else ""
                if title in ("guardian", "wildmage"):
                    continue
                kept.append(topic)
            path.write_text((separator + "\n").join(kept))
        with (runtime / "help/duris_help_parsed.hlp").open("a") as help_file:
            help_file.write("\nGuardian\nGuardian - Last Edited: 2026-11-02\n"
                            "============================================================\n"
                            "Redirect: Class journey details\n\n#0\n"
                            "\nWildmage\nWildmage - Last Edited: 2026-11-02\n"
                            "============================================================\n"
                            "==Skill changes==\nDeliberately stale authored grant table.\n\n"
                            "==Class mechanics==\n\n==See also==\nSorcerer\n\n#0\n"
                            "\nClass journey details\nClass journey details - Last Edited: 2026-11-02\n"
                            "============================================================\n"
                            "Redirected Guardian focus for the disposable journey.\n\n"
                            "==Class mechanics==\nProtects allies with a shield.\n\n#0\n")
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        process = None
        clients = []
        output_path = runtime / "server.out"
        with authority(backend, runtime) as (env, sql), output_path.open("w") as output:
            if sql:
                # SQL redirects use the help catalog's redirect category.
                sql("UPDATE pages SET category_id=1 WHERE title='Guardian'")
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

            try:
                process = boot()
                for name, account in ((PLAYER, ACCOUNT), (GOD, GOD_ACCOUNT)):
                    client = journey.MudClient(plain)
                    clients.append(client)
                    journey.create_character(client, account=account, character=name,
                                             email=name.lower() + "@example.invalid",
                                             class_name="w")
                    client.send("save")
                    client.expect("Saving " + name + ".", timeout=30)
                stop()
                if sql:
                    sql("UPDATE player_data SET level=62,highest_level=62 WHERE name='" + GOD + "'")
                process = boot()
                god = login(GOD, GOD_ACCOUNT)
                player = login(PLAYER, ACCOUNT)
                deadline = time.monotonic() + 20
                while True:
                    roster = command(player, "class")
                    if "Front-line weapon combat" in roster:
                        break
                    assert time.monotonic() < deadline, roster
                    time.sleep(.1)
                assert "THE CLASS ROSTER" in roster
                for row in ("  Thief (Retired ID 17: Special/Legacy) - Standalone theft/stealth class.",
                            "  Theurgist (Disabled: Special/Legacy) - Celestial invocations and divine/arcane magic.",
                            "  Summoner - Bound creatures, planar magic, and barriers.",
                            "  Dragoon (Disabled) - Mounted draconic martial combat and invocations."):
                    assert row in roster.splitlines(), roster
                assert "Available in" not in roster
                listed = command(player, "class list")
                assert roster.split("THE CLASS ROSTER", 1)[1].split("Inspect:", 1)[0] == listed.split("THE CLASS ROSTER", 1)[1].split("Inspect:", 1)[0]
                human = command(player, "class list human")
                assert "Human : CLASS CHOICES" in human and "Alignment: good" in human
                assert "  Warrior" in human and "  Dragoon" not in human
                assert "No new character can currently select this race" in command(player, "class list lich")
                assert "Grey Elf" in command(player, "class list GrEy-ElF")
                assert "Planetbound Illithid" in command(player, "class list pillithid")
                guardian = command(player, "class info guardian")
                assert "Parent class: Warrior" in guardian and "Redirected Guardian focus" in guardian
                assert "Protects allies with a shield" in guardian
                assert "Lost skill: dual wield" in guardian and "Changed skill:" in guardian
                assert "Added innate: bulwark (level 41, passive)" in guardian
                assert "skills Guardian" in guardian and "spells Guardian" in guardian
                assert guardian.index("Availability") < guardian.index("Class features") < guardian.index("Further reading")
                warrior = command(player, "class info warrior")
                assert "BASE CLASS" in warrior and "Guardian - Protects allies with a shield." in warrior
                assert warrior.index("Specializations") < warrior.index("Class features")
                specs = command(player, "class specs warrior")
                assert "Guardian" in specs and "Swashbuckler" in specs and "class info <specialization>" in specs
                assert "Use specialize at level 30." in specs
                theurgist = command(player, "class info theurgist")
                theurgist_specs = command(player, "class specs theurgist")
                for text in (theurgist, theurgist_specs):
                    for name in ("Medium", "Templar", "Thaumaturge"):
                        assert "  " + name + " (Not available to Human)" in text.splitlines(), text
                    assert " is a Theurgist specialization" not in text
                    assert "Description unavailable" not in text
                medium = command(player, "class info medium")
                assert "Added spell: return soul" in medium and "Added innate: summon host" in medium
                assert " is a Theurgist specialization" not in medium
                assert "Not Used" not in command(player, "class specs rogue")
                assert "No named specializations" in command(player, "class specs warlock")
                missing = command(player, "class info wildmage")
                assert "Parent class: Sorcerer" in missing
                assert "Added innate: wildmagic" in missing
                assert "Deliberately stale" not in missing and "Authored mechanics" not in missing
                for name in ("assassin", "thief"):
                    text = command(player, "class info " + name)
                    assert "Parent class: Rogue" in text and "is a Rogue specialization" not in text
                    assert "Standalone" not in text
                    assert "help Rogue " + name.title() in text
                assert "Anti-Paladin" in command(player, "class info DaRk-KnIgHt")
                # Human cannot select the Dragon Priest path, but can browse it.
                forbidden = command(player, "class info dragon priest")
                assert "Your race permission (Human): not allowed" in forbidden
                assert "skills Dragon Priest" in forbidden
                innates = command(player, "class innates fire magus")
                assert "fireshield (level 30, active)" in innates
                assert "*protection from fire (level 30, passive)" in innates
                assert "fire affinity (level 51, passive)" in innates
                assert "fireshield" in command(player, "class info fire magus")
                inherited = command(player, "class innates huntsman")
                assert "outdoor sneak (level 1, passive)" in inherited
                assert "woodland renewal (level 30, passive)" in inherited
                # Computed modifiers use live class/race data, including base-class
                # inheritance and fractional penalties, without inventing grant IDs.
                warrior_innates = command(player, "class innates warrior")
                assert "Melee and archery damage: +15% (passive)" in warrior_innates
                assert "None. No class innates" not in warrior_innates
                assert "Melee and archery damage: -17.5% (passive)" in command(player, "class innates monk")
                assert "Melee and archery damage: -10% (passive)" in command(player, "class innates berserker")
                for name in ("thief", "assassin"):
                    assert "Melee and archery damage: +10% (passive)" in command(player, "class innates " + name)
                assert "Melee and archery damage" not in command(player, "class innates paladin")
                assert "Melee and archery damage" not in command(player, "race innates barbarian")
                for value, expected in (("1.150", "+15%"), ("0.825", "-17.5%")):
                    command(god, "properties set damage.totalOutput.racial.Barbarian " + value)
                    text = command(player, "race innate barbarian")
                    assert "Melee and archery damage: " + expected + " (passive)" in text, text
                command(god, "properties set damage.totalOutput.racial.Barbarian 1.000")
                assert "Melee and archery damage" not in command(player, "race innates barbarian")
                assert "Max damroll (gear + buffs): 72" in command(player, "race innates storm giant")
                command(god, "properties set damage.totalOutput.racial.StormGiant 1.100")
                text = command(player, "race innates storm giant")
                assert "Melee and archery damage: +10% (passive)" in text and "None." not in text
                command(god, "properties set damage.totalOutput.racial.StormGiant 1.000")
                modifier_help = command(player, "help attack damage modifiers")
                for explanation in ("ordinary melee", "backstab", "higher of their two", "+32.25%"):
                    assert explanation in modifier_help, modifier_help
                wizard = command(player, "class info wizard")
                assert "Lost spell: solbeeps missile barrage" in wizard
                assert "Changed spell: haste (Circle 10 -> 8)" in command(player, "class info shock reaver")
                assert "No such" not in command(god, "class info guardian")
                assert "CLASS ROSTER" in command(god, "class")
                assert "Matching names" in command(player, "class i warrior")
                assert "Matching names" in command(player, "class info s")
                assert "Matching names" in command(player, "class list gith")
                assert "No such class/specialization" in command(player, "class info missing")
                for text in ("class info", "class specs", "class innates", "class wrong"):
                    assert "Usage:" in command(player, text)
                assert "Provide a base class" in command(player, "class specs assassin")
                help_text = command(player, "help class")
                for form in ("class list <race>", "class info <class or specialization>",
                             "class innates <class or specialization>"):
                    assert form in help_text
                for removed in ("transport alignment", "account admission", "readiness"):
                    assert removed not in help_text.lower()
                assert "creation" in command(player, "help classes").lower()
                assert "Guardian" in command(player, "skills guardian")
                assert "SPECIALIZATION" in command(player, "spells guardian")
                assert "fire form" in command(player, "spells fire magus")
                assert "Area of effect" in command(player, "spells info fireball")
                assert "Valid classes" in command(player, "race info human")
                for client in (god, player):
                    command(client, "toggle paging yes")
                    client.send("class")
                    client.expect("THE CLASS ROSTER")
                    client.expect("[Return to continue", timeout=20)
                    client.send("q")
                    client.expect(">", timeout=20)
                    command(client, "toggle paging no")
                assert b"\x1b[" in player.raw_transcript
                for name, text in (("roster", roster), ("guardian", guardian), ("wizard", wizard),
                                   ("warrior", warrior), ("specs", specs), ("innates", innates),
                                   ("damage-modifier", warrior_innates), ("damage-help", modifier_help),
                                   ("forbidden", forbidden), ("human", human),
                                   ("theurgist", theurgist), ("theurgist-specs", theurgist_specs),
                                   ("medium", medium)):
                    for removed in ("Transport alignment", "account admission", "readiness",
                                    "does not establish", "effective definitions", "Authored mechanics"):
                        assert removed not in text, text
                    (ROOT / "bin/tests" / ("class-" + name + "-" + backend + ".txt")).write_text(text)
                    generated = text.split("Score information", 1)[0]
                    for line in generated.splitlines():
                        if name in ("roster", "human", "warrior", "specs", "theurgist", "theurgist-specs") and line.startswith("  ") and " - " in line:
                            continue
                        assert len(line) <= 79, generated
                print("PASS: " + backend + " real staff/mortal class dispatcher, live policy, spec deltas, "
                      "inherited innates, redirected/missing help, legacy collisions, navigation, color, single-line roster and paging", flush=True)
            except BaseException:
                print(output_path.read_text(errors="replace")[-5000:])
                for client in clients:
                    print(bytes(client.transcript[-5000:]).decode(errors="replace"))
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
    parser.add_argument("--backend", choices=("mariadb",), default="mariadb")
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    run(args.server.resolve(), args.backend)
