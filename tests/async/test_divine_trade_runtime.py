#!/usr/bin/env python3
"""Execute real cargo producer, reservation and completion paths with a controlled world."""
import subprocess
import tempfile
from pathlib import Path
from _paths import ROOT, extract_function
with tempfile.TemporaryDirectory(prefix="divine-runtime-",dir=ROOT / "bin/tests") as temporary:
    binary=Path(temporary) / "runtime"
    source=Path(temporary) / "runtime.cpp"
    harness=(ROOT / "tests/async/divine_trade_runtime_harness.cpp").read_text()
    split="\n".join(extract_function("cmd/actoth.c",signature) for signature in
                    ["static bool split_wallet_change(", "void do_split("])
    source.write_text(harness.replace("// SPLIT_FUNCTIONS",split))

    subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-Wno-unused-parameter",
        "-Wno-missing-field-initializers","-g","-O1","-fsanitize=address,undefined",
        "-ffunction-sections","-fdata-sections","-Isrc","-I/usr/include/mysql",
        str(source),"src/economy/divine_trade_runtime.c",
        "src/economy/divine_trade.c","src/economy/divine_boon.c","src/economy/divine_trade_command.c",
        "src/economy/currency_transaction.c","src/economy/currency_command.c",
        "src/persistence/critical_command.c","src/player/player_snapshot_codec.c",
        "-Wl,--gc-sections","-lcrypto","-o",str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],cwd=ROOT,check=True,timeout=60)
print("PASS: real trade producers preserve memory until commit, fixed 9+1 provenance, ordinary money, rejection, retry and relog")
