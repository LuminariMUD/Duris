#!/usr/bin/env python3
"""Full generated-world trap commands, saved budgets and restart on either backend."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import test_flatfile_combat_journey as journey
from test_corpse_trap_restart_journey import clone_banana, drain
from test_legacy_trap_content import check, parse_objects
from legacy_trap_manifest import TRAPS

ROOT = journey.ROOT
BUILDER, ACCOUNT = "Trapbuilder", "Trapacct"
ROOM, DEST = 95514, 95513
INVALID = 800001


def command(client, text, timeout=40):
    # TIME is a read-only causal barrier allowed during paralysis. Room activity can print a
    # prompt before the requested command runs, so a prompt alone is not an ACK.
    drain(client, .01)
    client.send(text)
    client.send("time")
    deadline = time.monotonic() + timeout
    pager_exited = False
    while time.monotonic() < deadline:
        client._receive()
        output = client.pending.decode(errors="replace")
        if "[Return to continue" in output and not pager_exited:
            pager_exited = True
            client.send("q")
            client.send("time")
        if "Current time is:" in output:
            before, timestamp = output.split("Current time is:", 1)
            if re.search(r"Pos:[^\r\n]*>", timestamp):
                client.pending.clear()
                return before
    raise AssertionError((text, bytes(client.pending).decode(errors="replace")[-5000:]))


def fixture(runtime):
    areas = runtime / "areas"
    areas.unlink()
    areas.mkdir()
    for entry in (ROOT / "areas").iterdir():
        target = areas / entry.name
        if entry.name in ("world.obj", "world.wld"):
            shutil.copy2(entry, target)
        else:
            target.symlink_to(entry, target_is_directory=entry.is_dir())
    objects = (areas / "world.obj").read_text(encoding="latin1")
    check(parse_objects(objects))
    banana = re.search(r"(?ms)^#15\n.*?(?=^#16\n)", objects)[0]
    invalid = clone_banana(banana, INVALID, "invalidprobe", "an invalid trap probe",
                           "An invalid trap probe lies here.") + "T\n2 17 2 60\n"
    objects = objects.replace("#9999999\n", invalid + "#9999999\n")
    (areas / "world.obj").write_bytes(objects.encode("latin1"))
    world = (areas / "world.wld").read_text(encoding="latin1")
    for room, destination in ((ROOM, DEST), (DEST, ROOM)):
        match = re.search(rf"(?ms)^#{room}\n.*?(?=^#|\Z)", world)
        assert match, room
        original = match[0]
        # Preserve the authored room name, description and flags; provide all six
        # ordinary exits so the test independently checks each object's direction mask.
        offset = 0
        for _ in range(2):
            end = re.search(r"~[ \t]*$", original[offset:], re.M)
            offset += end.end()
        header = re.search(r"\S[^\n]*\n", original[offset:])
        prefix = original[:offset + header.end()]
        exits = "".join(f"D{direction}\n~\n~\n0 0 {destination}\n" for direction in range(6))
        world = world[:match.start()] + prefix + exits + "S\n" + world[match.end():]
    (areas / "world.wld").write_bytes(world.encode("latin1"))


def run(binary, backend):
    assert backend in ("flatfile", "mariadb")
    evidence = ROOT / "bin/issue368-evidence" / (backend + "-" + uuid.uuid4().hex[:8])
    evidence.mkdir(parents=True)
    env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
               PERSISTENCE_MODE=backend + "-primary", REDIS="FALSE", CHAOS_MUD="FALSE",
               LISTEN_ADDRESS="127.0.0.1", DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1")
    if value := os.environ.get("LD_LIBRARY_PATH"):
        env["LD_LIBRARY_PATH"] = value
    sql, database, redis = None, None, None
    if backend == "mariadb":
        database = "legacy_traps_" + uuid.uuid4().hex[:12]
        host = os.environ["TEST_DB_HOST"]
        assert host in ("127.0.0.1", "localhost")
        env.update(DB_HOST=host, DB_PORT=os.environ["TEST_DB_PORT"], DB_NAME=database,
                   DB_USER=os.environ["TEST_DB_USER"], DB_PASSWD=os.environ["TEST_DB_PASSWORD"],
                   MYSQL_PWD=os.environ["TEST_DB_PASSWORD"], DB_TLS="FALSE",
                   DB_ALLOWED_TARGETS=host + "/" + database)
        mysql = ["mysql", "--protocol=tcp", "-h", host, "-P", env["DB_PORT"], "-u", env["DB_USER"], "-N", "-B"]

        def sql(statement, selected=True):
            return subprocess.check_output(mysql + ([database] if selected else []),
                                           input=statement, text=True, env=env).strip()

        sql("CREATE DATABASE " + database, False)
    clients, process, output = [], None, None
    try:
        with tempfile.TemporaryDirectory(prefix="legacy-trap-world-", dir=ROOT / "bin/tests") as temporary:
            runtime = Path(temporary)
            state = runtime / "authority"
            state.mkdir(mode=0o700)
            (state / "domains").mkdir(mode=0o700)
            if sql:
                sql((ROOT / "migrations/bootstrap_multithread_safe.sql").read_text())
                for arguments in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
                    subprocess.run(["python3", "scripts/migration_runner.py", *arguments],
                                   cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
            else:
                subprocess.run([sys.executable, "tests/async/test_flatfile_player_repository.py",
                                "--build-inspector", str(journey.INSPECTOR)], cwd=ROOT, check=True,
                               stdout=subprocess.DEVNULL)
                subprocess.run([str(journey.INSPECTOR), str(state), "seed-combat"], check=True)
                env["FLATFILE_STATE_DIR"] = str(state)
            redis_port = journey.available_ports()[0]
            redis = subprocess.Popen(["redis-server", "--bind", "127.0.0.1", "--port", str(redis_port),
                                      "--save", "", "--appendonly", "no"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            env.update(REDIS="TRUE", REDIS_HOST="127.0.0.1", REDIS_PORT=str(redis_port),
                       REDIS_NAMESPACE="duris:local:" + (database or "legacy-traps-flatfile"), REDIS_WORLD_STATE="TRUE",
                       REDIS_WORLD_STATE_INTERVAL="5", REDIS_WORLD_STATE_SECRET="local-legacy-trap-qualification-secret-368")
            journey.make_fixture(runtime)
            fixture(runtime)
            journey.generate_certificate(runtime)
            (runtime / "logs/log").mkdir(parents=True)
            (runtime / "journals/critical").mkdir(parents=True, mode=0o700)
            game_port, tls, ws = journey.available_ports()
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(runtime / "journals/critical"),
                       DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(ws))
            boot_number = 0

            def boot():
                nonlocal process, output, boot_number
                boot_number += 1
                output = (evidence / f"boot-{boot_number}.out").open("w")
                process = subprocess.Popen([str(binary), "-s", "-d", str(runtime), str(game_port)],
                                           cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while True:
                    text = (evidence / f"boot-{boot_number}.out").read_text(errors="replace")
                    if "Entering game loop." in text:
                        break
                    assert process.poll() is None and time.monotonic() < deadline, text[-5000:]
                    time.sleep(.1)
                for stage in ("-- Player corpses", "-- Shopkeepers", "Booting Ferries"):
                    assert stage in text, (stage, text[-5000:])
                print(f"{backend}: full-world boot {boot_number} ready", flush=True)

            def stop():
                nonlocal process, output
                for client in clients:
                    client.close()
                clients.clear()
                if process and process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                    assert process.returncode == 0
                if output:
                    output.close()
                process, output = None, None

            def connect(account, name, create=False):
                client = journey.MudClient(game_port) if create else journey.reconnect_character(
                    game_port, expected_room=None, account=account, character=name)
                clients.append(client)
                if create:
                    journey.create_character(client, expected_room=None, account=account,
                                             character=name, email=name.lower() + "@example.invalid")
                client.socket.settimeout(.05)
                return client

            try:
                boot()
                for account, name in ((ACCOUNT, BUILDER), (journey.ACCOUNT, journey.CHARACTER)):
                    client = connect(account, name, True)
                    client.send("save"); client.expect(f"Save complete for {name}.", timeout=45)
                    client.send("quit"); client.expect("ACCOUNT MENU", timeout=45)
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62,base_hit=200000 WHERE name='{BUILDER}'")
                    sql(f"UPDATE player_data SET level=50,highest_level=50,base_hit=200000 WHERE name='{journey.CHARACTER}'")
                else:
                    source = journey.OVERLORD_FIXTURE.replace(
                        "field.signed_value = field.unsigned_value = 62;",
                        "field.signed_value = field.unsigned_value = !strcasecmp(argv[2], \"Trapbuilder\") ? 62 : 50;\n"
                        "        for(auto &field : snapshot.status_integers) {\n"
                        "            if(field.field==player_status_field::base_hit) field.signed_value=field.unsigned_value=200000;\n"
                        "            if(field.field==player_status_field::hit_difference) field.signed_value=field.unsigned_value=0;\n"
                        "        }")
                    cpp, fixture_binary = runtime / "staff.cpp", runtime / "staff"
                    cpp.write_text(source)
                    subprocess.run(["g++", "-std=c++20", "-Isrc", str(cpp), "src/player/player_snapshot_codec.c",
                                    "src/flatfile/flatfile_player_snapshot_file.c", "src/flatfile/flatfile_store.c",
                                    "-lcrypto", "-o", str(fixture_binary)], cwd=ROOT, check=True)
                    for name in (BUILDER, journey.CHARACTER):
                        subprocess.run([str(fixture_binary), str(state), name], check=True)
                boot()
                builder, actor = connect(ACCOUNT, BUILDER), connect(journey.ACCOUNT, journey.CHARACTER)
                command(builder, f"goto {ROOM}")

                def home():
                    command(builder, f"goto {ROOM}")
                    command(builder, "transfer " + journey.CHARACTER)
                    drain(actor, .04)

                def load(vnum, prefix="probe"):
                    loaded = command(builder, f"load object {vnum}")
                    assert "You have created" in loaded, (vnum, loaded)
                    key = prefix + str(vnum)
                    result = command(builder, f"string obj {vnum} name {key}")
                    assert "Ok." in result, result
                    return key

                def inspect(key, expected):
                    text = command(builder, "stat trap " + key)
                    assert re.search(rf"Trap Charges left: {expected[2]}\.", text), (key, expected, text)
                    assert re.search(rf"Trap level: {expected[3]}\b", text), text
                    names = ("sleep", "teleport", "fire", "frost", "acid", "energy", "blunt", "pierce", "slash",
                             "dispel", "gate", "summon", "wither", "harm", "poison", "minor paralysis", "stun")
                    if 0 <= expected[1] <= 16:
                        assert f"Damage type is {names[expected[1]]}." in text, text
                    else:
                        assert f"Damage type {expected[1]} is unsupported" in text, text
                    effect = 0
                    for direction, bit in (("north", 8), ("east", 16), ("south", 32), ("west", 64)):
                        if "movement to the " + direction in text:
                            effect |= 1 | bit
                    for phrase, bit in (("movement up", 1 | 128), ("movement down", 1 | 256),
                                        ("set off by get or put", 2), ("affects the whole room", 4),
                                        ("set off when opened", 512), ("MULTI:", 1024), ("GLYPH:", 2048)):
                        if phrase in text:
                            effect |= bit
                    assert effect == expected[0], (key, effect, expected, text)
                    return text

                def floor(key):
                    command(builder, "drop " + key)

                def count(vnum):
                    text = command(builder, f"stat mob {vnum}")
                    match = re.search(r"# in game:\s*(\d+)", text)
                    assert match, text
                    return int(match[1]) - 1  # stat creates and then extracts its own probe

                home()
                command(actor, "drop all")
                caster_count = count(14)
                for vnum in (6714, 6003, 32015, 1458):
                    home(); key = load(vnum); floor(key)
                    command(actor, "get " + key)
                    final = TRAPS[vnum][2]
                    inspect(key, (final[0], final[1], 0, final[3]))
                    assert count(14) == caster_count
                    command(builder, "purge " + key)
                    if vnum == 32015:
                        command(builder,"affectpurge "+journey.CHARACTER+" all")
                    if vnum == 1458:
                        time.sleep(4.2)

                home(); hidden=load(3835);floor(hidden)
                hidden_attempt=command(actor,"get "+hidden)
                assert "do not see" in hidden_attempt,hidden_attempt
                inspect(hidden,TRAPS[3835][2])
                command(builder,"purge "+hidden)

                for vnum in (67803,142233,142251):
                    home();key=load(vnum);floor(key)
                    command(builder,"search")
                    text=command(actor,"open "+key)
                    assert "Ok." in text and "already open" not in text,text
                    final=TRAPS[vnum][2]
                    inspect(key,(final[0],final[1],0 if final[2]>0 else final[2],final[3]))
                    if vnum == 67803:
                        command(builder,"affectpurge "+journey.CHARACTER+" all")
                    if vnum != 142233:
                        command(builder,"purge "+key)

                # Real permission-complete item-on-put hook; retain one of two charges.
                home(); bag = load(142438); floor(bag)
                command(actor, "open " + bag)
                inspect(bag, (512, 9, 0, 60))
                key = load(35506)
                command(builder, f"give {key} {journey.CHARACTER}")
                refused=command(actor, f"put {key} {bag}")
                assert "won't fit" in refused,refused
                inspect(key,(2,15,2,100))
                control_started = time.monotonic()
                command(actor, f"put {key} probe142233")
                inspect(key, (2, 15, 1, 100))
                assert count(14) == caster_count
                time.sleep(max(0, 12.2 - (time.monotonic() - control_started)))

                # Wrong directions do not fire; a non-glyph harm blocks only the first east attempt.
                home(); key = load(44160); floor(key)
                for direction in ("north", "south", "west", "up", "down"):
                    home(); assert "Inside the Gates of Kimordril" in command(actor, direction)
                    inspect(key, TRAPS[44160][2])
                home()
                potion = load(38715)
                command(builder, f"give {potion} {journey.CHARACTER}")
                effect = command(actor, "quaff " + potion)
                assert "translucent" in effect.lower(), effect
                before_xp=command(builder,"stat mob "+journey.CHARACTER)
                before_xp=re.search(r"Experience:\s*([\d,]+)",before_xp)[1]
                reflected=command(actor, "east")
                assert "deflect" in reflected.lower(),reflected
                room_text=command(actor,"look")
                assert "Guard Post" in room_text and "corpse of a trap" not in room_text.lower()
                inspect(key, (17, 13, 0, 90))
                after_xp=command(builder,"stat mob "+journey.CHARACTER)
                after_xp=re.search(r"Experience:\s*([\d,]+)",after_xp)[1]
                assert before_xp==after_xp,(before_xp,after_xp)
                assert count(14)==caster_count
                command(builder, "affectpurge " + journey.CHARACTER + " all")
                assert "Inside the Gates of Kimordril" in command(actor, "east")

                # A later non-glyph remains blocking after a down glyph, including an unlimited trap.
                home(); blocker = load(43503); floor(blocker)
                glyph = load(91025); floor(glyph)
                command(actor, "down")
                assert "Guard Post" in command(actor, "look")
                inspect(glyph, (2309, 9, 4, 60))
                command(builder, "purge " + blocker)
                time.sleep(2.2)
                assert "Inside the Gates of Kimordril" in command(actor, "down")
                inspect(glyph, (2309, 9, 3, 60))

                # Authored profiles use real converted NPCs; compare prototype population deltas.
                for vnum, mob, batch, trigger in ((41361,200,1,"east"),(42290,200,1,"get"),
                        (32820,32861,3,"open"),(32870,32861,3,"open"),
                        (32835,32861,1,"west"),(32846,32871,1,"north"),(41927,200,1,"get")):
                    home(); before=count(mob); key=load(vnum);floor(key)
                    command(builder,"search")
                    if vnum in (32820,32870):
                        lock_key=load(32818)
                        command(builder,f"give {lock_key} {journey.CHARACTER}")
                        command(actor,"unlock "+key)
                    command(actor, trigger + (" " + key if trigger in ("get","open") else ""))
                    assert count(mob)==before+batch,(vnum,before,count(mob))
                    final=TRAPS[vnum][2]
                    inspect(key,(final[0],final[1],final[2]-1,final[3]))
                    keyword={200:"shadow",32861:"imp",32871:"stalker"}[mob]
                    for _ in range(batch): command(builder,"purge "+keyword)
                    assert count(mob)==before
                    command(builder,"purge "+key)
                    print(f"{backend}: profile {vnum} placed {batch} NPC {mob}",flush=True)

                # A builder glyph that creates combat must not bypass the normal
                # movement gate; the movement owner retains its explicit flee exception.
                home();before=count(32861);summoner=load(32835);floor(summoner)
                command(builder,"trapset "+summoner+" glyph")
                command(actor,"west")
                assert "Guard Post" in command(actor,"look")
                assert count(32861)==before+1
                command(builder,"purge imp");command(builder,"purge "+summoner)

                # Invalid types remain visible and inert through actual get.
                home(); invalid=load(INVALID);floor(invalid)
                command(actor,"get "+invalid)
                inspect(invalid,(2,17,2,60))
                actor.send("save");actor.expect("Save complete for Taverek.",timeout=45)
                assert count(14)==caster_count
                stop();boot()
                builder,actor=connect(ACCOUNT,BUILDER),connect(journey.ACCOUNT,journey.CHARACTER)
                command(builder,f"goto {ROOM}")
                inspect("probe35506",(2,15,1,100))
                inspect("probe44160",(17,13,0,90))
                inspect("probe91025",(2309,9,3,60))
                inspect("probe142438",(512,9,0,60))
                inspect("probe800001",(2,17,2,60))
                home()
                assert "already open" in command(actor,"open probe142438").lower()
                for vnum, (_, _, final) in TRAPS.items():
                    key = load(vnum, "golden")
                    inspect(key, final or (0, 0, 0, 0))
                    floor(key)
                    command(builder, "purge " + key)
                print(f"{backend}: all 61 loaded prototype states verified", flush=True)
                assert count(14)==caster_count
                stop()
                logs="\n".join(p.read_text(errors="replace") for p in (runtime/"logs/log").glob("*") if p.is_file())
                assert re.search(r"Object 800001 has unsupported trap damage type 17",logs)
                for vnum in TRAPS:
                    assert not re.search(rf"Object {vnum} has unsupported trap",logs),vnum
                result=dict(backend=backend,source=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                            source_patch_sha256=hashlib.sha256(subprocess.check_output(["git","diff","--binary","HEAD","--","src","areas/obj"],cwd=ROOT)).hexdigest(),
                            binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                            world_sha256=hashlib.sha256((runtime/"areas/world.obj").read_bytes()).hexdigest(),
                            result="passed",loaded_definitions=61,boots=boot_number)
                (evidence/"result.json").write_text(json.dumps(result,indent=2)+"\n")
                print(f"PASS: {backend} loaded trap effects/commands, seven native profiles and saved budgets/restart; {evidence}",flush=True)
            finally:
                if output: output.flush()
                for index,client in enumerate(clients):
                    (evidence/f"client-{index}.txt").write_text(client.transcript.decode(errors="replace").replace(journey.PASSWORD,"[REDACTED]"))
                shutil.copytree(runtime/"logs/log",evidence/"logs",dirs_exist_ok=True)
                stop()
    finally:
        if redis:
            redis.terminate();redis.wait(timeout=10)
        if sql: sql("DROP DATABASE "+database,False)


if __name__=="__main__":
    if len(sys.argv) in (2,3):
        run(Path(sys.argv[1]).resolve(),sys.argv[2] if len(sys.argv)==3 else "mariadb")
    elif len(sys.argv)==1:
        (ROOT/"bin/tests").mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="legacy-trap-build-",dir=ROOT/"bin/tests") as build:
            run(journey.build_flatfile_server(Path(build)),"flatfile")
    else: raise SystemExit("usage: test_legacy_trap_journey.py [SERVER [mariadb|flatfile]]")
