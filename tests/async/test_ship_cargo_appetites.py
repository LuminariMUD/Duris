#!/usr/bin/env python3
"""Every cargo route pays the same appetite in both directions.

cargo_location_mod[] holds the sailing distances printed by
calculate_port_distances(), so it must be symmetric with a zero diagonal.
Deramuth's row and column were once entered by hand: they matched neither its
distances nor each other, and Deramuth <-> Venan'Trut, the shortest route on
the map, paid like one of the longest.
"""

import re

from _paths import source

text = source("ship_cargo.c").read_text(encoding="utf-8")
body = text[text.index("const int cargo_location_mod[NUM_PORTS][NUM_PORTS] = {") :]
body = body[: body.index("};")]
body = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S)
matrix = [[int(v) for v in row.split(",")] for row in re.findall(r"\{([^{}]*)\}", body)]

ports = len(matrix)
assert ports == 10, ports
for a in range(ports):
    assert len(matrix[a]) == ports, (a, matrix[a])
    assert matrix[a][a] == 0, (a, matrix[a][a])
    for b in range(ports):
        assert matrix[a][b] == matrix[b][a], (a, b, matrix[a][b], matrix[b][a])

DERAMUTH, VENAN_TRUT = 9, 7
assert matrix[DERAMUTH][VENAN_TRUT] == 165
assert min(v for row in matrix for v in row if v) == 165

print("[PASS] cargo appetites are symmetric and Deramuth <-> Venan'Trut pays as the shortest route")
