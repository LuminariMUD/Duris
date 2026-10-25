#!/usr/bin/env python3
"""Execute the trap dispatcher and native spells with controlled saves/lifetimes."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, HARNESS_STUBS, extract_function

magic = (SRC / "magic.c").read_text()
start = magic.rfind("typedef struct", 0, magic.index("} RemoveableSpellBit;"))
spells = magic[start:magic.index("void spell_dispel_magic(", start)]
spells += "\n".join(extract_function("magic.c", "void " + name + "(") for name in (
    "spell_dispel_magic", "spell_wither", "spell_harm", "spell_poison", "spell_minor_paralysis"))
spells += extract_function("affects.c", "void Stun(")
spells += extract_function("mobact.c", "void mobact_memoryHandle(")
spells += extract_function("interp.c", "char *one_argument(")
spells += extract_function("specs.shabo.c", "int pesky_imp_chest(")
spells += extract_function("specs.hoa.c", "int trap_tower1_para(")
spells += "\n".join(extract_function("utility.c", signature) for signature in (
    "int BOUNDED(", "int GET_CLASS(", "int IS_MORPH("))
harness = (ROOT / "tests/async/legacy_trap_effects_harness.cpp").read_text()
harness = harness.replace("// NATIVE_SPELLS", spells)
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="legacy-trap-effects-", dir=build) as directory:
    source = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    source.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql",
        str(source), "src/combat/trap.c", str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
print("legacy trap native spells and dispatch: passed (ASan/UBSan)")
