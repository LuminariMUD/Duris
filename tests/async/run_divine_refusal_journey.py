#!/usr/bin/env python3
"""Run ordered divine refusal A/B cases under with_disposable_mariadb.sh."""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time

import test_mariadb_combat_journey as journey


CLERIC_MOBS = """#22801
divine healer cleric~
a bound healer~
A bound healer waits here to test ordered divine magic.
~
~
10 0 0 0 0 0 0 0 S
PH 0 32 -1
50 0 0 200d1+2000 1d1+1
0.0.0.0 0
8 8 0
#22802
divine striker cleric~
a bound striker~
A bound striker waits here to test ordered attacks.
~
~
10 0 0 0 0 0 0 0 S
PH 0 32 -1
50 0 0 200d1+2000 1d1+1
0.0.0.0 0
8 8 0
#22803
divine witness warrior~
a bound witness~
A bound witness waits here to test mixed follower orders.
~
~
10 0 0 0 0 0 0 0 S
PH 0 1 -1
50 0 0 200d1+2000 1d1+1
0.0.0.0 0
8 8 0
"""


def drain(client: journey.MudClient, duration: float = 0.6) -> str:
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        client._receive()
        time.sleep(0.02)
    output = client.pending.decode("utf-8", errors="replace")
    client.pending.clear()
    return output


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def configure_fixture(runtime: Path, enabled: bool) -> None:
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)

    properties_path = runtime / "lib/duris.properties"
    properties = properties_path.read_text(encoding="utf-8")
    expected = "pets.divine_refusal.enabled=0"
    require(properties.count(expected) == 1, "divine-refusal master setting changed")
    properties = properties.replace(
        expected, f"pets.divine_refusal.enabled={1 if enabled else 0}"
    )
    properties = properties.replace(
        "pets.divine_refusal.percent=10", "pets.divine_refusal.percent=100"
    )
    properties = properties.replace(
        "pets.divine_refusal.retry_lock_seconds=4",
        "pets.divine_refusal.retry_lock_seconds=8",
    )
    properties_path.write_text(properties, encoding="utf-8")

    mobile_path = runtime / "areas_mini/mini.mob"
    mobiles = mobile_path.read_text(encoding="utf-8")
    require(mobiles.count("$~") == 1, "minimal mobile terminator changed")
    mobile_path.write_text(
        mobiles.replace("$~", CLERIC_MOBS + "$~"), encoding="utf-8"
    )


