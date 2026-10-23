#!/usr/bin/env python3
"""Execute command handlers, core state and native ANSI formatting together."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function
with tempfile.TemporaryDirectory(prefix="divine-commands-",dir=ROOT / "bin/tests") as tmp:
    directory=Path(tmp)
    harness=(ROOT / "tests/async/divine_boon_commands_harness.cpp").read_text()
    registry=(ROOT / "src/cmd/interp.c").read_text()
    registry=registry[registry.index("const char *command[MAX_CMD]"):registry.index("const char *fill_words")]
    harness=harness.replace("int main()",registry+"int main()")
    checks = """assert(std::string(command[CMD_BOON - 1]) == "boon");
    assert(std::string(command[CMD_QVIEW - 1]) == "qview");
    assert(std::string(command[CMD_QINFO - 1]) == "qinfo");
    assert(std::string(command[CMD_DIVINEBOON - 1]) == "divineboon");
    assert(command[MAX_CMD - 1][0] == 10);
    """
    harness=harness.replace("int main()"+chr(10)+"{", "int main()"+chr(10)+"{"+chr(10)+checks)
    native="\n".join(extract_function("core/utility.c",signature) for signature in
        ["string strip_ansi(","string pad_ansi("])
    (directory / "commands.cpp").write_text(harness.replace("// NATIVE_ANSI_FUNCTIONS",native))
    subprocess.run(["g++","-std=c++20","-g","-Og","-Wall","-Wextra","-Werror",
        "-fsanitize=address,undefined","-fno-omit-frame-pointer","-fno-pie","-no-pie",
        "-Isrc","-I/usr/include/mysql",str(directory / "commands.cpp"),
        "src/economy/divine_boon_commands.c","src/economy/divine_boon.c","-lcrypto",
        "-o",str(directory / "commands")],cwd=ROOT,check=True)
    subprocess.run([str(directory / "commands")],cwd=ROOT,check=True)
source=(ROOT / "src/cmd/interp.c").read_text()
assert "CMD_Y(CMD_BOON, STAT_SLEEPING + POS_PRONE, do_divine_boon, 0, FALSE)" in source
assert "CMD_Y(CMD_DIVINEBOON, STAT_DEAD + POS_PRONE, do_divineboon, IMMORTAL, FALSE)" in source
assert "#define CMD_BOON 804" in (ROOT / "src/cmd/interp.h").read_text()
toggle=(ROOT / "src/cmd/actoth.c").read_text().split("case 55:",1)[1].split("case 56:",1)[0]
assert "PLR2_TOG" not in toggle and "apply automatically" in toggle
