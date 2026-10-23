#!/usr/bin/env python3
"""Matched performance gates must reject regressions hidden by pooled samples."""
from copy import deepcopy

from run_telemetry_player_journey import verify_performance_pairs


def measurements(pulses):
    return [dict(pair=pair, enabled=enabled, save_p99_us=100,
                 native={"total_tick": {"p99_us": pulse}, "ne_events": {"max_us": 100}})
            for pair, values in enumerate(pulses)
            for enabled, pulse in zip((False, True), values)]


def rejected(rows):
    try:
        verify_performance_pairs(rows)
    except AssertionError:
        return
    raise AssertionError("a regressing matched pair was accepted")


def main():
    # Archived pooled p99 was 630 off / 592 on, but two actual pairs regressed.
    rejected(measurements(((615, 725), (504, 540), (631, 592))))
    passing = measurements(((100, 104), (100, 105), (100, 99)))
    verify_performance_pairs(passing)
    for pair in range(3):
        rows = deepcopy(passing)
        rows[pair * 2 + 1]["native"]["total_tick"]["p99_us"] = 106
        rejected(rows)
        rows = deepcopy(passing)
        rows[pair * 2 + 1]["save_p99_us"] = 106
        rejected(rows)
    print("PASS: every matched pulse/save pair enforces 5%; pooled improvement cannot mask a regression")


if __name__ == "__main__":
    main()
