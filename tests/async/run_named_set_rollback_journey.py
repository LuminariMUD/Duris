#!/usr/bin/env python3
"""Current -> compatible 115-row catalog -> current on a copy of test authority.

Pass the separately built flat-file compatibility server. The original named-set
runtime must be stopped; source state/accounts/journals are hashed before/after.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import test_flatfile_combat_journey as journey
from named_set_gameplay import NamedSetGame, expect_max_hp, save, score, selector

ROOT = journey.ROOT
source = (ROOT / "bin/tests/named-set-roster-world").resolve()
compat = Path(sys.argv[1]).resolve()
assert compat.is_file() and source.is_relative_to((ROOT / "bin/tests").resolve())
processes = subprocess.check_output(["ps", "-eo", "args"], text=True)
assert "-d " + str(source) + " " not in processes, "stop the source test authority before copying"


def source_hashes():
    return {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
            for directory in ("state", "Accounts", "journals")
            for path in sorted((source / directory).rglob("*")) if path.is_file()}


original_hashes = source_hashes()
runtime = Path(tempfile.mkdtemp(prefix="named-rollback-world-", dir=ROOT / "bin/tests"))
print("Artifacts: " + str(runtime), flush=True)
for directory in ("state", "Accounts", "journals"):
    shutil.copytree(source / directory, runtime / directory)
archive = subprocess.Popen(["git", "archive", "HEAD", "lib", "help"], cwd=ROOT, stdout=subprocess.PIPE)
subprocess.run(["tar", "-x", "-C", str(runtime)], stdin=archive.stdout, check=True)
archive.stdout.close()
assert archive.wait() == 0
(runtime / "areas").symlink_to(source / "areas", target_is_directory=True)
(runtime / "docs").symlink_to(ROOT / "docs", target_is_directory=True)
for directory in ("logs", "log"):
    (runtime / directory).mkdir()
journey.generate_certificate(runtime)
evidence = {"checks": [], "compat_binary_sha256": hashlib.sha256(compat.read_bytes()).hexdigest()}
game = NamedSetGame(runtime=runtime)
transcripts = []


def act(client, text, expected=None):
    client.send(text)
    if expected:
        client.expect(expected, timeout=30)
    return score(client)[1]


def stop():
    game.stop()
    if game.process:
        assert game.process.returncode == 0, "unclean rollback journey stop"
    transcripts.extend(game.transcripts)
    game.transcripts.clear()


def origins():
    return {row[0]: row[1] for row in game.items() + game.items(2)}


def graphs():
    from named_set_gameplay import inventory_graph
    return {pid: inventory_graph(game.inventory(pid)) for pid in (1, 2)}


def catalog_ids(text):
    return set(map(int, re.findall(r"^\s*\{\s*(\d+),\s*\{\s*\{", text, re.M)))


expanded_ids = catalog_ids((ROOT / "src/item/named_sets.c").read_text())
old_ids = catalog_ids(subprocess.check_output(
    ["git", "show", "bff1043fd:src/item/named_sets.c"], cwd=ROOT, text=True))
assert len(expanded_ids) == 298 and len(old_ids) == 115 and old_ids < expanded_ids


def report(client, label, expected):
    act(client, "toggle paging no")
    offset = len(client.transcript)
    client.send("namedreport")
    client.expect("Current listing of spells granted by named sets by zone.", timeout=30)
    for _ in range(60):
        match, _ = client.expect_any(("Return to continue", "Pos:"), timeout=30)
        if match == "Pos:":
            client.expect(">")
            break
        client.send("")
    else:
        raise AssertionError("rollback report did not finish")
    wire = re.sub(rb"\xff\xfa.*?\xff\xf0", b"", bytes(client.transcript[offset:]), flags=re.S)
    text = wire.replace(b"\xff\xf9", b"").decode(errors="replace").replace("\r\n", "\n")
    text = re.sub(r"\n\n\[Return to continue[^\]]*\]\n\n", "", text)
    ids = list(map(int, re.findall(r"(?m)^\s*#(\d+) ", text)))
    assert len(ids) == len(expected) and set(ids) == expected, (label, len(ids))
    (runtime / (label + "-report.txt")).write_text(text)


def check(label):
    evidence["checks"].append(label)
    (runtime / "evidence.json").write_text(json.dumps(evidence, indent=2))
    print("PASS " + label, flush=True)


try:
    initial = origins()
    evidence["copied_named_count"] = len(initial)
    journey.make_overlord(game.state, journey.CHARACTER)
    actor = game.boot("seed-expanded")
    act(actor, "vis 0")
    act(actor, "remove all")
    # Preserve the copied inventory before generating a new, independently
    # identified #827 cohort; no old UID or payload is fabricated or discarded.
    act(actor, "load obj 83445", "You have created")
    act(actor, "open collector")
    act(actor, "put all collector")
    act(actor, "goto 82701")
    selected = []
    for slot, flag in (("head", 16), ("body", 8), ("legs", 32)):
        act(actor, f"randobj eq {slot} 56 30", "Created 30 equipment items.")
        save(actor)
        candidates = [row for row in game.items() if row[1] == "827" and row[4] == "1"
                      and row[5] == "-1" and int(row[3]) & flag]
        assert candidates, ("no clean native #827 candidate", slot)
        uid = int(candidates[0][0])
        assert str(uid) not in initial
        act(actor, "wear " + selector(actor, uid))
        selected.append(uid)
    act(actor, "load obj 83445", "You have created")
    act(actor, "open collector")
    act(actor, "put all collector")
    act(actor, "goto 132500")
    save(actor)
    stop()
    game.prepare_mortal()
    actor = game.boot("current-before-rollback")
    act(actor, "remove all")
    time.sleep(6)
    baseline = score(actor)[0]
    for uid in selected:
        act(actor, "wear " + selector(actor, uid))
    assert "protection from animals (" in expect_max_hp(actor, baseline + 5)
    save(actor)
    assert not game.affects(383), "the set effect must not serialize as an ordinary cast"
    expected_origins, expected_graphs = origins(), graphs()
    assert all(expected_origins.get(uid) == origin for uid, origin in initial.items())
    evidence.update(uids=selected, baseline_hp=baseline, qualified_named_count=len(expected_origins))
    report(actor, "expanded-before", expanded_ids)
    check("expanded build grants #827 protection/+5 HP and reports all 298 rows on the copied authority")
    stop()

    game = NamedSetGame(runtime=runtime, binary=compat)
    actor = game.boot("compatibility-rollback")
    text = expect_max_hp(actor, baseline + 5)
    assert "protection from animals (" not in text
    save(actor)
    receiver = game.login(account="Namedguest", character="Meranen", source_host="127.0.0.2")
    save(receiver, "Meranen")
    assert origins() == expected_origins and graphs() == expected_graphs
    assert not game.affects(383)
    report(actor, "compatibility", old_ids)
    check("compatibility rollback retains every UID/origin/parent/slot and HP, removes the new spell and reports 115 rows")
    stop()

    game = NamedSetGame(runtime=runtime)
    actor = game.boot("expanded-after-rollback")
    assert "protection from animals (" in expect_max_hp(actor, baseline + 5)
    save(actor)
    receiver = game.login(account="Namedguest", character="Meranen", source_host="127.0.0.2")
    save(receiver, "Meranen")
    assert origins() == expected_origins and graphs() == expected_graphs
    assert not game.affects(383)
    report(actor, "expanded-after", expanded_ids)
    check("re-upgrade restores the new spell and 298-row report with the exact saved item graphs")
finally:
    stop()
    (runtime / "transcript.txt").write_bytes(b"\n\n".join(transcripts))
    assert source_hashes() == original_hashes, "the original authority changed during the copy rehearsal"
    evidence["source_authority_unchanged"] = True
    (runtime / "evidence.json").write_text(json.dumps(evidence, indent=2))
