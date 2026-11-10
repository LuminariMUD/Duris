#!/usr/bin/env python3
"""Actual privileged recovery dispatch against isolated historical damage."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess

import test_account_recovery_journey as account
import test_creation_prompt_journey as creation
from test_mariadb_combat_journey import make_overlord
from test_kept_character_approval_journey import enter_staff, OWNER, STAFF
from test_kept_character_journey import kept_journey_binary, persistence, login, character_choices, saved_character, pause_writer
from test_character_stat_choice_journey import WebSocketClient


def remove_synthetic_membership(server, pid):
    assert server.process.poll() is not None
    path = server.state_root / "identities/names/catalog.identity"
    data = path.read_bytes()
    version, size, revision = struct.unpack_from("<IIQ", data, 8)
    assert version == 3 and size == len(data) - 56
    payload = data[56:]
    next_pid, count = struct.unpack_from("<qI", payload)
    rows = []
    offset = 12
    for _ in range(count):
        start = offset
        row_pid = struct.unpack_from("<i", payload, offset)[0]
        offset += 6
        for _ in range(2):
            length = struct.unpack_from("<I", payload, offset)[0]
            offset += 4 + length
        offset += 46
        if row_pid != pid:
            rows.append(payload[start:offset])
    assert offset == len(payload) and len(rows) == count - 1
    payload = struct.pack("<qI", next_pid, len(rows)) + b"".join(rows)
    path.write_bytes(data[:8] + struct.pack("<IIQ", version, len(payload), revision + 1)
                     + hashlib.sha256(payload).digest() + payload)
    path.chmod(0o600)


def run(binary, backend):
    inspector = account.ROOT / "bin/tests/kept-character-inspector"
    with persistence(backend) as (environment, sql):
        fixture = account.IsolatedServer(binary, dict(environment, DURIS_WEBSOCKET="TRUE"))
        if backend == "flatfile":
            subprocess.run([str(inspector), str(fixture.state_root), "empty-authorities"], check=True)
        with fixture as server:
            clients = []
            try:
                staff = account.MudClient(server.plain_port)
                clients.append(staff)
                account.create_account(staff, account.OLD_PASSWORD)
                character_choices(staff, STAFF)
                creation.reply(staff, "y", creation.MENU)
                creation.play_saved_character(staff, STAFF)
                creation.reply(staff, "", "Your starter kit is ready")
                staff.expect("Pos: standing >")
                creation.reply(staff, "save", f"Saving {STAFF}.")
                mortal = account.MudClient(server.plain_port)
                clients.append(mortal)
                account.create_account(mortal, account.OLD_PASSWORD, name=OWNER)
                records = {}
                for name in ("Taverek", "Veralis", "Nariven", "Selanth"):
                    character_choices(mortal, name)
                    creation.reply(mortal, "y", creation.MENU)
                    records[name] = saved_character(server, sql, inspector, name)
                    mortal.close()
                    mortal = login(server, OWNER)
                    clients.append(mortal)
                server.shutdown()
                for client in clients: client.close()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{STAFF}'")
                    sql("UPDATE player_data SET account_name=NULL,act3=0 WHERE name='Taverek'")
                    sql("DELETE FROM account_characters WHERE char_name='Taverek'")
                    sql("DELETE FROM player_data WHERE name='Veralis'")
                    sql("UPDATE player_data SET act3=0 WHERE name='Selanth'")
                    sql("DELETE FROM account_characters WHERE char_name='Selanth'")
                else:
                    make_overlord(server.state_root, STAFF)
                    subprocess.run([str(inspector), str(server.state_root), "legacy-kept", str(records["Taverek"][0])], check=True)
                    remove_synthetic_membership(server, records["Taverek"][0])
                    (server.state_root / f"players/{records['Veralis'][0]}.snapshot").unlink()
                    subprocess.run([str(inspector), str(server.state_root), "legacy-kept", str(records["Selanth"][0])], check=True)
                    remove_synthetic_membership(server, records["Selanth"][0])
                creation.reboot(server)
                staff = enter_staff(server)
                clients.append(staff)
                pid = records["Taverek"][0]
                output = creation.reply(staff, f"keptchar inspect {pid} Taverek", "snapshot=1")
                assert "snapshot=1" in output and "mapping=-" in output, output
                creation.reply(staff, f"keptchar attach {pid} Wrongname {OWNER} synthetic-case", "refused")
                cached = login(server, OWNER)
                clients.append(cached)
                if sql:
                    sql("DELIMITER //\nCREATE TRIGGER kept_recovery_reject BEFORE UPDATE ON player_data FOR EACH ROW BEGIN IF OLD.name='Taverek' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic rollback'; END IF; END//\nDELIMITER ;")
                    creation.reply(staff, f"keptchar attach {pid} Taverek {OWNER} synthetic-case", "refused")
                    assert sql(f"SELECT COALESCE(account_name,'NULL') FROM player_data WHERE pid={pid}") == "NULL"
                    assert sql(f"SELECT COUNT(*) FROM account_characters WHERE pid={pid}") == "0"
                    sql("DROP TRIGGER kept_recovery_reject")
                creation.reply(staff, f"keptchar attach {pid} Taverek {OWNER} synthetic-case", "Kept recovery committed")
                creation.reply(staff, f"keptchar attach {pid} Taverek {OWNER} synthetic-case", "Kept recovery committed")
                known = records["Selanth"][0]
                creation.reply(staff, f"keptchar attach {known} Selanth {OWNER} synthetic-known-owner", "Kept recovery committed")
                assert saved_character(server, sql, inspector, "Selanth") == records["Selanth"]
                assert saved_character(server, sql, inspector) == records["Taverek"]
                creation.reply(cached, "1", "Taverek")
                cached.close()
                legitimate = records["Nariven"][0]
                creation.reply(staff, f"keptchar release {legitimate} Nariven {OWNER} synthetic-refusal", "refused")
                assert saved_character(server, sql, inspector, "Nariven") == records["Nariven"]
                broken = records["Veralis"][0]
                expected_owner = "-" if sql else OWNER
                creation.reply(staff, f"keptchar inspect {broken} Veralis", "snapshot=0")
                creation.reply(staff, f"keptchar release {broken} Veralis {expected_owner} synthetic-release", "Kept recovery committed")
                probe = WebSocketClient(server.websocket_port)
                result = probe.command("validate_name", {"name": "vErAlIs"})
                assert result.get("valid") or result.get("available"), result
                probe.close()
                mortal = login(server, OWNER)
                clients.append(mortal)
                character_choices(mortal, "Veralis")
                creation.reply(mortal, "y", creation.MENU)
                creation.play_saved_character(mortal, "Veralis")
                replacement = saved_character(server, sql, inspector, "Veralis")
                assert replacement[0] > broken and replacement[1] == 0
                creation.reply(staff, f"keptchar attach {replacement[0]} Veralis {OWNER} synthetic-live", "Refused: live/pending")
                creation.reply(staff, f"keptchar release {broken} Veralis {expected_owner} synthetic-repeat", "refused")
                assert saved_character(server, sql, inspector, "Veralis") == replacement
                mortal.close()
                server.shutdown()
                staff.close()
                creation.reboot(server)
                assert saved_character(server, sql, inspector) == records["Taverek"]
                assert saved_character(server, sql, inspector, "Veralis") == replacement
                staff = enter_staff(server)
                clients.append(staff)
                mortal = login(server, OWNER)
                clients.append(mortal)
                creation.reply(mortal, "1", "Taverek")
                creation.reply(mortal, "Taverek", "(Y/N)")
                with pause_writer(server, sql, pid):
                    creation.reply(mortal, "y", "Saving your character")
                    mortal.close()
                    creation.reply(staff, f"keptchar release {pid} Taverek {OWNER} synthetic-pending-save", "Refused: live/pending")
                mortal = login(server, OWNER)
                clients.append(mortal)
                creation.reply(mortal, "1", "Taverek")
                creation.reply(mortal, "Taverek", "(Y/N)")
                creation.reply(mortal, "y", "PRESS RETURN")
                creation.reply(mortal, "", "Your starter kit is ready")
                mortal.expect("Pos: standing >")
                creation.reply(mortal, "save", "Saving Taverek.")
                after = saved_character(server, sql, inspector)
                assert after == (pid, 1, records["Taverek"][2]), (records["Taverek"], after)
                server.shutdown()
                mortal.close()
                staff.close()
                grant = server.run_root / f"journals/critical/starter-kits/{pid}.kit"
                evidence = grant.read_bytes()
                assert evidence[0] == 1
                pending = bytes([0]) + evidence[1:-32]
                grant.write_bytes(pending + hashlib.sha256(pending).digest())
                grant.chmod(0o600)
                creation.reboot(server)
                staff = enter_staff(server)
                clients.append(staff)
                creation.reply(staff, f"keptchar inspect {pid} Taverek", "pending/live=1")
                creation.reply(staff, f"keptchar release {pid} Taverek {OWNER} synthetic-pending-grant", "Refused: live/pending")
                assert saved_character(server, sql, inspector) == after
                server.shutdown()
                grant.write_bytes(evidence)
                grant.chmod(0o600)
                print(f"PASS {backend} privileged inspection/attach/release, rollback/refusal, live/pending save/grant guards, PID-safe name reuse and cold account entry", flush=True)
            finally:
                for client in clients: client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mariadb", "flatfile"), default="flatfile")
    parser.add_argument("--server", type=Path)
    args = parser.parse_args()
    with kept_journey_binary(args.server, args.backend) as binary:
        run(binary, args.backend)
