# Durable outage and loss evidence

The SQL telemetry worker persists a producer registration before it qualifies
the repository or allows queue admission. It samples bounded counters about once
per second and attempts a final observation before publishing worker completion.
Gameplay capture performs no journal I/O, allocation or wait. The coherent sample
has four bounded attempts; a busy producer can defer a sample rather than delay
gameplay or publish torn queue/counter totals.

This is the bounded gap record that landed in `338092a78`. It does not spool
telemetry payloads, restore lost gameplay facts, or establish historical incident
ends, and nothing publishes a recorded gap into the rollups or reports.

## Local setup

When SQL telemetry is enabled, set `TELEMETRY_OUTAGE_LEDGER_DIR` to an existing,
absolute directory owned by the server's effective user with mode `0700`.
Provision it alongside the other local journals before enabling capture:

```sh
install -d -m 0700 /your/private/local/runtime/telemetry-outages
export TELEMETRY_OUTAGE_LEDGER_DIR=/your/private/local/runtime/telemetry-outages
```

This path alone does not enable telemetry. Dedicated SQL writer credentials,
schema compatibility and the reviewed property catalog still apply; see
[DATABASE.md](DATABASE.md) and [CONFIG_CONTEXT.md](CONFIG_CONTEXT.md).
The production repository binding requires this directory. Explicitly injected
component-test repositories may omit it; the durable runtime tests provide real
protected directories and exercise the actual journal implementation.

The directory and files are owner-only; leaf symlinks, hard links, unexpected
file permissions and a competing owner are refused. The worker rechecks directory
permissions, the ownership inode and existing ledger protection before mutation.
Descriptors close across exec. The journal contains numeric producer/scope IDs,
timestamps, record-family masks and bounded health counters. It contains no
character/account names, credentials, SQL text, commands or record payloads.

## Interpreting observations

| Phase | Evidence and limits |
| --- | --- |
| `running` | A durable registration or periodic sample. After an unfinished lifetime, the next producer converts this to `unknown_tail` while retaining the original observation time and counters. |
| `clean_drained` | All admitted records were acknowledged, no invalid/conflicting/quarantined record remains, and the queue/inflight batch is empty. This does **not** erase admission rejections, session gaps or earlier outage counters. |
| `abandoned` | The worker terminated with a known count of unattempted queued records and no unresolved inflight batch. Preserve that count and the final sampled boundary. |
| `unknown_tail` | An unfinished lifetime, unresolved inflight commit, or a non-durable tail. The last sample is a watermark, not an exact crash/end time. Do not infer later admissions, an exact loss count, or an inclusive missing sequence span. |

Admission rejection counters count failed admissions; a value may have been
retried. They are not a count of distinct permanently lost gameplay facts.
Counters saturate, so an extreme saturated value is a lower bound. Record sequence
numbers may have gaps from failed allocation/admission and do not measure duration.
Inflight outcomes remain unresolved even when a commit acknowledgement was lost.
No trustworthy final clock/sample leaves a running watermark instead of inventing
a terminal boundary. UTC unknown is exported as `null`.

## Bounded publication and recovery

Both wire versions store at most 256 producer lifetimes. Version 1 has a
64-byte frame overhead and 320 bytes per producer, capped at 81,984 bytes.
Version 2 adds 80 bytes for quota binding, daily limits, UTC-day high-water and
reservation counters, capped at 82,064 bytes; it may hold quota with no producers.
The observation encoding is unchanged. Version 1 remains in use when quota is
absent; initializing quota upgrades the live frame to version 2.

`outages.owner` is the stable exclusive lock file: empty for version 1, or a
48-byte generation/SHA-256 witness for quota-enabled storage. Each publication writes an
owner-only `outages.pending` file, synchronizes it, renames it to `outages.ledger`,
and synchronizes the directory. A SHA-256 checksum detects damaged frames;
protected storage provides access control, not the checksum. Quota publication
synchronizes the owner witness before renaming the frame. Restoring only the
ledger, including a same-generation replacement, fails the witness check. Never
edit, truncate or replace the owner file to bypass this refusal.

