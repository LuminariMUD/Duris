# Production deployment tracker

Last verified: 2026-10-10 14:12 UTC (production service names adopted, MUD backups scheduled)

## Objective

Run DurisMUD and the DurisWeb website as persistent production services for
`duris.sbs`. Services must recover from any exit on their own, and an
off-host check must alert when they do not.

This file intentionally records no passwords, API tokens, tunnel tokens, or
private keys. Those remain in owner-controlled ignored files. The earlier
`duris.sbs` deployment is not tracked here; its setup record is in this file's
Git history.

**This server, the shared Plesk host recorded in the operator's `.env`
(`STAGING_*` block), and the domain `duris.sbs` are the ONLY location of the
MUD and of the DurisWeb website. The website's public ingress is the Cloudflare tunnel
`durisweb-production`; Cloudflare is required, not optional. The earlier
dedicated-host deployment recorded in this file's history and its website
tunnel are retired and must not be treated as a fallback.**


## Production topology

| Component | Endpoint or location | Notes |
| --- | --- | --- |
| Host | Shared Plesk host; name, address and account in the operator's `.env` (`STAGING_*` block) | Everything below runs as one unprivileged account under user-scope systemd with lingering enabled |
| MUD checkout | `~/duris` | Deployed from `master` |
| MUD service | `duris-mud-production.service` | User unit running `scripts/cycle_mud.sh --production` |
| Database | `duris-mariadb.service`, `127.0.0.1:3307`, schema `duris_prod`, account `duris_prod` | MariaDB; `PERSISTENCE_MODE=mariadb-primary`; shared with the website |
| MUD Redis | `duris-redis.service`, `127.0.0.1:6381` | Namespace `duris:production:main`; ACL identities in `~/.config/duris-redis/users.acl` |
| Plain telnet | `mud.duris.sbs:7777` | DNS-only A record to the host |
| TLS telnet | `mud.duris.sbs:7778` | Let's Encrypt via the Cloudflare DNS-01 hooks in `~/.local/libexec/`, renewed by `duris-certbot-renew.timer` |
| MUD WebSocket/health origin | `127.0.0.1:4050` | Loopback-only. The MUD's `.env` must set `DURIS_WEBSOCKET=TRUE`: the listener is off by default, and the website and both health checks need it |
| Public MUD WebSocket/health | `wss://ws.duris.sbs`, `https://ws.duris.sbs/health` | `ws.duris.sbs` is a proxied CNAME to the website tunnel, whose ingress routes it to the loopback origin. `mud.duris.sbs` stays DNS-only for telnet, and its port 443 is Plesk's Nginx. The browser client connects through the website at `wss://www.duris.sbs/ws` |
| Website checkout | `~/durisweb` | The DurisWeb repository, deployed from `master` |
| Website application | `durisweb-production.service`, `127.0.0.1:7770` | Private cache `durisweb-redis.service` on `127.0.0.1:6380`; port 3001 belongs to another account on this host |
| Website tunnel | `durisweb-cloudflared.service`, tunnel `durisweb-production` | REQUIRED. `duris.sbs` and `www.duris.sbs` are proxied CNAMEs to this tunnel, and its ingress routes both directly to the application, and `ws.duris.sbs` to the MUD origin; no Nginx is in the website path |
| Tunnel readiness | `http://127.0.0.1:20243/ready` | Loopback-only |
| Watchdog | `durisweb-watchdog.timer` | User timer running the checkout's `deploy/scripts/durisweb-watchdog` every minute |

API work for them uses the credentials in
`~/durisweb/deploy/deployment.env` (mode 0600, gitignored), not a
workstation `.env`.

## Availability safeguards

The safeguards below were established on the retired host. On this host every
unit is a user unit of the service account, so the `sudo`, root-owned copy,
and `/etc/systemd/system` paths in this section and the next do not apply;
use `systemctl --user` and the pause file under `~/.local/state/durisweb-watchdog`.

On 2026-09-10 the website tunnel exited cleanly after losing every edge
connection. Its unit restarted only on failure, so `duris.sbs` served
Cloudflare error 1033 until the connector was started by hand on 2026-09-14.
Later that day, a maintenance stop and start of the website application stopped
the tunnel again, because the tunnel was bound to the application, and the site
was down for another 40 minutes.

