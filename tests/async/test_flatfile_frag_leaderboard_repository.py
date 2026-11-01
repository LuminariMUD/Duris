#!/usr/bin/env python3

from _paths import extract_function, rel
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory(prefix="duris-flat-frag-leaderboard-") as temporary:
    temporary_path = pathlib.Path(temporary)
    binary = temporary_path / "flatfile_frag_leaderboard_test"
    compile_result = subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-Isrc",
            "tests/async/flatfile_frag_leaderboard_repository_harness.cpp",
            rel("flatfile_frag_leaderboard_repository.c"),
            rel("flatfile_authority_transaction.c"),
            rel("flatfile_store.c"),
            "-lcrypto",
            "-pthread",
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if compile_result.returncode:
        raise SystemExit(compile_result.stdout)
    run_result = subprocess.run(
        [str(binary), str(temporary_path / "state")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if run_result.returncode:
        raise SystemExit(run_result.stdout)
    print(run_result.stdout.strip())

flatfile_route = extract_function("sql.c", "void sql_update_frag_leaderboard(P_char ch)")
for token in (
    "flatfile_frag_leaderboard_upsert",
    "record.total_frags = ch->only.pc->frags",
    "record.racewar = GET_RACEWAR(ch)",
    "persistence_alert(AVATAR, \"frag_leaderboard\"",
):
    if token not in flatfile_route:
        raise SystemExit(f"client-free frag leaderboard route is missing {token}")
