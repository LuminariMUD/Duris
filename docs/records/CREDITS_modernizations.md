# Credits: moshehbenavraham

**moshehbenavraham**, also known as **Zusuk** and **Max** (max@aiwithapex.com), founder of
[LuminariMUD.com](https://luminarimud.com).

This record credits the work moshehbenavraham did on DurisMUD from the first commit on
2026-08-25 to 2026-09-23, with the detail on the first two weeks, the most active stretch. It
was built out upon the work of previous contributors. Every figure comes from the Git history;
see [How the figures were counted](#how-the-figures-were-counted).

## At a glance

- **739 of the 799 commits** made in the first two weeks (2026-08-25 to 2026-09-08).
- **461 non-merge commits in the first week** and 203 in the second. The busiest day,
  2026-08-28, had 170.
- **813 commits by 2026-09-23:** 725 non-merge, which is 62% of the 1,171 made in that span,
  and 88 merges.

## Before and after

The tree at `4b56d8a1e` (2026-08-07, the last commit before the first one) against the tree at
`a1369059b` (2026-09-08, two weeks in):

| | Before | Two weeks in |
|---|---|---|
| Repository root | 49 entries: loose scripts, archives and binaries | 31 entries |
| `src/` | 364 files in one flat directory | 21 topical directories |
| `docs/` | none; 3 Markdown files in the whole tree | 85 files in 14 sections |
| Tests | 145 files | 571 files |
| CI | one 25-line build job | plus a quality gate, a security scan and Dependabot |
| Compiler flags | `-Wno-write-strings` and `-D_FORTIFY_SOURCE=0` | 28 warning flags under `-Werror`, and `-D_FORTIFY_SOURCE=3` |
| Migrations | 27 files | 123 files |
| `scripts/` | 2 files | 48 files |
| Root build and packaging | none | `Makefile`, `Dockerfile`, `compose.yaml`, `VERSION`, `deploy/`, `packaging/` |
| Tracked clutter | player, SQL and ship archives (about 8 MB), a compiled binary, a TLS private key, `__pycache__/`, `attic/` (122 files), `old_code/` | none |

## The work

### Repository structure

- **Root:** reorganised into topical directories on the first day (`7ab89cac9`). The archives,
  the key, the binary and the dead trees left the repository in the first three days.
- **Source tree:** every source file in `src/` moved into a directory named for what it does
  (`account`, `combat`, `economy`, `item`, `magic`, `net`, `persistence`, `world` and 13
  more) in 18 commits on 2026-08-31, with the build and include paths fixed to match.

### Build and compiler discipline

- **Warnings as errors:** the build went from one flag that silenced a warning to
  `-Wall -Wextra -Wpedantic -Werror` plus format, overflow, null-dereference, shadow and
  use-after-free checks.
- **No exceptions left:** all six legacy warning categories (write-strings, unused parameters,
  unused variables, missing field initialisers, set-but-unused variables and unused functions)
  were resolved across the code base rather than suppressed, and
  `tests/async/test_compiler_warning_profile.py` fails if a `-Wno-` flag comes back.
- **Hardening:** `_FORTIFY_SOURCE=3`, `-fstack-protector-strong` and
  `-fstack-clash-protection`.
- **One entry point:** a root `Makefile` with `build`, `test`, `test-all`, `test-db`,
  `security-check`, `security-sbom`, `clean` and `clean-all`.
- **Formatting:** `scripts/format.sh`, the commit hook installer and a repaired
  `.clang-format` (the file existed but was unusable).

### CI/CD

All three files added to `.github/` in the first two weeks, and 96% of the lines:

- **`quality.yml`** (2026-08-27): the format check, the warning profile, a full
  warnings-as-errors compile, and a second job that builds without MySQL, boots the game loop
  and runs the flat-file authority tests.
- **`security.yml`** (2026-08-27): CodeQL analysis, a Trivy dependency scan, a security
  baseline with an SBOM, and an enforced vulnerability policy.
- **Dependabot** configuration.
- **Later in the span:** `pages.yml` for the project website and `production-uptime.yml`
  (both 2026-09-15).

### Tests

- **399 of the 425 test files** added in the first two weeks, and 87% of the test lines
  (about 72,900).
- **The suite two weeks in:** 425 Python tests, 58 C++ harnesses and 70 shell runners.
- **By 2026-09-23:** 411 of the 853 test files added since the start.

### Documentation

- **`docs/` did not exist.** Two weeks in it held 85 files in 14 sections behind one index
  (`docs/README_docs.md`): the existing text gathered in from around the tree, plus 28 new
  files, 25 of them and 90% of the new lines (about 46,000) by moshehbenavraham.
- **Root documents:** `CONTRIBUTING.md`, `SECURITY.md` and the agent guide `AGENTS.md`.
- **Diagrams:** the server architecture and the database model.
- **Operations and reference:** Docker, Chaos mode, batch item commands, the website and
  donation APIs, the world recovery format, and the legacy dump import.
- **Agent skills:** `burnin`, `mergetree`, `plan-ablation` and `scopeguard`.

### Data and persistence

- **Migrations:** 76 of the 80 migration files added in the first two weeks.
- **One item, one owner:** the `item_current_owner` table and its transactional ownership
  primitive (`cab7e556f`, 2026-08-27), then the cut-over of live items, lockers and auction
  settlement onto it. Its primary key is still what stops one item having two owners.
- **A flat-file backend:** all 82 files of `src/flatfile/`, so the server builds, boots and
  runs with no MySQL at all: identities, accounts, players, items, auctions, shops, artifacts,
  alliances and world quests.
- **Redis world recovery:** grown from 3 source files to 42, with authenticated recovery
  generations and scoped maintenance.
- **Accounts:** permanent account deletion, with the erasure carried into backups.
- **Local setup:** the private local development setup, a local MariaDB deployment, and the
  `Dockerfile` and `compose.yaml`.

### Gameplay

- The `abort` command, which stops a spell being cast.
- A hometown for every player race that will not attack it.
- Class equipment kits for new Chaos characters, checked complete before play begins.
- A master spellbook holding every spellbook-class spell.
- Player news, with a short notice at login.
- Fixes to mob hunting, max-level quest feedback, repeated spell fade messages and the
  shipyard list.

## What came after

After 2026-09-23 the work continued in this repository. The persistence reset (Phases 1 to 7)
kept the ownership table and simplified the save-time checks built on it in this period; its
decision record is [ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md).

## How the figures were counted

- **History:** `master`, from `4b56d8a1e` to `a1369059b` for the first two weeks and to
  `e1357a30a` (2026-09-23) for the whole span.
- **Author:** commits whose author name is `moshehbenavraham` or `Max aka Mosheh`.
- **Files added:** files a commit created that still existed at the end of the range. Moved
  files count as moves, not additions.
- **Lines:** `git log --numstat`, merge commits excluded.
