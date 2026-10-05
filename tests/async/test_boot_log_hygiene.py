"""Source contracts for the boot-time log hygiene fixes.

Each assertion below guards a defect that showed up as an error or warning in
logs/log/* on a clean boot.
"""

from _paths import SRC
import re
from pathlib import Path
from contract_text import contains, find, index, split_at

ROOT = Path(__file__).resolve().parents[2]


# --- logs/log must exist before the game opens its log files -----------------
# logit() uses fopen(); a missing logs/log silently drops every log write.
cycle = (ROOT / "scripts/cycle_mud.sh").read_text()
assert "mkdir -p logs/log" in cycle
# Rotation must not carry off the tracked placeholder that keeps the dir alive.
assert "! -name .gitignore" in cycle
assert (ROOT / "logs/log/.gitignore").is_file()


# --- routine persistence traces are opt-in ----------------------------------
# A shopkeeper line for each shop on every boot, and locker moves on every save,
# filled the debug log; DURIS_PERSISTENCE_TRACE turns them on, failures stay on.
lockers = (SRC / "storage_lockers.c").read_text()
shop_restore = (SRC / "sql_player.c").read_text()
for text, line in [(shop_restore, "sql_restore_shopkeepers: shop %d"),
                   (lockers, "Locker save start:"),
                   (lockers, "LockerToPFile: saving private chest"),
                   (lockers, "LockerToPFile: private chest scan complete"),
                   (lockers, "LockerToPFile: moving public chest contents"),
                   (lockers, "LockerToPFile: moving loose room object"),
                   (lockers, "PFileToLocker: moving carried object")]:
    before = text[:text.index(line)].splitlines()[-8:]
    assert any("if (persistence_trace_enabled())" in row for row in before), line
for line in ("LockerToPFile: missing chest object", "LockerToPFile: failed to save private chest",
             "LockerToPFile: aborting before non-private chest moves"):
    before = lockers[:lockers.index(line)].splitlines()[-3:]
    assert not any("persistence_trace_enabled" in row for row in before), line
utility = (SRC / "utility.c").read_text()
assert contains(utility, 'getenv("DURIS_PERSISTENCE_TRACE")')
assert "`DURIS_PERSISTENCE_TRACE`" in (ROOT / "docs/operations/CONFIGURATION.md").read_text()


# --- SQL queued during boot must not be thrown away --------------------------
# The writer starts after every fatal world-data load, and it refused what boot queued
# before that ("sql job not queued"): artifact rows, outpost hit points, cache reads.
# Until the writer start, sql_queue() and sql_read() apply on the boot connection.
run_the_game = (SRC / "comm.c").read_text().split("int run_the_game(int port, int sslport)", 1)[1]
assert run_the_game.count("sql_async_boot_done();") == 1
assert index(run_the_game, "player_save_pipeline_init()") < index(run_the_game,
                                                                  "sql_async_boot_done();")
# The artifact lists are read once the boot's world is final. Read in the middle of boot,
# every one was dropped as stale when boot loaded an artifact afterwards: an owned one from
# its row, or all of them when a generation or a copyover is restored.
game_loop = (SRC / "comm.c").read_text().split("void game_loop(int port, int sslport)", 1)[1]
assert game_loop.count("arti_cache_init();") == 1
for restore in ("copyover_recover(", "redis_world_recovery_boot_clear();",
                "initialize_transport();"):
    assert index(game_loop, restore) < index(game_loop, "arti_cache_init();"), restore
artifact = (SRC / "artifact.c").read_text()
assert artifact.count("arti_cache_init();") == 0


# --- a connection line carries the logger's time stamp and no second one -----
# Quit, enter game, rent, void and lost link each added the time shifted by a fixed four
# or five hours and labelled EST, which is wrong for half of every year.
for name, line in (("actoth.c", '"%s has quit in [%d]."'),
                   ("nanny.c", '"%s [%s] enters game.%s [%d]"'),
                   ("specs.room.c", '"%s [%s] has rented out in [%d]."'),
                   ("limits.c", '"%s has voided in [%d]."'),
                   ("comm.c", '"%s [%s] has lost link."')):
    text = (SRC / name).read_text()
    assert line in text, line
    assert not re.search(r'\bEST\b', text), name


