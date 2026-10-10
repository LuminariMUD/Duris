#!/usr/bin/env python3
"""What only the text of character creation, entry and death can show.

The behaviour of these paths is checked where it runs: the death journey (a death saves),
the creation prompt journey (the account menu), the MariaDB load harness (duplicate
descriptions, refused stages), test_immutable_migration_runner.py (sealed migrations). What
stays here no harness or journey can show:

  1. a death no longer waits on a recovery event, and coin piles load with the other items;
  2. enter_game() bounds a restored room before it indexes the world;
  3. a new character's starter kit is granted once, after its baseline save, and withheld
     when that save fails (a crash between them is what the order guards);
  4. a MariaDB character's pid comes from the name index (no journey makes two).
"""

from _paths import SRC


def section(text: str, start: str, end: str) -> str:
    first = text.index(start)
    return text[first : text.index(end, first)]


FIGHT = (SRC / "fight.c").read_text()
LOAD_REPOSITORY = (SRC / "player_load_repository.c").read_text()
NANNY = (SRC / "nanny.c").read_text()

# 1. Code that must not come back.
assert "event_death_extract_retry" not in FIGHT and "schedule_death_extract_retry" not in FIGHT, (
    "a death no longer holds the character for a recovery event"
)
assert "coin_sql" not in LOAD_REPOSITORY, "coin piles load with the other items"

# 2. A restored room is bounded before it indexes world and zone_table.
enter_game = section(NANNY, "void enter_game(P_desc d)", "\n}\n")
assert "r_room = real_room(GET_ORIG_BIRTHPLACE(ch));" in enter_game
assert enter_game.index("if (r_room < 0 || r_room > top_of_world)") < enter_game.index(
    "if (zone_table[world[r_room].zone].flags & ZONE_CLOSED)"
), "enter_game must bound a restored room before indexing world and zone_table"

# 3. One starter grant, after the baseline save, withheld when it fails.
newbie_grant = NANNY[NANNY.index("if (!GET_LEVEL(ch))") :]
newbie_grant = newbie_grant[: newbie_grant.index("else if (IS_SET(ch->specials.act2")]
assert newbie_grant.count("load_obj_to_newbies(ch)") == 1
assert (
    newbie_grant.index("do_start_deferred_newbie_kit(ch, 0)")
    < newbie_grant.index("if (writeCharacter(ch, 1, NOWHERE))")
    < newbie_grant.index("load_obj_to_newbies(ch)")
    < newbie_grant.index("starter kit withheld")
), "a new character's kit is granted after its baseline save, and withheld if that fails"

# 4. The pid of a MariaDB character comes from the in-memory name index.
init_char = section(NANNY, "void init_char(P_char ch)", "\n}\n")
assert "sql_player_names_set(ch->only.pc->pid, GET_NAME(ch));" in init_char
assert "highestPCidNumb = sql_highest_player_pid() + 1;" in NANNY

print("character creation, entry and death: text-only contracts ok")
