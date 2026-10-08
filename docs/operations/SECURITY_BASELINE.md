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
  `packaging/duris-build-deps.equivs`, the installed alternative and version when
  available, and unresolved expressions explicitly.
- `duris.spdx.json` is SPDX 2.3 for those resolved direct packages. Its timestamp comes
  from the source commit and its namespace from canonical inventory content, so the
  same commit and installed package set reproduce byte-identical output.
- `scanner-rootfs/` contains minimal OS identity and dpkg status records for only the
  resolved direct packages. It exists because Trivy cannot infer Debian/Ubuntu package
  semantics from a direct-package-only SPDX document; the workflow rejects an
  unsupported or empty scan instead of treating it as clean.

The inventory does not resolve transitive packages, deployment-only MySQL/Redis/host
services, containers, firmware, or external DurisWeb infrastructure. SPDX generation
does not perform a vulnerability scan.

## The Security Workflow

`.github/workflows/security.yml` is the recipe. No hosted pipeline runs it: replay it by
hand when a change touches dependencies, `packaging/`, the `Dockerfile`, or network or
authentication code, and before a production deploy
([TESTING.md](../guides/TESTING.md#before-a-merge)). All `uses:` references are immutable
commit SHAs with human-readable version comments. It performs:

1. repository-specific local source/configuration contracts (`make security-check`);
2. a warning-as-error C++ build captured by CodeQL C/C++ analysis;
3. Trivy `v0.70.0` scanning of the generated direct-package root while preserving the
   equivalent SPDX document as the portable SBOM.

On GitHub it is an *advanced* CodeQL configuration, so CodeQL default setup must be off
there (`gh api repos/<owner>/<repo>/code-scanning/default-setup` reads `not-configured`);
otherwise the upload is refused and every later step, Trivy included, is skipped.

Native packages remain distribution-managed; the generated inventory is the review input
because Dependabot has no ecosystem for an `equivs` control file.

## Ownership And Failure Policy

Repository maintainers own triage. A fixed HIGH or CRITICAL Trivy finding fails the
check. Unfixed findings remain visible for triage but do not fail by default; changing
that policy requires a reviewed workflow change. No vulnerability is ignored in a
committed exception file at this baseline.

Reports are triaged for reachability, affected supported versions, exploitability, and
available upstream fixes. A temporary exception must be documented in a public issue
when disclosure is safe, or in the private advisory when it is not, with an owner,
rationale, compensating control, and expiry date.

## Baseline Result (2026-08-27)

- Direct manifest inventory and SPDX generation: completed locally.
- Repository-specific source/configuration gate: passed locally.
- Workflow syntax (`actionlint` 1.7.10): passed locally.
- CodeQL C/C++ analysis: ran clean; the run reported no failing alert.
- Trivy `v0.70.0` with the 2026-08-26 vulnerability database recognized Ubuntu 24.04
  and scanned all 19 resolved direct packages. It reported one unfixed MEDIUM advisory
  (`CVE-2024-52005`) for the installed Ubuntu Git package and no fixed HIGH/CRITICAL
  finding. This passes the stated gate but is not a clean or vulnerability-free claim.
- libcurl4-gnutls-dev added to the build dependencies (2026-09-06), after this scan:
  the count of 19 predates it and no scan has covered it yet. A fixed
  HIGH/CRITICAL finding against the Ubuntu 24.04 package is fixed by the package update,
  never by a weakened transport setting.
- Transitive and deployment dependency vulnerability status: `UNKNOWN` by design.

Security reports follow [SECURITY.md](../../SECURITY.md). Generated reports, scanner
databases, credentials, and private advisory contents must never be committed.
