# Character mechanics connections

[character_mechanics.h](../../src/player/character_mechanics.h) defines the compiled
connection vocabulary. The [aggregator and validators](../../src/player/character_mechanics.c)
enumerate references supplied beside the existing gameplay owners. They observe
implementation and state; gameplay continues through its existing handlers.

Start with `identity_connections()` for native race/class/spec tables and creation,
specialization and ordered-multiclass predicates. `mechanic_connections()` links
typed native bindings by `MechanicId`, relation, owning option and dependencies.
`transition_connections()` adds actual entry registrations, changed/retained state,
cleanup and capture/load dependencies. Specialization identity includes the primary
class and slot; multiclass pairs are ordered. Displayed, true and effective race
remain distinct.

Skill and innate grants come from their real initialized tables in
[skills.c](../../src/classes/skills.c) and [innates.c](../../src/classes/innates.c).
The existing registration functions/macros also retain startup write provenance:
ability, owner, observed level/cap and production caller. `validate_grants()` compares
the last observed write with each native cell and detects missing provenance and
conflicts before an overwritten value disappears. A specialization-specific grant
can override a class-wide default; conflicting specific writes are not implicit
precedence. No saved character fields or gameplay evaluations use the journal.

One existing conflict remains explicit: blindfighting grants Rogue Assassin a cap
of 100, then the later Rogue class-wide grant overwrites it to 90. Its connection
is incomplete, and the native test requires exactly that diagnostic and both
observed values. Current behavior is preserved pending a balance decision.

Run `python3 tests/async/test_character_mechanics.py` for the native bindings,
registration tables, named behavior assertions and mutation checks. Its `CONNECTION`
and `DEPENDENCY` rows identify compiled declarations and graph edges. `GRANT_SITE`
rows identify native startup callers by file, line and column. The reverse check
requires initializer calls to match those locations, and rejects new aliases,
uninvoked callers and removed calls. The exact four comprehension grants inside
`#if 0` remain a reviewed disabled exclusion. Assertion output states the tested
behavior and fixture boundaries. Registration of a callback
does not prove its effect, and a passive's null callback still requires consumers.
The same test resolves every registered spell/poison callback to a unique native
implementation and rejects removal. This is implementation-location evidence only.

Command connections expose the real vocabulary (`names[id - 1]`) and native slots
from [interp.c](../../src/cmd/interp.c). The seven existing assignment macros retain
each observed handler and its position, level, combat, confirmation, grant and
aggression guards. `validate_commands()` compares every field against those writes
and detects conflicting overwrites before they disappear. `COMMAND_SITE` rows use
the same source-location check as grants. New macro aliases/callers and direct
unobserved command writes fail it. Callback resolution accounts for exact command
signatures, `ACMD`, overloads and the three owners with separate backend bodies.
Registration fixtures abort on any unexercised callback; ordinary interpreter gates,
world interception and individual effects remain separate proof obligations.

Creation connections bind Telnet's actual login states and selection handlers,
WebSocket's native command table, lookup and dispatcher, account admission policy,
preflight/commit and `init_char`. Native assertions exercise dispatch and reject
new aliases; the selection and initialization bodies are separate full-server
evidence. `test_creation_prompt_journey.py` covers both transports with private
flat-file servers, normal-mode menus/denials, starter skills, save/restart and
Telnet relog. Human Necromancer is accepted by Telnet but rejected by WebSocket's
faction-derived alignment despite appearing in its menu. Complete changed-state,
body/innate-bit and starter-kit lifecycle ownership remains incomplete.

Disabled transformation connections bind ascend/descend's real command slots,
Theurgist helper and completion callback, legacy descend, and corpseform's real
spell slot/expiry. Native denial assertions compare complete character, PC and
corpse state and require no ledger/save calls. The `--trace disabled` option of
`test_character_mechanics_journey.py` exercises mortal interpreter denials and saved
state in the full world. Staff supplies boundary classes, levels and resources.
Successful completion and unreachable conversion branches remain separate,
incomplete declarations; binding an expiry callback does not prove its lifecycle.

The separate `python3 tests/async/test_character_mechanics_journey.py` drives private
full-world command and persistence cases. Staff-supplied items, levels and transport
are fixture setup and do not prove ordinary acquisition. Native Bulwark cases
currently record the amount delivered to raw damage; they do not prove actual HP
loss. All fixture mode switches and backend/world conditions must accompany proof.

Access (available/conditional/disabled/unresolved), implementation
(connected/incomplete/legacy) and proof (named assertions/failing/unverified) are
independent. A disabled entry may have a proven denial. Existing characters can
use creation-disabled options. Evidence expires when its relevant inputs change.

Migration remains open in [plan.md](../ongoing-projects/plan.md). Source reverse
coverage currently handles selected specialization, multiclass, Revenant and
cleanup sites; it is not yet complete across the server. This reference describes
the implemented contract, not a claim that every character option is qualified.
