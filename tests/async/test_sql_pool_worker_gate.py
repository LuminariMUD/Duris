#!/usr/bin/env python3
"""Async persistence must not create workers that fall back to one shared DB handle."""
from _paths import SRC
from pathlib import Path

root = Path(__file__).resolve().parents[2]
pool_h = (SRC / "sql_pool.h").read_text()
pool_c = (SRC / "sql_pool.c").read_text()
locker = (SRC / "locker_async.c").read_text()

assert "int sql_pool_is_active(void)" in pool_h
assert "active = pool != NULL" in pool_c
assert "if (!sql_pool_is_active())" in locker

print("pool availability worker-gating checks passed")
