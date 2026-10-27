# Daily account login statistics

Staff can inspect individual login events in game with the Avatar-level `last`
command. `last` searches all retained history; `last 24h`, `last Veridian 7d`,
and `last unique 7d` filter by elapsed time, current character name, or latest
login per account. Add `page 2` (and subsequent page numbers) to read all matches
in batches of 20. The output includes UTC timestamps, current character names,
account snapshots, and player IDs. New logins can shift these live pages.

The command reads `session_audit_outcome` through the existing asynchronous SQL
reader, including staff logins. It selects login events only, with deterministic
ordering by event time and operation ID; unique-account selection uses that same
ordering within the requested window. Accounts come from the event snapshot,
never from current character ownership. Missing character rows retain their PID
and display `(deleted)`. Unknown account snapshots display `(unknown)` and are
omitted from the unique-account view. Character lookup uses the existing name
index, so renamed characters must be requested under their current name. Account
menu authentication and reconnect notices are not character-entry events.

No schema change or new log is needed. Flat-file builds report that this command
requires MariaDB. Publish the `LAST` topic from `lib/information/help_index` through
the normal help import when deploying the command.

Focused verification: `python3 tests/async/test_last_command.py`, and
`tests/async/with_disposable_mariadb.sh python3 tests/async/test_last_command.py --mysql`.
The latter executes the production command's queries on isolated tables, including
repeated logins, time boundaries, ties, account transfers, and multiple pages.
`tests/async/with_disposable_mariadb.sh python3 tests/async/run_last_command_journey.py`
boots an isolated game to verify real staff dispatch, mortal denial, offline lookup,
persisted logins, filters, paging, and the imported help topic.

`scripts/login_stats_export.py` publishes `latest.json` for yesterday and
`history.json` for up to 90 completed calendar days. Both files are replaced
atomically. Days follow `--timezone` (UTC by default); today is excluded.

The game captures the lowercase account name and whether the character is staff
(level 57 or above) in the login command before queueing it. The audit outcome
retains that snapshot. Alts count once per day, and later promotion, account
transfer or character deletion cannot change previous counts. Staff logins do
not count. No account identities appear in the exported JSON.

Apply migration `0037_session_audit_identity` before starting the new server.
Old rows and version-1 journal commands retain NULL snapshot fields: current
player state cannot reconstruct historical identity. The exporter starts with
the first snapshotted login's day, omits older days, and reports excluded
unknown snapshots on stderr. The rollout day can therefore be partial. Do not
backfill these fields from `player_data`. The old binary can still insert rows
with NULL fields, but those logins will not contribute to statistics.

## Install on the documented user-service host

The checked-in units use `~/duris`, the user service `duris-mariadb.service`,
loopback port 3307, and `~/durisweb/backend/public/stats`. DurisWeb's
`backend/src/index.ts` serves `process.cwd()/public`, and its application unit
runs in `backend`, making these files available at `/stats/latest.json` and
`/stats/history.json`. DurisWeb currently gives this static directory a seven-day
cache lifetime: consumers should use a date/version query parameter or request
cache revalidation when fetching nightly updates.

Create `~/.config/duris/login-stats.env` with mode 0600. Set
`LOGIN_STATS_DB_DATABASE`, `LOGIN_STATS_DB_USER` and `LOGIN_STATS_DB_PASSWORD`.
The unit supplies `LOGIN_STATS_DB_HOST=127.0.0.1` and
`LOGIN_STATS_DB_PORT=3307`; the environment file may override them. The exporter
needs the `mysql` client, Python 3 and IANA timezone data. Use a dedicated account
with only `SELECT` on `session_audit_outcome`; no access to `player_data` is needed:

```sql
CREATE USER 'duris_stats'@'127.0.0.1' IDENTIFIED BY '<password from login-stats.env>';
GRANT SELECT ON duris_prod.session_audit_outcome TO 'duris_stats'@'127.0.0.1';
```

Use the same password in `LOGIN_STATS_DB_PASSWORD`. The account host must match
the connection: `127.0.0.1` for the unit's loopback TCP connection, or `localhost`
if overriding `LOGIN_STATS_DB_HOST` to use a Unix socket. A `localhost` grant does
not authorize loopback TCP on MariaDB/Linux.

After the migration and updated MUD are installed, run as the service account:

```sh
mkdir -p ~/.config/systemd/user
cp ~/duris/deploy/systemd/duris-login-stats.{service,timer} ~/.config/systemd/user/
systemd-analyze --user verify ~/.config/systemd/user/duris-login-stats.{service,timer}
systemctl --user daemon-reload
systemctl --user start duris-login-stats.service
systemctl --user enable --now duris-login-stats.timer
journalctl --user-unit duris-login-stats.service --since today
```

The exporter creates missing output directories on its first successful query.
These are user units without mount namespace options, as required on the shared
host. `Wants=` and `After=` start and order the database first. A failed query or
other failure retries after five minutes, including persistent timer catch-up
at boot. Each successful run rebuilds the window. If changing the day timezone,
change both `--timezone` in the service and `OnCalendar=` in the timer.

## Local verification

```sh
python3 tests/async/test_login_stats_export.py
python3 tests/async/test_session_audit_snapshot.py
tests/async/run_session_audit_schema_mysql.sh
python3 tests/async/run_login_stats_service.py
```

The SQL leg uses a disposable database, exercises typed writes and legacy replay,
and runs the exporter with SELECT-only grants before and after promotion,
transfer and deletion. It is included in `make test-db`. The service journey
needs a working user systemd manager; it links uniquely named temporary units,
uses a fake database/client, forces the first query to fail, checks retry and
first-run directory creation, and removes its units afterward. It never loads
real credentials or changes the deployed services.
