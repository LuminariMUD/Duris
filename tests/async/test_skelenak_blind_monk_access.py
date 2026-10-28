#!/usr/bin/env python3
"""Keep the blind monk's rock entrance and icy leggings quest reachable."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
AREAS = ROOT / "areas"


def record(path: Path, vnum: int) -> str:
    text = path.read_text(encoding="latin-1")
    match = re.search(rf"(?ms)^#{vnum}\n(.*?)(?=^#\d+\n|\Z)", text)
    assert match, f"missing VNUM {vnum} in {path}"
    return match[1]


def check() -> None:
    rock = record(AREAS / "obj/caves_skelenak.obj", 4027)
    fields = rock.split("~", 4)[4].strip().splitlines()
    assert int(fields[0].split()[0]) == 25, "rock must be an ITEM_TELEPORT"
    target, trigger, charges = map(int, fields[1].split()[:3])

    commands = (ROOT / "src/cmd/interp.h").read_text()
    climb = re.search(r"(?m)^#define CMD_CLIMB (\d+)\s*$", commands)
    assert climb, "climb command definition missing"
    assert (target, trigger, charges) == (4153, int(climb[1]), -1), (
        "rock must teleport to the monk using climb with unlimited charges",
        (target, trigger, charges),
    )

    interpreter = (ROOT / "src/cmd/interp.c").read_text()
    assert "CMD_N(CMD_CLIMB, STAT_NORMAL + POS_STANDING, do_climb," in interpreter
    dispatch = interpreter[interpreter.index("void command_interpreter("):]
    assert dispatch.index("check_item_teleport(exec_char,") < dispatch.index(
        "((*cmd_info[cmd].command_pointer)"), "portal must intercept climb before skill execution"
    teleport = (ROOT / "src/magic/magic.c").read_text()
    assert "generic_find(arg, FIND_OBJ_INV | FIND_OBJ_EQUIP | FIND_OBJ_ROOM" in teleport
    assert "obj->value[1] != cmd" in teleport

    resets = (AREAS / "zon/caves_skelenak.zon").read_text(encoding="latin-1")
    assert re.search(r"(?m)^O 0 4027 1 4110\b", resets), "rock must load beside the path"
    assert re.search(r"(?m)^M 0 4038 1 4153\b", resets), "monk must load atop the rock"
    top = record(AREAS / "wld/caves_skelenak.wld", 4153)
    assert re.search(r"(?m)^D5\n~\n~\n0 0 4110$", top), "monk's return exit missing"
    quest = record(AREAS / "qst/caves_skelenak.qst", 4038)
    assert re.search(r"(?m)^R I 4029$", quest), "icy leggings reward missing"
    assert "leggings frozen icy" in record(AREAS / "obj/caves_skelenak.obj", 4029)

    print("PASS: climb rock reaches the blind monk, returns, and retains icy leggings quest")


if __name__ == "__main__":
    check()
