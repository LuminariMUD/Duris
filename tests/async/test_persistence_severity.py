#!/usr/bin/env python3
"""Run the production persistence reporter with captured log/broadcast sinks (#176)."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
utility = (ROOT / 'src/core/utility.c').read_text()
header = (ROOT / 'src/core/prototypes.h').read_text()
fight = (ROOT / 'src/combat/fight.c').read_text()
severity = re.search(r'enum class persistence_severity\s*\{.*?\};', header, re.S).group()
reporter = utility[utility.index('static int persistence_alert_format_is_numeric('):
                   utility.index('unsigned long long persistence_next_item_uid(')]
# A 30-second wizlog window is too long to wait out here.
assert reporter.count('std::chrono::seconds(30)') == 2
reporter = reporter.replace('std::chrono::seconds(30)', 'std::chrono::milliseconds(300)')
harness = r'''
#include <cassert>
#include <cctype>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <chrono>
#include <limits>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#define MAX_STRING_LENGTH 256
#define LOG_FILE "file"
#define LOG_WIZ "wiz"
#define checked_snprintf snprintf
struct record { std::string sink, text; };
std::vector<record> logs;
std::vector<std::string> broadcasts;
int audience = 0;
bool persistence_log_submit(const char *text) {
    logs.push_back({LOG_FILE, text});
    logs.push_back({LOG_WIZ, text});
    return true;
}
void wizlog(int level, const char *format, ...) {
    char text[2048]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args);
    audience = level; broadcasts.emplace_back(text);
}
''' + severity + '\n' + reporter + r'''
void verify(const char *outcome, bool alert) {
    assert(logs.size() == 2);
    assert(logs[0].sink == LOG_FILE && logs[1].sink == LOG_WIZ);
    assert(logs[0].text == logs[1].text);
    assert(logs[0].text.find(std::string("outcome=") + outcome) != std::string::npos);
    assert(broadcasts.size() == (alert ? 1u : 0u));
    if (alert) {
        assert(audience == 57);
        assert(broadcasts[0].find("&+R&-LPERSISTENCE:") != std::string::npos);
    }
    for (const auto &row : logs) {
        assert(row.text.find("secret") == std::string::npos);
    }
}
int main() {
    // Each severity reports its own action, so the wizlog does not group them.
    const char *actions[] = {"severity_ok", "severity_info", "severity_alert",
                             "severity_unknown"};
    size_t severity_index = 0;
    for (auto level : {persistence_severity::ok, persistence_severity::info,
                       persistence_severity::alert, static_cast<persistence_severity>(99)}) {
        logs.clear(); broadcasts.clear();
        persistence_report(level, 57, "player_save", "secret_owner", "secret_uid", "none",
                           actions[severity_index], "delay=%d count=%llu", 4, 8ULL);
        verify(level == persistence_severity::ok ? "ok" :
               level == persistence_severity::info ? "info" : "alert",
               level != persistence_severity::ok && level != persistence_severity::info);
        assert(logs[0].text.find("detail=delay=4 count=8") != std::string::npos);
        for (const char *format : {static_cast<const char *>(nullptr), "", "name=%s", "ptr=%p", "write=%n"}) {
            logs.clear(); broadcasts.clear();
            persistence_report(level, 57, "bad category", "secret", "secret", "none",
                               "bad\naction", format, "secret");
            assert(logs[0].text.find("domain=unknown action=unknown") != std::string::npos);
            assert(logs[0].text.find("detail=") == std::string::npos);
        }
        ++severity_index;
    }
    logs.clear(); broadcasts.clear();
    persistence_alert(57, "player_save", "secret", "secret", "secret", "terminal_save_failed", "retry=%d", 1);
    verify("alert", true);
    assert(logs[0].text.find("detail=retry=1") != std::string::npos);

    logs.clear(); broadcasts.clear();
    persistence_alert(57, "corpse", "corpse_owner", "none", "rate_event",
                      "rate_limit_action", "retry=%d", 1);
    assert(broadcasts.size() == 1);
    persistence_alert(57, "corpse", "corpse_owner", "none", "rate_event",
                      "rate_limit_action", "retry=%d", 1);
    assert(broadcasts.size() == 1);
    assert(logs.size() == 4); // throttling only affects wizlog, not durable log records
    // Repeats are grouped by domain and action, whatever their detail, owner or event.
    persistence_alert(57, "corpse", "corpse_owner", "none", "rate_event",
                      "rate_limit_action", "retry=%d", 2);
    persistence_alert(57, "corpse", "different_owner", "none", "other_event",
                      "rate_limit_action", "retry=%d", 3);
    assert(broadcasts.size() == 1);
    assert(logs.size() == 8);
    persistence_alert(57, "corpse", "corpse_owner", "none", "rate_event",
                      "other_action", "retry=%d", 4);
    assert(broadcasts.size() == 2); // another action is its own group
    // The first after the window reports how many were held back.
    std::this_thread::sleep_for(std::chrono::milliseconds(400));
    persistence_alert(57, "corpse", "corpse_owner", "none", "rate_event",
                      "rate_limit_action", "retry=%d", 5);
    assert(broadcasts.size() == 3);
    assert(broadcasts[2].find("detail=retry=5 (suppressed=3 age=") != std::string::npos);
}
'''
with tempfile.TemporaryDirectory(prefix='persistence-severity-') as temp:
    source = Path(temp) / 'reporter.cpp'
    binary = Path(temp) / 'reporter'
    source.write_text(harness)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('[PASS] production reporter routing, fallback severity, legacy alerts, formatting and redaction')
print('[PASS] wizlog repeats are grouped by domain and action and counted')

from contract_text import contains
actoth_source = (ROOT / 'src/cmd/actoth.c').read_text()
# A death saves and leaves at once; a save that cannot be queued alerts where it is queued.
assert 'death_recovery' not in fight and 'terminal_save_failed' not in fight
assert '"queue_failed"' in actoth_source
print('[PASS] a death is quiet; a terminal save that cannot be queued alerts')

for file, snippet in [
    ('src/cmd/actoth.c', 'persistence_report(saved ? persistence_severity::ok : persistence_severity::alert,'),
]:
    assert contains((ROOT / file).read_text(), snippet), file
print('[PASS] other successful persistence operations use ok; paired failures retain alert severity')
