#!/usr/bin/env python3

from _paths import SRC, rel, extract_function
import pathlib
import subprocess
import tempfile
import re
from _paths import HARNESS_STUBS


ROOT = pathlib.Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory(prefix="duris-flat-artifact-") as temporary:
    temporary_path = pathlib.Path(temporary)
    binary = temporary_path / "flatfile_artifact_test"
    compile_result = subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-Isrc",
            "tests/async/flatfile_artifact_repository_harness.cpp",
            rel("flatfile_artifact_repository.c"),
            rel("artifact_population.c"),
            rel("player_snapshot_codec.c"),
            rel("item_transfer_command.c"),
            rel("critical_command.c"),
            rel("flatfile_authority_transaction.c"),
            rel("flatfile_store.c"),
            "-lcrypto",
            "-pthread",
            str(HARNESS_STUBS), "-o",
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

    runtime_binary = temporary_path / "flatfile_artifact_bind_runtime_test"
    runtime_compile_result = subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-D__NO_MYSQL__",
            "-ffunction-sections",
            "-fdata-sections",
            "-Isrc/no_mysql",
            "-Isrc",
            "tests/async/flatfile_artifact_bind_runtime_harness.cpp",
            rel("flatfile_artifact_repository.c"),
            rel("artifact_population.c"),
            rel("player_snapshot_codec.c"),
            rel("item_transfer_command.c"),
            rel("critical_command.c"),
            rel("flatfile_authority_transaction.c"),
            rel("flatfile_store.c"),
            "-Wl,--gc-sections",
            "-lcrypto",
            "-pthread",
            str(HARNESS_STUBS), "-o",
            str(runtime_binary),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if runtime_compile_result.returncode:
        raise SystemExit(runtime_compile_result.stdout)
    runtime_result = subprocess.run(
        [str(runtime_binary), str(temporary_path / "runtime-state")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if runtime_result.returncode:
        raise SystemExit(runtime_result.stdout)
    print(runtime_result.stdout.strip())

    gameplay_binary = temporary_path / "flatfile_artifact_gameplay_runtime_test"
    gameplay_compile_result = subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-fsanitize=undefined",
            "-fno-sanitize-recover=all",
            "-D__NO_MYSQL__",
            "-ffunction-sections",
            "-fdata-sections",
            "-Isrc/no_mysql",
            "-Isrc",
            "tests/async/flatfile_artifact_runtime_harness.cpp",
            "src/core/safe_format.c",
            rel("artifact.c"),
            rel("item_ownership_runtime.c"),
            rel("flatfile_artifact_repository.c"),
            rel("artifact_population.c"),
            rel("player_snapshot_codec.c"),
            rel("item_transfer_command.c"),
            rel("critical_command.c"),
            rel("flatfile_authority_transaction.c"),
            rel("flatfile_store.c"),
            "-Wl,--gc-sections",
            "-lcrypto",
            "-pthread",
            str(HARNESS_STUBS), "-o",
            str(gameplay_binary),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if gameplay_compile_result.returncode:
        raise SystemExit(gameplay_compile_result.stdout)
    gameplay_result = subprocess.run(
        [str(gameplay_binary), str(temporary_path / "gameplay-state")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if gameplay_result.returncode:
        raise SystemExit(gameplay_result.stdout)
    print(gameplay_result.stdout.strip())

    artifact_source = (SRC / "artifact.c").read_text()
    # Gameplay decisions and maintenance share the game-thread cache. The native
    # fixtures exercise values, writer refusal, retry and late acknowledgements;
    # these boundaries keep direct filesystem operations out of the hot paths.
    for signature in (
        "bool get_artifact_data_sql(", "artifact_feed_result artifact_feed_sql(",
        "void artifact_feed_to_min_sql(", "bool remove_owned_artifact_sql(",
        "void event_artifact_check_poof_sql(", "void event_artifact_wars_sql(",
        "void event_artifact_check_bind_sql(", "void arti_fixit_sql(",
        "void arti_reset_sql(", "void arti_clear_sql(",
    ):
        definition = re.search(re.escape(signature) + r"[^;{]*\{", artifact_source)
        assert definition is not None, signature
        body = extract_function("artifact.c", definition.group(0))
        assert "flatfile_artifact_" not in body, signature + " reads or writes storage directly"
        assert "db_query(" not in body and "qry(" not in body, signature + " waits for SQL"

    list_signature = "void list_artifacts_sql(P_char ch, int type, bool Godlist, bool allArtis)\n{"
    list_start = artifact_source.index(list_signature)
    list_end = artifact_source.index("\nvoid setupMortArtiList_sql(", list_start)
    list_body = artifact_source[list_start:list_end]
    if "flatfile_artifact_list(" not in list_body:
        raise AssertionError("client-free artifact list bypasses flat authority")
    if "requires a completed durable backend" in list_body:
        raise AssertionError("client-free artifact list remains disabled")

    player_start = artifact_source.index("void arti_player_sql(P_char ch, char *arg)\n{")
    player_body = artifact_source[player_start:]
    if "flatfile_artifact_list(" not in player_body:
        raise AssertionError("client-free per-player artifact list bypasses flat authority")
    if "requires MySQL support" in player_body:
        raise AssertionError("client-free per-player artifact list remains disabled")

    syncdb = extract_function("artifact.c", "void arti_syncdb_sql(P_char ch)\n{")
    assert "flatfile_artifact_reconcile_players(" not in syncdb
    assert "reconciliation requires a complete population audit" in syncdb

    boot_source = (SRC / "db.c").read_text()
    boot_start = boot_source.index("void boot_db(int mini_mode)\n{")
    boot_end = boot_source.index("\nvoid update_stat_data()", boot_start)
    boot_body = boot_source[boot_start:boot_end]
    if "flatfile_artifact_ensure(" not in boot_body:
        raise AssertionError("flat boot does not establish artifact authority")
    if boot_body.index("flatfile_artifact_ensure(") > boot_body.index("ne_init_events();"):
        raise AssertionError("artifact authority is established after boot zone resets")

    if "artifacts_load()" not in boot_body or boot_body.index("artifacts_load()") > boot_body.index("ne_init_events();"):
        raise AssertionError("flat artifact memory is not hydrated before world population")
