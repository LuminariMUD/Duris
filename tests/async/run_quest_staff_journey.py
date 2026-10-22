#!/usr/bin/env python3
"""Exercise quest inspection dispatch, permissions, help, and paging via Telnet.

Requires a fresh flat-file server binary. Uses synthetic accounts, a private
authored world and temporary state, without reading the checkout's .env.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import test_flatfile_combat_journey as journey
from run_item_pilot_journey import Server
from run_paladin_balance_journey import command

ROOT = journey.ROOT


def configure(runtime):
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / "help").symlink_to(ROOT / "help", target_is_directory=True)
    (runtime / "logs/log").mkdir(parents=True)
    (runtime / "logs/log/.since").touch()
    # Replace only the temporary fixture's areas symlink with a private world.
    (runtime / "areas").unlink()
    (runtime / "areas").mkdir()
    generated = {f"world.{suffix}" for suffix in
                 ("wld", "mob", "obj", "zon", "trg", "shp", "qst", "tab", "weather")}
    for path in (ROOT / "areas").iterdir():
        if path.name not in generated:
            (runtime / "areas" / path.name).symlink_to(path, target_is_directory=path.is_dir())
    for suffix in ("wld", "mob", "obj", "zon"):
        shutil.copyfile(runtime / f"areas_mini/mini.{suffix}", runtime / f"areas/world.{suffix}")
    for name in ("world.shp", "world.tab", "world.weather"):
        source = runtime / "areas_mini" / name
        (runtime / "areas" / name).write_text(source.read_text() if source.exists() else "$~\n")
    (runtime / "areas/world.trg").write_text("#~\n")
    response = "\n".join(f"QUEST_PAGE_{i:03d}" for i in range(90))
    (runtime / "areas/world.qst").write_text(f"""#11
M
help quest~
{response}
QUEST_RESPONSE_END~
Q
QUEST_GIVE_COMPLETION~
G I 15
G I 15
R I 3
D
QUEST_DISAPPEAR_MESSAGE~
QA
QUEST_RECEIVE_COMPLETION~
G C 5
R I 15
S
#12
M
hello~
DIALOGUE_ONLY~
S
#~
""")
    oversized = "#13\n" + ("Q\n" + "OVERSIZED_QUEST_TEXT " * 220 + "~\n") * 250 + "S\n#~\n"
    quest_file = runtime / "areas/world.qst"
    quest_file.write_text(quest_file.read_text().replace("#~\n", oversized))


def run(binary):
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quest-staff-journey-", dir=ROOT / "bin/tests") as directory:
        root = Path(directory)
        runtime, state = root / "runtime", root / "state"
        runtime.mkdir(); state.mkdir(mode=0o700)
        (state / "domains").mkdir(mode=0o700)
        configure(runtime)
        server = Server(binary, runtime, state, "quest-staff")
        result = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "checks": []}
        try:
            server.start()
            mortal = server.client = journey.MudClient(server.port)
            journey.create_character(mortal)
            for text in ("qview 11", "qref 15", "qinfo 15", "qlist", "hlqlist"):
                output = command(mortal, text)
                assert "Quest giver" not in output and "Quest references" not in output, output
                assert "Pardon?" in output, output
            result["checks"].append("all five commands denied to a mortal")
            mortal.send("save"); mortal.expect(f"Save complete for {journey.CHARACTER}.")
            mortal.send("quit"); mortal.expect("ACCOUNT MENU", timeout=45)
            server.stop()
            journey.make_overlord(state, journey.CHARACTER)
            server.start()
            staff = server.client = journey.reconnect_character(server.port)
            command(staff, "vis 0")
            command(staff, f"setbit char {journey.CHARACTER} pcact PAGING_ON 1")
            listing = command(staff, "qlist")
            assert "[11]" in listing and "[12]" in listing and "0 completion rule(s)" in listing, listing
            assert "[11]" in command(staff, "hlqlist 11"), listing
            assert "[12]" not in command(staff, "qlist 11 11"), listing
            result["checks"].append("current-zone, exact and range listings; hlqlist alias")
            view = command(staff, "qview 11")
            for part in ("Quest giver [11]", "Key: help quest", "QUEST_PAGE_000", "QUEST_PAGE_089",
                         "QUEST_RESPONSE_END", "QUEST_GIVE_COMPLETION", "QUEST_RECEIVE_COMPLETION",
                         "QUEST_DISAPPEAR_MESSAGE", "Item [15]", "Coins:"):
                assert part in view, (part, view)
            assert "Return to continue" in view, view
            result["checks"].append("qview reaches every response page, both completions and disappearance")
            command(staff, f"setbit char {journey.CHARACTER} pcact PAGING_ON 0")
            assert "requires paging" in command(staff, "qview 13")
            command(staff, f"setbit char {journey.CHARACTER} pcact PAGING_ON 1")
            oversized = command(staff, "qview 13")
            assert "report is too large" in oversized, oversized
            assert "and the list goes on" not in oversized, oversized
            result["checks"].append("oversized qview returns an explicit capacity error")
            refs = command(staff, "qref 15")
            assert "GIVE" in refs and "RECEIVE" in refs, refs
            assert "QUEST_GIVE_COMPLETION" not in refs, refs
            info = command(staff, "qinfo 15")
            assert "QUEST_GIVE_COMPLETION" in info and "QUEST_RECEIVE_COMPLETION" in info, info
            assert info.count("Item [15]") == 3, info
            result["checks"].append("qref compact references and qinfo full matching exchanges")
            for name in ("qview", "qref", "qinfo", "qlist", "hlqlist"):
                help_text = command(staff, f"help {name}")
                assert "Syntax:" in help_text and name in help_text.lower(), help_text
                assert name in command(staff, "wizhelp").lower()
            result["checks"].append("help and wizhelp discover all five commands")
            for text, expected in (("qview x", "Usage:"), ("qview 999999", "No such mobile"),
                                   ("qview 12", "No completion rules"),
                                   ("qref 999999", "No such object"),
                                   ("qlist 2147483648", "Usage:")):
                assert expected in command(staff, text), text
            result["checks"].append("invalid arguments and absent references handled through dispatch")
        finally:
            server.stop()
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.binary.resolve())
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
