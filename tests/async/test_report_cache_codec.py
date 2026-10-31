#!/usr/bin/env python3
"""Native cached leaderboard framing; live cap/progress never enters shared text."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, source

HARNESS = r'''
#include "SOURCE"
#include <cassert>
#include <string>
static std::string cached;
char *redis_cache_store_transform(const char *, redis_cache_store_transform_fn transform, void *context)
{
    return transform(cached.c_str(), context);
}
int main()
{
    sql_rows rows = {{{"total", "1", "120"}}, {{"total", "2", "-25"}},
                     {{"top", "Alice", "150"}}, {{"low", "Bob", "-55"}}};
    char *payload = fraglist_cache_payload(rows);
    assert(payload);
    cached = payload;
    free(payload);
    assert(cached.starts_with("FRAGLIST2\n"));
    assert(cached.find("1.20") != std::string::npos && cached.find("-0.25") != std::string::npos);
    assert(cached.find("Alice") != std::string::npos && cached.find("Bob") != std::string::npos);
    for (const char *private_text : {"World level cap", "earned", "acceleration", "opening"})
        assert(cached.find(private_text) == std::string::npos);
    report_cache_enabled = true;
    char *rendered = redis_get_fraglist();
    assert(rendered && std::string(rendered) == cached.substr(10));
    free(rendered);
    cached = "FRC1|old countdown and cap state";
    assert(!redis_get_fraglist());
    cached = "bad";
    assert(!redis_get_fraglist());
}
'''

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="fraglist-cache-", dir=output) as directory:
    probe = Path(directory) / "harness.cpp"
    probe.write_text(HARNESS.replace("SOURCE", str(source("redis_report_cache.c"))))
    binary = Path(directory) / "harness"
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc", "-I/usr/include/mysql",
                    "-ffunction-sections", "-fdata-sections", str(probe), "-Wl,--gc-sections", "-lbsd",
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
print("PASS cached leaderboard totals/rankings, per-viewer exclusion and retired framing rejection")
