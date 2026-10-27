#!/usr/bin/env python3
"""The staff target expander keeps percent text literal and stays in bounds."""

from pathlib import Path
import subprocess
import tempfile

from _paths import SRC, extract_function


SOURCE = extract_function('actwiz.c', 'static bool substitute_staff_target(')
HARNESS = r'''
#include <cassert>
#include <cstddef>
#include <cstring>
#include <string>

''' + SOURCE + r'''

int main()
{
    char output[65536];
    assert(substitute_staff_target(output, sizeof output, "look %p", 'p', "Auditor"));
    assert(strcmp(output, "look Auditor") == 0);
    assert(substitute_staff_target(output, sizeof output, "say %p %x %n %%", 'p', "Auditor"));
    assert(strcmp(output, "say Auditor %x %n %%") == 0);

    std::string repeated = "say ";
    for (int i = 0; i < 80; ++i)
        repeated += "%p ";
    assert(substitute_staff_target(output, sizeof output, repeated.c_str(), 'p', "Auditor"));
    assert(std::string(output).find("Auditor Auditor") != std::string::npos);

    char short_output[8];
    assert(!substitute_staff_target(short_output, sizeof short_output,
                                    "say %p", 'p', "Auditor"));
    assert(substitute_staff_target(output, sizeof output, "look %m %x", 'm', "guard"));
    assert(strcmp(output, "look guard %x") == 0);
}
'''

with tempfile.TemporaryDirectory(prefix='duris-staff-template-') as directory:
    path = Path(directory)
    source = path / 'test.cpp'
    binary = path / 'test'
    source.write_text(HARNESS)
    subprocess.run(['g++', '-std=c++20', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-I', str(SRC), str(source),
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

print('staff target substitution passed under ASan/UBSan')
