#!/usr/bin/env python3
"""Exercise the shaman totem check through the real cast command."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import server_build_artifacts
import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command

SHAMAN, ACCOUNT = "Totemcaller", "Totemacct"
GOD, GOD_ACCOUNT = "Totemwarden", "Totemstaff"


def run(binary):
    build = journey.ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shaman-totems-", dir=build) as temporary:
        runtime = Path(temporary)
        journey.make_fixture(runtime)
        # Combat-only scavengers must not steal the totems this journey drops.
        zone = runtime / "areas_mini/mini.zon"
        zone.write_text("".join(line for line in zone.read_text().splitlines(keepends=True)
                                if not line.startswith(("M ", "G "))))
        # Give the fixture's quartz totem a neck slot to exercise non-hand equipment.
        objects = runtime / "areas_mini/mini.obj"
        before, quartz = objects.read_text().split("#111\n", 1)
        objects.write_text(before + "#111\n" + quartz.replace("1024 16385", "1024 16389", 1))
        journey.generate_certificate(runtime)
        (runtime / "logs/log").mkdir(parents=True)
        critical = runtime / "journals/critical"
        critical.mkdir(parents=True, mode=0o700)
        plain, tls, websocket = journey.available_ports()
        log = runtime / "server.out"

        with authority("flatfile", runtime) as (env, _):
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket),
                       MAINTENANCE_STATE_FILE=str(runtime / "maintenance.state"))

            def boot(stack):
                start = log.stat().st_size if log.exists() else 0
                output = stack.enter_context(log.open("a"))
                process = subprocess.Popen(
                    [str(binary), "--minimal", "-d", str(runtime), str(plain)],
                    cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)

                def stop():
                    if process.poll() is None:
                        process.send_signal(signal.SIGTERM)
                        assert process.wait(timeout=60) == 0

                stack.callback(stop)
                deadline = time.monotonic() + 120
                while b"Entering game loop." not in log.read_bytes()[start:]:
                    assert process.poll() is None and time.monotonic() < deadline, "boot failed"
                    time.sleep(.1)

            try:
                with ExitStack() as stack:
                    boot(stack)
                    for name, account, class_key in ((SHAMAN, ACCOUNT, "h"),
                                                     (GOD, GOD_ACCOUNT, "w")):
                        client = journey.MudClient(plain)
                        stack.callback(client.close)
                        journey.create_character(client, account=account, character=name,
                                                 email=name.lower() + "@example.invalid",
                                                 class_name=class_key)
                        client.send("save")
                        client.expect("Saving " + name + ".", timeout=30)

                journey.make_overlord(Path(env["FLATFILE_STATE_DIR"]), GOD)
                with ExitStack() as stack:
                    boot(stack)
                    players = []
                    for name, account in ((SHAMAN, ACCOUNT), (GOD, GOD_ACCOUNT)):
                        client = journey.reconnect_character(plain, account=account, character=name)
                        stack.callback(client.close)
                        players.append(client)
                    shaman, god = players
                    result = command(god, "advance " + SHAMAN + " 50")
                    assert "You feel generous" in result, result
                    shaman.send("rest")
                    for spell in ("spirit armor",) * 3 + ("cold ward", "lionrage"):
                        shaman.send("memorize " + spell)
                        shaman.expect("You are memorizing " + spell)
                    shaman.expect("memorization complete", timeout=90)
                    command(shaman, "stand")

                    def move_item(line, expected):
                        result = command(shaman, line)
                        assert expected in result, result

                    def cast(spell):
                        return command(shaman, f"cast '{spell}' {SHAMAN}")

                    def expect_cast(spell, effect):
                        result = cast(spell)
                        assert effect in result, result

                    def expect_missing(spell, requirement, color):
                        start = len(shaman.raw_transcript)
                        result = cast(spell)
                        assert (f"You need a {requirement} totem equipped or in your inventory "
                                "for that spell!") in result, result
                        assert (color + requirement.encode() + b"\x1b[0m") in shaman.raw_transcript[start:]

                    # Leave room to move the test items back into inventory.
                    command(shaman, "drop all")
                    for item in ("bag", "bear", "obsidian", "quartz"):
                        move_item("get " + item, "You get")

                    # The spirit focus works loose in inventory and around the neck.
                    expect_cast("spirit armor", "You feel protective spirits watching over you.")
                    move_item("put quartz bag", "Ok.")
                    expect_missing("spirit armor", "Lesser Spirit", b"\x1b[0;1;36m")
                    move_item("get quartz bag", "You get")
                    move_item("wear quartz neck", "around your neck")
                    expect_cast("spirit armor", "The spirits seem refreshed.")

                    move_item("drop obsidian", "You drop")
                    expect_missing("cold ward", "Lesser Elemental", b"\x1b[0;1;31m")
                    move_item("get obsidian", "You get")
                    move_item("hold obsidian", "You hold")
                    expect_cast("cold ward", "You feel protected from the cold!")

                    move_item("drop bear", "You drop")
                    command(god, "load obj 105")
                    command(god, "drop raven")
                    move_item("get raven", "You get")
                    expect_missing("lionrage", "Greater Animal", b"\x1b[0;1;33m")
                    move_item("drop raven", "You drop")
                    move_item("get bear", "You get")
                    expect_cast("lionrage", "You feel strength and power courses through your veins!")
            except BaseException:
                print(log.read_text(errors="replace")[-4000:])
                raise

    print("PASS: real shaman casts from inventory, neck and hold, with colored sphere and tier errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, help="use an existing flat-file server build")
    args = parser.parse_args()
    if args.server:
        run(args.server.resolve())
    else:
        build = journey.ROOT / "bin/tests"
        build.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="shaman-totem-build-", dir=build) as temporary:
            run(server_build_artifacts.build_flatfile_server(Path(temporary)))