A whole pending publication is recovered only when its generation extends
the existing chain, preserves producer identities/scopes, advances cumulative
watermarks, and retains terminal history. Registration may only append an empty
new producer and convert the prior running phase to unknown without extending its
time. Quota must retain its binding and advance its day/counters monotonically;
an explicit season rollover may change only the season while exhausting the new
day's allowance. A quota rotation may replace the full terminal table with one
empty registration only after verifying its matching archive. Recovery
synchronizes the pending file before publication and is idempotent.
A whole pending frame that decodes but does not extend the chain is kept and
refuses capture. A pending file that is not a whole frame (empty, short, or with
a digest that does not match) is what a crash, a power cut or a full disk leaves
between the create and the rename; it never became the ledger and holds nothing
the ledger lacks, so an open removes it and the ledger stands. Until the rename
the pending file is the writer's own staging copy: a write, fsync or close that
fails removes it and a later sample can retry. A failure at witness publication
or rename can leave a whole pending frame. Any failed quota publication disables
reservations for that owner until a fresh open validates the on-disk chain; no
failed or ambiguous attempt authorizes HTTP or receives a refund.

A sample that cannot be written costs evidence, not records: the records are
durable in SQL whatever the ledger says, capture goes on, and the ledger's last
good sample stays a running watermark (an unknown tail after the next
registration). A registration that cannot be written refuses capture, as do a
missing, unsafe or conflicting directory and a ledger that does not decode: the
telemetry circuit opens payload-free with `storage_check` naming the check
(`directory`, `protection`, `owner`, `ledger`, `io`) and `error` the errno, and
normal gameplay startup remains available. The worker never deletes a ledger or
reconstructs missing facts.

During normal publication, ledger plus pending occupy at most 163,968 bytes for
version 1 or 164,128 bytes for version 2, plus metadata and the 0/48-byte owner.
Archives and recovery evidence require additional retained space.

At 256 lifetimes, version 1 publishes the terminal frame once more (an unfinished
lifetime becomes unknown), renames it to
`outages.ledger.<incoming registered utc usec>.<generation>`, and resets generation
for a new chain containing only the incoming producer.
Version 2 publishes the terminal frame only when it must close a running phase,
then copies it to `outages.ledger.<outgoing registered utc usec>.<generation>`.
An unknown registration UTC uses registered monotonic time in either name.
Quota and generation continue; the full live frame remains until the incoming
registration commits. Fresh registration retries reuse that same terminal archive
instead of advancing an unchanged frame or creating duplicate archives. An
existing archive must match the terminal generation/digest; conflicts refuse
rotation. The worker reads that archive to validate rotation/recovery, but never
removes archives. Retain all evidence with the directory.
Never remove or replace `outages.owner` while a worker is active.

## Quota setup, restore and season rollover

Build the one-shot command with `make -C src telemetry-state`; it is written to
`bin/tools/telemetry-state` (or the chosen `BIN_ROOT`). Stop the telemetry worker
before running it. All commands use the existing protected directory and lock:

```text
telemetry-state initialize DIRECTORY PROJECT SENDER ENVIRONMENT SEASON TOTAL NORMAL HEALTH
telemetry-state exhaust-day DIRECTORY PROJECT SENDER ENVIRONMENT SEASON TOTAL NORMAL HEALTH
telemetry-state rollover-season DIRECTORY PROJECT SENDER ENVIRONMENT NEW_SEASON TOTAL NORMAL HEALTH
```

