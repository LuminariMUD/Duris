# Production host follow-ups, 2026-10-09

Work left for the owner of the shared Plesk host that runs production (staging until
2026-10-10; its service account is still named `staging`). It comes from the
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
| 3 | The MUD's backups have no off-host copy or restore drill, and their alert can't send mail | Medium | Open, owner |
| 4 | Loose ends from root's log sweep | Low | Open, optional |
| 5 | The service account is still named `staging` | Low | Open, root (owner chose to rename it) |

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

### 3. The MUD's backups have no off-host copy or restore drill, and their alert can't send mail

Since 2026-10-10 the service account takes verified hourly backups under the policy and timers
that `docs/operations/PRODUCTION_DEPLOYMENT.md` lists, kept on the same disk as the database.
A failed backup or health run starts `duris-backup-alert@.service`, which mails the operator
through `/usr/sbin/sendmail` at most once an hour per unit. Plesk refuses it: "Mail handler
'limit-out' said: The user staging is not allowed to send email." The owner left the off-host
copy for later. It needs an SSHFS mount (`replica_root`), and a restore drill needs a dedicated
restore filesystem (`drill_seconds`, `restore_root`).

**Next** (owner). In Plesk's outgoing mail control, let the service account send mail, then run
the deliberate-failure test in `BACKUPS.md` and check that the mail arrives. Provide the mount
and the filesystem when wanted, then set those policy fields.

### 4. Loose ends from root's log sweep

Root read the logs the service account can't read and found nothing the MUD needs to act on.
These are left, all optional:

- **Other MUDs crash.** Since 10-04 the kernel log shows 8 segfaults of aod's `circle` (all at
  address `0x28`, one instruction, so one bug) and 7 of frmud's (at address 0). Their
  `checkmud` crons restart them. If their owners want it, pass this on.
- **luminari-sage pins.** Its `requirements.txt` pins early-2024 versions that don't build on
  the host's Python 3.14. Root built the host venv from `requirements-core.txt` instead. The
  Docker image (`python:3.11-slim`) is unaffected.

### 5. The service account is still named `staging`

Everything else on the host says production. The account keeps the name, and its home
`/home/staging` is written out in its configuration. Root agreed to rename it.

**Next** (root). Keep the uid (10014): file ownership and the AppArmor allowance follow it.
1. As `staging`, rename the MariaDB admin login first, since `unix_socket` maps the Linux name:
   `RENAME USER 'staging'@'localhost' TO '<new>'@'localhost';`. Then pause the website watchdog
   and stop every `duris-*` and `durisweb-*` user unit and timer.
2. `loginctl disable-linger staging`, `usermod -l <new> -d /home/<new> -m staging`,
   `groupmod -n <new> staging`.
3. Replace `/home/staging` in `~/duris/.env`, `~/.config/duris-backup/policy.json` (and its
   `custodian`), `~/.config/duris-mariadb/my.cnf`, `~/.config/duris-redis/redis.conf`,
   `~/.config/durisweb/redis.conf`, `~/.config/letsencrypt/renewal/mud.duris.sbs.conf`, the two
   ACME hooks in `~/.local/libexec/`, and DurisWeb's `backend/.env` (with `MUD_PROCESS_USER`),
   `frontend/.env` and `deploy/deployment.env`; then re-render the website units from
   `deployment.env`. Re-create the absolute symlinks `~/duris/duris.crt`, `~/duris/duris.key`
   and the five `durisweb-*` links in `~/.config/systemd/user`.
4. Update the paths in `/etc/apparmor.d/local/mariadbd` and reload the `mariadbd` profile, and
   the account's name in the `Match User` line of `/etc/ssh/sshd_config.d/40-hardening.conf`
   (`sshd -t`, then reload ssh).
5. `loginctl enable-linger <new>`; as `<new>`, `systemctl --user daemon-reload`, start the units,
   resume the watchdog, and run the verification commands in `PRODUCTION_DEPLOYMENT.md`.
