# PvP webinfo privacy investigation

Investigated on 2026-10-18 UTC. Scope: test battles 3, 4, and 5; the paired MUD;
the website's database reader, API, and rendered desktop/mobile views.
**Findings only. No application repair or production mutation was performed.**

Website implementation tasks are tracked in the
[dedicated DurisWeb workfile](https://github.com/LuminariMUD/DurisWeb/blob/master/docs/ongoing-projects/2026-10-18-durisweb-pvp-privacy-workfile.md).

**The equipment snapshots were captured, but the publication privacy contract
is broken on both ends.** The MUD captures every participant's equipment and
public-log buffer without recording their `webinfo` setting. The website
filters only the separate equipment field using the player's current saved
flag and publishes their combat log regardless. There is also a confirmed
conversation disclosure: seven outgoing whisper messages, including their
text, are present in the public battle 3 log.

The earlier explanation that Pil's equipment was hidden by a saved privacy
setting was accurate about that single API field, but incomplete about the
test sequence and wrong as reassurance about overall POV privacy.

## Intended behavior confirmed by the owner

`webinfo off` means **do not publish that player's own POV**. It does not restrict
what that player can see in the game or which otherwise-public opponent POVs
they can view. The private player's combat log and equipment must not be sent
to anonymous readers just because another participant permits publication.
An opponent's own permitted account of the fight remains a separate POV.

Private conversations need their own protection too. A tell, whisper, or other
private message must not become public through a participant's log. Disabling
publication of one player's POV cannot protect a message that was incorrectly
classified as public in somebody else's permitted POV.

The owner supplied the following test settings. Routes below use the configured
website origin, `SITE_URL`, to keep this repository document portable.

| Order and route | Stored battle time in UTC | Pil at the battle | Zahm at the battle | POVs eligible under those settings |
| --- | --- | --- | --- | --- |
| Oldest: `/pvp/3?pov=Zahm` | 2026-10-16 03:30:05 | On | Off | Pil only |
| Second: `/pvp/4?pov=Pil` | 2026-10-16 03:32:38 | On | On | Both |
| Last: `/pvp/5` | 2026-10-16 03:34:39 | Off | Off | Neither |

This is a publication rule for each participant, not a rule to erase the battle
metadata or suppress everyone on a team. Whether later switching `webinfo` off
should additionally withdraw previously public POVs is a separate historical
visibility decision. The current implementation records no battle-time privacy
state with which to preserve the distinct outcomes of this test matrix.

## What the live evidence shows

At inspection, `respect_webinfo_toggle=true` and `pvp_delay_minutes=15`.
All three battles are long past that release delay. In `player_data`, Pil's
saved `PLR2_WEBINFO` bit is off and Zahm's is on. Consequently, **all three
public responses show Zahm's equipment, hide Pil's equipment, and expose both
players' entire stored combat logs**.

Read-only SQL and fresh requests to both the public origin and local backend
agree for all six participant records. Every returned log equals its stored
snapshot exactly. Every returned equipment field follows the current saved
bit, not the settings supplied for each battle. Public responses were dynamic;
this is not a stale Cloudflare response or a POV-selector mix-up.

| Battle | Player and role | Stored equipment lines | Stored equipment characters | Stored log characters | Public equipment | Public log |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 3 | Pil, victim | 21 | 1,923 | 37,028 | Hidden | Full stored log |
| 3 | Zahm, killer | 22 | 1,739 | 46,321 | Visible | Full stored log |
| 4 | Pil, killer | 18 | 1,716 | 35,068 | Hidden | Full stored log |
| 4 | Zahm, victim | 18 | 1,413 | 46,020 | Visible | Full stored log |
| 5 | Pil, victim | 15 | 1,285 | 33,663 | Hidden | Full stored log |
| 5 | Zahm, killer | 19 | 1,499 | 27,475 | Visible | Full stored log |

The captured logs corroborate several of the owner's settings without requiring
access to private chat contents:

- Zahm's battle 3 log contains an on confirmation followed by an off confirmation.
- Zahm's battle 4 log contains an on confirmation.
- Zahm's battle 5 log contains off, on, then off confirmations.
- Pil's battle 5 log contains an off confirmation.
- Pil's earlier two retained log buffers have no such confirmation. Their
  battle-time settings come from the owner's test record, not an invented
  database history.

The player rows have been saved since the tests: Zahm's `last_save` is
2026-10-18 06:21:42 and Pil's is 2026-10-17 06:01:54. Therefore today's saved
bits cannot prove what was saved immediately after each October 16 toggle,
whether a later toggle occurred, or the characters' current in-memory state.
The snapshot schema has no privacy-history column, and no complete historical
toggle/save timeline was established. The missing immediate save described
below is a real defect, but it must not be presented as a proven explanation
for every later flag value.

## Confirmed defects

### High priority Private POVs are published in full

MUD `src/combat/fight.c:820`, `combat_outcome_add_participant()`, unconditionally
calls `get_equipment_list(ch, equipment, 1)` and
`GET_PLAYER_LOG(ch)->read(LOG_PUBLIC, MAX_LOG_LEN)`. Neither call is gated by
`PLR2_WEBINFO`. `src/combat/combat_outcome_command.h` carries owned equipment
and log strings; its participant flags record participation/gameplay state, not privacy.
`src/combat/combat_outcome_repository.c:332` inserts both strings into
`pkill_info`. The live table likewise has no captured privacy field.

The website's [getPvPEventDetail](https://github.com/LuminariMUD/DurisWeb/blob/ade01ddcea70c0448825a0b4ab3e8ba77982aae4/backend/src/services/pvpService.ts)
conditionally selects `p.equip`, but always selects `p.log`. Its public
`GET /api/pvp/events/:event_id` handler does not authenticate the reader.
The API therefore publishes every participant's log even when the database
flag is off. Disabling the viewer's own `webinfo` does not affect this query;
the missing control is on the data being published.

[BattleDetailView.vue](https://github.com/LuminariMUD/DurisWeb/blob/ade01ddcea70c0448825a0b4ab3e8ba77982aae4/frontend/src/views/BattleDetailView.vue) renders
the returned log and offers every returned participant in its POV selector.
Its privacy message applies only to `equip === null`. Desktop, mobile, and
maximized-log rendering use the log independently of that equipment state.
A frontend-only hiding change would leave the anonymous API disclosure intact.

**Live reproduction:** open any of the three battles as Pil. The Equipment
view says it is hidden by privacy settings, while the combat log is readable.
Both POVs of battle 5 are readable despite the owner's both-off test setting.

### High priority Whisper message text enters the public combat log

Zahm's public battle 3 snapshot contains **seven outgoing whisper message
lines with quoted message bodies**. Their text is intentionally omitted here.
These lines precede the retained on/off confirmations, so they do not establish
the toggle state at the instant each whisper was sent. They do establish that
private conversation text entered the buffer subsequently published as this
battle's POV, which the owner identifies as opted out at battle time.

MUD `src/cmd/actcomm.c:1204`, `do_whisper()`, sends the sender's echo with the
`send_to_char(message, character, OutputContext)` overload. In
`src/net/comm.c:4687`, that overload selects `LOG_PUBLIC`. Recipient whisper
delivery uses `act(..., TO_VICT, context)` without `ACT_PRIVATE`; the common
`act()` delivery path at `comm.c:5977` also chooses `LOG_PUBLIC` in that case.
The chat styling channel `ChatWhisper` does not itself make the log private.

The ordinary private-channel paths are different:

| Channel | Inspected MUD path | Logging classification |
| --- | --- | --- |
| Tell and reply | `actcomm.c:1038`; reply delegates to tell at 1020 | Message bodies use `LOG_PRIVATE` for sender and recipient |
| Group chat | `src/cmd/actnew.c:222`, `do_gsay()` | Direct recipient delivery uses `ACT_PRIVATE`; sender echo uses `LOG_PRIVATE` |
| Guild chat | `actcomm.c:525`, `do_gcc()` | Sender and recipient message bodies use `LOG_PRIVATE` |
| Alliance chat | `src/guild/alliances.c:420`, `do_acc()` | Sender and recipient message bodies use `LOG_PRIVATE` |
| Whisper | `actcomm.c:1204` | Sender and recipient content can enter `LOG_PUBLIC` |

The real `PlayerLog` implementation keeps its private and public buffers
separate. Reading `LOG_PUBLIC` does exclude correctly classified private
messages. There is no evidence here that ordinary tells are being copied from
the private buffer into PvP. A format-pattern scan found no ordinary tell or
group-say message lines in the six inspected logs; that bounded scan is not a
guarantee for every channel, NPC script, or message format.

`do_ask()` also uses public-default delivery for directed message bodies and
needs a deliberate channel-policy review. No ask-message incident was verified
in these battles. Public bystander notices such as someone whispering are
distinct from disclosure of the whisper's actual text.

MUD ADR 0003 and `test_chat_log_privacy.py` protect server chat logs and the
command-debug ring. Their passing checks do **not** cover this separate
`PlayerLog` → PvP snapshot → anonymous website publication path.

### High priority The equipment privacy field can be bypassed inside the log

Pil's public battle 4 response has `equip: null`, but its `log` contains all
**18 equipment lines** from the saved equipment snapshot. The browser renders
those lines in the combat log while the Equipment view displays its privacy
message. This was verified by exact line comparison and rendered DOM checks.

MUD `src/cmd/actinf.c:8703`, `do_equipment()`, sends its listing through the
public-default `send_to_char()` overload. The website filters only the separate
equipment column; it does not remove equipment text already in `p.log`.
Under the owner's corrected contract, withholding the private POV must include
the entire log. Merely hiding the equipment dialog cannot provide that privacy.

### Historical visibility uses mutable current state

The website joins `pkill_info.pid` to today's `player_data.pid` and tests
`player_data.act2 & 134217728`. This is the correct numeric mask for the MUD's
`PLR2_WEBINFO`; there is no bit-number mismatch. The problem is which point in
time that flag represents and that it is applied to only one field.

An isolated MariaDB reproduction executed the deployed detail-query function
against synthetic battles 3–5. Changing only the current player flags changed
equipment visibility on all three existing events together. Turning both flags
off hid both equipment fields but left both logs and equipment embedded inside
those logs readable. Removing a current player row also hid its equipment while
still publishing its log.

Preserving the owner's per-battle test outcomes requires an authoritative
publication decision captured with the battle. Decide separately whether a
later opt-out can revoke an earlier permitted snapshot. A later opt-in must
not accidentally publish previously private buffered text. The rolling public
buffer retains messages across toggles, and the current toggle handler does not
clear or mark that buffer; gating only the moment of death is not a complete
answer to privacy during an earlier off interval.

### The MUD toggle does not immediately propagate or acknowledge persistence

At `src/cmd/actoth.c:5729`, the webinfo branch changes the live character's
`act2` flag with `PLR2_TOG` and calls `sql_webinfo_toggle()`. The MySQL
implementation at `src/sql/sql.c:2584` checks the character and then does
nothing. The live MUD executable was inspected without attaching a debugger:
its `sql_webinfo_toggle()` machine code returns immediately. The current
`do_toggle()` body has no save request or dirty-status mark.

The displayed on/off confirmation therefore does not establish that the
website's SQL reader has received the change. A small native harness using
the extracted production toggle helpers confirms that the in-memory flag
changes while a persisted-state fixture remains unchanged until a separate
checkpoint is modeled.

**This is not a claim that the setting never saves.** Normal saves include
`act2`: `src/player/player_snapshot_capture.c:184` captures it, and
`player_snapshot_repository.c:254` writes status fields. Current source
registers a dirty-player checkpoint every 30 seconds at
`src/world/new_events.c:2104`; that checkpoint marks status for logged-in
characters to update playtime. Manual saves, autosaves, and terminal/death
saves also provide propagation paths. Scheduling and writer failures can delay
durability, so 30 seconds is not an unconditional acknowledgement guarantee.

Different save timing for a dying victim and surviving killer can create a
temporary difference between their saved flags. This is a supported mechanism,
not a reconstructed history of these three fights. Their later save times and
the absence of recorded battle-time flags prevent that stronger conclusion.

Reuse the existing status-persistence pattern in
`src/player/output_preferences.c:37` when repairing the toggle, including
failure handling. Do not promise publication privacy based solely on a
successful in-memory bit flip.

The website's admin setting description also documents `tog web info`, while
the MUD's canonical option is the single token `webinfo`. The checked command
form is `toggle webinfo on` or `toggle webinfo off`. Refreshing the page or
saving manually can update the existing equipment filter; neither fixes the
unconditional combat-log publication or the missing historical policy.

## Repair boundaries and acceptance criteria

1. Enforce the participant's publication decision on the MUD side when preparing
   exportable POV data, and preserve an authoritative privacy state through the
   combat payload and database transaction. Keep ordinary game reception,
   personal recall, battle metadata, and permitted opponent POVs independent.
2. Enforce the same decision in the website API for **both log and equipment**,
   then render an intentional private-POV state on desktop and mobile. Returning
   raw private fields and hiding them in Vue is insufficient. Distinguish private
   snapshots from genuinely missing historical data.
3. Correct private message classification, starting with the confirmed whisper
   sender and recipient paths. Test tells, replies, group, guild, alliance, and
   whisper bodies independently of `webinfo`; an opted-in recipient must not
   republish another player's private message.
4. Propagate toggle changes through the supported persistence path and report
   pending/failure outcomes accurately. Test both directions, a queued save,
   writer failure, disconnect/reconnect, and victim/survivor save timing.
5. Define historical visibility and buffer behavior explicitly. Repeat the
   owner's three-battle matrix with synthetic participants: permitted POVs at
   capture are Pil only, both, then neither. Verify API fields and rendered
   controls, and verify that toggling later cannot silently expose an off-period
   buffer. Test missing/deleted current player rows and the global admin override.
6. Review already stored/published snapshots separately. The six raw snapshots
   exist, and battle 3 contains confirmed whisper text. Fixing future capture
   alone cannot remove already published content. Do not guess historical
   consent for unrelated battles or silently backfill privacy from today's bit.

No historical data edit, migration, setting change, restart, or new combat test
was performed. The owner asked for findings; these are acceptance criteria for
a subsequent implementation, not a claim that the defects have been repaired.

## Verification and reproducibility

Source revisions inspected:

- Website: `ade01ddcea70c0448825a0b4ab3e8ba77982aae4`.
- MUD: `e07b51a6d84c4010a89a333b9cafc00d804717f2`.

Both source worktrees started clean. Source HEAD is not assumed to identify the
running MUD: the active executable was hashed and inspected directly, and its
hash differs from the staged `dms_new`. The running game process started after
the October 16 test fights. Current runtime inspection verifies the present
no-op, not the exact executable used for every historical fight. The public
captured messages are direct evidence of what reached those battle snapshots.

Temporary scripts, sanitized summaries, executable hashes, and screenshots are
outside the checkout in a private `durisweb-webinfo-audit-20261018.*` directory
under the system temporary directory. The temporary SQL server used port 46237,
its own data directory, and synthetic records only; it was shut down after use.
No live database environment was used for fixture writes. Secret values, raw
chat text, equipment descriptions, and account records are excluded from this
report.

| Command or check | Result and scope |
| --- | --- |
| Read-only Node/mysql2 transactions and fresh public/local `GET /api/pvp/events/{3,4,5}` requests | Six stored/public/origin comparisons agree; API logs exactly match stored snapshots; equipment follows current saved flags; all six raw equipment snapshots exist |
| `node "$PVP_AUDIT_DIR/sql-reproduction.mjs"` | Deployed `getPvPEventDetail()` body executed with an isolated SQL pool and settings/time helpers; reproduced current-state changes across all three events, both-off log disclosure, embedded equipment disclosure, and missing-player behavior |
| `NODE_ENV=test TEST_PVP_DB_PORT=46237 pnpm --dir backend test --runInBand src/services/__tests__/pvpService.test.ts` | 35 passed, including actual SQL cases on the disposable instance |
| `pnpm --dir frontend test:unit --run src/views/__tests__/BattleDetailView.spec.ts` | 8 passed |
| `python3 tests/async/test_combat_outcome_transactional_cutover.py` in the MUD repository | 5 passed; capture ownership, public-buffer selection, codec/schema/transaction source contracts |
| `python3 tests/async/test_chat_log_privacy.py` in the MUD repository | Passed; server `LOG_CHAT` and command-debug contracts only |
| `g++ -std=c++20 -Wall -Wextra -Werror -I"$MUD_DIR/src" "$PVP_AUDIT_DIR/mud-boundary.cpp" -o "$PVP_AUDIT_DIR/mud-boundary"`, then the executable | Extracted toggle helper behavior and real private/public `PlayerLog` buffer separation passed |
| `node "$PVP_AUDIT_DIR/browser.mjs"` with the existing Chromium library path | Fresh anonymous browser rendered both POVs of all three battles at 1440 × 1000; Pil's hidden Equipment view coexists with readable logs; battle 4 renders its 18 embedded equipment lines; battle 5 repeats the defect at 390 × 844 |
| Browser console, page errors, HTTP failures, framework overlay, and screenshots | No console/page/HTTP errors or framework overlay; meaningful log content and correct requested POV; desktop private-equipment screenshot inspected and mobile screenshot retained privately |
| `git diff --check`, documentation-link check, and `./scripts/check-config-literals.sh` | Passed; local document links resolve and configuration-literal checks accept the report |

Browser plugin not available; the browser checks used existing Playwright and
Chromium without installing dependencies. These checks verify the defective
rendered behavior, not a privacy pass. Existing green tests largely encode the
old equipment-only policy and do not test the owner's publication contract.

Additional commands used: `git status --short`, `git rev-parse HEAD`, targeted
`git log --all` searches, `rg`/`rg --files`, `cat`, `sed`, `nl`, `ps`, and
`systemctl --user show` for source/runtime inspection; Python helpers for
bounded source extraction, hashes and metadata; `nm` and bounded `objdump`
for the live no-op; `mariadb-install-db`, an isolated `mariadbd`, and
`mariadb-admin ping/shutdown` for the disposable fixture. Initial discovery
lookups encountered renamed/missing source paths and were corrected using
`rg --files`. No production service-control command was run for this audit.

Not run: full package suites, package format/lint/type-check commands, production
builds/preflights, migrations, live player toggle/save/chat commands, new live
combat, authenticated mutation flows, or a restart/copyover. This deliverable
changes documentation only. No Website Changelog entry is needed because no
website behavior has been deployed.
