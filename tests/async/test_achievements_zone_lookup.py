#!/usr/bin/env python3
"""`achievements zone <area>` finds an area by its name, as the command hands it over."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function

PRELUDE = r'''
#include "core/utils.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <string>
using namespace std;

zone_data zones[2]{};
zone_data *zone_table = zones;
int top_of_zone_table = 1;
'''

CASES = r'''
int main() {
    char winterhaven[] = "&+LThe &+cCity &+Lof &+WWinterhaven&n";
    char alatorin[] = "&+cAlatorin &+L- the Forge City&n";
    zones[0].number = 550;
    zones[0].name = winterhaven;
    zones[1].number = 831;
    zones[1].name = alatorin;
    // one_argument() returns the text after "zone", its leading space included.
    char by_name[] = " the city of winterhaven";
    char by_prefix[] = " alat";
    char by_number[] = " 831";
    char unknown[] = " nowhere";
    char empty[] = "";
    assert(zone_number_from_player_name(by_name) == 550);
    assert(zone_number_from_player_name(by_prefix) == 831);
    assert(zone_number_from_player_name(by_number) == 831);
    assert(zone_number_from_player_name(unknown) == 0);
    assert(zone_number_from_player_name(empty) == 0);
    assert(zone_number_from_player_name(nullptr) == 0);
}
'''


def main() -> None:
    functions = [
        extract_function("sparser.c", "char *skip_spaces("),
        extract_function("interp.c", "bool is_abbrev("),
        extract_function("utility.c", "string strip_ansi("),
        extract_function("achievements.c", "int zone_number_from_player_name("),
    ]
    with tempfile.TemporaryDirectory(prefix="achievements-zone-") as temporary:
        program = Path(temporary) / "harness.cpp"
        program.write_text(PRELUDE + "\n".join(functions) + CASES, encoding="utf-8")
        binary = Path(temporary) / "harness"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                        str(program), "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
    print("achievements zone lookup by area name passed")


if __name__ == "__main__":
    main()