Initialize once before enabling delivery. Startup never grants fresh allowance.
The binding includes project, sender, environment, season and all three limits;
mismatches refuse reservations and worker registration in a different scope.
Each HTTP attempt, including a retry, must reserve durably first. UTC clock
rollback, exhausted quota, missing initialization and publication failure refuse
export. Normal/health limits share the combined cap, at most 20,000/day and at
most 100 health attempts. Use only the sender allocation assigned in
[CONTRACT.md](CONTRACT.md#durable-sender-quota-59).

After restoring a complete backup, run `exhaust-day` with its original binding.
A complete rollback of both ledger and witness cannot detect itself. This command
preserves the original frame as `outages.ledger.recovery.<generation>` and consumes
today's remaining allowance without sending. Preserve corrupt/mismatched evidence
and restore a consistent backup before recovery; do not reinitialize a directory
to bypass quota.

For a documented world reset, run `rollover-season` with the new season before
restarting with the new `TELEMETRY_SEASON_ID`. It uses the same recovery archive,
keeps historical observations/scopes and generation, updates only the quota
season binding, and exhausts today's allowance. Project, sender, environment and
limits must stay unchanged. No same-day reservations are allowed; the next UTC
day restores the normal allocation. Both commands refuse clock rollback and use
the journal's validated pending-frame recovery after interruption. Independent
directories or a season change never grant another project allocation.

## Offline evidence export

Stop the telemetry worker before using the POSIX offline reader:

```sh
python3 scripts/telemetry/outage.py /your/private/local/runtime/telemetry-outages
python3 scripts/telemetry/outage.py /your/private/local/runtime/telemetry-outages --ledger outages.ledger.<utc>.<generation>
```

The reader takes the same exclusive ownership lock, validates the bounded frame
and protection, and writes sanitized JSON to standard output; `--ledger` reads an
archive the writer kept instead of the live ledger. It creates no files and
performs no repair. Exit 2 reports refused input/storage with a stable reason
and, for I/O errors, a numeric code. `pending_publication` (a whole pending frame
beside the live ledger) requires the worker's validated recovery path or evidence
review; the reader will not delete/repair it.
Both unknown-tail end fields are `null`. The separate last-observed timestamps,
queue decomposition and acknowledged/rejected counters retain their actual
meaning. Store exported packets privately, not in the repository.

The reader does not supply gaps to balance reports. Its evidence can establish a
sampled outage watermark, not the existence, duration or balance of a battle that
was never recorded.

## Reproducible local qualification

From a Linux checkout, WSL or a disposable local container with the normal C++20
and OpenSSL development dependencies:

```sh
python3 tests/async/test_telemetry_outage.py
python3 tests/async/test_telemetry_runtime_outage.py
```

The native journal tests use synthetic protected temporary directories and cover
clean/abandoned observations, monotonic watermarks and immutable scopes, producer
reuse, simultaneous process ownership, unsafe/symlink/hard-link storage,
checksum/semantic/truncation/size corruption, ENOSPC write and fsync faults with
the retry in place, an interrupted rename, an empty, short or torn pending file
removed at open, idempotent recovery, real SIGKILL, real exec, historical-chain
refusal, storage changes and the archive at 256 lifetimes. The offline reader
consumes a real native frame and is checked for unchanged bytes, null unknown
ends, active-owner refusal, retained whole pending evidence and an archive read
under its own name. Quota cases also cover v2 sizing/witnesses, daily caps and
retry charging, rollback refusal, native initialization/recovery/season commands,
every rollover publication fault, historical scope retention and next-day
allowance, and repeated failed fresh registrations retaining one full archive.

The runtime journey runs SQL-header and client-free variants with bounded
synthetic repository faults. It verifies registration before SQL initialization
and admission, clean drain/restart, transient SQL recovery, unresolved commit
shutdown, a disk-full registration (refused, no staging file left), a disk-full
sample (capture goes on, sampling resumes), a transient qualification failure
retried past the old budget, and worker-only I/O. Existing transport stress
verifies coherent queue/counter samples while gameplay admission is active.
These tests require no production, staging or personal database credentials.
