#!/usr/bin/env python3
"""Execute production Elemental Groves reset code with deterministic engine services."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

from test_castle_key_reset import production_source, records

ROOT = Path(__file__).resolve().parents[2]
# key, source, holder (mobile or pedestal), home, near room, direction, far room
GATES = (
    (3800, "carrier", 3811, 3900, 3899, 1, 3898),
    (3801, "carrier", 3812, 3898, 3898, 2, 3897),
    (3802, "carrier", 3813, 3909, 3910, 1, 3911),
    (3803, "carrier", 3814, 3910, 3910, 2, 3908),
    (3804, "carrier", 3815, 3919, 3921, 3, 3922),
    (3805, "carrier", 3816, 3921, 3921, 0, 3920),
    (3806, "carrier", 3817, 3925, 3926, 3, 3928),
    (3807, "carrier", 3818, 3928, 3928, 0, 3927),
    (3808, "floor", 0, 3854, 3951, 4, 3952),
    (3809, "floor", 0, 3823, 3947, 4, 3953),
    (3810, "pedestal", 3818, 3897, 3960, 0, 3961),
    (3811, "pedestal", 3818, 3908, 3961, 0, 3962),
    (3812, "pedestal", 3818, 3920, 3962, 0, 3963),
    (3813, "pedestal", 3818, 3927, 3963, 0, 3964),
    (3814, "pedestal", 3818, 3952, 3964, 0, 3965),
    (3815, "pedestal", 3819, 3953, 3965, 0, 3966),
)
REVERSE = (2, 3, 0, 1, 5, 4)
KEYS = {g[0] for g in GATES}
PEDESTALS = {g[2] for g in GATES if g[1] == "pedestal"}
CARRIERS = {g[2] for g in GATES if g[1] == "carrier"}
OUTSIDE = 5760


def element_data():
    rooms = records((ROOT / "areas/wld/element.wld").read_text(encoding="latin-1"))
    exits = {}
    for room, block in rooms.items():
        for match in re.finditer(
                r"(?m)^D(\d+)\s*\n(.*?)~\s*(.*?)~\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)",
                block, re.S):
            direction, _, _, flags, key, destination = match.groups()
            exits[room, int(direction)] = (int(destination), int(key), int(flags))
    rows = []
    for line in (ROOT / "areas/zon/element.zon").read_text(encoding="latin-1").splitlines():
        if re.match(r"^[A-Z] ", line):
            fields = line.split("*")[0].split()
            rows.append((fields[0], tuple(map(int, fields[1:]))))
    return rooms, exits, rows


def check_contract(exits, rows):
    """Each gate key breaks on use, has one source row, and opens both sides."""
    objects = records((ROOT / "areas/obj/element.obj").read_text(encoding="latin-1"))
    for key in KEYS:
        numeric = objects[key].split("~")[4].strip().splitlines()
        assert int(numeric[0].split()[0]) == 18, key
        assert int(numeric[1].split()[1]) == 100, key
    sources, previous = {}, None
    for command, args in rows:
        if command in ("E", "G") and args[1] in KEYS:
            assert previous[0] == "M" and args[2] == 1, (command, args)
            sources[args[1]] = ("carrier", previous[1][1], previous[1][3])
        elif command == "O" and args[1] in KEYS:
            assert args[2] == 1 and args[4] == 100, args
            sources[args[1]] = ("floor", 0, args[3])
        elif command == "P" and args[1] in KEYS:
            assert previous[0] == "O" and previous[1][1] == args[3], (command, args)
            assert args[0] == 1 and args[2] == 1, args
            sources[args[1]] = ("pedestal", args[3], previous[1][3])
        if command in ("M", "O"):
            previous = (command, args)
    doors = {(args[1], args[2]): args[3] for command, args in rows if command == "D"}
    for key, source, holder, home, near, direction, far in GATES:
        assert sources[key] == (source, holder, home), key
        assert exits[near, direction][:2] == (far, key), key
        assert exits[far, REVERSE[direction]][0] == near, key
        assert doors[near, direction] == doors[far, REVERSE[direction]] == 2, key


def fixture_source():
    rooms, exits, rows = element_data()
    check_contract(exits, rows)
    selected, keep = [], False
    for command, args in rows:
        if command in ("M", "F", "O"):
            keep = ((command == "M" and args[1] in CARRIERS) or
                    (command == "O" and (args[1] in KEYS or args[1] in PEDESTALS)))
        if command == "D" or (keep and command in ("M", "E", "G", "O", "P")):
            selected.append((command, args))
    objects = sorted({args[1] for c, args in selected if c in ("E", "G", "O", "P")})
    result = ["static void load_fixture() {"]
    result += [f"add_room({v}, {0 if v == OUTSIDE else 1});"
               for v in sorted(set(rooms) | {OUTSIDE})]
    result += [f"add_index(mob_index, {v});" for v in sorted(CARRIERS)]
    result += [f"add_index(obj_index, {v}, {'false' if v in PEDESTALS else 'true'});"
               for v in objects]
    result += [f"add_exit({r}, {d}, {dest}, {key}, {flags});"
               for (r, d), (dest, key, flags) in exits.items()]
    result += ["zone_table[1].cmd = {"]
    result += ["{'" + c + "', " + ", ".join(map(str, args)) + "}," for c, args in selected]
    result += ["{'S', 0, 0, 0, 0, 0, 0, 0, 0}};", "renumber_commands();", "}"]
    return "\n".join(result)


def main():
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    harness = (ROOT / "tests/async/elemental_groves_key_reset_harness.cpp").read_text()
    harness = harness.replace("// PRODUCTION", production_source("MGEDOP!"))
    harness = harness.replace("// FIXTURE", fixture_source())
    with tempfile.TemporaryDirectory(prefix="element-reset-", dir=build_root) as temp:
        source, binary = Path(temp) / "test.cpp", Path(temp) / "test"
        source.write_text(harness)
        subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                        # Variables for omitted production reset cases are unused here.
                        "-Wno-unused-variable", "-Wno-unused-but-set-variable",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-fno-pie", "-no-pie", "-I", str(ROOT / "src"),
                        "-I", str(ROOT / "tests/async"),
                        str(source), "-o", str(binary)], check=True)
        failures = []
        for case in [str(g[0]) for g in GATES] + ["controls", "occupancy", "boundaries"]:
            result = subprocess.run([str(binary), case], capture_output=True, text=True,
                                    env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
            print(f"elemental groves reset {case}: {'PASS' if result.returncode == 0 else 'FAIL'}",
                  flush=True)
            if result.returncode:
                print(result.stdout + result.stderr, flush=True)
                failures.append(case)
        assert not failures, f"failed elemental groves reset cases: {failures}"


if __name__ == "__main__":
    main()
