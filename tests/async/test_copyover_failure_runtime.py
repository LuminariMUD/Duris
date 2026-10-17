#!/usr/bin/env python3
"""Production failure path queues each transport and resumes persistence."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

source = 'copyover.c'

comm = (ROOT / "src/net/comm.c").read_text()
restore = comm[comm.index("\t// copyover recovery - pool must exist first"):comm.index("\t// redis crash recovery - restore world state from redis snapshot")]
sockets = comm[comm.index("\t// use recovered sockets if copyover, otherwise create new ones"):comm.index('\telse\n\t{\n\t\tlogit(LOG_STATUS, "Opening mother connection.")')]
shutdown_case = r"""
#include <thread>
#include <atomic>
static bool recovery_ok=false, entered=false;
static int reboot_requested=0, post_restore=0;
int copyover_recover(int *plain,int *tls,int *ws) {
 *plain=recovery_ok ? 11 : -1; *tls=*ws=-1; return recovery_ok;
}
void copyover_restore_combat() { ++post_restore; }
void calc_zone_mob_level() { ++post_restore; }
void fatal_boot_error(const char *,const char *,...) { std::abort(); }
void logit(const char *,const char *,...) {}
void restored_startup() {
 int copyover_boot=1, recovered_mother_desc=-1, recovered_mother_desc_ssl=-1, recovered_ws_desc=-1;
 int s=-1,S=-1,WS=-1;
#define _reboot reboot_requested
""" + restore + sockets + r"""
#undef _reboot
 entered=true;
 assert(s==11 && S==-1 && WS==-1);
}
void shutdown_regression() {
 std::atomic<bool> stop=false;
 std::thread worker([&] { while(!stop.load()) std::this_thread::yield(); });
 restored_startup(); assert(reboot_requested==1 && !entered && post_restore==0);
 stop=true; worker.join();
 recovery_ok=true; reboot_requested=0;
 restored_startup(); assert(entered && !reboot_requested && post_restore==2);
}
"""

code = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include <cassert>
#include <cstdlib>
#include <string>
#include <vector>
P_desc descriptor_list;
static int resumed = 0;
static std::vector<txt_q *> queued;
void critical_command_coordinator_resume() { ++resumed; }
void critical_outbox_resume() { ++resumed; }
void player_save_pipeline_resume() { ++resumed; }
void write_to_q(const char *text, txt_q *queue, int wrap) {
    assert(std::string(text) == "failed" && wrap == 1);
    queued.push_back(queue);
}
static void raw_write_to_fd(int, const char *) { std::abort(); }
''' + extract_function(source, 'const char *copyover_state_file()') + '\n' + extract_function(source, 'static void notify_copyover_failure(') + r'''
int main() {
    unsetenv("COPYOVER_STATE_FILE");
    assert(std::string(copyover_state_file()) == "copyover.dat");
    setenv("COPYOVER_STATE_FILE", "/var/lib/duris/copyover.dat", 1);
    assert(std::string(copyover_state_file()) == "/var/lib/duris/copyover.dat");
    setenv("COPYOVER_STATE_FILE", "", 1);
    assert(std::string(copyover_state_file()) == "copyover.dat");
    descriptor_data desc[5] = {};
    char_data player = {};
    for (int i=0; i<5; ++i) {
        desc[i].descriptor = 10 + i;
        desc[i].connected = i == 4 ? CON_MAIN_MENU : CON_PLAYING;
        desc[i].character = &player;
        desc[i].next = i == 4 ? nullptr : &desc[i+1];
    }
    desc[1].out_compress = 2;
    desc[2].sslses = reinterpret_cast<gnutls_session_t>(1);
    desc[3].websocket = 1;
    descriptor_list = desc;
    notify_copyover_failure("failed");
    assert(resumed == 3 && queued.size() == 4);
    for (int i=0; i<4; ++i) assert(queued[i] == &desc[i].output);
    puts("copyover state path and queued Telnet/MCCP/TLS/WebSocket failure notices passed");
}
'''
code=code.replace("int main() {", shutdown_case+"\nint main() {\n    shutdown_regression();",1)
with tempfile.TemporaryDirectory(prefix='copyover-failure-') as directory:
    path = Path(directory)
    (path / 'test.cpp').write_text(code)
    subprocess.run(['g++', '-std=c++20', '-g', '-fsanitize=address,undefined', '-pthread', '-Isrc',
                    str(path / 'test.cpp'), '-o', str(path / 'test')], cwd=ROOT, check=True)
    subprocess.run([str(path / 'test')], check=True)
