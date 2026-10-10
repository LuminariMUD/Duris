# Staging host follow-ups, 2026-10-09

Work left for the owner of the shared Plesk host that runs staging. It comes from the
2026-10-09 log review, whose other findings were fixed in #15 to #24 (its own file was
deleted then; its last version is at `24e7d3fba`), and from the root session that followed the
host's upgrade to Ubuntu 26.04.1 (rebooted 12:34 UTC). Root's notes were copied here with
host-security details left out: IP addresses, which accounts accept passwords, and where
credentials and backups are stored. Root can read those on the host with the commands below.
Last checked as the host's service account at 19:55 UTC. This file is a working note: delete
a finding when it is done, and the file when none is left.

## Summary

| # | Finding | Severity | State |
|---|---|---|---|
| 1 | SSH still accepts passwords for some tenant accounts | Medium | Open, owner and tenants |
| 2 | The old GitHub token from `wildeditor`'s `origin` URL may not be revoked | Medium | Open, owner (GitHub) |
| 3 | Nothing backs up the MUD's persistence on staging except DurisWeb's hourly dump | Low-medium | Open, decision |
| 4 | Loose ends from root's log sweep | Low | Open, optional |

## Findings

### 1. SSH still accepts passwords for some tenant accounts

Since 2026-10-04, `auth.log` shows 133,194 failed password attempts from 929 addresses. Root
logins are now key-only, and so are the owner's and the service accounts, staging's among
them. The setting is a `Match User` list in `/etc/ssh/sshd_config.d/40-hardening.conf`, which
sshd reads first. A probe from staging's service account at 18:35 confirms that it and `root`
are offered only `publickey`. Plesk's Fail2Ban runs the `ssh` and `recidive` jails. Tenant
accounts not on the list still accept passwords. The `swrpg` session of 2026-09-26, which came
from a hosting-type address range, has still not been confirmed by that tenant.

**Next** (owner, agree with the tenants). Find who still accepts passwords with
`sudo sshd -T -C user=<name>` and the `Match User` line. Install a key for each of them, then
add them to that line or make `PasswordAuthentication no` global in `40-hardening.conf`. Run
`sudo sshd -t` and `sudo systemctl reload ssh`. `last` and `lastb` are not installed on 26.04,
so read logins from `auth.log` or `wtmpdb`. Ask the `swrpg` tenant about the 2026-09-26
session.

### 2. The old GitHub token from `wildeditor`'s `origin` URL may not be revoked

The `wildeditor` checkout had a GitHub token in its `origin` URL. At 13:45 root changed the URL
to `https://github.com/LuminariMUD/wildeditor.git`, and fetches still work through its
account's credential helper. No other `.git/config` on the disk holds credentials.

**Next** (owner, on GitHub). Revoke the old token. Root can't do it from the host.

### 3. Nothing backs up the MUD's persistence on staging except DurisWeb's dump

`.env` sets neither `BACKUP_POLICY_FILE` nor `PREBOOT_BACKUP`. The user manager has no backup
timer and the service account has no crontab, so `scripts/persistence_backup.py` never runs
here, and `cycle_mud.sh` skips the pre-boot backup (L318-323). The one database copy is
DurisWeb's hourly dump in `~/durisweb-backups`. It keeps the last 24, from 2026-10-08 17:00 to
2026-10-09 18:00, missing only 12:00 and 13:00 on 10-09, when the upgrade had staging down.
The latest holds `database/duris_staging.sql` (61 MB). This dump is not the verified, drilled
backup that `docs/operations/BACKUPS.md` describes, and no one has tried restoring it.
`~/backups/duris/2026-10-07-prebuild` is a one-off copy of a binary and the scheduler state.

**Next** (decision). Staging may not need more than this. If it does, install the policy and
the sample units in `deploy/systemd/duris-backup-*` as `BACKUPS.md` says, or set
`PREBOOT_BACKUP=1`.

### 4. Loose ends from root's log sweep

Root read the logs the service account can't read and found nothing the MUD needs to act on.
These are left, all optional:

- **Other MUDs crash.** Since 10-04 the kernel log shows 8 segfaults of aod's `circle` (all at
  address `0x28`, one instruction, so one bug) and 7 of frmud's (at address 0). Their
  `checkmud` crons restart them. If their owners want it, pass this on.
- **luminari-sage pins.** Its `requirements.txt` pins early-2024 versions that don't build on
  the host's Python 3.14. Root built the host venv from `requirements-core.txt` instead. The
  Docker image (`python:3.11-slim`) is unaffected.
