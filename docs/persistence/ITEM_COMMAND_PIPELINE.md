# Item command pipeline

Item commands (get, drop, put, give, empty) move the object in memory at once. The next save of
each owner records where it went; nothing waits on the database (see
[the persistence reset plan](../ongoing-projects/2026-09-28-persistence-memory-authority-plan.md)).

src/item/item_command_parser.h owns only the GET grammar. It turns the legacy
forms into a typed command kind while preserving the existing six behaviors:

| Form | Kind |
| --- | --- |
| get all or get all.<name> | floor bulk |
| get <object> | floor item |
| get all from <container> or get all.<name> from <container> | container bulk |
| get <object> from <container> | container item |
| get <object> from all | matching item from every eligible container |

The parser is bounded by MAX_INPUT_LENGTH, keeps all.<name> filtering separate
from the command kind, and does not retain the input buffer.

src/item/item_command_policy.h holds the two checks get, put and empty share:
item_command_object_is_takeable() and item_command_container_is_valid().

The bulk forms (get all, drop all, put all, empty) select their items first, check carry and
container limits as they go, then move each one and report once; see
[BATCH_ITEM_COMMANDS.md](../reference/BATCH_ITEM_COMMANDS.md).
