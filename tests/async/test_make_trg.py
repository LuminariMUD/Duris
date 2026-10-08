#!/usr/bin/env python3
"""make_trg builds world.trg from the areas' trg/<area>.trg sources and refuses a
malformed one with its file and line, which fails make world."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
GOOD = "* a comment\n#100 M\nT SPEECH hello\nsay Hi, $n.\n~\nS\n"
MALFORMED = {
    "#200 O\nT DEATH\nsay ow\nS\n": "trg/bad.trg:4: a trigger is not ended by ~",
    "#200 O\nT DEATH\nsay ow\n~\n": "trg/bad.trg:4: a record is not ended by S",
    "#200\nT DEATH\n": "trg/bad.trg:1: expected a #<vnum> <M|O|R> record header",
    "#200 X\n": "trg/bad.trg:1: expected a #<vnum> <M|O|R> record header",
    "#200 R\nsay ow\n": "trg/bad.trg:2: expected T, S or a * comment",
    "#~\n": 'trg/bad.trg:1: "#~" ends the combined file; a source may not hold it',
}

with tempfile.TemporaryDirectory(prefix="duris-make-trg-") as scratch:
    tool = Path(scratch) / "make_trg"
    subprocess.run(["gcc", "-Wall", "-Wextra", "-Werror", "-o", str(tool),
                    str(ROOT / "areas/src/trg/make_trg.c")], check=True)
    run = Path(scratch) / "areas"
    (run / "trg").mkdir(parents=True)
    (run / "trg/good.trg").write_text(GOOD)

    # An area without a source is skipped; the file always ends with "#~".
    (run / "AREA").write_text("* comment\ngood *1\nplain *2\n")
    subprocess.run([str(tool)], cwd=run, check=True, stdout=subprocess.DEVNULL)
    assert (run / "tworld.trg").read_text() == GOOD + "#~\n"
    (run / "trg/good.trg").unlink()
    subprocess.run([str(tool)], cwd=run, check=True, stdout=subprocess.DEVNULL)
    assert (run / "tworld.trg").read_text() == "#~\n"

    (run / "AREA").write_text("bad *1\n")
    for source, error in MALFORMED.items():
        (run / "trg/bad.trg").write_text(source)
        result = subprocess.run([str(tool)], cwd=run, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, text=True)
        assert result.returncode != 0, source
        assert result.stderr == f"error: {error}\n", (source, result.stderr)

print("make_trg builds world.trg and refuses a malformed trigger source")
