# Security And Dependency Baseline

This baseline makes Duris security work reproducible without claiming that a completed
scan proves the repository or a deployment is vulnerability-free.

## Local Commands

```bash
make security-sbom
make security-check
```

Generated outputs are written under ignored `bin/security/`:

- `dependency-inventory.json` records every direct expression from
  `packaging/duris-build-deps.equivs`, the installed alternative with its version and
  source package when available, and unresolved expressions explicitly. A metapackage
  from a `*-defaults` source (the MySQL defaults, `python3`, `clang-format`) is recorded
  as the installed package it depends on: no advisory names the metapackage.
- `duris.spdx.json` is SPDX 2.3 for those resolved direct packages. Its timestamp comes
  from the source commit and its namespace from canonical inventory content, so the
  same commit and installed package set reproduce byte-identical output.
- `scanner-rootfs/` contains minimal OS identity and dpkg status records for only the
  resolved direct packages, each with its `Source:` line: Trivy matches Ubuntu
  advisories by source package (`curl`, not `libcurl4-gnutls-dev`). It exists because
  Trivy cannot infer Debian/Ubuntu package semantics from a direct-package-only SPDX
  document; the workflow rejects an unsupported or empty scan, or an unresolved
  dependency, instead of treating it as clean.

The inventory does not resolve transitive packages, deployment-only MySQL/Redis/host
services, containers, firmware, or external DurisWeb infrastructure. SPDX generation
does not perform a vulnerability scan.

A scan describes the machine it ran on. To scan a host, run there `make security-sbom`,
check that the inventory lists no `unresolved` entry, and run the workflow's Trivy step
with Trivy `v0.70.0`:

```bash
trivy rootfs --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 bin/security/scanner-rootfs
```

A deployment counts as scanned only from such a run on it, recorded with its date and
Trivy's database version.

## The Security Workflow

`.github/workflows/security.yml` (`security baseline`) runs on every push to `master` and
every pull request to it, on GitHub. Verification here is local and does not wait for a
hosted run, so replay it by hand when a change touches dependencies, `packaging/`, the
`Dockerfile`, or network or authentication code, and before a production deploy
([TESTING.md](../guides/TESTING.md#before-a-merge)). For a deploy, a green run on the
commit being deployed (`gh run list --workflow security.yml --commit <sha>`) stands for
the replay, and the target host is scanned as above. Nothing else holds back a red run:
the `master` ruleset requires no status check. All `uses:` references are immutable
commit SHAs with human-readable version comments. It performs:

1. repository-specific local source/configuration contracts (`make security-check`);
2. CodeQL C/C++ analysis of what the build step compiles: the warning-as-error
   `make build`, `pfile`, and the legacy migration tools in `migrations/tools`, which
   read old player and account files. The test harnesses and the area generators in
   `areas/src/areas` are not built there, so CodeQL does not see them;
3. Trivy `v0.70.0` scanning of the generated direct-package root while preserving the
   equivalent SPDX document as the portable SBOM. That root is the runner's: a fresh
   `ubuntu-24.04` image that has just installed the build-deps package, so the
   archive's newest builds and the runner's alternatives (MySQL, not MariaDB; git from
   the runner's PPA). It shows whether those builds carry a fixed HIGH or CRITICAL
   advisory, not whether a host Duris runs on is up to date.

On GitHub it is an *advanced* CodeQL configuration, so CodeQL default setup must be off
there (`gh api repos/<owner>/<repo>/code-scanning/default-setup` reads `not-configured`);
otherwise the upload is refused and every later step, Trivy included, is skipped.

A local CodeQL replay must trace an uncached build: a compile that ccache serves never
reaches CodeQL's tracer, and one replay here traced 34 of 1265 files that way. Take
ccache off `PATH`, set `CCACHE_DISABLE=1`, and read the analysis's "scanned N out of M"
line.

Native packages remain distribution-managed; the generated inventory is the review input
because Dependabot has no ecosystem for an `equivs` control file. Dependabot
(`.github/dependabot.yml`) proposes updates to the workflow action pins and to the
`site/` npm packages weekly, and its security updates and alerts cover `site/` as well.

## Ownership And Failure Policy

Repository maintainers own triage. A fixed HIGH or CRITICAL Trivy finding fails the
check. The workflow's scan lists nothing else (`ignore-unfixed`, `HIGH,CRITICAL`):
unfixed and lower findings are seen only by running Trivy by hand over
`bin/security/scanner-rootfs` without those options; changing that policy requires a
reviewed workflow change. No vulnerability is ignored in a
committed exception file at this baseline.

Reports are triaged for reachability, affected supported versions, exploitability, and
available upstream fixes. A temporary exception must be documented in a public issue
when disclosure is safe, or in the private advisory when it is not, with an owner,
rationale, compensating control, and expiry date.

## Baseline Result (2026-10-09)

The workflow replayed locally on 2026-10-09, at the tree that records this result:

- `make security-check` (inventory, SPDX and the repository's source/configuration
  contracts): passed.
- CodeQL 2.27.1, its `cpp-code-scanning` suite (58 rules), over the build step's
  compilation with ccache off: 1103 of 1265 C/C++ files, where the hosted run below
  covered 1087 without `pfile` and `migrations/tools`. Those two added ten results, all
  in the migration tools: eight `cpp/overflowing-snprintf` in `migrate_players.c` and two
  `cpp/toctou-race-condition`, in `migrate_accounts.c` and `pfile_converter.c`. With them
  fixed, the suite reports 0 results.
- Trivy `v0.70.0`, vulnerability database of 2026-10-08 19:05 UTC, over the root that
  `make security-sbom` wrote in a fresh `ubuntu:24.04` container after it installed the
  build-deps package, as the workflow's runner does (git came from Ubuntu, not the
  runner's PPA). All 23 direct dependencies resolved, each with its source package:
  `libcurl4-gnutls-dev` `8.5.0-2ubuntu10.15` (source `curl`; it joined the build
  dependencies on 2026-09-06) and `mysql-server-8.0` `8.0.46-0ubuntu0.24.04.4` among
  them. No fixed HIGH or CRITICAL finding, so the gate passes. Without the gate's
  options it lists 26 unfixed findings: MEDIUM for cJSON (9), Redis (7, in both
  `redis-server` and `redis-tools`), Git (`CVE-2024-52005`) and zlib (`CVE-2026-85091`),
  and LOW for `clang-format-18` (`CVE-2024-7883`). This is not a clean or
  vulnerability-free claim. A fixed HIGH/CRITICAL finding against the Ubuntu 24.04
  libcurl package is fixed by the package update, never by a weakened transport setting.
- The hosted run of 2026-10-08 on `master` at `690a7575d` (run 37808827646) is not a
  dependency result: its root had no `Source:` lines, so Trivy matched only packages
  named like their source (`git`, `gawk`, `gdb`, `valgrind`) and saw none of libcurl's,
  OpenSSL's or Redis's advisories. The August scan had the same blind spot. Its CodeQL
  result, 0 results, holds for what it built.
- No host Duris runs on has been scanned yet.
- On 2026-10-08 the owner turned on, for `LuminariMUD/Duris`, private vulnerability
  reporting, Dependabot security updates, and secret scanning with push protection.
- Transitive and deployment dependency vulnerability status: `UNKNOWN` by design.

Security reports follow [SECURITY.md](../../SECURITY.md). Generated reports, scanner
databases, credentials, and private advisory contents must never be committed.
