#!/usr/bin/env python3
"""Keep the blind monk's rock entrance and icy leggings quest reachable."""

from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
AREAS = ROOT / "areas"


def record(path: Path, vnum: int) -> str:
    text = path.read_text(encoding="latin-1")
    match = re.search(rf"(?ms)^#{vnum}\n(.*?)(?=^#\d+\n|\Z)", text)
    assert match, f"missing VNUM {vnum} in {path}"
    return match[1]



def check_climb_targeting(teleport: str) -> None:
    """Compile the production lookup branch with isolated object-targeting stubs."""
    selection = re.search(
        r"(?s)bool check_item_teleport\(P_char ch, char \*arg, int cmd\).*?"
        r"\n\troom = ch->in_room;\n(.*?)\n\tif \(!obj\)", teleport,
    )
    assert selection, "cannot extract actual item teleport lookup branch"
    harness = r"""
#include <cassert>
#include <cstring>

struct Object {
    const char *name;
    int type;
    int value[8];
    Object *next_content;
};
struct Character { int in_room; Object *carrying; };
struct Room { Object *contents; };
using P_obj = Object *;
using P_char = Character *;
Room world[1] = {};
enum {
    CMD_NORTH = 1, CMD_DOWN = 6, CMD_NORTHWEST = 541, CMD_SE = 548,
    CMD_CLIMB = 556, ITEM_TELEPORT = 25,
    FIND_OBJ_INV = 1, FIND_OBJ_EQUIP = 2, FIND_OBJ_ROOM = 4
};

// Model the documented inventory-first generic_find selection order.
void generic_find(char *arg, int flags, P_char ch, P_char *target, P_obj *obj) {
    *target = nullptr;
    *obj = nullptr;
    if (!arg || !*arg) return;
    if ((flags & FIND_OBJ_INV) && ch->carrying &&
        std::strcmp(arg, ch->carrying->name) == 0) {
        *obj = ch->carrying;
        return;
    }
    if ((flags & FIND_OBJ_ROOM) && world[ch->in_room].contents &&
        std::strcmp(arg, world[ch->in_room].contents->name) == 0)
        *obj = world[ch->in_room].contents;
}

P_obj select_climb_target(P_char ch, char *arg, int cmd) {
    P_obj obj = nullptr, obj_next;
    P_char dummy = nullptr;
    int room = ch->in_room;
    (void)room;
    /* PRODUCTION_LOOKUP */
    return obj;
}

int main() {
    Object roomRock = {"rock", ITEM_TELEPORT, {4153, CMD_CLIMB, -1}, nullptr};
    Object carriedRing = {"rock", 11, {}, nullptr};
    Object carriedPortal = {"rock", ITEM_TELEPORT, {9999, CMD_CLIMB, -1}, nullptr};
    Character player = {0, &carriedRing};
    world[0].contents = &roomRock;
    char rock[] = "rock";
    char empty[] = "";
    // A non-portal ring cannot shadow the quest entrance.
    assert(select_climb_target(&player, rock, CMD_CLIMB) == &roomRock);
    assert(roomRock.value[0] == 4153);
    // Bare climb stays with do_climb; it must not select the portal.
    assert(select_climb_target(&player, empty, CMD_CLIMB) == nullptr);
    // Preserve legitimate carried-portal precedence.
    player.carrying = &carriedPortal;
    assert(select_climb_target(&player, rock, CMD_CLIMB) == &carriedPortal);
    player.carrying = nullptr;
    assert(select_climb_target(&player, rock, CMD_CLIMB) == &roomRock);
}
""".replace("/* PRODUCTION_LOOKUP */", selection[1])
    with tempfile.TemporaryDirectory(prefix="skelenak-climb-") as tmp:
        source = Path(tmp) / "lookup.cpp"
        binary = Path(tmp) / "lookup"
        source.write_text(harness)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


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

    # A carried non-teleport named 'rock' must not shadow the room entrance.
    # generic_find checks inventory before room objects; retry room-only after a
    # nonmatching carried item, without overriding a matching carried portal.
    handler = (ROOT / "src/world/handler.c").read_text()
    find = handler[handler.index("int generic_find("):]
    assert find.index("FIND_OBJ_INV") < find.index("FIND_OBJ_ROOM"), (
        "expected inventory-first targeting, regression scenario no longer applies"
    )
    climb_fallback = re.search(
        r"(?s)if\s*\(cmd\s*==\s*CMD_CLIMB\s*&&\s*"
        r"\(!obj\s*\|\|\s*obj->type\s*!=\s*ITEM_TELEPORT\s*\|\|\s*"
        r"obj->value\[1\]\s*!=\s*cmd\)\)\s*"
        r"\{\s*generic_find\(arg,\s*FIND_OBJ_ROOM,\s*ch,\s*&dummy,\s*&obj\);",
        teleport,
    )
    assert climb_fallback, "a carried ordinary 'rock' must not block climb rock"

    resets = (AREAS / "zon/caves_skelenak.zon").read_text(encoding="latin-1")
    assert re.search(r"(?m)^O 0 4027 1 4110\b", resets), "rock must load beside the path"
    assert re.search(r"(?m)^M 0 4038 1 4153\b", resets), "monk must load atop the rock"
    top = record(AREAS / "wld/caves_skelenak.wld", 4153)
    assert re.search(r"(?m)^D5\n~\n~\n0 0 4110$", top), "monk's return exit missing"
    quest = record(AREAS / "qst/caves_skelenak.qst", 4038)
    assert re.search(r"(?m)^R I 4029$", quest), "icy leggings reward missing"
    assert "leggings frozen icy" in record(AREAS / "obj/caves_skelenak.obj", 4029)

    check_climb_targeting(teleport)
    print("PASS: blind monk portal content and climb object-selection regression")


if __name__ == "__main__":
    check()
