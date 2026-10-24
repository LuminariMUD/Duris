#!/usr/bin/env python3
"""Execute the real bootstrap, catalog/custody transaction and runtime publication."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, rel

with tempfile.TemporaryDirectory(prefix='duris-shop-bootstrap-') as temporary:
    binary = Path(temporary) / 'bootstrap'
    sources = ['tests/async/flatfile_shopkeeper_bootstrap_harness.cpp'] + [rel(name) for name in (
        'flatfile_shopkeeper_restore.c', 'flatfile_shopkeeper_repository.c', 'flatfile_shopkeeper_ownership.c',
        'flatfile_item_repository.c', 'flatfile_authority_transaction.c', 'flatfile_store.c',
        'player_snapshot_codec.c', 'item_ownership_runtime.c', 'item_claim.c',
        'shop_trade_runtime.c', 'shop_trade_command.c', 'item_transfer_command.c',
        'currency_command.c', 'critical_command.c')]
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Isrc',
                    '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                    '-fno-pie', '-no-pie', *sources, '-Wl,--gc-sections', '-lcrypto', '-pthread',
                    '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary), str(Path(temporary) / 'state')], check=True)
