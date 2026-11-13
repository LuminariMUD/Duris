#!/usr/bin/env python3
"""A local test can fix the game's rolls at boot; nothing else can.

Compiles the production src/core/random.c and runs randomize_at_boot() with
DURIS_TEST_RNG_SEED in different environments. With ENVIRONMENT=local the same
seed replays the same rolls and prints the seed; in any other environment, or
with no seed, the generator keeps fresh entropy.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT

HARNESS = r'''
#include "core/prototypes.h"
#include <cstdio>

int main()
{
	randomize_at_boot();
	for (int i = 0; i < 8; i++)
		std::printf("%d ", number(1, 1000000000));
	std::puts("");
}
'''


def rolls(binary, **environment):
    env = {key: value for key, value in os.environ.items()
           if key not in ("DURIS_TEST_RNG_SEED", "ENVIRONMENT")}
    env.update(environment)
    run = subprocess.run([str(binary)], env=env, capture_output=True, text=True, check=True)
    return run.stdout.strip(), run.stderr


(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="rng-boot-seed-", dir=ROOT / "bin/tests") as tmp:
    source = Path(tmp) / "seed.cpp"
    source.write_text(HARNESS)
    binary = source.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=undefined", "-Isrc", "-I/usr/include/mysql",
                    str(source), "src/core/random.c", "-o", str(binary)], cwd=ROOT, check=True)

    first, said = rolls(binary, DURIS_TEST_RNG_SEED="20261113", ENVIRONMENT="local")
    again, _ = rolls(binary, DURIS_TEST_RNG_SEED="20261113", ENVIRONMENT="local")
    other, _ = rolls(binary, DURIS_TEST_RNG_SEED="20261114", ENVIRONMENT="local")
    assert first == again, "the same local seed must replay the same rolls"
    assert first != other, "a different seed must give different rolls"
    assert "RNG seed: 20261113" in said, said

    production, said = rolls(binary, DURIS_TEST_RNG_SEED="20261113", ENVIRONMENT="production")
    assert production != first and "RNG seed" not in said, "production must ignore the seed"
    unseeded, said = rolls(binary, ENVIRONMENT="local")
    assert unseeded != first and "RNG seed" not in said, "no seed keeps fresh entropy"
    zero, said = rolls(binary, DURIS_TEST_RNG_SEED="0", ENVIRONMENT="local")
    assert zero != first and "RNG seed" not in said, "seed 0 means fresh entropy"

print("local test seeds replay rolls; production and unseeded boots stay random")