def run_scenario(server_binary: Path, enabled: bool) -> None:
    label = "enabled-100-percent" if enabled else "disabled"
    print(f"divine refusal journey: {label}", flush=True)
    with journey.mariadb_authority() as (environment, sql), \
            tempfile.TemporaryDirectory(prefix=f"divine-refusal-{label}-") as temporary:
        root = Path(temporary)
        runtime = root / "runtime"
        runtime.mkdir()
        (runtime / "logs/log").mkdir(parents=True)
        configure_fixture(runtime, enabled)
        (runtime / "journals" / "critical").mkdir(parents=True, mode=0o700)
        (runtime / "bin/server").mkdir(parents=True)
        for name in ("dms", "dms_new"):
            shutil.copy2(server_binary, runtime / "bin/server" / name)

        port, tls_port, websocket_port = journey.available_ports()
        environment.update(
            PATH=os.environ.get("PATH", "/usr/bin:/bin"),
            ENVIRONMENT="local",
            CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
            REDIS="FALSE",
            CHAOS_MUD="FALSE",
            LISTEN_ADDRESS="127.0.0.1",
            DURIS_TLS_PORT=str(tls_port),
            DURIS_WEBSOCKET_PORT=str(websocket_port),
            DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
        )
        process = None
        output = None
        client = None

        def stop() -> None:
            nonlocal process, output, client
            if client:
                client.close()
                client = None
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process = None
            if output:
                output.close()
                output = None

        def boot() -> None:
            nonlocal process, output
            output = (runtime / "server.out").open("w", encoding="utf-8")
            process = subprocess.Popen(
                [str(runtime / "bin/server/dms"), "--minimal", "-s", str(port)],
                cwd=runtime,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            deadline = time.monotonic() + 90
            while "Entering game loop." not in (runtime / "server.out").read_text(
                encoding="utf-8", errors="replace"
            ):
                require(process.poll() is None, "server exited during boot")
                require(time.monotonic() < deadline, "server boot timed out")
                time.sleep(0.1)

        try:
            boot()
            client = journey.MudClient(port)
            journey.create_character(client, class_name="3")
            client.send("save")
            client.expect("Saving Taverek.")
            client.send("quit")
            client.expect("ACCOUNT MENU", timeout=30)
            stop()
            sql("UPDATE player_data SET level=62,highest_level=62,base_hit=200000,hit_diff=0 "
                "WHERE name='" + journey.CHARACTER + "'")

            boot()
            client = journey.reconnect_character(port)
            drain(client)
            for vnum in (22801, 22802, 22803):
                client.send(f"givepet Taverek {vnum}")
                response = drain(client)
                require("not loadable" not in response.lower(), response)
            client.send("look")
            room = client.expect("Pos: standing >")
            for description in ("A bound healer", "A bound striker", "A bound witness"):
                require(description in room, f"missing fixture pet {description}:\n{room}")

            if not enabled:
                client.send("order healer cast 'heal' Taverek")
                heal = client.expect("Ok.", timeout=15) + drain(client, 1.0)
                require("My deity has warned me" not in heal, heal)
                client.send("order striker kill raoul")
                attack = client.expect("Ok.", timeout=15) + drain(client, 1.0)
                require("My deity has warned me" not in attack, attack)
                print(
                    "PASS disabled: ordered heal and attack accepted (2/2), no refusal",
                    flush=True,
                )
            else:
                client.send("order healer frobnicate")
                unknown = client.expect("Ok.", timeout=15) + drain(client)
                require("My deity has warned me" not in unknown, unknown)

                client.send("order healer abort")
                exempt = client.expect("Ok.", timeout=15) + drain(client)
                require("My deity has warned me" not in exempt, exempt)

                client.send("order healer cast 'heal' Taverek")
                heal = client.expect("My deity has warned me", timeout=15)
                heal += drain(client)
                require("Ok." not in heal, heal)

                # The command is sent immediately. The master's ordinary combat-round
                # wait delays dispatch, while the eight-second test lock keeps this
                # execution inside the same refusal window.
                client.send("order healer kill raoul")
                retry = client.expect("still refusing that order", timeout=15)
                retry += drain(client)
                require("My deity has warned me" not in retry, retry)
                require("Ok." not in retry, retry)

                client.send("order striker ki raoul")
                attack = client.expect("My deity has warned me", timeout=15)
                attack += drain(client)
                require("Ok." not in attack, attack)

                client.send("order followers say mixed-accepted")
                mixed = client.expect("mixed-accepted", timeout=20)
                mixed += drain(client)
                require("Ok." in mixed, mixed)
                require("None here are loyal" not in mixed, mixed)
                print(
                    "PASS enabled: ordered heal and attack refused (0/2 cleric "
                    "dispatches), retry stayed locked, mixed non-cleric acted",
                    flush=True,
                )
        except Exception:
            print((runtime / "server.out").read_text(errors="replace")[-8000:])
            print(journey.runtime_logs(runtime)[-12000:])
            if client:
                print(client.transcript.decode(errors="replace")[-10000:])
            raise
        finally:
            stop()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_divine_refusal_journey.py /path/to/mariadb/dms", file=sys.stderr)
        return 2
    binary = Path(sys.argv[1]).resolve()
    require(binary.is_file(), f"server binary does not exist: {binary}")
    run_scenario(binary, False)
    run_scenario(binary, True)
    print(
        "Divine refusal disposable A/B complete; forced boundaries are not a DPS estimate.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
