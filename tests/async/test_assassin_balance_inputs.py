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
                     "tests/async/test_assassin_combat_journey.py"):
            path = root / name
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            assert source_digest(root) == source_before, name
            assert source_digest(root, RUNTIME_INPUTS) != runtime_before, name
            path.write_bytes(original)
            assert source_digest(root, RUNTIME_INPUTS) == runtime_before, name
        (root / "bin").mkdir()
        (root / "bin/results.json").write_text("generated result")
        assert source_digest(root, RUNTIME_INPUTS) == runtime_before
    print("Assassin manifest detects configuration, world, recipe and fixture changes")


if __name__ == "__main__":
    main()
