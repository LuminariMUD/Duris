# XML quest engine

This documents the parser and runtime in [nq.c](../../src/cmd/nq.c), checked on
2026-10-30. The [quest-system reference](QUEST_SYSTEMS.md) explains how it relates
to static `.qst` content, bartender quests, tracking, and epic tasks.

## Current reachability and persistence

`nq_list` starts empty. `nq_parse_quest()` reads `quest/<filename>` relative to
the server's working directory. `nq_interface_load()` parses, initializes actors,
and prepends the quest to that list. The checkout has no checked-in `quest/`
directory or XML quest definitions, no boot call to that loader, and no callers
of `do_quest2()` outside this translation unit.

`do_quest2()` defines an interface, but [interp.c](../../src/cmd/interp.c) registers
no `quest2` command. Ordinary `quest` invokes the bartender/daily handler.
The interface below describes existing functions, not available player commands:

- Trusted `load <filename>`: load and create/bind actors.
- Trusted `list`: display loaded definitions, participants, tags, and actors.
- Trusted `delete <id>`: free a loaded definition and actors it created. Its
  non-head unlink assigns `prev` rather than `prev->next`, and it prints
  `Quest not found` even after success; it is not a reliable unload procedure.
- Mortal `show`: display journal text for instances matching the character name;
  its buffer is overwritten per quest, so multiple entries do not all render.
- Mortal `list`/`delete` and trusted `show`: empty stubs.

`nq_save_quest()` is also a stub. XML can contain serialized instances, but
there is no save/reload lifecycle or player snapshot adapter for this engine.
Loaded instances, tags, actors, and journals are process memory. Do not assume
restart/copyover recovery, permanent completion history, or zone-story credit.

Interaction hooks do exist: `do_ask()` and the ordinary whisper branch in
[actcomm.c](../../src/cmd/actcomm.c), object giving in
[actobj.c](../../src/cmd/actobj.c), and the rogue give path in
[rogues.c](../../src/classes/rogues.c) call `nq_action_check()`.
[fight.c](../../src/combat/fight.c) calls `nq_char_death()` for a PC killer before
death cleanup. The current money-give branch returns before the object
give hook; cash requirements cannot be assumed to trigger on giving coins.

## Model and action lifecycle

A quest owns shared actors, actor templates, and a list of named-player
instances. Each instance owns actor bindings, an expiry timestamp, tags, and
journal messages. Instances use the character's name string, not PID/account
identity. An actor template identifies an NPC prototype, possible rooms,
description overrides, common actions, and alternative action sets.

`nq_init_actor()` chooses one room and one action set randomly. If there are no
sets it uses common actions. `nq_load_actor()` reuses an unclaimed matching NPC
in that room within this quest, or loads one. It changes descriptions on reused
NPCs too. Cleanup extracts actors it loaded; it does not restore description
overrides on reused NPCs. This is world mutation, not a private room instance.

`nq_init_quest()` creates shared bindings for templates without template tags.
`nq_accept_quest()` creates instance actors from template index 1 onward,
regardless of those template tags; index 0 is conventionally the shared giver.
Template tags therefore are not a functioning conditional spawn language.

An interaction resolves an actor, then visits its actions in list order. Most
parsed lists prepend entries, so later actions in the XML are tested first.
Alternative-set actions precede the appended common actions. The first action
whose requirements pass consumes its inputs and applies its reward.

An action whose reward grants tags starts a new instance if the character is
not already participating. Admission checks class, race, total instance count,
and the optional exact taught-skill value. Actions with no reward tags can run
without accepting an instance. Existing participants do not repeat admission.

## XML definition language

This is a description of accepted fields, not a validating schema. Unknown
elements are generally ignored. Much parsing uses `atoi()` and fixed arrays
without content validation. Provide valid loaded mobile/object/room VNUMs and
required attributes before exercising a definition in an isolated fixture.

### Root and admission fields

