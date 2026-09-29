# AGENTS.md

## Golden rules

Write the simplest code that fully solves the task. Build only what is needed now: no new abstractions, helpers, options, or layers for needs that don't exist yet, and no handling for situations that can't happen. Reuse what the codebase already has before adding anything new. Simple means easy to read and follow, not short or clever, so keep the error handling and tests the task really needs. If a fix would stack another patch onto tangled code, straighten out the piece you are touching instead. Before finishing, reread the change and cut anything the task would not miss.

## Repository map

- `src/`: the server. Its `.c` files are compiled as C++20 with `g++`.
- `tests/async/`: focused regression and source-contract tests.
- `areas/`: world data and generators.
- `migrations/`: the authoritative location for schema changes.
- `docs/`: all project documentation, where practical.
- `README.md`: setup, runtime, and database details.
- `.env`: `ENVIRONMENT` says whether this is local/dev or production/remote. It also holds the DB credentials and the in-game test account (`GAME_ACCOUNT_NAME`, `GAME_ACCOUNT_PASSWORD`, `GAME_ACCOUNT_CHARACTER_NAME`).

## Working conventions

- **Scope:** Keep changes narrow and follow the style of nearby code.
- **Format:** `.clang-format` is authoritative for touched C/C++ code. `./scripts/format.sh` formats your changed lines; `--check` only verifies. `./scripts/install-hooks.sh` installs the hook that enforces it at commit time.
- **Build:** Run `make -C src` after C/C++ changes. The executable is `bin/server/dms_new`. All compiled artifacts belong under `bin/` and must not be committed.
- **Test:** Run the smallest relevant test directly, for example `python3 tests/async/test_<feature>.py` or its `run_<feature>.sh` wrapper. Add or update a focused regression test when behavior changes.
- **Verify:** Use local builds, focused executable tests, and applicable gameplay/persistence journeys as verification. Do not require or wait for CI results to finish or merge work, and do not bypass other review or branch protection requirements. Report any validation that could not be run.
- **Attribution:** NEVER add co-authors, attributions, `Claude-Session`, or signed-off-by lines.

## Safety

- **Production:** Never run migrations, wipes, or operational scripts against production without owner/user permission. Staging and local/dev need no permission: run them freely.
- **Migrations:** Keep them additive, guarded, and re-runnable where practical.
- **Protected files:** Do not edit or commit credentials, private keys, logs, player/account data, archives, generated area outputs, or local environment files unless the task explicitly requires it.
- **Git:** Preserve unrelated worktree changes and avoid destructive Git commands.
