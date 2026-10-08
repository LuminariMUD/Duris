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

Wire version 1 stores at most 256 producer lifetimes in an 81,984-byte ledger.
`outages.owner` is the stable exclusive lock file. Each publication writes an
owner-only `outages.pending` file, synchronizes it, renames it to `outages.ledger`,
and synchronizes the directory. A SHA-256 checksum detects damaged frames;
protected storage provides access control, not the checksum.

A whole pending publication is recovered only when its generation extends
the existing chain, preserves producer identities/scopes, advances cumulative
watermarks, and retains terminal history. Registration may only append an empty
new producer and convert the prior running phase to unknown without extending its
time. Recovery synchronizes the pending file before publication and is idempotent.
A whole pending frame that decodes but does not extend the chain is kept and
refuses capture. A pending file that is not a whole frame (empty, short, or with
a digest that does not match) is what a crash, a power cut or a full disk leaves
between the create and the rename; it never became the ledger and holds nothing
the ledger lacks, so an open removes it and the ledger stands. Until the rename
the pending file is the writer's own staging copy: a write, fsync or close that
fails removes it and the next sample writes again. Only a rename that fails
leaves a whole frame behind and poisons the in-memory writer until a fresh open
validates the on-disk chain.

A sample that cannot be written costs evidence, not records: the records are
durable in SQL whatever the ledger says, capture goes on, and the ledger's last
good sample stays a running watermark (an unknown tail after the next
registration). A registration that cannot be written refuses capture, as do a
missing, unsafe or conflicting directory and a ledger that does not decode: the
telemetry circuit opens payload-free with `storage_check` naming the check
(`directory`, `protection`, `owner`, `ledger`, `io`) and `error` the errno, and
normal gameplay startup remains available. The worker never deletes a ledger or
reconstructs missing facts.

During normal publication the two frame files occupy at most 163,968 bytes,
plus filesystem metadata and the empty owner file. When the ledger already holds
256 lifetimes the next registration publishes it once more (the unfinished
lifetime closed as an unknown tail), keeps it as
`outages.ledger.<registered utc usec>.<generation>` and starts a new chain with
itself as the only entry; nothing is lost and no operator step is needed. Archive
files are never read or removed by the worker; retain them with the directory.
Never remove or replace `outages.owner` while a worker is active.

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
under its own name.

The runtime journey runs SQL-header and client-free variants with bounded
synthetic repository faults. It verifies registration before SQL initialization
and admission, clean drain/restart, transient SQL recovery, unresolved commit
shutdown, a disk-full registration (refused, no staging file left), a disk-full
sample (capture goes on, sampling resumes), a transient qualification failure
retried past the old budget, and worker-only I/O. Existing transport stress
verifies coherent queue/counter samples while gameplay admission is active.
These tests require no production, staging or personal database credentials.
