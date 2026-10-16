#!/usr/bin/env python3
"""Inspect actual write_one_object frames without materializing gameplay objects."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

functions = "\n".join(extract_function("files.c", signature) for signature in (
    "static bool has_serializable_extra_description(P_obj obj)\n{",
    "ulong ObjUniqueFlags(P_obj obj, P_obj control)\n{",
    "int writeObject(P_obj obj, int o_f_flag, ulong o_u_flag, int count, int loc, char *dest_buff)\n{",
    "int write_one_object(P_obj obj, char *dest_buff, int include_persistent_uid)\n{",
))
output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="legacy-identity-", dir=output) as directory:
    source = Path(directory) / "identity.cpp"
    source.write_text((ROOT / "tests/async/legacy_object_identity_harness.cpp").read_text().replace(
        "// LEGACY_WRITER_FUNCTIONS", functions))
    binary = Path(directory) / "identity"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
        "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql",
        str(source), "src/item/legacy_object_identity.c", "src/sql/item_extra_descr_codec.c",
        str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