- The website application, cache, and tunnel restart after any exit other than
  configuration refusal, with no start rate limit, and the tunnel is no longer
  bound to the application. DurisWeb `docs/deployment.md` ("Keep the site
  available") describes the policy.
- `durisweb-watchdog.timer` starts any stopped website unit or Nginx. It
  restarts the tunnel after three failed readiness or public-health checks and
  the application after three failed local-health checks, at most once per unit
  every ten minutes.
- `nginx`, `mysql`, and `redis-server` have
  `/etc/systemd/system/<unit>.service.d/10-availability.conf` overrides that set
  `Restart=always`, `RestartSec=5s`, and `StartLimitIntervalSec=0`.
- `duris-mud-production.service` uses `Restart=always` with no start rate limit
  (`deploy/systemd/duris-mud-production.service.in`).
- The `production uptime` workflow probes `https://duris.sbs/health` and
  `https://ws.duris.sbs/health` every ten minutes from GitHub-hosted runners.
  A failed run notifies through GitHub.
- A Cloudflare Tunnel Health Alert emails the Cloudflare account owner when the
  website tunnel goes down.

Fault tests on 2026-09-14 at 23:10 UTC confirmed the behavior. Stopping and
starting only the application left the tunnel running, with 2 seconds of
gateway errors. A clean tunnel exit restarted by itself within 6 seconds. An
explicitly stopped tunnel was started by a watchdog run.

## Planned maintenance

Pause the watchdog before deliberately stopping a website unit or the tunnel.
The watchdog ignores a pause older than four hours. All website units are
user units of the service account.

```bash
mkdir -p ~/.local/state/durisweb-watchdog && touch ~/.local/state/durisweb-watchdog/pause
# Maintenance...
systemctl --user start durisweb-redis durisweb-production durisweb-cloudflared
rm ~/.local/state/durisweb-watchdog/pause
```

Stopping only the MUD does not require a pause. Before ending maintenance, run
the public health checks below.

## Service and configuration locations

- Website deployment input: `~/durisweb/deploy/deployment.env`
  (mode `0600`, gitignored)
- Rendered website units: `~/.local/share/durisweb/rendered`,
  linked into the service account's user manager
- Website application drop-in (user-scope process-monitor fix):
  `~/.config/systemd/user/durisweb-production.service.d/10-user-scope-process-monitor.conf`
- Watchdog executable: the website checkout's `deploy/scripts/durisweb-watchdog`
  (user scope; no root-owned copy)
- Watchdog drop-in (stops AppArmor user-namespace denials):
  `~/.config/systemd/user/durisweb-watchdog.service.d/10-user-scope-no-namespaces.conf`
- Watchdog state and pause file: `~/.local/state/durisweb-watchdog`
- MUD service unit: `~/.config/systemd/user/duris-mud-production.service`
- MUD secrets and connection values: `~/duris/.env` (mode `0600`)
- MUD TLS certificate: `~/duris/duris.crt` and `duris.key`, symlinks
  into `~/.config/letsencrypt/live/mud.duris.sbs/`
- Cloudflare DNS token used by certificate renewal and by the website tunnel
  launcher: `~/.config/duris-certbot/cloudflare.env` (mode `0600`)
- MUD persistence backups: policy `~/.config/duris-backup/policy.json` (named by
  `BACKUP_POLICY_FILE` in `.env`), generations in `~/backups/duris/generations`.
  `duris-backup-backup.timer` takes one an hour and `duris-backup-health.timer` checks
  them every minute. Both units are in `~/.config/systemd/user`, adapted from
  `deploy/systemd/duris-backup-*` without the sandboxing options a user unit can't use.
  Both route failures through `duris-backup-alert@.service`. Its maintained
  `scripts/backup_alert.py` is installed as `~/.local/libexec/duris-backup-alert`
  and reads the existing protected MAIL_* settings. Direct SMTP delivery and
  recipient receipt were verified on 2026-10-16. Off-host replica and restore
  qualification remain separate; see the [host follow-ups](#host-follow-ups).
- The website's own hourly dump of the shared database: `~/durisweb-backups`
- One-off copies (pre-change dumps, configuration): `~/backups/duris/<date>-*`
- Host AppArmor allowance for the MUD database: `/etc/apparmor.d/local/mariadbd`
  (root-owned). Ubuntu 26.04 enforces the `mariadbd` profile on `duris-mariadb.service`
  too. Without this file, MariaDB can't read `~/.config/duris-mariadb/my.cnf` or
  `~/.local/state/duris-mariadb/`, or tell systemd it is ready. If those paths or the
  account's uid change, root must update it.

## Host follow-ups

These items preserve the 2026-10-10 14:20 UTC observations recorded in commit
`023179af6` before the separate host follow-up note was retired.
They were reconciled on 2026-10-14; the alert status below was subsequently
verified on 2026-10-16. Other historical follow-ups retain their stated limits.

### Backup alerts and restore qualification

A failed backup or health run starts `duris-backup-alert@.service`. Its existing
helper path now contains the maintained [backup notifier](../../scripts/backup_alert.py),
with `--recipient` and `--env-file` supplied by the user-unit template. It reads
MAIL_HOST/PORT/TLS/USERNAME/PASSWORD/FROM from `~/duris/.env`, uses the configured
SMTP account and verified sender directly, and retains one successful submission
per unit per hour. MAIL_ENABLED still controls game account recovery only.

The historical sendmail path was blocked first by Plesk and then by the shared
relay's unverified sender. The corrected notifier was verified through a harmless
transient-unit OnFailure test on 2026-10-16: the recipient server accepted delivery,
the owner confirmed receipt, and a repeated failure sent no second message. The
test unit/stamp were cleaned up. The temporary Plesk exception was removed; this
notifier does not require a service-account exception or changes to the shared
relay. Do not reinstate that obsolete workaround when diagnosing future alerts.
Use [Backup operations](BACKUPS.md) and the
[issue #106 evidence](../ongoing-projects/plan-issue-106.md) for current checks.
The later PR #126 authentication, checkout-path, and journal corrections have local
regression coverage only; they were not installed or sent through the live relay
as part of that follow-up review.

At the historical check there was no off-host replica or restore drill; the owner had deferred
the off-host copy. Providing an SSHFS mount for `replica_root` and a dedicated restore
filesystem for `restore_root`, then setting `drill_seconds`, remains separate work.
Follow [separate/off-host storage](BACKUPS.md#separateoff-host-storage) and the restore
qualification procedure in that runbook.

### Planned service-account rename

At the same check, production service names had changed but the Linux account still
used its staging name. A root-led account rename was planned. Confirm the current
account, UID and paths from the operator's private configuration before scheduling
an authorized maintenance window. Preserve the existing UID so ownership and the
AppArmor allowance continue to identify the same account.

1. While logged in as the old service account, rename its MariaDB administrative
   login first: `unix_socket` authentication maps the Linux login name. Pause the
   website watchdog and stop every `duris-*` and `durisweb-*` user unit and timer.
2. As root, disable lingering and stop the old account's user manager and sessions.
   Rename the Linux login, primary group and home directory, retaining the UID.
3. Replace the old home path in `~/duris/.env`, `~/.config/duris-backup/policy.json`
   (including its `custodian`), `~/.config/duris-mariadb/my.cnf`,
   `~/.config/duris-redis/redis.conf`, `~/.config/durisweb/redis.conf`,
   `~/.config/letsencrypt/renewal/mud.duris.sbs.conf`, and both ACME hooks under
   `~/.local/libexec/`. Update DurisWeb's `backend/.env` (including `MUD_PROCESS_USER`),
   `frontend/.env` and `deploy/deployment.env`; re-render its units from that deployment
   input. Re-create the absolute `~/duris/duris.crt` and `duris.key` symlinks and the
   five `durisweb-*` unit links under `~/.config/systemd/user`.
4. Update the paths in `/etc/apparmor.d/local/mariadbd` and reload the MariaDB profile.
   Update the account in the `Match User` rule under
   `/etc/ssh/sshd_config.d/40-hardening.conf`; validate with `sshd -t` before reloading SSH.
5. Enable lingering for the renamed account. As that account, reload the user manager,
   start the services and timers, resume the watchdog, and run the
   [verification commands](#verification-commands) below.

## Verification commands

Run these on the host without printing `.env`:

```bash
systemctl --user is-active duris-mariadb duris-redis duris-mud-production \
  durisweb-redis durisweb-production durisweb-cloudflared durisweb-watchdog.timer \
  duris-backup-backup.timer duris-backup-health.timer
(cd ~/duris && scripts/backup_pfiles.sh status --require-drill)
systemctl --user list-timers durisweb-watchdog.timer
journalctl --user-unit durisweb-watchdog.service --since -1h
curl --fail --silent --show-error http://127.0.0.1:20243/ready
curl --fail --silent --show-error https://duris.sbs/health
curl --fail --silent --show-error https://ws.duris.sbs/health

openssl s_client \
  -connect mud.duris.sbs:7778 \
  -servername mud.duris.sbs \
  -verify_hostname mud.duris.sbs \
  -verify_return_error </dev/null
```

The website health response must report `"status":"ok"` and
`"service":"durisweb-backend"` with `ok` database and cache checks. The MUD
health response must be `{"status":"healthy","persistence":"ready"}`.

## Security invariants

- MySQL, both Redis instances, the website application, the MUD WebSocket
  origin, and tunnel metrics listen only on loopback.
- Credentials remain only in the mode-`0600` environment files above; this
  document and tracked files contain no secret values.
- The root-run watchdog executes a root-owned copy, never a script in a checkout
  the service account can modify.
- The MUD WebSocket origin allow-list is restricted to `https://duris.sbs`
  and `https://www.duris.sbs`.
