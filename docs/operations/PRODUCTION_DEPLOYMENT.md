# Production deployment tracker

Last verified: 2026-10-08 12:08 UTC (website live on this host)

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
| Database | `duris-mariadb.service`, `127.0.0.1:3307`, schema `duris_staging` | MariaDB; `PERSISTENCE_MODE=mariadb-primary`; shared with the website |
| MUD Redis | `duris-redis.service`, `127.0.0.1:6381` | Namespace `duris:production:staging`; ACL identities in `~/.config/duris-redis/users.acl` |
| Plain telnet | `mud.duris.sbs:7777` | DNS-only A record to the host |
| TLS telnet | `mud.duris.sbs:7778` | Let's Encrypt via the Cloudflare DNS-01 hooks in `~/.local/libexec/`, renewed by `duris-certbot-renew.timer` |
| MUD WebSocket/health origin | `127.0.0.1:4050` | Loopback-only. The MUD's `.env` must set `DURIS_WEBSOCKET=TRUE`: the listener is off by default, and the website and both health checks need it |
| Public MUD WebSocket/health | `wss://mud.duris.sbs`, `https://mud.duris.sbs/health` | Needs a TLS proxy to the loopback origin on this host; not in place yet (Plesk owns the system Nginx). `ws.duris.sbs` still points at the retired MUD tunnel |
| Website checkout | `~/durisweb` | The DurisWeb repository, deployed from `master` |
| Website application | `durisweb-production.service`, `127.0.0.1:7770` | Private cache `durisweb-redis.service` on `127.0.0.1:6380`; port 3001 belongs to another account on this host |
| Website tunnel | `durisweb-cloudflared.service`, tunnel `durisweb-production` | REQUIRED. `duris.sbs` and `www.duris.sbs` are proxied CNAMEs to this tunnel, and its ingress routes both directly to the application; no Nginx is in the website path |
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
  `https://mud.duris.sbs/health` every ten minutes from GitHub-hosted runners.
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
- Backups: `~/backups/duris`
- Host AppArmor allowance for the MUD database: `/etc/apparmor.d/local/mariadbd`
  (root-owned). Ubuntu 26.04 enforces the `mariadbd` profile on `duris-mariadb.service`
  too. Without this file, MariaDB can't read `~/.config/duris-mariadb/my.cnf` or
  `~/.local/state/duris-mariadb/`, or tell systemd it is ready. If those paths or the
  account's uid change, root must update it.

## Verification commands

Run these on the host without printing `.env`:

```bash
systemctl --user is-active duris-mariadb duris-redis duris-mud-production \
  durisweb-redis durisweb-production durisweb-cloudflared durisweb-watchdog.timer
systemctl --user list-timers durisweb-watchdog.timer
journalctl --user-unit durisweb-watchdog.service --since -1h
curl --fail --silent --show-error http://127.0.0.1:20243/ready
curl --fail --silent --show-error https://duris.sbs/health
curl --fail --silent --show-error https://mud.duris.sbs/health

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
