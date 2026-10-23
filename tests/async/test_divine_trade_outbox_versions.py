#!/usr/bin/env python3
"""Run the real gameplay dispatcher against retained trade payload versions."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function
body=extract_function("net/comm.c", "static critical_outbox_delivery_result\ncritical_gameplay_outbox_delivery(")
harness=r'''#include <cassert>
#include <cstdint>
#include <vector>
enum class critical_outbox_delivery_result {already_delivered,terminal_failure};
struct critical_outbox_record {int destination=10,event_type=1,payload_version=1;std::vector<uint8_t> payload{1};};
struct divine_trade_result {};
constexpr int DIVINE_TRADE_OUTBOX_DESTINATION=10,COLLECTOR_OUTBOX_DESTINATION=11,DIVINE_TRADE_PAYLOAD_VERSION=3;
bool divine_trade_result_decode(const uint8_t *p,size_t n,divine_trade_result *) {return n==1 && *p==1;}
// DISPATCHERS
// BODY
int main() {
 critical_outbox_record r;
 for(int v : {1,2,3}) {r.payload_version=v;assert(critical_gameplay_outbox_delivery(r,nullptr)==critical_outbox_delivery_result::already_delivered);}
 r.payload_version=4;assert(critical_gameplay_outbox_delivery(r,nullptr)==critical_outbox_delivery_result::terminal_failure);
 r.payload_version=2;r.payload.clear();assert(critical_gameplay_outbox_delivery(r,nullptr)==critical_outbox_delivery_result::terminal_failure);
 r.payload={1};r.event_type=2;assert(critical_gameplay_outbox_delivery(r,nullptr)==critical_outbox_delivery_result::terminal_failure);
}
'''
names=("combat_outcome_transaction", "artifact_guild_transaction", "boon_reward_transaction", "zone_touch_transaction", "collector_transaction", "auction_transaction")
stubs="\n".join("critical_outbox_delivery_result "+name+"_outbox_delivery(const critical_outbox_record &,void *) {return critical_outbox_delivery_result::terminal_failure;}" for name in names)
out=ROOT/"bin/tests";out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="trade-outbox-",dir=out) as directory:
    source=Path(directory)/"outbox.cpp";binary=Path(directory)/"outbox"
    source.write_text(harness.replace("// DISPATCHERS",stubs).replace("// BODY",body))
    subprocess.run(["g++","-std=c++20","-include","cstddef","-Wall","-Wextra","-Werror",str(source),"-o",str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
print("PASS actual trade outbox versions 1/2/3 and invalid version/event/framing rejection")