# --- a peer that closes its connection is not a read error -------------------
# End of file, a reset and TLS ended without a close each wrote a line from the read,
# beside the one close_socket() writes for every descriptor it closes.
process_input = (SRC / "comm.c").read_text().split("int process_input(P_desc t)", 1)[1]
process_input = process_input.split("\n}\n", 1)[0]
assert "EOF encountered" not in process_input
for closed in ("GNUTLS_E_PREMATURE_TERMINATION", "GNUTLS_E_PULL_ERROR", "ECONNRESET"):
    assert contains(process_input, "!= " + closed), closed


# --- an absent mud_info page is its normal state ------------------------------
# The creation lock is an optional row that no migration seeds, and every new-character
# name logged that it "doesn't exist". The MariaDB lookup is the file's second.
sql = (SRC / "sql.c").read_text()
lookup = sql[sql.rindex("string get_mud_info(const char *name)"):].split("\n}\n", 1)[0]
assert contains(lookup, "mud_info.find(") and "logit(" not in lookup


# --- a shutdown with profiling off reports no profile -------------------------
# Every shutdown wrote a "Profile info" line of zeros for each event function.
shutdown = (SRC / "comm.c").read_text().split("int run_the_game(int port, int sslport)", 1)[1]
profile = shutdown[index(shutdown, "if (do_profile)"):index(shutdown, "save_func_call_info();")]
assert shutdown.count("save_func_call_info();") == 1 and contains(profile, "PROFILES(SAVE);")


# --- the donation subscriber must not block the game loop --------------------
# A blocking Redis subscriber socket stalled every idle pulse and showed up as
# a once-per-second NEVENT SLOW entry in logs/log/status.
donation_runtime = (SRC / "redis_donation_runtime.c").read_text()
check = donation_runtime.split("void check_donation_messages(void)", 1)[1]
check = check.split("} // namespace", 1)[0]
assert contains(check, "redis_donation_worker_take")
for forbidden in ("redisGetReply", "redisBufferRead", "redisConnect", "poll("):
    assert not contains(check, forbidden)
donation_worker = (SRC / "redis_donation_worker.c").read_text()
assert contains(donation_worker, "poll(&descriptor, 1, 100)")
assert contains(donation_worker, "redisBufferRead(")
assert contains(donation_worker, "redisGetReplyFromReader(")
# src/poll.h shadows <poll.h> through the Makefile's -I. include path.
assert contains(donation_worker, "#include <sys/poll.h>")


# --- account saves must not emit a NULL pid ----------------------------------
# account_characters.pid is NOT NULL; writing NULL aborted the whole account
# transaction, discarding the accounts and account_ips writes with it.
sql_player = (SRC / "sql_player.c").read_text()
# Anchor on the definition; the bare signature also matches the prototype.
# The MariaDB definition follows the flat-file stub.
save_chars = split_at(sql_player, "bool sql_save_account(struct acct_entry *acc)\n{", 2)[2]
save_chars = save_chars.split("\n}\n", 1)[0]
assert contains(save_chars, "if (pid <= 0)\n\t\t\t\t\tcontinue;")
assert not contains(save_chars, '"NULL"')


# --- a missing ban file is a normal state, not a failure ---------------------
actwiz = (SRC / "actwiz.c").read_text()
read_ban = actwiz.split("void read_ban_file(void)", 1)[1].split("\nvoid ", 1)[0]
assert contains(read_ban, "errno != ENOENT")
assert contains(actwiz, "#include <errno.h>")