The root must be `<quest>`. Its attributes are:

- `id`: identifier/display name and trusted deletion key.
- `allowedinstances`: integer used by `count < allowed_instances`. Use a positive
  value. Although a struct comment calls `-1` unlimited, the comparison rejects
  new instances with `-1` or 0. The attribute is read without a missing check.
- `duration`: minutes, default 0; acceptance sets `expires = now + duration * 60`.
- `listedclasses="allow"` or `listedraces="allow"`: start an empty allow list.
  Any other/missing value starts with all allowed and listed children exclude.
- `minlevel`, `maxlevel`: parsed integers, currently unused by admission.
- `onceperplayer`, `resetmode`: parsed but unused by lifecycle policy.
  Their comparisons are also inverted: `onceperplayer="YES"` stores false;
  `resetmode="ALWAYS"` selects NEVER, while other strings select ALWAYS in
  the first branch. These attributes do not provide completion/reset guarantees.

Root children `<class>name</class>` and `<race>name</race>` apply to their lists.
Names compare case-insensitively. Classes accept display names or three-letter
codes; races accept spaced names, unspaced names, or two-letter codes from the
server tables. Unknown names log a debug message and do not alter the list.

Optional `<s value="N">skill-or-spell-name</s>` uses the exact `spells` lookup
and requires `skills[id].taught == N` for a new instance, not a minimum skill
test. Multiple root skill nodes replace the same pointer rather than forming
a list. No per-character once-completed check exists.

### Actors and items

Root `<actor>` elements are stored in document order. The parser applies
`atoi()` to the content of the first child node for the actor VNUM; the
documented format uses leading text, for example
`<actor>12300<l>12301</l>...</actor>`. There is no named `<vnum>` handler.
Actor children are:

- `<l>room-vnum</l>`: candidate room; at least one is required for random choice.
- `<kw>...</kw>`, `<short>...</short>`, `<long>...</long>`: NPC text overrides.
- `<a>...</a>`: common action.
- `<aset><a>...</a>...</aset>`: one alternative action set.
- `<t>...</t>`: template tag marker used by the shared-actor initialization test.

An item node likewise begins with a text VNUM:
`<i>12302<kw>token</kw><short>a token</short></i>`. Its optional overrides are
`kw`, `short`, and `long`. As a requirement it matches only the VNUM in the
NPC's carried inventory; overrides apply when creating reward objects.

Constants allocate 10 actor templates, 10 locations per actor, 10 alternative
sets, and 128 item-component slots. Template/location/set iteration relies on
zero/null sentinels, so leave a slot: at most 9 templates, 9 locations, and 9
sets. The counted component array holds up to 128 required items per action.
Parsing does not enforce those bounds. Invalid
or absent prototypes/locations also are not comprehensively rejected.

### Actions and rewards

An `<a>` accepts the following children:

- `<p>phrase</p>`: any one listed phrase must match the entire supplied message,
  case-insensitively. This is not `.qst` keyword matching. A phrase action cannot
  pass an object-give/death event with a null phrase.
- `<i>vnum...</i>`: require distinct carried objects on the NPC; successful
  execution extracts them. Multiple identical VNUM nodes require multiple copies.
- `<t>tag</t>`: require **all** listed instance tags, then consume them on success.
- `<nt>tag</nt>`: forbid any listed tag; forbidden tags are not consumed.
- `<r>...</r>`: reward. Supply one for every action: the runtime dereferences
  `action->reward` without checking for absence. Repeated `r` nodes replace it.

`flag="completed"` marks an action that frees its participating instance after
rewarding. `flag="disappear"` sets a bit with no execution path.
An action's first child text exactly equal to `death` sets its death flag:
`<a>death<r>...</r></a>`. Leading whitespace changes this test. Death actions
run only on the death hook; other actions run only on nondeath hooks.

