#!/usr/bin/env python3
"""Validate authored pilot gloves with the production server valuation function."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

PILOT = ((21575, "clfhaven", 12), (500110, "surface", 18),
         (76052, "cosmic", 24), (5817, "minizones", 30))


def record(vnum, source):
    text = (ROOT / f"areas/obj/{source}.obj").read_text()
    return re.search(rf"^#{vnum}\n.*?(?=^#\d+\n|^\$~)", text, re.M | re.S).group()


if __name__ == "__main__":
    tree = ast.parse((ROOT / "tests/async/test_monk_glove_tools.py").read_text())
    code = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "RUNTIME" for t in n.targets))
    code = code.split("int main() {", 1)[0]
    code = code.replace("return spell == 32 ? 1 : 0;", "return spell == 37 ? 3 : 0;")
    # Pin the fixture's circle to the actual spell registration, not a guessed ID.
    skills = (ROOT / "src/classes/skills.c").read_text().split('SPELL_CREATE("shocking grasp"', 1)[1].split("SPELL_CREATE", 1)[0]
    circles = [int(n) for n in re.findall(r"(?:SPEC_)?SPELL_ADD\(CLASS_[A-Z_]+, (\d+)", skills)]
    assert min(circles) == 3
    baselines = json.loads((ROOT / "docs/ongoing-projects/monk-proc-research/monk-glove-ivalues.json").read_text())
    statements = []
    for vnum, source, level in PILOT:
        text = record(vnum, source)
        lines = text.split("~", 4)[4].strip().splitlines()
        header, values, base = (list(map(int, lines[i].split())) for i in range(3))
        assert header[0] in (9, 11) and header[7] & 128 and header[8] & (1 << 19)
        assert values[5:] == [37, level, 60]
        assert "A spark leaps from $p as your barehand strike lands!" in text
        # Authored object format requires all E descriptions before A modifiers.
        assert text.index("E\n_char_msg~") < re.search(r"^A\s*$", text, re.M).start()
        fields = [f"obj.type={header[0]}; obj.wear_flags={header[7]}u; obj.extra_flags={header[6]}u;",
                  f"obj.extra2_flags={header[8]}u; obj.anti_flags={header[9]}u; obj.anti2_flags={header[10]}u;"]
        fields += [f"obj.value[{i}]={value};" for i, value in enumerate(values)]
        fields += [f"obj.bitvector{i+1 if i else ''}={value}u;" for i, value in enumerate(base[3:])]
        fields += [f"obj.affected[{i}].location={where}; obj.affected[{i}].modifier={mod};"
                   for i, (where, mod) in enumerate(re.findall(r"^A\s*\n(-?\d+) (-?\d+)", text, re.M))]
        statements += ["{ obj_data obj{};", *fields,
            "const int after=itemvalue(&obj); obj.extra2_flags &= ~ITEM2_MONK_PROC;",
            "obj.value[5]=obj.value[6]=obj.value[7]=0; const int before=itemvalue(&obj);",
            f"assert(before == {baselines[str(vnum)]['ivalue']} && after > before);",
            f'std::printf("{vnum}: %d -> %d\\n", before, after); }}']
    code += "int main() {\n" + "\n".join(statements) + "\n}\n"
    code = code.replace("// FUNCTIONS", "")
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="monk-pilot-value-", dir=ROOT / "bin/tests") as tmp:
        source = Path(tmp) / "pilot.cpp"; binary = source.with_suffix("")
        source.write_text(code)
        subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            "-fno-omit-frame-pointer", "-Isrc", str(source), str(HARNESS_STUBS),
            "src/item/item_value.c", "src/item/item_value_runtime.c", "-o", str(binary)],
            cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env=dict(os.environ,
            ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))

    # Reuse the scheduler fixture, then execute the actual dispatcher and selected
    # spell. Only the save, damage sink and dice endpoints are controlled here.
    fixture_path = ROOT / "tests/async/test_weapon_actions_runtime.py"
    scope = {"__file__": str(fixture_path)}
    prefix = fixture_path.read_text().split('\n(ROOT / "bin/tests").mkdir', 1)[0]
    exec(compile(prefix, str(fixture_path), "exec"), scope)
    bodies = "\n".join(extract_function("magic.c", signature) for signature in (
        "static int shocking_grasp_damage(", "static int shocking_grasp_failed_save(",
        "void spell_shocking_grasp("))
    cases = ",".join("{" + f"{vnum},{level}" + "}" for vnum, _, level in PILOT)
    proof = r'''
#include "abilities/abilities.h"
static int pilot_dice(int count, int sides) { assert(sides == 6); return count; }
const Rolls live_rolls = {pilot_dice, number};
int get_default_save_mod(P_char, P_char, int, int) { return 0; }
bool NewSaves(P_char, int, int) { return false; }
// SPELLS
int main() {
    nevent_bind_game_thread(); ne_dead_event_pool = &test_pool;
    fake_clock_ns = 1000000000ULL; ne_events();
    struct glove { int vnum, level; };
    int opportunities=0, activations=0;
    for (auto item : std::initializer_list<glove>{ // CASES
    }) for (int actor_level : {1,30,56}) for (int spec : {0,1,2,3})
    for (bool pressure : {false,true}) {
        weapon_scene s("weapons", false); s.packed();
        obj_index[0].virtual_number=item.vnum;
        s.actor->player.m_class=CLASS_MONK; s.actor->player.level=actor_level;
        s.actor->player.spec=spec;
        s.actor->equipment[WIELD]=nullptr; s.actor->equipment[WEAR_HANDS]=s.source;
        s.source->type=ITEM_ARMOR; s.source->wear_flags=ITEM_WEAR_HANDS;
        s.source->extra2_flags=ITEM2_MONK_PROC;
        s.source->value[5]=37; s.source->value[6]=item.level; s.source->value[7]=60;
        skills[37].spell_pointer=spell_shocking_grasp; skills[37].targets=TAR_AGGRO;
        for (int roll=0; roll<60; ++roll) {
            effects.clear(); choices={roll}; ++opportunities;
            if (pressure) assert(monk_superhit(s.actor,s.target,nullptr));
            else dispatch_monk_glove_proc(capture_monk_glove_proc(s.actor,s.target,nullptr));
            assert(choices.empty() && effects.size() == (roll == 0 ? 1 : 0));
            if (!roll) {
                ++activations;
                assert(effects[0].power == (item.level/6+5)*4*2);
                assert(effects[0].target == s.target->runtime_id);
            }
        }
    }
    assert(opportunities == activations*60);
    std::printf("pilot dispatcher: %d qualifying opportunities, %d activations; fixed spell levels across actor levels/specs and both hooks\n", opportunities, activations);
}
'''.replace("// SPELLS", bodies).replace("// CASES", cases)
    doubles = scope["DOUBLES"].split("int main() {", 1)[0] + proof
    doubles = doubles.replace("messages", "captured_messages").replace("damage_captured_messages", "damage_messages")
    with tempfile.TemporaryDirectory(prefix="monk-pilot-dispatch-", dir=ROOT / "bin/tests") as tmp:
        source = Path(tmp) / "dispatch.cpp"; binary = source.with_suffix("")
        source.write_text(scope["platform"] + scope["fixture"] +
                          doubles.replace("// INSERT_CALLBACKS", scope["callbacks"]))
        subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-ffunction-sections", "-fdata-sections",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-pthread", "-Isrc",
            str(source), "src/persistence/latency_trace.c", "-Wl,--gc-sections", str(HARNESS_STUBS),
            "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env=dict(os.environ,
            ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1",
            DURIS_NEVENT_ANALYTICS="0", DURIS_NEVENT_BUDGET_USEC="0", DURIS_NEVENT_MAX_CALLBACKS="0"))
