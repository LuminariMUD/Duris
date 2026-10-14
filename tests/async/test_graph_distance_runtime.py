#!/usr/bin/env python3
"""Execute real how_close, edge macros and BFS queue at distance/room limits."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

source = (ROOT / 'src/world/graph.c').read_text()
queue = source[source.index('int bfs_cur_marker;'):source.index('// some very specialized versions')]
fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/graph.h"
#include "core/mm.h"
#include <cassert>
#include <climits>
#include <cstdlib>
#include <cstdio>
#include <string>
#include <vector>
const int top_of_world = BFS_MAX_ROOMS + 4;
static std::vector<room_data> rooms(top_of_world + 1);
static std::vector<room_direction_data> exits(top_of_world);
P_room world = rooms.data();
static mm_ds pool{};
static int live, allocated, diagnostics;
static std::string last_log;
mm_ds *mm_create(const char *, size_t size, size_t, unsigned) { pool.size=size; return &pool; }
void *_mm_get(mm_ds *p, const char *, int) { ++live; ++allocated; return std::calloc(1,p->size); }
void mm_release(mm_ds *, void *p) { --live; std::free(p); }
void logit(const char *,const char *format,...) { ++diagnostics; last_log=format; }
''' + queue + extract_function('graph.c','int how_close(') + r'''
static void check(int target,int limit,int expected) {
    const int result=how_close(0,target,limit);
    if (result!=expected) std::fprintf(stderr,"distance target=%d limit=%d got=%d expected=%d\n",target,limit,result,expected);
    assert(result==expected);
    assert(!live && !queue_head && !queue_tail);
}
int main() {
    for (int i=0;i<top_of_world;++i) {
        exits[i].to_room=i+1;
        rooms[i].dir_option[0]=&exits[i];
    }
    bfs_reset_marks();
    check(4,3,BFS_NO_PATH); // Target must not bypass the maximum distance.
    check(2,3,2); check(3,3,3); check(1,0,BFS_NO_PATH); check(1,-1,BFS_NO_PATH);
    check(0,0,0); check(-1,3,BFS_ERROR); check(top_of_world+1,3,BFS_ERROR);
    // Door flags remain eligible; ocean destinations and NOWHERE do not.
    exits[0].exit_info=EX_CLOSED|EX_SECRET|EX_BLOCKED|EX_LOCKED;
    check(1,1,1);
    rooms[1].sector_type=SECT_OCEAN;
    check(1,1,BFS_NO_PATH);
    rooms[1].sector_type=SECT_CITY;
    exits[0].to_room=NOWHERE;
    check(1,1,BFS_NO_PATH);
    exits[0].to_room=1;
    // Large traversal retains its room cap, emits one diagnostic and empties its queue.
    diagnostics=allocated=0;
    check(top_of_world,top_of_world,BFS_ERROR);
    assert(allocated<=static_cast<int>(BFS_MAX_ROOMS)+3);
    assert(diagnostics==1 && last_log.find("BFS_MAX_ROOMS")!=std::string::npos);
    check(1,1,1); // A failed search cannot poison the next search.
    diagnostics=0;
    for(int i=0;i<37;++i) check(4,2,BFS_NO_PATH);
    assert(diagnostics==37); // One line per bounded exit, no diagnostic loop.
    std::puts("PASS real graph: exact distance, zero/negative, room cap, eligibility, queue cleanup and reuse");
}
'''
out=ROOT/'bin/tests'; out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='graph-distance-',dir=out) as temporary:
    cpp,binary=Path(temporary)/'test.cpp',Path(temporary)/'test'
    cpp.write_text(fixture)
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-g','-Isrc',str(cpp),'-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],check=True,timeout=30)
