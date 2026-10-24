#!/usr/bin/env python3
"""Run the actual optional registry lookup with owned files and descriptor checks."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "src/account/account.c").read_text()
start = source.index("bool is_email_taken(")
lookup = source[start:source.index("\nvoid close_account_sessions_named(", start)]
harness = r'''
#include <cassert>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#define ACCOUNT_EMAIL_DB "Accounts/email.db"
#define TRUE true
#define FALSE false
void statuslog(int,const char *,...) {}
// ACTUAL_LOOKUP
size_t descriptors() {
    size_t count=0;
    for(const auto &entry:std::filesystem::directory_iterator("/proc/self/fd")) { (void)entry; ++count; }
    return count;
}
void registry(const std::string &text) {
    std::ofstream file(ACCOUNT_EMAIL_DB); file << text; assert(file.good());
}
int main() {
    std::filesystem::create_directory("Accounts");
#ifdef REQUIRE_EMAIL_VERIFICATION
    registry(""); assert(!is_email_taken("fresh@example.invalid"));
    registry("first@example.invalid\nmatch@example.invalid\nlast@example.invalid\n");
    assert(is_email_taken("match@example.invalid"));
    assert(!is_email_taken("fresh@example.invalid"));
    // Preserve the original whitespace-token matching semantics and exact case.
    registry("  first@example.invalid \t match@example.invalid\r\n");
    assert(is_email_taken("match@example.invalid"));
    assert(!is_email_taken("MATCH@example.invalid"));
    // A corrupt long token cannot overflow a fixed buffer or hide a later entry.
    registry(std::string(4096,'x')+"\nmatch@example.invalid\n");
    assert(is_email_taken("match@example.invalid"));
    assert(!is_email_taken("fresh@example.invalid"));
    const auto before=descriptors();
    for(int n=0;n<1000;++n) {
        assert(is_email_taken("match@example.invalid"));
        assert(!is_email_taken("fresh@example.invalid"));
    }
    assert(descriptors()==before);
    std::filesystem::remove(ACCOUNT_EMAIL_DB);
    assert(is_email_taken("fresh@example.invalid")); // Unavailable registry fails closed.
    std::filesystem::create_directory(ACCOUNT_EMAIL_DB);
    assert(is_email_taken("fresh@example.invalid")); // Read error also fails closed.
#else
    assert(!is_email_taken("fresh@example.invalid"));
    assert(!std::filesystem::exists(ACCOUNT_EMAIL_DB));
#endif
}
'''
with tempfile.TemporaryDirectory(prefix="account-email-registry-") as directory:
    work = Path(directory)
    cpp = work / "test.cpp"
    cpp.write_text(harness.replace("// ACTUAL_LOOKUP", lookup))
    for enabled in (False, True):
        executable = work / ("enabled" if enabled else "disabled")
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                        "-fno-omit-frame-pointer", *(["-DREQUIRE_EMAIL_VERIFICATION"] if enabled else []),
                        str(cpp), "-o", str(executable)], check=True)
        scenario = work / ("enabled-state" if enabled else "disabled-state")
        scenario.mkdir()
        subprocess.run([str(executable)], cwd=scenario, check=True, timeout=10)
print("Actual email registry: EOF, exact matches, whitespace/long tokens, descriptor closure, fail-closed IO and disabled path passed (ASan/UBSan)")
