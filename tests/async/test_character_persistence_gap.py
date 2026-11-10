#!/usr/bin/env python3
"""What only the text of character creation, entry and death can show.

The behaviour of these paths is checked where it runs: the death journey (a death saves),
the creation prompt journey (the account menu), the MariaDB load harness (duplicate
descriptions, refused stages), test_immutable_migration_runner.py (sealed migrations). What
stays here no harness or journey can show:

  1. a death no longer waits on a recovery event, and coin piles load with the other items;
  2. enter_game() bounds a restored room before it indexes the world;
  3. first-entry starter kit preparation follows the level-one checkpoint, and
     submission waits for its written revision (exercised by the native lifecycle test);
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

# 3. First entry sets the durable pending bit and queues a checkpoint before
# resuming a saved kit or preparing a fresh one. The queue owns the write fence.
checkpoint = enter_game.index("writeCharacter(ch, 1, NOWHERE)")
starter = section(enter_game[checkpoint:], "if (IS_SET(ch->specials.act3, PLR3_STARTER_KIT_PENDING))",
                  "else if (IS_SET(ch->specials.act2, PLR2_NEWBIEEQ)")
assert (enter_game.index("SET_BIT(ch->specials.act3, PLR3_STARTER_KIT_PENDING)")
        < enter_game.index("do_start_deferred_newbie_kit(ch, 0)") < checkpoint)
assert (starter.index("if (!item_creation_grant_resume_starter(ch))")
        < starter.index("load_chaos_new_character_kit(ch, true)")
        < starter.index("load_obj_to_newbies(ch)"))
assert starter.count("load_obj_to_newbies(ch)") == 1

# The queued starter revision fence runs in test_newbie_grant_lifecycle.py.

# 4. The pid of a MariaDB character comes from the in-memory name index.
init_char = section(NANNY, "void init_char(P_char ch)", "\n}\n")
assert init_char.index("ch->only.pc->pid = getNewPCidNumb();") < init_char.index(
    "sql_player_names_set(ch->only.pc->pid, GET_NAME(ch));"
)
allocate_pid = section(NANNY, "int getNewPCidNumb(void)", "\n}\n")
assert (
    allocate_pid.index("const int highest = sql_highest_player_pid();")
    < allocate_pid.index("if (highest == INT_MAX)")
    < allocate_pid.index("return -1;")
    < allocate_pid.index("highestPCidNumb = highest + 1;")
    < allocate_pid.index("return highestPCidNumb;")
), "MariaDB allocates past the name index, refusing an exhausted native PID range"

print("character creation, entry and death: text-only contracts ok")
