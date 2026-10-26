# Reflection core-dump investigation — 2026-10-26

Scope: every `core.*` file in the project root on October 26. This report records
the investigation and its source-level resolution. No production operation was
performed.

## Finding

All three dumps are one crash family. Reflection marks a newly loaded image NPC's
shared prototype strings as privately owned before calling `setup_pet()`. A change
in commit `5b53d6617f235c047f15053c5c92c9ecdfd63c8a` made `setup_pet()` free a pet name
when that ownership bit is set. It therefore frees mobile 250's shared keyword
pointer on the first image. The second image receives the dangling pointer from the
mobile index and frees it again.

The first two processes detect the invalid free and call `exit(1)`. During that
exit, the static telemetry runtime destroys a still-joinable `std::thread`, so
`std::terminate()` converts the failure into the SIGABRT recorded in the cores.
The third process faults directly while the memory checker dereferences the damaged
allocation header, producing SIGSEGV. The telemetry abort is a secondary shutdown
failure, not a separate initiating crash.

Any route into `spell_reflection()` can expose the defect. The observed triggers
were the Reflection innate and the mentality mace. A one-image cast still frees the
shared prototype string and poisons later mobile-250 loads; the observed four-image
casts fail immediately on their second image.

## Dump inventory and matching executable

All dumps came from `bin/server/dms 7777`. The executable image embedded in each
core has GNU build ID `21a28ca92f53477d5e1c26786caf13cd6c041758`, exactly matching
the available `bin/server/dms`. That binary contains debug information and was used
for all source-level inspection. Its file timestamp is October 25 21:25:45 UTC.
The precise Git revision used to build it is not embedded in the executable, so it
was not independently established.

| Dump | Bytes | Faulting LWP | Signal | Archived trigger |
| --- | ---: | ---: | --- | --- |
| `core.2026.10.25-23.27.18` | 2,290,577,408 | 3483081 | SIGABRT | `innate reflect`, room 83142, 23:27:06 |
| `core.2026.10.25-23.28.20` | 2,259,873,792 | 3651464 | SIGABRT | `innate reflect`, room 83140, 23:28:08 |
| `core.2026.10.26-01.23.53` | 2,296,299,520 | 3652925 | SIGSEGV | mentality-mace activation through `say`, room 80800, 01:23:41 |

The core filenames are about twelve seconds later than the corresponding command
records. They identify completed dump files, not exact command times. Player names
and the mace activation phrase are intentionally omitted.

## Direct core evidence

The common game-thread path is:

```text
str_free                         core/utility.c:536
__free / delmem                  core/memory.c:278 or :309
setup_pet                        classes/necromancy.c:294
spell_reflection                 classes/sillusionist.c:703
```

The first two continue through `do_innate_reflection()` and command dispatch. The
third continues through `mentality_mace()`, `special()`, and command dispatch.

State at `setup_pet()` is the same in all three cores:

- the image is mobile VNUM 250, real-number index 109;
- `image->only.npc->str_mask == 7`, including `STRUNG_KEYS`;
- `image->player.name` is exactly equal to `mob_index[109].keys`;
- the loop is processing image index 1, the second of four images where GDB retained
  those optimized locals; and
- the purported allocation header before the name is already freed or reused. In
  the SIGABRT dumps its tag is not a valid `MEMCHK` tag; in the SIGSEGV dump the tag
  pointer itself is inaccessible.

Those observations directly establish that `setup_pet()` is trying to release the
shared mobile-index string, and that the shared pointer was invalidated before the
second image reached it. The main game thread owns the fault. The other threads are
waiting in their ordinary password, persistence, maintenance, SQL, or telemetry
loops; their stacks do not support a worker race as the initiating cause.

## Source sequence

1. `read_mobile()` loads mobile 250. For normal subsequent loads it assigns
   `mob->player.name = mob_index[nr].keys`; the comment in `world/db.c` explicitly
   says mobs of the same type share this text.
2. `spell_reflection()` assigns
   `STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2` before replacing any of those shared
   fields.
3. It calls `setup_pet()`. Since the caster is a player and `STRUNG_KEYS` is already
   set, `setup_pet()` calls `str_free(mob->player.name)`.
4. That releases `mob_index[109].keys` even though the individual image does not own
   it. The mobile index retains the dangling address.
5. The first image receives a new private name. `spell_reflection()` then overwrites
   that name again with its final image name without releasing the interim pet name,
   which is also a leak but not the crash.
6. The second `read_mobile()` copies the dangling index pointer to the next image.
   Its `setup_pet()` attempts the second free. `delmem()` either reports
   `memory failed check` and exits or faults while reading the stale header.

Commit `5b53d6617` added the conditional `str_free()` and the corresponding
`STRUNG_KEYS` assignment in `setup_pet()`. The earlier reflection code already set
the ownership mask prematurely. The crash is the interaction between those two
behaviors; the October 25 change is the regression boundary that made the invalid
ownership claim fatal.

## Why existing coverage did not catch it

`tests/async/test_innate_reflection.py` checks innate dispatch, eligibility,
cooldown, and titan rejection, but replaces `spell_reflection()` with a stub. It
does not execute image creation, `read_mobile()`, string ownership, `setup_pet()`, or
more than one generated image. The test passes with leak detection disabled in this
environment; its scope cannot exercise this failure.

A focused regression should execute the real reflection image loop with at least
two mobile-250 instances and the real `setup_pet()` ownership transition under
ASan/UBSan or the server memory checker. It should also assert that the prototype's
`mob_index[].keys`, `desc1`, and `desc2` remain valid after image creation and
cleanup.

## Repair direction

Keep shared template fields unowned until each field is replaced by a private
allocation. In the reflection path, call `setup_pet()` while the freshly loaded
image still has an unowned string mask, release the private interim name that
`setup_pet()` creates before replacing it with the final image name, and set the
three ownership bits only after the final private strings are installed. This
preserves `setup_pet()`'s new cleanup for genuinely owned pet names without teaching
it to infer ownership from pointer identity.

The separate telemetry shutdown symptom should also be tracked: a deep `exit(1)`
bypasses `main()`'s explicit `telemetry_runtime_shutdown()` and
`telemetry_runtime_final_reap()`, leaving the static worker joinable. Fixing that
would make fatal diagnostics cleaner, but it would not repair the reflection
ownership bug and did not cause the direct SIGSEGV dump.

## Resolution

`spell_reflection()` now leaves the freshly loaded prototype strings unowned while
`setup_pet()` installs its private pet name. It releases that interim name before
installing the final image name, long description, and short description, then sets
the three ownership bits. The shared mobile-250 strings therefore remain untouched,
and every private image string has one owner and one cleanup path.

The allocator's invalid-free diagnostic now calls `panic_corruption()` directly
instead of `exit(1)`. A failed memory check consequently aborts at `delmem()` without
running static destruction and without converting the failure into a later
joinable-thread `std::terminate()`.

The focused regressions execute the real four-image Reflection loop and real
`setup_pet()` for both player and NPC casters under ASan/UBSan, verify the prototype
pointers and contents before and after image cleanup, and account for all private
strings. A second process test triggers the real `delmem()` failure with a live
static worker and verifies that the only diagnostic is the allocator panic before
SIGABRT.

## Investigation artifacts

Ignored local evidence is under `bin/analysis/core-dumps-2026-10-26/`: full
main-thread and all-thread backtraces for every dump, focused GDB state captures,
the extracted build-ID inventory, and the existing test output. No core, log, or
player data was added to version control.
