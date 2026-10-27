#!/usr/bin/env python3
"""Opt-in input receipts expose dequeue order, never typed arguments or login input."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function, source

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/gmcp.h"
#include "net/comm.h"
#include <cjson/cJSON.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
static std::string sent;
const char *input_command_label(const char *input) {
    return !strncmp(input,"cast ",5) ? "cast" : "unknown";
}
void gmcp_send(P_desc, const char *package, const char *json) {
    assert(std::string(package)=="Char.Input"); sent=json;
}
// PRODUCTION
int main() {
    descriptor_data d{};
    d.connected=CON_PLAYING;
    gmcp_input_receipt(&d,"cast 'secret' victim"); assert(sent.empty());
    d.gmcp_enabled=1;
    gmcp_input_receipt(&d,"cast 'secret' victim"); assert(sent.empty());
    d.gmcp_command_receipts=true;
    gmcp_input_receipt(&d,nullptr);
    assert(sent=="{\"sequence\":0}");
    gmcp_input_receipt(&d,"cast 'secret' victim");
    assert(sent=="{\"sequence\":1,\"command\":\"cast\"}");
    assert(sent.find("secret")==std::string::npos && sent.find("victim")==std::string::npos);
    gmcp_input_receipt(&d,"private-unrecognized-input");
    assert(sent=="{\"sequence\":2,\"command\":\"unknown\"}");
    d.connected=CON_MAIN_MENU; sent.clear();
    gmcp_input_receipt(&d,"password-secret");
    assert(sent.empty() && d.gmcp_input_sequence==2);
    gmcp_input_receipt(&d,nullptr);
    assert(sent=="{\"sequence\":2}"); // renegotiation cannot acknowledge queued input
    d.gmcp_command_receipts=false; sent.clear();
    gmcp_input_receipt(&d,nullptr); assert(sent.empty());
    puts("GMCP input receipts: opt-in, monotonic dequeue sequence, no arguments/login leakage passed");
}
'''

dispatch = extract_function("comm.c", "static void dispatch_session_input(")
playing = dispatch.split("case session_input_route::playing:", 1)[1].split("break;", 1)[0]
assert playing.index("gmcp_input_receipt(descriptor, input)") < playing.index("dispatch_playing_command(character, input)")
assert dispatch.count("gmcp_input_receipt(") == 1
hello = source("gmcp.c").read_text().split("void gmcp_handle_input(", 1)[1].split("/* core gmcp send", 1)[0]
assert 'cJSON_GetObjectItem(root, "commandReceipts")' in hello
assert "cJSON_IsBool(receipts)" in hello and "gmcp_input_receipt(d, nullptr)" in hello
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="gmcp-receipts-", dir=ROOT / "bin/tests") as directory:
    path, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    path.write_text(harness.replace("// PRODUCTION", extract_function("gmcp.c", "void gmcp_input_receipt(")))
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    "-Isrc", str(path), "-lcjson", "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
