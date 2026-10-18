#!/usr/bin/env python3
"""Qualify #57 through disposable full-world Telnet sessions and scheduler traces.

Use a fresh flat-file binary. No checkout credentials or existing player data are read.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time

import test_flatfile_combat_journey as journey
from run_divine_refusal_journey import drain
from run_item_pilot_journey import Server
from run_paladin_balance_journey import command

ROOT = journey.ROOT
NAME = "Regenreader"
TRACE = re.compile(r"PLAYER EVENT TIMING: func=event_mana_regen sequence=\d+ "
                   r"ch_pid=(\d+) due_tick=(\d+) actual_tick=(\d+)")


def player_command(client, text, duration=.5):
    drain(client, .05)
    client.send(text)
    return drain(client, duration)


def run(binary):
    with tempfile.TemporaryDirectory(prefix="psp-journey-", dir=ROOT / "bin") as directory:
        root = Path(directory)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir(); state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        (runtime / "logs/log").mkdir(parents=True)
        for name in ("areas", "areas_mini", "docs"):
            (runtime / name).symlink_to(ROOT / name, target_is_directory=True)
        shutil.copytree(ROOT / "lib", runtime / "lib")
        properties = runtime / "lib/duris.properties"
        properties.write_text(properties.read_text().replace("camp.timer=9.000", "camp.timer=2.000"))
        journey.generate_certificate(runtime)
        server = Server(binary, runtime, state, "psp", {
            "DURIS_NEVENT_TRACE_PLAYER": "1", "CREATION_ALL_CLASSES": "TRUE",
        })
        player = None
        result = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
        try:
            server.start(full_world=True)
            staff = server.client = journey.MudClient(server.port)
            journey.create_character(staff, expected_room=None)
            staff.send("save"); staff.expect("Save complete for Taverek.")
            staff.send("quit"); staff.expect("ACCOUNT MENU", timeout=45)
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            server.start(full_world=True)
            staff = server.client = journey.reconnect_character(server.port, expected_room=None)
            command(staff, "vis 0")
            command(staff, f"setbit char {journey.CHARACTER} pcact PAGING_ON 0")
            player = journey.MudClient(server.port, source_host="127.0.0.2")
            journey.create_character(player, expected_room=None, account=NAME, character=NAME,
                                     email="regen@example.invalid")
            player_command(player, "toggle boon")
            player_command(player, "remove all")
            command(staff, f"transfer {NAME}")
            command(staff, f"affectpurge {NAME} 'well-rested bonus'")
            for field, value in (("class", "Psionicist"), ("level", "50"),
                                 # Human's configured +5 racial bonus yields current 100.
                                 ("pow", "95"), ("int", "95"), ("mxmana", "10000"),
                                 ("skill", "'meditate' 75"),
                                 ("skill", "'adrenaline control' 100")):
                text = command(staff, f"setbit char {NAME} {field} {value}")
                assert "Invalid" not in text and "Valid flags" not in text, text
            identity = command(staff, f"stat char {NAME}")
            player_id = int(re.search(r"ID numb: (\d+)", identity)[1])

            def rows():
                text = (runtime / "logs/log/status").read_text(errors="replace")
                return [tuple(map(int, m.groups())) for m in TRACE.finditer(text)
                        if int(m[1]) == player_id]

            def sample():
                before = rows()
                text = command(staff, f"stat char {NAME}")
                after = rows()
                m = re.search(r"Mana:\s*\[\s*(-?\d+)\s*/\s*(\d+)\s*/\s*\d+\s*\+\s*(-?\d+)\]", text)
                assert m, text
                stats = [int(re.search(rf"{label}:\s*(\d+)", text)[1]) for label in ("Pow", "Int")]
                assert stats == [100, 100], stats
                return {"mana": int(m[1]), "maximum": int(m[2]), "rate": int(m[3]),
                        "tick_low": before[-1][2] if before else 0,
                        "tick_high": after[-1][2] if after else 0,
                        "callbacks": len(after)}

            def set_mana(value):
                command(staff, f"setbit char {NAME} mana {value}")

            print("Full-world PSP fixture ready", flush=True)
            result["dial_samples"] = []
            for dial, rate in ((5, 80), (1, 160), (10, 40)):
                command(staff, f"difficulty set player.recovery {dial}")
                set_mana(1000)
                player_command(player, "rest")
                player_command(player, "stand")
                before = sample()
                assert before["rate"] == rate, before
                target = before["tick_high"] + 120
                deadline = time.monotonic() + 40
                while rows()[-1][2] < target:
                    assert time.monotonic() < deadline, "no ongoing PSP callback"
                    time.sleep(.1)
                after = sample()
                low = (after["tick_low"] - before["tick_high"]) * rate / 300 - 1
                high = (after["tick_high"] - before["tick_low"]) * rate / 300 + 1
                gain = after["mana"] - before["mana"]
                assert low <= gain <= high and after["rate"] == rate, (before, after, low, high)
                result["dial_samples"].append({"dial": dial, "before": before, "after": after})
                print("Recovery dial", dial, "gain", gain, "rate", rate, flush=True)
            command(staff, "difficulty set player.recovery 5")

            set_mana(sample()["maximum"] - 400)
            player_command(player, "rest")
            response = player_command(player, "meditate")
            assert "meditat" in response.lower(), response
            med = sample()
            assert med["rate"] == 1500, med
            player.expect("Your mana reserves are now full.", timeout=60)
            time.sleep(1)  # Let the asynchronous status logger flush the final callback.
            full = sample()
            assert full["mana"] == full["maximum"], full
            time.sleep(.6)
            assert sample()["callbacks"] == full["callbacks"], "full PSP kept scheduling"
            player_command(player, "stand")
            result["meditation"] = {"during": med, "full": full,
                "completion_messages": bytes(player.transcript).count(b"Your mana reserves are now full.")}
            assert result["meditation"]["completion_messages"] == 1
            print("Meditation completion and event termination passed", flush=True)

            # Full reserve -> real will/cast dispatch -> expenditure -> one recovery chain.
            for cls in ("Psionicist", "MindFlayer"):
                command(staff, f"setbit char {NAME} class {cls}")
                set_mana(full["maximum"])
                time.sleep(1)
                idle = sample()
                time.sleep(.6)
                assert sample()["callbacks"] == idle["callbacks"]
                player.send("will 'adrenaline control'")
                player.expect("Your mental manipulations become a reality", timeout=30)
                cast = sample()
                assert cast["mana"] < cast["maximum"] and cast["callbacks"] > idle["callbacks"], cast
                result[cls + "_casting"] = cast
            print("Psionicist and mindflayer casting restarts passed", flush=True)
            command(staff, f"setbit char {NAME} class Psionicist")

            set_mana(1000)
            pending = sample()
            assert pending["rate"] == 80
            response = player_command(player, "hit dummy", 2)
            fighting = sample()
            assert fighting["rate"] == 0, (response, fighting)
            time.sleep(5)
            still = sample()
            assert still["mana"] == fighting["mana"] and still["rate"] == 0, (fighting, still)
            assert still["callbacks"] == fighting["callbacks"], (fighting, still)
            command(staff, f"tranquilize {NAME}")
            player_command(player, "wake")
            player_command(player, "stand")
            start = time.monotonic()
            while True:
                recovered = sample()
                if recovered["mana"] > still["mana"]:
                    break
                assert time.monotonic() - start < 77, "periodic combat-exit restart failed"
                time.sleep(.5)
            result["combat"] = {"entry": fighting, "blocked": still, "recovered": recovered,
                                "restart_seconds": round(time.monotonic() - start, 3)}
            print("Combat suppression and periodic restart passed", flush=True)

            # Use the just-cast affect as a disposable signed-modifier fixture. A normal
            # staff character edit runs balance_affects/affect_total, the real restart path.
            text = command(staff, f"stat char {NAME}")
            affects = re.findall(r"\S+\s+by\s+-?\d+\s+for\s+-?\d+\s+from '([^']+)'", text)
            index = affects.index("adrenaline control")
            command(staff, f"setbit aff {NAME}{index} dur 1000")
            command(staff, f"setbit aff {NAME}{index} loc MANA_REG")
            command(staff, f"setbit aff {NAME}{index} mod -80")
            command(staff, f"setbit char {NAME} hunger 24")
            time.sleep(.6)
            zero = sample()
            assert zero["rate"] == 0, zero
            time.sleep(2)
            assert sample()["mana"] == zero["mana"]
            command(staff, f"setbit aff {NAME}{index} mod 10")
            command(staff, f"setbit char {NAME} hunger 24")
            time.sleep(2)
            positive = sample()
            assert positive["rate"] == 90 and positive["mana"] > zero["mana"], (zero, positive)
            result["modifier_restart"] = {"zero": zero, "positive": positive}
            command(staff, f"affectpurge {NAME} 'adrenaline control'")
            print("Zero-to-positive affect modifier restart passed", flush=True)
            entries = rows()
            assert len({(r[0], r[2]) for r in entries}) == len(entries), "duplicate PSP callback in one pulse"
            result["callback_count"] = len(entries)
            result["duplicate_psp_callbacks"] = 0
            return result
        except Exception:
            if "rows" in locals():
                print("PSP trace tail:", rows()[-20:])
            for client in (server.client, player):
                if client:
                    text = bytes(client.transcript).decode(errors="replace")
                    print(text.replace(journey.PASSWORD, "[REDACTED]")[-7000:])
            print(server.output_path.read_text(errors="replace")[-3000:])
            raise
        finally:
            if player: player.close()
            server.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.binary.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
