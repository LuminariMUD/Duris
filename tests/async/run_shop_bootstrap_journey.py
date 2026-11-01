#!/usr/bin/env python3
"""Boot a fresh full-world flat-file shop authority, then cold-restart it.

Uses the supplied server and the existing disposable world helpers. No checkout
.env or running game is used. The shop catalog must be created once and remain
byte-identical when restored without trades.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority
from run_world_quest_dual_backend import setup_run_root

ROOT = journey.ROOT


def run(binary, output, areas=None):
    evidence = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'passed': False, 'boots': []}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='shop-bootstrap-') as temporary:
        runtime = Path(temporary)
        _, critical, log = setup_run_root(runtime)
        if areas is not None:
            assert (runtime / 'areas').is_symlink()
            (runtime / 'areas').unlink()
            (runtime / 'areas').symlink_to(areas, target_is_directory=True)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        plain, tls, websocket = journey.available_ports()
        with authority('flatfile', runtime) as (environment, _):
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                               DURIS_WEBSOCKET_PORT=str(websocket))
            try:
                for iteration in range(2):
                    offset = log.stat().st_size if log.exists() else 0
                    with log.open('a') as stream:
                        process = subprocess.Popen([str(binary), '-d', str(runtime), str(plain)], cwd=runtime,
                                                   env=environment, stdout=stream, stderr=subprocess.STDOUT)
                    try:
                        deadline = time.monotonic() + 120
                        while 'Entering game loop.' not in log.read_text(errors='replace')[offset:]:
                            assert process.poll() is None and time.monotonic() < deadline, log.read_text(errors='replace')[-4000:]
                            time.sleep(.1)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            process.wait(timeout=45)
                        assert process.returncode == 0, 'full-world boot/shutdown failed'
                    catalog = runtime / 'state/domains/shopkeeper_catalog'
                    assert catalog.is_file() and catalog.stat().st_size > 0, 'fresh shops have no catalog'
                    digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
                    evidence['boots'].append({'iteration': iteration, 'catalog_sha256': digest, 'catalog_bytes': catalog.stat().st_size})
                    assert digest == evidence['boots'][0]['catalog_sha256'], 'restart rewrote existing stock/revisions'
                    print('[PASS] full-world shop', 'initialization' if iteration == 0 else 'cold restoration', flush=True)
                evidence['passed'] = True
            finally:
                output.write_text(json.dumps(evidence, indent=2))
                if log.exists():
                    output.with_suffix('.log').write_bytes(log.read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--areas', type=Path, help='isolated generated full-world area directory')
    parser.add_argument('--output', type=Path, default=ROOT / 'bin/qualification/shop-bootstrap.json')
    args = parser.parse_args()
    run(args.server.resolve(), args.output.resolve(), args.areas.resolve() if args.areas else None)
