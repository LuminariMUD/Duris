#!/usr/bin/env python3
"""Room-dependent regeneration must not index the world before placement."""

from pathlib import Path
import subprocess
import tempfile

from _paths import SRC, extract_function


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <cassert>

static room_data rooms[2]{};
P_room world = rooms;
extern const int top_of_world = 1;

''' + extract_function('utility.c', 'bool IS_OUTDOORS(') + r'''

int main()
{
    rooms[0].sector_type = SECT_FIELD;
    rooms[1].sector_type = SECT_FIELD;
    rooms[1].room_flags = ROOM_INDOORS;
    assert(!IS_OUTDOORS(-1));
    assert(!IS_OUTDOORS(2));
    assert(IS_OUTDOORS(0));
    assert(!IS_OUTDOORS(1));
}
'''

with tempfile.TemporaryDirectory(prefix='duris-outdoors-bounds-') as directory:
    path = Path(directory)
    source = path / 'test.cpp'
    binary = path / 'test'
    source.write_text(HARNESS)
    subprocess.run(['g++', '-std=c++20', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-I', str(SRC), str(source),
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

print('outdoor room bounds passed under ASan/UBSan')
