#!/usr/bin/env python3
"""A player's death enters collector intake with its corpse's save."""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def function_body(text: str, signature: str) -> str:
    """Return one function from its signature through its closing brace."""
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 0
    for position in range(opening, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                return text[start:position + 1]
    raise AssertionError(f"unterminated function: {signature}")


def main() -> None:
    src = ROOT / "src"
    fight = (src / "combat/fight.c").read_text(encoding="utf-8", errors="replace")
    make_corpse = function_body(fight, "P_obj make_corpse(P_char ch, int loss)")
    # The death begins before the corpse's first save, which carries it.
    assert make_corpse.index("collector_death_enrollment_begin(ch, corpse);") < make_corpse.index(
        "writeCorpse(corpse);"
    )
    files = (src / "core/files.c").read_text(encoding="utf-8", errors="replace")
    queue = function_body(files, "bool queue_corpse_save(P_obj corpse, bool remove)")
    assert "collector_death_enrollment_for(corpse, &snapshot.collector_death);" in queue
    assert "flatfile_corpse_snapshot_apply(path, record, remove, death, &error)" in queue
    pipeline = (src / "player/player_save_pipeline.c").read_text(encoding="utf-8")
    assert "collector_death_enrollment_saved(completion.owner, completion.error_code);" in pipeline
    # Both writers record the death in the corpse save's own transaction.
    repository = (src / "player/player_snapshot_repository.c").read_text(encoding="utf-8")
    write_corpse = function_body(repository, "query_result write_corpse(")
    assert write_corpse.index("insert_item_rows(") < write_corpse.index(
        "enroll_collector_death(connection, corpse.collector_death, written,"
    )
    assert "collector_repository_enroll_death(connection, death, eligible, refused)" in repository
    flat = (src / "flatfile/flatfile_player_repository.c").read_text(encoding="utf-8")
    assert "flatfile_collector_prepare_death_enrollment(" in function_body(
        flat, "player_save_apply_result flatfile_corpse_snapshot_apply("
    )

    output = ROOT / "bin" / "tests"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="collector-death-enrollment-", dir=output) as directory:
        binary = Path(directory) / "collector-death-enrollment"
        subprocess.run(
            [
                "g++",
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                "-O2",
                "-I",
                str(src),
                str(src / "persistence/critical_command.c"),
                str(src / "item/item_transfer_command.c"),
                str(src / "player/player_snapshot_codec.c"),
                str(src / "economy/collector_policy.c"),
                str(src / "economy/collector_death_enrollment.c"),
                str(ROOT / "tests/async/collector_death_enrollment_harness.cpp"),
                "-lcrypto",
                "-o",
                str(binary),
            ],
            check=True,
        )
        subprocess.run([str(binary)], check=True, timeout=30)
    print("collector death intake rides the corpse save PASS")


if __name__ == "__main__":
    main()
