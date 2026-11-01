#!/usr/bin/env python3
"""Execute idle/save/ownership bodies with the real locker writer state machine.

Only unrelated gameplay, transport, item capture and SQL are stubbed. The full
disconnect, item serialization and restart are covered by the MariaDB journey.
"""
import subprocess
from _paths import ROOT, HARNESS_STUBS, extract_function, source

build = ROOT / 'bin/tests/locker-idle-lifecycle'
build.mkdir(parents=True, exist_ok=True)
template = (ROOT / 'tests/async/locker_idle_lifecycle_template.cpp').read_text()
actoth = source('actoth.c').read_text()
start = actoth.index('struct deferred_save_slot\n{')
slot = actoth[start:actoth.index('\n};', start) + 3]
bodies = '\n'.join(extract_function(file, signature) for file, signature in (
    ('account.c', 'const char *get_account_name_safe(P_char ch)'),
    ('storage_lockers.c', 'static bool esc_locker_name_matches_player('),
    ('storage_lockers.c', 'StorageLocker::StorageLocker('),
    ('storage_lockers.c', 'static void locker_handle_postsave('),
    ('utility.c', 'int char_in_list(const P_char ch)'),
    ('storage_lockers.c', 'bool locker_leave_for_extraction('),
    ('handler.c', 'void extract_char_after_terminal_save('),
    ('actoth.c', 'bool persistence_save_character_terminal(P_char ch, int type)'),
    ('actoth.c', 'bool persistence_save_all_characters_terminal(int type)'),
    ('limits.c', 'void point_update(void)'),
))
cpp = build / 'harness.cpp'
cpp.write_text(template.replace('// PRODUCTION_SLOT', slot).replace('// PRODUCTION_BODIES', bodies))
binary = build / 'harness'
subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-Wno-missing-field-initializers', '-pthread',
                '-Isrc', '-I/usr/include/mysql', str(cpp), 'src/persistence/locker_async.c',
                str(HARNESS_STUBS), '-o', str(binary)], cwd=ROOT, check=True)
subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
