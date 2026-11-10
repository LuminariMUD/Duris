#!/usr/bin/env python3
"""Real Disharmonist control timers, Globe-piercing Storms and Echo slot usage on MariaDB."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

import test_mariadb_combat_journey as journey
from test_minor_creation_instrument_journey import configure, spell_id
from test_flight_network_journey import command

ROOT=journey.ROOT
BARD,MAGE="Dishsinger","Spellward"
REPORT=ROOT/"bin/qualification/issue707/disharmonist-gameplay.json"


def cast_result(client,spell,target=""):
    start=len(client.transcript)
    client.send(f"cast '{spell}' {target}".rstrip())
    result,_=client.expect_any(("You complete your spell", "You abort your spell before",
                               "You don't know that spell", "You don't have that spell memorized",
                               "reserves are not sufficient"),timeout=60)
    client.expect(">",timeout=20)
    return result,bytes(client.transcript[start:]).decode(errors="replace")


def cast(client,spell,target=""):
    for _ in range(6):
        result,text=cast_result(client,spell,target)
        if result=="You complete your spell": return text
        assert result=="You abort your spell before",text
    raise AssertionError("concentration retries exhausted: "+spell)


def run(binary,phase):
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    report={"binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"phase":phase}
    with tempfile.TemporaryDirectory(prefix="bard-disharmonist-",dir=ROOT/"bin/tests") as temporary, \
            journey.mariadb_authority() as (authority,sql):
        runtime=Path(temporary); configure(runtime)
        (runtime/"journals/critical").mkdir(parents=True,mode=0o700)
        zone=runtime/"areas_mini/mini.zon"
        zone.write_text(re.sub(r"^[MGEO] .*\n","",zone.read_text(),flags=re.M))
        world=runtime/"areas_mini/mini.wld"
        body=world.read_text(); at=body.index("#22800\n"); arena=body[at:body.index("$~",at)]
        assert "1 0 0\nS\n" in arena
        arena=arena.replace("1 0 0\nS\n",f"1 {1 << 15} 0\nS\n") # No unrelated Chaos teleport.
        world.write_text(body[:at]+arena+"$~\n")
        port,tls,websocket=journey.available_ports()
        env={**authority,"CRITICAL_COMMAND_JOURNAL_DIR":str(runtime/"journals/critical"),
             "DURIS_TLS_PORT":str(tls),"DURIS_WEBSOCKET_PORT":str(websocket)}
        output_path=runtime/"server.out"; process=None; clients=[]
        with output_path.open("a") as output:
            def boot():
                at=output_path.stat().st_size
                proc=subprocess.Popen([str(binary),"--minimal","-s","-d",str(runtime),str(port)],
                                      cwd=runtime,env=env,stdout=output,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+120
                while "Entering game loop." not in output_path.read_text(errors="replace")[at:]:
                    assert proc.poll() is None and time.monotonic()<deadline,"boot failed"
                    time.sleep(.1)
                return proc
            def stop():
                for client in clients: client.close()
                clients.clear(); process.send_signal(signal.SIGTERM); process.wait(timeout=60)
                assert process.returncode==0
            def login(name):
                client=journey.reconnect_character(port,account=name,character=name)
                clients.append(client); client.expect(">",timeout=30)
                command(client,"toggle paging no"); return client
            try:
                process=boot()
                for name in (journey.CHARACTER,BARD,MAGE):
                    print("Creating disposable character: "+name,flush=True)
                    client=journey.MudClient(port); clients.append(client)
                    journey.create_character(client,account=name,character=name,email=name.lower()+"@example.invalid",
                                             alignment="e" if name==MAGE else "g")
                    command(client,"save"); client.send("quit"); client.expect("ACCOUNT MENU",timeout=30)
                stop(); journey.make_overlord(sql,journey.CHARACTER)
                for name,cls,spec,side in ((BARD,1 << 15,1,1),(MAGE,1 << 11,0,2)):
                    sql(f"UPDATE player_data SET m_class={cls},secondary_class=0,spec={spec},racewar={side},"
                        f"level=56,highest_level=56,played_time=200000,base_hit=100000,hit_diff=0,"
                        f"base_cha=100,screen_length=100,last_room=22800 WHERE name='{name}'")
                    pid=sql(f"SELECT pid FROM player_data WHERE name='{name}'")
                    sql(f"DELETE FROM player_affects WHERE pid={pid}; DELETE FROM player_skills WHERE pid={pid}")
                    sql(f"INSERT INTO player_affects(pid,type,duration,modifier,flags,level) "
                        f"VALUES({pid},{spell_id('AIP_LEVELACHIEVEMENT')},-1,56,0,56)")
                    keys=("SKILL_CONCENTRATION", "SKILL_QUICK_CHANT")
                    keys+=(("SONG_STORMS","SONG_CHAOS","SONG_DISSONANCE","INSTRUMENT_DRUMS","INSTRUMENT_HORN","SPELL_MAGIC_MISSILE")
                           if name==BARD else ("SPELL_GROUP_GLOBE",))
                    for key in keys:
                        rating=40 if name==MAGE and key=="SKILL_QUICK_CHANT" else 100
                        sql(f"INSERT INTO player_skills(pid,skill_id,learned,taught) VALUES({pid},{spell_id(key)},{rating},100)")
                    spell=spell_id("SPELL_MAGIC_MISSILE" if name==BARD else "SPELL_GROUP_GLOBE")
                    sql(f"INSERT INTO player_affects(pid,type,duration,modifier,flags,level) "
                        f"VALUES({pid},{spell_id('TAG_MEMORIZE')},-1,{spell},16,56);"*30)
                    if name==BARD:
                        # Human Adaptive's +5 plus this +406 produces the engine's 511-stat ceiling.
                        sql(f"INSERT INTO player_affects(pid,type,duration,location,modifier,flags,level) "
                            f"VALUES({pid},{spell_id('SPELL_PULCHRITUDE')},-1,38,406,0,56)")
                # This fresh fixture changes a Human's faction after creation; it has no real faction history.
                sql(f"UPDATE accounts SET last_good_char=NULL,last_evil_char=NULL WHERE account_name='{MAGE}'")
                process=boot()
                staff=login(journey.CHARACTER); command(staff,"vis 0")
                bard,mage=login(BARD),login(MAGE)
                command(staff,"dummy despawn") # Remove the minimal world's unrelated default target.
                command(bard,"remove all"); command(mage,"remove all")
                for client in (bard,mage): command(client,"consent "+journey.CHARACTER)
                for vnum,keyword in ((1243,"drum"),(1242,"horn")):
                    command(staff,f"load obj {vnum}"); command(staff,f"give {keyword} {BARD}")
                cast(staff,"haste",BARD)
                def stats(name): return command(staff,"stat char "+name)
                assert "Racewar: Evil" in stats(MAGE)
                assert re.search(r"Cha:\s*511\b",stats(BARD))
                def marker(song): return "from 'song of "+song+"'" in stats(MAGE)
                def expire(song,started,duration):
                    deadline=started+duration+12
                    while marker(song):
                        assert time.monotonic()<deadline,(song,stats(MAGE))
                        time.sleep(.25)
                    elapsed=time.monotonic()-started
                    assert elapsed>=duration-2,(song,elapsed)
                    return round(elapsed,2)
                if phase in ("all","control"):
                    command(bard,"hold horn"); assert "You start playing" in command(bard,"play dissonance")
                    interrupted=False
                    for attempt in range(20):
                        result,text=cast_result(mage,"group globe of invulnerability")
                        if "The Disharmonist's discord tears apart your concentration!" in text:
                            interrupted=True; break
                        assert result in ("You complete your spell","You abort your spell before"),text
                    assert interrupted,"no casting interruption in 20 long casts"
                    started=time.monotonic(); assert marker("dissonance")
                    before=time.monotonic(); looked=command(mage,"look")
                    lag=time.monotonic()-before
                    assert "The Regression Arena" in looked and lag<2,(lag,looked)
                    result,text=cast_result(mage,"group globe of invulnerability")
                    assert result=="You complete your spell" and "tears apart your concentration" not in text,text
                    command(bard,"play")
                    elapsed=expire("dissonance",started,25)
                    report["dissonance"]={"attempts":attempt+1,"look_seconds":round(lag,3),"immunity_seconds":elapsed}
                    print("PASS real Dissonance mid-cast interrupt, immediate look and 25-second immunity",flush=True)
                    time.sleep(2.2)
                    for spell in ("globe of invulnerability","bless","infravision","detect invisibility"):
                        cast(staff,spell,MAGE)
                    known={"globe of invulnerability","bless","infravision","detect invisibility"}
                    before=known & set(re.findall(r"from '([^']+)'",stats(MAGE)))
                    assert len(before)==4,before
                    command(bard,"remove horn"); command(bard,"hold drum")
                    assert "You start playing" in command(bard,"play chaos")
                    deadline=time.monotonic()+180
                    while not marker("chaos"):
                        assert time.monotonic()<deadline,"no Chaos dispel"
                        time.sleep(.25)
                    started=time.monotonic()
                    after=known & set(re.findall(r"from '([^']+)'",stats(MAGE)))
                    assert len(before-after)==1,(before,after)
                    command(bard,"play")
                    elapsed=expire("chaos",started,10)
                    report["chaos"]={"removed":list(before-after),"immunity_seconds":elapsed}
                    print("PASS real Chaos single-effect removal and 10-second immunity",flush=True)
                    command(staff,"peace"); time.sleep(2.2)
                if phase in ("all","storms"):
                    cast(staff,"globe of invulnerability",MAGE)
                    assert "from 'globe of invulnerability'" in stats(MAGE)
                    command(bard,"remove all"); command(bard,"hold drum")
                    assert "You start playing" in command(bard,"play storms")
                    start=len(mage.transcript)
                    mage.expect_any(("Hurricane winds sweep through the room tearing at you",
                                     "You are savagely tossed around by the freezing squall"),timeout=180)
                    text=bytes(mage.transcript[start:]).decode(errors="replace")
                    assert "from 'globe of invulnerability'" in stats(MAGE)
                    command(bard,"play")
                    report["storms"]={"globe_present":True,"hit":"hurricane" if "Hurricane" in text else "squall"}
                    print("PASS real Storms hit through an active Globe",flush=True)
                if phase in ("all","echo"):
                    cast(staff,"globe of invulnerability",MAGE)
                    pid=sql(f"SELECT pid FROM player_data WHERE name='{BARD}'")
                    def mems():
                        return int(sql(f"SELECT COUNT(*) FROM player_affects WHERE pid={pid} AND type={spell_id('TAG_MEMORIZE')} "
                                       f"AND modifier={spell_id('SPELL_MAGIC_MISSILE')} AND (flags & 16)<>0"))
                    completed=0; echoed=False
                    for _ in range(25):
                        before=mems(); assert before>0
                        result,text=cast_result(bard,"magic missile","human") # Enemy names are hidden across factions.
                        assert result=="You complete your spell",text
                        completed+=1
                        command(bard,"save")
                        deadline=time.monotonic()+10
                        while mems()==before:
                            assert time.monotonic()<deadline,"save did not publish spell use"
                            time.sleep(.05)
                        assert mems()==before-1,(before,mems(),text)
                        if "Your completed spell echoes once more!" in text:
                            echoed=True; break
                    assert echoed,"no spell echo in 25 completed casts"
                    report["echo"]={"completed_casts":completed,"extra_slot_cost":0}
                    print("PASS real completed-spell Echo with exactly one memorized spell consumed",flush=True)
                stop(); process=None
            except BaseException:
                print(output_path.read_text(errors="replace")[-5000:])
                for client in clients: print(bytes(client.transcript[-5000:]).decode(errors="replace"))
                raise
            finally:
                if process and process.poll() is None: stop()
    REPORT.write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server",type=Path,required=True)
    parser.add_argument("--phase",choices=("all","control","storms","echo"),default="all")
    args=parser.parse_args(); run(args.server.resolve(),args.phase)
