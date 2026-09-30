#!/usr/bin/env python3
"""Source-contract checks for the async locker snapshot/pulsed pipeline."""

from _paths import SRC
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
files = {
    "async_c": (SRC / "locker_async.c").read_text(encoding="utf-8", errors="replace"),
    "async_h": (SRC / "locker_async.h").read_text(encoding="utf-8", errors="replace"),
    "lockers": (SRC / "storage_lockers.c").read_text(encoding="utf-8", errors="replace"),
    "interp": (SRC / "interp.c").read_text(encoding="utf-8", errors="replace"),
    "comm": (SRC / "comm.c").read_text(encoding="utf-8", errors="replace"),
    "makefile": (SRC / "Makefile").read_text(encoding="utf-8", errors="replace"),
    "repository": (SRC / "player_snapshot_repository.c").read_text(encoding="utf-8",
                                                                   errors="replace"),
}


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
        return True
    print(f"  FAIL  {name} {detail}")
    return False


def main():
    ok = True
    print("locker async pipeline checks")

    ok &= check("header mark_dirty returns int",
                "int locker_async_mark_dirty" in files["async_h"])
    ok &= check("pulse budget is 1",
                "LOCKER_ASYNC_SNAPSHOTS_PER_PULSE 1" in files["async_h"])
    ok &= check("no in-flight cap: each dirty locker queues its own writer job",
                "LOCKER_ASYNC_MAX_INFLIGHT" not in files["async_h"]
                and "g_inflight" not in files["async_c"])
    ok &= check("the slot and result tables grow instead of refusing",
                "std::deque<struct locker_async_slot> g_slots" in files["async_c"]
                and "std::deque<struct locker_async_result> g_results" in files["async_c"]
                and "LOCKER_ASYNC_SLOTS" not in files["async_c"])
    ok &= check("obj lock only while DIRTY",
                "slot.state == LCHK_DIRTY && slot.user_pid == pid" in files["async_c"])
    ok &= check("terminal priority selection",
                "oldest_terminal" in files["async_c"] and "start_one_snapshot(oldest_terminal)" in files["async_c"])
    ok &= check("the writer applies the captured snapshot through the repository",
                "locker_snapshot_repository_apply_from_pool(*job.snapshot)" in files["async_c"]
                and "player_item_snapshot_list_capture(" in files["async_c"])
    ok &= check("the game thread makes no database call for a locker save",
                all(token not in files["async_c"] for token in (
                    "mysql_", "qry(", "db_query", "sql_get_", "sql_save_locker",
                    "writeCharacter", "sql_persistence_connection", "INSERT INTO")))
    ok &= check("the writer finds or creates the locker, deletes the public rows, then inserts",
                "SELECT id FROM lockers WHERE locker_name=" in files["repository"]
                and "INSERT INTO lockers (locker_name,owner_pid,owner_assoc_id,racewar,race)"
                in files["repository"]
                and "DELETE FROM locker_items WHERE locker_id=" in files["repository"]
                and "insert_item_rows(connection, written, keys," in files["repository"])
    ok &= check("leave marks terminal dirty",
                'locker_async_mark_dirty(chLocker, ch, 1, "leave-terminal")' in files["lockers"])
    ok &= check("save_locker_char marks nonterminal dirty",
                'locker_async_mark_dirty(chLocker, ch, 0, "save_locker_char-nonterminal")' in files["lockers"])
    ok &= check("re-entry counts async busy",
                "locker_async_name_busy" in files["lockers"])
    ok &= check("interp blocks obj cmds while locked",
                "locker_async_player_obj_locked" in files["interp"]
                and "Your belongings are being secured for storage" in files["interp"])
    ok &= check("boot starts locker worker",
                "locker_async_init" in files["comm"])
    ok &= check("pulse wired into game loop",
                "locker_async_pulse" in files["comm"])
    ok &= check("shutdown drain",
                "locker_async_shutdown" in files["comm"] and "locker_async_drain" in files["comm"])
    ok &= check("makefile builds locker_async.o",
                "locker_async.o" in files["makefile"])
    ok &= check("restore view after seal",
                "locker_async_restore_snapshot_view" in files["async_c"]
                and "locker_async_restore_snapshot_view" in files["lockers"])
    ok &= check("prepare snapshot walk before seal",
                "locker_async_prepare_snapshot" in files["async_c"]
                and "locker_async_prepare_snapshot" in files["lockers"])
    ok &= check("inflight coalesce rebuild flag",
                "rebuild_objects" in files["async_c"])
    ok &= check("terminal extract waits for a landed save; a failure retries through the writer",
                "if (r->ok && chLocker && !s->rebuild_objects)" in files["async_c"] and
                "slot_retry_later(s);" in files["async_c"] and
                "s->retry_at > now" in files["async_c"])
    ok &= check("ambiguity prefers non-descriptor locker char",
                "name lookup ambiguous" in files["async_c"] and
                "!ch->desc" in files["async_c"])

    if ok:
        print("All locker async pipeline checks passed.")
        return 0
    print("locker async pipeline checks FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
