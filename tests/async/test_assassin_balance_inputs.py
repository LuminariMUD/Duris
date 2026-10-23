#!/usr/bin/env python3
"""Prepared Assassin audits must reject changes to their runtime inputs."""
from pathlib import Path
import tempfile

from run_assassin_balance_journey import RUNTIME_INPUTS, source_digest


def main():
    with tempfile.TemporaryDirectory(prefix="assassin-inputs-") as temporary:
        root = Path(temporary)
        for name in ("src", "lib", "areas_mini"):
            (root / name).mkdir()
        for name in RUNTIME_INPUTS:
            path = root / name
            if not path.is_dir():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture input")
        (root / "src/server.c").write_text("server source")
        for name in ("lib/duris.properties", "areas_mini/mini.wld"):
            (root / name).write_text("runtime input")
        source_before = source_digest(root)
        runtime_before = source_digest(root, RUNTIME_INPUTS)
        for name in ("lib/duris.properties", "areas_mini/mini.wld",
                     "areas/obj/heavens.obj", "tests/async/assassin_journey_fixture.cpp",
                     "tests/async/test_assassin_combat_journey.py",
                     "tests/async/test_flatfile_player_repository.py",
                     "tests/async/flatfile_player_repository_harness.cpp"):
            path = root / name
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            assert source_digest(root) == source_before, name
            assert source_digest(root, RUNTIME_INPUTS) != runtime_before, name
            path.write_bytes(original)
            assert source_digest(root, RUNTIME_INPUTS) == runtime_before, name
        # Baseline verification also pins builder inputs outside src and rejects
        # unexpected compiled files, rather than trusting a qualification-ref.
        tracked = ("src/server.c", "tests/async/test_flatfile_player_repository.py")
        baseline = source_digest(root, tracked)
        builder = root / tracked[1]
        original = builder.read_bytes()
        builder.write_bytes(original + b"changed")
        assert source_digest(root, tracked) != baseline
        builder.write_bytes(original)
        (root / "src/unexpected.c").write_text("untracked source")
        assert source_digest(root) != source_before
        (root / "src/unexpected.c").unlink()
        assert source_digest(root) == source_before
        (root / "bin").mkdir()
        (root / "bin/results.json").write_text("generated result")
        assert source_digest(root, RUNTIME_INPUTS) == runtime_before
    print("Assassin manifest detects configuration, world, recipe and fixture changes")


if __name__ == "__main__":
    main()
