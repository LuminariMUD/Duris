#!/usr/bin/env python3
"""Runtime coverage for overlap-safe, checked fixed-buffer formatting."""

from _paths import SRC
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r"""
#include "core/safe_format.h"

#include <stdio.h>
#include <string.h>

int main(void)
{
	char exact[16];
	char overlap[8] = "abc";
	char truncated[5];
	char substituted[32];
	char hostile[32];
	char short_buffer[8];
	const char *values[] = {"Alice", "10 gold"};

	if (checked_snprintf(exact, sizeof exact, "%s-%d", "value", 7) != 7 ||
	    strcmp(exact, "value-7") != 0)
		return 1;
	if (checked_snprintf(overlap, sizeof overlap, "%s-%s", overlap, "defgh") != 9 ||
	    strcmp(overlap, "abc-def") != 0)
		return 2;
	if (checked_snprintf(truncated, sizeof truncated, "%s", "abcdef") != 6 ||
	    strcmp(truncated, "abcd") != 0)
		return 3;
	if (checked_substitute_strings(substituted, sizeof substituted, "%s pays %s (100%%)",
				       values, 2) != 25 ||
	    strcmp(substituted, "Alice pays 10 gold (100%)") != 0)
		return 4;
	if (checked_substitute_strings(hostile, sizeof hostile, "%s says %n %x", values, 1) != 16 ||
	    strcmp(hostile, "Alice says %n %x") != 0)
		return 5;
	if (checked_substitute_strings(short_buffer, sizeof short_buffer, "%s pays", values, 1) !=
		    10 ||
	    strcmp(short_buffer, "Alice p") != 0)
		return 6;
	return 0;
}
"""

with tempfile.TemporaryDirectory(prefix="duris-safe-format-") as temp_dir:
    temp = Path(temp_dir)
    harness = temp / "harness.cpp"
    binary = temp / "harness"
    harness.write_text(HARNESS)
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            f"-I{SRC}",
            str(harness),
            str(SRC / "safe_format.c"),
            "-o",
            str(binary),
        ],
        check=True,
    )
    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
    # The truncated call names its own line and counts bytes with the NUL: "abcdef"
    # needs 7, and the buffer holds 5.
    truncated_line = HARNESS.splitlines().index(
        '\tif (checked_snprintf(truncated, sizeof truncated, "%s", "abcdef") != 6 ||') + 1
    assert (f"harness.cpp:{truncated_line}: checked_snprintf: output requires 7 bytes but "
            "destination holds 5; truncated.") in result.stderr, result.stderr
    assert ("checked_substitute_strings: output requires 11 bytes but destination holds 8; "
            "truncated.") in result.stderr, result.stderr

print("safe formatting runtime tests passed")
