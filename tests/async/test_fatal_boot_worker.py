#!/usr/bin/env python3
"""The actual fatal boot handler must retain its exit status with live workers."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

harness = r"""
#include "core/prototypes.h"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
std::thread worker;
std::atomic<bool> running{false};
void logit(const char *, const char *, ...) {}
unsigned logcount=0;
// CMDLOG_BODY
// FATAL_BODY
int main(int argc,char **argv) {
 if(argc>1 && !std::strcmp(argv[1],"worker")) {
  worker=std::thread([] { running=true; for(;;) std::this_thread::sleep_for(std::chrono::seconds(1)); });
  while(!running) std::this_thread::yield();
 }
 init_cmdlog();
 if(argc>2 && !std::strcmp(argv[2],"populated")) {
  std::strcpy(cmdlog_lines[0],"safe_command\n"); logcount=1;
 }
 if(argc>1 && !std::strcmp(argv[1],"ordinary")) return 0;
 if(argc>1 && !std::strcmp(argv[1],"signal")) {
  std::signal(SIGTERM, [](int number) { write_cmdlog(); _Exit(128+number); });
  std::raise(SIGTERM);
 }
 std::fputs("startup output before failure\n",stdout);
 fatal_boot_error("fixture_boot","invalid handoff %d",42);
}
"""
debug=(ROOT/'src/core/debug.c').read_text()
ring=debug[debug.index('#define CMDLOG_LINES'):debug.index('// Makes only calls a signal handler')]
harness=harness.replace('// CMDLOG_BODY',ring+extract_function('debug.c','void write_cmdlog(')+'\n'+extract_function('debug.c','void write_boot_cmdlog(')+'\n'+extract_function('debug.c','void init_cmdlog('))
harness=harness.replace('// FATAL_BODY',extract_function('common.c','static void fatal_message_v(')+'\n'+extract_function('common.c','void fatal_boot_error('))
with tempfile.TemporaryDirectory(prefix='duris-fatal-worker-') as directory:
 source=Path(directory)/'fatal.cpp'; binary=Path(directory)/'fatal'
 source.write_text(harness)
 subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-Isrc',str(source),'-pthread','-o',str(binary)],cwd=ROOT,check=True)
 runtime=Path(directory)/'runtime'; (runtime/'logs/log').mkdir(parents=True)
 for worker in ('none','worker'):
  for ring_state in ('empty','populated'):
   command_log=runtime/'logs/log/cmd.debug'; command_log.write_text('previous startup\n')
   arguments=[worker,ring_state]
   result=subprocess.run([str(binary),*arguments],cwd=runtime,capture_output=True,text=True,timeout=5)
   assert result.returncode==1,(arguments,result.returncode,result.stdout,result.stderr)
   assert result.stdout=='startup output before failure\n',result.stdout
   assert result.stderr=='fixture_boot: invalid handoff 42\n',result.stderr
   assert command_log.read_text()==('safe_command\n' if ring_state=='populated' else 'previous startup\n'),arguments
 for mode in ('ordinary','signal'):
  for ring_state in ('empty','populated'):
   command_log=runtime/'logs/log/cmd.debug'; command_log.write_text('previous process commands\n')
   result=subprocess.run([str(binary),mode,ring_state],cwd=runtime,capture_output=True,text=True,timeout=5)
   assert result.returncode==(0 if mode=='ordinary' else 143),(mode,result.returncode)
   assert command_log.read_text()==('safe_command\n' if ring_state=='populated' else ''),(mode,ring_state)
print('actual fatal boot status, console and command-ring diagnostics with live/static workers passed')
