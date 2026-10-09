# Security & Compliance

> Cumulative security posture and GDPR compliance record. Findings were last audited at
> Phase 03 (2026-08-27); the text was brought up to date on 2026-10-09.
>
> This is an engineering record, not legal advice or a determination of applicability.

---

## Current Security Posture

### Overall: AT RISK

The implemented security boundaries are clean. The remaining risk is the externally
owned lifecycle/privacy policy needed before canonical export, erasure, retention, and
archive behavior can be activated or a compliance claim can be made.

| Metric | Value |
|--------|-------|
| Open Findings | 1 |
| Critical/High | 0 |
| Medium/Low | 1 medium |
| Phases Audited | 4 |
| Last Clean Security Phase | P03 |
| Findings Resolved | 9 |

### Existing Safeguards

- [P03] Runtime role, target allow-list, credentials, transport, database session state,
  schema identity, and migration history fail closed before mutation or service startup.
- Player loads, saves, and critical commands use bounded typed work, exact identity,
  operation dedupe and transactional authority. Memory is the authority and one writer
  applies saves in capture order
  ([ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md)).
- [P03] Logs and reports use stable identifiers, counts, timing, checksums, and outcomes;
  gate output rejects credentials, row values, player data, and private targets.
- [P03] Archive, export, and erasure tooling is policy-bound, synthetic-only while
  approval is pending, permission-restricted, checksummed, resumable, and restore-aware.
- [P03] MySQL 8.0 and MariaDB 10.11 compatibility and clean-build portability are tested.
- [P03] The unauthenticated health response exposes only process and selected-persistence
  readiness, performs no blocking backing-store round trip, is non-cacheable, and closes
  the probe connection.

---

## Open Findings

### Critical / High

No open critical or high findings.

### Medium / Low

- **[P00-S08] Canonical data-subject and retention policy is not approved or active**
  - Severity: Medium
  - Files: `migrations/data_lifecycle_manifest.json`, `scripts/lifecycle_archive.py`,
    `scripts/personal_data_export.py`, `scripts/account_erasure.py`
  - Description: Phase 03 implemented complete technical inventory, guarded archive,
    authenticated export, erasure/tombstone, and restore contracts. Canonical actions
    remain disabled because lawful-basis, disclosure, retention, and exception decisions
    have no controller-approved references.
  - Remediation: The responsible controller must approve the manifest decisions. Then
    validate the real adapters and protected delivery on isolated data before activation.
  - Status: Open - external controller decision required
  - Partial decision (2026-10-09): the owner decided what the game may log or watch of its
    players and how long it keeps their network addresses
    ([ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md)). Private conversation
    is not logged, `snoop` tells its target, and addresses are kept at most 30 days. The
    logging rule is in the code since 2026-10-09; the snoop and address rules are not yet.
    The lawful basis and the rest of the policy stay pending.
  - Opened: P00 (2026-08-26); technical boundary completed P03 (2026-08-27)

---

## GDPR Compliance Status

### Overall: NON-COMPLIANT

This status means the repository cannot yet support a GDPR-readiness claim. Engineering
controls pass, but the required controller decisions, privacy notice, deployment/processor
inventory, and canonical activation evidence are absent. Pending decisions deliberately
fail closed.

### Personal Data Inventory

| Data Element | Source | Storage | Purpose | Legal Basis | Retention | Deletion Path | Since |
|-------------|--------|---------|---------|-------------|-----------|---------------|-------|
| Account identity and authentication data | Registration, login, account updates | Account tables and request-scoped runtime state | Authentication, recovery, account operation | Pending controller decision | Pending | Policy-gated erasure/tombstone contract; canonical action disabled | P00 |
| Network identifiers and access history | Client connections | Account/player IP fields, login and operational records, log archives, `lib/etc/hosts` | Abuse prevention, authentication history, operations | Pending controller decision | 30 days, ban-list entries while the ban stands (ADR 0003, 2026-10-09); not yet enforced | Manifest-mapped erasure or retained pseudonymization; disabled | P00 |
| Character profiles and user-authored content | Character creation and gameplay | Player tables, messages, descriptions, pfiles and archives | Gameplay and communication | Pending controller decision | Pending | Manifest-mapped export and erasure contracts; disabled | P00 |
| Gameplay, economy, ownership and audit history | Gameplay commands and events | Current rows, ledgers, inbox/results, outbox and histories | Gameplay authority, reconciliation, fraud and audit | Pending controller decision | Protected/pending | Value-safe domain disposition plus approved retain/pseudonymize rules | P00 |
| Activity, moderation and communication records | Runtime and administrator actions | Database logs, message/PvP/moderation tables and files | Operations, moderation, support and audit | Pending controller decision | Pending. Private conversation is not logged, only petitions, immortal actions and the newbie channel (ADR 0003, enforced since 2026-10-09). `snoop` is to tell its target and be audited, and immortals are not to read a player's private messages with `recall` (ADR 0003); not yet enforced | Manifest dependency order and approved exception rules | P00 |
| Recovery and generated private copies | Persistence, failures and operator actions | Locker receipts, Redis recovery, backups, export spool and archives | Durability, disaster recovery and data access | Pending controller decision | Pending; export TTL bounded | Restore-time tombstones, one-time export retrieval and spool expiry | P00 |