# --- only an owned artifact with a zero timer is worth warning about ---------
artifact = (SRC / "artifact.c").read_text()
artifact_lines = artifact.splitlines()
timer_warnings = [
    n
    for n, line in enumerate(artifact_lines)
    if "WARNING: timer was" in line and "resetting to 10 days" in line
]
assert len(timer_warnings) == 3
for n in timer_warnings:
    # clang-format wraps the logit() call, so the ownership guard sits a couple
    # of lines above the message rather than immediately before it.
    window = [line.strip() for line in artifact_lines[max(0, n - 4) : n]]
    assert any(g in window for g in ("if (owned)", "if (new_owned)")), window


# --- MAX_TRADE must cover the largest trade list shipped in world.shp --------
config_h = (SRC / "config.h").read_text()
max_trade = int(re.search(r"#define MAX_TRADE\s+(\d+)", config_h).group(1))

shop_file = ROOT / "areas/world.shp"
if shop_file.is_file():
    lines = shop_file.read_text(encoding="latin-1").split("\n")
    longest = 0
    i = 0
    while i < len(lines):
        if not (lines[i].startswith("#") and lines[i].rstrip().endswith("~")):
            i += 1
            continue
        i += 1
        if i < len(lines) and lines[i].strip() == "N":
            i += 1
        while i < len(lines) and lines[i].strip() != "0":  # produce list
            i += 1
        i += 3  # terminator, buy %, sell %
        traded = 0
        while i < len(lines) and lines[i].strip() != "0":  # trade type list
            traded += 1
            i += 1
        longest = max(longest, traded)
    assert max_trade >= longest, f"MAX_TRADE {max_trade} < world.shp needs {longest}"

# --- the rose flavour event must not hand out a NULL object ------------------
# Object vnum 6107 is not in the world, so read_object() returns NULL and
# obj_to_char() logged "no obj: mob" on every occurrence.
handler = (SRC / "handler.c").read_text()
rose = handler.split("P_obj flow = read_object(6107, VIRTUAL);", 1)[1][:400]
assert contains(rose, "if (flow)")
assert index(rose, "if (flow)") < index(rose, "obj_to_char(flow, t_ch);")
assert index(rose, "if (flow)") < index(rose, "do_give(t_ch, text, CMD_GIVE);")


# --- the exit log must not report stale errno as a shutdown failure ----------
# LOG_EXIT is also used for normal termination messages.  perror() appended an
# unrelated EAGAIN left by the nonblocking game loop to each of those messages.
utility = (SRC / "utility.c").read_text()
write_line = utility.split("static void write_log_line(const char *filename, const char *line)", 1)[1]
write_line = write_line.split("\n}\n", 1)[0]
assert contains(write_line, "fputs(line, stderr)")
assert not contains(write_line, "perror(")


# --- Heaven's persisted zone number must match its first room vnum -----------
# Zone numbers are defined as first_room_vnum / 100; Heaven begins below 100.
heaven_zone = (ROOT / "areas/zon/heavens.zon").read_text()
assert heaven_zone.startswith("#0\n")


# --- ACT_SPEC is derived from assigned functions -----------------------------
# boot_mobiles() strips an unassigned source bit and sets it when a function is
# present.  Keeping the derived bit out of active area sources prevents dormant
# prototypes from producing configuration warnings when they eventually spawn.
active_area_names = [
    line.split()[0]
    for line in (ROOT / "areas/AREA").read_text().splitlines()
    if line.strip() and not line.lstrip().startswith(("*", "#"))
]
for area_name in active_area_names:
    mob_source = (ROOT / f"areas/mob/{area_name}.mob").read_text()
    headers = list(re.finditer(r"(?m)^#(\d+)\n", mob_source))
    for record_number, header in enumerate(headers):
        vnum = int(header.group(1))
        record_end = (
            headers[record_number + 1].start()
            if record_number + 1 < len(headers)
            else len(mob_source)
        )
        record = mob_source[header.end() : record_end]
        if vnum == 9999999 and record == "$~\n":
            continue
        remainder = record
        for _ in range(4):
            remainder = remainder.split("~\n", 1)[1]
        act_flags = int(remainder.split(None, 1)[0])
        assert not act_flags & 1, f"mob {vnum} persists derived ACT_SPEC"


print("boot log hygiene contracts passed")
