#!/usr/bin/env python3
"""Run the issue #272 offline capacity/performance gate."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/telemetry"))

from benchmark_272 import DEFAULT_WORKLOADS, Toolchain, build_report, distribution, percentile  # noqa: E402


def test_percentiles() -> None:
    samples = list(range(2000, 0, -1))
    assert distribution(samples) == {
        "sample_count": 2000, "p50_ns": 1000, "p95_ns": 1900,
        "p99_ns": 1980, "p999_ns": 1998,
    }
    assert samples[0] == 2000  # Sorting must not mutate the observations.
    assert percentile(list(range(1, 1002)), 999) == 1000
    assert percentile([], 999) == 0
    assert percentile([17], 999) == 17
    assert percentile([7] * 2000, 999) == 7


def main() -> int:
    test_percentiles()
    repetitions = int(os.environ.get("TELEMETRY_272_REPETITIONS", "3"))
    assert 1 <= repetitions <= 8
    report = build_report(DEFAULT_WORKLOADS, repetitions, Toolchain.discover())
    destination = Path(
        os.environ.get(
            "TELEMETRY_272_REPORT",
            str(ROOT / "bin/tests/telemetry_capacity_272.report.json"),
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert report["gate"]["status"] == "pass", report["gate"]
    assert [item["records"] for item in report["workloads"]] == list(DEFAULT_WORKLOADS)
    for workload in report["workloads"]:
        assert set(workload["modes"]) == {"off", "capture_only", "capture_write"}
        for mode in workload["modes"].values():
            for field in ("p50_ns", "p95_ns", "p99_ns", "p999_ns"):
                assert field in mode
        assert workload["modes"]["capture_write"]["producer_allocation_bytes"] == 0
        assert workload["rollup"]["allocation_bytes"] == workload["rollup"]["peak_python_alloc_bytes"]
        assert workload["report"]["memory_bytes"] == workload["report"]["peak_python_alloc_bytes"]
        assert workload["rollup"]["database_calls"] == 0
        assert workload["report"]["database_calls"] == 0
    print(
        "TELEMETRY_272_CAPACITY_GATE_PASS "
        f"workloads={','.join(str(value) for value in DEFAULT_WORKLOADS)} "
        f"repetitions={repetitions} report={destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