### Compliance Checklist

| Requirement | Status | Notes |
|------------|--------|-------|
| Data stores and technical purposes are inventoried | PASS | All declared database and non-database stores have one versioned lifecycle entry. |
| Lawful basis and controller approval are documented | FAIL | Explicitly pending; the repository does not invent legal decisions. |
| Data minimization is technically enforced | PASS | Bounded DTOs, aggregate-only evidence, secret exclusions and redacted logs are tested. |
| Retention limits are approved and active | FAIL | Destructive rules and archive scheduling remain disabled by policy. Network identifiers have an approved 30-day limit (ADR 0003), not yet active. |
| Authenticated access/export path is active | FAIL | Packaging, isolation and delivery contracts pass synthetically; canonical collection/release is disabled. |
| Deletion/erasure path is active | FAIL | Ordered erasure, tombstones and restore protection pass synthetically; canonical mutation is disabled. |
| No private values in persistence diagnostics | PASS | Log-hygiene and gate-containment tests pass. |
| Security of processing is verified | PASS | One-writer persistence, critical transactions, migration/boot gates and dual-engine tests pass. |
| Third-party/processor transfers are documented | FAIL | No processor inventory, backup-storage record or transfer documentation exists. |
| Vulnerability reporting process exists | PASS | `SECURITY.md` names the current `0.1.x` line and this repository's private vulnerability reporting form, turned on 2026-10-08. |

---

## Dependency Security

### Current Vulnerabilities

The `security baseline` workflow runs the scans on every push to `master`, on a fresh
GitHub runner. Until 2026-10-09 its dependency scan matched packages by binary name and
missed every advisory filed under a source package (curl, OpenSSL, Redis), so no hosted
or earlier dependency result counts. The workflow replayed locally on 2026-10-09 over the
runner's package set (all 23 direct packages, `libcurl4-gnutls-dev` and the MySQL server
among them) found no fixed high or critical issue and 26 unfixed lower ones (cJSON,
Redis, Git, zlib, `clang-format`). CodeQL found ten issues in the migration tools, now
fixed, and nothing else. No host Duris runs on has been scanned. Transitive
dependencies, deployment-only services, and external infrastructure are outside the scan;
the record does not claim the dependency set is vulnerability-free
([SECURITY_BASELINE.md](../operations/SECURITY_BASELINE.md)).

| Scope | Current State | Status |
|-------|---------------|--------|
| Native/system direct dependencies | Deterministic inventory and SPDX 2.3 output (`make security-sbom`) | PARTIAL |
| Workflow action pins | Immutable SHAs, held by `test_security_dependency_baseline.py`; Dependabot proposes updates weekly | PASS |
| Source and configuration security | `make security-check` and CodeQL on every push to `master`, over the server, the editor, the area tools, `pfile` and `migrations/tools` (not the test harnesses or the area generators); 0 results on the 2026-10-09 replay | PASS |
| Container/root filesystem scan | Pinned Trivy, by source package, over the runner's direct packages on every push to `master`; the 2026-10-09 replay found no fixed high or critical finding. No host Duris runs on has been scanned | PARTIAL |

---

## Resolved Findings

| ID | Finding | Severity | Resolved | Phase | Resolution |
|----|---------|----------|----------|-------|------------|
| P00-S01 | Sensitive SQL/private values in persistence logs | High | 2026-08-27 | P00 | Replaced with stable metadata-only diagnostics and regression checks. |
| P00-S02 | Database credentials and transport failed open | High | 2026-08-27 | P00 | Explicit role, credentials, target, TLS/local transport and session invariants now fail closed. |
| P00-S03 | Tracked local TLS key usable on network listeners | High | 2026-08-28 | P00 | Tracked keypair removed; ignored per-developer generation is loopback-only and all private keys require owner-only metadata. |
| P00-S04 | Persistence could overwrite or destroy newer state | High | 2026-08-27 | P01 | Typed workers and safe terminal behavior replaced forked saves; since ADR 0002 one writer applies every save in capture order. |
| P00-S05 | Economy/ownership writes lacked atomic integrity | High | 2026-08-27 | P02 | Operation-keyed domain transactions couple authority, ledger, result and outbox state. |
| P00-S06 | SQL construction relied on unenforced session assumptions | Medium | 2026-08-27 | P00 | Every connection now establishes and verifies the required session contract. |
| P00-S07 | Private chest secrets used unsalted SHA-256 | Medium | 2026-08-27 | P00 | Bcrypt with unique salts and safe legacy upgrade is enforced. |
| P00-S09 | Redis failure could block or trigger synchronous saves | Medium | 2026-08-27 | P00 | Connections are bounded and dirty state remains retryable without synchronous fallback. |
| P00-S10 | Security/dependency automation was placeholder-only | Low | 2026-08-27 | P00 | Disclosure policy, inventory, SBOM, CodeQL, Trivy and dependency updates are configured. |