Reward `<r>` children are `<p>` (an `act()` response and journal entry), `<i>`
(objects), `<t>` (new tags), and `<s value="N">name</s>` (add N to `taught`).
Repeated identical reward tags are deduplicated. A completed action does not
grant its reward tags to the freed instance. A phrase becomes a journal entry
only when an instance exists, with duplicate rendered messages omitted.

Reward objects go to the player for ordinary actions and to the victim NPC
for death actions, before death cleanup. This path calls `read_object()` and
`obj_to_char()` directly, rather than the static/world quest item-grant service.
Its invalid-object handling is incomplete. Cash and XP fields exist in structs,
but the XML action/reward parsers populate neither; XP is never applied here.
The unreachable-through-XML cash reward branch adds `cash / 1000` platinum.
There is no XML coin-cost or XP-reward syntax implemented by this parser.

### Parser illustration

This illustrates mixed text VNUMs, phrase matching, and tags. Numbers are
placeholders. It is not a deployable fixture or a promise of a working command.

```xml
<quest id="Token lesson" onceperplayer="NO" resetmode="NEVER"
       duration="30" allowedinstances="1"
       listedclasses="deny" listedraces="deny">
  <actor>12300<l>12301</l>
    <a><p>help</p><nt>started</nt>
      <r><p>$n asks you to find a token.</p><t>started</t></r>
    </a>
    <a flag="completed"><i>12302</i><t>started</t>
      <r><p>$n thanks you.</p><i>12303</i></r>
    </a>
  </actor>
</quest>
```

The shared giver can start the named participant's instance and later consume
its `started` tag on turn-in. The completion action is tested before the start
action because it was declared later. Numeric VNUM text stays adjacent to the
opening `actor`/`i` tag to make the first-child requirement unambiguous.

### Instance input format

Root `<instance>` input starts with literal questor-name text and may contain `expires`
(Unix seconds), `logentry`, `t`, and `actorinstance`. An `actorinstance` contains
`l`, `templateindex`, and `actionsetindex`; indexes are zero-based and must
refer to an already parsed template and a nonempty alternative set. Templates
must therefore precede instances in the XML. Invalid indexes are logged and
that actor binding is skipped. Leading/trailing whitespace in the name text is
retained, so it can prevent the exact character-name match. There is no writer
for this format.

## Lifecycle limitations

The action comment promises level/slot checks beyond what executes. Only the
class/race, count, optional skill, and actual action conditions described above
are enforced for new instances. Reset modes, level bounds, and once-per-player
are not enforced, and `allowedinstances=-1` is not unlimited.

Expiry is also incomplete: `nq_find_actor()` scans instance-owned actors only
when `expires < now`, the reverse of a normal active-until-expiry condition.
Shared actors are found first and the later participant-name lookup does not
check expiry at all. There is no expiry sweep or automatic reset/respawn loop.
Duration cannot be documented as an enforced time limit.

Required items and tags are consumed before reward execution. There is no
atomic transaction connecting NPC inventory, rewards, journal, and completion,
nor a durable ownership/credit adapter. Parser acceptance alone is insufficient
evidence that an authored quest is safe or playable.

Actor lookup is not an ownership boundary: it can return an instance-owned
actor without checking the interacting character's name. The action path may
then use the caller's existing instance, or retain the actor's instance when
the caller has none. Do not treat these actors as isolated personal quest
instances or assume that name-based journal lookup prevents cross-player
interference.

## Verification

[test_deferred_findings_repairs.py](../../tests/async/test_deferred_findings_repairs.py)
contains source assertions for class/race name resolution and allow/deny handling.
It does not execute a full XML quest. No maintained end-to-end XML quest journey
was found in this checkout. The example above is syntax documentation, not such
a journey. Before enabling this engine, separately qualify command/boot loading,
input validation, actors, admission, tag transitions, giving, death, cleanup,
expiry, reward ownership, and restart/copyover persistence in disposable worlds.
