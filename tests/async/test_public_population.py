#!/usr/bin/env python3
"""Execute who visibility, copyover population recovery and public status producers."""

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
assert 'max_descs_this_hour' not in who
recover = extract_function('copyover.c', 'int copyover_recover(')
restore_start = recover.index('\t// restore descriptors')
restore = recover[restore_start:recover.index('\n\tif (header.version >= 15)', restore_start)]

harness = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "persistence/maintenance_snapshot.h"
#include "persistence/copyover.h"
#include "core/mm.h"
#include "net/ttype.h"
#include <cassert>
#include <cstring>
#include <string>
#include <sys/socket.h>
#include <netinet/tcp.h>
#include <unistd.h>

int max_descs = 42;
int max_descs_this_hour = 0;
int max_descs_previous_hour = 0;
bool max_descs_previous_hour_valid = false;
int curr_ingame_good = 0, curr_ingame_evil = 0;
int max_ingame_good = 0, max_ingame_evil = 0;
P_desc descriptor_list = nullptr;
P_char character_list = nullptr;
mm_ds *dead_desc_pool = nullptr;
int used_descs = 0, top_of_world = 0;
char_data restored[6] = {};
long boot_time = 0;
time_info_data time_info = {};
const char *weekdays[] = { "day", "day", "day", "day", "day", "day", "day" };
const char *month_name[] = { "month" };
time_info_data real_time_passed(time_t, time_t) { return {}; }
void logit(const char *, const char *, ...) {}
void *_mm_get(mm_ds *, const char *, int) { return new descriptor_data{}; }
void mm_release(mm_ds *, void *d) { delete static_cast<P_desc>(d); }
void nonblock(int) {}
void check_cp437(P_desc) {}
void account_read(P_desc d, const char *, account_read_done done) { done(d, true, nullptr); }
bool char_to_room(P_char ch, int room, int) { ch->in_room = room; return true; }
void player_load_pets_place(P_char) {}
void epic_bonus_hydrate(P_char) {}
bool start_hatred_check(P_char) { return true; }
void raw_write_to_fd(int, const char *) {}
P_char copyover_load_player(const char *name, P_desc, std::string *) {
    for (auto &ch : restored)
        if (!strcmp(GET_NAME(&ch), name)) return &ch;
    return nullptr;
}

@UPDATE_POPULATION@

bool restore_descriptors(FILE *fp, int count) {
    copyover_header header = {};
    header.num_descriptors = count;
    copyover_desc desc_entry = {};
    P_desc d;
    P_char ch;
    int i, save_room;
    @RESTORE@
    return true;
copyover_recover_fail:
    return false;
}

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
    max_descs_this_hour = 99; // Live socket peak must never appear in who.
    assert(summary(&good) == ordinary);
    const auto trusted = summary(&staff);
    assert(trusted.find("connections this boot: 42") != std::string::npos);
    assert(trusted.find("Total in-game connections: 8") != std::string::npos);
    const std::string last_hour_label =
        "&+rPeak simultaneous connections in the previous completed hour: ";
    for (int peak : { 0, 1, 7 }) {
        max_descs_previous_hour = peak;
        max_descs_previous_hour_valid = true;
        const auto suffix = last_hour_label + std::to_string(peak) + ".&n\n";
        assert(summary(&good) == ordinary + suffix);
        assert(summary(&staff) == trusted + suffix);
        max_descs_this_hour = peak + 100;
        assert(summary(&good) == ordinary + suffix);
    }
    max_descs_previous_hour_valid = false;
    assert(summary(&good) == ordinary);
    for (int good_count : { 0, 1, 7 }) {
        for (int evil_count : { 0, 1, 7 }) {
            curr_ingame_good = good_count;
            curr_ingame_evil = evil_count;
            assert(summary(&good) == ordinary +
                   (evil_count > 0 ? "There are &+Revil(s)&N online.\n" : ""));
            assert(summary(&evil) == ordinary +
                   (good_count > 0 ? "There are &+Ygood(s)&N online.\n" : ""));
            assert(summary(&staff) == trusted);
        }
    }
    curr_ingame_good = curr_ingame_evil = 0;
    // Exercise the production recovery loop with live sockets, both factions,
    // the mortal/staff boundary, an invalid socket and a failed player load.
    FILE *image = tmpfile();
    assert(image);
    int peers[7];
    for (int i = 0; i < 7; ++i) {
        int sockets[2];
        assert(socketpair(AF_UNIX, SOCK_STREAM, 0, sockets) == 0);
        peers[i] = sockets[1];
        copyover_desc entry = {};
        entry.fd = sockets[0];
        snprintf(entry.player_name, sizeof(entry.player_name), "player%d", i);
        if (i < 6) {
            restored[i].player.name = strdup(entry.player_name);
            restored[i].player.level = i < 4 ? MINLVLIMMORTAL - 1 : MINLVLIMMORTAL;
            GET_RACEWAR(&restored[i]) = i % 2 == 0 ? RACEWAR_GOOD : RACEWAR_EVIL;
        }
        assert(fwrite(&entry, sizeof(entry), 1, image) == 1);
    }
    copyover_desc invalid = {};
    invalid.fd = -1;
    assert(fwrite(&invalid, sizeof(invalid), 1, image) == 1);
    rewind(image);
    assert(restore_descriptors(image, 8));
    fclose(image);
    assert(used_descs == 6 && curr_ingame_good == 2 && curr_ingame_evil == 2);
    assert(max_ingame_good == 2 && max_ingame_evil == 2);
    assert(summary(&good) == ordinary + "There are &+Revil(s)&N online.\n");
    assert(summary(&evil) == ordinary + "There are &+Ygood(s)&N online.\n");
    assert(summary(&staff) == trusted);
    for (int i = 0; i < 4; ++i) {
        assert(restored[i].desc && STATE(restored[i].desc) == CON_PLAYING);
        update_ingame_racewar(-GET_RACEWAR(&restored[i]));
    }
    assert(curr_ingame_good == 0 && curr_ingame_evil == 0);
    assert(summary(&good) == ordinary && summary(&evil) == ordinary);
    update_ingame_racewar(RACEWAR_EVIL);
    assert(summary(&good) == ordinary + "There are &+Revil(s)&N online.\n");
    update_ingame_racewar(-RACEWAR_EVIL);
    while (descriptor_list) {
        P_desc d = descriptor_list;
        descriptor_list = d->next;
        close(d->descriptor);
        delete d;
    }
    for (int fd : peers) close(fd);
    for (auto &ch : restored) free(ch.player.name);
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
    '@UPDATE_POPULATION@': extract_function('nanny.c', 'void update_ingame_racewar('),
    '@RESTORE@': restore,
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
