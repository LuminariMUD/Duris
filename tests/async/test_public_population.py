#!/usr/bin/env python3
"""Execute the who summary/visibility and both public status producers."""

from _paths import ROOT, SRC, extract_function
from pathlib import Path
import subprocess
import tempfile

who = extract_function("actinf.c", "void do_who(")
start = who.index('\t\t\tchecked_snprintf(\n', who.index('/* No frag food title?'))
end = who.index('\n\t\t}\n\t\tsend_to_char(who_output', start)
summary = who[start:end]
# The command still applies the real visibility rule before constructing its list.
assert 'if (!who_visible_to(ch, tch)' in who
for name in ('curr_ingame_good', 'curr_ingame_evil', 'max_descs_this_hour'):
    assert name not in who

harness = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "persistence/maintenance_snapshot.h"
#include <cassert>
#include <cstring>
#include <string>

int max_descs = 42;
long boot_time = 0;
time_info_data time_info = {};
const char *weekdays[] = { "day", "day", "day", "day", "day", "day", "day" };
const char *month_name[] = { "month" };
time_info_data real_time_passed(time_t, time_t) { return {}; }
void logit(const char *, const char *, ...) { assert(false); }

@MORPH@
@VISIBLE@
@SET_CONTENT@
@STATUS@
@LEGACY@

std::string summary(P_char ch)
{
    char who_output[MAX_STRING_LENGTH] = {};
    int who_list_size = 2, who_gods_size = 1, total_ingame_connections = 8;
    @SUMMARY@
    return who_output;
}

int main()
{
    char_data good = {}, other_good = {}, evil = {}, staff = {};
    for (auto ch : { &good, &other_good, &evil, &staff }) {
        ch->specials.position = STAT_NORMAL;
        ch->player.level = 10;
    }
    GET_RACEWAR(&good) = GET_RACEWAR(&other_good) = RACEWAR_GOOD;
    GET_RACEWAR(&evil) = RACEWAR_EVIL;
    staff.player.level = MAXLVL;
    assert(who_visible_to(&good, &other_good));
    assert(!who_visible_to(&good, &evil));
    assert(who_visible_to(&staff, &evil));
    const auto ordinary = summary(&good);
    assert(ordinary.find("Total visible players: 3") != std::string::npos);
    assert(ordinary.find("connections") == std::string::npos);
    assert(ordinary.find("online") == std::string::npos);
    assert(summary(&staff).find("connections this boot: 42") != std::string::npos);
    assert(summary(&staff).find("Total in-game connections: 8") != std::string::npos);
    for (int peak : { 0, 1, 99 }) {
        max_descs = peak;
        assert(summary(&good) == ordinary);
        maintenance_request request;
        assert(prepare_web_status(request));
        std::string report(request.content.data(), request.content_size);
        assert(report.find("Time elapsed") != std::string::npos);
        assert(report.find("connections") == std::string::npos);
        web_info();
        FILE *file = fopen("lib/reports/status", "r");
        assert(file);
        char content[4096] = {};
        assert(fread(content, 1, sizeof(content) - 1, file) > 0);
        fclose(file);
        assert(std::string(content).find("connections") == std::string::npos);
    }
    puts("public population visibility and report cases passed");
}
'''

for marker, code in {
    '@MORPH@': extract_function('utility.c', 'int IS_MORPH('),
    '@VISIBLE@': extract_function('utility.c', 'bool who_visible_to('),
    '@SET_CONTENT@': extract_function('maintenance_snapshot.c', 'bool set_content('),
    '@STATUS@': extract_function('maintenance_snapshot.c', 'bool prepare_web_status('),
    '@LEGACY@': extract_function('actinf.c', 'void web_info('),
    '@SUMMARY@': summary,
}.items():
    harness = harness.replace(marker, code)

output = ROOT / 'bin/tests'
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='public-population-', dir=output) as directory:
    directory = Path(directory)
    (directory / 'lib/reports').mkdir(parents=True)
    source = directory / 'harness.cpp'
    source.write_text(harness)
    binary = directory / 'harness'
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', f'-I{SRC}',
                    str(source), str(SRC / "safe_format.c"), '-lbsd', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], cwd=directory, check=True)
