# Base-stat persistence and ended-session recovery

Base stats use signed shorts at runtime. The former signed TINYINT database
columns could reject values accepted by staff commands, rolling back the entire
save transaction. Migration `0042_player_base_stats` widens all ten columns to
signed SMALLINT. Bootstrap, the immutable manifest, runtime contract, and measured
MySQL/MariaDB metadata fingerprints advance together.

The migration changes only TINYINT columns, preserves defaults and nullability,
and can be replayed. Unexpected wider columns are not narrowed; the verifier
rejects noncanonical definitions rather than silently changing their data.

The synthetic database regression uses disposable socket-only servers and invented
characters. It checks fresh and legacy schemas, replay, retained rows, partial
upgrades, and repository writes of values above the old limit plus both signed-short
limits across all ten stats. It never reads `.env` or connects to a running game.

Run `python3 tests/async/test_player_base_stats_mysql.py` for MariaDB, or add
`--mysql-basedir <native-mysql8>` for MySQL 8. Runtime and ledger checks are
`python3 tests/async/test_runtime_boot_compatibility.py`,
`python3 tests/async/test_immutable_migration_runner.py`, and
`python3 scripts/validate_runtime_compatibility.py`.

The review stack separates four dependent changes: #111 widens stat storage;
#112 validates `setbit` short input; #113 fixes `setattr` writes; #114 restores
login after failed ended-session saves and improves persistence diagnostics.
A queued revision is not a committed revision. Recovery must retain live dirty
state and outstanding writes while allowing a departed character to load the
last committed state after its final failed write has completed.

Production migration, deployment, character repair, and retention of failed
snapshots are outside this review's scope. No production incident records or
private-log links are needed to reproduce the defects.
