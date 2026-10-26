#!/usr/bin/env python3
"""Compile the REAL spell_reflection function from a supplied Duris source and run
an ASan/UBSan memory-ownership regression with fake room, follower and pet runtime.

The fake runtime matches the ownership rules of read_mobile + setup_pet but does
not claim to emulate the complete game server or persistence system.
"""
import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).with_name('reflection_sanitizer_harness.cpp')

def function(source: str) -> str:
    match = re.search(r'void spell_reflection\(int level, P_char ch,', source)
    if not match:
        raise ValueError('spell_reflection signature not found')
    opening = source.index('{', match.start())
    depth = 0
    for index in range(opening,len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if not depth:
                return source[match.start():index+1]+'\n'
    raise ValueError('unbalanced braces in spell_reflection')

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=ROOT/'src/classes/sillusionist.c', help='Actual src/classes/sillusionist.c, or an extracted .inc fixture')
parser.add_argument('--setup-source', type=Path, default=ROOT/'src/classes/necromancy.c', help='Actual src/classes/necromancy.c or the included verified fixture')
parser.add_argument('--expect-failure', action='store_true', help='For baseline demonstration only')
parser.add_argument('--compiler', default=os.environ.get('CXX','g++'))
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='reflection_asan_') as name:
    directory=Path(name)
    (directory/'production.inc').write_text(function(args.source.read_text()))
    setup_source=args.setup_source.read_text()
    start=setup_source.index('int setup_pet(P_char mob, P_char ch, int duration, int flag)')
    # Reuse the same brace-matching extraction logic without relying on regexp-based body slicing.
    setup_part=setup_source[start:]
    depth=0; opening=setup_part.index('{'); end=None
    for index in range(opening,len(setup_part)):
        if setup_part[index]=='{': depth+=1
        elif setup_part[index]=='}':
            depth-=1
            if not depth:
                end=index+1; break
    assert end is not None
    (directory/'setup_pet.inc').write_text(setup_part[:end]+'\n')
    binary=directory/'test_reflection'
    cmd=[args.compiler,'-std=c++20','-O1','-g','-Wall','-Wextra','-Werror',
         '-fsanitize=address,undefined','-fno-omit-frame-pointer',
         '-fno-pie','-no-pie',
         '-DTEST_REFLECTION_INCLUDE="production.inc"',
         '-DTEST_SETUP_PET_INCLUDE="setup_pet.inc"',
         '-I'+str(directory),str(HARNESS),'-o',str(binary)]
    subprocess.run(cmd,check=True)
    result=subprocess.run([str(binary)], capture_output=True,text=True,
                          env={'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'},timeout=50)
    if args.expect_failure:
        if result.returncode == 0:
            raise SystemExit('Unexpected baseline PASS — no sanitizer failure!')
        if 'AddressSanitizer' not in result.stderr:
            raise SystemExit('Baseline failed, but not from an AddressSanitizer finding:\n'+result.stderr[:3000])
        print('EXPECTED baseline ASan failure:\n'+result.stderr[:3700])
    else:
        print(result.stdout[-2500:])
        if result.returncode:
            raise SystemExit('Regression FAILED:\n'+result.stderr[-7000:])
        print('PASS AddressSanitizer + UndefinedBehaviorSanitizer (no memory findings)')
