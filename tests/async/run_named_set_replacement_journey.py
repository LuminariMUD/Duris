#!/usr/bin/env python3
"""Qualify the worksheet replacement on a private full-world MariaDB authority.

Pass the previous catalog linked with current persistence/ownership safety fixes.
Failure evidence and SQL are retained under bin/tests; --resume preserves UIDs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import test_mariadb_combat_journey as journey
from named_set_gameplay import ARTIFACT_ROOT, NamedSetGame, dump_authority, expect_max_hp, get_from_container, inventory_graph, save, score, selector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("compatibility_server", type=Path)
parser.add_argument("--resume", type=Path)
options = parser.parse_args()
compatibility = options.compatibility_server.resolve()
assert compatibility.is_file()
if not os.environ.get("TEST_DB_HOST"):
    wrapper = journey.ROOT / "tests/async/with_disposable_mariadb.sh"
    os.execv(wrapper, [str(wrapper), sys.executable, str(Path(__file__).resolve()),
                      str(compatibility), *(["--resume", str(options.resume.resolve())] if options.resume else [])])
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
runtime = options.resume.resolve() if options.resume else Path(tempfile.mkdtemp(
    prefix="named-replacement-", dir=ARTIFACT_ROOT))
assert runtime.is_relative_to(ARTIFACT_ROOT)
print("Named replacement artifacts: " + str(runtime), flush=True)
if not options.resume:
    journey.make_fixture(runtime)
    journey.generate_certificate(runtime)
    (runtime / "logs/log").mkdir(parents=True)
    (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
evidence = json.loads((runtime / "replacement.json").read_text()) if options.resume else {"completed": []}
evidence.pop("passed", None)
with journey.mariadb_authority() as (environment, sql):
    environment.update({key: os.environ[key] for key in ("TEST_DB_HOST", "TEST_DB_PORT", "TEST_DB_USER", "TEST_DB_PASSWORD")})
    environment.update(NAMED_SET_RUNTIME=str(runtime), NAMED_SET_SERVER=str(journey.ROOT / "bin/server/dms_new"))
    environment["NAMED_SET_ARTIFACT_ROOT"] = str(ARTIFACT_ROOT)
    game = NamedSetGame(runtime=runtime, environment=environment)
    evidence["binary_sha256"] = hashlib.sha256(game.binary.read_bytes()).hexdigest()
    evidence["compatibility_sha256"] = hashlib.sha256(compatibility.read_bytes()).hexdigest()
    if options.resume:
        sql((runtime / "authority.sql").read_text())
    try:
        if not options.resume:
            game.start("replacement-create")
            client = journey.MudClient(game.port)
            game.clients.append(client)
            journey.create_character(client, expected_room=None)
            save(client)
            client.send("quit")
            client.expect("ACCOUNT MENU", timeout=30)
            game.stop()
            game.make_overlord()
        cases = [("wear-" + str(zone), "run_named_set_wear_journey.py", [str(zone)])
                 for zone in (1325, 159, 455, 112, 883, 1424)]
        cases += [("transfer", "run_named_set_transfer_journey.py", [str(runtime)]),
                  ("report", "run_named_set_report_journey.py", [])]
        for label, script, args in cases:
            if label in evidence["completed"]:
                continue
            if label == "transfer":
                # Form cases temporarily use a matching Magus; the transfer
                # fixture's donor starts as the original Warrior again.
                game.sql("UPDATE player_data SET m_class=1,secondary_class=0,spec=0 WHERE pid=1")
            print("Named replacement case: " + label, flush=True)
            subprocess.run([sys.executable, str(journey.ROOT / "tests/async" / script), *args],
                           cwd=journey.ROOT, env=environment, check=True)
            evidence["completed"].append(label)
            (runtime / "replacement.json").write_text(json.dumps(evidence, indent=2))

        if "catalog-roundtrip" not in evidence["completed"]:
            # The same four-piece #112 gear has old bonuses under the previous
            # catalog, HP only under the replacement, and retains its item graph.
            uids = json.loads((runtime / "named-zone-112-result.json").read_text())["uids"]
            initial_origins = {r[0]: r[1] for r in game.items()}
            reference_graph = None
            current_binary = game.binary
            for label, binary, effect in (("previous", compatibility, "flesh armor"),
                                          ("replacement", current_binary, None)):
                game.binary = binary
                client = game.boot("rollback-" + label)
                client.send("remove all")
                score(client)

                def bring_to_inventory(uid):
                    rows = game.inventory()
                    row = next(row for row in rows if row[0] == uid)
                    if row[2] < 0:
                        return
                    parent = rows[row[2]][0]
                    bring_to_inventory(parent)
                    client.send("open " + selector(client, parent))
                    score(client)
                    get_from_container(client, uid, parent)

                for uid in uids:
                    bring_to_inventory(uid)
                    save(client)
                time.sleep(6)
                baseline = score(client)[0]
                for uid in uids:
                    client.send("wear " + selector(client, uid))
                    score(client)
                time.sleep(6)
                text = expect_max_hp(client, baseline + 10)
                for name in ("enhance agility", "flesh armor", "intellect fortress"):
                    assert (name + " (" in text) == bool(effect), (label, name, text)
                save(client)
                assert {r[0]: r[1] for r in game.items()} == initial_origins
                graph = {uid: state for uid, state in inventory_graph(game.inventory()).items()
                         if uid in initial_origins}
                if reference_graph is None:
                    reference_graph = graph
                else:
                    assert graph == reference_graph
                game.stop()
            evidence["completed"].append("catalog-roundtrip")
        evidence["passed"] = True
        print("PASS named replacement native wear, tiers, reload, transfer, report and rollback", flush=True)
    finally:
        game.stop()
        (runtime / "replacement-transcript.txt").write_bytes(b"\n".join(game.transcripts))
        (runtime / "authority.sql").write_bytes(dump_authority(environment))
        (runtime / "authority.sql").chmod(0o600)
        (runtime / "replacement.json").write_text(json.dumps(evidence, indent=2))
