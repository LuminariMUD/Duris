#!/usr/bin/env python3
"""Execute production castle reset/timer code with deterministic engine services."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
# key, carrier, home, near room, direction, far room, equipment slot (0 = G)
GATES = (
    (2405, 2406, 2427, 2414, 5, 2415, 18),
    (2418, 2415, 2439, 2427, 4, 2428, 0),
    (2422, 2418, 2452, 2446, 3, 2448, 0),
    (2425, 2419, 2456, 2460, 4, 2461, 18),
    (2436, 2433, 2481, 2471, 0, 2479, 0),
    (2437, 2420, 2477, 2480, 0, 2488, 4),
    (2438, 2428, 2493, 2480, 2, 2498, 18),
)
REVERSE = (2, 3, 0, 1, 5, 4)


def records(text):
    return {int(vnum): entry for entry, vnum in re.findall(
        r"(?ms)(^#(\d+)\s*\n.*?)(?=^#\d+\s*$|^\$~?$)", text)}


def castle_data():
    rooms = records((ROOT / "areas/wld/castle.wld").read_text())
    exits = {}
    for room, block in rooms.items():
        for match in re.finditer(
                r"(?m)^D(\d+)\s*\n(.*?)~\s*(.*?)~\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)",
                block, re.S):
            direction, _, _, flags, key, destination = match.groups()
            exits[room, int(direction)] = (int(destination), int(key), int(flags))
    rows = []
    for line in (ROOT / "areas/zon/castle.zon").read_text().splitlines():
        if re.match(r"^[A-Z] ", line):
            fields = line.split("*")[0].split()
            rows.append((fields[0], tuple(map(int, fields[1:]))))
    carrier = None
    sources = {}
    for command, args in rows:
        if command in ("M", "F"):
            carrier = args
        elif command in ("E", "G") and args[1] in {g[0] for g in GATES}:
            sources[args[1]] = (carrier[1], carrier[3], command, args[3], args[2], args[4])
    for key, mob, home, near, direction, far, slot in GATES:
        assert sources[key] == (mob, home, "E" if slot else "G", slot, 1, 100)
        assert exits[near, direction][:2] == (far, key)
        assert exits[far, REVERSE[direction]][:2] == (near, key)
    objects = records((ROOT / "areas/obj/castle.obj").read_text())
    for key, *unused in GATES:
        numeric = objects[key].split("~")[4].strip().splitlines()
        assert int(numeric[0].split()[0]) == 18
        assert int(numeric[1].split()[1]) == 100
    return rooms, exits, rows


def fixture_source():
    rooms, exits, rows = castle_data()
    carriers = {g[1] for g in GATES} | {2401}
    selected, use_carrier = [], False
    for command, args in rows:
        if command in ("M", "F"):
            use_carrier = command == "M" and args[1] in carriers
        if command == "D" or (use_carrier and command in ("M", "E", "G")):
            selected.append((command, args))
    objects = sorted({args[1] for c, args in selected if c in ("E", "G")} | {2434})
    result = ["static void load_fixture() {"]
    result += [f"add_room({v}, {0 if v == 5760 else 1});" for v in sorted(set(rooms) | {5760})]
    result += [f"add_index(mob_index, {v});" for v in sorted(carriers)]
    result += [f"add_index(obj_index, {v});" for v in objects]
    result += [f"add_exit({r}, {d}, {dest}, {key}, {flags});"
               for (r, d), (dest, key, flags) in exits.items()]
    result += ["zone_table[1].cmd = {"]
    result += ["{'" + c + "', " + ", ".join(map(str, args)) + "}," for c, args in selected]
    result += ["{'S', 0, 0, 0, 0, 0, 0, 0, 0}};", "renumber_commands();", "}"]
    return "\n".join(result)


def production_source():
    db = (ROOT / "src/world/db.c").read_text()
    events = (ROOT / "src/world/events.c").read_text()
    helper_start = db.find("static void restore_castle_reset_access(")
    helper = "" if helper_start < 0 else db[helper_start:db.index("#define ZCMD", helper_start)]
    start = db.index("void reset_zone(")
    reset = db[start:db.index("#undef ZCMD", start)]
    # Retain the production admission/loop, M/G/E/D bodies and finalization.
    # Other reset commands are absent from this fixture and rejected by default.
    reset = re.sub(r"(?ms)^\t\t\tcase '([^']+)':.*?(?=^\t\t\t(?:case |default:))",
                   lambda m: m[0] if m[1] in "MGED!" else "", reset)
    start = db.index("int is_empty(")
    empty = db[start:db.index("\n/************************************************************************", start)]
    start = events.index("void event_reset_zone(")
    event = events[start:events.index("\nvoid room_event(", start)]
    return helper + "\n#define ZCMD zone_table[zone].cmd[cmd_no]\n" + reset + "\n#undef ZCMD\n" + empty + event


def main():
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    harness = (ROOT / "tests/async/castle_key_reset_harness.cpp").read_text()
    harness = harness.replace("// PRODUCTION", production_source())
    harness = harness.replace("// FIXTURE", fixture_source())
    with tempfile.TemporaryDirectory(prefix="castle-reset-", dir=build_root) as temp:
        source, binary = Path(temp) / "test.cpp", Path(temp) / "test"
        source.write_text(harness)
        subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                        # Variables for omitted production reset cases are unused here.
                        "-Wno-unused-variable", "-Wno-unused-but-set-variable",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-fno-pie", "-no-pie", "-I", str(ROOT / "src"),
                        str(source), "-o", str(binary)], check=True)
        failures = []
        for case in [str(g[0]) for g in GATES] + ["controls", "occupancy", "boundaries"]:
            result = subprocess.run([str(binary), case], capture_output=True, text=True,
                                    env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
            print(f"castle reset {case}: {'PASS' if result.returncode == 0 else 'FAIL'}", flush=True)
            if result.returncode:
                print(result.stdout + result.stderr, flush=True)
                failures.append(case)
        assert not failures, f"failed castle reset cases: {failures}"


if __name__ == "__main__":
    main()
