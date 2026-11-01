#!/usr/bin/env python3

from _paths import extract_function, rel
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory(prefix="duris-flat-offline-") as temporary:
    temporary_path = pathlib.Path(temporary)
    binary = temporary_path / "flatfile_offline_test"
    sources = [
        "tests/async/flatfile_offline_message_repository_harness.cpp",
        rel("flatfile_offline_message_repository.c"),
        rel("flatfile_authority_transaction.c"),
        rel("flatfile_store.c"),
    ]
    compile_result = subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-Isrc",
            *sources,
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

flatfile_route = "\n".join(extract_function("sql.c", signature) for signature in (
    "static bool enqueue_flat_offline_message(",
    "void send_to_pid_offline(const char *message, int pid)",
    "void send_offline_messages(P_char ch)",
))
assert "enqueue_flat_offline_message(message, pid);" in flatfile_route
for token in (
    "flatfile_offline_message_enqueue",
    "flatfile_offline_message_list",
    "flatfile_offline_message_acknowledge",
):
    if token not in flatfile_route:
        raise SystemExit(f"client-free offline route is missing {token}")
