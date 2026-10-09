# Staging host follow-ups, 2026-10-09

Four findings of the 2026-10-09 log review that belong to the host's owner rather than the
MUD's code: SSH, backups, the logs only root can read, and the kernel. They are handled apart
from the review, whose other open findings are in [plan.md](plan.md); its own file was
deleted then, and its last version is at `24e7d3fba`. Checked on the shared Plesk host that
runs staging, as its service account, on 2026-10-09, last at 09:10 UTC. This file is a working
note: delete a finding when it is done, and the file when none is left.

## Summary

| # | Finding | Severity | State |
|---|---|---|---|
| 1 | SSH offers passwords, permits root, and nothing limits attempts | Medium | Open, owner |
| 2 | Nothing backs up the MUD's persistence on staging except DurisWeb's hourly dump | Low-medium | Open, decision, owner |
| 3 | Root-only logs are unread while they grow | Low | Open, owner |
| 4 | A new kernel is installed but not booted | Low | Open, owner |

## Findings

### 1. SSH accepts passwords, permits root, and nothing limits attempts

`/etc/ssh/sshd_config` L132 is `PermitRootLogin yes`. The readable drop-in
`60-cloudimg-settings.conf` says `PasswordAuthentication no`, but a probe of sshd, on
127.0.0.1 and on the public address, answers `Permission denied (publickey,password)`, so
passwords are offered. sshd takes the first value it reads, and `50-cloud-init.conf` (root-only,
27 bytes) is read before the 60 file; it is probably `PasswordAuthentication yes`. fail2ban is
not installed. ufw is off (`ENABLED=no`); the Plesk firewall is the active one, and its rules
could not be read. `auth.log` grows about 11 MB a day. Root can read it to tell brute force
from PAM and cron noise; `staging` cannot. `wtmp` shows 15 interactive sessions from 7
addresses in 14 days, and no root login since 2025-09. One session (`swrpg`, 2026-09-26) came
from a hosting-type range, and the owner should confirm it.

**Next** (owner, root). Read `50-cloud-init.conf`. Set `PasswordAuthentication no` and
`PermitRootLogin prohibit-password` (or `no`) where they take effect, and check them with
`sshd -T`. Add fail2ban or a Plesk equivalent. This host serves other tenants (krynn, swrpg,
aod), so agree the change with them.

### 2. Nothing backs up the MUD's persistence on staging except DurisWeb's dump

`.env` sets neither `BACKUP_POLICY_FILE` nor `PREBOOT_BACKUP`. The user manager has no backup
timer and `staging` has no crontab, so `scripts/persistence_backup.py` never runs here, and
`cycle_mud.sh` skips the pre-boot backup (L318-323). The one database copy is DurisWeb's hourly
dump in `/home/staging/durisweb-backups`: 20 of 20 succeeded from 2026-10-08 13:00 to
2026-10-09 08:00 (and the 09:00 one since), and the latest holds `database/duris_staging.sql`
(61 MB). That dump is not the verified, drilled backup `docs/operations/BACKUPS.md` describes,
and its restore has not been tried. `/home/staging/backups/duris/2026-10-07-prebuild` is a
one-off copy of a binary and the scheduler state.

**Next** (decision). Staging may not need more than this. If it does, install the policy and
the sample units in `deploy/systemd/duris-backup-*` as `BACKUPS.md` says, or set
`PREBOOT_BACKUP=1`.

### 3. Root-only logs are unread while they grow

`staging` is not in `adm` or `systemd-journal` and `sudo -n` needs a password, so these could
not be read: `syslog`, `kern.log`, `auth.log`, `mail.err`, `php8.3-fpm.log`, `cloud-init`,
`apt/term.log`, `btmp`, the system journal, `dmesg`, the Plesk and Apache logs, and
`/etc/ssh/sshd_config.d/50-cloud-init.conf`. Kernel segfault or OOM lines therefore cannot be
ruled out, though no unit shows an OOM event, the host's `oom_kill` count is 0 since boot, and
`/var/crash` is empty. Some of these logs are growing:

- `kern.log`: 12.8 KB from 2026-09-27 to 10-03, then 374 KB from 10-04 to 10-09 09:10.
- `mail.err`: 172 KB, last written 2026-10-08 05:48.
- `php8.3-fpm.log`: about 1.7 MB a week.
- `auth.log`: see finding 1.

`/var/log/sa-update.log` is readable. It is a 41 MB debug-level log (426,000 lines since
2026-07-31), it is not rotated, and SpamAssassin runs without Mail::SPF, Razor2 and
Mail::DMARC. That is Plesk mail, not the MUD.

**Next** (owner, root):

```bash
sudo grep -E 'segfault|traps:|oom-kill|I/O error|EXT4-fs error' /var/log/kern.log*
sudo tail -50 /var/log/mail.err
```

Also summarize failed SSH logins with `lastb` or `auth.log`.

### 4. A new kernel is installed but not booted

`linux-image-6.8.0-146` was installed by unattended-upgrades at 06:49 on 2026-10-09. The host
runs 6.8.0-142, has been up since 2026-09-25, and `/run/reboot-required` is not set, so
nothing flags it.

**Next.** The owner's call: a reboot restarts every tenant on the host.
